"""Loads SKILL.md files from a directory into memory.

A skill is a folder containing a SKILL.md file. The file has YAML
frontmatter (metadata) followed by a markdown body (the procedure).
See ARCHITECTURE.md §5.4 for the format.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml


# Required frontmatter keys. Any SKILL.md missing these is rejected.
REQUIRED_FIELDS = {"name", "description"}


@dataclass
class Skill:
    name: str
    description: str
    when_to_use: str
    body: str
    tools: list[str]
    version: int
    path: Path

    def index_line(self) -> str:
        """How the skill appears in the system prompt index."""
        line = f"  - {self.name}: {self.description}"
        if self.when_to_use:
            line += f"\n      use when: {self.when_to_use}"
        return line

    def to_prompt(self) -> str:
        """The full skill, formatted for injection into a conversation."""
        return (
            f"# SKILL: {self.name} (v{self.version})\n"
            f"{self.description}\n"
            f"\n"
            f"{self.body.strip()}\n"
        )


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a SKILL.md into (frontmatter_dict, body_string).

    The frontmatter must be delimited by a line containing exactly '---'
    at the start and another such line later.
    """
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with '---' frontmatter")
    end = text.find("\n---", 3)
    if end == -1:
        raise ValueError("SKILL.md frontmatter is not closed with '---'")
    front = text[3:end].strip()
    body = text[end + 4:].lstrip()
    data = yaml.safe_load(front) or {}
    if not isinstance(data, dict):
        raise ValueError("Frontmatter must be a YAML mapping")
    return data, body


def load_skill(skill_md: Path) -> Skill:
    """Load one SKILL.md. Raises ValueError if malformed."""
    raw = skill_md.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    missing = REQUIRED_FIELDS - meta.keys()
    if missing:
        raise ValueError(f"{skill_md}: missing required fields: {sorted(missing)}")
    return Skill(
        name=str(meta["name"]),
        description=str(meta["description"]),
        when_to_use=str(meta.get("when_to_use", "")),
        body=body,
        tools=list(meta.get("tools", []) or []),
        version=int(meta.get("version", 1)),
        path=skill_md,
    )


def load_skill_library(root: Path) -> dict[str, Skill]:
    """Walk a directory tree and load every SKILL.md found.

    Returns {skill_name: Skill}. Duplicate names are an error.
    Malformed skills are skipped with a warning on stderr — one broken
    file should not break the whole library.
    """
    root = Path(root).expanduser().resolve()
    skills: dict[str, Skill] = {}
    if not root.exists():
        return skills

    for path in sorted(root.rglob("SKILL.md")):
        try:
            skill = load_skill(path)
        except Exception as e:
            import sys
            print(f"[skills] skipping {path}: {e}", file=sys.stderr)
            continue
        if skill.name in skills:
            import sys
            print(
                f"[skills] duplicate name '{skill.name}' at {path}, ignoring",
                file=sys.stderr,
            )
            continue
        skills[skill.name] = skill
    return skills