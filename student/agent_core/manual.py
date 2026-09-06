"""Generate the sandbox manual fed to the LLM system prompt (§V.2.6).

Dynamically built from the connected MCP server's tool schemas (name,
description, parameter types) — when a different server is connected,
this reflects that server's tools automatically, no benchmark-specific
code here. Scope: only "the MCP tools doc" (§V.2.6) — the surrounding
Thought/Code/Observation instructions and worked examples (§V.1 point 6)
are a separate, larger system prompt assembled elsewhere.
"""

from typing import Any

_EXAMPLE_VALUES: dict[str, str] = {
    "string": '"..."',
    "integer": "0",
    "number": "0",
    "boolean": "True",
    "array": "[]",
    "object": "{}",
}


def build_manual(tools: list[Any]) -> str:
    """Return a text manual documenting each MCP tool, one entry per tool.

    Takes an already-fetched tool list rather than an MCPBridge — avoids a
    second list_tools() round-trip on top of the one session.build_container()
    already makes; the caller is responsible for fetching once and passing
    the same list here.
    """
    if not tools:
        return "No tools are available in this sandbox."
    return "\n\n".join(_describe_tool(tool) for tool in tools)


def extract_param_types(tools: list[Any]) -> dict[str, dict[str, str]]:
    """Return {tool_name: {param_name: json_schema_type}}, derived from the
    same tool.inputSchema used by build_manual() — lets parsing.py's XML
    format (b) type parameters by the tool's real declared schema instead
    of guessing from the raw string's shape (a plain heuristic wrongly
    turns a string parameter whose value merely looks numeric into a bare
    int/float literal).
    """
    return {
        tool.name: {
            name: json_type
            for name, schema in (tool.inputSchema or {}).get(
                "properties", {}
            ).items()
            if (json_type := _resolve_json_type(schema)) is not None
        }
        for tool in tools
    }


def _resolve_json_type(schema: dict[str, Any]) -> str | None:
    """Return the JSON Schema type name for one parameter's schema, or
    None if unresolvable. Resolves `anyOf` unions — how FastMCP renders
    an `X | None` parameter (confirmed empirically: no top-level "type"
    key, an "anyOf" with the real type plus {"type": "null"} instead) —
    by taking the first non-null branch.
    """
    if "type" in schema:
        type_value = schema["type"]
        return type_value if isinstance(type_value, str) else None
    for branch in schema.get("anyOf", []):
        if branch.get("type") != "null":
            branch_type = branch.get("type")
            return branch_type if isinstance(branch_type, str) else None
    return None


def _describe_tool(tool: Any) -> str:
    properties = (tool.inputSchema or {}).get("properties", {})
    params = ", ".join(
        f"{name}: {schema.get('type', 'Any')}"
        for name, schema in properties.items()
    )
    example_args = ", ".join(
        f"{name}={_EXAMPLE_VALUES.get(schema.get('type', ''), '...')}"
        for name, schema in properties.items()
    )
    return (
        f"- {tool.name}({params})\n"
        f"  {tool.description}\n"
        f"  Example: print({tool.name}({example_args}))"
    )
