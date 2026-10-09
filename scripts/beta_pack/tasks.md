# Machia — Beta Test Tasks

Run these five tasks in order. Each one is a little harder than the last.

**Before you start:** make sure the Machia CLI is running. The prompt
looks like `machia >`.

**For each task:**

- Run it
- Note whether it succeeded (yes / partly / no)
- Note anything confusing, surprising, or broken
- Fill in the "Your notes" line

Do not fix the machine between tasks. A messy workspace is a feature.

---

## Task 1 — List files (warm-up)

**Type this:**

```text
list the files in my workspace
```

**What should happen:**

Machia calls `fs_list`, then tells you how many files and folders are
in the workspace.

**What could go wrong:**

- It reads the wrong folder
- It only lists some of the files
- It says "Task complete" without listing anything

**Your notes:**

---

## Task 2 — Create a file

**Type this:**

```text
create a file called hello.txt with 'made by machia'
```

**What should happen:**

1. Machia asks `allow? [y/N]`
2. You type `y` and press Enter
3. The file is created and Machia confirms

**Then verify in PowerShell:**

```powershell
Get-Content $env:USERPROFILE\machia-workspace\hello.txt
```

Should print made by machia.

**What could go wrong:**

- It writes to the wrong place
- The confirmation message is vague ("Task complete")
- The file is empty

**Your notes:**

---

## Task 3 — Read a file back

**Type this:**

```text
read the file hello.txt and tell me what's in it
```

**What should happen:**

Machia calls `fs_read` and prints the contents in the answer panel.

**What could go wrong:**

- It reads a different file
- It summarizes instead of quoting
- It says the file doesn't exist when it does

**Your notes:**

---

## Task 4 — Save a skill (the interesting one)

First, do a task that's worth remembering:

```text
create a file called todo.txt with 'milk, eggs, bread'
```

Approve the write. Wait for confirmation.

Then, in the same session, type:

```text
save what you just did as a skill called 'make-todo'
```

**What should happen:**

1. A yellow hint panel appears
2. Machia calls `create_skill` and asks for approval
3. You approve
4. Machia says the skill was saved

Then check it exists in PowerShell (in a different terminal):

```powershell
Get-Content C:\dev\Hackathon\machia-agent\skills\make-todo\SKILL.md
```

You should see YAML frontmatter (name, description, tools) followed by
a numbered procedure.

**What could go wrong:**

- The hint doesn't appear (routing failed)
- The skill body is prose instead of numbered steps
- The `tools:` list is empty or wrong
- "The file isn't where you expected"

**Your notes:**

---

## Task 5 — Use the skill in a new session

Exit the CLI (type `exit`).

Restart it:

```powershell
python -m machia.cli --workspace $env:USERPROFILE\machia-workspace
```

Check the startup banner — your new make-todo skill should be listed
under `skills:`.

Now try a new task that should match the skill:

```text
create a file called shopping.txt with 'rice, beans, yam'
```

**What should happen:**

The first step should be `load_skill`, not `fs_write`. Then it writes
the file.

This is the moment that matters most. If the agent loads its own
skill and follows it, the self-improvement loop is working.

**What could go wrong:**

- It skips `load_skill` and writes directly (the hint failed)
- It loads the skill but ignores the procedure
- It loops, repeating the same call

**Your notes:**

---

## When you're done

Run `collect.ps1` to bundle everything up. Then fill in `feedback.md`
and send both back.
