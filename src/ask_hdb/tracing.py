"""Optional Langfuse tracing, off unless both keys are set.

Visitor text is private: unless TRACE_TEXT=1 every input and output is replaced by a placeholder before it leaves
the process, so traces keep only structure (which tools ran, timings, token counts, errors).
Install with `uv sync --extra tracing`; the app runs without the package.
"""

import os

REDACTED = "[redacted]"


def enabled():
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def mask(data=None, **kwargs):
    """Langfuse mask function: keep the text only when the operator asked for it."""
    return data if os.getenv("TRACE_TEXT") == "1" else REDACTED


def callbacks():
    """LangChain callbacks for one run; empty when tracing is off or the package is missing."""
    if not enabled():
        return []
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        return []
    Langfuse(mask=mask)  # configures the client used by the handler (host and keys come from the environment)
    return [CallbackHandler()]
