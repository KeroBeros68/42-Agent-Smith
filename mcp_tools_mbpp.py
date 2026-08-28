"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.

[!] Important notice :
- Needs a MBPPTaskInput set in the env variable "MBPP_TASK_JSON"
- Needs a transport value set in the env variable "MCP_TRANSPORT"
    e.g: 'http' or 'stdio'. defaults to 'stdio'
- Needs a MCP_TIMEOUT_DELAY env variable set to the number of seconds
    for a subprocess timeout. (>=1)
"""

import json
import os
import subprocess
import sys
from typing import Literal

from dotenv import load_dotenv
from fastmcp import FastMCP
from pydantic import ValidationError

from student.mcp_server_shared.share import truncate_output
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

if TASK is None:
    print(
        "Could not load the task. Please restart "
        "the MCP server with a valid MBPPTaskInput in the "
        "MBPP_TASK_JSON env variable.",
        file=sys.stderr,
    )
    exit(1)


# Load the timeout delay
try:
    TIMEOUT_DELAY_SEC = int(os.environ.get('MCP_TIMEOUT_DELAY', -1))
    if TIMEOUT_DELAY_SEC < 1:
        raise ValueError('Invalid timeout delay')
except ValueError:
    print('Unable to load the env variable corresponding '
          'to MCP_TIMEOUT_DELAY. Make sure it\'s present as '
          'a positive int value (>=1).')
    exit(1)

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
        return ("There are no available tests for this task. "
                "You may skip testing.")

    imports = "\n".join(TASK.test_imports)

    # Create a patch string to override the os._exit() function to
    # prevent false postive tests.
    # This string will be injecte in the code, making os._exit() unusable.
    OS_EXIT_PATCH = (
        "import os\n\ndef PATCH_EXIT(status):\n"
        "    sys.exit(1)\nos._exit = PATCH_EXIT\n"
    )

    # First, check if the syntax is correct
    try:
        compile(f"{imports}\n\n{code}", "<mbpp_solution>", "exec")
    except SyntaxError as e:
        loc = f"line {e.lineno}" if e.lineno is not None else ("unknown"
                                                               " location")
        return truncate_output(
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
                    f"import sys\n{imports}\n{OS_EXIT_PATCH}\n"
                    f"try:\n{indented_code}\n\n"
                    f"    {test}\nexcept SystemExit:\n    sys.exit(1)\n",
                ],
                timeout=TIMEOUT_DELAY_SEC,
                input="",
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                # Test failed. Add details to the error
                #   (e.g NameError: name 'sub_list' is not defined)
                # and save the error to the list of fails.
                tb_lines = (proc.stderr or "").rstrip("\n").splitlines()
                reason = (
                    tb_lines[-1].strip()
                    if tb_lines
                    else (f"exit code {proc.returncode}, no stderr")
                )
                failed_tests.append(f"{test}  # {reason[:300]}")
        except subprocess.TimeoutExpired:
            failed_tests.append(f"{test}  # TIMEDOUT AFTER "
                                f"{TIMEOUT_DELAY_SEC} SECONDS")
    if len(failed_tests) != 0:
        return truncate_output(
            "Error during the following tests :\n" + "\n".join(failed_tests))
    return "All test passed successfully !"


if __name__ == "__main__":
    # Get transport mode from env variable MCP_TRANSPORT
    transport_mode = os.environ.get("MCP_TRANSPORT", "stdio")

    # Verify transport mode
    if transport_mode != "http" and transport_mode != "stdio":
        raise TypeError(
            f'Wrong transport mode ("{transport_mode}") '
            'provided in the env variable "MCP_TRANSPORT".'
        )

    # Use literal value for mypy
    mode: Literal["http", "stdio"] = "http"
    if transport_mode == 'stdio':
        mode = 'stdio'

    # Listen
    mcp.run(transport=mode)
