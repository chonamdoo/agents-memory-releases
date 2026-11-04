"""Native database ownership and first-install behavior; actual SQL is covered by release E2E."""
import hashlib
import json
import os
import subprocess
import tarfile
from pathlib import Path

import pytest

pytest_plugins = ["test_mcp_local_setup"]


@pytest.fixture
def legacy_mac_runtime(helper, installation, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    with tarfile.open(root / "distribution/mcp-local/assets/pgvector-0.8.7-darwin-arm64.tar.gz") as source:
        module = source.extractfile("lib/vector.so").read()
    directory = installation / "database" / helper.NATIVE_VERSION
    files = {}
    for name in ("bin/postgres", "bin/initdb", "bin/pg_ctl", "bin/psql", "lib/vector.so",
                 "share/extension/vector.control", "share/extension/vector--0.8.7.sql"):
        data = module if name == "lib/vector.so" else ("unchanged-fixture:" + name).encode()
        helper.write_private(directory / name, data)
        files[name] = hashlib.sha256(data).hexdigest()
    helper.write_json(directory / "RUNTIME.json", {"version": helper.NATIVE_VERSION,
                     "product_id": "a" * 32, "files": files})
    helper.write_private(installation / "database/data/PG_VERSION", b"18\n")
    helper.write_private(installation / "database/data/sentinel", b"existing-database-content")
    helper.write_json(installation / "settings/jev-credential.json", {"schema_version": 1, "api_key": "synthetic-kept-key"})
    helper.write_json(installation / "settings/mcp-database.json", {"mode": "native", "runtime_version": helper.NATIVE_VERSION,
                     "product_id": "a" * 32, "url": "postgresql://am_local:synthetic-secret@127.0.0.1:54321/am_hindsight_local"})
    monkeypatch.setattr(helper.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(helper.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(helper.platform, "mac_ver", lambda: ("15.7", (), "arm64"))
    monkeypatch.setattr(helper, "run", lambda *args, **kwargs: pytest.fail("Repair downloaded or executed another runtime"))
    return directory, module


@pytest.mark.parametrize("previous_action", ["none", "copied", "renamed", "relative_link", "absolute_link", "recorded_link"])
def test_legacy_mac_repair_keeps_database_keys_and_profile(helper, installation, legacy_mac_runtime, previous_action):
    directory, module = legacy_mac_runtime
    if previous_action in {"copied", "renamed"}:
        helper.write_private(directory / "lib/vector.dylib", module)
    if previous_action == "renamed":
        (directory / "lib/vector.so").unlink()
    if previous_action in {"relative_link", "recorded_link"}:
        (directory / "lib/vector.dylib").symlink_to("vector.so")
    if previous_action == "absolute_link":
        (directory / "lib/vector.dylib").symlink_to(directory / "lib/vector.so")
    if previous_action == "recorded_link":
        receipt = helper.read_json(directory / "RUNTIME.json")
        receipt["files"]["lib/vector.dylib"] = receipt["files"].pop("lib/vector.so")
        helper.write_json(directory / "RUNTIME.json", receipt)
    protected = [installation / "settings/profile.json", installation / "settings/jev-credential.json",
                 installation / "settings/mcp-database.json", installation / "database/data/PG_VERSION",
                 installation / "database/data/sentinel"]
    before = {path: path.read_bytes() for path in protected}
    assert helper.native_runtime(installation) == directory
    assert (directory / "lib/vector.dylib").read_bytes() == module
    assert not (directory / "lib/vector.dylib").is_symlink()
    receipt = helper.read_json(directory / "RUNTIME.json")
    assert receipt["files"]["lib/vector.dylib"] == helper.LEGACY_DARWIN_VECTOR_SHA256
    assert "lib/vector.so" not in receipt["files"]
    saved = (directory / "RUNTIME.json").read_bytes()
    helper.native_runtime(installation)
    assert (directory / "RUNTIME.json").read_bytes() == saved
    assert {path: path.read_bytes() for path in protected} == before


@pytest.mark.parametrize("conflict", ["different_bytes", "outside_link", "dangling_link"])
def test_mac_repair_preserves_unknown_destination(helper, installation, legacy_mac_runtime, conflict):
    directory, _ = legacy_mac_runtime
    destination = directory / "lib/vector.dylib"
    if conflict == "outside_link":
        outside = installation.parent / "outside-vector.so"
        outside.write_bytes((directory / "lib/vector.so").read_bytes())
        destination.symlink_to(outside)
    elif conflict == "dangling_link":
        destination.symlink_to("missing-vector.so")
    else:
        helper.write_private(destination, b"unrelated-module")
    before = (directory / "RUNTIME.json").read_bytes()
    with pytest.raises(helper.Refused, match="no file was replaced"):
        helper.native_runtime(installation)
    assert (directory / "RUNTIME.json").read_bytes() == before
    assert destination.is_symlink() if conflict.endswith("link") else destination.read_bytes() == b"unrelated-module"


def test_verified_vector_link_is_replaced_atomically(helper, installation, legacy_mac_runtime, monkeypatch):
    directory, module = legacy_mac_runtime
    destination = directory / "lib/vector.dylib"
    destination.symlink_to("vector.so")
    source = directory / "lib/vector.so"
    before = source.stat()
    original = helper.os.replace
    replacements = []

    def observe(source_path, destination_path):
        if Path(destination_path) == destination:
            assert destination.is_symlink()
            assert Path(source_path).read_bytes() == module
            replacements.append(True)
        return original(source_path, destination_path)

    monkeypatch.setattr(helper.os, "replace", observe)
    helper.native_runtime(installation)
    assert replacements == [True]
    assert not destination.is_symlink() and destination.read_bytes() == module
    assert source.stat().st_ino == before.st_ino and source.read_bytes() == module


def test_link_repair_recovers_after_receipt_write_interruption(helper, installation, legacy_mac_runtime, monkeypatch):
    directory, module = legacy_mac_runtime
    destination = directory / "lib/vector.dylib"
    destination.symlink_to("vector.so")
    original = helper.write_json

    def interrupt(path, data):
        if path == directory / "RUNTIME.json":
            raise OSError("synthetic interrupted receipt")
        return original(path, data)

    monkeypatch.setattr(helper, "write_json", interrupt)
    with pytest.raises(OSError, match="interrupted"):
        helper.native_runtime(installation)
    assert not destination.is_symlink() and destination.read_bytes() == module
    monkeypatch.setattr(helper, "write_json", original)
    helper.native_runtime(installation)
    assert "lib/vector.dylib" in helper.read_json(directory / "RUNTIME.json")["files"]


def test_mac_repair_recovers_after_receipt_write_interruption(helper, installation, legacy_mac_runtime, monkeypatch):
    directory, module = legacy_mac_runtime
    original = helper.write_json

    def interrupt(path, data):
        if path == directory / "RUNTIME.json":
            raise OSError("synthetic interrupted write")
        return original(path, data)

    monkeypatch.setattr(helper, "write_json", interrupt)
    with pytest.raises(OSError, match="interrupted"):
        helper.native_runtime(installation)
    assert (directory / "lib/vector.dylib").read_bytes() == module
    monkeypatch.setattr(helper, "write_json", original)
    helper.native_runtime(installation)
    assert "lib/vector.dylib" in helper.read_json(directory / "RUNTIME.json")["files"]


def test_mac_repair_does_not_run_after_other_runtime_tampering(helper, installation, legacy_mac_runtime):
    directory, _ = legacy_mac_runtime
    (directory / "bin/postgres").write_bytes(b"changed-postgres")
    before = (directory / "RUNTIME.json").read_bytes()
    with pytest.raises(helper.Refused, match="runtime changed"):
        helper.native_runtime(installation)
    assert not (directory / "lib/vector.dylib").exists()
    assert (directory / "RUNTIME.json").read_bytes() == before


def test_fresh_database_defaults_to_native_without_consulting_docker(helper, installation, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(helper.shutil, "which", lambda *args: pytest.fail("Docker/system executable lookup"))
    observed = []

    def prepare(prefix, state, *, provision):
        observed.append(state)
        assert provision
        return state["url"]

    monkeypatch.setattr(helper, "native_database", prepare)
    url = helper.ensure_database(installation, provision=True)
    state = helper.read_json(installation / "settings/mcp-database.json")
    assert observed == [state] and state["mode"] == "native"
    assert state["product_id"] == "a" * 32 and "docker_endpoint" not in state
    assert "127.0.0.1" in url and "am_hindsight_local" in url
    assert (installation / "settings/mcp-database.json").stat().st_mode & 0o777 == 0o600


def test_foreign_native_database_is_preserved(helper, installation, monkeypatch):
    path = installation / "settings/mcp-database.json"
    helper.write_json(path, {"mode": "native", "product_id": "b" * 32})
    before = path.read_bytes()
    monkeypatch.setattr(helper, "native_database", lambda *args, **kwargs: pytest.fail("Foreign DB touched"))
    with pytest.raises(helper.Refused, match="identity"):
        helper.ensure_database(installation, provision=True)
    assert path.read_bytes() == before
    with pytest.raises(helper.Refused, match="identity"):
        helper.stop_native_database(installation)


def test_mac_minimum_is_checked_before_download(helper, installation, monkeypatch):
    monkeypatch.setattr(helper.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(helper.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(helper.platform, "mac_ver", lambda: ("14.7.1", (), "arm64"))
    monkeypatch.setattr(helper, "run", lambda *args, **kwargs: pytest.fail("Download before OS check"))
    with pytest.raises(helper.Refused, match="macOS 15"):
        helper.native_runtime(installation)


def test_changed_native_runtime_is_not_executed_or_replaced(helper, installation, monkeypatch):
    directory = installation / "database" / helper.NATIVE_VERSION
    binary = directory / "bin/postgres"
    helper.write_private(binary, b"trusted-fixture")
    helper.write_json(directory / "RUNTIME.json", {"product_id": "a" * 32,
                      "version": helper.NATIVE_VERSION,
                      "files": {"bin/postgres": hashlib.sha256(b"trusted-fixture").hexdigest()}})
    binary.write_bytes(b"changed-fixture")
    monkeypatch.setattr(helper, "run", lambda *args, **kwargs: pytest.fail("Changed runtime executed"))
    with pytest.raises(helper.Refused, match="runtime changed"):
        helper.native_runtime(installation)
    assert binary.read_bytes() == b"changed-fixture"


def test_native_database_will_not_adopt_existing_unmarked_data(helper, installation, monkeypatch):
    data = installation / "database/data"
    data.mkdir(parents=True, mode=0o700)
    sentinel = data / "do-not-adopt"
    sentinel.write_text("existing")
    state = {"runtime_version": helper.NATIVE_VERSION, "port": 54321,
             "url": "postgresql://am_local:" + "x" * 32 + "@127.0.0.1:54321/am_hindsight_local"}
    monkeypatch.setattr(helper, "native_runtime", lambda *args: pytest.fail("Unmarked data adopted"))
    with pytest.raises(helper.Refused, match="ownership marker"):
        helper.native_database(installation, state, provision=True)
    assert sentinel.read_text() == "existing"


def test_pinned_native_artifacts_match_their_record(helper):
    root = Path(__file__).resolve().parents[2]
    for name, expected in helper.NATIVE_VECTOR.values():
        assert hashlib.sha256((root / "distribution/mcp-local/assets" / name).read_bytes()).hexdigest() == expected


def test_existing_project_ports_are_never_changed(helper, installation, monkeypatch):
    helper.write_json(installation / "settings/mcp-projects.json", {"kept": {}})
    before = (installation / "settings/profile.json").read_bytes()
    monkeypatch.setattr(helper, "available_port", lambda: pytest.fail("Existing ports moved"))
    helper.initial_service_ports(installation)
    assert (installation / "settings/profile.json").read_bytes() == before


def test_tool_schema_matches_the_compiled_plain_text_profile(helper):
    schema = {"type": "object", "properties": {key: {"type": "string"} for key in
              ("content", "context", "timestamp", "tags", "metadata", "document_id", "strategy")},
              "required": ["content"], "additionalProperties": False}
    result = helper.admission_tool_schema(schema)
    assert set(result["properties"]) == {"content", "timestamp", "tags"}
    assert helper.admission_arguments_valid({"content": "plain text"})
    assert not helper.admission_arguments_valid({"content": "plain text", "context": "unsupported"})
    assert not helper.admission_arguments_valid({"content": "plain text", "document_id": "unsupported"})


def test_current_connector_has_stable_tools_and_honest_readiness_without_runtime(tmp_path):
    root = Path(__file__).resolve().parents[2]
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "setup_status"}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "recall", "arguments": {"query": "synthetic"}}},
    ]
    result = subprocess.run([str(root / "plugins/agents-memory-local/bin/connector-linux-x86_64"),
        "--project", str(home), "--helper", str(root / "distribution/mcp-local/setup.py")],
        env=dict(os.environ, HOME=str(home), XDG_CACHE_HOME=str(home / "cache")),
        input="\n".join(json.dumps(r) for r in requests) + "\n", text=True, capture_output=True, timeout=5, check=True)
    responses = {r["id"]: r["result"] for r in map(json.loads, result.stdout.splitlines())}
    names = [tool["name"] for tool in responses[2]["tools"]]
    assert len(names) == len(set(names)) == 10
    assert "Before your first substantive answer" in responses[1]["instructions"]
    recall = next(tool for tool in responses[2]["tools"] if tool["name"] == "recall")
    assert "without waiting" in recall["description"]
    assert responses[3]["structuredContent"]["ready"] is False
    logs = responses[3]["structuredContent"]["logs"]
    assert set(logs) == {"setup", "operations", "postgres", "service"}
    assert all("credential" not in path for path in logs.values())
    scope = responses[3]["structuredContent"]["memory_scope"]
    assert scope["authority"] == "agents-memory-hindsight-local" and scope["project"] == str(home)
    assert responses[4]["isError"] is True
    assert not (home / ".local/share/agents-memory-hindsight").exists()


def test_omp_existing_generated_instruction_disable_is_migrated(helper, installation, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    helper.configure_client(project, installation, "omp")
    path = project / ".omp/mcp.json"
    data = json.loads(path.read_text())
    data["mcpServers"][helper.NAME]["instructions"] = False
    helper.write_json(path, data)
    assert helper.configure_client(project, installation, "omp")["changed"]
    assert json.loads(path.read_text())["mcpServers"][helper.NAME]["instructions"] is True
    assert not helper.configure_client(project, installation, "omp")["changed"]


def test_omp_custom_instruction_text_is_preserved(helper, installation, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    helper.configure_client(project, installation, "omp")
    path = project / ".omp/mcp.json"
    data = json.loads(path.read_text())
    data["mcpServers"][helper.NAME]["instructions"] = "Keep my custom instructions"
    helper.write_json(path, data)
    before = path.read_bytes()
    assert not helper.configure_client(project, installation, "omp")["changed"]
    assert path.read_bytes() == before
