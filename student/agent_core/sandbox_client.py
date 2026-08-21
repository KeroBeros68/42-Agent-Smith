"""Generic client used by the agent loop to talk to the `sandbox` process.

Transport-agnostic (stdio or HTTP), benchmark-agnostic.
"""

from sandbox.container import SandboxContainer
from sandbox.mcp_bridge import MCPBridge
from sandbox.session import relay_tool_calls


def run_code(
    container: SandboxContainer,
    mcp_bridge: MCPBridge | None,
    code: str,
) -> dict:
    """Send code to the sandbox and return its final response.

    Returns the raw response dict (result/error/final_answer) — formatting
    it into a StepMetrics.sandbox_output string is left to the caller
    (loop.py), which is the only piece that knows the surrounding step.
    """
    try:
        container.send({"type": "exec", "code": code})
        return relay_tool_calls(container, mcp_bridge)
    except (ConnectionError, TimeoutError) as e:
        return {
            "type": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "traceback": "",
        }
