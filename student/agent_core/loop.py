"""Thought -> Code -> Observation loop engine (§V.1).

Benchmark-agnostic: driven by a TaskInput, a limits config, an LLM provider
and a sandbox connection. Must not contain MBPP- or SWE-bench-specific logic.
"""

import time

from agent_core.parsing import extract_code
from agent_core.provider import LLM, LLMError
from agent_core.sandbox_client import run_code
from agent_core.schemas import StepMetrics
from sandbox.container import SandboxContainer
from sandbox.mcp_bridge import MCPBridge

_SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


def _announce(step: int, word: str) -> None:
    frame = _SPINNER_FRAMES[step % len(_SPINNER_FRAMES)]
    print(f"{frame} [step {step}] {word}...")


def run(
    container: SandboxContainer,
    mcp_bridge: MCPBridge | None,
    model_name: str,
    system_prompt: str,
    max_iterations: int,
    max_input_tokens: int | None = None,
    max_output_tokens: int | None = None,
    max_time_seconds: float | None = None,
) -> tuple[list[StepMetrics], str | None]:
    """Run the agent loop and return the per-step metrics and final answer.

    Stops early on final_answer, or if the LLM call itself fails
    (LLMError) — in both cases the steps already collected are kept and
    returned rather than lost. The second element is the code passed to
    final_answer() if the loop stopped that way, else None (max_iterations
    reached or LLMError) — this is what lets the caller set
    SolutionOutput.success/.solution without guessing from the steps.

    Cumulative token/time budgets (§VI.1.1/1.2) are enforced between
    iterations: checked at the start of each step against the running
    total from prior steps — usage for a call is only known once it
    returns, so this can't preempt mid-call, only prevent starting
    another one once the budget is already exhausted. None disables the
    corresponding check (e.g. no such budget applies to the REPL).
    """
    llm = LLM(model_name)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    steps: list[StepMetrics] = []
    final_answer: str | None = None
    start_time = time.time()
    total_input_tokens = 0
    total_output_tokens = 0

    for step in range(1, max_iterations + 1):
        if (
            max_time_seconds is not None
            and time.time() - start_time > max_time_seconds
        ):
            break
        if (
            max_input_tokens is not None
            and total_input_tokens > max_input_tokens
        ):
            break
        if (
            max_output_tokens is not None
            and total_output_tokens > max_output_tokens
        ):
            break

        _announce(step, "Thinking")
        try:
            metrics = llm.get_response(step, messages)
        except LLMError:
            break
        messages.append({"role": "assistant", "content": metrics.llm_output})
        steps.append(metrics)
        total_input_tokens += metrics.input_tokens
        total_output_tokens += metrics.output_tokens

        code, warning = extract_code(metrics.llm_output)
        if code is None:
            _announce(step, "Retrying")
            observation = "No valid code block was found in your response."
            messages.append({"role": "user", "content": observation})
            continue

        _announce(step, "Executing")
        metrics.sandbox_input = code
        response = run_code(container, mcp_bridge, code)
        observation = _format_observation(response)
        if warning is not None:
            observation = f"{warning}\n\n{observation}"
        metrics.sandbox_output = observation
        messages.append({"role": "user", "content": observation})

        if response.get("type") == "final_answer":
            final_answer = response.get("answer", "")
            _announce(step, "Done")
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
