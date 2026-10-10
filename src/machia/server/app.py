"""FastAPI web server for Machia.

Serves a single-page UI and streams agent events over SSE.
Run with:
    python -m machia.server.app --workspace C:\\path\\to\\workspace
"""
from __future__ import annotations
import argparse
import asyncio
import json
import threading
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from ..agent import Agent
from ..backends.llamacpp import LocalLlamaServer
from ..tools import (
    ToolRegistry, FINISH, SYS_INFO,
    FS_LIST, FS_READ, FS_WRITE, FS_MOVE, FS_DELETE,
)
from ..safety.policy import Policy
from ..safety.audit import AuditLog


# ---------------------------------------------------------------------------
# Global state (single-user, so a module-level dict is fine)
# ---------------------------------------------------------------------------

app = FastAPI(title="Machia")

# Configuration set at startup by main().
_config: dict[str, Any] = {
    "workspace": ".",
    "skills_dir": None,
    "mode": "confirm",
}

# Per-session state.
_sessions: dict[str, dict] = {}
# session_id -> asyncio.Queue of events
_queues: dict[str, asyncio.Queue] = {}
# approval_id -> threading.Event
_approvals: dict[str, threading.Event] = {}
# approval_id -> "y" | "n"
_approval_answers: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Agent construction
# ---------------------------------------------------------------------------

def _build_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(SYS_INFO)
    reg.register(FS_LIST)
    reg.register(FS_READ)
    reg.register(FS_WRITE)
    reg.register(FS_MOVE)
    reg.register(FS_DELETE)
    reg.register(FINISH)
    return reg


def _build_agent(policy: Policy, on_event) -> Agent:
    """Build a fresh agent per session.

    Each web session gets its own Agent so conversation history and
    callback closures don't leak between users.
    """
    skills_dir = _config.get("skills_dir")
    return Agent(
        backend=LocalLlamaServer(),
        registry=_build_registry(),
        workspace_root=_config["workspace"],
        max_steps=25,
        policy=policy,
        audit=AuditLog(),
        skills_dir=skills_dir,
        on_tool_call=lambda name, args: on_event("tool_call", {"name": name, "args": args}),
        on_tool_result=lambda name, result: on_event("tool_result", {"name": name, "result": result}),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    html_path = Path(__file__).parent / "static" / "index.html"
    return html_path.read_text(encoding="utf-8")


@app.get("/api/config")
async def get_config():
    return {
        "workspace": _config["workspace"],
        "mode": _config["mode"],
    }


@app.get("/api/skills")
async def list_skills():
    """List skills currently in the library."""
    skills_dir = _config.get("skills_dir")
    if not skills_dir:
        return {"skills": []}
    from ..skills import load_skill_library
    lib = load_skill_library(Path(skills_dir))
    return {
        "skills": [
            {
                "name": s.name,
                "description": s.description,
                "when_to_use": s.when_to_use,
                "version": s.version,
                "tools": s.tools,
            }
            for s in lib.values()
        ]
    }


@app.get("/api/audit")
async def get_audit(limit: int = 30):
    """Return the most recent audit entries."""
    audit_path = Path("~/.machia/audit.jsonl").expanduser()
    if not audit_path.exists():
        return {"entries": []}
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return {"entries": list(reversed(entries))}


@app.post("/api/chat")
async def start_chat(payload: dict):
    """Start a new agent run. Returns a session_id to stream events from."""
    message = (payload or {}).get("message", "").strip()
    if not message:
        raise HTTPException(400, "message is required")

    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    _queues[session_id] = queue

    loop = asyncio.get_running_loop()

    def push(event_type: str, data: dict) -> None:
        """Thread-safe push of an event into the session queue."""
        loop.call_soon_threadsafe(queue.put_nowait, {"type": event_type, "data": data})

    def web_prompter(question: str) -> str:
        """Called from the agent thread when a tool needs approval.

        Emits an approval_needed event, then blocks until the client
        POSTs a decision to /api/approve/{id}.
        """
        approval_id = str(uuid.uuid4())
        event = threading.Event()
        _approvals[approval_id] = event
        push("approval_needed", {"id": approval_id, "question": question})
        event.wait(timeout=300)  # 5 min, then auto-deny
        answer = _approval_answers.pop(approval_id, "n")
        _approvals.pop(approval_id, None)
        return answer

    policy = Policy(mode=_config["mode"], prompter=web_prompter)
    agent = _build_agent(policy=policy, on_event=push)
    _sessions[session_id] = {"agent": agent, "history": []}

    def run_agent() -> None:
        try:
            answer = agent.run(message, verbose=False)
            push("answer", {"text": answer})
        except Exception as e:
            push("error", {"text": f"{type(e).__name__}: {e}"})
        finally:
            push("done", {})

    threading.Thread(target=run_agent, daemon=True).start()

    return {"session_id": session_id}


@app.get("/api/stream/{session_id}")
async def stream(session_id: str):
    """Server-Sent Events stream of agent progress for one session."""
    if session_id not in _queues:
        raise HTTPException(404, "unknown session")

    queue = _queues[session_id]

    async def event_generator():
        try:
            while True:
                event = await queue.get()
                yield {
                    "event": event["type"],
                    "data": json.dumps(event["data"]),
                }
                if event["type"] == "done":
                    break
        finally:
            _queues.pop(session_id, None)

    return EventSourceResponse(event_generator())


@app.post("/api/approve/{approval_id}")
async def approve(approval_id: str, payload: dict):
    """Client sends the user's decision on a pending approval."""
    if approval_id not in _approvals:
        raise HTTPException(404, "unknown or expired approval")
    allow = bool((payload or {}).get("allow", False))
    _approval_answers[approval_id] = "y" if allow else "n"
    _approvals[approval_id].set()
    return {"ok": True}


@app.get("/api/session/{session_id}/reset")
async def reset_session(session_id: str):
    """Forget a session's conversation."""
    if session_id in _sessions:
        _sessions[session_id]["agent"].reset()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(prog="machia-web")
    parser.add_argument("--workspace", "-w", default=".")
    parser.add_argument(
        "--mode", "-m",
        choices=["dry-run", "confirm", "auto"],
        default="confirm",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    # Find skills directory next to the repo root.
    skills_dir = Path(__file__).resolve().parent.parent.parent.parent / "skills"

    _config["workspace"] = str(Path(args.workspace).expanduser().resolve())
    _config["mode"] = args.mode
    _config["skills_dir"] = str(skills_dir) if skills_dir.exists() else None

    print()
    print("  Machia web UI")
    print(f"  workspace: {_config['workspace']}")
    print(f"  skills:    {_config['skills_dir'] or '(none)'}")
    print(f"  mode:      {_config['mode']}")
    print()
    print(f"  Open:      http://{args.host}:{args.port}")
    print()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()