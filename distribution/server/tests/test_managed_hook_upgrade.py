import json
import shlex
import shutil
import subprocess
import sys
import threading
import tomllib
from argparse import Namespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

import pytest

from agents_memory_collab.automation_setup import plan
from agents_memory_collab.client import Remote, Replica
from agents_memory_collab.models import Failure
from agents_memory_collab.protocol import GENESIS, operation_digest
from agents_memory_collab.setup import host_config, install, write_private

LEGACY_OMP = '''// agents-memory managed adapter. Paths only; no credentials in this file.
import { spawn } from "node:child_process";

export default function (pi: any) {
  pi.on("before_agent_start", async (event: any, ctx: any) => {
    const result: any = await new Promise((resolve) => {
      const child = spawn(__PYTHON__, __ARGS__, { stdio: ["pipe", "pipe", "ignore"] });
      let output = "";
      let settled = false;
      const finish = (value: any) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        child.kill();
        resolve(value);
      };
      const timer = setTimeout(() => finish({ systemMessage: "agents-memory: automatic_memory_deferred" }), 2500);
      child.on("error", () => finish({ systemMessage: "agents-memory: automatic_memory_deferred" }));
      child.stdin.on("error", () => {});
      child.stdout.on("data", (data: Buffer) => {
        output += data.toString("utf8");
        if (Buffer.byteLength(output, "utf8") > 8192) finish({});
      });
      child.on("close", () => {
        try { finish(JSON.parse(output)); } catch { finish({}); }
      });
      child.stdin.end(JSON.stringify({ hook_event_name: "before_agent_start", prompt: event.prompt,
        session_id: ctx.sessionManager.getSessionId() }));
    });
    if (result.systemMessage) ctx.ui.notify(result.systemMessage, "warning");
    if (result.additionalContext) return { message: { customType: "agents-memory.context",
      content: result.additionalContext, display: false } };
  });
}
'''


@pytest.fixture
def service():
    token = "amc_synthetic_upgrade_device"
    user, installation, epoch = (str(uuid4()) for _ in range(3))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, value):
            raw = json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.headers.get("Authorization") != "Bearer " + token:
                return self.respond(401, {"error": "invalid_credential"})
            if self.path == "/v1/me":
                return self.respond(200, {"user_id": user, "installation_id": installation,
                    "epoch": epoch, "writable": True, "manage_keys": False,
                    "memory": {"ready": True, "contract": "agents-memory-grounded-v1", "origin_aware": True}})
            if self.path == "/v1/sync/changes?after=0":
                return self.respond(200, {"epoch": epoch, "anchor": GENESIS, "head": 0,
                                         "cursor": 0, "changes": []})
            return self.respond(404, {"error": "unexpected_upgrade_route"})

        def do_POST(self):
            value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path in {"/v1/recall", "/v1/session/context"}:
                return self.respond(200, {"memories": [{"id": "synthetic-context",
                    "text": "Synthetic upgraded project memory: preserve the selected account."}]})
            if self.path == "/v1/sync/ops":
                operation = value["operations"][0]
                if operation["text"] == "Synthetic discarded candidate":
                    return self.respond(200, {"epoch": epoch, "acked": [], "discarded": [{
                        "op_id": operation["op_id"], "digest": operation_digest(operation), "state": "discarded"}],
                        "reasons": {operation["op_id"]: "no_supported_memory"}})
                return self.respond(400, {"error": "synthetic_review_required"})
            return self.respond(404, {"error": "unexpected_upgrade_route"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield Remote(f"http://127.0.0.1:{server.server_port}", token)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def apply(entry):
    path, _, output = entry
    if output is not None:
        write_private(path, output)
    return path


def operation_history(replica):
    return {table: [tuple(row) for row in replica.db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
            for table in ("outbox", "operation_intents", "receipts", "recovery_archive")}


def invoke_installed_hook(host, project, tmp_path):
    prompt = "Synthetic new upgrade decision: keep the existing device credential."
    if host != "omp":
        path = project / (".claude/settings.local.json" if host == "claude" else ".codex/hooks.json")
        groups = json.loads(path.read_text())["hooks"]["UserPromptSubmit"]
        command = next(group["hooks"][0]["command"] for group in groups
                       if "agents_memory_collab.automation" in group["hooks"][0]["command"])
        result = subprocess.run(shlex.split(command), input=json.dumps({
            "hook_event_name": "UserPromptSubmit", "session_id": "synthetic-upgrade-session",
            "turn_id": "synthetic-upgrade-turn", "prompt": prompt}),
            text=True, capture_output=True, timeout=10, check=False)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
    bun = shutil.which("bun")
    if not bun:
        pytest.skip("Bun is required for the disposable installed OMP extension consumer")
    runner = tmp_path / "native-upgrade-consumer.ts"
    runner.write_text('''import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";
const handlers = new Map();
const adapter = (await import(pathToFileURL(process.argv[2]).href)).default;
adapter({ on(name, callback) { assert.ok(!handlers.has(name)); handlers.set(name, callback); } });
const ctx = { hasUI: false, sessionManager: { getSessionId: () => "synthetic-upgrade-session" } };
await handlers.get("session_start")({}, ctx);
await handlers.get("before_agent_start")({ prompt: process.argv[3] }, ctx);
await handlers.get("session_compact")({ prompt: "Synthetic summary is not a user turn" }, ctx);
await handlers.get("session_switch")({ reason: "resume", prompt: "Synthetic resume is not a user turn" }, ctx);
let result = await handlers.get("context")({ messages: [{ role: "user", content: "Synthetic question" }] }, ctx);
result = await handlers.get("context")(result, ctx);
const memories = result.messages.filter((message) => message.customType === "agents-memory.context");
assert.equal(memories.length, 1);
console.log(memories[0].content);
''')
    result = subprocess.run([bun, str(runner), str(project / ".omp/extensions/agents-memory-cloud.ts"), prompt],
                            text=True, capture_output=True, timeout=15, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("host, legacy_omp", [
    ("claude", False), ("codex", False), ("omp", True), ("omp", False),
    ("omp", "unbuffered_lifecycle"),
])
@pytest.mark.parametrize("capture_enabled", [True, False])
def test_old_managed_install_upgrades_launcher_and_invokes_current_capture_recall(
    service, tmp_path, monkeypatch, host, legacy_omp, capture_enabled,
):
    if host == "omp" and not shutil.which("bun"):
        pytest.skip("Bun is required for the disposable installed OMP extension consumer")
    home = tmp_path / "isolated-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("PYTHONPATH", raising=False)
    global_config = home / ".codex/config.toml"
    global_config.parent.mkdir()
    global_config.write_text('model = "synthetic-user-selected-model"\n')
    global_before = global_config.read_bytes()
    project = tmp_path / "consumer project"
    project.mkdir()
    root = tmp_path / "profiles"
    connection, state = root / "personal/connection.json", root / "personal/replica.sqlite"
    write_private(connection, json.dumps({"url": service.url, "token": service.token,
        "automatic_memory": capture_enabled, "automation_projects": {"app": [host]}}))
    connection_before = connection.read_bytes()
    replica = Replica(state, service)
    try:
        replica.connect()
        failed = replica.stage("app", "Synthetic failed candidate")
        discarded = replica.stage("app", "Synthetic discarded candidate")
        replica.cycle()
        assert replica.outcome(failed["op_id"])["state"] == "needs_review"
        assert replica.outcome(discarded["op_id"])["state"] == "discarded"
        original_history = operation_history(replica)
        replica.record_host_event("app", host, "before_agent_start" if host == "omp" else "UserPromptSubmit",
                                  capture_enabled=True, context_delivered=True, captured=True)
    finally:
        replica.close()
    old = tmp_path / "obsolete launcher"
    old.write_text("#!/bin/sh\necho obsolete_launcher_must_not_run >&2\nexit 97\n")
    old.chmod(0o700)
    current = tmp_path / "current launcher"
    current.write_text("#!/bin/sh\nexec " + shlex.quote(sys.executable) + ' "$@"\n')
    current.chmod(0o700)
    config = apply(host_config(host, project, connection, state, "app", python_launcher=old))
    if host == "codex":
        write_private(config, config.read_text().replace('"-I", ', '', 1))
    else:
        previous_config = json.loads(config.read_text())
        previous_config["mcpServers"]["agents-memory-cloud"]["args"].pop(0)
        write_private(config, json.dumps(previous_config))
    custom = {"hooks": [{"type": "command", "command": "echo synthetic-user-hook", "timeout": 7}]}
    if host == "omp":
        adapter = project / ".omp/extensions/agents-memory-cloud.ts"
        args = ["-m", "agents_memory_collab.automation", "--connection", str(connection),
                "--state", str(state), "--project", "app", "--host", host]
        if legacy_omp == "unbuffered_lifecycle":
            path = apply(plan(host, project, connection, state, "app", python_launcher=old))
            write_private(path, path.read_text()
                          .replace('    child.stdout.setEncoding("utf8");\n', '')
                          .replace('(data: string)', '(data: Buffer)')
                          .replace('output += data;', 'output += data.toString("utf8");'))
        elif legacy_omp:
            write_private(adapter, LEGACY_OMP.replace("__PYTHON__", json.dumps(str(old))).replace("__ARGS__", json.dumps(args)))
        else:
            path = apply(plan(host, project, connection, state, "app", python_launcher=old))
            write_private(path, path.read_text().replace('["-I", ', '['))
        custom_path = adapter.with_name("agents-memory.ts")
        custom_path.write_text("export default function () {}\n")
        custom_before = custom_path.read_bytes()
    else:
        adapter = apply(plan(host, project, connection, state, "app", python_launcher=old))
        document = json.loads(adapter.read_text())
        for groups in document["hooks"].values():
            for group in groups:
                group["hooks"][0]["command"] = group["hooks"][0]["command"].replace(" -I -m ", " -m ", 1)
        document["hooks"]["SessionStart"].insert(0, custom)
        document["hooks"]["SessionStart"].append(document["hooks"]["SessionStart"][1])
        document["userSetting"] = "preserve"
        write_private(adapter, json.dumps(document))
    args = Namespace(profile="personal", client=[host], root=root, project=project, project_name="app",
                     url=None, credential_file=None, device_name=None, python_launcher=current)
    first = install(args)
    assert not first["ready"]
    assert first["automation"]["native_trust"] == "unverified"
    assert first["automation"]["hosts"][host]["execution"] == "unverified"
    installed = {path: path.read_bytes() for path in (config, adapter)}
    second = install(args)
    assert not second["ready"]
    assert {path: path.read_bytes() for path in installed} == installed
    assert connection.read_bytes() == connection_before
    assert global_config.read_bytes() == global_before
    data = tomllib.loads(config.read_text()) if host == "codex" else json.loads(config.read_text())
    server = data["mcp_servers" if host == "codex" else "mcpServers"]["agents-memory-cloud"]
    assert server["command"] == str(current)
    if host == "omp":
        assert custom_path.read_bytes() == custom_before
    else:
        document = json.loads(adapter.read_text())
        assert document["userSetting"] == "preserve"
        assert document["hooks"]["SessionStart"] == [custom, document["hooks"]["UserPromptSubmit"][0]]
    replica = Replica(state, service)
    try:
        assert operation_history(replica) == original_history
    finally:
        replica.close()
    trap = project / "agents_memory_collab"
    trap.mkdir()
    marker = project / "cwd-module-executed"
    (trap / "__init__.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('executed')\n"
        "raise RuntimeError('malicious cwd package executed')\n")
    monkeypatch.chdir(project)
    control = subprocess.run([sys.executable, "-m", "agents_memory_collab.cli"],
                             text=True, capture_output=True, timeout=10, check=False)
    assert control.returncode != 0 and marker.read_text() == "executed"
    marker.unlink()
    registered = subprocess.run([server["command"], *server["args"], "--help"],
                                text=True, capture_output=True, timeout=10, check=False)
    assert registered.returncode == 0, registered.stderr
    assert "usage:" in registered.stdout
    assert not marker.exists()
    context = invoke_installed_hook(host, project, tmp_path)
    assert "Synthetic upgraded project memory" in context
    assert not marker.exists()
    replica = Replica(state, service)
    try:
        assert replica.outcome(failed["op_id"])["state"] == "needs_review"
        assert replica.outcome(discarded["op_id"])["state"] == "discarded"
        new_rows = replica.db.execute("SELECT body FROM outbox WHERE op_id != ?", (failed["op_id"],)).fetchall()
        assert len(new_rows) == int(capture_enabled)
        if capture_enabled:
            operation = json.loads(new_rows[0][0])
            assert operation["origin"] == "user_prompt"
            assert operation["project"] == "app"
            assert operation["session_id"] == "synthetic-upgrade-session"
            assert operation["text"] == "Synthetic new upgrade decision: keep the existing device credential."
        capture = replica.host_automation_status("app", [host], capture_enabled=capture_enabled)["hosts"][host]["capture"]
        assert capture == ("observed" if capture_enabled else "disabled")
        assert replica.db.execute("SELECT count(*) FROM recovery_archive").fetchone()[0] == 0
    finally:
        replica.close()
    assert connection.read_bytes() == connection_before
    assert global_config.read_bytes() == global_before


@pytest.mark.parametrize("change", ["custom_code", "different_profile", "different_project"])
def test_setup_preserves_unowned_omp_extension_before_contacting_service(tmp_path, change):
    project = tmp_path / "consumer"
    project.mkdir()
    root = tmp_path / "profiles"
    connection, state = root / "personal/connection.json", root / "personal/replica.sqlite"
    args = ["-m", "agents_memory_collab.automation", "--connection", str(connection),
            "--state", str(state), "--project", "app", "--host", "omp"]
    if change == "different_profile":
        args[3] = str(tmp_path / "other-connection.json")
    if change == "different_project":
        args[7] = "another-app"
    content = LEGACY_OMP.replace("__PYTHON__", json.dumps(sys.executable)).replace("__ARGS__", json.dumps(args))
    if change == "custom_code":
        content += "\nexport const userCustomization = true;\n"
    adapter = project / ".omp/extensions/agents-memory-cloud.ts"
    write_private(adapter, content)
    before = adapter.read_bytes()
    with pytest.raises(Failure) as error:
        install(Namespace(profile="personal", client=["omp"], root=root, project=project,
                          project_name="app", url=None, credential_file=None, device_name=None))
    assert error.value.code == "existing_omp_automation_differs"
    assert adapter.read_bytes() == before
    assert not connection.exists() and not state.exists()
    assert not (project / ".omp/mcp.json").exists()


@pytest.mark.parametrize("host", ["claude", "codex"])
def test_upgrade_preserves_custom_hook_groups_and_other_profile_commands(tmp_path, host):
    connection, state = tmp_path / "connection.json", tmp_path / "replica.sqlite"
    previous = Path("/synthetic/obsolete/python")
    path, _, output = plan(host, tmp_path, connection, state, "app", python_launcher=previous)
    document = json.loads(output)
    owned = document["hooks"]["UserPromptSubmit"][0]
    customized = {"hooks": [dict(owned["hooks"][0], timeout=9)]}
    mixed = {"hooks": [owned["hooks"][0], {"type": "command", "command": "echo custom"}]}
    other = json.loads(json.dumps(owned))
    other["hooks"][0]["command"] += " --synthetic-user-flag"
    document["hooks"]["UserPromptSubmit"] = [customized, mixed, other, owned, owned]
    write_private(path, json.dumps(document))
    apply(plan(host, tmp_path, connection, state, "app"))
    groups = json.loads(path.read_text())["hooks"]["UserPromptSubmit"]
    assert groups[:3] == [customized, mixed, other]
    assert len(groups) == 4
    assert shlex.split(groups[3]["hooks"][0]["command"])[0] == sys.executable
    assert plan(host, tmp_path, connection, state, "app")[2] is None


@pytest.mark.parametrize("host", ["claude", "codex", "omp"])
def test_launcher_upgrade_preserves_custom_mcp_entry(tmp_path, host):
    old, current = tmp_path / "old-python", tmp_path / "new-python"
    for path in (old, current):
        path.write_text("#!/bin/sh\nexit 97\n")
        path.chmod(0o700)
    connection, state = tmp_path / "connection.json", tmp_path / "replica.sqlite"
    path = apply(host_config(host, tmp_path, connection, state, "app", python_launcher=old))
    if host == "codex":
        write_private(path, path.read_text() + 'env = { SYNTHETIC_USER_SETTING = "preserve" }\n')
    else:
        document = json.loads(path.read_text())
        document["mcpServers"]["agents-memory-cloud"]["env"] = {"SYNTHETIC_USER_SETTING": "preserve"}
        write_private(path, json.dumps(document))
    before = path.read_bytes()
    with pytest.raises(Failure) as error:
        host_config(host, tmp_path, connection, state, "app", python_launcher=current)
    assert error.value.code == "existing_mcp_config_differs"
    assert path.read_bytes() == before


def test_omp_preserves_a_character_split_between_hook_stdout_chunks(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node 24+ is required for the controlled UTF-8 stream boundary")
    version = subprocess.run(
        [node, "--version"], text=True, capture_output=True, check=True,
    ).stdout
    if int(version.removeprefix("v").split(".")[0]) < 24:
        pytest.skip("Node 24+ is required for the controlled UTF-8 stream boundary")
    adapter = apply(plan(
        "omp", tmp_path / "consumer", tmp_path / "connection.json",
        tmp_path / "replica.sqlite", "app",
    ))
    runner = tmp_path / "split-utf8-consumer.mts"
    runner.write_text('''import assert from "node:assert/strict";
import childProcess from "node:child_process";
import { syncBuiltinESMExports } from "node:module";
import { EventEmitter } from "node:events";
import { PassThrough, Writable } from "node:stream";
import { pathToFileURL } from "node:url";
const expected = "한글 백업은 29일 보관하지만 법적 보존 명령이 끝날 때까지 삭제하지 않는다.";
const raw = Buffer.from(JSON.stringify({ additionalContext: expected }), "utf8");
const cut = raw.indexOf(Buffer.from("한", "utf8")) + 1;
childProcess.spawn = () => {
  const child = new EventEmitter();
  child.stdout = new PassThrough();
  child.kill = () => true;
  child.stdin = new Writable({
    write(_chunk, _encoding, done) { done(); },
    final(done) {
      queueMicrotask(() => {
        child.stdout.once("end", () => child.emit("close", 0));
        child.stdout.write(raw.subarray(0, cut));
        child.stdout.end(raw.subarray(cut));
      });
      done();
    },
  });
  return child;
};
syncBuiltinESMExports();
const handlers = new Map();
(await import(pathToFileURL(process.argv[2]).href)).default({
  on(name, handler) { handlers.set(name, handler); },
});
const ctx = { hasUI: false, sessionManager: { getSessionId: () => "split-utf8-session" } };
await handlers.get("session_start")({}, ctx);
const result = await handlers.get("context")({ messages: [] }, ctx);
assert.deepEqual(
  result.messages.map((message) => [message.customType, message.content]),
  [["agents-memory.context", expected]],
);
''')
    result = subprocess.run(
        [node, str(runner), str(adapter)],
        text=True, capture_output=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stderr
