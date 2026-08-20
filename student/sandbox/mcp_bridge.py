"""Host-side MCP client (stdio or HTTP streamable, §V.2.5).

Owns the actual connection to the connected MCP server and answers
`tool_call` messages relayed from inside the container over the JSON Lines
protocol — the container itself never gets network access, it only ever
talks to this bridge through the same stdio channel used for code exec.
"""

import asyncio
import shlex
import threading
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


class MCPBridge:
    """Synchronous facade over fastmcp's async Client.

    fastmcp.Client is entirely async; the rest of the sandbox (container.py,
    repl.py, cli.py) is synchronous, built on blocking sockets. A dedicated
    thread runs a persistent asyncio event loop for the lifetime of the
    bridge, so the MCP connection (stdio subprocess or HTTP session) is
    opened once per sandbox session, not per call. `_run()` is the only
    sync-to-async crossing point; every public method goes through it.
    """

    def __init__(
        self,
        stdio_command: str | None = None,
        server_url: str | None = None,
    ) -> None:
        self._client = Client(self._build_transport(stdio_command, server_url))
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever, daemon=True
        )
        self._thread.start()

    @staticmethod
    def _build_transport(
        stdio_command: str | None, server_url: str | None
    ) -> Any:
        if stdio_command is not None:
            command, *args = shlex.split(stdio_command)
            return StdioTransport(command=command, args=args)
        if server_url is not None:
            return server_url
        raise ValueError("MCPBridge requires stdio_command or server_url")

    def _run(self, coro: Any) -> Any:
        # Found by testing: after close(), the loop is stopped and its
        # thread joined. run_coroutine_threadsafe() still schedules the
        # callback without error, but nothing ever runs it again, so
        # future.result() blocks forever instead of failing fast.
        if not self._loop.is_running():
            coro.close()
            raise ConnectionError("MCPBridge is closed")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def connect(self) -> None:
        self._run(self._client.__aenter__())

    def close(self) -> None:
        self._run(self._client.__aexit__(None, None, None))
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join()

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def list_tools(self) -> list[Any]:
        return self._run(self._client.list_tools())

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        # Distinguish a legitimate tool-side error (e.g. the tool's own
        # exception, correctly propagated) from the server actually being
        # gone — only the latter gets rewrapped, so a real ToolError still
        # surfaces with its original message instead of a misleading
        # "disconnected" report.
        try:
            return self._run(self._client.call_tool(name, arguments))
        except Exception:
            if not self.is_connected():
                raise ConnectionError(
                    f"MCP server disconnected while calling tool {name!r}"
                ) from None
            raise

    def __enter__(self) -> "MCPBridge":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
