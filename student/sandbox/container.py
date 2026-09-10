"""Docker container lifecycle manager, one container per sandbox session
    (decided 2026-08-12).

Uses docker-py. Responsibilities:
- build/pull the right image (team-built minimal image for MBPP, task-provided
  `docker_image` for SWE-bench per §VII.2)
- layer a derived image `FROM` that base with executor/ baked in via `COPY`
  (put_archive/`docker cp` cannot write into a read_only=True container, so
  the executor must be in the image before start, not injected after)
- start the container with --network none, memory limit from SandboxConfig,
  and attach stdio for the JSON Lines protocol (sandbox/executor/protocol.py)
- guarantee teardown in a `finally` (§VII, cleanup at the team's charge),
  without swallowing KeyboardInterrupt/SystemExit (§V.2.2)
"""

import contextlib
import hashlib
import io
import json
import os
import tarfile
from pathlib import Path
from types import TracebackType
from typing import Any, cast

import docker
from docker.errors import DockerException, ImageNotFound
from docker.models.containers import Container

from mcp_server_shared.share import (
    DERIVED_IMAGE_PREFIX,
    OWNER_PID_LABEL,
    SANDBOX_GID,
    SANDBOX_UID,
)
from sandbox.config import SandboxConfig
from sandbox.executor.protocol import (
    ENV_MCP_TOOLS_JSON,
    ENV_SANDBOX_CONFIG_JSON,
)

EXECUTOR_CONTAINER_PATH = "/sandbox_executor"
EXECUTOR_CONTEXT_SUBDIR = "executor"

# Docker multiplexes container output when no TTY is allocated: each frame is
# an 8-byte header (stream type, 3 padding bytes, big-endian payload size)
# followed by the payload itself.
STREAM_STDOUT = 1
FRAME_HEADER_SIZE = 8

# runner.py's watchdog must always respond within max_execution_time_seconds;
# this margin covers network/serialization overhead on top of that bound.
RECEIVE_TIMEOUT_MARGIN_SECONDS = 30

# Writable areas carved out of the read-only root filesystem. A tmpfs is
# RAM-backed and mounted root:root 0755 by default, hence the explicit size
# cap (DoS) and uid/gid (the container runs as the unprivileged `sandbox`
# user). Paths are hardcoded on purpose: deriving them from
# allowed_directories would tmpfs-mount /testbed for SWE-bench and mask the
# task repository behind an empty mount.
#
# `exec`, not just the absence of `noexec`: Docker mounts tmpfs `noexec`
# by default and only drops it when `exec` is explicitly listed — merely
# omitting `noexec` from the options string still produced a `noexec`
# mount in testing (`mount` inside the container showed it regardless).
# Needed because SWE-bench's own eval_script invokes test runners
# directly (e.g. `./tests/runtests.py`, relying on the file's own exec
# bit) inside /workspace — confirmed by testing (`Permission denied`
# without this). Doesn't weaken the restricted-Python-execution boundary
# (runner.py): that code path already blocks subprocess/os.system/
# dangerous imports at the Python level (restrictions.py), so `noexec`
# was defense-in-depth on top of that, not the only barrier — and it
# never applied to MCP tools' own `docker exec` calls (a separate
# security domain, §V.2.5) anyway.
TMPFS_OPTIONS = (
    f"rw,exec,nosuid,nodev,size=4096m,uid={SANDBOX_UID},"
    f"gid={SANDBOX_GID},mode=0700"
)
TMPFS_MOUNTS = {
    "/workspace": TMPFS_OPTIONS,
    "/tmp": TMPFS_OPTIONS,
}


def _recv_exactly(sock: Any, size: int) -> bytes:
    data = b""
    while len(data) < size:
        try:
            chunk = sock.recv(size - len(data))
        except TimeoutError:
            raise TimeoutError(
                "Sandbox container did not respond in time"
            ) from None
        if not chunk:
            raise ConnectionError("Sandbox container closed the connection")
        data += chunk
    return data


def _skip_pycache(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
    if "__pycache__" in tarinfo.name or tarinfo.name.endswith(".pyc"):
        return None
    return tarinfo


def _build_executor_image_context(dockerfile: str) -> io.BytesIO:
    # The Dockerfile itself lives at the context root, alongside but outside
    # the "executor" subdir, so `COPY executor/ ...` below never copies it
    # into the image.
    executor_dir = Path(__file__).parent / "executor"
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        tar.add(
            executor_dir, arcname=EXECUTOR_CONTEXT_SUBDIR, filter=_skip_pycache
        )
        dockerfile_bytes = dockerfile.encode("utf-8")
        info = tarfile.TarInfo("Dockerfile")
        info.size = len(dockerfile_bytes)
        tar.addfile(info, io.BytesIO(dockerfile_bytes))
    buffer.seek(0)
    return buffer


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists, just owned by another user.
        return True
    return True


def _sweep_orphaned_containers(client: docker.DockerClient) -> None:
    """Remove sandbox containers whose owning process is gone.

    `with container:` cleans up on every normal exit, and even on a
    SIGTERM (agent_core/shutdown.py turns it into an exception) — but a
    SIGKILL cannot be caught, so a hard-killed session leaves its
    container running forever and nothing ever reclaims it. Observed for
    real: three orphans accumulated across exam runs, one per run, left
    by a test that deliberately kills the process.

    The owner-pid label is what makes them identifiable, and a dead owner
    is what makes them unambiguously safe to remove. A recycled PID makes
    us skip a container that is in fact orphaned — conservative, and a
    later run will sweep it. Images are deliberately left alone: the
    derived image tag is shared between sessions, so removing it here
    could pull the rug from under a concurrent run.
    """
    for container in client.containers.list(
        all=True, filters={"label": OWNER_PID_LABEL}
    ):
        pid = container.labels.get(OWNER_PID_LABEL, "")
        if not pid.isdigit() or _pid_alive(int(pid)):
            continue
        with contextlib.suppress(DockerException):
            container.remove(force=True)


class SandboxContainer:
    def __init__(
        self,
        config: SandboxConfig,
        image: str,
        build_context: Path | None = None,
        tools: dict[str, list[str]] | None = None,
    ) -> None:
        self._client = docker.from_env()
        self._config = config
        self._image = image
        self._build_context = build_context
        self._tools = tools or {}
        self._runtime_image: str | None = None
        self._container: Container | None = None
        self._socket: Any = None
        self._recv_buffer: bytes = b""
        self._stderr_buffer: bytes = b""

    def _ensure_image(self) -> None:
        if self._build_context is not None:
            self._client.images.build(
                path=str(self._build_context), tag=self._image
            )
        else:
            try:
                self._client.images.get(self._image)
            except ImageNotFound:
                self._client.images.pull(self._image)
        self._runtime_image = self._build_executor_image(self._image)

    def _build_executor_image(self, base_image: str) -> str:
        # A container created with read_only=True refuses put_archive/docker
        # cp ("container rootfs is marked read-only"), including before
        # start(). Baking the executor in at build time sidesteps that
        # entirely, and works uniformly whether base_image was just built
        # (MBPP) or pulled as-is (task-provided SWE-bench image) — the build
        # is a plain `docker build`, unrelated to any runtime read-only
        # constraint. --chown pins ownership to the sandbox user (uid 1000)
        # instead of the host uid tar.add() used to preserve.
        tag = DERIVED_IMAGE_PREFIX + hashlib.sha256(
            base_image.encode("utf-8")
        ).hexdigest()[:16]
        dockerfile = (
            f"FROM {base_image}\n"
            f"COPY --chown=1000:1000 {EXECUTOR_CONTEXT_SUBDIR}/ "
            f"{EXECUTOR_CONTAINER_PATH}\n"
        )
        context = _build_executor_image_context(dockerfile)
        self._client.images.build(
            fileobj=context, custom_context=True, tag=tag
        )
        return tag

    def start(self) -> None:
        _sweep_orphaned_containers(self._client)
        self._ensure_image()
        assert self._runtime_image is not None
        container = self._client.containers.create(
            image=self._runtime_image,
            command=["python3", f"{EXECUTOR_CONTAINER_PATH}/runner.py"],
            detach=True,
            network_mode="none",
            mem_limit=f"{self._config.max_memory_mb}m",
            stdin_open=True,
            tty=False,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            read_only=True,
            tmpfs=TMPFS_MOUNTS,
            pids_limit=self._config.pids_limit,
            environment={
                ENV_SANDBOX_CONFIG_JSON: self._config.model_dump_json(),
                ENV_MCP_TOOLS_JSON: json.dumps(self._tools),
            },
            # Identifies the containers belonging to this process, which
            # is what lets _sweep_orphaned_containers() above reclaim
            # those left behind by a hard-killed session. Informational
            # only — no other process reads it.
            labels={OWNER_PID_LABEL: str(os.getpid())},
        )
        container.start()
        self._container = container
        self._socket = cast(
            Any,
            container.attach_socket(
                params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
            ),
        )
        self._socket._sock.settimeout(
            self._config.max_execution_time_seconds
            + RECEIVE_TIMEOUT_MARGIN_SECONDS
        )

    def send(self, message: dict[str, Any]) -> None:
        data = (json.dumps(message) + "\n").encode("utf-8")
        self._socket._sock.sendall(data)

    def _read_frame(self) -> tuple[int, bytes]:
        header = _recv_exactly(self._socket._sock, FRAME_HEADER_SIZE)
        payload_size = int.from_bytes(header[4:FRAME_HEADER_SIZE], "big")
        return header[0], _recv_exactly(self._socket._sock, payload_size)

    @property
    def stderr(self) -> str:
        return self._stderr_buffer.decode("utf-8", errors="replace")

    def receive(self) -> dict[str, Any]:
        while b"\n" not in self._recv_buffer:
            try:
                stream_type, payload = self._read_frame()
            except ConnectionError as e:
                if self._stderr_buffer:
                    raise ConnectionError(
                        f"{e}\nContainer stderr:\n{self.stderr}"
                    ) from None
                raise
            if stream_type == STREAM_STDOUT:
                self._recv_buffer += payload
            else:
                self._stderr_buffer += payload
        line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
        return cast(dict[str, Any], json.loads(line.decode("utf-8")))

    def stop(self) -> None:
        if self._container is None:
            return
        try:
            self._container.stop()
        finally:
            try:
                if self._socket is not None:
                    self._socket.close()
            finally:
                try:
                    self._container.remove(force=True)
                finally:
                    self._container = None
                    if self._runtime_image is not None:
                        try:
                            self._client.images.remove(
                                self._runtime_image, force=True
                            )
                        finally:
                            self._runtime_image = None

    def __enter__(self) -> "SandboxContainer":
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
