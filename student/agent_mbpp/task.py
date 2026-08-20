"""Input for an MBPP task, as provided by the moulinette (§V.3).

Mirrors ``moulinette.models_public.MBPPTaskInput`` so the agent and the
evaluation contract share the same schema.
"""

from pydantic import Field

from agent_core.schemas import TaskInput


class MBPPTaskInput(TaskInput):
    """Input for an MBPP task."""

    task_id: int = Field(..., description="MBPP task identifier (integer)")
    task_definition: str = Field(
        ...,
        description=(
            "Natural language description of the function to implement"
        ),
    )
    function_definition: str = Field(
        ...,
        description="Function signature (e.g., 'def solve(nums):')",
    )
    test_imports: list[str] = Field(
        default_factory=list,
        description="Import statements needed to run the public tests",
    )
    test_list: list[str] = Field(
        default_factory=list,
        description="Public test assertions the solution must pass",
    )
