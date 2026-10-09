"""The load_skill and create_skill tools.

Unlike fs_* and sys_info, these tools are built dynamically — they need
access to the loaded skill library and the skills directory. Hence the
factory pattern.

Argument tolerance notes:
- load_skill accepts several aliases for the `name` argument, because
  small models frequently invent names ('skill', 'skill_name', 'id').
- create_skill picks the best body candidate from any of several fields
  (the model has been seen splitting the procedure across 'procedure'
  and 'code'), and normalizes the `tools` field which may arrive as
  a list, a JSON-encoded string, or a comma-separated string.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

from .spec import ToolSpec
from ..skills.loader import Skill
from ..skills.creator import create_skill_file, SkillValidationError


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

# Argument names the model might invent for load_skill's `name`.
NAME_ALIASES = ("name", "skill", "skill_name", "skill_id", "id")

# Argument aliases the model might invent for create_skill.
CREATE_ALIASES = {
    "name": ("name", "skill", "skill_name", "id"),
    "description": ("description", "desc", "summary"),
    "when_to_use": ("when_to_use", "when", "trigger", "use_when"),
    "body": ("body", "procedure", "content", "instructions", "steps"),
    "tools": ("tools", "tool_names", "uses"),
}

# Fields the model has used for the procedure body.
BODY_ALIASES = (
    "body", "procedure", "instructions", "steps",
    "markdown", "code", "actions", "text", "content",
)

PLACEHOLDERS = {"your procedure here", "todo", "tbd", "n/a", "...", "<procedure>"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_tools(raw) -> list[str]:
    """Best-effort: turn whatever the model sent into a list of tool names.

    The model has been observed sending:
      - a real list:                ["fs_write"]
      - a JSON-encoded list string: '["fs_write"]'
      - a bare name:                "fs_write"
      - a comma-separated string:   "fs_write, fs_list"
    We accept all of them.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(t).strip() for t in raw if str(t).strip()]
    if isinstance(raw, str):
        s = raw.strip()
        # JSON-encoded list, e.g. '["fs_write", "fs_list"]'
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(t).strip() for t in parsed if str(t).strip()]
            except json.JSONDecodeError:
                pass
        # Comma-separated string.
        if "," in s:
            return [t.strip() for t in s.split(",") if t.strip()]
        # Single name.
        return [s] if s else []
    return [str(raw)]


def _score_body(text: str) -> float:
    """Rate a candidate body. Numbered steps > backticked tools > length."""
    numbered = sum(
        1 for ln in text.splitlines()
        if re.match(r"^\s*\d+\.\s+\S", ln)
    )
    backticks = text.count("`")
    return numbered * 10 + backticks * 2 + min(len(text), 2000) / 200


def _pick_body(kwargs: dict) -> str | None:
    """Choose the best body candidate from any alias field.

    Small models sometimes split the procedure across fields
    ('procedure' gets prose, 'code' gets the numbered list). We pick
    whichever candidate looks most like a real procedure.
    """
    candidates: list[str] = []
    for alias in BODY_ALIASES:
        v = kwargs.get(alias)
        if isinstance(v, str) and v.strip():
            v = v.strip()
            if v.lower() not in PLACEHOLDERS and len(v) > 15:
                candidates.append(v)
    if not candidates:
        return None
    candidates.sort(key=_score_body, reverse=True)
    return candidates[0]


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------

def make_load_skill_tool(get_skills) -> ToolSpec:
    """Return a ToolSpec that reads skills via a zero-arg getter.

    The getter is called on every invocation, so the tool always sees
    the *current* library — including any skills added by create_skill
    during the same session. This is what makes hot-reload work without
    ever re-registering the tool.
    """

    def load_skill(**kwargs) -> dict:
        skills = get_skills()  # fresh read every call
        requested = None
        for key in NAME_ALIASES:
            if key in kwargs:
                requested = kwargs[key]
                break
        if requested is None:
            return {
                "error": "Missing skill name. Provide it as 'name'.",
                "available_skills": sorted(skills.keys()),
            }
        skill = skills.get(str(requested))
        if skill is None:
            return {
                "error": f"Unknown skill: {requested}",
                "available_skills": sorted(skills.keys()),
            }
        return {
            "name": skill.name,
            "version": skill.version,
            "body": skill.to_prompt(),
        }

    return ToolSpec(
        name="load_skill",
        description=(
            "Read the full procedure of a skill. Call this BEFORE starting "
            "a task that matches a skill."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The skill name exactly as written in the SKILLS list.",
                }
            },
            "required": ["name"],
        },
        function=load_skill,
        risk="low",
    )


# ---------------------------------------------------------------------------
# create_skill
# ---------------------------------------------------------------------------

def make_create_skill_tool(
    skills_dir: Path,
    on_created: callable | None = None,
    known_tools: set[str] | None = None,
) -> ToolSpec:
    """Return a ToolSpec that lets the model write a new SKILL.md.

    on_created: optional callback(skill_path) called after a successful
                write. The agent uses this to hot-reload the library.
    """

    def _pick(kwargs: dict, field: str):
        for key in CREATE_ALIASES[field]:
            if key in kwargs:
                return kwargs[key]
        return None

    def create_skill(**kwargs) -> dict:
        name = _pick(kwargs, "name")
        description = _pick(kwargs, "description")
        when_to_use = _pick(kwargs, "when_to_use")
        body = _pick_body(kwargs)
        tools = _pick(kwargs, "tools") or []

        if not name or not description or not body:
            return {
                "error": "Missing required field(s).",
                "required": {
                    "name": "slug like 'sort-files'",
                    "description": "one sentence",
                    "body": "markdown procedure",
                },
                "received": {
                    k: ("<empty>" if not v else str(v)[:80])
                    for k, v in {
                        "name": name,
                        "description": description,
                        "body": body,
                    }.items()
                },
            }

        tools = _normalize_tools(tools)

        try:
            path = create_skill_file(
                skills_dir=Path(skills_dir),
                name=str(name),
                description=str(description),
                when_to_use=str(when_to_use or description),
                body=str(body),
                tools=[str(t) for t in tools],
                known_tools=known_tools,
            )
        except SkillValidationError as e:
            return {"error": str(e)}

        if on_created is not None:
            try:
                on_created(path)
            except Exception:
                # Non-fatal: the file exists, the reload just failed.
                pass

        return {
            "created": str(path),
            "name": name,
            "message": (
                f"Skill '{name}' was saved. It is now available for use "
                f"in this session."
            ),
        }

    return ToolSpec(
        name="create_skill",
        description=(
            "Save a new SKILL.md to the skill library. Use this when the "
            "user asks you to save a procedure you just performed, or to "
            "remember how to do something for next time."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "A slug (lowercase letters, digits, dashes), e.g. 'sort-files-by-type'.",
                },
                "description": {
                    "type": "string",
                    "description": "One sentence describing what the skill does.",
                },
                "when_to_use": {
                    "type": "string",
                    "description": "When the skill should be used.",
                },
                "body": {
                    "type": "string",
                    "description": (
                        "The step-by-step markdown procedure. Use numbered steps. "
                        "Reference tool names like `fs_list` and `fs_move`."
                    ),
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tool names this procedure uses.",
                },
            },
            "required": ["name", "description", "when_to_use", "body"],
        },
        function=create_skill,
        risk="medium",
        requires_approval=True,
    )