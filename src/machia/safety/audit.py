"""Append-only audit log. Every tool call lands here.

Format: newline-delimited JSON (JSONL). One record per line.
Location: ~/.machia/audit.jsonl by default.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, path: str | Path = "~/.machia/audit.jsonl") -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, **fields) -> None:
        """Append one record. Adds a UTC timestamp automatically."""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def tail(self, n: int = 20) -> list[dict]:
        """Read the last N records. Useful for debugging and for the UI."""
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        return [json.loads(line) for line in lines[-n:] if line.strip()]