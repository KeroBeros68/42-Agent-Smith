# Model Benchmark Report

![SWE-bench banner](https://www.swebench.com/SWE-bench/assets/figures/swellama_banner_nobg.svg)

## 1. Models and tests

- **Models / providers compared:** (free tiers only)
  | Model | Provider |
  |---|---|
  | huggingface/Qwen/Qwen3.8-27B | Huggingface |
  | openrouter/nvidia/nemotron-3-ultra-550b-a55b:free | OpenRouter |
  | openrouter/minimax/minimax-m3:free | OpenRouter |
  | openrouter/inclusionai/ling-3.0-flash-fin:free | OpenRouter |
  | openrouter/minimax/minimax-m2.7:free | OpenRouter |
- **Tested on:**
  - `sympy__sympy-14711`
  - `django__django-15104`
  - `pydata__xarray-4629`

**These are different tasks from different codebases. Using a model on various codebases ensure that it's performing on a codebase it was well trained on.**

## 2. Results Table

Grid: 5 models × 3 tasks (each model runs every task).

### sympy__sympy-14711

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| qwen3.8-27b | True | 18 | 188 742 | 6650 | 856 |
| nemotron-3-ultra-550b-a55b | False | 16 | 305 892 | 2894 | 568 |
| minimax-m3 | False | 30 | 272 561 | 1715 | 163 |
| ling-3.0-flash-fin | False | 30 | 69 584 | 994 | 99 |
| minimax-m2.7 | True | 15 | 45 396 | 2430 | 105 |

### django__django-15104

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| qwen3.8-27b | True | 8 | 42 971 | 1079 | 115 |
| nemotron-3-ultra-550b-a55b | True | 8 | 97 638 | 12 906 | 805 |
| minimax-m3 | True | 6 | 33 816 | 373 | 101 |
| ling-3.0-flash-fin | False | 30 | 95 476 | 947 | 93 |
| minimax-m2.7 | True | 9 | 75 560 | 4345 | 78 |

### pydata__xarray-4629

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| qwen3.8-27b | True | 5 | 35 440 | 662 | 365 |
| nemotron-3-ultra-550b-a55b | True | 6 | 40 425 | 1160 | 508 |
| minimax-m3 | True | 9 | 46 609 | 684 | 340 |
| ling-3.0-flash-fin | False | 30 | 88 872 | 921 | 269 |
| minimax-m2.7 | True | 7 | 48 942 | 1119 | 153 |

## 3. Provider Reliability

| Model | Avg response time / request | Retries | Availability |
|---|---|---|---|
| qwen3.8-27b | 29.6 s | 0 | 100% |
| nemotron-3-ultra-550b-a55b | 44.7 s | 0 | 100% |
| minimax-m3 | 2.3 s | 0 | 100% |
| ling-3.0-flash-fin | 1.1 s | 0 | 100% |
| minimax-m2.7 | 4.1 s | 0 | 100% |

> Note : We chose providers/models that are specially reliable. The only reiability problems that can be encountered during tests are rate-limit API errors. In this case, the test is cancelled and the error is reported in the results.

## 4. Intermediary Metrics (at least 2)

Two process metrics, measured per model from the `solution.json` step traces. Only runs that produced a final patch (exploration) or submitted via `final_answer` (discipline) can be measured; failed runs are marked « — ».

### Exploration efficiency

Step at which the model first reads/edits the file that ends up in its final patch (first `read_file`/`edit_file` on that file).

| Model | sympy-14711 | django-15104 | xarray-4629 |
|---|---|---|---|
| qwen3.8-27b | 2 | 3 | 1 |
| nemotron-3-ultra-550b-a55b | — | 2 | 1 |
| minimax-m3 | — | 2 | 2 |
| ling-3.0-flash-fin | — | — | — |
| minimax-m2.7 | 7 | 1 | 2 |

### Submission discipline

Agent iterations between the step where the tests first pass (`run_tests()` showing no failure) and `final_answer` — 0 is ideal. Failed runs that never submit are « — ».

| Model | sympy-14711 | django-15104 | xarray-4629 |
|---|---|---|---|
| qwen3.8-27b | 1 | 1 | 1 |
| nemotron-3-ultra-550b-a55b | — | 1 | 1 |
| minimax-m3 | — | 1 | 1 |
| ling-3.0-flash-fin | — | — | — |
| minimax-m2.7 | 1 | 2 | 1 |

The « partial progress » metric (step at which test failures first decrease) was dropped: every run calls `run_tests()` only once, at the end, with no initial failure baseline — so it is not measurable from these traces.

## 5. Ablation Study

System prompt with worked debugging example vs. bare "solve this bug" prompt, same model, same 3 tasks.

### Before a bare "solve this bug" prompt

The model navigate through the codebase, reads files, etc. It changes code, executes MCP tools calls, build python code blocs, etc.

### After a bare "solve this bug" prompt

The model doesn't even know it can call tools. No code bloc is writte, nor interpreted. The model fails to complete a single step.

Result: Without proper instructions, the AI model has more difficulties to understand what is its purpose, what are the tools available, etc.

## 6. Conclusions

Aggregated over the 3 tasks (every model ran every task). « Avg » means per task. Wall-clock times in seconds.

| Model | Tasks passed | Avg iterations | Avg input tokens | Avg output tokens | Avg wall-clock time | Avg time / iteration |
|---|---|---|---|---|---|---|
| qwen3.8-27b | 3 / 3 | 10.3 | 89 051 | 2 797 | 445 s | 43.1 s |
| nemotron-3-ultra-550b-a55b | 2 / 3 | 10.0 | 147 985 | 5 653 | 627 s | 62.7 s |
| minimax-m3 | 2 / 3 | 15.0 | 117 662 | 924 | 201 s | 13.4 s |
| ling-3.0-flash-fin | 0 / 3 | 30.0 | 84 644 | 954 | 154 s | 5.1 s |
| minimax-m2.7 | 3 / 3 | 10.3 | 56 633 | 2 631 | 112 s | 10.8 s |

Takeaways:

- Only **qwen3.8-27b** and **minimax-m2.7** solve all 3 tasks. nemotron and minimax-m3 solve 2, ling-3.0-flash-fin solves none — it always exhausts the 30-iteration cap.
- **minimax-m2.7 is the best overall**: perfect score with the shortest average wall-clock time (112 s) and the lowest token consumption (56.6k input / 2.6k output per task).
- qwen3.8-27b is equally accurate but roughly 4× slower (445 s/task) and much more input-token-hungry on sympy (188.7k vs 45.4k for m2.7).
- nemotron-3-ultra-550b-a55b is the most expensive runner: the most input (148k) and output (5.7k) tokens per task and the highest wall-clock time, yet still fails sympy.
- ling-3.0-flash-fin is cheap and fast per iteration but never converges — it reaches the iteration cap on every run.

> **Prefered model :**  **minimax-m2.7** (accuracy + speed + cost). **Qwen3.8-27b** is also very good in its outputs, but the fact that its only free provider, HuggingFace, is very restrictive in the usage, makes us prefer to use **minimax-m2.7** as the best free model for these tasks.
