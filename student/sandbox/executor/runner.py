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
import sys
import traceback
from contextlib import redirect_stdout

import protocol
import restrictions

SANDBOX_CONFIG = json.loads(os.environ.get("SANDBOX_CONFIG_JSON", "{}"))

NAMESPACE: dict = {}


def _handle_exec(
    message: protocol.ExecMessage,
) -> protocol.ResultMessage | protocol.ErrorMessage:
    buffer = io.StringIO()
    try:
        code_obj = compile(message["code"], "<sandbox>", "exec")
        with redirect_stdout(buffer):
            exec(code_obj, NAMESPACE)
    except Exception as e:
        return protocol.ErrorMessage(
            type=protocol.MSG_ERROR,
            error_type=type(e).__name__,
            message=str(e),
            traceback=traceback.format_exc(),
        )
    return protocol.ResultMessage(
        type=protocol.MSG_RESULT,
        stdout=buffer.getvalue(),
    )


def main() -> None:
    restrictions.install(SANDBOX_CONFIG.get("authorized_imports", []))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response: protocol.ResultMessage | protocol.ErrorMessage
        try:
            message = json.loads(line)
        except json.JSONDecodeError as e:
            response = protocol.ErrorMessage(
                type=protocol.MSG_ERROR,
                error_type="ProtocolError",
                message=f"Malformed JSON message: {e}",
                traceback="",
            )
        else:
            msg_type = message.get("type")
            if msg_type == protocol.MSG_EXEC:
                response = _handle_exec(message)
            else:
                response = protocol.ErrorMessage(
                    type=protocol.MSG_ERROR,
                    error_type="ProtocolError",
                    message=f"Unknown message type: {msg_type!r}",
                    traceback="",
                )
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
