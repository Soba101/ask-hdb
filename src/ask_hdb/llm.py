"""Choose a chat client without exposing credentials to the agent."""

import os

import openai
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Hosted providers with an OpenAI-style endpoint: (base URL, key variable, model variable, default model).
HOSTED = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-3.5-flash"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "GROQ_MODEL", "openai/gpt-oss-120b"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL", "openrouter/free"),
}
# A rate limit, an outage, a timeout or a rejected request moves on to the next provider in the chain.
FALLBACK_ON = (openai.OpenAIError,)


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
    """One free-tier provider from the chain: `gemini` or `gemini:other-model`."""
    provider, _, model = name.partition(":")
    if provider not in HOSTED:
        raise ValueError(f"LLM_CHAIN entry {name!r}: use local, {', '.join(HOSTED)}, optionally as name:model")
    url, key_name, model_name, default = HOSTED[provider]
    key = os.getenv(key_name)
    if not key:
        return None  # no key yet: skip this provider rather than fail
    return ChatOpenAI(model=model or os.getenv(model_name, default), temperature=0, base_url=url, api_key=key,
                      timeout=float(os.getenv("LLM_HOSTED_TIMEOUT", "60")), max_retries=0)


class Chain:
    """Providers tried in order. Each call goes to the first one that answers; the rest are fallbacks."""

    def __init__(self, models):
        self.models = models

    def _wrap(self, runnables):
        first, *rest = runnables
        return first.with_fallbacks(rest, exceptions_to_handle=FALLBACK_ON) if rest else first

    def bind_tools(self, tools):
        return self._wrap([model.bind_tools(tools) for model in self.models])

    def bind(self, **kwargs):
        return self._wrap([model.bind(**kwargs) for model in self.models])


def get_chat_model():
    load_dotenv()
    names = [n.strip() for n in os.getenv("LLM_CHAIN", "").split(",") if n.strip()]
    if not names:
        return _single()
    models = [_single() if name == "local" else _hosted(name) for name in names]
    models = [model for model in models if model is not None]
    if not models:
        raise ValueError("LLM_CHAIN lists no usable provider (missing keys?)")
    return Chain(models) if len(models) > 1 else models[0]
