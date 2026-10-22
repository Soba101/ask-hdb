"""The API streams tool evidence and the checked answer, and enforces its limits."""

import json

import pytest
from fastapi.testclient import TestClient

from ask_hdb import api


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def client(monkeypatch):
    def fake_ask(question, history=None, confirm=False, on_event=None):
        assert confirm is True
        on_event({"type": "tool_call", "name": "price_stats", "args": {"town": "BEDOK"}})
        on_event({"type": "tool_result", "name": "price_stats", "result": {"median": 500000}})
        return {"answer": f"Median is 500000. ({len(history)} earlier turns)", "tool_calls": [], "tokens": 1200,
                "stopped_reason": None, "grounding": None, "needs_confirmation": False}

    monkeypatch.setattr(api.agent, "ask", fake_ask)
    return TestClient(api.create_app())


def test_events_arrive_in_order_with_the_notice(client):
    response = client.post("/chat", json={"question": "Median in Bedok?", "history": [
        {"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]})
    got = events(response)
    assert [e["type"] for e in got] == ["tool_call", "tool_result", "answer"]
    assert "2 earlier turns" in got[-1]["answer"] and "not financial advice" in got[-1]["notice"]
    assert client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("body", [{"question": ""}, {"question": "x" * 1001},
                                  {"question": "ok", "history": [{"role": "system", "content": "x"}]},
                                  {"question": "ok", "history": [{"role": "user", "content": "x"}] * 13}])
def test_bad_requests_are_rejected(client, body):
    assert client.post("/chat", json=body).status_code == 422


def test_rate_limit_and_daily_cap(client):
    client.app.state.limits.per_minute = 2
    ok = [client.post("/chat", json={"question": "q"}).status_code for _ in range(3)]
    assert ok == [200, 200, 429]
    other = TestClient(api.create_app())
    other.app.state.limits.daily_tokens = 1000
    assert other.post("/chat", json={"question": "q"}).status_code == 200  # fake_ask patched on the module
    other.app.state.limits.add_tokens(5000)
    assert other.post("/chat", json={"question": "q"}).status_code == 429


def test_model_errors_do_not_leak_provider_text(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("401 key sk-secret at https://provider")

    monkeypatch.setattr(api.agent, "ask", broken)
    got = events(TestClient(api.create_app()).post("/chat", json={"question": "q"}))
    assert got == [{"type": "error", "message": "The model call failed. Please try again."}]


def test_busy_returns_503_and_the_lock_is_freed_after_a_run(client):
    limits = client.app.state.limits
    assert limits.busy.acquire(blocking=False)
    assert client.post("/chat", json={"question": "q"}).status_code == 503
    limits.busy.release()
    assert client.post("/chat", json={"question": "q"}).status_code == 200
    assert not limits.busy.locked()


def test_tokens_are_counted_when_the_run_fails(monkeypatch):
    def spends_then_fails(question, history=None, confirm=False, on_event=None):
        on_event({"type": "usage", "tokens": 4000})
        raise RuntimeError("provider down")

    monkeypatch.setattr(api.agent, "ask", spends_then_fails)
    test_client = TestClient(api.create_app())
    got = events(test_client.post("/chat", json={"question": "q"}))
    assert [e["type"] for e in got] == ["error"]  # usage events are not sent to the visitor
    assert test_client.app.state.limits.used == 4000


def test_a_departed_client_stops_the_run_and_frees_the_lock():
    from queue import Queue
    from threading import Event

    limits = api.Limits()
    limits.busy.acquire()
    left = Event()
    left.set()
    seen = []

    def long_run(question, history=None, confirm=False, on_event=None):
        on_event({"type": "usage", "tokens": 10})  # raises: the visitor already left
        seen.append("kept going")

    api.agent.ask, original = long_run, api.agent.ask
    try:
        api.work("q", [], limits, Queue(), left)
    finally:
        api.agent.ask = original
    assert seen == [] and not limits.busy.locked()


def test_daily_cap_resets_on_a_new_day():
    limits = api.Limits()
    limits.daily_tokens = 100
    limits.add_tokens(500)
    assert limits.over_cap()
    limits.day = "2000-01-01"
    assert not limits.over_cap() and limits.used == 0


def test_idle_visitors_are_forgotten():
    limits = api.Limits()
    limits.allow("a", now=0)
    limits.allow("b", now=100)
    assert "a" not in limits.hits


def test_the_page_is_served_and_the_api_still_wins(client):
    page = client.get("/")
    assert page.status_code == 200 and "Ask HDB" in page.text and "app.js" in page.text
    assert client.get("/app.js").status_code == 200 and client.get("/health").json() == {"status": "ok"}
    assert "innerHTML" not in client.get("/app.js").text  # model and tool text is never inserted as HTML


def test_security_and_cache_headers(client):
    page = client.get("/")
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"] == "nosniff" and page.headers["cache-control"] == "no-cache"
    assert client.post("/chat", json={"question": "q"}).headers["cache-control"] == "no-store"


def test_the_page_keeps_the_history_within_the_server_limits():
    from pathlib import Path
    js = (Path(api.__file__).parent / "static/app.js").read_text()
    assert "slice(0, 2000)" in js and "slice(0, 1000)" in js and 'aria-live", "off"' in js
