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
import json
import tarfile
from pathlib import Path
from typing import Any

import docker
from docker.errors import ImageNotFound
from docker.models.containers import Container

from sandbox.config import SandboxConfig

EXECUTOR_CONTAINER_PATH = "/sandbox_executor"

# Docker multiplexes container output when no TTY is allocated: each frame is
# an 8-byte header (stream type, 3 padding bytes, big-endian payload size)
# followed by the payload itself.
STREAM_STDOUT = 1
FRAME_HEADER_SIZE = 8


def _recv_exactly(sock: Any, size: int) -> bytes:
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Sandbox container closed the connection")
        data += chunk
    return data


def _build_executor_archive() -> bytes:
    executor_dir = Path(__file__).parent / "executor"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        tar.add(executor_dir, arcname=EXECUTOR_CONTAINER_PATH.lstrip("/"))
    buffer.seek(0)
    return buffer.read()


class SandboxContainer:
    def __init__(
        self,
        config: SandboxConfig,
        image: str,
        build_context: Path | None = None,
    ) -> None:
        self._client = docker.from_env()
        self._config = config
        self._image = image
        self._build_context = build_context
        self._container: Container | None = None
        self._socket: Any = None
        self._recv_buffer: bytes = b""
        self._stderr_buffer: bytes = b""

    def _ensure_image(self) -> None:
        if self._build_context is not None:
            self._client.images.build(
                path=str(self._build_context), tag=self._image
            )
            return
        try:
            self._client.images.get(self._image)
        except ImageNotFound:
            self._client.images.pull(self._image)

    def start(self) -> None:
        self._ensure_image()
        container = self._client.containers.create(
            image=self._image,
            command=["python3", f"{EXECUTOR_CONTAINER_PATH}/runner.py"],
            detach=True,
            network_mode="none",
            mem_limit=f"{self._config.max_memory_mb}m",
            stdin_open=True,
            tty=False,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
        )
        self._inject_executor(container)
        container.start()
        self._container = container
        self._socket = container.attach_socket(
            params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
        )

    def _inject_executor(self, container: Container) -> None:
        archive = _build_executor_archive()
        container.put_archive(path="/", data=archive)

    def send(self, message: dict[str, Any]) -> None:
        data = (json.dumps(message) + "\n").encode("utf-8")
        self._socket._sock.sendall(data)

    def _read_frame(self) -> tuple[int, bytes]:
        header = _recv_exactly(self._socket._sock, FRAME_HEADER_SIZE)
        payload_size = int.from_bytes(header[4:FRAME_HEADER_SIZE], "big")
        return header[0], _recv_exactly(self._socket._sock, payload_size)

    def receive(self) -> dict[str, Any]:
        while b"\n" not in self._recv_buffer:
            stream_type, payload = self._read_frame()
            if stream_type == STREAM_STDOUT:
                self._recv_buffer += payload
            else:
                self._stderr_buffer += payload
        line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))

    def stop(self) -> None:
        if self._container is not None:
            self._container.stop()
            self._socket.close()
            self._container.remove()
            self._container = None

    def __enter__(self) -> "SandboxContainer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.stop()
