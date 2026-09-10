"""Main loop running inside the container (§V.2.1, §V.2.2).

Reads JSON Lines from stdin, executes code in a persistent namespace shared
across the whole session, writes results back on stdout. Injects
`final_answer` into the namespace (constant regardless of the connected MCP
server) and stub functions for MCP tools that serialize a `tool_call`
message instead of calling anything directly (no network in the container).
Delegates import/builtins enforcement to restrictions.py and per-snippet
timeout to watchdog.py.
"""

import io
import json
import os
import resource
import sys
import traceback
from contextlib import redirect_stdout
from typing import Any, Callable, TypeAlias

import protocol
import restrictions
import watchdog

SANDBOX_CONFIG = json.loads(
    os.environ.get(protocol.ENV_SANDBOX_CONFIG_JSON, "{}")
)
MAX_EXECUTION_TIME_SECONDS = SANDBOX_CONFIG.get(
    "max_execution_time_seconds", 10
)
TOOLS = json.loads(os.environ.get(protocol.ENV_MCP_TOOLS_JSON, "{}"))

_MAX_MEMORY_MB = SANDBOX_CONFIG.get("max_memory_mb")

# _handle_exec wraps user code in redirect_stdout(buffer) to capture print()
# output. A tool stub's own protocol message must bypass that and reach the
# real channel, so it writes to this reference captured before any
# redirection happens, never to sys.stdout directly.
REAL_STDOUT = sys.stdout

NAMESPACE: dict = {}


class _FinalAnswerSignal(Exception):
    def __init__(self, answer: str) -> None:
        super().__init__(answer)
        self.answer = answer


def final_answer(answer: str) -> None:
    raise _FinalAnswerSignal(answer)


def _make_tool_stub(name: str, param_names: list[str]) -> Callable[..., Any]:
    # Called from deep inside exec(), while main()'s own stdin loop is
    # paused mid-iteration — the stub does its own send/wait directly on
    # stdout/stdin rather than going through main(), since main() cannot
    # run again until this call returns.
    def stub(*args: Any, **kwargs: Any) -> Any:
        # param_names comes from the tool's inputSchema (dict preserves
        # declaration order), so positional call-site args map back to
        # the keyword arguments the real MCP tool actually expects.
        kwargs = {**dict(zip(param_names, args)), **kwargs}
        REAL_STDOUT.write(
            json.dumps(
                protocol.ToolCallMessage(
                    type=protocol.MsgType.TOOL_CALL,
                    name=name,
                    arguments=kwargs,
                )
            )
            + "\n"
        )
        REAL_STDOUT.flush()
        remaining = watchdog.pause()
        try:
            response = json.loads(sys.stdin.readline())
        finally:
            watchdog.resume(remaining)
        if response.get("type") == protocol.MsgType.TOOL_RESULT:
            return response["result"]
        raise RuntimeError(f"Unexpected response to tool_call: {response}")

    return stub


ExecResponse: TypeAlias = (
    protocol.ResultMessage
    | protocol.ErrorMessage
    | protocol.FinalAnswerMessage
)


def _handle_exec(message: protocol.ExecMessage) -> ExecResponse:
    buffer = io.StringIO()
    try:
        code_obj = compile(message["code"], "<sandbox>", "exec")
        with redirect_stdout(buffer), watchdog.enforce(
            MAX_EXECUTION_TIME_SECONDS
        ):
            exec(code_obj, NAMESPACE)
    except _FinalAnswerSignal as e:
        return protocol.FinalAnswerMessage(
            type=protocol.MsgType.FINAL_ANSWER,
            answer=e.answer,
        )
    except Exception as e:
        return protocol.ErrorMessage(
            type=protocol.MsgType.ERROR,
            error_type=type(e).__name__,
            message=str(e),
            traceback=traceback.format_exc(),
        )
    return protocol.ResultMessage(
        type=protocol.MsgType.RESULT,
        stdout=buffer.getvalue(),
    )


def main() -> None:
    if _MAX_MEMORY_MB is not None:
        # A soft, in-process limit set below Docker's hard `mem_limit`
        # cgroup limit (container.py), so Python's own allocator raises a
        # catchable MemoryError before the kernel's OOM killer SIGKILLs
        # the whole container — the two aren't equivalent: a container
        # OOM-kill isn't observable/recoverable from inside exec(), it
        # just drops the connection with no error message at all.
        soft_bytes = int(_MAX_MEMORY_MB * 0.9 * 1024 * 1024)
        resource.setrlimit(resource.RLIMIT_AS, (soft_bytes, soft_bytes))
    restrictions.install(SANDBOX_CONFIG.get("authorized_imports", []))
    NAMESPACE["__builtins__"] = restrictions.restricted_builtins(
        SANDBOX_CONFIG.get("allowed_directories", [])
    )
    NAMESPACE["final_answer"] = final_answer
    for name, param_names in TOOLS.items():
        NAMESPACE[name] = _make_tool_stub(name, param_names)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response: ExecResponse
        try:
            message = json.loads(line)
        except json.JSONDecodeError as e:
            response = protocol.ErrorMessage(
                type=protocol.MsgType.ERROR,
                error_type="ProtocolError",
                message=f"Malformed JSON message: {e}",
                traceback="",
            )
        else:
            msg_type = message.get("type")
            if msg_type == protocol.MsgType.EXEC:
                response = _handle_exec(message)
            else:
                response = protocol.ErrorMessage(
                    type=protocol.MsgType.ERROR,
                    error_type="ProtocolError",
                    message=f"Unknown message type: {msg_type!r}",
                    traceback="",
                )
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
