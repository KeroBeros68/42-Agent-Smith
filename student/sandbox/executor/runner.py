"""Main loop running inside the container (§V.2.1, §V.2.2).

Reads JSON Lines from stdin, executes code in a persistent namespace shared
across the whole session, writes results back on stdout. Injects
`final_answer` into the namespace (constant regardless of the connected MCP
server) and stub functions for MCP tools that serialize a `tool_call`
message instead of calling anything directly (no network in the container).
Delegates import/builtins enforcement to restrictions.py and per-snippet
timeout to watchdog.py.
"""
