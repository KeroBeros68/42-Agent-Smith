"""
This file contains common variables and fonctions shared
between all MCP Servers.
"""

from enum import Enum


class TransportMode(str, Enum):
    """MCP transport modes for the MCP_TRANSPORT env var (§V.2.5)."""

    STDIO = "stdio"
    HTTP = "http"


# Environment variable names crossing the MCP-server-subprocess boundary
# — set by sandbox/mcp_bridge.py when spawning an MCP server over stdio,
# read by mcp_tools_mbpp.py/mcp_tools_swebench.py at import time.
ENV_MCP_TRANSPORT = "MCP_TRANSPORT"
ENV_MCP_TIMEOUT_DELAY = "MCP_TIMEOUT_DELAY"
ENV_MBPP_TASK_JSON = "MBPP_TASK_JSON"
ENV_SWE_TASK_JSON = "SWE_TASK_JSON"


# Sandbox container identity, used by container.py when it creates and
# tags containers. OWNER_PID_LABEL is informational: it makes our own
# containers identifiable in `docker ps` when tracking down orphans, and
# is deliberately no longer a contract between processes — an MCP server
# that had to find its client's container could not be reused by any
# other agent (see mcp_tools_swebench.py).
SANDBOX_UID = 1000
SANDBOX_GID = 1000
DERIVED_IMAGE_PREFIX = "sandbox-executor:"
OWNER_PID_LABEL = "agent-smith.owner-pid"


# Some evaluation scripts can take some times to run
MAX_OUTPUT_CHARS = 50_000


def truncate_output(text: str) -> str:
    # Head-only truncation lost the verdict on a real run_tests() output
    # (1.86M chars, the "Start Test Output" marker sat at char 1,861,195
    # — past any head-only cutoff) — noisy diagnostics (git diff without
    # core.fileMode=false, pip install) fill the head, the actual result
    # is at the tail. Keeping both halves covers each tool's needs:
    # search/list results (useful from the start) and run_tests/
    # run_command output (verdict at the end).
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    half = MAX_OUTPUT_CHARS // 2
    omitted = len(text) - MAX_OUTPUT_CHARS
    return (
        f'{text[:half]}\n'
        f'(... {omitted} characters omitted ...)\n'
        f'{text[-half:]}'
    )
