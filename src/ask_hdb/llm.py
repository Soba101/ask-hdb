"""Choose a chat client without exposing credentials to the agent."""

import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI


def get_chat_model():
    load_dotenv()
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
