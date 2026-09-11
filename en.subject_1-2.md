# Agent Smith

## Autonomous reasoning, code generation, and execution

Summary: In this project, you will build an **agentic framework** capable ofautonomously solving coding challenges.

Your agent will reason, write code, execute it in a sandboxed environment, and iterate until a solution is found.

This project introduces **Code Agents**, **Model Context Protocol (MCP)**, andcontrolled code execution.

Made in collaboration with @ldevelle

Version: 1.1

# Contents

| I | Foreword | 2 |
| --- | --- | --- |
| II | AI Instructions | 3 |

**III Overview 5**III.1 What is a Code Agent? . . . . . . . . . . . . . . . . . . . . . . . . . . 6

**IV Common Instructions 9**IV.1 General Rules . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 9

IV.2 Technical Constraints . . . . . . . . . . . . . . . . . . . . . . . . . . . 9

**V Mandatory Part 10**V.1 Agentic Framework . . . . . . . . . . . . . . . . . . . . . . . . . . . . 10

V.1.1 Common Output Models . . . . . . . . . . . . . . . . . . . . . . . 11 V.1.2 Development Approach . . . . . . . . . . . . . . . . . . . . . . . . 13

| V.2 V.3 | The Sandbox . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . MBPP Agent . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 17 13 |
| --- | --- |
| V.4 V.5 | SWE-bench Agent . . . . . . . . . . . . . . . . . . . . . . . . . . . . . Mandatory Tools . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 18 20 |

V.5.1 File System Tools . . . . . . . . . . . . . . . . . . . . . . . . . . . 21 V.5.2 Code Search Tools . . . . . . . . . . . . . . . . . . . . . . . . . . 21

V.5.3 Execution Tools . . . . . . . . . . . . . . . . . . . . . . . . . . . . 21 V.6 LLM API Providers . . . . . . . . . . . . . . . . . . . . . . . . . . . . 22

V.6.1 Examples of Free Providers . . . . . . . . . . . . . . . . . . . . . 22 V.7 Model Benchmark Report . . . . . . . . . . . . . . . . . . . . . . . . . 23

**VI Evaluation 25**VI.1 Hard Requirements and Limits . . . . . . . . . . . . . . . . . . . . . . 26

VI.1.1 MBPP Limits . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 26 VI.1.2 SWE-bench Limits . . . . . . . . . . . . . . . . . . . . . . . . . . 26

VI.2 Pass Criteria . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 27 VI.3 Grading Criteria . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 27

VI.4 What We Will Test in the Review . . . . . . . . . . . . . . . . . . . . 27 VI.4.1 AI Safety in Evaluation . . . . . . . . . . . . . . . . . . . . . . . . 28

VI.5 Evaluation logging structure . . . . . . . . . . . . . . . . . . . . . . . 28

| VII Readme Requirements | 29 |
| --- | --- |
| VIII Submission | 31 |

1

# Chapter I

# Foreword

_Software engineering is no longer only about writing correct code, it is about_ under-standing systems, navigating large codebases, debugging failures, and iter-

**ating efficiently**. Modern LLMs generate code well, but fixing real bugs also needsexploration, hypothesis testing, execution, and observation.

_This is where_ Agent Smith _comes in. A Code Agent is not just a model that writes code:it_ reasons about a task, interacts with tools, executes code safely, observes

**results, and adapts its strategy**. In this project, you will design and implement sucha system, moving beyond static prompts and JSON-based tool calling to build a **fully**

**agentic loop** driven by executable Python code.

2

# Chapter II

# AI Instructions

### ● Context

AI is now a powerful coding partner — alongside your peers — for tackling large and demanding projects. You will guide it through both technical and non-technical aspects

of your work.

AI tools can boost your efficiency and improve the quality of your output, but you should be able to dive deep into any part of the project without relying on them.

Your AI partner supports you, but you remain fully responsible for making informed technical decisions and to clearly explain and defend them.

### ● Main message

**☛** Strive for a mature and responsible use of AI.

**☛** Never let AI take responsibility for decisions — especially when it lacks awarenessof your goals, constraints, or team dynamics.

**☛** Maintain creativity, innovation, and human oversight through active collaborationwith your peers. AI is trained on existing data and rarely generates truly new ideas.

**☛** Stay informed about emerging trends and be ready to adapt to new concepts andtechnologies.

### ● Learner rules:

- **•** Maintain intellectual leadership over your projects and make your own informeddecisions.
- **•** Prioritise the collective intelligence of your team and peers.
- **•** Actively stay informed about the ongoing evolution of AI technologies.
3

Agent Smith Autonomous reasoning, code generation, and execution

### ● Phase outcomes:

- **•** AI engineering skills.
- **•** Increased efficiency.
- **•** Greater reliability and quality.
- **•** A pioneering mindset.
### ● Comments and examples:

- **•** Your peers can identify trade-offs, question assumptions, and help you improve. Thefirst answer from an AI might not be the best — it may lack efficiency, security, or
real added value. Now more than ever, you should rely on your peers.

- **•** AI can make you faster, but your peers make you better. Collaboration, discussion,and mutual challenge are key to success.
- **•** Be transparent about how AI was used in your projects, and clearly identify whatwas generated by AI tools.
**✓** Good practice:

I asked AI to help generate unit tests for my API. I reviewed them with my teammate, and we adjusted them for edge cases. It saved time, and we both learned something

new.

**✗** Bad practice:

I had AI generate the entire architecture of my project. It “works,” but when I’m asked to explain design decisions during the peer review or in front from of a customer, I

cannot. I lose credibility and I fail.

4

# Chapter III

# Overview

This project explores a new paradigm in AI-driven software engineering: **agentic codegeneration**.

Unlike classical approaches where an LLM outputs a final answer, your system will allow the model to:

- **•** Write executable Python code
- **•** Call tools directly from code
- **•** Observe execution results
- **•** Iterate until the task is solved
Your agent will operate through a structured loop: _Thought_ **→** _Code_ **→** _Observation_.

You will apply this framework to two different benchmarks:

5

Agent Smith Autonomous reasoning, code generation, and execution

- _•_ **MBPP**: algorithmic Python problems
- _•_ **SWE-bench**: real-world bug fixing in production repositories
The core challenge of this project is not only to make the agent intelligent, but also tomake it **safe, controlled, reproducible, and measurable**.

In particular, you are expected to **evaluate and benchmark multiple language mod-els** in order to analyze their performance and identify the most effective ones according

to success rate and iteration efficiency.

### III.1 What is a Code Agent?

A **Code Agent** is an AI system that can:

- **•** Reason about a programming task
- **•** Generate executable code
- **•** Execute that code in a controlled environment
- **•** Use tools to interact with files, tests, and repositories
- **•** Observe the results and refine its approach
In this project, you will implement a **code-based tool calling** approach, where the LLMgenerates Python code such as:

result = search_code("validate_email")_print (result)_

content = read_file("models.py", 1, 50)_print (content)_

This approach is more expressive than JSON tool calling, allowing:

- **•** Persistent variables between steps
- **•** Conditional logic and loops
- **•** Complex multi-step reasoning
6

Agent Smith Autonomous reasoning, code generation, and execution

7

Agent Smith Autonomous reasoning, code generation, and execution

1. **Agent/Orchestrator** is the central loop. It calls the LLM, extracts code, feeds itto the sandbox, reads observations, and repeats.
2. **Code Extraction** is a transform step between the LLM response and the sandbox.
3. **Sandbox** is the execution boundary. It enforces security restrictions on LLM-generated code. The sandbox contains an MCP client that connects to an external
MCP server.

4. **final_answer()** is a built-in sandbox construct — it is NOT an MCP tool.
5. **MCP Server(s)** run as separate process(es) (via stdio or HTTP). Only your ownMCP server(s) are allowed.
8

# Chapter IV

# Common Instructions

### IV.1 General Rules

- _•_ You must use **Python 3.10**.
- _•_ You must use **uv** as your package manager.
- **•** Your project must follow clean software architecture principles.
- **•** All errors must be handled gracefully — crashes during evaluation will result infailure.
- **•** Your code must be readable, structured, and documented.
- _•_ All execution must happen in a **sandboxed environment**.
### IV.2 Technical Constraints

- **•** You must support multiple LLM providers and models.
- **•** You must implement usage tracking (tokens, retries, latency, requests).
- **•** You must implement a configurable sandbox (imports, filesystem access), as speci-fied in Section 5.2.
- **•** Your tools must work independently of the agent loop.
- **•** You must not use any library that re-implements agent orchestration logic (e.g.,llama-index, smolagents, langgraph, crewai, autogen).
- **•** The agent loop must be your own implementation.
- **•** Even though the project can be completed without it, multi-agent architectures areallowed, but the orchestration must be your own code.
9

# Chapter V

# Mandatory Part

### V.1 Agentic Framework

In this project, you must build an **agentic framework** capable of autonomously solvingcoding challenges.

For LLM provider selection, see Section 5.6.1 for examples of free-tier APIs.

Your system must:

_1. Implement a_ Thought **→** Code **→** Observation _loop_
2. Extract LLM-generated Python code from the model responses
```
When benchmarking across multiple providers (Section 5.7), your
extraction layer should handle different output formats that LLMs
produce — as well as to fit what the LLMs you use were trained on —
not just Python code blocks. A non-exhaustive list:
(a) Python code blocks (primary) — “‘python ... “‘ <end_code>
(b) XML tool calls — Anthropic-style <invoke
name="..."><parameter>...</parameter></invoke>
(c) JSON/Hermes tool calls — <tool_call>{"name": "...",
"arguments": {...}}</tool_call>
(d) ReAct format — Action: tool_name / Action Input: {...}
Non-Python formats should be converted to equivalent Python function
calls (e.g., result = read_file(filepath="/testbed/file.py")) before
sandbox execution. This lets the sandbox remain format-agnostic
while supporting any model.
```

3. Execute the generated code inside a sandboxed environment
4. Feed the sandbox execution results back to the LLM
10

Agent Smith Autonomous reasoning, code generation, and execution

5. Solve benchmark tasks autonomously using the agent loop
6. Design the **system prompt**, including:
- **•** clear documentation of the available tools
- _•_ examples of structured response slots (e.g. **Thought**, **Code**, **Observation**)
- **•** examples of effective agent reasoning loops
```
Your sandbox must provide explicit feedback to the LLM in all of
these situations:
• No valid code block was found in the model’s response
• A code block was malformed but was interpreted anyway (explain
how)
• Execution hit the timeout and output is partial
• Tool output was truncated due to size limits
• An edit introduced a syntax error or lint violation
The LLM should never be left guessing about what happened. Silent
failures lead to hallucinated observations and wasted iterations.
```

V.1.1 Common Output Models

Both MBPP and SWE-bench agents produce the same **StepMetrics**/**SolutionOutput**shape; only the **benchmark** and **solution** field semantics change (Python code for MBPP,

a git patch for SWE-bench).

```
class StepMetrics(BaseModel):
"""Metrics for a single agent step.
Each step corresponds to one LLM generate -> sandbox execute cycle.
All fields are required for evaluation, empty strings are acceptable
for steps where a field doesn't apply (e.g., no sandbox execution).
"""
step: int = Field(..., description="1-indexed iteration number")
input_tokens: int = Field(..., description="Tokens sent to the LLM for this
step")
output_tokens: int = Field(..., description="Tokens generated by the LLM
for this step")
request_time_ms: float = Field(..., description="Wall-clock time for the
LLM API call in milliseconds")
timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(),
description="ISO 8601 timestamp of when this step was recorded")
api_url: str = Field(default="", description="Base URL of the LLM API
endpoint (e.g., 'https://openrouter.ai/api/v1')")
```

11

Agent Smith Autonomous reasoning, code generation, and execution

```
model_name: str = Field(default="", description="Model identifier used for
this step (e.g., 'qwen/qwen3-235b-a22b-2507')")
llm_output: str = Field(default="", description="Raw text generated by the
LLM before code extraction")
sandbox_input: str = Field(default="", description="Python code sent to the
sandbox for execution")
sandbox_output: str = Field(default="", description="Sandbox execution
result (stdout/stderr/error message)")
retries: int = Field(default=0, description="Number of LLM API retries
before getting a successful response (0 = first attempt succeeded)")
class SolutionOutput(BaseModel):
"""Output from student solution, required format for evaluation.
This is the JSON structure your agent must produce and write to solution.
json.
The moulinette validates this against task correctness and metrics limits.
"""
task_id: str = Field(..., description="Task identifier (MBPP task_id as
string, or SWE-bench instance_id)")
benchmark: str = Field(..., description="Benchmark type: 'mbpp' or '
swebench'")
success: bool = Field(..., description="Whether the agent believes it
solved the task")
solution: str = Field(..., description="For MBPP: the Python function code.
For SWE-bench: the git patch (diff)")
iterations: int = Field(..., description="Number of agent loop iterations
used")
total_requests: int = Field(..., description="Total number of LLM API
requests made (including retries)")
total_input_tokens: int = Field(..., description="Sum of input_tokens
across all steps")
total_output_tokens: int = Field(..., description="Sum of output_tokens
across all steps")
total_time_seconds: float = Field(..., description="Wall-clock time from
agent start to finish")
steps: List[StepMetrics] = Field(default_factory=list, description="Per-
step metrics, one entry per agent iteration")
system_prompt: str = Field(default="", description="Full system prompt sent
to the LLM (for provenance checking)")
error: Optional[str] = Field(default=None, description="Error message if
the agent failed (None if successful)")
timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(),
description="ISO 8601 timestamp of when the solution was produced")
```

12

Agent Smith Autonomous reasoning, code generation, and execution

```
Each step in the steps array of SolutionOutput must include api_url,
model_name, fields identifying the LLM endpoint used for that step,
plus llm_output (raw LLM response), sandbox_input (code sent to
sandbox), sandbox_output (execution result), and retries (API retry
count).
```

V.1.2 Development Approach

Building an autonomous agent is a complex task. Here are questions to guide your development:

**Starting out:** Which benchmark is simpler and should be tackled first? Am I testingwith the most capable model available, or handicapping myself with constraints too early?

Can my system solve the easiest task with token and iteration limits temporarily removed? If not, adding constraints will only make it worse.

**Debugging your agent:** What happens in the first 3–5 iterations: tool-callingstruggles, hallucinated observations, or an unexpected path? Have I tried solving the

target task myself, manually, and does my prompt reflect that methodology? For SWE- bench, break the eval script into smaller goals and track whether individual tests pass

rather than waiting for the full script to succeed.**Scaling up:** Does a solution that works on one task generalize, or did I overfit? Am

I optimizing too early (tokens, model choice), or have I proven the approach works first? Different models prefer different tool-calling styles: am I fighting the model’s natural

tendencies, or working with them?

### V.2 The Sandbox

This part focuses on the design and implementation of a secure and configurable execution sandbox for the agent.

_1. Implement a_ sandbox CLI usage
```
# Launch interactive sandbox
uv run sandbox
# With custom configuration
uv run sandbox sandbox_template.json
# With MBPP tools (stdio)
uv run sandbox --mcp-stdio "python mcp_tools_mbpp.py" sandbox_template.
json
# With MBPP tools (HTTP)
uv run sandbox --mcp-server <URL>
# With SWE-bench tools
uv run sandbox --mcp-stdio "python mcp_tools_swebench.py"
sandbox_template.json
```

13

Agent Smith Autonomous reasoning, code generation, and execution

The _interactive sandbox_ (**uv run sandbox** with no task argument) is a REPL-style command-line mode. It must open a prompt, read user-typed code in a loop,

and execute each entry inside the sandbox namespace, subject to the same import, filesystem, timeout and memory restrictions defined in Section 5.2, with the con-

nected MCP tool wrappers and **final_answer** available. After each entry it printsthe result or any raised error and returns to the prompt. It exits cleanly on the

**exit** command or on EOF (**Ctrl+D**).

2. Implement a **final_answer** tool
```
What final_answer IS:
```

**final_answer** is a callable function that the sandbox injects into the executionnamespace. When the agent’s code calls **final_answer(answer_string)**, the sand-

box captures the argument and signals to the agent loop that the task is complete.The agent loop then terminates and produces the **SolutionOutput**.

**What** _final_answer_ **is NOT:** _final_answer_ is **not** an MCP tool — it is notprovided by any MCP server. It is always available in the sandbox namespace re-

gardless of which MCP server is connected. MCP tools operate outside the sandbox(e.g., reading files in Docker, running tests), while **final_answer** operates within

the sandbox to control the agent loop.

```
How to use final_answer:
```

- _•_ **MBPP**: call _final_answer(your_solution_code)_:pass your Python code as the argument
- _•_ **SWE-bench**: call _final_answer(get_patch())_:pass the git patch retrieved via _get_patch()_ as the argument
**Architectural boundary:**The sandbox provides two kinds of callable functions in the execution namespace:

(a) **MCP tool wrappers**:discovered dynamically from the connected MCP server

(b) **final_answer**: always present, provided by the sandbox itself

When you connect a different MCP server, the MCP tool wrappers change but**final_answer** remains.

**Exception propagation:** Your sandbox must correctly propagate exceptions thatcontrol program flow. In particular, _KeyboardInterrupt_ and _SystemExit_ must not

be silently caught — they need to reach the agent loop for proper shutdown.

3. Enforce sandbox security constraints: Running LLM-generated code is inherentlyrisky. Your sandbox is not just a technical component; it is a **safety boundary**
14

Agent Smith Autonomous reasoning, code generation, and execution

between an autonomous system and the real world.

- **•** _Import restrictions_: Only modules from the configured allowlist may beimported
- _•_ _Filesystem restrictions_: file access by the sandboxed code is limited to anallowlist of directories (the **allowed_directories** field of **SandboxConfig**).
These are paths on the filesystem the sandbox process itself sees, evaluated inside the sandbox, not host-only paths: any directory the code must reach

has to be in the allowlist. Several entries are allowed so you can keep thetask workspace (e.g., **/testbed**) separate from a writable scratch/runtime area

(e.g., **/tmp/agent**); anything outside the allowlist is denied.

- _•_ **No network access**: Prevent any outbound or inbound network connections
- _•_ **Execution timeout**: Terminate code exceeding the configured timeout (ap-plies only to sandboxed code)
- _•_ **Memory limits**: Terminate code exceeding allowed RAM usage
- **•** _Restricted builtins_: Remove or override dangerous builtins to prevent priv-ilege escalation
4. Integrate an **MCP server**
- **•** Mandatory tools must be integrated into the agent
- **•** MCP tools, resources, and prompts must be exposed
- **•** MCP tools must be callable as Python functions from the sandbox
- _•_ The system will be tested with an **unknown MCP server**
- **•** The MCP tool files (mcp_tools_mbpp.py, mcp_tools_swebench.py) shouldbe located at the root of your repository
- **•** Both stdio and streamable HTTP transports must be supported for MCPserver connections
5. Generate a sandbox manual to be fed to the LLM prompt, which must include the MCP tools doc, or how to access it.
```
The sandbox manual should be dynamically generated from the connected
MCP server’s tool schemas — tool names, descriptions, and parameter
types. When a different MCP server is connected, the manual should
automatically reflect that server’s tools.
The manual is what the LLM reads to understand what tools are
available and how to call them.
```

Sandbox limits and behavior must be configurable using **Pydantic models and JSONconfiguration files**.

15

Agent Smith Autonomous reasoning, code generation, and execution

```
class SandboxConfig(BaseModel):
"""Sandbox configuration for student solutions.
Uses allowlist approach: only imports in authorized_imports are allowed.
Everything else is blocked by default.
"""
authorized_imports: List[str] = Field(default_factory=lambda: [
"math", "math.*",
"collections", "collections.*",
"itertools", "re", "json",
"typing", "typing.*",
"functools", "operator",
"heapq", "bisect", "copy",
"string", "random",
"datetime", "datetime.*",
"array", "cmath",
])
allowed_directories: List[str] = Field(default_factory=lambda: [
"/testbed", "/tmp/agent"
])
max_execution_time_seconds: int = 30
max_memory_mb: int = 512
```

An entry ending in **.*** also allows importing that module’s submodules (e.g. **collections.***permits **collections.abc**).

When a different MCP server is connected, the sandbox should dynamically discover and expose that server’s tools. Your mandatory tools are only present when your own MCP

server is connected.

```
The sandbox is the central execution layer. It connects to an MCP
server and exposes its tools as callable Python functions within
the sandbox namespace. The sandbox wraps the MCP client, not the
other way around. The sandbox and MCP tools are independent security
domains: the sandbox restricts what LLM-generated Python code can
do (imports, paths, timeout, memory), while MCP tool actions happen
outside the sandbox and are not subject to the sandbox timeout (e.g.
a tool spawning an external process).
You are expected to implement the security mechanisms using only
standard Python libraries and builtins. No external packages like
RestrictedPython are allowed.
```

16

Agent Smith Autonomous reasoning, code generation, and execution

Sandbox isolation approaches

```
Think about it: untrusted code inside your own process or in a
separate one? Each choice trades off security boundaries, timeout
handling (how do you kill runaway code?), and communication (how do
you get results back?). Multiple valid approaches exist, pick what
fits your architecture.
```

### V.3 MBPP Agent

In this part, you will implement an autonomous agent dedicated to solving **MBPP(Mostly Basic Python Problems)** tasks.

_1. Implement an_ agent CLI interface
```
# 1. Dump a task
cd moulinette
uv run moulinette_eval dump mbpp --output ../cache/mbpp_task.json
# 2. Run your agent
cd ../student
uv run python -m agent_mbpp --task-file ../cache/mbpp_task.json \
--output ../cache/mbpp_solution.json \
--model-name "model/name" --provider-url "https://provider.api/v1"
# 3. Validate solution
cd ../moulinette
uv run moulinette_eval validate mbpp ../cache/mbpp_task.json \
../cache/mbpp_solution.json
```

- **•** Task loading
- **•** Agent execution
_2. Implement_ MBPP MCP tools
- _•_ **run_tests(code, test_list)**Run a candidate solution against the given test assertions. It returns a JSON
string with a **success** boolean (whether all assertions passed) and an **output**field.

- **•** You may implement any additional tools you consider useful
_3. Define_ Pydantic models _for:_
- **•** Task input
17

Agent Smith Autonomous reasoning, code generation, and execution

```
class MBPPTaskInput(BaseModel):
"""Input for MBPP task evaluation."""
task_id: int
task_definition: str
function_definition: str
test_imports: List[str] = Field(default_factory=list)
test_list: List[str] = Field(default_factory=list)
```

- _•_ Agent output: same **StepMetrics**/**SolutionOutput** models as in Section 5.1(**benchmark="mbpp"**, **solution** = your function code)
4. Design your agent to operate within the limits defined in Section 6.1 (iterations, tokens, time). The evaluation validates that your agent’s output stays within these
limits. **max_iterations** should be a configurable parameter of your agent loop.

External LLM providers are allowed, provided the interface remains compliant with the project constraints.

### V.4 SWE-bench Agent

This part focuses on implementing an autonomous agent capable of solving **SWE-bench**tasks inside Dockerized environments.

For SWE-bench, both approaches are valid: (a) deploy the sandbox inside the Docker container, or

(b) run the sandbox on the host with MCP tools bridging into Docker.

Regardless of choice, sandbox security constraints must be enforced.

- **•** Fix real bugs or implement features in real repositories
- **•** Explore codebases inside Docker containers, you are responsible to clean it afteryour program execution
- **•** Generate and submit valid patches using ’git -c core.fileMode=false diff’
```
When testing your SWE-bench tools in isolation, the moulinette sets
the environment variable TESTBED_PATH to the repository root before
starting your MCP server. Your tools must read this exact variable
name to locate the repository.
```

You may install additional dependencies inside the Docker container (e.g., ruff, jedi, tree) to enhance your tools.

18

Agent Smith Autonomous reasoning, code generation, and execution

```
For initial testing, try the simplest task first:
sympy__sympy-14711, sympy__sympy-13480, pydata__xarray-4629. What
happens when you remove unused tools from your setup?
```

_1. Implement an_ agent CLI interface
```
# 1. Dump a task
cd moulinette
uv run moulinette_eval dump swebench --output ../cache/swebench_task.json
# 2. Run your agent
cd ../student
uv run python -m agent_swebench --task-file ../cache/swebench_task.json \
--output ../cache/swebench_solution.json \
--model-name "model/name" --provider-url "https://provider.api/v1"
# 3. Validate solution
cd ../moulinette
uv run moulinette_eval validate swebench ../cache/swebench_task.json \
../cache/swebench_solution.json
```

_2. Implement_ SWE-bench MCP tools
- **•** Tools must follow the specification defined in Mandatory Tools
- **•** You may implement any additional tools you consider useful
_3. Define_ Pydantic models _for:_
- **•** Task input
```
class SWEBenchTaskInput(BaseModel):
"""Input for a SWE-bench task, provided by the moulinette.
Your agent receives this and must produce a git patch that fixes
the issue.
"""
instance_id: str = Field(..., description="SWE-bench instance
identifier (e.g., 'sympy__sympy-23534')")
problem_statement: str = Field(..., description="The GitHub issue
description, what needs to be fixed")
docker_image: str = Field(..., description="Full Docker image
name to pull (e.g., 'swebench/sweb.eval.x86_64.
sympy_1776_sympy-23534:latest')")
eval_script: str = Field(..., description="Bash script to run
inside the container to evaluate the patch")
```

19

Agent Smith Autonomous reasoning, code generation, and execution

```
hints_text: str = Field(default="", description="Optional hints
about the issue (may be empty)")
repo: str = Field(default="", description="Repository name (e.g.,
'sympy/sympy')")
```

- _•_ Agent output (patch): same **StepMetrics**/**SolutionOutput** models as in Sec-tion 5.1 (**benchmark="swebench"**, **solution** = your git patch)
4. Enforce **hard limits** as defined in Section 6.1
External LLM providers are allowed, provided the agent remains fully compatible with the evaluation infrastructure.

**SolutionOutput** must include a **system_prompt** field containing the full system promptsent to the LLM. Each step in **steps** must include **llm_output**, **sandbox_input**, and

**sandbox_output** fields logging the raw LLM response, the Python code sent to the sand-box, and the execution result. A **retries** field tracks how many LLM API retries were

needed for the step.

```
{
"steps": [
{
"step": 1,
"llm_output": "I'll read the file to understand the module.\n```python\
nresult = read_file(filepath=\"/testbed/src/module.py\")\n```",
"sandbox_input": "result = read_file(filepath=\"/testbed/src/module.py\")
",
"sandbox_output": "def solve(x):\n return x + 1\n...",
"retries": 0,
"input_tokens": 1234,
"output_tokens": 567,
"..."
}
]
}
```

This metadata is inspected during evaluation to verify the agent solved tasks through legitimate code exploration and reasoning, not by looking up solutions from pull requests,

issues, or external sources.

### V.5 Mandatory Tools

You must implement all the following tools. Each tool is exposed by the MCP (Model Context Protocol) server and will be tested independently in the context of the SWE-

bench benchmark.

20

Agent Smith Autonomous reasoning, code generation, and execution

V.5.1 File System Tools

- _•_ **read_file(filepath, start_line, end_line)**Read the content of a file with line numbers.
The output format must be similar to **cat -n**:

```
<line_number>: <line_content>
<line_number>: <line_content>
...
```

- _•_ **edit_file(filepath, old_str, new_str)**Replace an exact string in a file with a new string.
- _•_ **list_files(directory, pattern)**List files in a directory matching a given pattern.
V.5.2 Code Search Tools

- _•_ **search_code(pattern, file_pattern)**Perform a grep-like search in the codebase.
The output must follow this format:

```
/absolute/path_to_file.py:<line_number> <line_content>
/absolute/path_to_other_file.py:<line_number> <line_content>
...
```

- **•** search_function_or_class_definition_in_code(name)_Find the definition of a function or a class._
The output format must be similar to search_code format.

- _•_ **find_references(name, filepath, line)**Find all usages of a symbol (function or class).
The output format must be similar to search_code format.

V.5.3 Execution Tools

- _•_ **run_tests()**Execute the evaluation script.
- _•_ **get_patch()**Retrieve the unified **git diff** of all changes made to the repository, depending on
the implementation.

- _•_ **run_command(command, workdir)**Execute a shell command in the specified working directory.
Returns the command’s stdout, stderr, and exit code.

21

Agent Smith Autonomous reasoning, code generation, and execution

### V.6 LLM API Providers

To implement your agent, you will need to perform calls to **Large Language Model(LLM) APIs**. Several providers offer free tiers or usage quotas that are sufficient for

development and experimentation.

The list below is provided for **illustrative purposes only**. It is based on publicly avail-able resources and may evolve over time.

**You are free to use other providers** as long as your system complies with the projectrequirements (free tier, multiple API tokens per provider).

The dataset your agent is evaluated on is called SWE-bench Verified. Knowing this, you can find:

- _•_ **Model leaderboards**: which LLMs perform best on real-world coding tasks?
- _•_ **Agent system descriptions**: how do the top-performing systems design theiragent loop, tools, and prompts?
- _•_ **Per-task traces and evaluations** — how does a specific model perform on theexact task you’re iterating on? This can help you choose the right model for your
first debugging cycles.

```
What happens if the model keeps generating after a tool call instead
of waiting for real execution output? Use a stop_sequences (or stop)
API parameter (e.g. <end_code>, </tool_call>) to stop generation at
the token that ends a code block, otherwise the model may hallucinate
fictional tool output instead of waiting for the real one.
```

V.6.1 Examples of Free Providers

Examples include OpenRouter, Together AI, Groq, Google AI Studio (Gemini), Mistral AI, Cohere, Fireworks AI, Perplexity AI, and Anyscale (non-exhaustive).

Ensure your implementation supports **multiple API keys per provider** and considerimplementing provider fallback. Rate limits and quotas may vary, especially under load

during evaluation.

Important:

- **•** _This list is_ not exhaustive and not contractual_._
- **•** Access conditions, quotas, and available models may change over time.
- **•** Learners are encouraged to explore additional providers or to use self-hosted modelsif needed.
- **•** The entire solution must rely exclusively on free tiers.
- **◦** No paid plans, purchased credits, or billing-enabled accounts are allowed.
- **◦** The project must be fully executable using only free quotas at evaluation time.
22

Agent Smith Autonomous reasoning, code generation, and execution

- _•_ Multi-token management is mandatory.
- **◦** _Your system must support_ multiple API tokens per provider_._
- **◦** Token rotation must be implemented to handle rate limits and quota exhaus-tion.
- **•** Your implementation must be sufficiently _abstract_ to allow switching providerswithout major refactoring.
```
The choice of provider is not graded. The quality of your
abstraction, error handling, and overall architecture is.
```

### V.7 Model Benchmark Report

Raw solve rate only tells part of the story of which model is best for your agent, explo- ration efficiency, token cost, provider reliability, and iteration discipline matter too. You

must produce a benchmark report (_BENCHMARK_REPORT.md_ at the root of your repository)comparing at least **5 models** across at least **2 providers** on the same set of at least **3**

SWE-bench tasks_._

```
Free-tier providers enforce daily token/request quotas, and running
5 models can exhaust one before you’re done. Since more providers
means more independent quotas to draw from, we recommend keeping
more than 2 providers ready rather than the bare minimum, so a single
quota wall doesn’t stall your benchmark run.
```

Your report must include:

1. **Setup**: Which models/providers were compared, which tasks were used, and whythose tasks were selected
2. _Results table_: For each model **×** task combination:
- **•** Pass/Fail
- **•** Iterations used
- **•** Total input tokens
- **•** Total output tokens
- **•** Wall-clock time
3. **Provider reliability**: For each model/provider:
- **•** Average response time per request
- **•** Number of retries needed (rate limits, timeouts, errors)
23

Agent Smith Autonomous reasoning, code generation, and execution

- **•** Overall availability during benchmark runs
4. **Intermediary metrics** (at least 2 of the following):
- **•** Step at which the agent first reads/edits the file that appears in the final patch(exploration efficiency)
- **•** Step at which test failures first decrease vs baseline (partial progress)
- _•_ Iterations between “tests first pass” and **final_answer** (submission discipline
- zero is ideal)
These metrics can be measured manually by inspecting your **solution.json** files

- automation is not required. What matters is the analysis, not the tooling.
5. **Ablation study**: At least one before/after comparison of a change to your agent(prompt, tools, parameters) on the same tasks with the same model
6. **Conclusions**: Which model(s) you selected for your final pipeline and why. Whichmodels can be disregarded and why. Based on your data.
The backing **solution.json** files must be present in your repository.

24

# Chapter VI

# Evaluation

During evaluation, API keys and configuration are provided via a ‘.env‘ file passed as a required argument to evaluation scripts:

```
./exam_TYPE.sh --student-path ./student --moulinette-path ./moulinette --env-
file /path/to/.env
```

Your CLI must support loading API keys from environment variables. Students should use standard environment variables (e.g., ‘OPENROUTER_API_KEY‘).

| exam_mbpp.sh 5 random tasks | exam_swebench.sh 3 random tasks | exam_sandbox.sh Security tests |
| --- | --- | --- |
| Pass: 4/5 For each task: | Pass: 2/3 For each task: | Pass: ALL Tests: |
| 1. dump task 2. run agent | 1. dump task 2. run agent | - import block - builtin block |
| 3. validate | 3. validate 4. container cleanup | - network block - path restrict |

- timeout - memory limit
- MCP protocol
Table VI.1: Summary of exam scripts and tasks. Iteration/token/timeout limits are detailed in Section 6.1.

25

Agent Smith Autonomous reasoning, code generation, and execution

### VI.1 Hard Requirements and Limits

Your implementation must strictly respect the following execution limits. Exceeding any of these limits will result in a failure of the corresponding task.

VI.1.1 MBPP Limits

| Metric Maximum iterations | Limit 10 |
| --- | --- |
| Maximum input tokens Maximum output tokens | 6,000 1,500 |
| Timeout | 120 seconds |

VI.1.2 SWE-bench Limits

**Metric Limit**Maximum iterations 30

Maximum input tokens 300,000 Maximum output tokens 10,000

Timeout 900 seconds

- _•_ Token limits are _cumulative_ across all iterations of a single task (all Thought **→**Code **→** Observation cycles combined).
- **•** Thinking/reasoning tokens (when used by reasoning models) count toward the limitjust like all other tokens.
- **•** If your chosen model’s reasoning tokens make limits tight, consider using a non-reasoning model.
26

Agent Smith Autonomous reasoning, code generation, and execution

- _•_ The timeout is enforced by force-killing your agent’s process (and any process itspawned) with **SIGTERM** then **SIGKILL** if it hasn’t returned in time, not just checked
after the fact. For SWE-bench, make sure your Docker container cleanup can still run in that case (e.g. a signal handler), or complete quickly enough that it usually

isn’t reached.

### VI.2 Pass Criteria

Benchmark Tasks Pass Threshold_MBPP 5 random tasks 4 out of 5_

SWE-bench 3 random tasks 2 out of 3

_No retries are allowed during examination_: a failed task is not re-run. This does notrestrict your own agent’s internal LLM-call retry logic, tracked by **StepMetrics.retries**.

### VI.3 Grading Criteria

To pass the project, you must satisfy _all_ of the following conditions:

- **•** Meet the pass criteria for both MBPP and SWE-bench
- **•** Respect all iteration, token, and timeout limits
- **•** All mandatory tools pass independent tests
- **•** The sandbox passes isolation and security tests
```
Hardcoded API keys in your code are a security failure. All API
keys must be loaded from environment variables or configuration files
(.env). Any API key found in your source code will be flagged during
evaluation.
```

### VI.4 What We Will Test in the Review

- **•** Correctness of mandatory tools
- **•** Correct implementation of the agent reasoning loop
- **•** Sandbox security and isolation guarantees
- **•** Model benchmarking results and token statistics
- **•** Code quality, robustness, and overall architecture
27

Agent Smith Autonomous reasoning, code generation, and execution

```
During the evaluation, you will be asked to make small live
modifications to your agent and re-run it on an MBPP task. This
tests that you understand your own codebase and that the data in
solution.json comes from real execution, not fabricated values. Each
modification should take 2–5 minutes. If you cannot find where to
make a change, it indicates you do not understand your own codebase.
You will be asked to revert all changes after the exercise (e.g., git
checkout).
```

VI.4.1 AI Safety in Evaluation

Building an autonomous code agent raises important safety considerations beyond just sandbox security. During evaluation, we verify that your agent solves tasks through le-

gitimate reasoning and code exploration — not by exploiting shortcuts.

Your agent must **not**:

- **•** Fetch solutions from pull requests, issues, or external sources
- **•** Use memorized patches from its training data without genuine exploration
- **•** Bypass the sandbox security constraints
- **•** Access resources outside the provided task context
The **SolutionOutput** includes **system_prompt**, **llm_output**, **sandbox_input**, and **sandbox_output**fields precisely so that evaluators can trace the agent’s reasoning process. This trans-

parency is a core part of responsible AI development.

Violations will result in a grade of 0.

### VI.5 Evaluation logging structure

Evaluation results are stored in:

```
./evaluations/EVAL_TYPE/YYYY-MM-DD_HH-MM-SS/task_id/task.json, solution.json,
stdout.log, stderr.log
```

28

# Chapter VII

# Readme Requirements

A **README.md** file must be provided at the root of your Git repository. Its purpose isto allow anyone unfamiliar with the project (peers, staff, recruiters, etc.) to quickly

understand what the project is about, how to run it, and where to find more information on the topic.

The **README.md** must include at least:

- **•** _The very first line must be italicized and read:_ This project has been created as partof the 42 curriculum by <login1>[, <login2>[, <login3>[...]]].
- _•_ A “**Description**” section that clearly presents the project, including its goal and abrief overview.
- **•** An “_Instructions_” section containing any relevant information about compilation,installation, and/or execution.
- _•_ A “**Resources**” section listing classic references related to the topic (documen-tation, articles, tutorials, etc.), as well as a description of how AI was used —
specifying for which tasks and which parts of the project.

**➠** _Additional sections may be required depending on the project_ (e.g., usageexamples, feature list, technical choices, etc.).

Any required additions will be explicitly listed below.

Your **README.md** must include:

- **•** System architecture
- **•** Agent loop explanation
- **•** Sandbox design
- **•** Tool implementation details
- **•** Benchmark results and analysis
29

Agent Smith Autonomous reasoning, code generation, and execution

```
Your README must be written in English.
```

30

# Chapter VIII

# Submission

Submit your project in your Git repository. Your repository must contain:

- **•** The internal architecture and directory structure of your submission are left to you.
- **•** Configuration files for sandbox and models
- _•_ README.md
```
Do not include Docker images, large model weights, or generated
outputs.
```

31
