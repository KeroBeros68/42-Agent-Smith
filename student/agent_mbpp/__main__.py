"""Entry point for `python -m agent_mbpp` (§V.3.1).

Usage:
  uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json \\
      --output ../cache/mbpp_solution.json \\
      --model-name "provider/model" --provider-url "https://provider.api/v1"

Loads a task, drives the sandbox + agent_core.loop against it, and writes a
SolutionOutput to --output. Benchmark-specific glue only: task loading, the
MBPP system prompt, and success/solution derivation — the loop itself
(agent_core.loop) has no MBPP-specific logic.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from agent_core import loop, manual
from agent_core.schemas import SolutionOutput
from agent_mbpp.task import MBPPTaskInput
from pydantic import ValidationError
from sandbox import session
from sandbox.config import SandboxConfig
from sandbox.mcp_bridge import MCPBridge

REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_IMAGE = "agent-smith-sandbox:latest"
SANDBOX_BUILD_CONTEXT = REPO_ROOT / "student" / "sandbox"
SANDBOX_TEMPLATE = REPO_ROOT / "sandbox_template.json"
MCP_SERVER_SCRIPT = REPO_ROOT / "mcp_tools_mbpp.py"
DEFAULT_MAX_ITERATIONS = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_mbpp")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--provider-url", default=None)
    parser.add_argument(
        "--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS
    )
    return parser


def build_system_prompt(task: MBPPTaskInput, tools_doc: str) -> str:
    return f"""You are an autonomous coding agent solving a Python
programming task.

You work in a loop: Thought, then Code, then Observation.
- Thought: briefly explain your reasoning as plain text.
- Code: exactly one ```python ... ``` block with the code to run.
- After your code runs, the result is given back to you as the next
  message (Observation).

Available tools:
{tools_doc}

When you are confident the task is solved, call final_answer(code) with the
complete function code as a string, instead of writing more code.

IMPORTANT: You must call run_tests on your code and see "All test passed
successfully !" before calling final_answer. Never call final_answer on code
you have not verified with run_tests first.

Example of a full reasoning loop:

Thought: I will define the function and immediately verify it with run_tests.
Code:
```python
def add_one(x):
    return x + 1
print(run_tests(code="def add_one(x):\\n    return x + 1"))
```
Observation: All test passed successfully !

Thought: The tests passed, so I can submit this as the final answer.
Code:
```python
final_answer("def add_one(x):\\n    return x + 1")
```

Task: {task.task_definition}
Function signature: {task.function_definition}
"""


def write_output(output_path: Path, solution: SolutionOutput) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(solution.model_dump_json(indent=2))
    os.replace(tmp_path, output_path)


def main() -> None:
    args = build_parser().parse_args()
    start_time = time.time()

    try:
        task = MBPPTaskInput.model_validate_json(
            Path(args.task_file).read_text()
        )
    except (FileNotFoundError, json.JSONDecodeError, ValidationError) as e:
        print(f"error: could not load task file: {e}", file=sys.stderr)
        sys.exit(1)

    # mcp_tools_mbpp.py reads this env var at import time (it spawns as a
    # subprocess of MCPBridge, so it must be set before instantiating it).
    os.environ["MBPP_TASK_JSON"] = task.model_dump_json()

    solution = SolutionOutput(
        task_id=str(task.task_id),
        benchmark="mbpp",
        success=False,
        solution="",
        iterations=0,
        total_requests=0,
        total_input_tokens=0,
        total_output_tokens=0,
        total_time_seconds=0.0,
    )

    mcp_bridge = MCPBridge(stdio_command=f"python3 {MCP_SERVER_SCRIPT}")
    try:
        mcp_bridge.connect()
        tools = mcp_bridge.list_tools()
        tools_doc = manual.build_manual(tools)

        config = SandboxConfig(**json.loads(SANDBOX_TEMPLATE.read_text()))
        container = session.build_container(
            config, SANDBOX_IMAGE, SANDBOX_BUILD_CONTEXT, mcp_bridge
        )
        with container:
            system_prompt = build_system_prompt(task, tools_doc)
            steps, final_answer = loop.run(
                container,
                mcp_bridge,
                model_name=args.model_name,
                system_prompt=system_prompt,
                max_iterations=args.max_iterations,
            )

        solution.system_prompt = system_prompt
        solution.steps = steps
        solution.iterations = len(steps)
        solution.total_requests = len(steps)
        solution.total_input_tokens = sum(s.input_tokens for s in steps)
        solution.total_output_tokens = sum(s.output_tokens for s in steps)
        solution.success = final_answer is not None
        solution.solution = final_answer or ""
    except Exception as e:
        # Broad on purpose: this is the outermost boundary of the CLI.
        # Anything from here down (Docker down, LLMError, MCP connection
        # errors — mcp.shared.exceptions.McpError isn't a ConnectionError,
        # found by checking what mcp_bridge.connect() actually raises)
        # must produce a valid solution.json with `error` set, per §IV.1,
        # not a raw traceback. KeyboardInterrupt/SystemExit are BaseException,
        # not caught here.
        solution.error = str(e)
    finally:
        mcp_bridge.close()
        solution.total_time_seconds = time.time() - start_time
        write_output(Path(args.output), solution)

    sys.exit(0 if solution.success else 1)


if __name__ == "__main__":
    main()
