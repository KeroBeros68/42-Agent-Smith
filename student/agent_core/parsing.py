"""Extract LLM-generated Python code from a model response (§V.1.2).

Primary format only for now: fenced ```python ... ``` blocks. The other
formats listed in the subject (XML tool calls, JSON/Hermes tool calls,
ReAct) are deferred until this path is proven end-to-end.
"""

import re

_CODE_BLOCK_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)


def extract_code(llm_output: str) -> str | None:
    """Return the Python code found in llm_output, or None if none was found.

    None is the explicit "no valid code block" signal (§V.1) — the caller
    (loop.py) decides what feedback to give the LLM, this function only
    reports absence honestly instead of guessing.
    """
    match = _CODE_BLOCK_RE.search(llm_output)
    if match is None:
        return None
    return match.group(1).strip()
