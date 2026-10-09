"""Beautiful terminal UI for Machia, powered by rich.

Aesthetic: minimal dark TUI. Indigo/violet structure, subtle rules,
gradient blue->green wordmark, and a compact spinner during inference.
"""
from __future__ import annotations
from contextlib import contextmanager
from typing import Iterator

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text
from rich import box


# The one true console.
console = Console()


# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------

INDIGO  = "#6366f1"
VIOLET  = "#8b5cf6"
EMERALD = "#10b981"
AMBER   = "#f59e0b"
ROSE    = "#f43f5e"
SLATE   = "#94a3b8"
MUTED   = "#64748b"
WHITE   = "#f8fafc"

# Banner gradient endpoints: blue -> green
BANNER_C1 = "#3b82f6"
BANNER_C2 = "#22c55e"


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

_MACHIA_ASCII = r"""
 __  __    _    ____ _   _ ___    _
|  \/  |  / \  / ___| | | |_ _|  / \
| |\/| | / _ \| |   | |_| || |  / _ \
| |  | |/ ___ \ |___|  _  || | / ___ \
|_|  |_/_/   \_\____|_| |_|___/_/   \_\
"""


def _lerp_hex(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate two hex colours, returning '#rrggbb'."""
    def parse(h: str):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    r1, g1, b1 = parse(c1)
    r2, g2, b2 = parse(c2)
    return "#{:02x}{:02x}{:02x}".format(
        int(r1 * (1 - t) + r2 * t),
        int(g1 * (1 - t) + g2 * t),
        int(b1 * (1 - t) + b2 * t),
    )


def _gradient_line(line: str, c1: str, c2: str) -> Text:
    """Apply a horizontal gradient across one line of ASCII art."""
    out = Text()
    n = max(1, len(line) - 1)
    for i, ch in enumerate(line):
        out.append(ch, style=Style(color=_lerp_hex(c1, c2, i / n)))
    return out


def print_banner() -> None:
    """Gradient wordmark inside a double-edged panel."""
    art_lines = _MACHIA_ASCII.strip("\n").splitlines()
    body = Text()
    for ln in art_lines:
        body.append_text(_gradient_line(ln, BANNER_C1, BANNER_C2))
        body.append("\n")

    subtitle = Text("an agent runtime for N-ATLAS", style=f"italic {SLATE}")

    console.print()
    console.print(
        Panel(
            Group(Align.center(body), Align.center(subtitle)),
            border_style=INDIGO,
            box=box.DOUBLE_EDGE,
            padding=(0, 4),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Startup status
# ---------------------------------------------------------------------------

def print_status(workspace: str, mode: str, skills: list[str]) -> None:
    """Compact key/value block inside a subtle border."""
    mode_colour = {
        "auto":    EMERALD,
        "confirm": AMBER,
        "dry-run": SLATE,
    }.get(mode, WHITE)

    table = Table.grid(padding=(0, 2))
    table.add_column(style=f"dim {SLATE}", justify="right")
    table.add_column(style=WHITE)
    table.add_row("workspace", f"[{WHITE}]{workspace}[/{WHITE}]")
    table.add_row("mode",      f"[bold {mode_colour}]{mode}[/bold {mode_colour}]")
    table.add_row(
        "skills",
        (", ".join(f"[{VIOLET}]{s}[/{VIOLET}]" for s in skills)
         if skills else f"[dim {AMBER}](none loaded)[/dim {AMBER}]"),
    )

    console.print(
        Panel(
            table,
            title=f"[bold {INDIGO}]session[/bold {INDIGO}]",
            border_style=INDIGO,
            box=box.SIMPLE_HEAD,
            padding=(0, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Answer / error / hint output
# ---------------------------------------------------------------------------

def answer_panel(text: str) -> Panel:
    return Panel(
        Text(text, style=WHITE),
        title=f"[bold {EMERALD}]  answer[/bold {EMERALD}]",
        border_style=EMERALD,
        box=box.ROUNDED,
        padding=(1, 3),
    )


def error_panel(text: str) -> Panel:
    return Panel(
        Text(text, style=WHITE),
        title=f"[bold {ROSE}]  error[/bold {ROSE}]",
        border_style=ROSE,
        box=box.ROUNDED,
        padding=(1, 3),
    )


def hint_panel(text: str) -> Panel:
    return Panel(
        Text(text, style=f"italic {AMBER}"),
        title=f"[bold {AMBER}]  hint[/bold {AMBER}]",
        border_style=AMBER,
        box=box.ROUNDED,
        padding=(1, 3),
    )


# ---------------------------------------------------------------------------
# Inference spinner
# ---------------------------------------------------------------------------

_SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


class Spinner:
    """Compact centred spinner shown while the model runs.

    The frame counter advances inside __rich_console__, so the animation
    runs without a background thread while the main thread blocks on the
    model call.
    """

    def __init__(self, label: str = "thinking") -> None:
        self.label = label
        self.frame = 0

    def __rich_console__(self, console: Console, options) -> Iterator:
        tick = self.frame
        self.frame += 1

        spin = _SPINNER[tick % len(_SPINNER)]

        line = Text()
        line.append("  ")
        line.append(spin, style=f"bold {EMERALD}")
        line.append("  ")
        line.append(f"{self.label}", style=WHITE)
        line.append("…", style=MUTED)

        yield Panel(
            Align.center(line),
            border_style=INDIGO,
            box=box.ROUNDED,
            padding=(0, 3),
            expand=False,
        )


@contextmanager
def thinking(label: str = "thinking") -> Iterator[None]:
    """Context manager: show the spinner while the block runs.

    The animation is transient -- it disappears when the block exits,
    so it doesn't clutter the scrollback.
    """
    with Live(
        Spinner(label),
        console=console,
        refresh_per_second=10,
        transient=True,
    ):
        yield


# ---------------------------------------------------------------------------
# Separators and prompt
# ---------------------------------------------------------------------------

def print_separator() -> None:
    console.print(Rule(style=MUTED))


def prompt_user() -> str:
    """Display the styled prompt and read one line."""
    console.print(
        f"[bold {INDIGO}]machia[/bold {INDIGO}]"
        f"[{SLATE}] >[/{SLATE}] ",
        end="",
    )
    try:
        return input()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return "exit"