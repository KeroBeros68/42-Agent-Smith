"""Thought -> Code -> Observation loop engine (§V.1).

Benchmark-agnostic: driven by a TaskInput, a limits config, an LLM provider
and a sandbox connection. Must not contain MBPP- or SWE-bench-specific logic.
"""

from agent_core.parsing import extract_code
from agent_core.provider import LLM, LLMError
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
) -> tuple[list[StepMetrics], str | None]:
    """Run the agent loop and return the per-step metrics and final answer.

    Stops early on final_answer, or if the LLM call itself fails
    (LLMError) — in both cases the steps already collected are kept and
    returned rather than lost. The second element is the code passed to
    final_answer() if the loop stopped that way, else None (max_iterations
    reached or LLMError) — this is what lets the caller set
    SolutionOutput.success/.solution without guessing from the steps. No
    cumulative token/time limit yet.
    """
    llm = LLM(model_name)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    steps: list[StepMetrics] = []
    final_answer: str | None = None

    for step in range(1, max_iterations + 1):
        try:
            metrics = llm.get_response(step, messages)
        except LLMError:
            break
        messages.append({"role": "assistant", "content": metrics.llm_output})
        steps.append(metrics)

        code, warning = extract_code(metrics.llm_output)
        if code is None:
            observation = "No valid code block was found in your response."
            messages.append({"role": "user", "content": observation})
            continue

        metrics.sandbox_input = code
        response = run_code(container, mcp_bridge, code)
        observation = _format_observation(response)
        if warning is not None:
            observation = f"{warning}\n\n{observation}"
        metrics.sandbox_output = observation
        messages.append({"role": "user", "content": observation})

        if response.get("type") == "final_answer":
            final_answer = response.get("answer", "")
            break

    return steps, final_answer


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
