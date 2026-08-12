"""JSON Lines message schemas shared by the host (container.py, mcp_bridge.py)
and the in-container runner.py (decided 2026-08-12).

Message kinds to define: exec (code to run), tool_call (relay to mcp_bridge),
result, error — covering the explicit feedback cases required by §V.1.3
(no code block found, malformed block, timeout, truncated output, syntax
error after an edit).
"""
