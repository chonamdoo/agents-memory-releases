"""Distribution invariants using synthetic configuration, never real account histories."""
import argparse
import hashlib
import importlib.util
import json
import os
import plistlib
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "distribution/mcp-local/setup.py"


@pytest.fixture
def helper():
    spec = importlib.util.spec_from_file_location("mcp_setup_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installation(helper, tmp_path):
    prefix = tmp_path / "private installation"
    prefix.mkdir(mode=0o700)
    identity = "a" * 32
    helper.write_json(prefix / "PRODUCT.json", {"product": helper.PRODUCT, "id": identity})
    install = prefix / "installs/test-owned"
    helper.write_json(install / "payload/MANIFEST.json", {"version": "1.0.2"})
    helper.write_json(install / "READY.json", {"product_id": identity, "install_id": install.name,
                                              "version": "1.0.2", "manifest_sha256": hashlib.sha256(
                                                  (install / "payload/MANIFEST.json").read_bytes()).hexdigest()})
    (prefix / "current").symlink_to("installs/test-owned")
    helper.write_json(prefix / "settings/profile.json", {"provider": "local-llm", "model": "gpt-6.1-terra",
                                                        "subscription_host": "codex", "api_port": 18250})
    return prefix


@pytest.mark.parametrize("client", ["claude", "codex", "omp"])
def test_project_registration_preserves_other_servers_and_is_idempotent(helper, installation, tmp_path, client):
    project = tmp_path / 'project with "quotes" and emoji 🧠'
    project.mkdir()
    path = {"claude": project / ".mcp.json", "codex": project / ".codex/config.toml",
            "omp": project / ".omp/mcp.json"}[client]
    path.parent.mkdir(parents=True, exist_ok=True)
    original = ('# keep my comment\nmodel = "keep-this-model"\n[mcp_servers.other]\ncommand = "existing"\n'
                if client == "codex" else json.dumps({"other_setting": "keep", "mcpServers": {
                    "other": {"command": "existing"}}}))
    path.write_text(original)
    first = helper.configure_client(project, installation, client)
    assert first["changed"]
    if client == "codex":
        data = helper.tomllib.loads(path.read_text())
        assert "# keep my comment" in path.read_text() and data["model"] == "keep-this-model"
        servers = data["mcp_servers"]
    else:
        data = json.loads(path.read_text())
        assert data["other_setting"] == "keep"
        servers = data["mcpServers"]
    assert servers["other"] == {"command": "existing"}
    assert servers[helper.NAME]["args"] == ["proxy", "--project", str(project)]
    before = path.read_bytes()
    assert not helper.configure_client(project, installation, client)["changed"]
    assert path.read_bytes() == before
    backups = list(path.parent.glob(path.name + ".am-backup-*"))
    assert len(backups) == 1 and backups[0].read_text() == original
    assert path.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("client", ["claude", "codex", "omp"])
def test_conflicting_server_never_overwritten(helper, installation, tmp_path, client):
    project = tmp_path / "project"
    project.mkdir()
    helper.configure_client(project, installation, client)
    path = {"claude": project / ".mcp.json", "codex": project / ".codex/config.toml",
            "omp": project / ".omp/mcp.json"}[client]
    path.write_text(path.read_text().replace(str(installation), str(tmp_path / "other installation")))
    before = path.read_bytes()
    with pytest.raises(helper.Refused):
        helper.configure_client(project, installation, client)
    assert path.read_bytes() == before


def test_explicit_omp_disable_is_respected(helper, installation, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    path = project / ".omp/mcp.json"
    helper.write_json(path, {"mcpServers": {}, "disabledServers": [helper.NAME]})
    before = path.read_bytes()
    with pytest.raises(helper.Refused, match="disabled"):
        helper.configure_client(project, installation, "omp")
    assert path.read_bytes() == before


@pytest.mark.parametrize("component", ["file", "directory"])
def test_registration_refuses_symlinks(helper, installation, tmp_path, component):
    project = tmp_path / "project"
    project.mkdir()
    target = tmp_path / "foreign"
    target.mkdir()
    if component == "directory":
        (project / ".omp").symlink_to(target)
    else:
        (project / ".omp").mkdir()
        helper.write_json(target / "config.json", {"do_not_touch": True})
        (project / ".omp/mcp.json").symlink_to(target / "config.json")
    with pytest.raises(helper.Refused, match="Symbolic"):
        helper.configure_client(project, installation, "omp")


def test_broken_json_is_not_replaced(helper, installation, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / ".mcp.json").write_text("{broken")
    with pytest.raises(json.JSONDecodeError):
        helper.configure_client(project, installation, "claude")
    assert (project / ".mcp.json").read_text() == "{broken"


def test_client_choice_does_not_change_judge_or_key(helper, installation, tmp_path):
    key = installation / "settings/jev-credential.json"
    helper.write_json(key, {"api_key": "synthetic-kept-key"})
    profile = installation / "settings/profile.json"
    before = profile.read_bytes(), key.read_bytes()
    args = argparse.Namespace(prefix=installation, bundle=None, provider=None, judge_host=None,
                              model=None, executable=None, client=["omp"])
    helper.install_core(args)
    assert (profile.read_bytes(), key.read_bytes()) == before
    args.provider = "jev"
    with pytest.raises(helper.Refused, match="preserved"):
        helper.install_core(args)
    assert (profile.read_bytes(), key.read_bytes()) == before


@pytest.mark.parametrize("system,machine,release,expected", [
    ("Linux", "x86_64", "6.6.87.2-microsoft-standard-WSL2", True),
    ("Linux", "x86_64", "5.15.167.4-microsoft-standard-WSL2", True),
    ("Linux", "x86_64", "4.4.0-19041-Microsoft", False),
    ("Linux", "aarch64", "6.6.87.2-microsoft-standard-WSL2", False),
    ("Linux", "x86_64", "6.12.0-generic", False),
    ("Windows", "AMD64", "11", False),
])
def test_windows_support_requires_actual_wsl2_x64_kernel(helper, monkeypatch, system, machine, release, expected):
    monkeypatch.setattr(helper.platform, "system", lambda: system)
    monkeypatch.setattr(helper.platform, "machine", lambda: machine)
    monkeypatch.setattr(helper.platform, "release", lambda: release)
    monkeypatch.setenv("WSL_INTEROP", "/not-evidence-of-wsl2")
    assert helper.is_wsl2() is expected


def test_wsl_setup_reaches_install_without_virtual_no_start_flags(helper, tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(helper, "is_wsl2", lambda: True)
    monkeypatch.setattr(helper.platform, "system", lambda: "Linux")

    def reached(args):
        assert not args.virtual_linux and not args.no_start
        raise RuntimeError("reached supported WSL setup")

    monkeypatch.setattr(helper, "install_core", reached)
    args = helper.parser().parse_args(["setup", "--project", str(project), "--client", "codex"])
    with pytest.raises(RuntimeError, match="reached supported WSL"):
        helper.setup(args)


def test_wsl_installs_immutable_linux_core_without_requiring_virtual_user_flag(helper, tmp_path, monkeypatch):
    monkeypatch.setattr(helper, "is_wsl2", lambda: True)
    monkeypatch.setattr(helper.threading.Thread, "start", lambda self: None)
    monkeypatch.setattr(helper.threading.Thread, "join", lambda self, **kwargs: None)

    def run(command, **kwargs):
        assert "--virtual-linux" in command
        assert str(tmp_path / "bundle/installer.py") in command
        raise RuntimeError("verified Linux core route")

    monkeypatch.setattr(helper.subprocess, "run", run)
    args = argparse.Namespace(prefix=tmp_path / "runtime", bundle=tmp_path / "bundle", provider="jev",
                              judge_host=None, model=None, executable=None, virtual_linux=False)
    with pytest.raises(RuntimeError, match="verified Linux core"):
        helper.install_core(args)


def test_wsl_service_start_is_private_and_uses_exact_owned_helper(helper, installation, monkeypatch):
    calls = []
    readiness = iter([False, False, True])
    monkeypatch.setattr(helper, "ready", lambda prefix: next(readiness))
    monkeypatch.setattr(helper.time, "sleep", lambda delay: None)
    monkeypatch.setattr(helper, "wait_service_ports", lambda prefix: None)

    def spawn(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr(helper.subprocess, "Popen", spawn)
    helper.start_process_agent(installation)
    command, kwargs = calls[0]
    assert command == [str(installation / "current/venv/bin/python"), "-I",
                       str(installation / "integration/current/setup.py"), "--prefix", str(installation), "service-run"]
    assert kwargs["start_new_session"] and kwargs["stdin"] == helper.subprocess.DEVNULL
    assert helper.read_json(installation / "settings/mcp-service.json")["enabled"] is True
    assert (installation / "integration/logs/service.log").stat().st_mode & 0o777 == 0o600


def test_wsl_service_does_not_replace_unowned_live_api(helper, installation, monkeypatch):
    monkeypatch.setattr(helper, "ready", lambda prefix: True)
    monkeypatch.setattr(helper.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Started over live API"))
    with pytest.raises(helper.Refused, match="already occupies"):
        helper.start_process_agent(installation)


def test_owner_rejects_manifest_changes(helper, installation):
    (installation / "current/payload/MANIFEST.json").write_text("{}")
    with pytest.raises(helper.Refused, match="manifest changed"):
        helper.owner(installation)


def test_setup_lock_refuses_concurrent_writer(helper, installation):
    with helper.locked(installation), pytest.raises(helper.Refused, match="active"), helper.locked(installation):
        pytest.fail("A second setup operation acquired the lock")


@pytest.mark.parametrize("url", ["postgresql://user:secret@remote.example/db", "postgresql://localhost/postgres",
                                 "postgresql://localhost/template1", "postgresql://localhost/db?options=unsafe"])
def test_database_binding_is_local_and_dedicated(helper, url):
    with pytest.raises(helper.Refused):
        helper.database_valid(url)


def test_external_database_is_private_and_preserved(helper, installation, monkeypatch):
    url = "postgresql://local:synthetic-secret@127.0.0.1:5555/project_memory"
    monkeypatch.setenv("DATABASE_URL", url)
    assert helper.ensure_database(installation, provision=True) == url
    path = installation / "settings/mcp-database.json"
    before = path.read_bytes()
    monkeypatch.setenv("DATABASE_URL", "postgresql://elsewhere/other")
    assert helper.ensure_database(installation, provision=True) == url
    assert path.read_bytes() == before and path.stat().st_mode & 0o777 == 0o600


def test_remote_docker_is_rejected(helper, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2375")
    with pytest.raises(helper.Refused, match="local Docker"):
        helper.docker_endpoint("docker")


def test_unavailable_daemon_is_not_treated_as_missing_resource(helper, installation, monkeypatch):
    def unavailable(*args, **kwargs):
        raise helper.Refused("daemon unavailable")

    monkeypatch.setattr(helper, "docker", unavailable)
    with pytest.raises(helper.Refused, match="daemon unavailable"):
        helper.inspect_docker(installation, "volume", "existing")


def test_foreign_docker_volume_is_not_adopted(helper, installation, monkeypatch):
    helper.write_json(installation / "settings/mcp-database.json", {
        "mode": "docker", "product_id": "a" * 32, "image": helper.PG_IMAGE,
        "url": "postgresql://am_local:synthetic-test-password-123456@127.0.0.1:5555/am_hindsight_local",
        "port": 5555, "volume": "foreign"})
    monkeypatch.setattr(helper, "inspect_docker", lambda *args: {"Labels": {helper.LABEL: "someone-else"}})
    with pytest.raises(helper.Refused, match="unrelated"):
        helper.ensure_database(installation, provision=True)


def test_manual_stop_latch_prevents_service_recovery(helper, installation, monkeypatch):
    helper.write_json(installation / "settings/mcp-service.json", {"enabled": False, "product_id": "a" * 32})
    monkeypatch.setattr(helper, "ensure_database", lambda *args, **kwargs: pytest.fail("Database was started"))
    with pytest.raises(helper.Refused, match="explicitly stopped"):
        helper.service_run(installation)


def test_launchagent_uses_stable_paths_and_no_credentials(helper, installation, tmp_path, monkeypatch):
    monkeypatch.setattr(helper.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(helper, "run", lambda *args, **kwargs: b"")
    monkeypatch.setattr(helper, "ready", lambda prefix: True)
    helper.start_agent(installation)
    label, path = helper.launch_details(installation)
    config = plistlib.loads(path.read_bytes())
    assert config["Label"] == label
    assert config["ProgramArguments"] == [str(installation / "bin/am-mcp"), "service-run"]
    assert {"PATH", "HOME", "USER", "LOGNAME"} <= set(config["EnvironmentVariables"])
    assert not any("API_KEY" in key or "TOKEN" in key or "DATABASE" in key for key in config["EnvironmentVariables"])
    assert config["Umask"] == 0o077
    assert config["KeepAlive"] == {"SuccessfulExit": False}
    assert path.stat().st_mode & 0o777 == 0o600


def test_stop_never_boots_out_unowned_launchagent(helper, installation, tmp_path, monkeypatch):
    monkeypatch.setattr(helper.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(helper.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    monkeypatch.setattr(helper, "run", lambda *args, **kwargs: pytest.fail("Unowned service was stopped"))
    with pytest.raises(helper.Refused, match="unowned"):
        helper.stop_agent(installation)


def test_nested_project_routes_to_its_explicit_receipt(helper, installation, tmp_path):
    project = tmp_path / "project"
    child = project / "nested"
    child.mkdir(parents=True)
    bank = "project-" + hashlib.sha256(os.fsencode(project)).hexdigest()[:24]
    item = {"project": str(project), "bank": bank, "mcp_url": f"http://127.0.0.1:18250/mcp/{bank}/"}
    helper.write_json(installation / "settings/mcp-projects.json", {str(project): item})
    assert helper.project_record(installation, child) == item
    item["bank"] = "another-project"
    helper.write_json(installation / "settings/mcp-projects.json", {str(project): item})
    with pytest.raises(helper.Refused, match="routing"):
        helper.project_record(installation, child)


def test_unconfigured_proxy_reports_setup_without_connecting(helper, installation, tmp_path, monkeypatch):
    import asyncio

    states = []

    async def diagnostic(state):
        states.append(state)

    monkeypatch.setattr(helper, "diagnostic_server", diagnostic)
    monkeypatch.setattr(helper, "ready", lambda *args: pytest.fail("Incomplete setup attempted HTTP"))
    asyncio.run(helper.proxy(installation, tmp_path))
    assert states == ["setup_incomplete"]


def test_bootstrap_accepts_custom_prefix_after_setup_subcommand(helper, tmp_path):
    args = helper.parser().parse_args(["setup", "--prefix", str(tmp_path), "--project", str(tmp_path),
                                      "--client", "omp"])
    assert args.prefix == tmp_path and args.client == ["omp"] and args.judge_host is None


def test_native_omp_suppresses_only_its_own_marketplace_alias(helper, installation, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    helper.configure_client(project, installation, "omp")
    servers = json.loads((project / ".omp/mcp.json").read_text())["mcpServers"]
    assert servers[helper.NAME + ":" + helper.NAME]["enabled"] is False
    assert servers[helper.NAME].get("enabled") is not False


def test_preflight_registration_makes_no_changes(helper, installation, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    assert helper.configure_client(project, installation, "codex", dry_run=True)["changed"]
    assert not (project / ".codex").exists()


def test_env_only_jev_key_is_not_copied_into_service_settings(helper, installation, monkeypatch):
    helper.write_json(installation / "settings/profile.json", {"provider": "jev"})
    monkeypatch.setenv("HINDSIGHT_API_MEMORY_ADMISSION_API_KEY", "synthetic-env-key-do-not-copy")
    monkeypatch.setattr(helper.sys.stdin, "isatty", lambda: False)
    with pytest.raises(helper.Refused, match="saved key"):
        helper.require_service_credentials(installation)
    assert not (installation / "settings/jev-credential.json").exists()


def test_unknown_newer_core_is_not_downgraded(helper, installation, tmp_path):
    path = (installation / "current/READY.json").resolve()
    value = json.loads(path.read_text())
    value["version"] = "9.0.0"
    helper.write_json(path, value)
    args = argparse.Namespace(prefix=installation, bundle=tmp_path, provider=None, judge_host=None,
                              model=None, executable=None)
    with pytest.raises(helper.Refused, match="pinned"):
        helper.install_core(args)
    assert json.loads(path.read_text())["version"] == "9.0.0"


def test_stop_persists_disabled_launchagent_across_logins(helper, installation, tmp_path, monkeypatch):
    monkeypatch.setattr(helper.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(helper, "run", lambda *args, **kwargs: b"")
    monkeypatch.setattr(helper, "ready", lambda prefix: True)
    helper.start_agent(installation)
    monkeypatch.setattr(helper.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(helper, "ready", lambda prefix: False)
    monkeypatch.setattr(helper, "stop_agent", lambda prefix: True)
    assert helper.main(["--prefix", str(installation), "stop"]) == 0
    _, path = helper.launch_details(installation)
    config = plistlib.loads(path.read_bytes())
    assert config["RunAtLoad"] is False and config["KeepAlive"] is False
    assert helper.read_json(installation / "settings/mcp-service.json")["enabled"] is False


def test_published_bootstrap_pins_helper_and_matches_marketplace_copy():
    root = SOURCE.parents[2]
    script = (SOURCE.parent / "install.sh").read_text()
    assert "helper_sha=" + hashlib.sha256(SOURCE.read_bytes()).hexdigest() in script
    assert (root / "plugins/agents-memory-local/scripts/install.sh").read_text() == script
    assert "3324b7fb06618a0c9d466bb4876e1d810eb4ef03b92f66ae996118f04d632b34" in script
    assert "eb80f6277f6d712a89e854f0f54b7067a9bfc9cc" in script
    assert "HELPER_SHA256" not in script


def test_stopped_proxy_never_connects_even_if_a_port_is_ready(helper, installation, tmp_path, monkeypatch):
    import asyncio

    states = []

    async def diagnostic(state):
        states.append(state)

    helper.write_json(installation / "settings/mcp-service.json", {"enabled": False, "product_id": "a" * 32})
    monkeypatch.setattr(helper, "ready", lambda *args: pytest.fail("Stopped proxy attempted HTTP"))
    monkeypatch.setattr(helper, "diagnostic_server", diagnostic)
    asyncio.run(helper.proxy(installation, tmp_path))
    assert states == ["explicitly_stopped"]


def test_existing_transport_environment_is_not_silently_adopted(helper, installation, tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    helper.configure_client(project, installation, "omp")
    path = project / ".omp/mcp.json"
    data = json.loads(path.read_text())
    data["mcpServers"][helper.NAME]["env"] = {"HOME": "/another-account"}
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises(helper.Refused, match="differs"):
        helper.configure_client(project, installation, "omp")
    assert path.read_bytes() == before
