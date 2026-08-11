"""Extraction of executable code from LLM output (§V.1.2).

Must handle: ```python ... ``` <end_code>, Anthropic-style XML tool calls,
JSON/Hermes tool_call blocks, and ReAct Action/Action Input pairs.
Non-Python formats are converted to equivalent Python function calls.
"""
