# Machia

**An agent runtime for N-ATLAS.**Machia turns [N-ATLAS](https://huggingface.co/NCAIR1/N-ATLaS) from a chat model into a **local agent that acts on your PC**. You give it a task in English, Hausa, Igbo, Yoruba, or Nigerian Pidgin. It plans, calls tools on your filesystem, asks before doing anything risky, and **writes new skills for itself** so it gets better with use.

Everything runs locally. No API keys. No cloud. No extra model service in the loop.

---

## What it does

- **Runs N-ATLAS offline** — quantized Q4_K_M, CPU-only, no GPU needed.
- **Calls tools** — reads, writes, moves, and deletes files in a sandboxed workspace.
- **Asks before it acts** — every medium/high-risk action requires your explicit approval. Everything is logged.
- **Learns new skills** — after completing a task, you can tell it to save the procedure. It writes a `SKILL.md` file and can reuse it in the next session, in any supported language.
- **Speaks Nigerian languages** — task instructions work in English, Hausa, Igbo, Yoruba, and Nigerian Pidgin.

---

## Requirements

| Item       | Requirement                     |
| ---------- | ------------------------------- |
| **OS**     | Windows 10/11, macOS, or Linux  |
| **Python** | 3.11 or newer                   |
| **Disk**   | ~6 GB (mostly the model)        |
| **RAM**    | 8 GB minimum, 16 GB comfortable |
| **GPU**    | Not required                    |

---

## Quick start

### Windows (PowerShell)

```powershell
git clone https://github.com/Mudath-thir-HM/machia-agent machia-agent
cd machia-agent
.\scripts\beta_pack\install.ps1
```

### macOS / Linux (bash)

```bash
git clone https://github.com/Mudath-thir-HM/machia-agent machia-agent
cd machia-agent
chmod +x scripts/beta_pack/*.sh
./scripts/beta_pack/install.sh
```

Either installer:

1. Verifies Python 3.11+
2. Installs the machia package
3. Checks for the model (and tells you how to download it if missing)
4. Starts the model server in the background
5. Drops you into the CLI

---

## Using it

Once the CLI starts, you'll see:

```text
 __  __    _    ____ _   _ ___    _
|  \/  |  / \  / ___| | | |_ _|  / \
| |\/| | / _ \| |   | |_| || |  / _ \
| |  | |/ ___ \ |___|  _  || | / ___ \
|_|  |_/_/   \_\____|_| |_|___/_/   \_\

  an agent runtime for N-ATLAS

workspace C:\dev\machia-workspace
mode confirm
skills organize-by-type
Type a task:

machia > list the files in my workspace
machia > create a file called todo.txt with 'buy milk, eggs, bread'
machia > save what you just did as a skill called 'make-todo'
```

### Slash commands

| Command   | What it does                    |
| --------- | ------------------------------- |
| `/help`   | Examples and command list       |
| `/skills` | List loaded skills              |
| `/mode`   | Show the current safety mode    |
| `/clear`  | Forget the conversation         |
| `/web`    | Open the web UI in your browser |
| `/exit`   | Leave the REPL                  |

### Safety model

Every tool call passes through a safety policy before it runs:

| Mode      | Behaviour                                                   |
| --------- | ----------------------------------------------------------- |
| `dry-run` | Plan only. No side effects.                                 |
| `confirm` | Default. Every medium/high-risk action asks `allow? [y/N]`. |
| `auto`    | Allowlisted tools run without prompting.                    |

Every call is appended to `~/.machia/audit.jsonl` — a full trace you can inspect or submit as evidence.

The filesystem is path-jailed to the workspace you pass with `--workspace`. Attempts to read or write outside that folder are rejected by the tool layer, not the model.

---

## How it works

```text
┌───────────────────────────────────────────┐
│ N-ATLAS (Llama-3 8B fine-tune, Q4*K_M) │
│ served by llama.cpp on 127.0.0.1:8080    │
└────────────────────┬──────────────────────┘
                     │ HTTP
                     ▼
┌────────────────────▼──────────────────────┐
│ Machia agent loop                          │
│ think → call a tool → observe → repeat     │
└───────┬──────────────┬─────────────────┬────┘
        │              │                 │
        ▼              ▼                 ▼
   ┌─────────┐   ┌────────────┐   ┌──────────────┐
   │ Tools   │   │ Safety     │   │ Skills       │
   │ fs*     │   │ policy     │   │ SKILL.md     │
   │ shell   │   │ + audit    │   │ progressive │
   │ meta    │   │            │   │ disclosure   │
   └─────────┘   └────────────┘   └──────────────┘
```

The agent loop is in `src/machia/agent.py`. It's roughly 400 lines and heavily commented. Read that file to understand the whole system.

Detailed architecture is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Skills

A skill is a Markdown file with YAML frontmatter:

```yaml
name: organize-by-type
description: Sort files in a folder into subfolders by file extension.
when_to_use: User asks to clean up, sort, or organize a messy folder.
version: 1
tools: [fs_list, fs_move]
```

### Procedure

1. Call `fs_list` to see files in the workspace.
2. Group by extension: images, documents, installers, etc.
3. Call `fs_move` for each file to move it into the right subfolder.
4. Call `finish` with a summary.

Skills live in `skills/`. Only the name and description go into the system prompt on every turn — the body is loaded on demand via the `load_skill` tool. This keeps the 8K context budget under control.

The agent can create new skills with `create_skill`. This is the self-improvement loop: the user runs a task, asks the agent to remember how, and the skill is available in the next session.

---

## Project layout

```text
machia-agent/
├── README.md            ← you are here
├── pyproject.toml
├── docs/
│   └── ARCHITECTURE.md  ← full system design
├── skills/              ← SKILL.md library
│   └── organize-by-type/
├── src/machia/
│   ├── agent.py         ← the loop
│   ├── cli.py           ← REPL
│   ├── launcher.py      ← one-command startup
│   ├── ui.py            ← terminal UI
│   ├── backends/        ← LLM backends
│   ├── prompting/       ← chat format, grammar
│   ├── tools/           ← fs, shell, meta, skills
│   ├── skills/          ← loader, creator
│   ├── safety/          ← policy, audit
│   └── server/          ← FastAPI web UI
├── evals/              ← task suite
├── scripts/
│   └── beta_pack/      ← cross-platform installer
└── tests/
```

---

## Development

```bash
# Editable install with all deps
pip install -e .

# Run the CLI
python -m machia.cli --workspace ./workspace

# Run the launcher (model + web + CLI)
machia --workspace ./workspace

# Run the web UI only
python -m machia.server.app --workspace ./workspace
```

---

## Backend swap

The agent never talks to a specific model server — it talks to an `LLMBackend`. Three implementations exist:

- `LocalLlamaServer` — talks to `llama-server` over HTTP (default)
- `RemoteGPU` — same interface, different host
- `NatlasAPI` — official N-ATLAS API (when credentials are available)

Change backends without touching any agent code.

---

## Status

This is a v0 design built for the NAIC 2026 Problem Statement 1 — Developer Infrastructure. The submission deadline is 12 Oct 2026.

What works today:

- ✅ Local N-ATLAS server on CPU
- ✅ Agent loop with tool calling
- ✅ Filesystem tools with path jail
- ✅ Safety policy (dry-run / confirm / auto)
- ✅ Audit log (JSONL)
- ✅ Skill library with progressive disclosure
- ✅ `create_skill` — self-improvement loop
- ✅ CLI with themed UI and spinner
- ✅ FastAPI web UI with live streaming
- ✅ Cross-platform installer (Windows + macOS/Linux)

What's planned:

- ☐ GBNF grammar for tool calls (eliminates malformed output)
- ☐ `shell_exec` with allowlist
- ☐ Multilingual task benchmarks
- ☐ Rented-GPU backend for the demo video

---

## Beta testers

If you have a copy of this repo and were asked to run it, start here:

- [`scripts/beta_pack/README.md`](scripts/beta_pack/README.md) — the tester guide
- [`scripts/beta_pack/tasks.md`](scripts/beta_pack/tasks.md) — the 5 tasks
- [`scripts/beta_pack/feedback.md`](scripts/beta_pack/feedback.md) — the survey

When you're done, run `collect.ps1` (Windows) or `collect.sh` (macOS/Linux) to bundle your trace into a zip and send it back.

---

## Acknowledgements

- N-ATLAS — NCAIR Nigeria. Llama-3 8B fine-tune, multilingual.
- llama.cpp — the GGUF runtime that makes CPU inference practical.
- Rich — the terminal UI library.

---

## License

To be determined before submission.
| Select-Object Name, Length
Expected:

text
Name Length

---

README.md ~2500
collect.ps1 ~3600
collect.sh ~3000
feedback.md ~2600
install.ps1 ~6700
install.sh ~5500
tasks.md ~3700
Also confirm the root README saved:

powershell
Get-Item README.md | Select-Object Name, Length

```

```
