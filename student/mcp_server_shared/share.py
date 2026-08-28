"""
This file contains common variables and fonctions shared
between all MCP Servers.
"""


# Some evaluation scripts can take some times to run
MAX_OUTPUT_CHARS = 50_000


def truncate_output(text: str) -> str:
    # Head-only truncation lost the verdict on a real run_tests() output
    # (1.86M chars, the "Start Test Output" marker sat at char 1,861,195
    # — past any head-only cutoff) — noisy diagnostics (git diff without
    # core.fileMode=false, pip install) fill the head, the actual result
    # is at the tail. Keeping both halves covers each tool's needs:
    # search/list results (useful from the start) and run_tests/
    # run_command output (verdict at the end).
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    half = MAX_OUTPUT_CHARS // 2
    omitted = len(text) - MAX_OUTPUT_CHARS
    return (
        f'{text[:half]}\n'
        f'(... {omitted} characters omitted ...)\n'
        f'{text[-half:]}'
    )
