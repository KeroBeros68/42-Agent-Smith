"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

import json
import os

from fastmcp import FastMCP
from pydantic import BaseModel, ValidationError


class MBPPException(Exception):
    pass

class MBPPTask(BaseModel):
    task_id: int
    task_definition: str
    function_definition: str
    test_imports: list
    test_list: list

# --- Server Setup ---

mcp = FastMCP("MBPP MCP Server")

# Loaded ONCE at startup from the env var the sandbox sets before
# starting the MCP Server.
try:
    TASK = MBPPTask.model_validate(
        json.loads(os.environ.get("MBPP_TASK_JSON", "null")) or {}
    )
except (ValidationError, json.JSONDecodeError):
    TASK = None

# --- MCP Tools ---

@mcp.tool
def run_tests(code: str) -> bool:
    """Run unit tests to check if a given function passes the unit tests."""
    if TASK is None:
        raise MBPPException('Invalid task format.')
    for test in TASK.test_list:
        # Execute the test
        raise NotImplementedError(f"TASK TEST NOT IMPLEMENTED YET for {test}")
    return True

if __name__ == "__main__":
    # Listen to input
    mcp.run(transport='stdio')
