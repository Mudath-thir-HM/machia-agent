---
name: organize-by-type
description: Sort files in the workspace root into subfolders by file extension.
when_to_use: User asks to clean up, sort, or organize a messy folder or workspace.
version: 2
tools: [fs_list, fs_move]
---

## Procedure

Follow these steps IN ORDER. Do not skip any. Do not add any.

**Step 1.** Call `fs_list` with `path="."` to see the workspace root.

**Step 2.** From the listing, identify every entry whose `type` is `"file"`.
IGNORE every entry whose `type` is `"dir"`. Never move folders.
Never look inside subfolders. Only the top-level files matter.

**Step 3.** For each top-level file, decide its destination using this
table. The mapping is FINAL — do not override it:

| Extension               | Destination folder |
| ----------------------- | ------------------ |
| jpg, jpeg, png, gif     | `images/`          |
| pdf, doc, docx, txt, md | `documents/`       |
| exe, msi                | `installers/`      |
| mp3, wav, flac          | `audio/`           |
| mp4, mov, mkv           | `videos/`          |
| anything else           | `other/`           |

**Step 4.** Call `fs_move` ONCE per top-level file. The `src` is the
filename only (e.g. `report.pdf`), never a path with a subfolder in it.
The `dst` is the destination folder plus the filename
(e.g. `documents/report.pdf`).

**Step 5.** After you have moved every top-level file exactly once,
call `finish` with a summary. Example:
"Moved 6 files: 2 to documents/, 1 to images/, 1 to installers/, 2 to other/."

## Forbidden actions

- Do NOT call `fs_list` more than once at the start.
- Do NOT look inside `images/`, `documents/`, `other/`, or any
  folder you create.
- Do NOT move a file that is already inside a subfolder.
- Do NOT move the same file twice.
- Do NOT move `downloads/` or any other existing folder.
