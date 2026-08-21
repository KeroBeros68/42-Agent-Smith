"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

import json
import os
import subprocess
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import ValidationError

from student.agent_mbpp.task import MBPPTaskInput


class MBPPException(Exception):
    pass


# --- Server Setup ---

load_dotenv()
mcp = FastMCP("MBPP MCP Server")

# Loaded ONCE at startup from the env var the sandbox sets before
# starting the MCP Server.
try:
    TASK = MBPPTaskInput.model_validate(
        json.loads(os.environ.get("MBPP_TASK_JSON", "null")) or {}
    )

except (ValidationError, json.JSONDecodeError):
    TASK = None

TIMEOUT_DELAY_SEC = 10

# --- MCP Tools ---


@mcp.tool
def run_tests(code: str) -> str:
    """Run unit tests to check if a given function passes the unit tests."""
    failed_tests: list[str] = []

    # Verify that the task is valid
    if TASK is None:
        raise MBPPException(
            "The distant MCP server couldn't perform the"
            " tests because the tests were not loaded."
            " Calling this tool again won't change anything since"
            " this is a server-side error."
        )

    if len(TASK.test_list) == 0:
        return "There are no available tests for this task. You may skip testing."

    imports = "\n".join(TASK.test_imports)

    # Create a patch string to override the os._exit() function to prevent false postive tests.
    # This string will be injecte in the code, making os._exit() unusable.
    OS_EXIT_PATCH = 'import os\n\ndef PATCH_EXIT(status):\n    sys.exit(1)\nos._exit = PATCH_EXIT\n'

    # First, check if the syntax is correct
    try:
        compile(f"{imports}\n\n{code}", "<mbpp_solution>", "exec")
    except SyntaxError as e:
        loc = (
            f"line {e.lineno}" if e.lineno is not None else "unknown location"
        )
        return (
            f"SyntaxError in the submitted code: {e.msg} at {loc}. "
            f"Fix it and retry — tests cannot run against invalid Python."
        )

    # Indent all lines to put the code inside a try/except
    indented_code = "\n".join("    " + line for line in code.splitlines())

    # Run each unit test
    for test in TASK.test_list:
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    f"import sys\n{imports}\n{OS_EXIT_PATCH}\ntry:\n{indented_code}\n\n"
                    f"    {test}\nexcept SystemExit:\n    sys.exit(1)\n",
                ],
                timeout=TIMEOUT_DELAY_SEC * len(TASK.test_list),
                input="",
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                failed_tests.append(f"{test}")
        except subprocess.TimeoutExpired:
            failed_tests.append(
                f"{test}  # TIMEDOUT AFTER {TIMEOUT_DELAY_SEC} SECONDS"
            )
    if len(failed_tests) != 0:
        return "Error during the following tests :\n" + "\n".join(failed_tests)
    return "All test passed successfully !"


if __name__ == "__main__":
    # Get transport mode from env variable MCP_TRANSPORT
    transport_mode = os.environ.get("MCP_TRANSPORT", "null")

    # Verify transport mode
    if transport_mode != 'http' and transport_mode != 'stdio':
        raise TypeError(f'Wrong transport mode ("{transport_mode}") provided in the env variable "MCP_TRANSPORT".')

    # Listen
    mcp.run(transport=transport_mode)
