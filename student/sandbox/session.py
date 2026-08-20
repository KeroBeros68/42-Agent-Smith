"""Shared sandbox session bootstrap (§V.2.5).

Wires a SandboxContainer to whatever MCP tools the connected bridge
exposes. Kept separate from cli.py so agent_core can reuse the exact same
wiring later instead of duplicating it — the connection lifecycle itself
(when to connect/close mcp_bridge) stays with the caller, since that part
genuinely differs between the REPL and the future agent loop.
"""

from pathlib import Path

from sandbox.config import SandboxConfig
from sandbox.container import SandboxContainer
from sandbox.mcp_bridge import MCPBridge


def build_container(
    config: SandboxConfig,
    image: str,
    build_context: Path | None,
    mcp_bridge: MCPBridge | None,
) -> SandboxContainer:
    tools: dict[str, list[str]] = {}
    if mcp_bridge is not None:
        for tool in mcp_bridge.list_tools():
            properties = (tool.inputSchema or {}).get("properties", {})
            tools[tool.name] = list(properties.keys())
    return SandboxContainer(
        config,
        image=image,
        build_context=build_context,
        tools=tools,
    )
