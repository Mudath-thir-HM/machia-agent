"""Validates and writes new SKILL.md files.

This module is the safety gate for skill creation. Every value that
goes into a SKILL.md — name, description, body — passes through here
before touching disk. See ARCHITECTURE.md §5.4 for the skill format.
"""
from __future__ import annotations
import re
from pathlib import Path

import yaml

# Matches tool names wrapped in backticks, e.g. `fs_write`.
_TOOL_IN_BODY_RE = re.compile(r"`([a-z][a-z0-9_]+)`")

# Skill names must be slugs. This prevents path traversal, absolute
# paths, Windows reserved names, and anything that isn't a clean folder.
# We accept both dashes and underscores — small models produce snake_case
# by default, and forcing dashes causes needless validation failures.
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
# A body over this size is refused. 4 KB is generous — our own
# organize-by-type skill is ~1 KB.
MAX_BODY_BYTES = 4096

# Frontmatter fields that must be present in the generated skill.
REQUIRED_FRONTMATTER = {"name", "description", "when_to_use", "version", "tools"}


class SkillValidationError(ValueError):
    """Raised when a proposed skill fails validation."""


def validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise SkillValidationError(
            f"Invalid skill name: {name!r}. "
            "Use lowercase letters, digits, dashes or underscores "
            "(e.g. 'sort-by-type' or 'sort_by_type')."
        )
    return name


def validate_body(body: str) -> str:
    if not isinstance(body, str) or not body.strip():
        raise SkillValidationError("Skill body is empty.")
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise SkillValidationError(
            f"Skill body is too large ({len(body.encode('utf-8'))} bytes). "
            f"Limit is {MAX_BODY_BYTES} bytes."
        )
    if body.startswith("---") or "\n---\n" in body:
        raise SkillValidationError(
            "Skill body must not contain '---' frontmatter delimiters."
        )

    # A procedure must contain at least two numbered steps.
    # Models that hallucinate often write plain paragraphs — reject those.
    numbered_steps = re.findall(r"(?:^|\s)\d+\.\s+\S", body)
    if len(numbered_steps) < 2:
        raise SkillValidationError(
            "Skill body must contain at least two numbered steps "
            "(e.g. '1. Call fs_list ... 2. Call fs_write ...'). "
            "Do not write prose descriptions."
        )

    return body


def validate_description(description: str) -> str:
    if not isinstance(description, str) or not description.strip():
        raise SkillValidationError("Skill description is empty.")
    if len(description) > 300:
        raise SkillValidationError("Skill description is too long (max 300 chars).")
    return description


def create_skill_file(
    skills_dir: Path,
    name: str,
    description: str,
    when_to_use: str,
    body: str,
    tools: list[str] | None = None,
    known_tools: set[str] | None = None,
) -> Path:
    """Validate and write a new SKILL.md. Returns the path written.

    Refuses to overwrite an existing skill.
    """
    # 1. Validate the raw inputs.
    name = validate_name(name)
    description = validate_description(description)
    body = validate_body(body)
    when_to_use = when_to_use or description

    # 2. Ensure the body ends with a finish step.
    if "finish" not in body.lower():
        existing_steps = sum(
            1 for ln in body.splitlines()
            if re.match(r"^\s*\d+\.\s+\S", ln)
        )
        body = body.rstrip() + (
            f"\n{existing_steps + 1}. Call `finish` with a one-line summary "
            "of what was done.\n"
        )

    # 3. Detect tool names in the body. This is authoritative — the model
    #    often forgets to list them, or lists the wrong ones.
    detected = set()
    for match in _TOOL_IN_BODY_RE.finditer(body):
        token = match.group(1)
        if known_tools is None or token in known_tools:
            detected.add(token)
    final_tools = sorted(detected | set(tools or []))

    # 4. Resolve the write path and jail it inside skills_dir.
    skills_dir = Path(skills_dir).expanduser().resolve()
    skill_dir = skills_dir / name
    skill_file = skill_dir / "SKILL.md"
    if not skill_dir.is_relative_to(skills_dir):
        raise SkillValidationError(f"Skill path escapes library: {skill_dir}")
    if skill_file.exists():
        raise SkillValidationError(
            f"A skill named '{name}' already exists. "
            f"Use a different name or delete the existing one at {skill_file}."
        )

    # 5. Build the frontmatter.
    frontmatter = {
        "name": name,
        "description": description,
        "when_to_use": when_to_use,
        "version": 1,
        "tools": final_tools,
    }
    missing = REQUIRED_FRONTMATTER - frontmatter.keys()
    if missing:
        raise SkillValidationError(f"Internal error: missing fields {missing}")

    fm_text = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    ).strip()
    full_text = f"---\n{fm_text}\n---\n\n{body.strip()}\n"

    # 6. Write atomically: temp file, then rename.
    skill_dir.mkdir(parents=True, exist_ok=True)
    tmp = skill_file.with_suffix(".md.tmp")
    tmp.write_text(full_text, encoding="utf-8")
    tmp.replace(skill_file)

    return skill_file