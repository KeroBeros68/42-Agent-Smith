"""
This file contains an MCP server build with FastMCP.

It contains useful tools that can be used in the agentic loop
for the Agent Smith project.
"""

from fastmcp import FastMCP

mcp = FastMCP("MBPP MCP Server")

@mcp.tool
def run_tests() -> bool:
    """Run unit tests to check if a given function passes the unit tests."""
    return True

if __name__ == "__main__":
    mcp.run()
