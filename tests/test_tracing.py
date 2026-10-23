"""Tracing is off by default, never sends visitor text unless asked, and never breaks the app."""

import sys
import types

from ask_hdb import tracing


def test_off_without_both_keys(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    assert tracing.callbacks() == []
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    assert tracing.callbacks() == []  # one key is not enough


def test_text_is_masked_unless_the_operator_opts_in(monkeypatch):
    monkeypatch.delenv("TRACE_TEXT", raising=False)
    assert tracing.mask(data="Can we buy a flat? income 4400") == tracing.REDACTED
    assert tracing.mask({"question": "private"}) == tracing.REDACTED
    monkeypatch.setenv("TRACE_TEXT", "1")
    assert tracing.mask(data="kept") == "kept"


def test_with_keys_the_handler_is_returned_and_the_mask_is_installed(monkeypatch):
    seen = {}
    langfuse = types.ModuleType("langfuse")
    langfuse.Langfuse = lambda **kwargs: seen.update(kwargs)
    lc = types.ModuleType("langfuse.langchain")
    lc.CallbackHandler = lambda: "handler"
    monkeypatch.setitem(sys.modules, "langfuse", langfuse)
    monkeypatch.setitem(sys.modules, "langfuse.langchain", lc)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    assert tracing.callbacks() == ["handler"] and seen["mask"] is tracing.mask
    assert seen["mask_otel_spans"] is tracing.mask_otel_spans


def test_a_missing_package_means_no_tracing_not_a_crash(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setitem(sys.modules, "langfuse", None)  # makes `import langfuse` raise ImportError
    assert tracing.callbacks() == []


def test_error_messages_are_dropped_from_exported_spans_unless_text_is_allowed(monkeypatch):
    from types import SimpleNamespace

    from langfuse.types import MaskOtelSpansParams  # noqa: F401 - the real package is installed in the dev environment

    spans = {"a": SimpleNamespace(attributes={tracing.STATUS_MESSAGE: "income='8,500 a month'"}),
             "b": SimpleNamespace(attributes={"other": 1})}
    params = SimpleNamespace(spans=spans)
    monkeypatch.delenv("TRACE_TEXT", raising=False)
    result = tracing.mask_otel_spans(params=params)
    assert set(result.span_patches) == {"a"} and result.span_patches["a"].delete_attributes == (tracing.STATUS_MESSAGE,)
    monkeypatch.setenv("TRACE_TEXT", "1")
    assert tracing.mask_otel_spans(params=params) is None


def test_a_hosted_provider_never_inherits_the_local_model_url(monkeypatch):
    from ask_hdb import llm

    for name in ("LLM_BASE_URL", "LLM_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.setenv("LOCAL_LLM_URL", "http://host.docker.internal:11434/v1")
    assert "host.docker.internal" in str(llm.get_chat_model().openai_api_base)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    assert "host.docker.internal" not in str(getattr(llm.get_chat_model(), "anthropic_api_url", ""))
