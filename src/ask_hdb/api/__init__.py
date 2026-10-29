"""Web API around the agent: stateless, streams tool evidence, stores nothing about visitors."""

import asyncio
import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from ask_hdb import agent
from ask_hdb.api import amenities, buildings, mapdata
from ask_hdb.api.points import map_actions, map_points

NOTICE = ("Information only, not financial advice. Figures come from HDB data and rules with the dates shown; "
          "check anything you act on with HDB.")
MAX_HISTORY = 12


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=2000)


class Selected(BaseModel):
    kind: Literal["block", "mrt", "lrt", "primary_school", "bto"]
    id: str = Field(max_length=80)


class Context(BaseModel):
    selected: Selected | None = None


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    history: list[Turn] = Field(default_factory=list, max_length=MAX_HISTORY)
    context: Context = Field(default_factory=Context)


class Limits:
    """In-memory guards: requests per visitor per minute, one run at a time, tokens per day.

    shortcut: counters live in this process, so they reset on restart and do not span several workers;
    move them to a shared store if the app ever runs more than one worker.
    """

    def __init__(self, per_minute=None):
        # /chat reads its own setting; other routes pass their own number.
        self.per_minute = per_minute if per_minute is not None else int(os.getenv("API_RATE_PER_MINUTE", "6"))
        self.daily_tokens = int(os.getenv("API_DAILY_TOKEN_CAP", "2000000"))
        self.hits = defaultdict(deque)
        self.day, self.used = time.strftime("%Y-%m-%d"), 0
        self.busy = Lock()  # held by the model thread itself, so a dropped client cannot free it early
        self.counting = Lock()
        self.window = Lock()  # /route calls allow() from worker threads
        # A second visitor may wait this many seconds for the model, behind at most `queue_max` others.
        self.queue_wait = float(os.getenv("API_QUEUE_WAIT", "0"))
        self.queue_max, self.waiting = 3, 0

    def allow(self, visitor, now=None):
        with self.window:
            return self._allow(visitor, now)

    def _allow(self, visitor, now):
        now = time.time() if now is None else now
        recent = self.hits[visitor]
        while recent and now - recent[0] > 60:
            recent.popleft()
        if len(recent) >= self.per_minute:
            return False
        recent.append(now)
        for other, times in list(self.hits.items()):  # forget idle visitors so the table cannot grow forever
            while times and now - times[0] > 60:
                times.popleft()
            if not times:
                del self.hits[other]
        return True

    async def take_turn(self):
        """Get the one model slot: at once, or after a short wait in a small queue. False means try again later."""
        if self.busy.acquire(blocking=False):
            return True
        with self.counting:
            if self.queue_wait <= 0 or self.waiting >= self.queue_max:
                return False
            self.waiting += 1
        try:
            return await asyncio.to_thread(self.busy.acquire, True, self.queue_wait)
        finally:
            with self.counting:
                self.waiting -= 1

    def over_cap(self):
        with self.counting:
            today = time.strftime("%Y-%m-%d")
            if today != self.day:
                self.day, self.used = today, 0
            return self.used >= self.daily_tokens

    def add_tokens(self, tokens):
        with self.counting:
            self.used += tokens or 0


def sse(event):
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


def warm():
    """Load the data tables and compress the outlines once, so the first visitor does not wait for them."""
    try:
        mapdata.features()
        mapdata.card(mapdata.resolve({"kind": "block", "id": mapdata.load_blocks().block_id.iloc[0]}))
        buildings.zipped(), buildings.etag()
    except (OSError, ValueError, KeyError):  # a missing data file must not stop the app; the endpoints report it themselves
        return


@asynccontextmanager
async def lifespan(app):
    Thread(target=warm, daemon=True).start()
    yield


def create_app():
    app = FastAPI(title="Ask HDB", docs_url=None, redoc_url=None, lifespan=lifespan)
    limits = Limits()
    app.state.limits = limits

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.include_router(buildings.router)
    app.include_router(amenities.router)

    @app.get("/map/features")
    def map_features():
        return JSONResponse(mapdata.features(), headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/map/metrics")
    def map_metrics(flat_type: str):
        if flat_type not in mapdata.METRIC_FLAT_TYPES:
            raise HTTPException(404, "Unsupported flat type.")
        return JSONResponse(mapdata.metrics(flat_type), headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/around/{kind}/{key}")
    def around(kind: str, key: str, km: float):
        selection = mapdata.resolve({"kind": kind, "id": key})
        if selection is None or km not in mapdata.RADII_KM:
            raise HTTPException(404, "Unknown place or radius.")
        return mapdata.around(selection, km)

    @app.get("/schools/{kind}/{key}")
    def schools(kind: str, key: str):
        selection = mapdata.resolve({"kind": kind, "id": key})
        if selection is None:
            raise HTTPException(404, "Unknown place.")
        return mapdata.schools_nearby(selection)

    @app.get("/card/{kind}/{key}")
    def card(kind: str, key: str):
        selection = mapdata.resolve({"kind": kind, "id": key})
        if selection is None:
            raise HTTPException(404, "Unknown place.")
        return mapdata.card(selection)

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
        if not await limits.take_turn():
            raise HTTPException(503, "Busy with other questions. Please try again in a moment.")
        history = [(HumanMessage if turn.role == "user" else AIMessage)(content=turn.content)
                   for turn in body.history]
        events, left = Queue(), Event()
        line = mapdata.context_line(mapdata.resolve(body.context.selected.model_dump() if body.context.selected else None))
        Thread(target=work, args=(body.question, history, limits, events, left, line), daemon=True).start()
        return StreamingResponse(stream(events, left), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-store"})

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-cache")  # a redeploy must not run an old app.js
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: blob:; connect-src 'self' https://tile.openstreetmap.org; "
            "frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        return response

    # Mounted last so the API routes win; the page and its script are plain files.
    app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
    return app


class ClientLeft(Exception):
    """Raised inside the model thread once the visitor has disconnected, to stop spending tokens."""


def work(question, history, limits, events, left, context=None):
    spent = 0

    def on_event(event):
        nonlocal spent
        if left.is_set():
            raise ClientLeft
        if event["type"] == "usage":
            spent = event["tokens"]
        else:
            events.put({k: v for k, v in event.items() if k != "args"} if event["type"] == "tool_result" else event)
            if event["type"] == "tool_result":
                try:
                    points = map_points(event["args"], event["result"])
                except Exception:  # noqa: BLE001 - a missing map point must never break an answer
                    points = []
                if points:
                    events.put({"type": "map", "actions": map_actions(points)})
                result = event["result"]
                if event["name"] == "resolve_place" and isinstance(result, dict) and result.get("status") == "ambiguous":
                    events.put({"type": "choices", "candidates": result["candidates"]})

    try:
        result = agent.ask(question, history, confirm=True, on_event=on_event, context=context)
        events.put({"type": "answer", "answer": result["answer"],
                    "needs_confirmation": result["needs_confirmation"],
                    "stopped_reason": result["stopped_reason"], "notice": NOTICE})
    except ClientLeft:
        pass
    except Exception:  # noqa: BLE001 - never leak provider text, URLs or keys to a visitor
        events.put({"type": "error", "message": "The model call failed. Please try again."})
    finally:
        limits.add_tokens(spent)  # also when the run failed or the visitor left
        events.put(DONE)
        limits.busy.release()


DONE = object()


async def stream(events, left):
    try:
        while True:
            try:
                event = events.get_nowait()
            except Empty:
                await asyncio.sleep(0.05)
                continue
            if event is DONE:
                return
            yield sse(event)
    finally:
        left.set()  # a visitor who leaves stops the run at its next model or tool step


app = create_app()
