"""Keep one MCP session alive while synchronous agent tools use it."""

import asyncio
import json
import os
import sys
from concurrent.futures import Future
from contextlib import contextmanager
from threading import Thread

from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools as load_session_tools

SAFE_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "VIRTUAL_ENV", "PYTHONPATH")


def result_dict(content):
    # The adapter preserves MCP text as content blocks; direct tools return dicts.
    if isinstance(content, list):
        content = "".join(block["text"] for block in content if block.get("type") == "text")
    return json.loads(content)


@contextmanager
def load_mcp_tools():
    """Yield sync LangChain tools, then close their session and subprocess.

    One owner task enters and exits the SDK session. Its loop stays on a separate
    thread so callers can also use this from a thread with a running event loop.
    """
    ready = Future()
    finished = Future()
    loop = asyncio.new_event_loop()
    stop = asyncio.Event()

    async def serve():
        client = MultiServerMCPClient({"housing": {
            "transport": "stdio", "command": sys.executable,
            "args": ["-m", "ask_hdb.mcp"],
            # Pass only what Python needs: the server must never see ONEMAP or LLM credentials.
            "env": {**{k: os.environ[k] for k in SAFE_ENV if k in os.environ}, "ASK_HDB_MCP_QUIET": "1"},
        }})
        try:
            async with client.session("housing") as session:
                remote = await load_session_tools(session)
                ready.set_result(remote)
                await stop.wait()
        except BaseException as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                raise

    def run():
        try:
            loop.run_until_complete(serve())
            finished.set_result(None)
        except BaseException as exc:  # noqa: BLE001 - relay thread failures to the caller
            if not ready.done():
                ready.set_exception(exc)
            finished.set_exception(exc)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def wrap(tool):
        def invoke(**kwargs):
            content = asyncio.run_coroutine_threadsafe(tool.ainvoke(kwargs), loop).result()
            return result_dict(content)

        return StructuredTool(name=tool.name, description=tool.description,
                              args_schema=tool.args_schema, func=invoke)

    thread = Thread(target=run, name="housing-mcp", daemon=True)
    thread.start()
    try:
        yield [wrap(tool) for tool in ready.result()]
    finally:
        if not loop.is_closed():
            loop.call_soon_threadsafe(stop.set)
        thread.join()
        finished.result()
