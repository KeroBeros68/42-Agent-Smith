"""Thought -> Code -> Observation loop engine (§V.1).

Benchmark-agnostic: driven by a TaskInput, a limits config, an LLM provider
and a sandbox connection. Must not contain MBPP- or SWE-bench-specific logic.
"""

from agent_core.parsing import extract_code
from agent_core.provider import LLM
from agent_core.sandbox_client import run_code
from agent_core.schemas import StepMetrics
from sandbox.container import SandboxContainer
from sandbox.mcp_bridge import MCPBridge


def run(
    container: SandboxContainer,
    mcp_bridge: MCPBridge | None,
    model_name: str,
    system_prompt: str,
    max_iterations: int,
) -> list[StepMetrics]:
    """Run the agent loop and return the per-step metrics.

    Stops early on final_answer; otherwise runs for max_iterations. No
    cumulative token/time limit yet, and a failing LLM call still loses
    the current step (loop.py doesn't catch LLMError yet).
    """
    llm = LLM(model_name)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    steps: list[StepMetrics] = []

    for step in range(1, max_iterations + 1):
        metrics = llm.get_response(step, messages)
        messages.append({"role": "assistant", "content": metrics.llm_output})
        steps.append(metrics)

        code = extract_code(metrics.llm_output)
        if code is None:
            observation = "No valid code block was found in your response."
            messages.append({"role": "user", "content": observation})
            continue

        metrics.sandbox_input = code
        response = run_code(container, mcp_bridge, code)
        observation = _format_observation(response)
        metrics.sandbox_output = observation
        messages.append({"role": "user", "content": observation})

        if response.get("type") == "final_answer":
            break

    return steps


def _format_observation(response: dict) -> str:
    msg_type = response.get("type")
    if msg_type == "result":
        return response.get("stdout", "")
    if msg_type == "error":
        return response.get("traceback") or (
            f"{response.get('error_type', 'Error')}: "
            f"{response.get('message', '')}"
        )
    if msg_type == "final_answer":
        return response.get("answer", "")
    return repr(response)
