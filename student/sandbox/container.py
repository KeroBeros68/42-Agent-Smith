"""Docker container lifecycle manager, one container per sandbox session (decided 2026-08-12).

Uses docker-py. Responsibilities:
- build/pull the right image (team-built minimal image for MBPP, task-provided
  `docker_image` for SWE-bench per §VII.2)
- for SWE-bench, `docker cp` the executor/ package into the container before start
- start the container with --network none, memory limit from SandboxConfig,
  and attach stdio for the JSON Lines protocol (sandbox/executor/protocol.py)
- guarantee teardown in a `finally` (§VII, cleanup at the team's charge),
  without swallowing KeyboardInterrupt/SystemExit (§V.2.2)
"""
