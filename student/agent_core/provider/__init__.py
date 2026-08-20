"""LLM provider abstraction — multi-provider, multi-key (§V.6).

- ``AbstractLLM``: interface every provider implementation must satisfy
- ``LLM``: LiteLLM-backed implementation with per-provider key rotation
- ``LLMError``: raised on provider configuration errors
"""

from agent_core.provider.base import AbstractLLM, LLM, LLMError

__all__ = [
    "AbstractLLM",
    "LLM",
    "LLMError",
]
