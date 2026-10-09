"""Meta-tools: tools that control the agent rather than acting on the PC."""
from __future__ import annotations
from .spec import ToolSpec


def finish(message: str = "") -> dict:
    """Sentinel — the agent loop intercepts this before it runs.

    If you're seeing this function execute, the loop is broken.
    """
    raise RuntimeError("finish() should be intercepted by the agent loop, not run.")


FINISH = ToolSpec(
    name="finish",
    description=(
        "Call this ONLY when you have the answer the user asked for. "
        "Pass the final answer text in `message`."
    ),
    parameters={
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": (
                    "The final answer to the user's question, as a complete "
                    "sentence containing the real data you found."
                ),
            }
        },
        "required": ["message"],
    },
    function=finish,
    risk="low",
)

