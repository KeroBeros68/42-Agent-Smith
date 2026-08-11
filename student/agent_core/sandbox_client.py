"""Generic client used by the agent loop to talk to the `sandbox` process.

Transport-agnostic (stdio or HTTP), benchmark-agnostic. Surfaces the explicit
feedback cases required by §V.1.3: no code block found, malformed block,
timeout, truncated output, syntax/lint error after an edit.
"""
