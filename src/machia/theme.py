"""The Machia CLI colour theme.

Palette: blue (structure), white (content), green (success / approval).
Also a few extras for warnings and errors, because a REPL without them
gets painful to read.
"""
from __future__ import annotations

from colorama import Fore, Style, init as _colorama_init

# Initialise colorama once at import time. On Windows this wraps stdout
# so ANSI escape sequences work; on Unix it's a no-op.
_colorama_init(autoreset=True)


# ---------- Raw colour codes ----------
BLUE = Fore.BLUE + Style.BRIGHT
GREEN = Fore.GREEN + Style.BRIGHT
WHITE = Fore.WHITE + Style.BRIGHT
YELLOW = Fore.YELLOW + Style.BRIGHT
RED = Fore.RED + Style.BRIGHT
DIM = Style.DIM


# ---------- Convenience wrappers ----------
def header(text: str) -> str:
    """Section headers, banner. Blue."""
    return f"{BLUE}{text}{Style.RESET_ALL}"


def content(text: str) -> str:
    """Regular output content. White."""
    return f"{WHITE}{text}{Style.RESET_ALL}"


def success(text: str) -> str:
    """Successful tool results, approvals, positive feedback. Green."""
    return f"{GREEN}{text}{Style.RESET_ALL}"


def warn(text: str) -> str:
    """Warnings: blocked calls, bad JSON, dry-run skips. Yellow."""
    return f"{YELLOW}{text}{Style.RESET_ALL}"


def error(text: str) -> str:
    """Errors. Red."""
    return f"{RED}{text}{Style.RESET_ALL}"


def muted(text: str) -> str:
    """Secondary info: timestamps, paths, technical detail. Dim."""
    return f"{DIM}{text}{Style.RESET_ALL}"


# ---------- The banner ----------
BANNER = f"""{BLUE}
 __  __    _    ____ _   _ ___    _
|  \\/  |  / \\  / ___| | | |_ _|  / \\
| |\\/| | / _ \\| |   | |_| || |  / _ \\
| |  | |/ ___ \\ |___|  _  || | / ___ \\
|_|  |_/_/   \\_\\____|_| |_|___/_/   \\_\\
{Style.RESET_ALL}{WHITE}
 An agent runtime for N-ATLAS.{Style.RESET_ALL}
"""