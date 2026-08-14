"""Pydantic data models for the Agent Smith evaluation contract.

These mirror the student-facing models defined by the moulinette
(``moulinette/models_public.py``) and the subject (§V.2–V.4):

- Task inputs, provided by the moulinette: ``MBPPTaskInput``,
  ``SWEBenchTaskInput``
- Agent output, written to ``solution.json``: ``StepMetrics``,
  ``SolutionOutput``

``SandboxConfig`` lives in ``student.sandbox.config`` (it configures the
sandbox itself rather than the evaluation contract).
"""

from student.data_models.mbpp_task import MBPPTaskInput
from student.data_models.solution import SolutionOutput
from student.data_models.step_metrics import StepMetrics
from student.data_models.swebench_task import SWEBenchTaskInput

__all__ = [
    "MBPPTaskInput",
    "SWEBenchTaskInput",
    "SolutionOutput",
    "StepMetrics",
]
