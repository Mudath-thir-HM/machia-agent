"""The agent loop: think -> call a tool -> feed the result back -> repeat."""
from __future__ import annotations
import json
from typing import Callable
from pathlib import Path

from . import ui
from .skills import load_skill_library, Skill
from .backends.base import LLMBackend, Message
from .tools.registry import ToolRegistry
from .safety.policy import Policy
from .safety.audit import AuditLog
from .tools.skills import make_load_skill_tool, make_create_skill_tool


class Agent:
    def __init__(
        self,
        backend: LLMBackend,
        registry: ToolRegistry,
        workspace_root: str,
        max_steps: int = 10,
        policy: Policy | None = None,
        audit: AuditLog | None = None,
        skills_dir: str | Path | None = None,
        on_tool_call: Callable[[str, dict], None] | None = None,
        on_tool_result: Callable[[str, object], None] | None = None,
    ):
        self.backend = backend
        self.registry = registry
        self.workspace_root = workspace_root
        self.max_steps = max_steps
        self.policy = policy or Policy(mode="confirm")
        self.audit = audit or AuditLog()
        self.on_tool_call = on_tool_call or (lambda name, args: None)
        self.on_tool_result = on_tool_result or (lambda name, result: None)
        self.messages: list[Message] = []

        self.skills: dict[str, Skill] = {}
        self.skills_dir: Path | None = None
        if skills_dir is not None:
            self.skills_dir = Path(skills_dir).expanduser().resolve()
            self.skills = load_skill_library(self.skills_dir)
            self.registry.register(make_load_skill_tool(lambda: self.skills))
            self.registry.register(
                make_create_skill_tool(
                    self.skills_dir,
                    on_created=self._reload_skills,
                    known_tools=set(self.registry.known_names()),
                )
            )

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    def _recent_tool_calls(self, max_calls: int = 6) -> list[tuple[str, str]]:
        calls: list[tuple[str, str]] = []
        for m in self.messages:
            if m.role == "assistant" and m.tool_calls:
                for tc in m.tool_calls:
                    fn = tc.get("function", {})
                    calls.append((fn.get("name", "?"), fn.get("arguments", "{}")))
        return calls[-max_calls:]

    def _reload_skills(self, _path=None) -> None:
        if self.skills_dir is None:
            return
        self.skills = load_skill_library(self.skills_dir)

    def _trim_context(self, max_estimated_tokens: int = 4000) -> None:
        """Trim the oldest non-system messages to keep the prompt small."""
        if len(self.messages) < 3:
            return

        def est(msg: Message) -> int:
            n = len(msg.content or "")
            if msg.tool_calls:
                n += len(json.dumps(msg.tool_calls, default=str))
            return max(1, n // 4)

        system_msg = self.messages[0]
        rest = self.messages[1:]

        budget = max_estimated_tokens - est(system_msg)
        kept: list[Message] = []
        for msg in reversed(rest):
            cost = est(msg)
            if cost > budget:
                break
            kept.append(msg)
            budget -= cost
        kept.reverse()

        while kept and kept[0].role != "user":
            kept.pop(0)

        if kept:
            self.messages = [system_msg] + kept

    # -----------------------------------------------------------------
    # Skill hint routing
    # -----------------------------------------------------------------

    def _skill_hint(self, user_message: str) -> str:
        msg_lower = user_message.lower()

        save_markers = (
            "save that as a skill", "save this as a skill",
            "save it as a skill",
            "save what you just", "save what i just",
            "save the procedure", "save that procedure",
            "make that a skill", "make this a skill",
            "make it a skill",
            "create a skill", "remember how to", "add a skill",
            "as a skill called", "as a skill named",
        )

        if any(m in msg_lower for m in save_markers):
            base_hint = (
                "HINT: The user wants you to save a skill.\n"
                "\n"
                "STEP 1: Look at the conversation above. The task you just "
                "completed is the procedure to save.\n"
                "\n"
                "STEP 2: Call create_skill with these fields:\n"
                "  name:         lowercase slug (letters, digits, dashes)\n"
                "  description:  ONE sentence describing WHAT the skill does\n"
                "  when_to_use:  WHEN the skill should be used\n"
                "  tools:        list of tool names you used\n"
                "  body:         a NUMBERED MARKDOWN PROCEDURE with the exact\n"
                "                steps you took, using tool names in backticks\n"
                "\n"
                "IMPORTANT: The description and body must describe a GENERAL\n"
                "procedure, not the specific task you just did. If you wrote\n"
                "'Create recipe.txt with jollof rice recipe', that is too specific.\n"
                "Generalize to 'Create a text file with the given name and content'.\n"
                "\n"
                "Example of a GOOD body:\n"
                "  1. Call `fs_list` to see files in the workspace.\n"
                "  2. Call `fs_write` with `path` and `content`.\n"
                "  3. Call `finish` with a one-line summary.\n"
                "\n"
                "Do NOT write prose that describes what a skill 'would do'.\n"
                "Do NOT invent steps that did not happen.\n"
            )
            recent = self._recent_tool_calls()
            if recent:
                lines = "\n".join(f"  - {name}({args})" for name, args in recent)
                base_hint += (
                    "\nYOUR RECENT TOOL CALLS (these ARE the procedure):\n"
                    f"{lines}\n"
                )
            return base_hint

        if not self.skills:
            return ""
        stopwords = {
            "user", "wants", "want", "with", "that", "this", "from", "into",
            "file", "files", "folder", "text", "when", "then", "have", "will",
            "here", "some", "them", "also", "each", "made", "make", "does",
            "should", "must", "not", "but", "for", "and", "the", "can",
            "create", "creates", "content", "specific", "given",
        }
        scores: list[tuple[int, str]] = []
        for skill in self.skills.values():
            name_words = {w for w in skill.name.split("-") if len(w) >= 3}
            text = f"{skill.when_to_use} {skill.description}".lower()
            text_words = {
                w.strip(".,()[]:;\"'")
                for w in text.split()
                if len(w) >= 4 and w.strip(".,()[]:;\"'") not in stopwords
            }
            score = 0
            for w in name_words:
                if w in msg_lower:
                    score += 2
            for w in text_words:
                if w in msg_lower:
                    score += 1
            if score >= 2:
                scores.append((score, skill.name))
        if not scores:
            return ""
        scores.sort(reverse=True)
        best = scores[0][1]
        return (
            f"HINT: This request matches the '{best}' skill.\n"
            f"Call `load_skill` with name='{best}' as your FIRST action, "
            f"then follow the procedure step by step.\n"
            f"IMPORTANT: '{best}' is a skill, not a tool. Do NOT call it "
            f"directly. Call the `load_skill` TOOL and pass the skill name "
            f"as its `name` argument."
        )

    # -----------------------------------------------------------------
    # System prompt
    # -----------------------------------------------------------------

    def _system_prompt(self) -> str:
        tool_names = ", ".join(s.name for s in self.registry.all())

        if self.skills:
            skill_lines = "\n".join(s.index_line() for s in self.skills.values())
            skills_block = (
                "SKILLS (call load_skill FIRST to read the full procedure):\n"
                f"{skill_lines}\n"
                "\n"
            )
        else:
            skills_block = ""

        return (
            "You are Machia, a local agent for this Windows machine.\n"
            f"Workspace: {self.workspace_root}\n"
            "\n"
            f"{skills_block}"
            f"Tools: {tool_names}\n"
            "\n"
            "To call a tool, reply with ONLY this JSON and nothing else:\n"
            '  {"name": "<tool>", "parameters": {<values>}}\n'
            "\n"
            "RULES:\n"
            "1. If the task matches a SKILL, call load_skill first.\n"
            "2. Before moving/deleting/reading files, call fs_list to see what exists.\n"
            "3. Use paths relative to the workspace (e.g. 'notes.txt', not 'C:\\...').\n"
            "4. One tool call per turn. Never repeat a failed call.\n"
            "5. When done, call finish with the actual answer, not 'Task complete'.\n"
            "6. When following a skill, do exactly what it says. Do not improvise.\n"
            "7. When the user asks to save a procedure as a skill, call create_skill.\n"
            "8. If the user's message is conversational (a greeting, a question\n"
            "   about you, or a question you can answer without using any tool),\n"
            "   reply with plain text. No tool call.\n"
        )

    # -----------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------

    def run(self, user_message: str, verbose: bool = True) -> str:
        if self.messages and self.messages[0].role == "system":
            self.messages[0] = Message(role="system", content=self._system_prompt())
        else:
            self.messages.insert(0, Message(role="system", content=self._system_prompt()))

        hint = self._skill_hint(user_message)
        if hint and verbose:
            ui.console.print(ui.hint_panel(hint))
            ui.console.print()

        self.messages.append(Message(role="user", content=user_message))

        messages = self.messages
        call_counts: dict[str, int] = {}
        hint_for_this_step = hint
        successful_calls: dict[str, str] = {}

        for step in range(1, self.max_steps + 1):
            self._trim_context()

            call_messages = list(self.messages)
            if hint_for_this_step:
                call_messages.append(
                    Message(role="user", content=hint_for_this_step)
                )

            with ui.thinking(f"step {step}"):
                response = self.backend.chat(
                    messages=call_messages,
                    tools=self.registry.schemas(),
                    max_tokens=256,
                )
            hint_for_this_step = ""

            # 2. No tool call? Reply is text.
            if not response.tool_calls:
                text = (response.content or "").strip()
                looks_like_tool_call = (
                    text.startswith('{"name"')
                    or text.startswith('{ "name"')
                    or '"parameters"' in text[:120]
                )

                if messages and messages[-1].role == "tool":
                    try:
                        last = json.loads(messages[-1].content)
                        if isinstance(last, dict) and last.get("message"):
                            return str(last["message"])
                    except (json.JSONDecodeError, TypeError):
                        pass

                if looks_like_tool_call:
                    return (
                        "I attempted to call a tool but produced malformed "
                        "output. Please try again with a clearer instruction."
                    )
                return text

            # 3. Extract the tool call.
            tool_call = response.tool_calls[0]
            tool_name = tool_call["function"]["name"]
            args_raw = tool_call["function"]["arguments"]
            call_id = tool_call.get("id", "call_0")

            fingerprint = f"{tool_name}:{args_raw}"
            call_counts[fingerprint] = call_counts.get(fingerprint, 0) + 1
            if call_counts[fingerprint] >= 2:
                if fingerprint in successful_calls:
                    if verbose:
                        ui.console.print(
                            f"[dim]  ✓ done — finishing on the model's behalf[/dim]"
                        )
                    return successful_calls[fingerprint]
                if verbose:
                    ui.console.print(
                        f"[yellow]  ✗ identical failing call repeated "
                        f"({call_counts[fingerprint]}x), aborting[/yellow]"
                    )
                return (
                    f"Stopped: the same tool call ({tool_name}) was repeated "
                    f"with identical arguments and no progress. "
                    f"Last raw call: {args_raw[:200]}"
                )

            # 4. Parse args.
            try:
                args = json.loads(args_raw) if args_raw else {}
                if not isinstance(args, dict):
                    raise ValueError("arguments must be a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                if verbose:
                    ui.console.print(f"[yellow]  ✗ bad JSON from model: {e}[/yellow]")
                messages.append(Message(
                    role="assistant", content="", tool_calls=[tool_call],
                ))
                messages.append(Message(
                    role="tool",
                    content=json.dumps({"error": f"invalid JSON: {e}"}),
                    tool_call_id=call_id,
                ))
                continue

            if verbose:
                ui.console.print(
                    f"[white]  →[/white] [bold cyan]{tool_name}[/bold cyan]"
                    f"[white]({args})[/white]"
                )
            self.on_tool_call(tool_name, args)

            # 5. Finish.
            if tool_name == "finish":
                for val in args.values():
                    if isinstance(val, str) and val.strip():
                        return val.strip()
                return "Done."

            # 6. Append assistant turn.
            messages.append(Message(
                role="assistant", content=response.content, tool_calls=[tool_call],
            ))

            # 7a. Policy lookup.
            spec = self.registry.get(tool_name)
            if spec is None:
                if tool_name in self.skills:
                    lower = user_message.lower()
                    conversational = not any(
                        w in lower
                        for w in (
                            "create", "write", "save", "read", "list",
                            "move", "delete", "make", "file", "folder",
                            "sort", "organize",
                        )
                    )
                    if conversational:
                        error = {
                            "error": f"'{tool_name}' is not the right tool for this message.",
                            "fix": (
                                "The user's message is conversational. "
                                "Reply with plain text. Do NOT call any tool."
                            ),
                        }
                        if verbose:
                            ui.console.print(
                                f"[yellow]  ! '{tool_name}' is a skill, but the "
                                f"message is conversational — replying in text[/yellow]"
                            )
                    else:
                        error = {
                            "error": f"'{tool_name}' is a SKILL, not a tool.",
                            "fix": (
                                f"Call the `load_skill` TOOL with name='{tool_name}'. "
                                f"Then follow the procedure that comes back."
                            ),
                        }
                        if verbose:
                            ui.console.print(
                                f"[yellow]  ! '{tool_name}' is a skill, not a tool "
                                f"— nudging model to call load_skill[/yellow]"
                            )
                    messages.append(Message(
                        role="tool", content=json.dumps(error), tool_call_id=call_id,
                    ))
                    continue

                import difflib
                suggestions = difflib.get_close_matches(
                    tool_name, self.registry.known_names(), n=3, cutoff=0.4
                )
                error = {
                    "error": f"Unknown tool: {tool_name}",
                    "available_tools": self.registry.known_names(),
                }
                if suggestions:
                    error["did_you_mean"] = suggestions
                    error["hint"] = (
                        f"'{tool_name}' does not exist. Did you mean one of: "
                        f"{suggestions}? Use the exact tool name from the list."
                    )
                if verbose:
                    suffix = f" (did you mean {suggestions}?)" if suggestions else ""
                    ui.console.print(
                        f"[yellow]  ! unknown tool: {tool_name}{suffix}[/yellow]"
                    )
                messages.append(Message(
                    role="tool", content=json.dumps(error), tool_call_id=call_id,
                ))
                continue

            decision = self.policy.check(spec, args)
            self.audit.record(
                event="tool_call",
                tool=tool_name,
                args=args,
                risk=spec.risk,
                policy_mode=self.policy.mode,
                allowed=decision.allowed,
                reason=decision.reason,
            )

            if not decision.allowed:
                if verbose:
                    ui.console.print(
                        f"[yellow]  ✗ blocked: {decision.reason}[/yellow]"
                    )
                messages.append(Message(
                    role="tool",
                    content=json.dumps({
                        "blocked": True,
                        "reason": decision.reason,
                        "hint": (
                            "This tool call was blocked by the safety policy. "
                            "If you need to accomplish this, consider an alternative "
                            "tool or ask the user for permission."
                        ),
                    }),
                    tool_call_id=call_id,
                ))
                continue

            # 7b. Run the tool.
            result = None
            try:
                result = self.registry.run(tool_name, args)
            except Exception as e:
                result = {
                    "error": f"{type(e).__name__}: {e}",
                    "hint": (
                        "You called this tool with incorrect arguments. "
                        "The SAME call with the SAME arguments will fail the SAME way. "
                        "Read the schema above and either fix the argument names or "
                        "call a different tool."
                    ),
                }

            self.audit.record(
                event="tool_result",
                tool=tool_name,
                ok=("error" not in result) if isinstance(result, dict) else True,
                result=result,
            )

            was_problem = (
                isinstance(result, dict)
                and ("error" in result or result.get("blocked"))
            )

            if verbose:
                preview = json.dumps(result, default=str)
                line = f"  ← {preview[:200]}"
                if was_problem:
                    ui.console.print(f"[yellow]{line}[/yellow]")
                else:
                    ui.console.print(f"[green]{line}[/green]")
            self.on_tool_result(tool_name, result)

            if not was_problem:
                summary = (
                    result.get("message")
                    if isinstance(result, dict) else None
                ) or f"Called {tool_name} successfully."
                successful_calls[fingerprint] = str(summary)

            messages.append(Message(
                role="tool",
                content=json.dumps(result, default=str),
                tool_call_id=call_id,
            ))

            # create_skill is terminal.
            if (
                tool_name == "create_skill"
                and isinstance(result, dict)
                and "created" in result
            ):
                return str(result.get("message", "Skill created."))

            if not was_problem:
                hint_for_this_step = (
                    f"You just successfully called `{tool_name}`. "
                    f"What is the NEXT step?\n"
                    f"- If the user's task is now complete, call `finish` "
                    f"with the final answer.\n"
                    f"- Otherwise, call the next required tool.\n"
                    f"Do NOT repeat the same tool call."
                )

        return (
            f"Stopped after {self.max_steps} steps without finishing. "
            "The task may be too complex for a single run. Try breaking it "
            "into smaller commands, or check the audit log for what happened."
        )

    def reset(self) -> None:
        """Forget the conversation. The next run() starts fresh."""
        self.messages = []