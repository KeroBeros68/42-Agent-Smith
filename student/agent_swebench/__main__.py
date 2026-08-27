"""Entry point for `python -m agent_swebench` (§V.4.1).

Usage:
  uv run python -m agent_swebench --task-file ../cache/swebench_task.json \\
      --output ../cache/swebench_solution.json \\
      --model-name "provider/model" --provider-url "https://provider.api/v1"

Loads a task, drives the sandbox + agent_core.loop against it, and writes a
SolutionOutput to --output. Benchmark-specific glue only: task loading, the
SWE-bench system prompt, and success/solution derivation — the loop itself
(agent_core.loop) has no SWE-bench-specific logic.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from agent_core import loop, manual
from agent_core.schemas import SolutionOutput
from agent_swebench.task import SWEBenchTaskInput
from pydantic import ValidationError
from sandbox import session
from sandbox.config import SandboxConfig
from sandbox.mcp_bridge import MCPBridge

REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_TEMPLATE = REPO_ROOT / "sandbox_template.json"
MCP_SERVER_SCRIPT = REPO_ROOT / "mcp_tools_swebench.py"
DEFAULT_MAX_ITERATIONS = 30


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_swebench")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--provider-url", default=None)
    parser.add_argument(
        "--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS
    )
    return parser


def build_system_prompt(task: SWEBenchTaskInput, tools_doc: str) -> str:
    hints = f"\nHints: {task.hints_text}\n" if task.hints_text else ""
    return f"""You are an autonomous coding agent fixing a real bug in a
software repository.

You work in a loop: Thought, then Code, then Observation.
- Thought: briefly explain your reasoning as plain text.
- Code: exactly one ```python ... ``` block with the code to run.
- After your code runs, the result is given back to you as the next
  message (Observation).

The repository is checked out at /workspace/testbed. Use the available
tools to explore it, locate the code responsible for the issue, and
fix it.

Available tools:
{tools_doc}

Workflow:
1. Explore the repository (read_file, search_code, list_files,
   search_function_or_class_definition_in_code, find_references) to find
   the code responsible for the issue.
2. Edit it with edit_file.
3. Verify your fix with run_tests() — no arguments, it re-runs the
   repository's own test suite against your change.
4. Once run_tests() confirms your fix, retrieve the diff with get_patch()
   and submit it with final_answer(patch) — the diff text, not the code.

IMPORTANT: You must call run_tests() and confirm your fix works before
calling final_answer. Never call final_answer without verifying first.

IMPORTANT: run_tests() already runs the test suite in the correct
environment (interpreter, PYTHONPATH, virtual env). Do NOT try to
manually re-invoke the test runner yourself via run_command — trust
run_tests(). As soon as run_tests() reports success (e.g. "OK"), stop
exploring immediately: call get_patch() and then final_answer(patch)
in your very next step. Do not keep editing or debugging after a
successful run_tests() — you are done.

Example of a full reasoning loop:

Thought: I will look for where the reported function is defined.
Code:
```python
print(search_function_or_class_definition_in_code(name="some_function"))
```
Observation: /workspace/testbed/pkg/module.py:42 def some_function(x):

Thought: I found it. I will fix the bug.
Code:
```python
print(edit_file(
    filepath="/workspace/testbed/pkg/module.py",
    old_str="buggy line",
    new_str="fixed line",
))
```
Observation: Successfully replaced the string !

Thought: Let's verify the fix works.
Code:
```python
print(run_tests())
```
Observation: All tests passed.

Thought: The fix is verified. I will retrieve the diff and submit it.
Code:
```python
print(get_patch())
```
Observation: diff --git a/pkg/module.py b/pkg/module.py
...

Thought: Submitting the verified patch.
Code:
```python
final_answer("diff --git a/pkg/module.py b/pkg/module.py\\n...")
```

Issue: {task.problem_statement}
{hints}"""


def write_output(output_path: Path, solution: SolutionOutput) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(solution.model_dump_json(indent=2))
    os.replace(tmp_path, output_path)


def main() -> None:
    args = build_parser().parse_args()
    start_time = time.time()

    try:
        task = SWEBenchTaskInput.model_validate_json(
            Path(args.task_file).read_text()
        )
    except (FileNotFoundError, json.JSONDecodeError, ValidationError) as e:
        print(f"error: could not load task file: {e}", file=sys.stderr)
        sys.exit(1)

    # mcp_tools_swebench.py reads this env var at import time (it spawns
    # as a subprocess of MCPBridge, so it must be set before instantiating
    # it).
    os.environ["SWE_TASK_JSON"] = task.model_dump_json()

    solution = SolutionOutput(
        task_id=task.instance_id,
        benchmark="swebench",
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
        # Unlike agent_mbpp, the image is task-provided, not built locally
        # from student/sandbox/Dockerfile — build_context=None means
        # session.build_container() pulls it if missing (§VII.2).
        container = session.build_container(
            config, task.docker_image, None, mcp_bridge
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
        # Broad on purpose — same rationale as agent_mbpp/__main__.py.
        solution.error = str(e)
    finally:
        mcp_bridge.close()
        solution.total_time_seconds = time.time() - start_time
        write_output(Path(args.output), solution)

    sys.exit(0 if solution.success else 1)


if __name__ == "__main__":
    main()
