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


def test_a_missing_package_means_no_tracing_not_a_crash(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setitem(sys.modules, "langfuse", None)  # makes `import langfuse` raise ImportError
    assert tracing.callbacks() == []
