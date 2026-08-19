"""SandboxConfig Pydantic model (§V.2.4).

Fields: authorized_imports, allowed_directories, max_execution_time_seconds,
max_memory_mb, pids_limit. For MBPP, allowed_directories resolves to
/workspace inside the container (no host bind mount, decided 2026-08-12).
"""

from pydantic import BaseModel, Field

AUTHORIZED_IMPORTS = [
    "math",
    "math.*",
    "random",
    "itertools",
    "collections",
    "collections.*",
    "functools",
    "operator",
    "heapq",
    "bisect",
    "string",
    "re",
    "datetime",
    "datetime.*",
    "time",
    "json",
    "json.*",
    "typing",
    "typing.*",
    "copy",
    "array",
    "cmath",
]

ALLOWED_DIRECTORIES = [
    "/workspace",
    "/testbed",
]  # no host bind mount, decided 2026-08-12

MAX_EXECUTION_TIME_SECONDS = 10
MAX_MEMORY_MB = 256
PIDS_LIMIT = 64


class SandboxConfig(BaseModel):
    authorized_imports: list[str] = Field(
        default=AUTHORIZED_IMPORTS,
        min_length=1,
        description=(
            "Allowlist of Python modules the sandboxed code is "
            "permitted to import; everything else is blocked."
        ),
    )
    allowed_directories: list[str] = Field(
        default=ALLOWED_DIRECTORIES,
        min_length=1,
        description=(
            "Filesystem paths the sandboxed code may access, "
            "as seen by the sandbox process itself."
        ),
    )
    max_execution_time_seconds: int = Field(
        default=MAX_EXECUTION_TIME_SECONDS,
        gt=0,
        description=(
            "Wall-clock timeout in seconds after which a "
            "running snippet is terminated."
        ),
    )
    max_memory_mb: int = Field(
        default=MAX_MEMORY_MB,
        gt=0,
        description=(
            "Maximum RAM in megabytes the sandboxed code may "
            "use before being terminated."
        ),
    )
    pids_limit: int = Field(
        default=PIDS_LIMIT,
        gt=0,
        description=(
            "Maximum number of processes/threads the sandboxed "
            "code may spawn, to prevent fork bombs."
        ),
    )
