"""Serve the existing tools without changing their schemas or calculations."""

import json
import os
import sys
from pathlib import Path

from mcp import types
from mcp.server.fastmcp import FastMCP

from ask_hdb.tools import TOOLS


class HousingMCP(FastMCP):
    # FastMCP's handlers use these methods. Skip signature inference so the
    # published schema is exactly the one used by the direct tools.
    async def list_tools(self):
        return [types.Tool(name=tool.name, description=tool.description,
                           inputSchema=tool.args_schema.model_json_schema())
                for tool in TOOLS]

    async def call_tool(self, name, arguments):
        tool = next((tool for tool in TOOLS if tool.name == name), None)
        try:
            result = tool.invoke(arguments) if tool else {"error": f"Unknown tool: {name}"}
        except Exception:  # noqa: BLE001 - bad calls must not end the protocol session
            result = {"error": f"Invalid arguments or unavailable data for {name}"}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(result, allow_nan=False))],
            structuredContent=result,
        )


def main():
    if os.getenv("ASK_HDB_MCP_QUIET") == "1":
        # The client owns this subprocess. Keep SDK logs out of terminal chat but keep tool failure
        # traces in a git-ignored log file.
        log = Path(__file__).resolve().parents[3] / "data/mcp.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a") as sink:
            os.dup2(sink.fileno(), sys.stderr.fileno())
    HousingMCP("ask-hdb").run(transport="stdio")
