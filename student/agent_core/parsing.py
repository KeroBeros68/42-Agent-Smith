"""Extract LLM-generated Python code from a model response (§V.1.2).

Formats (a), (b), (c), and (d) of the subject.
"""

import json
import re

_CODE_BLOCK_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)

_TOOL_CALL_RE = re.compile(
    r'<[^>]*\binvoke\b[^>]*\bname="([^"]+)"[^>]*>(.*?)</[^>]*\binvoke\b[^>]*>',
    re.DOTALL,
)
_PARAMETER_RE = re.compile(
    r'<[^>]*\bparameter\b[^>]*\bname="([^"]+)"[^>]*>'
    r'(.*?)</[^>]*\bparameter\b[^>]*>',
    re.DOTALL,
)
_JSON_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(.*?)\s*</tool_call>", re.DOTALL
)
_REACT_ACTION_RE = re.compile(
    r"Action:\s*(\S+)\s*\n\s*Action Input:\s*", re.IGNORECASE
)


def extract_code(llm_output: str) -> str | None:
    """Return the Python code found in llm_output, or None if none was found.

    Tries the primary format (a) first (fenced ```python block), then
    falls back in order to formats (b) XML tool calls, (c) JSON/Hermes
    tool calls, (d) ReAct — some models default to their own trained
    tool-calling syntax instead of the fenced-block pattern demonstrated
    in the system prompt's worked example (found empirically for format
    (b) with DeepSeek). None is the explicit "no valid code block" signal
    (§V.1) if no format matches — the caller (loop.py) decides what
    feedback to give the LLM, this function only reports absence
    honestly instead of guessing.
    """
    match = _CODE_BLOCK_RE.search(llm_output)
    if match is not None:
        return match.group(1).strip()
    code = _extract_xml_tool_calls(llm_output)
    if code is not None:
        return code
    code = _extract_json_tool_calls(llm_output)
    if code is not None:
        return code
    return _extract_react_tool_calls(llm_output)


def _python_literal(value: str) -> str:
    """Render a captured XML parameter value as a Python literal."""
    stripped = value.strip()
    if re.fullmatch(r"-?\d+", stripped):
        return stripped
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        return stripped
    if stripped in ("true", "false"):
        return stripped.capitalize()
    return repr(value)


def _extract_xml_tool_calls(llm_output: str) -> str | None:
    """Convert XML-style <invoke>/<parameter> tool calls (§V.1, format (b))
    to equivalent Python code — one print(tool(...)) call per <invoke>,
    in order. print() rather than the subject's own `result = ...`
    example: runner.py compiles in "exec" mode (no REPL auto-echo), so a
    bare assignment would produce an empty Observation — found the hard
    way with manual.py's first example (see AUDIT_AGENT_CORE.md). Tag
    names are matched loosely (only requiring "invoke"/"parameter" as a
    substring) since providers prefix them differently — e.g. DeepSeek's
    own <｜DSML｜invoke>/<｜DSML｜parameter>, not just the Anthropic-style
    <invoke> the subject's example shows.
    """
    invokes = _TOOL_CALL_RE.findall(llm_output)
    if not invokes:
        return None

    lines = []
    for tool_name, body in invokes:
        params = _PARAMETER_RE.findall(body)
        args = ", ".join(
            f"{name}={_python_literal(value)}" for name, value in params
        )
        lines.append(f"print({tool_name}({args}))")
    return "\n".join(lines)


def _format_tool_call(name: str, arguments: object) -> str | None:
    """Render a (tool name, JSON-decoded arguments) pair as print(tool(...)).

    Shared by formats (c) and (d): both carry a JSON object of arguments,
    already correctly typed by json.loads — unlike format (b)'s raw XML
    text, no literal-type inference is needed, repr() is enough.
    """
    if not isinstance(arguments, dict):
        return None
    args = ", ".join(f"{key}={value!r}" for key, value in arguments.items())
    return f"print({name}({args}))"


def _extract_json_tool_calls(llm_output: str) -> str | None:
    """Convert JSON/Hermes-style <tool_call>{...}</tool_call> blocks
    (§V.1, format (c)) to equivalent Python code.
    """
    bodies = _JSON_TOOL_CALL_RE.findall(llm_output)
    if not bodies:
        return None

    lines = []
    for body in bodies:
        try:
            call = json.loads(body)
        except json.JSONDecodeError:
            continue
        name = call.get("name")
        if not name:
            continue
        line = _format_tool_call(name, call.get("arguments", {}))
        if line is not None:
            lines.append(line)
    return "\n".join(lines) if lines else None


def _extract_react_tool_calls(llm_output: str) -> str | None:
    """Convert ReAct-style `Action: tool\\nAction Input: {...}` pairs
    (§V.1, format (d)) to equivalent Python code. Uses
    json.JSONDecoder.raw_decode to find where the JSON object ends,
    instead of a regex — a brace-counting regex would mishandle nested
    objects/arrays in the arguments.
    """
    decoder = json.JSONDecoder()
    lines = []
    for match in _REACT_ACTION_RE.finditer(llm_output):
        name = match.group(1)
        brace_pos = llm_output.find("{", match.end())
        if brace_pos == -1:
            continue
        try:
            arguments, _ = decoder.raw_decode(llm_output, brace_pos)
        except json.JSONDecodeError:
            continue
        line = _format_tool_call(name, arguments)
        if line is not None:
            lines.append(line)
    return "\n".join(lines) if lines else None
