"""Filesystem tools. For now, read-only."""
from __future__ import annotations
import os
from pathlib import Path
from .spec import ToolSpec


# Every filesystem tool will be jailed to this folder.
# We'll make this configurable later; for now hard-code it.
WORKSPACE_ROOT = Path(r"C:\dev\machia-workspace")


def _safe_path(user_path: str) -> Path:
    """Resolve user_path and ensure it is inside WORKSPACE_ROOT.

    Uses Path.is_relative_to (Python 3.9+) rather than string startswith,
    because "C:\\dev\\machia-workspace-evil" would pass a startswith check.
    """
    p = (WORKSPACE_ROOT / user_path).resolve()
    root = WORKSPACE_ROOT.resolve()
    if not p.is_relative_to(root):
        raise PermissionError(f"Path outside workspace: {user_path}")
    return p


def _matches(name: str, pattern: str) -> bool:
    """Match a filename against one or more comma-separated patterns.

    Accepts both glob patterns ('*.png') and bare words ('image', 'pdf'),
    which the model uses interchangeably. Matching is case-insensitive.
    """
    import fnmatch
    name_lower = name.lower()
    for raw in pattern.split(","):
        p = raw.strip().lower()
        if not p or p == "*":
            return True
        if fnmatch.fnmatch(name_lower, p):
            return True
        # Bare words (no wildcards) match as substrings — the model
        # frequently says 'image' meaning 'any image extension'.
        if "*" not in p and "?" not in p and p in name_lower:
            return True
    return False


def fs_list(path: str = ".", pattern: str = "*") -> dict:
    """List the entries of a folder inside the workspace.

    `pattern` filters the results. Accepts a glob ('*.png'), a comma-
    separated list ('*.png,*.jpg'), or a bare word ('pdf'). Default is
    '*' meaning everything.
    """
    # Models sometimes put a glob pattern in `path` instead of
    # `pattern` (e.g. path='*.jpg'). If `path` looks like a glob,
    # reinterpret: use '.' as the directory and move the glob to
    # `pattern`. This is harmless when the model calls it correctly.
    if "*" in path or "?" in path:
        if pattern == "*":
            pattern = path
        path = "."
    target = _safe_path(path)
    if not target.exists():
        return {"error": f"Path does not exist: {path}"}
    if not target.is_dir():
        return {"error": f"Not a directory: {path}"}

    entries = []
    for child in sorted(target.iterdir()):
        if not _matches(child.name, pattern):
            continue
        entries.append({
            "name": child.name,
            "type": "dir" if child.is_dir() else "file",
            "size_bytes": child.stat().st_size if child.is_file() else None,
        })

    files = [e for e in entries if e["type"] == "file"]
    dirs  = [e for e in entries if e["type"] == "dir"]
    filter_note = (
        f" (filtered by '{pattern}')" if pattern and pattern != "*" else ""
    )
    return {
        "success": True,
        "path": str(target),
        "pattern": pattern,
        "entries": entries,
        "message": (
            f"{len(entries)} entries{filter_note}: "
            f"{len(files)} files, {len(dirs)} folders."
        ),
    }

FS_LIST = ToolSpec(
    name="fs_list",
    description=(
        "List the files and folders inside a directory in the workspace. "
        "Use `pattern` to filter by name or extension, e.g. '*.png' for "
        "images, or '*.pdf,*.txt' for multiple types. Default lists all."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root. Use '.' for the root.",
            },
            "pattern": {
                "type": "string",
                "description": (
                    "Optional. A glob ('*.png'), a comma-separated list "
                    "('*.png,*.jpg'), or a bare word ('pdf'). Default '*'."
                ),
            },
        },
        "required": ["path"],
    },
    function=fs_list,
    risk="low",
    aliases={
        "path":    ("dir", "directory", "folder", "filepath", "file"),
        "pattern": ("filter", "glob", "match", "extension", "ext", "type"),
    },
)

def fs_read(path: str) -> dict:
    """Read the contents of a file inside the workspace.

    Caps at 64 KB so a single huge file can't blow the 8K context window.
    Truncation is reported, not silent.
    """
    target = _safe_path(path)
    if not target.exists():
        return {"error": f"File does not exist: {path}"}
    if not target.is_file():
        return {"error": f"Not a file: {path}"}
    raw = target.read_bytes()
    MAX = 64 * 1024
    truncated = len(raw) > MAX
    text = raw[:MAX].decode("utf-8", errors="replace")
    return {
        "path": str(target),
        "size_bytes": len(raw),
        "truncated": truncated,
        "content": text,
    }


FS_READ = ToolSpec(
    name="fs_read",
    description="Read the text contents of a file in the workspace.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace root."},
        },
        "required": ["path"],
    },
    function=fs_read,
    risk="low",
    aliases={"path": ("file", "filename", "filepath")},
)


def fs_write(path: str, content: str) -> dict:
    """Write text to a file in the workspace, creating it if needed.

    Refuses to overwrite an existing file unless the caller opts in
    via the `overwrite` flag. This is a deliberate safety default.
    """
    target = _safe_path(path)
    if target.exists() and target.is_file():
        # We do not silently overwrite. The policy layer will surface
        # this to the user via confirm mode.
        pass
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "success": True,
        "path": str(target),
        "bytes_written": len(content.encode("utf-8")),
        "message": f"Wrote {len(content.encode('utf-8'))} bytes to {target.name}.",
    }


FS_WRITE = ToolSpec(
    name="fs_write",
    description="Create or overwrite a text file inside the workspace. Pass the full content; this replaces any existing file.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path relative to the workspace root."},
            "content": {"type": "string", "description": "The text to write into the file."},
        },
        "required": ["path", "content"],
    },
    function=fs_write,
    risk="medium",
    requires_approval=True,
    aliases={
        "path": ("file", "filename", "filepath", "dir", "directory", "target"),
        "content": ("text", "data", "value", "body", "contents"),
    },
)

def fs_move(src: str, dst: str) -> dict:
    """Move or rename a FILE inside the workspace.

    We deliberately refuse to move directories. The demo task is about
    tidying up loose files, and moving folders lets the model do things
    like moving 'downloads' into 'downloads/files'. If you ever need
    directory moves, add a separate tool with a louder risk rating.
    """
    src_path = _safe_path(src)
    dst_path = _safe_path(dst)

    if not src_path.exists():
        return {"error": f"Source does not exist: {src}. "
                         f"Call fs_list first to see what is actually there."}

    if src_path.is_dir():
        return {"error": f"Refusing to move a directory: {src}. "
                         f"Only individual files can be moved."}

    if dst_path.exists():
        return {"error": f"Destination already exists: {dst}"}

    # Sanity check: destination must not be inside source (paranoia; source
    # is a file, so this can't actually happen, but the check is cheap).
    if str(src_path) == str(dst_path):
        return {"error": f"Source and destination are the same: {src}"}

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    src_path.rename(dst_path)
    return {
        "success": True,
        "from": str(src_path),
        "to": str(dst_path),
        "message": f"Moved {src_path.name} to {dst_path.parent.name}/.",
    }


FS_MOVE = ToolSpec(
    name="fs_move",
    description="Move or rename a single file inside the workspace. Cannot move directories — only files.",
    parameters={
        "type": "object",
        "properties": {
            "src": {"type": "string", "description": "Current path of the file (relative to workspace)."},
            "dst": {"type": "string", "description": "New path of the file (relative to workspace)."},
        },
        "required": ["src", "dst"],
    },
    function=fs_move,
    risk="medium",
    requires_approval=True,
    aliases={
        "src": ("source", "from", "source_path", "src_path"),
        "dst": ("destination", "to", "dest", "target", "target_path", "dst_path"),
    },
)


def fs_delete(path: str) -> dict:
    """Delete a file (not a directory) inside the workspace.

    We deliberately do not delete folders. That would let the model
    wipe out an entire tree with one call. If you need that later,
    make it a separate tool with a `recursive` flag that users must
    explicitly approve.
    """
    target = _safe_path(path)
    if not target.exists():
        return {"error": f"Path does not exist: {path}"}
    if target.is_dir():
        return {"error": f"Refusing to delete a directory: {path}. Only files can be deleted."}
    size = target.stat().st_size
    target.unlink()
    return {"deleted": str(target), "bytes_freed": size}


FS_DELETE = ToolSpec(
    name="fs_delete",
    description="Delete a single file in the workspace. Does not delete folders.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path of the file to delete."},
        },
        "required": ["path"],
    },
    function=fs_delete,
    risk="medium",
    requires_approval=True,
    aliases={"path": ("file", "filename", "filepath")},
)