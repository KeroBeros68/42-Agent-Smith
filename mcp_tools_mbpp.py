"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.

--- DEVELOPER NOTE : ---
The server currently doesn't have any timeout support. Any
while True loop or anything like that will end up making the server
loop in the void. Should consider implementing one to avoid this.
"""

import json
from typing import Any

from fastmcp import FastMCP
from pydantic import ValidationError

from student.data_models import MBPPTaskInput


class MBPPException(Exception):
    pass

# --- Server Setup ---

mcp = FastMCP("MBPP MCP Server")

# Loaded ONCE at startup from the env var the sandbox sets before
# starting the MCP Server.
try:
    # TASK = MBPPTaskInput.model_validate(
    #     json.loads(os.environ.get("MBPP_TASK_JSON", "null")) or {}
    # )

    # DEBUG TASK
    TASK = MBPPTaskInput.model_validate(
        json.loads(
            """
                {
                "task_id": 282,
                "task_definition": "Write a function to substaract two lists using map and lambda function.",
                "function_definition": "def sub_list(nums1,nums2):",
                "test_imports": [],
                "test_list": [
                    "assert sub_list([1,2],[3,4])==[-2,-2]",
                    "assert sub_list([90,120],[50,70])==[40,50]"
                ]
                }
            """
        ) or {}
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
        raise MBPPException('The distant MCP server couldn\'t perform the'
                            ' tests because the tests were not loaded.'
                            ' Calling this tool again won\'t change anything since'
                            ' this is a server-side error.')

    # Prepare the execution namespace
    try:
        namespace: dict[str, Any] = {'__name__': "__main__"}
        for imports in TASK.test_imports:
            exec(imports, namespace)
        exec(code, namespace)
    except Exception as e:
        # Return an error because the code is invalid
        return f'Your code could not be interpreted by Python : {e}'

    # Run each unit test
    for test in TASK.test_list:
        try:
            exec(test, namespace)
        except Exception as e:
            # If the test doesn't pass, add it the the failed
            # tests list with error details.
            failed_tests.append(test)
    if len(failed_tests) != 0:
        return "Error during the following tests :\n" + '\n'.join(failed_tests)
    return "All test passed successfully !"

if __name__ == "__main__":
    # Listen to input
    # REPLACE THIS STRING TO 'http' TO USE HTTP INSTEAD OF STDIO
    mcp.run(transport='stdio')
