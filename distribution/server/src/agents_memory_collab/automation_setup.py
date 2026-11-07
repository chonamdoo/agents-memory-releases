"""Plan host event integration without touching live user configuration."""
import hashlib
import json
import shlex
import sys
from pathlib import Path

from .models import Failure


def host_capabilities(host):
    if host not in {"claude", "codex", "omp"}:
        raise ValueError("Unsupported host")
    events = (["before_agent_start", "session_start", "session_switch", "session_compact", "context"]
              if host == "omp" else ["SessionStart", "UserPromptSubmit"])
    return {"events": events,
            "recall_after_compaction": "context" if host == "omp" else "SessionStart",
            "recall_on_resume": "session_switch" if host == "omp" else "SessionStart",
            "prompt_channel_verified": True, "human_origin_verified": False,
            "prompt_channel": "before_agent_start" if host == "omp" else "UserPromptSubmit",
            "prompt_channel_notes": ("Also receives scheduled tasks, subagent reports, and cross-session messages."
                                     if host == "claude" else "Host prompt channel is not human-origin attestation."),
            "trust": "user_review_required", "model_compliance": "unverified"}


def _read(path):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise Failure(400, "unsafe_automation_path")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise Failure(400, "unsafe_automation_path")
    return path.read_text() if path.exists() else ""


def _managed_command(command, args):
    if not isinstance(command, str):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    return (bool(words) and Path(words[0]).is_absolute()
            and words[1:] in (args, args[1:]) and shlex.join(words) == command)


def _managed_omp(raw, template, args):
    marker = "const child = spawn("
    if raw.count(marker) != 1:
        return False
    start = raw.index(marker) + len(marker)
    decoder = json.JSONDecoder()
    try:
        command, command_end = decoder.raw_decode(raw, start)
        if raw[command_end:command_end + 2] != ", ":
            return False
        previous_args, end = decoder.raw_decode(raw, command_end + 2)
    except ValueError:
        return False
    if not isinstance(command, str) or not Path(command).is_absolute() or previous_args not in (args, args[1:]):
        return False
    normalized = raw[:start] + "__PYTHON__, __ARGS__" + raw[end:]
    # Only complete known SDK templates prove ownership, not their header.
    return (normalized == template or hashlib.sha256(normalized.encode()).hexdigest() in {
        "35df372587f63ac7b8732916584b850dbfac463e2f90b4851c2b3928ca0ac19a",
        "145833714aaeb4d7726f4bea4883b780567c717c18fdb44e36017d1f14e64f51",
    })


def plan(host, project, connection, state, project_name, *, python_launcher=None):
    host_capabilities(host)
    python = str(python_launcher) if python_launcher else sys.executable
    args = ["-I", "-m", "agents_memory_collab.automation", "--connection", str(connection),
            "--state", str(state), "--project", project_name, "--host", host]
    if host in {"claude", "codex"}:
        path = project / (".claude/settings.local.json" if host == "claude" else ".codex/hooks.json")
        raw = _read(path)
        document = json.loads(raw or "{}")
        hooks = document.setdefault("hooks", {})
        for event in ("SessionStart", "UserPromptSubmit"):
            command = {"type": "command", "command": shlex.join([python, *args]), "timeout": 3}
            group = {"hooks": [command]}
            entries = hooks.setdefault(event, [])
            if not isinstance(entries, list):
                raise Failure(400, "invalid_automation_config")
            updated = []
            installed = False
            for existing in entries:
                handlers = existing.get("hooks") if isinstance(existing, dict) else None
                handler = handlers[0] if isinstance(handlers, list) and len(handlers) == 1 else None
                owned = (isinstance(handler, dict) and set(existing) == {"hooks"}
                         and set(handler) == {"type", "command", "timeout"}
                         and handler["type"] == "command" and handler["timeout"] == 3
                         and _managed_command(handler["command"], args))
                if owned:
                    if not installed:
                        updated.append(group)
                        installed = True
                else:
                    updated.append(existing)
            if not installed:
                updated.append(group)
            hooks[event] = updated
        output = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        return path, raw, None if output == raw else output
    path = project / ".omp/extensions/agents-memory-cloud.ts"
    raw = _read(path)
    template = Path(__file__).with_name("omp_memory.ts").read_text()
    output = template.replace("__PYTHON__", json.dumps(python)).replace("__ARGS__", json.dumps(args))
    if raw and raw != output and not _managed_omp(raw, template, args):
        raise Failure(409, "existing_omp_automation_differs")
    return path, raw, None if output == raw else output
