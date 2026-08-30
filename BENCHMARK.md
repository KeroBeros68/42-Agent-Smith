# Model Benchmark Report

> **WIP — no data yet.** All cells are `—` until measured from real runs.
> Benchmark: comparing at least 5 models on the same set of at least 3 SWE-bench tasks.
> Backing `solution.json` files must be present in the repository.

## 1. Setup

- **Models / providers compared:** (free tiers only)
  | Model | Provider |
  |---|---|
  | nvidia/nemotron-3-ultra-550b-a55b:free | OpenRouter |
  | minimax/minimax-m3:free | OpenRouter |
  | poolside/laguna-s-2.1:free | OpenRouter |
  | thinkingmachines/inkling:free | OpenRouter |
  | inclusionai/ling-3.0-flash-fin:free | OpenRouter |
- **Tested on:**
  - `sympy__sympy-14711`
  - `sympy__sympy-13480`
  - `pydata__xarray-4629`

## 2. Results Table

Grid: 5 models × 3 tasks (each model runs every task).

### sympy__sympy-14711

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| nemotron-3-ultra-550b-a55b | — | — | — | — | — |
| minimax-m3 | — | — | — | — | — |
| laguna-s-2.1 | — | — | — | — | — |
| inkling | — | — | — | — | — |
| ling-3.0-flash-fin | — | — | — | — | — |

### sympy__sympy-13480

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| nemotron-3-ultra-550b-a55b | — | — | — | — | — |
| minimax-m3 | — | — | — | — | — |
| laguna-s-2.1 | — | — | — | — | — |
| inkling | — | — | — | — | — |
| ling-3.0-flash-fin | — | — | — | — | — |

### pydata__xarray-4629

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| nemotron-3-ultra-550b-a55b | — | — | — | — | — |
| minimax-m3 | — | — | — | — | — |
| laguna-s-2.1 | — | — | — | — | — |
| inkling | — | — | — | — | — |
| ling-3.0-flash-fin | — | — | — | — | — |

## 3. Provider Reliability

| Model | Avg response time / request | Retries | Availability |
|---|---|---|---|
| nemotron-3-ultra-550b-a55b | — | — | — |
| minimax-m3 | — | — | — |
| laguna-s-2.1 | — | — | — |
| inkling | — | — | — |
| ling-3.0-flash-fin | — | — | — |

## 4. Intermediary Metrics (at least 2)

| Metric | sympy-14711 | sympy-13480 | xarray-4629 |
|---|---|---|---|
| Exploration: step first reads/edits file in final patch | — | — | — |
| Partial progress: step test failures first decrease | — | — | — |
| Submission discipline: steps between "tests pass" and `final_answer` | — | — | — |

## 5. Ablation Study

Planned: system prompt with worked debugging example vs. bare "solve this bug" prompt, same model, same 3 tasks.

Result: —

## 6. Conclusions

To be written once runs are complete and data is in.
