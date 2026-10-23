"""Optional Langfuse tracing, off unless both keys are set.

Visitor text is private: unless TRACE_TEXT=1 every input, output and metadata value is replaced by a placeholder, and error
messages (which can quote tool arguments the visitor's text produced) are dropped from the exported spans, so traces keep only
structure: which tools ran, timings, token counts and whether a step failed.
Install with `uv sync --extra tracing`; the app runs without the package.
One visitor question is one trace (`turn`). No user or session id is set: the app keeps nothing that links questions.
Every tracing step swallows its own errors, so tracing can never break or fail an answer.
"""

import os
from contextlib import ExitStack, contextmanager, suppress
from functools import cache

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


def _client():
    from langfuse import Langfuse

    return Langfuse(mask=mask, mask_otel_spans=mask_otel_spans)  # same singleton the callback handler uses


@cache
def _version():
    from importlib.metadata import version

    with suppress(Exception):
        return version("ask-hdb")


class _Turn:
    """Handed to `ask()`; `record` adds the answer and the scores once the result exists."""

    def __init__(self, client=None, root=None):
        self.client, self.root = client, root

    def record(self, question, result):
        if self.root is None:
            return
        with suppress(Exception):  # tracing must never break an answer
            grounding = result.get("grounding") or {}
            calls = len(result.get("tool_calls") or [])
            stopped = result.get("stopped_reason")
            # Input and output go through the mask, so they read [redacted] unless TRACE_TEXT=1.
            # Token and tool-call counts are not set as metadata: the mask would hide them, so the scores and the generation usage carry them.
            self.root.update(input=question, output=result.get("answer"))
            scores = [("stopped", bool(stopped), "BOOLEAN"), ("tool_calls", calls, "NUMERIC")]
            if grounding:  # absent when the run stopped or asked for confirmation
                scores += [("grounded", not grounding.get("ungrounded"), "BOOLEAN"),
                           ("ungrounded_numbers", len(grounding.get("ungrounded") or []), "NUMERIC"),
                           ("grounding_rewritten", bool(grounding.get("rewritten")), "BOOLEAN")]
            for name, value, kind in scores:  # numbers only, never a comment
                self.client.create_score(name=name, value=float(value), data_type=kind,
                                         trace_id=self.root.trace_id)


@contextmanager
def turn(source):
    """One trace for one visitor question, however many graph runs it takes. A no-op when tracing is off."""
    stack, t = ExitStack(), _Turn()
    if enabled():
        try:
            from langfuse import propagate_attributes

            client = _client()
            model = os.getenv("LLM_MODEL")
            meta = {"tool_source": source, **({"model": model} if model else {})}
            version = _version()
            stack.enter_context(propagate_attributes(
                trace_name="answer-question", tags=["ask-hdb", f"tools-{source}"], metadata=meta,
                **({"version": version} if version else {})))
            t = _Turn(client, stack.enter_context(
                client.start_as_current_observation(name="answer-question", as_type="agent")))
        except Exception:  # noqa: BLE001 - a broken tracing setup means no tracing, not a failed answer
            t = _Turn()
            with suppress(Exception):
                stack.close()
    try:
        yield t
    except BaseException:
        if t.root is not None:
            with suppress(Exception):
                t.root.update(level="ERROR")  # no message: error text can quote visitor input
        raise
    finally:
        with suppress(Exception):
            stack.close()
