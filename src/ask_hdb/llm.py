"""Choose a chat client without exposing credentials to the agent."""

import os
import threading
import time
from collections import deque

import openai
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import ChatGoogleGenerativeAIError
from langchain_openai import ChatOpenAI

# Hosted free-tier providers: (key variables, model variable, default model). Gemini 3 needs its own client because the
# OpenAI-style endpoint drops the thought signatures that tool calls must carry; the others use an OpenAI-style endpoint.
HOSTED = {
    "gemini": (("GEMINI_API_KEY",), "GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "groq": (("GROQ_API_KEY",), "GROQ_MODEL", "openai/gpt-oss-120b"),
    "openrouter": (("OPENROUTER_API_KEY", "OPENROUTER"), "OPENROUTER_MODEL", "openrouter/free"),
}
ENDPOINTS = {"groq": "https://api.groq.com/openai/v1", "openrouter": "https://openrouter.ai/api/v1"}
# A rate limit, an outage, a timeout or a rejected request moves on to the next provider in the chain.
FALLBACK_ON = (openai.OpenAIError, ChatGoogleGenerativeAIError)


def _single():
    provider = os.getenv("LLM_PROVIDER", "local").lower()
    options = {"model": os.getenv("LLM_MODEL", "qwen3.5-9b-16k"), "temperature": 0,
               "timeout": float(os.getenv("LLM_TIMEOUT", "180")), "max_retries": 0}
    key = os.getenv("LLM_API_KEY")
    url = os.getenv("LLM_BASE_URL")
    if provider == "local":
        # Thinking tokens made a 9B model slow and sloppy on tool calls; turn them off.
        options["reasoning_effort"] = os.getenv("LLM_REASONING_EFFORT", "none")
        return ChatOpenAI(**options, base_url=url or os.getenv("LOCAL_LLM_URL", "http://localhost:11434/v1"),
                          api_key=key or "none")
    if provider == "openai":
        return ChatOpenAI(**options, **({"api_key": key} if key else {}),
                          **({"base_url": url} if url else {}))
    if provider == "anthropic":
        return ChatAnthropic(**options, **({"api_key": key} if key else {}),
                             **({"base_url": url} if url else {}))
    raise ValueError("LLM_PROVIDER must be local, openai or anthropic")


def _hosted(name):
    """One free-tier provider from the chain: `gemini` or `gemini:other-model`. None when its key is missing."""
    provider, _, model = name.partition(":")
    if provider not in HOSTED:
        raise ValueError(f"LLM_CHAIN entry {name!r}: use local, {', '.join(HOSTED)}, optionally as name:model")
    key_names, model_name, default = HOSTED[provider]
    key = next((os.getenv(n) for n in key_names if os.getenv(n)), None)
    if not key:
        return None  # no key yet: skip this provider rather than fail
    model = model or os.getenv(model_name, default)
    timeout = float(os.getenv("LLM_HOSTED_TIMEOUT", "60"))
    rpm = int(os.getenv(f"{provider.upper()}_RPM", RPM[provider]))
    if provider == "gemini":
        return Member(ChatGoogleGenerativeAI(model=model, google_api_key=key, temperature=0, max_retries=0, timeout=timeout),
                      {"max_tokens": "max_output_tokens"}, rpm)
    return Member(ChatOpenAI(model=model, temperature=0, base_url=ENDPOINTS[provider], api_key=key, timeout=timeout,
                             max_retries=0), rpm=rpm)


# Calls per minute each free tier allows (Gemini's free tier said 5 for one model; OpenRouter says 20 for :free models).
# Override with GEMINI_RPM, GROQ_RPM or OPENROUTER_RPM; 0 turns the pacing off.
RPM = {"gemini": 5, "groq": 30, "openrouter": 20}


class Member:
    """One provider in the chain, with the names its client uses for settings the agent sets in OpenAI terms.
    A provider with a per-minute budget is skipped while the budget is used up, or waited for when it is the only one."""

    def __init__(self, model, rename=None, rpm=0):
        self.model, self.rename, self.rpm = model, rename or {}, rpm
        self.times, self.lock = deque(), threading.Lock()

    def wait(self, now=None):
        """Seconds until a call is allowed; 0 means now."""
        if not self.rpm:
            return 0
        now = time.time() if now is None else now
        with self.lock:
            while self.times and now - self.times[0] >= 60:
                self.times.popleft()
            return 0 if len(self.times) < self.rpm else 60 - (now - self.times[0])

    def note(self, now=None):
        with self.lock:
            self.times.append(time.time() if now is None else now)

    def adapt(self, kwargs):
        return {self.rename.get(name, name): value for name, value in kwargs.items()}


class Bound:
    """A call to the chain: tools and settings are applied to each provider, which are tried in order."""

    def __init__(self, members, tools=None, settings=None):
        self.members, self.tools, self.settings = members, tools, settings or {}

    def bind(self, **kwargs):
        return Bound(self.members, self.tools, {**self.settings, **kwargs})

    def invoke(self, messages, config=None, **kwargs):
        last = None
        for position, member in enumerate(self.members):
            pause = member.wait()
            if pause and position < len(self.members) - 1:
                continue  # this tier's minute is used up: let the next provider take the call
            if pause:
                time.sleep(pause)  # the last resort: waiting beats failing
            member.note()
            model = member.model.bind_tools(self.tools) if self.tools else member.model
            try:
                return model.invoke(messages, config, **member.adapt({**self.settings, **kwargs}))
            except FALLBACK_ON as error:
                last = error
            except ValueError as error:
                # OpenRouter can answer 200 with an error body (an upstream outage); the client raises it as a ValueError.
                if not (error.args and isinstance(error.args[0], dict) and "code" in error.args[0]):
                    raise
                last = error
        raise last


class Chain:
    """Providers tried in order. Each call goes to the first one that answers; the rest are fallbacks."""

    def __init__(self, members):
        self.members = members

    def bind_tools(self, tools):
        return Bound(self.members, tools)

    def bind(self, **kwargs):
        return Bound(self.members, None, kwargs)


def get_chat_model():
    load_dotenv()
    names = [n.strip() for n in os.getenv("LLM_CHAIN", "").split(",") if n.strip()]
    if not names:
        return _single()
    members = [Member(_single()) if name == "local" else _hosted(name) for name in names]
    members = [member for member in members if member is not None]
    if not members:
        raise ValueError("LLM_CHAIN lists no usable provider (missing keys?)")
    return Chain(members)
