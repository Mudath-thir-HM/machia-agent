# Machia — Beta Tester Guide

You are about to try **Machia**, a local-first AI agent that runs on your
own computer. It can create, read, move, and organise files when you tell
it to — in plain English. It also writes its own reusable skills.

This is a **pre-release beta**. Expect rough edges. Your job is to find
them, not to enjoy them.

## What you need

- **Windows 10 or 11**
- **Python 3.11 or newer**
- **~6 GB free disk space**
- **~15 minutes** for the first install
- PowerShell

## Quickstart

Open PowerShell in the `machia-agent` folder and run:

```powershell
.\scripts\beta_pack\install.ps1
```

The script will:

1. Check that you have Python 3.11+
2. Install the machia package
3. Download the AI model (about 5 GB, one time)
4. Start the model server in a background window
5. Launch the Machia CLI

## Your first task

Once the CLI starts, type:

```text
list the files in my workspace
```

If Machia calls a tool and lists the files, the install worked. Then try
the five tasks in `tasks.md`.

## The rules of the beta

- Don't give it anything important. Use a scratch folder.
- Watch the approval prompts. Before file writes, Machia asks
  `allow? [y/N]`. Read before you type `y`.
- When something goes wrong, don't fix it. Write it down.

## What to send back

Run `.\scripts\beta_pack\collect.ps1` when you're done. It creates a zip
on your desktop. Send that zip plus your filled-in `feedback.md` back.

## Known limitations

- Slow on CPU. Each step takes 30–90 seconds.
- Sometimes forgets to stop. Press Ctrl+C if it loops.
- Multilingual chat is imperfect. Task instructions work better than
  casual conversation.
- No shell commands yet.

## Questions?

Message whoever sent you the pack.
