"""Interactive REPL mode (§V.2.1, no task provided).

Reads input, sends it to the running container as an `exec` message via
container.py, prints the result/error, exits cleanly on `exit` or EOF
(Ctrl+D). Same restrictions as a normal task run (§V.2.3).
"""

import codeop

from sandbox.container import SandboxContainer

PRIMARY_PROMPT = ">>> "
CONTINUATION_PROMPT = "... "


def _read_block() -> str | None:
    lines: list[str] = []
    prompt = PRIMARY_PROMPT
    while True:
        try:
            line = input(prompt)
        except EOFError:
            return None
        except KeyboardInterrupt:
            print()
            lines = []
            prompt = PRIMARY_PROMPT
            continue

        lines.append(line)
        source = "\n".join(lines)
        try:
            code = codeop.compile_command(source, "<sandbox>", "single")
        except (SyntaxError, OverflowError, ValueError):
            return source
        if code is not None:
            return source
        prompt = CONTINUATION_PROMPT


def run(container: SandboxContainer) -> None:
    while True:
        source = _read_block()
        if source is None:
            break
        if source.strip() == "exit":
            break
        if not source.strip():
            continue

        try:
            container.send({"type": "exec", "code": source})
            response = container.receive()
            print(response)
        except (ConnectionError, TimeoutError):
            print("Connection to container lost.")
            break
