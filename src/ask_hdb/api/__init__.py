"""Web API around the agent: stateless, streams tool evidence, stores nothing about visitors."""

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from queue import Empty, Queue
from threading import Thread
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from ask_hdb import agent

NOTICE = ("Information only, not financial advice. Figures come from HDB data and rules with the dates shown; "
          "check anything you act on with HDB.")
MAX_HISTORY = 12


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=MAX_HISTORY)


class Limits:
    """In-memory guards: requests per visitor per minute, one run at a time, tokens per day.

    shortcut: counters live in this process, so they reset on restart and do not span several workers;
    move them to a shared store if the app ever runs more than one worker.
    """

    def __init__(self):
        self.per_minute = int(os.getenv("API_RATE_PER_MINUTE", "6"))
        self.daily_tokens = int(os.getenv("API_DAILY_TOKEN_CAP", "2000000"))
        self.hits = defaultdict(deque)
        self.day, self.used = time.strftime("%Y-%m-%d"), 0
        self.busy = asyncio.Lock()

    def allow(self, visitor, now=None):
        now = time.time() if now is None else now
        recent = self.hits[visitor]
        while recent and now - recent[0] > 60:
            recent.popleft()
        if len(recent) >= self.per_minute:
            return False
        recent.append(now)
        return True

    def over_cap(self):
        today = time.strftime("%Y-%m-%d")
        if today != self.day:
            self.day, self.used = today, 0
        return self.used >= self.daily_tokens

    def add_tokens(self, tokens):
        self.used += tokens or 0


def sse(event):
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def create_app():
    app = FastAPI(title="Ask HDB", docs_url=None, redoc_url=None)
    limits = Limits()
    app.state.limits = limits

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/chat")
    async def chat(body: ChatRequest, request: Request):
        visitor = request.client.host if request.client else "unknown"
        if not limits.allow(visitor):
            raise HTTPException(429, "Too many questions. Please wait a minute.")
        if limits.over_cap():
            raise HTTPException(429, "Today's usage limit has been reached. Please come back tomorrow.")
        if limits.busy.locked():
            raise HTTPException(503, "Busy with another question. Please try again in a moment.")
        history = [(HumanMessage if turn.role == "user" else AIMessage)(content=turn.content)
                   for turn in body.history]
        return StreamingResponse(stream(body.question, history, limits), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store"})

    return app


async def stream(question, history, limits):
    async with limits.busy:
        events = Queue()
        done = object()

        def work():
            try:
                result = agent.ask(question, history, confirm=True, on_event=events.put)
                events.put({"type": "answer", "answer": result["answer"],
                            "needs_confirmation": result["needs_confirmation"],
                            "stopped_reason": result["stopped_reason"], "notice": NOTICE})
                limits.add_tokens(result.get("tokens"))
            except Exception as exc:  # noqa: BLE001 - never leak provider text, URLs or keys to a visitor
                events.put({"type": "error", "message": "The model call failed. Please try again.",
                            "kind": type(exc).__name__})
            finally:
                events.put(done)

        Thread(target=work, daemon=True).start()
        while True:
            try:
                event = events.get_nowait()
            except Empty:
                await asyncio.sleep(0.05)
                continue
            if event is done:
                return
            yield sse(event)


app = create_app()
