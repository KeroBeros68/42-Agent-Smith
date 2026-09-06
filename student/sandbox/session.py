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
from sandbox.executor.protocol import MsgType
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
            schema = tool.inputSchema or {}
            if "properties" not in schema:
                raise ValueError(
                    f"MCP tool {tool.name!r} has no 'properties' in its "
                    f"inputSchema (object schema expected) — positional "
                    f"arguments to this tool would silently be dropped by "
                    f"runner.py's call stub (zip(param_names, args) with "
                    f"an empty param_names list)."
                )
            tools[tool.name] = list(schema["properties"].keys())
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
        if response.get("type") != MsgType.TOOL_CALL:
            return response

        if mcp_bridge is None:
            container.send(
                {
                    "type": MsgType.TOOL_RESULT,
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
        container.send({"type": MsgType.TOOL_RESULT, "result": str(result)})
