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
    assert got == [{"type": "error", "message": "The model call failed. Please try again.", "kind": "RuntimeError"}]
