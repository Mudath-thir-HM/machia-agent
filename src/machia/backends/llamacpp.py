"""Talks to a local `llama-server` process over HTTP.

We deliberately do NOT use the API's `tools=` parameter. The llama.cpp
PEG parser rejects N-ATLAS's native tool-call format, so we describe tools
in the system prompt instead and extract tool calls from the model's text
output ourselves. See docs/ARCHITECTURE.md §5.2.
"""
from __future__ import annotations
import json
import re
import requests
from .base import Message, LLMResponse


class LocalLlamaServer:
    """LLMBackend that talks to llama.cpp's llama-server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout  # CPU inference is slow; be patient

    def chat(
        self,
        messages: list[Message],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        # Convert our Message dataclasses into the JSON the API expects.
        payload_messages = []
        for m in messages:
            msg: dict = {"role": m.role, "content": m.content}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            payload_messages.append(msg)

        # NOTE: we deliberately do NOT include a "tools" key here.
        # Tool schemas live in the system prompt (see agent.py).
        payload: dict = {
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})

        raw_content = choice.get("content") or ""

        # Try to pull a tool call out of the model's text output.
        tool_calls = _extract_tool_call(raw_content)

        return LLMResponse(
            content="" if tool_calls else raw_content,
            tool_calls=tool_calls,
            raw=data,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

    def count_tokens(self, text: str) -> int:
        # Rough approximation: ~4 chars per token for English.
        return len(text) // 4


# ---------------------------------------------------------------------------
# Tool-call extraction helpers (module-level, NOT inside the class)
# ---------------------------------------------------------------------------

# Matches a JSON object of the form {"name": "...", "parameters": {...}}.
# Deliberately permissive: allows prose around it, code fences, etc.
_TOOL_CALL_RE = re.compile(
    r'\{\s*"name"\s*:\s*"([A-Za-z_][A-Za-z0-9_]*)"\s*,'
    r'\s*"parameters"\s*:\s*(\{.*?\})\s*\}',
    re.DOTALL,
)


def _extract_tool_call(text: str) -> list[dict]:
    """Find a {"name": ..., "parameters": ...} block in the model's output.

    Returns a list with one synthetic tool call in the OpenAI/Llama-3.1
    format, or an empty list if nothing was found.
    """
    if not text:
        return []

    # First try: the entire output is a clean JSON object.
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and "name" in obj and "parameters" in obj:
                return [_to_openai_shape(obj)]
        except json.JSONDecodeError:
            pass

    # Second try: find a tool-call block embedded in prose or code fences.
    m = _TOOL_CALL_RE.search(text)
    if m:
        name = m.group(1)
        try:
            params = json.loads(m.group(2))
        except json.JSONDecodeError:
            return []
        return [_to_openai_shape({"name": name, "parameters": params})]

    return []


def _to_openai_shape(obj: dict) -> dict:
    """Wrap a {"name", "parameters"} dict into the OpenAI tool_calls shape."""
    return {
        "id": "call_0",
        "type": "function",
        "function": {
            "name": obj["name"],
            "arguments": json.dumps(obj.get("parameters", {})),
        },
    }