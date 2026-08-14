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

from student.data_models import MBPPTaskInput


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

    # DEBUG TASK
    # TASK = MBPPTaskInput.model_validate(
    #     json.loads(
    #         """
    #             {
    #             "task_id": 282,
    #             "task_definition": "Write a function to substaract two lists using map and lambda function.",
    #             "function_definition": "def sub_list(nums1,nums2):",
    #             "test_imports": [],
    #             "test_list": [
    #                 "assert sub_list([1,2],[3,4])==[-2,-2]",
    #                 "assert sub_list([90,120],[50,70])==[40,50]"
    #             ]
    #             }
    #         """
    #     ) or {}
    # )
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

    imports = "\n".join(TASK.test_imports)

    # First, check if the syntax is correct
    try:
        compile(f"{imports}\n\n{code}", "<mbpp_solution>", "exec")
    except SyntaxError as e:
        loc = f"line {e.lineno}" if e.lineno is not None else "unknown location"
        return (
            f"SyntaxError in the submitted code: {e.msg} at {loc}. "
            f"Fix it and retry — tests cannot run against invalid Python."
        )

    # Run each unit test
    for test in TASK.test_list:
        try:
            proc = subprocess.run(
                [sys.executable, "-c", f"{imports}\n\n{code}\n\n{test}"],
                timeout=TIMEOUT_DELAY_SEC,
                input="",
                capture_output=True,
                text=True,
            )
            if proc.returncode != 0:
                failed_tests.append(f"{test}")
        except subprocess.TimeoutExpired:
            failed_tests.append(f"{test}  # TIMEDOUT AFTER {TIMEOUT_DELAY_SEC} SECONDS")
    if len(failed_tests) != 0:
        return "Error during the following tests :\n" + "\n".join(failed_tests)
    return "All test passed successfully !"


if __name__ == "__main__":
    # Listen to input
    # REPLACE THIS STRING TO 'http' TO USE HTTP INSTEAD OF STDIO
    mcp.run(transport="stdio")
