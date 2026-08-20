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


def relay_tool_calls(
    container: SandboxContainer, mcp_bridge: MCPBridge | None
) -> dict:
    """Forward `tool_call` messages to mcp_bridge until a terminal response.

    Shared between the REPL (human-typed code) and agent_core's
    sandbox_client (LLM-generated code) — both need the exact same relay
    loop around whatever `container.send({"type": "exec", ...})` triggers.
    """
    while True:
        response = container.receive()
        if response.get("type") != "tool_call":
            return response

        if mcp_bridge is None:
            container.send(
                {
                    "type": "tool_result",
                    "result": "error: no MCP server connected",
                }
            )
            continue

        try:
            result = mcp_bridge.call_tool(
                response["name"], response["arguments"]
            )
        except Exception as e:
            result = f"error calling tool: {e}"
        container.send({"type": "tool_result", "result": str(result)})
