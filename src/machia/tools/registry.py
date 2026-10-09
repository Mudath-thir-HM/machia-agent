"""A registry of tools. The agent loop asks it what exists and runs them."""
from __future__ import annotations
from typing import Any
from .spec import ToolSpec


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool '{spec.name}' is already registered")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def schemas(self) -> list[dict]:
        """All schemas, ready to pass to the model."""
        return [spec.to_openai_schema() for spec in self._tools.values()]

    def run(self, name: str, arguments: dict[str, Any]) -> Any:
        """Execute a tool by name. Remaps aliased argument keys first."""
        spec = self._tools.get(name)
        if spec is None:
            raise ValueError(f"Unknown tool: {name}")
        remapped = self._remap_aliases(spec, arguments)
        return spec.function(**remapped)


    def _remap_aliases(self, spec: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
        """Map synonym keys to canonical argument names.

        Example: if the spec declares aliases={'path': ('file', 'filename')}
        and the model sends {'file': 'x.txt'}, this returns {'path': 'x.txt'}.
        """
        if not spec.aliases:
            return dict(arguments)
        # Build a reverse lookup: alias -> canonical.
        reverse: dict[str, str] = {}
        for canonical, synonyms in spec.aliases.items():
            for syn in synonyms:
                reverse[syn] = canonical
        out: dict[str, Any] = {}
        for key, val in arguments.items():
            out[reverse.get(key, key)] = val
        return out


    def known_names(self) -> list[str]:
        """All registered tool names. Used for 'did you mean' hints."""
        return sorted(self._tools.keys())