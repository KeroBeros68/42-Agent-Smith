"""JSON Lines message schemas shared by the host (container.py, mcp_bridge.py)
and the in-container runner.py (decided 2026-08-12).

Message kinds to define: exec (code to run), tool_call (relay to mcp_bridge),
result, error — covering the explicit feedback cases required by §V.1.3
(no code block found, malformed block, timeout, truncated output, syntax
error after an edit).
"""

from typing import Any, TypedDict

# host -> container
MSG_EXEC = "exec"
MSG_TOOL_RESULT = "tool_result"

# container -> host
MSG_RESULT = "result"
MSG_ERROR = "error"
MSG_TOOL_CALL = "tool_call"
MSG_FINAL_ANSWER = "final_answer"


class ExecMessage(TypedDict):
    type: str  # MSG_EXEC
    code: str


class ResultMessage(TypedDict):
    type: str  # MSG_RESULT
    stdout: str


class ErrorMessage(TypedDict):
    type: str  # MSG_ERROR
    error_type: str
    message: str
    traceback: str


class ToolCallMessage(TypedDict):
    type: str  # MSG_TOOL_CALL
    name: str
    arguments: dict[str, Any]


class ToolResultMessage(TypedDict):
    type: str  # MSG_TOOL_RESULT
    result: Any


class FinalAnswerMessage(TypedDict):
    type: str  # MSG_FINAL_ANSWER
    answer: str
