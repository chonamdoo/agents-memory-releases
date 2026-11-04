"""Native database ownership and first-install behavior; actual SQL is covered by release E2E."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

pytest_plugins = ["test_mcp_local_setup"]


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
    assert responses[3]["structuredContent"]["ready"] is False
    assert responses[4]["isError"] is True
    assert not (home / ".local/share/agents-memory-hindsight").exists()
