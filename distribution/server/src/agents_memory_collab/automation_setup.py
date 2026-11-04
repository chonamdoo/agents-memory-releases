"""Plan host event integration without touching live user configuration."""
import json
import shlex
import sys
from pathlib import Path

from .models import Failure


def _read(path):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise Failure(400, "unsafe_automation_path")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise Failure(400, "unsafe_automation_path")
    return path.read_text() if path.exists() else ""


def plan(host, project, connection, state, project_name):
    args = ["-m", "agents_memory_collab.automation", "--connection", str(connection),
            "--state", str(state), "--project", project_name, "--host", host]
    if host in {"claude", "codex"}:
        path = project / (".claude/settings.local.json" if host == "claude" else ".codex/hooks.json")
        raw = _read(path)
        document = json.loads(raw or "{}")
        hooks = document.setdefault("hooks", {})
        for event in ("SessionStart", "UserPromptSubmit"):
            command = {"type": "command", "command": shlex.join([sys.executable, *args]), "timeout": 3}
            group = {"hooks": [command]}
            entries = hooks.setdefault(event, [])
            if not isinstance(entries, list):
                raise Failure(400, "invalid_automation_config")
            if group not in entries:
                entries.append(group)
        output = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        return path, raw, None if output == raw else output
    path = project / ".omp/extensions/agents-memory-cloud.ts"
    raw = _read(path)
    template = Path(__file__).with_name("omp_memory.ts").read_text()
    output = template.replace("__PYTHON__", json.dumps(sys.executable)).replace("__ARGS__", json.dumps(args))
    if raw and raw != output:
        raise Failure(409, "existing_omp_automation_differs")
    return path, raw, None if output == raw else output
