"""Docker container lifecycle manager, one container per sandbox session
    (decided 2026-08-12).

Uses docker-py. Responsibilities:
- build/pull the right image (team-built minimal image for MBPP, task-provided
  `docker_image` for SWE-bench per §VII.2)
- for SWE-bench, `docker cp` the executor/ package into the container
    before start
- start the container with --network none, memory limit from SandboxConfig,
  and attach stdio for the JSON Lines protocol (sandbox/executor/protocol.py)
- guarantee teardown in a `finally` (§VII, cleanup at the team's charge),
  without swallowing KeyboardInterrupt/SystemExit (§V.2.2)
"""

import io
import tarfile
from pathlib import Path

import docker
from docker.models.containers import Container

from sandbox.config import SandboxConfig

EXECUTOR_CONTAINER_PATH = "/sandbox_executor"


def _build_executor_archive() -> bytes:
    executor_dir = Path(__file__).parent / "executor"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        tar.add(executor_dir, arcname=EXECUTOR_CONTAINER_PATH.lstrip("/"))
    buffer.seek(0)
    return buffer.read()


class SandboxContainer:
    def __init__(self, config: SandboxConfig, image: str) -> None:
        self._client = docker.from_env()
        self._config = config
        self._image = image
        self._container: Container | None = None

    def start(self) -> None:
        self._container = self._client.containers.create(
            image=self._image,
            command=["python3", f"{EXECUTOR_CONTAINER_PATH}/runner.py"],
            detach=True,
            network_mode="none",
            mem_limit=f"{self._config.max_memory_mb}m",
            stdin_open=True,
            stdout=True,
            stderr=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
        )
        self._inject_executor()
        self._container.start()

    def _inject_executor(self) -> None:
        archive = _build_executor_archive()
        self._container.put_archive(path="/", data=archive)

    def stop(self) -> None:
        if self._container is not None:
            self._container.stop()
            self._container.remove()
            self._container = None

    def __enter__(self) -> "SandboxContainer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()
