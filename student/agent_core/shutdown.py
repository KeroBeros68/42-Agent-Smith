"""Graceful SIGTERM handling, shared by agent_mbpp and agent_swebench (§V.2.2).

Real risk, not hypothetical: the moulinette's run-agent command sends
SIGTERM then SIGKILL after a 10s grace period on timeout, and
os.killpg only reaches local processes — never the Docker container a
CLI's `with container:` block owns, which would be orphaned without
this.
"""

import signal


class Terminated(SystemExit):
    """Raised from install_sigterm_handler()'s handler so a caller's
    `with container:`/`finally` blocks still unwind cleanly (they run
    for any exception, Exception or BaseException) instead of the
    process dying with zero cleanup. A SystemExit subclass (not plain
    Exception) so `except Exception` never swallows it — matches
    §V.2.2's requirement that SystemExit/KeyboardInterrupt must reach
    the top, not be caught.
    """


def _handle_sigterm(signum: int, frame: object) -> None:
    raise Terminated(143)  # 128 + SIGTERM(15), conventional


def install_sigterm_handler() -> None:
    """Convert SIGTERM into a Terminated exception for this process."""
    signal.signal(signal.SIGTERM, _handle_sigterm)
