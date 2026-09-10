"""Interactive REPL mode (§V.2.1, no task provided).

Reads input, sends it to the running container as an `exec` message via
container.py, prints the result/error, exits cleanly on `exit` or EOF
(Ctrl+D). Same restrictions as a normal task run (§V.2.3).
"""

import codeop
import sys

from sandbox.container import SandboxContainer
from sandbox.executor.protocol import MsgType, response_text
from sandbox.mcp_bridge import MCPBridge
from sandbox.session import relay_tool_calls


def _read_block() -> str | None:
    lines: list[str] = []
    prompt = ">>>"
    while True:
        try:
            line = input(prompt)
        except EOFError:
            return None
        except KeyboardInterrupt:
            print()
            lines = []
            prompt = ">>>"
            continue

        lines.append(line)
        source = "\n".join(lines)
        try:
            code = codeop.compile_command(source, "<sandbox>", "single")
        except (SyntaxError, OverflowError, ValueError):
            return source
        if code is not None:
            return source
        prompt = "..."


def _format_response(response: dict) -> str:
    """Human-facing formatting, layered onto protocol.response_text()'s
    shared result/error/final_answer/fallback classification — only the
    surrounding prefix/trailing newline differ from loop.py's LLM-facing
    Observation text.
    """
    msg_type = response.get("type")
    text = response_text(response)
    if msg_type == MsgType.FINAL_ANSWER:
        return f"final_answer: {text}\n"
    if msg_type == MsgType.RESULT:
        return text
    return f"{text}\n"


def run(
    container: SandboxContainer, mcp_bridge: MCPBridge | None = None
) -> None:
    if not sys.stdin.isatty():
        # Piped input (e.g. `cat script.py | uv run sandbox`) is a whole
        # program, not a human typing interactively — _read_block()'s
        # blank-line-terminates-a-block REPL semantics (codeop.compile_command,
        # "single" mode) misfire on a file with blank lines *inside* a
        # still-open block (normal Python style), splitting it into
        # fragments and executing them out of context. Run it as one
        # single exec instead, matching `python -` on a piped script.
        source = sys.stdin.read()
        if source.strip() and source.strip() != "exit":
            try:
                container.send({"type": MsgType.EXEC, "code": source})
                response = relay_tool_calls(container, mcp_bridge)
                print(_format_response(response), end="")
            except (ConnectionError, TimeoutError):
                print("Connection to container lost.")
        return

    while True:
        source = _read_block()
        if source is None:
            break
        if source.strip() == "exit":
            break
        if not source.strip():
            continue

        try:
            container.send({"type": MsgType.EXEC, "code": source})
            response = relay_tool_calls(container, mcp_bridge)
            print(_format_response(response), end="")
        except (ConnectionError, TimeoutError):
            print("Connection to container lost.")
            break
