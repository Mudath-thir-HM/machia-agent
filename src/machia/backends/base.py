"""Abstract interface that every LLM backend must implement.

Why this exists: the agent code should never know whether it is talking
to a local llama.cpp server, a rented GPU, or the official N-ATLAS API.
It just calls .chat() and gets a response back.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass
class Message:
    """A single message in a conversation"""
    role: str           # 'system' | 'user' | 'assistant' | 'tool'
    content: str = ""
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None # only present on "tool" role messages
    name: str | None = None
    
@dataclass
class LLMResponse:
    """What every backend returns from a .chat()"""
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    
class LLMBackend(Protocol):
    """The contract. Any backend we write must have these methods."""

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        ...

    def count_tokens(self, text: str) -> int:
        ...