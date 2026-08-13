"""Interactive REPL mode (§V.2.1, no task provided).

Reads input, sends it to the running container as an `exec` message via
container.py, prints the result/error, exits cleanly on `exit` or EOF
(Ctrl+D). Same restrictions as a normal task run (§V.2.3).
"""

from sandbox.container import SandboxContainer


def run(container: SandboxContainer) -> None:
    while True:
        try:
            line = input(">>> ")
        except EOFError:
            break

        if line.strip() == "exit":
            break

        container.send({"type": "exec", "code": line})
        response = container.receive()
        print(response)
