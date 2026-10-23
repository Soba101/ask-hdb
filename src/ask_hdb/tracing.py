"""Optional Langfuse tracing, off unless both keys are set.

Visitor text is private: unless TRACE_TEXT=1 every input, output and metadata value is replaced by a placeholder, and error
messages (which can quote tool arguments the visitor's text produced) are dropped from the exported spans, so traces keep only
structure: which tools ran, timings, token counts and whether a step failed.
Install with `uv sync --extra tracing`; the app runs without the package.
"""

import os

REDACTED = "[redacted]"


def enabled():
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


def mask(data=None, **kwargs):
    """Langfuse mask function: keep the text only when the operator asked for it."""
    return data if os.getenv("TRACE_TEXT") == "1" else REDACTED


STATUS_MESSAGE = "langfuse.observation.status_message"


def mask_otel_spans(*, params):
    """Export-stage masking: Langfuse's `mask` does not cover error messages, so drop them here."""
    if os.getenv("TRACE_TEXT") == "1":
        return None
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    patches = {identifier: OtelSpanPatch(delete_attributes=(STATUS_MESSAGE,))
               for identifier, span in params.spans.items() if STATUS_MESSAGE in (span.attributes or {})}
    return MaskOtelSpansResult(span_patches=patches) if patches else None


def callbacks():
    """LangChain callbacks for one run; empty when tracing is off or the package is missing."""
    if not enabled():
        return []
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        return []
    Langfuse(mask=mask, mask_otel_spans=mask_otel_spans)  # configures the client used by the handler (host and keys come from the environment)
    return [CallbackHandler()]
