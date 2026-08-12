"""Self-contained, stdlib-only package copied as-is into the sandbox container.

Must not depend on anything outside this folder (no pydantic, no docker-py):
the same executor/ has to run unmodified inside a team-built MBPP image and
inside an arbitrary task-provided SWE-bench image.
"""
