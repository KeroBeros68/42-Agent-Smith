"""JSON Lines message schemas shared by the host (container.py, mcp_bridge.py)
and the in-container runner.py (decided 2026-08-12).

Message kinds to define: exec (code to run), tool_call (relay to mcp_bridge),
result, error — covering the explicit feedback cases required by §V.1.3
(no code block found, malformed block, timeout, truncated output, syntax
error after an edit).
"""

from enum import Enum
from typing import Any, TypedDict


class MsgType(str, Enum):
    """Message type tags for the JSON Lines protocol (host <-> container).

    A `str` mixin (not `enum.StrEnum`, which needs Python 3.11+ — this
    project requires exactly 3.10) so members compare equal to, hash
    like, and JSON-serialize as their plain string value.
    """

    # host -> container
    EXEC = "exec"
    TOOL_RESULT = "tool_result"

    # container -> host
    RESULT = "result"
    ERROR = "error"
    TOOL_CALL = "tool_call"
    FINAL_ANSWER = "final_answer"


# Environment variable names carrying data from container.py (host) to
# runner.py (in-container) at container startup — set once as part of
# the container's environment, not part of the JSON Lines message
# protocol itself, but crossing the same host/container boundary.
ENV_SANDBOX_CONFIG_JSON = "SANDBOX_CONFIG_JSON"
ENV_MCP_TOOLS_JSON = "MCP_TOOLS_JSON"


class ExecMessage(TypedDict):
    type: MsgType
    code: str


class ResultMessage(TypedDict):
    type: MsgType
    stdout: str


class ErrorMessage(TypedDict):
    type: MsgType
    error_type: str
    message: str
    traceback: str


class ToolCallMessage(TypedDict):
    type: MsgType
    name: str
    arguments: dict[str, Any]


class ToolResultMessage(TypedDict):
    type: MsgType
    result: Any


class FinalAnswerMessage(TypedDict):
    type: MsgType
    answer: str


def response_text(response: dict) -> str:
    """Return the plain text content of a container response — the
    result/error/final_answer/fallback classification shared by
    agent_core.loop's LLM-facing Observation text and sandbox.repl's
    human-facing display, which previously duplicated this branching
    with only their surrounding prefix/newline formatting differing.
    """
    msg_type = response.get("type")
    if msg_type == MsgType.RESULT:
        return str(response.get("stdout", ""))
    if msg_type == MsgType.ERROR:
        return response.get("traceback") or (
            f"{response.get('error_type', 'Error')}: "
            f"{response.get('message', '')}"
        )
    if msg_type == MsgType.FINAL_ANSWER:
        return str(response.get("answer", ""))
    return repr(response)
