"""Per-snippet execution timeout (§V.2.3).

Docker's own limits apply to the whole long-lived container, not to a single
exec call, so an individual snippet exceeding max_execution_time_seconds
must be cut here without killing the container or losing the namespace.

Threads cannot be force-killed in Python, and a decorator that only measures
elapsed time after the fact cannot interrupt a running infinite loop. This
uses signal.alarm() instead: Python checks for pending signals between
bytecode instructions, so even a pure-Python `while True: pass` gets
interrupted. Unix-only and main-thread-only, both true of runner.py.
"""

import signal
from collections.abc import Generator
from contextlib import contextmanager


class ExecutionTimeout(TimeoutError):
    pass


def _raise_timeout(signum: int, frame: object) -> None:
    raise ExecutionTimeout("Execution exceeded the configured time limit")


@contextmanager
def enforce(seconds: int) -> Generator[None]:
    previous_handler = signal.signal(signal.SIGALRM, _raise_timeout)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def pause() -> int:
    """Cancel the pending alarm, returning the seconds left on it.

    Used around a tool_call round-trip: MCP server actions are not
    subject to the sandbox's own execution timeout, only the sandboxed
    code's own computation is.
    """
    return signal.alarm(0)


def resume(remaining_seconds: int) -> None:
    if remaining_seconds > 0:
        signal.alarm(remaining_seconds)
