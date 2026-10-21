"""Protocol parity uses local fixtures and never calls a model or the network."""

import asyncio
import json
from threading import enumerate as threads

import pandas as pd
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from test_agent_limits import LoopModel

from ask_hdb import agent, tools
from ask_hdb.check_cases import PROFILE
from ask_hdb.geo import filters
from ask_hdb.mcp.client import load_mcp_tools
from ask_hdb.mcp.server import HousingMCP


@pytest.fixture
def local_data(monkeypatch, sales):
    block = sales.iloc[0].block_id
    monkeypatch.setattr(tools, "load_sales", lambda: sales)
    monkeypatch.setattr(filters, "load_blocks", lambda: pd.DataFrame({
        "block_id": [block], "lat": [1.], "lng": [103.]}))
    monkeypatch.setattr(filters, "load_places", lambda: pd.DataFrame({
        "place_id": ["mrt_a"], "name": ["A"], "kind": ["mrt"], "lat": [1.], "lng": [103.]}))
    return block

# The buyer fields only (no flat fields), for the BTO rule tools.
BTO_PROFILE = {k: v for k, v in PROFILE.items() if k not in {"room", "lease_left_months", "price", "category"}}


@pytest.fixture(autouse=True)
def bto_tables(monkeypatch):
    # Tiny BTO tables so the every-tool check does not need the downloaded launch data.
    from test_bto_tools import FLATS, PLACES, PROJECTS

    from ask_hdb.bto import queries
    monkeypatch.setattr(queries, "load_projects", lambda: PROJECTS)
    monkeypatch.setattr(queries, "load_flats", lambda: FLATS)
    monkeypatch.setattr(queries, "load_places", lambda: PLACES)


def test_protocol_schemas_and_every_tool(local_data):
    async def check():
        async with create_connected_server_and_client_session(HousingMCP("test")) as session:
            listed = (await session.list_tools()).tools
            assert {t.name for t in listed} == {t.name for t in tools.TOOLS}
            assert len(listed) == len(tools.TOOLS)
            for spec, direct in zip(listed, tools.TOOLS, strict=True):
                assert spec.name == direct.name
                assert spec.description == direct.description
                assert spec.inputSchema == direct.args_schema.model_json_schema()
                args = {
                    "price_stats": {"near_kind": "mrt", "near_km": 0},
                    "find_sales": {"town": "tampines"},
                    "compare_price": {"block_id": local_data, "price": 150000,
                                      "flat_type": "4 ROOM", "min_n": 1, "as_of": "latest",
                                      "storey_mid": None, "lease_left_months": None,
                                      "floor_area_sqm": None},
                    "nearest_places": {"block_id": local_data, "kind": "mrt"},
                    "calculate": {"expression": "1 + 2"},
                    "list_bto_projects": {"name": None, "town": "TAMPINES", "flat_type": None, "launch_month": None,
                                          "category": None, "max_price": None},
                    "bto_nearby": {"project_id": "bto_a", "kind": "mrt"},
                    "can_apply_bto": BTO_PROFILE | {"category": "Standard", "flat_type": "4-room", "hfe_after_revision": None},
                    "bto_ehg_amount": BTO_PROFILE,
                    "bto_scenario": {"price": 400000, "grants": 0, "loan_kind": "hdb", "interest_rate_pct": 2.6,
                                     "loan_years": 25, "category": "Standard", "town": None, "flat_type": None},
                    "phg_amount": PROFILE | {"relation": "with"},
                }.get(direct.name, PROFILE)
                result = await session.call_tool(spec.name, args)
                expected = direct.invoke(args)
                assert "error" not in expected
                assert json.loads(result.content[0].text) == expected
                assert result.structuredContent == expected
            # Invalid calls must leave the same session usable.
            for name, args in [("can_buy_resale", {}), ("find_sales", {"limit": -1}),
                               ("price_stats", {"typo": True}),
                               ("nearest_places", {"block_id": "absent", "kind": "mrt"})]:
                result = await session.call_tool(name, args)
                assert json.loads(result.content[0].text) == getattr(tools, name).invoke(args)
                assert "error" in result.structuredContent
            assert "error" in (await session.call_tool("absent", {})).structuredContent
            assert "error" not in (await session.call_tool("price_stats", {})).structuredContent

    asyncio.run(check())


def test_agent_records_match(monkeypatch, local_data, memory_mcp):
    def ask(source):
        monkeypatch.setenv("TOOL_SOURCE", source)
        monkeypatch.setattr(agent, "get_chat_model", lambda: LoopModel(finish_after=1))
        return agent.ask("Query sales", [{"role": "user", "content": "Earlier question"}])

    assert ask("mcp") == ask("direct")
    assert not any(t.name == "housing-mcp" for t in threads())


def test_real_subprocess_and_cleanup():
    # Rules need no dataset, so this tests the production launch path offline.
    with load_mcp_tools() as remote:
        assert {t.name for t in remote} == {t.name for t in tools.TOOLS}
        for tool in remote:
            if tool.name == "can_buy_resale":
                assert tool.invoke(PROFILE) == tools.can_buy_resale.invoke(PROFILE)
                assert tool.invoke({}) == tools.can_buy_resale.invoke({})
    assert not any(t.name == "housing-mcp" for t in threads())


def test_client_closes_on_caller_error(memory_mcp):
    with pytest.raises(RuntimeError, match="caller"), load_mcp_tools():
        raise RuntimeError("caller")
    assert not any(t.name == "housing-mcp" for t in threads())


def test_client_inside_running_loop(memory_mcp):
    async def check():
        with load_mcp_tools() as remote:
            assert remote[3].invoke(PROFILE) == tools.can_buy_resale.invoke(PROFILE)

    asyncio.run(check())


def test_startup_failure_closes_thread(monkeypatch):
    from contextlib import asynccontextmanager

    from langchain_mcp_adapters.client import MultiServerMCPClient

    @asynccontextmanager
    async def fail(self, server_name):
        raise RuntimeError("startup")
        yield  # Keep this an async context manager.

    monkeypatch.setattr(MultiServerMCPClient, "session", fail)
    with pytest.raises(RuntimeError, match="startup"), load_mcp_tools():
        pytest.fail("Must not return tools after startup failure")
    assert not any(t.name == "housing-mcp" for t in threads())


def test_cli_mcp(monkeypatch):
    import ask_hdb

    started = []
    monkeypatch.setattr("ask_hdb.mcp.server.main", lambda: started.append(True))
    monkeypatch.setattr("sys.argv", ["ask-hdb", "mcp"])
    ask_hdb.main()
    assert started == [True]
