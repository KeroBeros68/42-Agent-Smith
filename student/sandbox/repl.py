"""Interactive REPL mode (§V.2.1, no task provided).

Reads input, sends it to the running container as an `exec` message via
container.py, prints the result/error, exits cleanly on `exit` or EOF
(Ctrl+D). Same restrictions as a normal task run (§V.2.3).
"""

import codeop

from sandbox.container import SandboxContainer
from sandbox.mcp_bridge import MCPBridge

PRIMARY_PROMPT = ">>> "
CONTINUATION_PROMPT = "... "


def _read_block() -> str | None:
    lines: list[str] = []
    prompt = PRIMARY_PROMPT
    while True:
        try:
            line = input(prompt)
        except EOFError:
            return None
        except KeyboardInterrupt:
            print()
            lines = []
            prompt = PRIMARY_PROMPT
            continue

        lines.append(line)
        source = "\n".join(lines)
        try:
            code = codeop.compile_command(source, "<sandbox>", "single")
        except (SyntaxError, OverflowError, ValueError):
            return source
        if code is not None:
            return source
        prompt = CONTINUATION_PROMPT


def _relay_tool_calls(
    container: SandboxContainer, mcp_bridge: MCPBridge | None
) -> dict:
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


def _format_response(response: dict) -> str:
    msg_type = response.get("type")
    if msg_type == "result":
        return response.get("stdout", "")
    if msg_type == "error":
        return response.get("traceback") or (
            f"{response.get('error_type', 'Error')}: "
            f"{response.get('message', '')}\n"
        )
    if msg_type == "final_answer":
        return f"final_answer: {response.get('answer', '')}\n"
    return f"{response!r}\n"


def run(
    container: SandboxContainer, mcp_bridge: MCPBridge | None = None
) -> None:
    while True:
        source = _read_block()
        if source is None:
            break
        if source.strip() == "exit":
            break
        if not source.strip():
            continue

        try:
            container.send({"type": "exec", "code": source})
            response = _relay_tool_calls(container, mcp_bridge)
            print(_format_response(response), end="")
        except (ConnectionError, TimeoutError):
            print("Connection to container lost.")
            break
