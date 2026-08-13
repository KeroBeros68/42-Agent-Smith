"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

import json
import os

from fastmcp import FastMCP

mcp = FastMCP("MBPP MCP Server")

# Loaded ONCE at startup from the env var the sandbox sets before
# starting the MCP Server.
TASK = json.loads(os.environ.get("MBPP_TASK_JSON", "null")) or {}

@mcp.tool
def run_tests(code: str) -> bool:
    """Run unit tests to check if a given function passes the unit tests."""
    return False

if __name__ == "__main__":
    mcp.run()
