"""Tracing is off by default, never sends visitor text unless asked, and never breaks the app."""

import sys
import types

import pytest

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

    for name in ("LLM_BASE_URL", "LLM_PROVIDER", "LLM_CHAIN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    monkeypatch.setenv("LOCAL_LLM_URL", "http://host.docker.internal:11434/v1")
    assert "host.docker.internal" in str(llm.get_chat_model().openai_api_base)
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    assert "host.docker.internal" not in str(getattr(llm.get_chat_model(), "anthropic_api_url", ""))


# ---- one trace per question (turn) ----

class _Root:
    trace_id = "t1"

    def __init__(self, log):
        self.log = log

    def update(self, **kw):
        self.log["update"] = kw


def _fake_langfuse(monkeypatch, log, fail=False):
    """Fake langfuse module that records what turn() asks for."""
    from contextlib import contextmanager

    @contextmanager
    def propagate(**kw):
        log["propagate"] = kw
        yield

    class Client:
        def __init__(self, **kw):
            pass

        @contextmanager
        def start_as_current_observation(self, **kw):
            if fail:
                raise RuntimeError("langfuse is down")
            log["observation"] = kw
            yield _Root(log)

        def create_score(self, **kw):
            log.setdefault("scores", []).append(kw)

    module = types.ModuleType("langfuse")
    module.Langfuse, module.propagate_attributes = Client, propagate
    monkeypatch.setitem(sys.modules, "langfuse", module)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")


RESULT = {"answer": "secret answer 4400", "tool_calls": [{}, {}], "tokens": 900, "stopped_reason": None,
          "grounding": {"ungrounded": ["7"], "rewritten": True, "replaced": False}}


def test_turn_is_a_noop_when_off_or_the_package_is_missing(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    with tracing.turn("direct") as t:
        t.record("q", RESULT)  # nothing to record to, nothing raised
    assert t.root is None
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setitem(sys.modules, "langfuse", None)
    with tracing.turn("mcp") as t:
        t.record("q", RESULT)
    assert t.root is None


def test_turn_names_tags_and_scores_one_trace(monkeypatch):
    log = {}
    _fake_langfuse(monkeypatch, log)
    monkeypatch.setenv("LLM_MODEL", "m1")
    with tracing.turn("mcp") as t:
        t.record("what is my grant?", RESULT)
    assert log["observation"] == {"name": "answer-question", "as_type": "agent"}
    prop = log["propagate"]
    assert prop["trace_name"] == "answer-question" and prop["tags"] == ["ask-hdb", "tools-mcp"]
    assert prop["metadata"] == {"tool_source": "mcp", "model": "m1"}
    assert "user_id" not in prop and "session_id" not in prop
    assert log["update"]["input"] == "what is my grant?" and log["update"]["output"] == RESULT["answer"]
    assert "metadata" not in log["update"]  # the mask would hide it; the scores carry the numbers
    scores = {s["name"]: (s["value"], s["data_type"]) for s in log["scores"]}
    assert scores == {"stopped": (0.0, "BOOLEAN"), "tool_calls": (2.0, "NUMERIC"), "grounded": (0.0, "BOOLEAN"),
                      "ungrounded_numbers": (1.0, "NUMERIC"), "grounding_rewritten": (1.0, "BOOLEAN")}
    assert all("comment" not in s and s["trace_id"] == "t1" for s in log["scores"])


def test_a_stopped_run_has_no_grounding_scores(monkeypatch):
    log = {}
    _fake_langfuse(monkeypatch, log)
    with tracing.turn("direct") as t:
        t.record("q", {**RESULT, "grounding": None, "stopped_reason": "tokens"})
    assert {s["name"] for s in log["scores"]} == {"stopped", "tool_calls"}


def test_tracing_errors_never_reach_the_caller(monkeypatch):
    log = {}
    _fake_langfuse(monkeypatch, log, fail=True)
    with tracing.turn("direct") as t:
        t.record("q", RESULT)  # the observation failed to start: still fine
    _fake_langfuse(monkeypatch, log)
    with tracing.turn("direct") as t:
        t.client = types.SimpleNamespace(create_score=lambda **kw: 1 / 0)
        t.record("q", RESULT)  # a failing score is swallowed
    log2 = {}
    _fake_langfuse(monkeypatch, log2)
    with pytest.raises(KeyError), tracing.turn("direct"):
        raise KeyError("the answer's own error still propagates")
    assert log2["update"] == {"level": "ERROR"}  # root marked failed, with no message


def test_ask_wraps_the_whole_question_in_one_turn(monkeypatch):
    from contextlib import contextmanager

    from ask_hdb import agent

    calls = []
    monkeypatch.setattr(agent, "load_dotenv", lambda: None)
    monkeypatch.setenv("TOOL_SOURCE", "direct")
    monkeypatch.setattr(agent, "_ask", lambda *a: RESULT)

    @contextmanager
    def fake_turn(source):
        calls.append(source)
        yield types.SimpleNamespace(record=lambda q, r: calls.append((q, r["answer"])))

    monkeypatch.setattr(agent.tracing, "turn", fake_turn)
    assert agent.ask("q") is RESULT  # the returned dict is untouched
    assert calls == ["direct", ("q", RESULT["answer"])]  # one turn around _ask, which holds both graph runs
