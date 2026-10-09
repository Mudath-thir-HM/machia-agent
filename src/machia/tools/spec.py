"""The shape of a Tool: a name, a JSON schema, and a Python function."""
from __future__ import annotations
from typing import Any, Callable
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class ToolSpec:
    """One tool the agent can call.

    name:         the function name the model will emit, e.g. "fs_list"
    description:  a one-sentence English description for the model
    parameters:   JSON Schema describing the arguments
    function:     the Python function that actually runs
    risk:         "low" | "medium" | "high"  -- used by the safety policy later
    requires_approval:  if True, the loop pauses and asks the user first
    """
    name: str
    description: str
    parameters: dict[str, Any]
    function: Callable[..., Any]
    risk: str = "low"
    requires_approval: bool = False
    # Alias map: canonical_argument_name -> tuple of accepted synonyms.
    # The registry remaps incoming argument keys to the canonical name
    # before calling the function. Small models routinely invent
    # argument names ('file' instead of 'path'); this absorbs that.
    aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_openai_schema(self) -> dict:
        """Return the schema in the format llama-server expects."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }