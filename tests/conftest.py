"""Small local sales shared by the cleaning and query tests."""

import pandas as pd
import pytest

from ask_hdb.clean import clean


@pytest.fixture
def raw_sales():
    columns = [
        "month", "town", "flat_type", "block", "street_name", "storey_range",
        "floor_area_sqm", "flat_model", "lease_commence_date", "remaining_lease",
        "resale_price",
    ]
    # Keep the prices simple enough to check statistics without another program.
    rows = [
        ("2024-01", "TAMPINES", "4 ROOM", "001A", " TAMPINES... ST / 11 ", "10 TO 12",
         "90", "Model A", "1985", "61 years 04 months", "100000"),
        ("2024-03", "TAMPINES", "4 ROOM", "001A", " TAMPINES... ST / 11 ", "04 TO 06",
         "90", "Model A", "1985", "61 years", "200000"),
        ("2024-02", "TAMPINES", "4 ROOM", "002", "TAMPINES ST 11", "07 TO 09",
         "95.5", "Model A", "2000", "", "300000"),
        ("2024-04", "TAMPINES", "4 ROOM", "003", "TAMPINES AVE 2", "10 TO 12",
         "100", "Model A", "2000", None, "400000"),
        ("2024-05", "TAMPINES", "3 ROOM", "004", "TAMPINES AVE 2", "01 TO 03",
         "70", "Model A", "1990", "60 years 01 months", "500001"),
        ("2024-06", "BEDOK", "4 ROOM", "005", "BEDOK NTH ST 1", "13 TO 15",
         "90", "Model A", "1985", "50 years", "500002"),
        ("2023-12", "BEDOK", "5 ROOM", "006", "BEDOK NTH ST 1", "16 TO 18",
         "120", "Model A", "1984", "59 years 11 months", "900000"),
    ]
    return pd.DataFrame(rows + [rows[0]], columns=columns)


@pytest.fixture
def sales(raw_sales):
    return clean(raw_sales)


@pytest.fixture
def memory_mcp(monkeypatch):
    from contextlib import asynccontextmanager

    from langchain_mcp_adapters.client import MultiServerMCPClient
    from mcp.shared.memory import create_connected_server_and_client_session

    from ask_hdb.mcp.server import HousingMCP

    @asynccontextmanager
    async def session(self, server_name):
        async with create_connected_server_and_client_session(HousingMCP("test")) as client:
            yield client

    monkeypatch.setattr(MultiServerMCPClient, "session", session)
