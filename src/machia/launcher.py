"""Unified launcher: model server + CLI + optional web UI, one command.

Run:
    machia --workspace C:\\dev\\machia-workspace

or:
    python -m machia.launcher --workspace C:\\dev\\machia-workspace

Steps:
  1. Check whether llama-server is already running on 127.0.0.1:8080
  2. If not, spawn it (using --model PATH or searching common locations)
  3. Start the FastAPI web UI in a background thread
  4. Run the CLI in the foreground
  5. On exit, terminate the model server if we spawned it
"""
from __future__ import annotations
import argparse
import atexit
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import requests


LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080
WEB_HOST   = "127.0.0.1"
WEB_PORT   = 5000


def _web_url(port: int) -> str:
    return f"http://{WEB_HOST}:{port}"


def _llama_alive(timeout: float = 1.0) -> bool:
    try:
        r = requests.get(f"http://{LLAMA_HOST}:{LLAMA_PORT}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _find_llama_server() -> Optional[str]:
    """Search common locations for llama-server.exe."""
    which = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if which:
        return which
    winget_root = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if winget_root.exists():
        for match in winget_root.rglob("llama-server.exe"):
            return str(match)
    return None


def _find_model() -> Optional[str]:
    """Search common locations for the Q4_K_M gguf file."""
    names = [
        "ggml-model-Q4_K_M.gguf",
        "N-ATLaS-8B-Q4_K_M.gguf",
    ]
    roots = [
        Path("C:/dev/models"),
        Path.home() / "models",
        Path.cwd() / "models",
    ]
    for root in roots:
        if not root.exists():
            continue
        for name in names:
            p = root / name
            if p.exists():
                return str(p)
    return None


def _spawn_llama_server(model_path: str, log_path: Path) -> subprocess.Popen:
    exe = _find_llama_server()
    if not exe:
        print("   X  Could not find llama-server.exe")
        print("      Install with:  winget install ggml.llamacpp")
        print("      Or start it manually and re-run this command.")
        sys.exit(1)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("w", encoding="utf-8")

    print(f"      exe:   {exe}")
    print(f"      model: {model_path}")
    print(f"      log:   {log_path}")

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    return subprocess.Popen(
        [
            exe,
            "-m", model_path,
            "--host", LLAMA_HOST,
            "--port", str(LLAMA_PORT),
            "-c", "8192",
            "--threads", "8",
            "--jinja",
            "--n-gpu-layers", "0",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )


def _wait_for_llama(timeout: int = 90) -> bool:
    print("      loading", end="", flush=True)
    for _ in range(timeout):
        if _llama_alive():
            print(" ready.")
            return True
        print(".", end="", flush=True)
        time.sleep(1)
    print(" timed out.")
    return False


def _start_web_server(workspace: str, mode: str, port: int) -> None:
    """Start the FastAPI app in a daemon thread.

    The daemon thread dies with the process, so no explicit shutdown
    is needed.
    """
    # Populate _config before importing the app module.
    from machia.server import app as server_app
    server_app._config["workspace"] = str(Path(workspace).expanduser().resolve())
    server_app._config["mode"] = mode
    skills_dir = Path(__file__).resolve().parent.parent.parent / "skills"
    server_app._config["skills_dir"] = str(skills_dir) if skills_dir.exists() else None

    import uvicorn
    config = uvicorn.Config(
        server_app.app,
        host=WEB_HOST,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    def run() -> None:
        try:
            server.run()
        except Exception as e:
            print(f"      !  web server failed: {e}")

    threading.Thread(target=run, daemon=True, name="machia-web").start()
    # Give uvicorn a moment to bind the port.
    time.sleep(0.6)


def main() -> int:
    parser = argparse.ArgumentParser(prog="machia")
    parser.add_argument("--workspace", "-w", default=".")
    parser.add_argument(
        "--mode", "-m",
        choices=["dry-run", "confirm", "auto"],
        default="confirm",
    )
    parser.add_argument("--port", type=int, default=WEB_PORT,
                        help="Web UI port (default 5000)")
    parser.add_argument("--no-web", action="store_true",
                        help="Skip the web UI entirely")
    parser.add_argument("--no-spawn", action="store_true",
                        help="Do not auto-start llama-server")
    parser.add_argument("--model", default=None,
                        help="Path to the .gguf model file")
    args = parser.parse_args()

    print()
    print("  Machia — starting up")
    print()

    # ---- 1. Model server ----
    print("  [1/3] model server")
    spawned_proc = None
    if _llama_alive():
        print("      already running on http://127.0.0.1:8080")
    elif args.no_spawn:
        print("      X  not running, and --no-spawn was given. Aborting.")
        return 1
    else:
        model = args.model or _find_model()
        if not model:
            print("      X  model file not found.")
            print("         Pass --model PATH, or place ggml-model-Q4_K_M.gguf in C:\\dev\\models.")
            return 1
        log_path = Path.home() / ".machia" / "llama-server.log"
        spawned_proc = _spawn_llama_server(model, log_path)
        if not _wait_for_llama():
            print(f"      check the log: {log_path}")
            return 1

    if spawned_proc is not None:
        def _cleanup() -> None:
            try:
                spawned_proc.terminate()
            except Exception:
                pass
        atexit.register(_cleanup)

    # ---- 2. Web UI ----
    if not args.no_web:
        print("  [2/3] web UI")
        try:
            _start_web_server(args.workspace, args.mode, args.port)
            print(f"      running at {_web_url(args.port)}")
        except Exception as e:
            print(f"      X  could not start: {e}")
            print(f"         Continuing without the web UI.")
    else:
        print("  [2/3] web UI disabled")

    # ---- 3. CLI ----
    print("  [3/3] CLI")
    print()

    # Hand off to the CLI, which will print its own banner.
    from machia.cli import run_cli

    # Show the web URL prominently before the CLI takes over.
    if not args.no_web:
        print(f"  Web UI:  {_web_url(args.port)}   (type /web to open)")
        print()

    return run_cli(args.workspace, args.mode, web_url=(None if args.no_web else _web_url(args.port)))


if __name__ == "__main__":
    sys.exit(main())