"""The Machia CLI REPL."""
from __future__ import annotations
import argparse
import sys
import webbrowser
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


HELP_TEMPLATE = """\
Machia executes tasks on your local PC. Try:

  create a file called todo.txt with 'buy milk'
  list everything in my workspace
  my workspace is a mess, move files into subfolders by type
  save what you just did as a skill called 'file-organizer'
  list my skills

Commands:
  /help     show this help
  /skills   list loaded skills
  /mode     show current safety mode
  /clear    forget the conversation
  /web      open the web UI in your browser
  /exit     leave the REPL
"""


def run_cli(workspace: str, mode: str, web_url: str | None = None) -> int:
    """Run the interactive REPL. Called by main() and by launcher.py."""
    ui.print_banner()
    agent = build_agent(workspace, mode)
    ui.print_status(
        workspace=workspace,
        mode=mode,
        skills=list(agent.skills.keys()),
    )
    if web_url:
        ui.console.print(
            f"[dim]web UI:[/dim] [white]{web_url}[/white] "
            f"[dim](type /web to open)[/dim]"
        )
        ui.console.print()
    ui.console.print(
        "[dim]type[/dim] [white]/help[/white] "
        "[dim]for commands,[/dim] [white]/exit[/white] [dim]to quit.[/dim]"
    )
    ui.console.print()

    while True:
        line = ui.prompt_user().strip()

        if not line:
            continue

        cmd = line.lower()

        if cmd in ("/exit", "exit", "quit", ":q"):
            break

        if cmd in ("/help", "help", ":h", "?"):
            ui.console.print()
            ui.console.print(f"[{ui.SLATE}]{HELP_TEMPLATE}[/{ui.SLATE}]")
            continue

        if cmd == "/skills":
            ui.console.print()
            if agent.skills:
                for name, skill in agent.skills.items():
                    ui.console.print(
                        f"[bold {ui.INDIGO}]▎[/bold {ui.INDIGO}] "
                        f"[{ui.VIOLET}]{name}[/{ui.VIOLET}] "
                        f"[{ui.MUTED}]v{skill.version}[/{ui.MUTED}]  "
                        f"[{ui.WHITE}]{skill.description}[/{ui.WHITE}]"
                    )
            else:
                ui.console.print(f"[{ui.AMBER}]No skills loaded yet.[/{ui.AMBER}]")
            ui.console.print()
            continue

        if cmd == "/mode":
            ui.console.print()
            ui.console.print(
                f"[{ui.SLATE}]current mode:[/{ui.SLATE}] "
                f"[bold {ui.AMBER}]{agent.policy.mode}[/bold {ui.AMBER}]"
            )
            ui.console.print()
            continue

        if cmd == "/clear":
            agent.reset()
            ui.console.print(
                f"[{ui.MUTED}]conversation cleared.[/{ui.MUTED}]"
            )
            ui.console.print()
            continue

        if cmd == "/web":
            if web_url:
                ui.console.print(
                    f"[{ui.MUTED}]opening {web_url} …[/{ui.MUTED}]"
                )
                webbrowser.open(web_url)
            else:
                ui.console.print(
                    f"[{ui.AMBER}]Web UI is not running "
                    f"(started with --no-web).[/{ui.AMBER}]"
                )
            ui.console.print()
            continue

        try:
            answer = agent.run(line, verbose=True)
        except Exception as e:
            ui.print_error(f"{type(e).__name__}: {e}")
            continue

        ui.print_answer(answer)

    ui.print_separator()
    ui.console.print(f"[{ui.MUTED}]goodbye.[/{ui.MUTED}]")
    ui.console.print()
    return 0


def main() -> int:
    """Standalone CLI entry point (no launcher, no web UI)."""
    parser = argparse.ArgumentParser(prog="machia-cli")
    parser.add_argument("--workspace", "-w", default=".")
    parser.add_argument(
        "--mode", "-m",
        choices=["dry-run", "confirm", "auto"],
        default="confirm",
    )
    args = parser.parse_args()
    return run_cli(args.workspace, args.mode, web_url=None)


if __name__ == "__main__":
    sys.exit(main())