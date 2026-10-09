"""The Machia CLI REPL."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from . import ui
from .backends.llamacpp import LocalLlamaServer
from .tools import (
    ToolRegistry, FINISH, SYS_INFO,
    FS_LIST, FS_READ, FS_WRITE, FS_MOVE, FS_DELETE,
)
from .agent import Agent
from .safety.policy import Policy
from .safety.audit import AuditLog


def build_agent(workspace: str, mode: str) -> Agent:
    reg = ToolRegistry()
    reg.register(SYS_INFO)
    reg.register(FS_LIST)
    reg.register(FS_READ)
    reg.register(FS_WRITE)
    reg.register(FS_MOVE)
    reg.register(FS_DELETE)
    reg.register(FINISH)

    skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"

    return Agent(
        backend=LocalLlamaServer(),
        registry=reg,
        workspace_root=workspace,
        max_steps=25,
        policy=Policy(mode=mode),
        audit=AuditLog(),
        skills_dir=skills_dir,
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="machia")
    parser.add_argument("--workspace", "-w", default=".")
    parser.add_argument(
        "--mode", "-m",
        choices=["dry-run", "confirm", "auto"],
        default="confirm",
    )
    args = parser.parse_args()

    ui.print_banner()
    agent = build_agent(args.workspace, args.mode)
    ui.print_status(
        workspace=args.workspace,
        mode=args.mode,
        skills=list(agent.skills.keys()),
    )
    ui.console.print(
        "[dim]type[/dim] [white]help[/white] "
        "[dim]for examples,[/dim] [white]exit[/white] [dim]to quit.[/dim]"
    )
    ui.console.print()

    while True:
        line = ui.prompt_user().strip()

        if not line:
            continue
        if line.lower() in ("exit", "quit", ":q"):
            break
        if line.lower() in ("help", ":h", "?"):
            ui.console.print(
                "[bold blue]commands[/bold blue]\n"
                "  [white]exit, quit, :q[/white]  – leave the REPL\n"
                "  [white]help, :h, ?[/white]     – this help\n"
                "\n"
                "[bold blue]try[/bold blue]\n"
                "  [green]List the files in my workspace.[/green]\n"
                "  [green]Create a file called todo.txt with 'buy milk'[/green]\n"
                "  [green]Save what you just did as a skill.[/green]\n"
            )
            continue

        try:
            answer = agent.run(line, verbose=True)
        except Exception as e:
            ui.console.print(ui.error_panel(f"{type(e).__name__}: {e}"))
            ui.console.print()
            continue

        ui.console.print()
        ui.console.print(ui.answer_panel(answer))
        ui.console.print()


if __name__ == "__main__":
    sys.exit(main())