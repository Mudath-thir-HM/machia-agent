"""The safety policy: decides whether a tool call is allowed to run.

Every tool call in the agent loop passes through Policy.check() before
execution. The policy implements the three modes from ARCHITECTURE.md §5.3:
dry-run, confirm, auto.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Callable

from ..tools.spec import ToolSpec
from .. import theme as t


@dataclass
class Decision:
    allowed: bool
    reason: str


class Policy:
    """Decides whether a tool may run, given its risk rating and the mode."""

    def __init__(
        self,
        mode: str = "confirm",
        auto_allow: list[str] | None = None,
        prompter: Callable[[str], str] | None = None,
    ) -> None:
        """mode: 'dry-run' | 'confirm' | 'auto'

        auto_allow: tool names that bypass the ask even in confirm/auto mode.
        prompter:   function that shows a prompt and returns the user's answer.
                    Defaults to input(); tests can pass a fake.
        """
        if mode not in ("dry-run", "confirm", "auto"):
            raise ValueError(f"Unknown policy mode: {mode}")
        self.mode = mode
        # Low-risk tools are always auto-allowed, regardless of user config.
        self.auto_allow = set(auto_allow or [])
        self._prompt = prompter or input

    def check(self, spec: ToolSpec, args: dict) -> Decision:
        """Return a Decision for this tool call."""

        # 1. Low-risk tools are always permitted. They cannot damage anything.
        if spec.risk == "low":
            return Decision(True, "low risk, auto-allowed")

        # 2. Explicitly allowlisted tools bypass everything else.
        if spec.name in self.auto_allow:
            return Decision(True, "in auto-allowlist")

        # 3. dry-run never lets medium/high tools execute.
        if self.mode == "dry-run":
            return Decision(False, f"dry-run: would have run {spec.name}")

        # 4. auto mode only allows allowlisted tools; without one, deny.
        if self.mode == "auto":
            return Decision(False, f"auto mode: {spec.name} not in allowlist")

        # 5. confirm mode: ask the human.
        question = (
            f"\n{t.warn('[APPROVAL NEEDED]')}\n"
            f"  {t.muted('tool:')} {t.content(spec.name)}\n"
            f"  {t.muted('risk:')} {t.warn(spec.risk)}\n"
            f"  {t.muted('args:')} {t.content(json.dumps(args, default=str))}\n"
            f"  {t.header('allow?')} {t.content('[y/N] ')}"
        )
        answer = self._prompt(question).strip().lower()
        if answer in ("y", "yes"):
            return Decision(True, "user approved")
        return Decision(False, "user denied")