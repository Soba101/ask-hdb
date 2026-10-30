"""The API streams tool evidence and the checked answer, and enforces its limits."""

import json
import os

import pytest
from fastapi.testclient import TestClient

from ask_hdb import api


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def client(monkeypatch):
    def fake_ask(question, history=None, confirm=False, on_event=None, context=None):
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
    def spends_then_fails(question, history=None, confirm=False, on_event=None, context=None):
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

    def long_run(question, history=None, confirm=False, on_event=None, context=None):
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
    assert "slice(0, 2000)" in js and "slice(0, 1000)" in js and 'tick.setAttribute("aria-hidden", "true")' in js


def test_points_events_follow_their_tool_result(monkeypatch):
    def ask_with_points(question, history=None, confirm=False, on_event=None, context=None):
        on_event({"type": "tool_call", "name": "bto_nearby", "args": {"project_id": "bto_tampines-nova"}})
        on_event({"type": "tool_result", "name": "bto_nearby", "args": {"project_id": "bto_tampines-nova"},
                  "result": {"places": []}})
        return {"answer": "ok", "tokens": 1, "stopped_reason": None, "needs_confirmation": False}

    monkeypatch.setattr(api.agent, "ask", ask_with_points)
    monkeypatch.setattr(api, "map_points", lambda args, result: [{"id": args["project_id"]}])
    monkeypatch.setattr(api, "map_actions", lambda points: [{"op": "highlight", "points": points}])
    got = events(TestClient(api.create_app()).post("/chat", json={"question": "q"}))
    assert [e["type"] for e in got] == ["tool_call", "tool_result", "map", "answer"]
    assert got[2]["actions"] == [{"op": "highlight", "points": [{"id": "bto_tampines-nova"}]}]


def test_a_failing_map_lookup_never_breaks_the_answer(monkeypatch):
    def ask_one(question, history=None, confirm=False, on_event=None, context=None):
        on_event({"type": "tool_call", "name": "t", "args": {}})
        on_event({"type": "tool_result", "name": "t", "args": {}, "result": {}})
        return {"answer": "ok", "tokens": 1, "stopped_reason": None, "needs_confirmation": False}

    def boom(args, result):
        raise RuntimeError("bad data")

    monkeypatch.setattr(api.agent, "ask", ask_one)
    monkeypatch.setattr(api, "map_points", boom)
    got = events(TestClient(api.create_app()).post("/chat", json={"question": "q"}))
    assert [e["type"] for e in got] == ["tool_call", "tool_result", "answer"]


def test_each_result_is_mapped_with_its_own_arguments(monkeypatch):
    def ask_two(question, history=None, confirm=False, on_event=None, context=None):
        for name in ("a", "b"):
            on_event({"type": "tool_call", "name": "t", "args": {"id": name}})
        for name in ("b", "a"):  # results in the other order: pairing must not depend on order
            on_event({"type": "tool_result", "name": "t", "args": {"id": name}, "result": {}})
        return {"answer": "ok", "tokens": 1, "stopped_reason": None, "needs_confirmation": False}

    monkeypatch.setattr(api.agent, "ask", ask_two)
    monkeypatch.setattr(api, "map_points", lambda args, result: [{"id": args["id"]}])
    monkeypatch.setattr(api, "map_actions", lambda points: [{"op": "highlight", "points": points}])
    got = events(TestClient(api.create_app()).post("/chat", json={"question": "q"}))
    assert [e["actions"][0]["points"][0]["id"] for e in got if e["type"] == "map"] == ["b", "a"]
    assert all("args" not in e for e in got if e["type"] == "tool_result")


def test_csp_allows_only_the_tile_server_and_the_page_isolates_the_map_library(client):
    csp = client.get("/").headers["content-security-policy"]
    assert "connect-src 'self' https://tile.openstreetmap.org" in csp and "worker-src" not in csp
    from pathlib import Path
    js = (Path(api.__file__).parent / "static/app.js").read_text()
    assert 'await import("./vendor/maplibre/maplibre-gl.mjs")' in js and "import * as" not in js


def test_the_page_guards_against_stale_cards_and_a_failed_map():
    from pathlib import Path
    js = (Path(api.__file__).parent / "static/app.js").read_text()
    card = (Path(api.__file__).parent / "static/card.js").read_text()
    assert 'import { initCard } from "./card.js"' in js and "card.select(point)" in js
    assert "cardRequest" in card and "mine !== cardRequest" in card  # late cards cannot fill a newer selection
    assert "The map data could not be loaded" in js and "todo.highlight" in js  # map failures show a note; early events are kept


def test_an_ambiguous_place_sends_choices_for_the_page(monkeypatch):
    candidates = [{"kind": "block", "id": "a", "label": "Blk 1 A St", "lat": 1.3, "lng": 103.8}]

    def ask_ambiguous(question, history=None, confirm=False, on_event=None, context=None):
        on_event({"type": "tool_call", "name": "resolve_place", "args": {"text": "blk 1"}})
        on_event({"type": "tool_result", "name": "resolve_place", "args": {"text": "blk 1"},
                  "result": {"status": "ambiguous", "candidates": candidates}})
        return {"answer": "Which one?", "tokens": 1, "stopped_reason": None, "needs_confirmation": False}

    monkeypatch.setattr(api.agent, "ask", ask_ambiguous)
    monkeypatch.setattr(api, "map_points", lambda args, result: [])
    got = events(TestClient(api.create_app()).post("/chat", json={"question": "q"}))
    assert [e["type"] for e in got] == ["tool_call", "tool_result", "choices", "answer"]
    assert got[2]["candidates"] == candidates
    from pathlib import Path
    js = (Path(api.__file__).parent / "static/app.js").read_text()
    assert "pendingChoices" in js and "ask(question); // ask the same question again" in js


def test_the_page_script_has_valid_syntax():
    """A syntax error blanks the whole page (chat and map), so check it whenever node is available."""
    import shutil
    import subprocess
    import tempfile
    from pathlib import Path

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    source = (Path(api.__file__).parent / "static/app.js").read_text()
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "app.mjs"
        path.write_text(source)
        done = subprocess.run([node, "--check", str(path)], check=False, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_smoke_the_page_wires_the_price_and_lease_layers_to_the_metrics_route():
    from pathlib import Path
    js = (Path(api.__file__).parent / "static/app.js").read_text()
    html = (Path(api.__file__).parent / "static/index.html").read_text()
    assert "/map/metrics?flat_type=" in js and 'data-mode="lease"' in html and 'id="budget"' in html
    assert 'data-mode="mop"' in html and 'id="mop-controls"' in html and "data.mop_limits" in js and 'layerMode === "mop"' in js
    assert 'metricsCache' in js and '"#b8bdc9"' in js  # grey for blocks with too few sales or above the budget


def test_a_second_question_waits_its_turn_and_the_queue_is_bounded(client):
    from threading import Timer

    limits = client.app.state.limits
    limits.queue_wait = 5
    assert limits.busy.acquire(blocking=False)
    Timer(0.3, limits.busy.release).start()
    assert client.post("/chat", json={"question": "q"}).status_code == 200  # got the slot after the first run ended
    assert limits.waiting == 0
    assert limits.busy.acquire(blocking=False)
    limits.waiting = limits.queue_max  # a full queue refuses at once
    assert client.post("/chat", json={"question": "q"}).status_code == 503
    limits.busy.release()


def test_about_lists_when_each_part_of_the_data_was_built(client):
    data = client.get("/about").json()["data"]
    labels = [row["label"] for row in data]
    assert {"Resale prices", "HDB rules and grants", "Bus stops and supermarkets", "Walking paths", "Map tiles"} <= set(labels)
    assert all(row["as_of"] and row["source"] for row in data)
    assert any("sales to 20" in row["as_of"] for row in data)


def test_a_quiet_stream_sends_pings_so_a_proxy_does_not_close_it(monkeypatch):
    import asyncio
    from queue import Queue

    monkeypatch.setattr(api, "PING_SECONDS", 0.05)

    async def run():
        events, left = Queue(), api.Event()
        got = []
        async def collect():
            async for chunk in api.stream(events, left):
                got.append(chunk)
        task = asyncio.create_task(collect())
        await asyncio.sleep(0.3)
        events.put({"type": "answer", "answer": "x"}); events.put(api.DONE)
        await task
        return got
    got = asyncio.run(run())
    assert got[0] == ": ping\n\n" and any('"answer"' in chunk for chunk in got) and got.count(": ping\n\n") >= 2


def test_prewarm_runs_one_question_only_for_a_local_model_and_frees_the_slot(monkeypatch):
    asked = []
    monkeypatch.setattr(api.agent, "ask", lambda question, *a, **k: asked.append(question))
    limits = api.Limits()
    monkeypatch.delenv("LLM_CHAIN", raising=False); monkeypatch.delenv("LLM_PROVIDER", raising=False)
    api.prewarm(limits)
    assert asked == ["Hello"] and not limits.busy.locked()
    monkeypatch.setenv("LLM_PROVIDER", "anthropic"); api.prewarm(limits)
    monkeypatch.setenv("LLM_PROVIDER", "local"); monkeypatch.setenv("PREWARM_MODEL", "0"); api.prewarm(limits)
    assert asked == ["Hello"]  # a hosted model and the off switch both skip it
    monkeypatch.setenv("PREWARM_MODEL", "1"); assert limits.busy.acquire(blocking=False); api.prewarm(limits)
    assert asked == ["Hello"]  # a visitor's question already holds the slot
    limits.busy.release()
    # With a chain, only a chain that ends in the local model is warmed, and the warm-up goes to the local model alone.
    seen = []
    monkeypatch.setattr(api.agent, "ask", lambda question, *a, **k: seen.append(os.environ.get("LLM_CHAIN")))
    monkeypatch.setenv("LLM_CHAIN", "gemini,local"); api.prewarm(limits)
    monkeypatch.setenv("LLM_CHAIN", "gemini,groq"); api.prewarm(limits)
    assert seen == ["local"] and os.environ["LLM_CHAIN"] == "gemini,groq"  # restored, and a hosted-only chain is not warmed
