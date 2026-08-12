"""Host-side MCP client (stdio or HTTP streamable, §V.2.5).

Owns the actual connection to the connected MCP server and answers
`tool_call` messages relayed from inside the container over the JSON Lines
protocol — the container itself never gets network access, it only ever
talks to this bridge through the same stdio channel used for code exec.
"""
