"""Extract LLM-generated Python code from a model response (§V.1.2).

Formats (a), (b), (c), and (d) of the subject, plus a DeepSeek-specific
DSML "python block" dialect and a Liquid-specific "tool_call_start" dialect
found empirically (see extract_code()).
"""

import ast
import json
import re

from agent_core.manual import JsonSchemaType

_CODE_BLOCK_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
_UNCLOSED_CODE_BLOCK_RE = re.compile(r"```python\s*\n(.*)", re.DOTALL)

_UNCLOSED_FENCE_WARNING = (
    "Note: your ```python code block was not closed with a closing ``` "
    "fence. Everything after the opening ```python marker was "
    "interpreted as code — always close your code blocks."
)

_DSML_PYTHON_RE = re.compile(
    r'<[^>]*\bpython\b[^>]*>(.*?)</[^>]+>',
    re.DOTALL,
)
_LIQUID_TOOL_CALL_RE = re.compile(
    r'<\|tool_call_start\|>\s*(.*?)\s*<\|tool_call_end\|>',
    re.DOTALL,
)
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


def extract_code(
    llm_output: str,
    tool_param_types: dict[str, dict[str, str]] | None = None,
) -> tuple[str | None, str | None]:
    """Return (code, warning) extracted from llm_output.

    tool_param_types (optional, {tool_name: {param_name: json_type}} from
    manual.extract_param_types()) lets format (b)'s XML parameter values
    be typed by the tool's real declared JSON Schema type instead of
    guessed from the raw string's shape — see _python_literal(). None
    falls back to that shape-based guess entirely (e.g. callers that
    don't have a tool list handy).

    `code` is None if no format matched at all — the explicit "no valid
    code block was found" signal (§V.1); the caller (loop.py) decides
    what feedback to give the LLM, this function only reports absence
    honestly instead of guessing.

    `warning` is set when a block was malformed but interpreted anyway
    (§V.1's second mandatory feedback case: "explain how") — e.g. a
    ```python fence opened but never closed — None otherwise.

    Tries the primary format (a) first (fenced ```python block), then
    its malformed/unclosed variant, then a DeepSeek-specific native
    "python block" tag (own dialect, distinct from — and found later
    than — its (b) invoke/parameter dialect below), then a
    Liquid-specific `<|tool_call_start|>[...]<|tool_call_end|>` dialect,
    then falls back in order to formats (b) XML tool calls, (c)
    JSON/Hermes tool calls, (d) ReAct — some models default to their own
    trained tool-calling syntax instead of the fenced-block pattern
    demonstrated in the system prompt's worked example (found
    empirically for format (b), then the DSML-python variant with
    DeepSeek, then this Liquid variant with liquid/lfm-2.5-2.6b:free).
    """
    match = _CODE_BLOCK_RE.search(llm_output)
    if match is not None:
        return match.group(1).strip(), None

    code = _extract_unclosed_code_block(llm_output)
    if code is not None:
        return code, _UNCLOSED_FENCE_WARNING

    match = _DSML_PYTHON_RE.search(llm_output)
    if match is not None:
        return match.group(1).strip(), None

    code = _extract_liquid_tool_calls(llm_output)
    if code is not None:
        return code, None

    code = _extract_xml_tool_calls(llm_output, tool_param_types)
    if code is not None:
        return code, None
    code = _extract_json_tool_calls(llm_output)
    if code is not None:
        return code, None
    code = _extract_react_tool_calls(llm_output)
    if code is not None:
        return code, None
    return None, None


def _extract_unclosed_code_block(llm_output: str) -> str | None:
    """Best-effort recovery for a ```python fence missing its closing ```.

    Interprets everything after the opening marker as code — only
    reached when _CODE_BLOCK_RE already failed to match, which means no
    closing ``` exists anywhere after "```python\\n" in the string.
    """
    match = _UNCLOSED_CODE_BLOCK_RE.search(llm_output)
    if match is None:
        return None
    body = match.group(1).strip()
    return body if body else None


def _extract_liquid_tool_calls(llm_output: str) -> str | None:
    """Convert Liquid's own `<|tool_call_start|>[call(...)]<|tool_call_end|>`
    dialect (found empirically with liquid/lfm-2.5-2.6b:free) to
    equivalent Python code. Unlike formats (b)/(c)/(d), the content is
    already valid Python call syntax (a list of calls, or a bare call),
    so this parses it with ast instead of a bespoke regex/JSON grammar —
    ast.unparse()
    regenerates each call's exact source, one print(call) per call, in order.
    """
    match = _LIQUID_TOOL_CALL_RE.search(llm_output)
    if match is None:
        return None
    try:
        tree = ast.parse(match.group(1), mode="eval")
    except SyntaxError:
        return None
    calls = tree.body.elts if isinstance(tree.body, ast.List) else [tree.body]
    lines = []
    for call in calls:
        if not isinstance(call, ast.Call):
            continue
        lines.append(f"print({ast.unparse(call)})")
    return "\n".join(lines) if lines else None


def _python_literal(value: str, json_type: str | None = None) -> str:
    """Render a captured XML parameter value as a Python literal.

    Uses the tool's declared JSON Schema type when known — correct by
    construction, unlike guessing from the value's shape: a *string*
    parameter whose value merely looks numeric (e.g. code="123") would
    otherwise be rendered as a bare int/float literal instead of a
    quoted string. Falls back to the previous shape-based heuristic only
    when no schema entry exists for this tool/parameter.
    """
    if json_type == JsonSchemaType.STRING:
        return repr(value)
    if json_type == JsonSchemaType.INTEGER:
        try:
            return str(int(value.strip()))
        except ValueError:
            return repr(value)
    if json_type == JsonSchemaType.NUMBER:
        try:
            return str(float(value.strip()))
        except ValueError:
            return repr(value)
    if json_type == JsonSchemaType.BOOLEAN:
        stripped_bool = value.strip().lower()
        if stripped_bool in ("true", "false"):
            return stripped_bool.capitalize()
        return repr(value)
    if json_type in (JsonSchemaType.ARRAY, JsonSchemaType.OBJECT):
        try:
            return repr(ast.literal_eval(value))
        except (ValueError, SyntaxError):
            return repr(value)

    stripped = value.strip()
    if re.fullmatch(r"-?\d+", stripped):
        return stripped
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        return stripped
    if stripped in ("true", "false"):
        return stripped.capitalize()
    return repr(value)


def _extract_xml_tool_calls(
    llm_output: str,
    tool_param_types: dict[str, dict[str, str]] | None = None,
) -> str | None:
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

    tool_param_types (see extract_code()) types each parameter value by
    the tool's real declared schema instead of _python_literal()'s
    shape-based guess.
    """
    invokes = _TOOL_CALL_RE.findall(llm_output)
    if not invokes:
        return None

    tool_param_types = tool_param_types or {}
    lines = []
    for tool_name, body in invokes:
        params = _PARAMETER_RE.findall(body)
        param_types = tool_param_types.get(tool_name, {})
        args = ", ".join(
            f"{name}={_python_literal(value, param_types.get(name))}"
            for name, value in params
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
