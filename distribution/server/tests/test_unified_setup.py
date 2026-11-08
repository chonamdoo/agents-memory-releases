"""Owned installer failures must not publish corrupt assets or switch providers."""
import errno
import hashlib
import importlib.util
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("owned_unified_setup", ROOT / "unified_setup.py")
assert spec is not None and spec.loader is not None
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


@pytest.fixture
def assets(tmp_path):
    bundle = tmp_path / "bundle"
    source = tmp_path / "model"
    bundle.mkdir()
    source.mkdir()
    expected = {}
    names = json.loads((ROOT / "reranker-assets.sha256.json").read_text())
    for name in names:
        data = ("Synthetic integrity fixture: " + name).encode()
        (source / name).write_bytes(data)
        expected[name] = hashlib.sha256(data).hexdigest()
    (bundle / "reranker-assets.sha256.json").write_text(json.dumps(expected))
    shutil.copyfile(ROOT.parent / "mcp-local/setup.py", bundle / "runtime-helper.py")
    manifest = {"version": "2.0.0", "files": {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in bundle.iterdir()
    }}
    (bundle / "ASSETS.json").write_text(json.dumps(manifest))
    return tmp_path / "prefix", bundle, source


def test_unlisted_executable_is_not_a_verified_bundle(assets):
    _prefix, bundle, _source = assets
    manifest = json.loads((bundle / "ASSETS.json").read_text())
    del manifest["files"]["runtime-helper.py"]
    (bundle / "ASSETS.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        setup.verify(bundle)


def test_model_cache_is_reused_only_while_its_bytes_match(assets):
    prefix, bundle, source = assets
    setup.install_reranker(prefix, bundle, source)
    target = setup.reranker_directory(prefix, bundle)
    original = (target / "model.onnx").read_bytes()
    setup.install_reranker(prefix, bundle, None)
    assert (target / "model.onnx").read_bytes() == original
    (target / "model.onnx").write_bytes(b"corrupt cached model")
    with pytest.raises(ValueError):
        setup.install_reranker(prefix, bundle, source)
    assert (target / "model.onnx").read_bytes() == b"corrupt cached model"


def test_copy_corruption_never_publishes_a_model_cache(assets, monkeypatch):
    prefix, bundle, source = assets
    copyfile = shutil.copyfile

    def corrupt_copy(src, dst):
        result = copyfile(src, dst)
        if Path(src).name == "model.onnx":
            Path(dst).write_bytes(b"corrupt during copy")
        return result

    monkeypatch.setattr(setup.shutil, "copyfile", corrupt_copy)
    with pytest.raises(ValueError):
        setup.install_reranker(prefix, bundle, source)
    assert not setup.reranker_directory(prefix, bundle).exists()
    assert list((prefix / "models/reranker").iterdir()) == []


def test_model_symlink_cannot_read_or_replace_an_external_file(assets, tmp_path):
    prefix, bundle, source = assets
    outside = tmp_path / "external-model"
    outside.write_bytes((source / "model.onnx").read_bytes())
    (source / "model.onnx").unlink()
    (source / "model.onnx").symlink_to(outside)
    with pytest.raises(ValueError):
        setup.install_reranker(prefix, bundle, source)
    assert outside.read_bytes().startswith(b"Synthetic integrity fixture:")
    assert not setup.reranker_directory(prefix, bundle).exists()


@pytest.mark.parametrize("provider", ["claude", "codex", "omp"])
def test_legacy_provider_requires_explicit_migration_without_touching_credentials(assets, provider):
    prefix, bundle, _source = assets
    settings = prefix / "settings"
    settings.mkdir(mode=0o700, parents=True)
    saved = settings / "unified.json"
    saved.write_text(json.dumps({"provider": provider, "model": "legacy-model"}))
    saved.chmod(0o600)
    credential = settings / "jev-credential.json"
    credential.write_bytes(b"synthetic credential must remain unread and unchanged")
    credential.chmod(0o600)
    before = saved.read_bytes(), credential.read_bytes()
    args = SimpleNamespace(bundle=bundle, prefix=prefix, provider=None)
    with pytest.raises(setup.ProviderMigrationRequired):
        setup.install(args)
    assert (saved.read_bytes(), credential.read_bytes()) == before
    assert not (prefix / "unified-current").exists()


@pytest.mark.parametrize("provider", ["claude", "codex", "omp"])
def test_service_refuses_legacy_provider_before_reading_any_credential(tmp_path, provider):
    with pytest.raises(setup.ProviderMigrationRequired):
        setup.service_environment(tmp_path, object(), {"provider": provider})
    assert list(tmp_path.iterdir()) == []


def test_service_cannot_import_code_from_the_calling_project(assets, monkeypatch):
    prefix, bundle, _source = assets
    current = prefix / "unified-installs/current-fixture"
    current.mkdir(parents=True)
    (current / "bundle").symlink_to(bundle, target_is_directory=True)
    python = current / "gateway/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    project = prefix / "untrusted-project"
    package = project / "agents_memory"
    package.mkdir(parents=True)
    marker = prefix / "project-code-executed"
    (package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nraise SystemExit(47)\n")
    positive = subprocess.run([sys.executable, "-c", "import agents_memory"], cwd=project,
                              capture_output=True, timeout=20, check=False,
                              env={"HOME": str(prefix), "PATH": os.defpath})
    assert positive.returncode == 47 and marker.read_text() == "executed"
    marker.unlink()
    helper = setup.helper(bundle)
    monkeypatch.setattr(helper, "ensure_database", lambda *args, **kwargs: None)
    helper.write_json(prefix / "settings/mcp-database.json", {"url": "postgresql://unused-synthetic-fixture"})
    config = {
        "provider": "jev", "model": "jev-1.14.0", "mode": "local", "path": os.defpath,
        "provider_verified": True,
        "product_id": "synthetic-owner",
        "port": 21021, "hindsight_port": 21022, "host": "127.0.0.1", "public_url": "http://127.0.0.1:21021",
    }
    monkeypatch.setattr(setup, "read_settings", lambda path: (current, helper, config))
    monkeypatch.setattr(setup.os, "execve", lambda file, args, env: subprocess.run(
        args, executable=file, env=env, cwd=project, capture_output=True, timeout=20, check=False))
    setup.run_service(prefix)
    assert not marker.exists()


@pytest.mark.parametrize("provider", ["claude", "codex", "omp", "jev"])
def test_failed_activation_cannot_restore_native_or_persist_an_unverified_key(assets, monkeypatch, provider):
    prefix, bundle, source = assets
    packages = bundle / "packages"
    packages.mkdir()
    manifest = json.loads((bundle / "ASSETS.json").read_text())
    for label in ("sdk", "core_313"):
        member = "packages/" + label + ".whl"
        (bundle / member).write_bytes(b"isolated activation fixture; pip is not executed")
        manifest[label] = member
        manifest["files"][member] = hashlib.sha256((bundle / member).read_bytes()).hexdigest()
    (bundle / "ASSETS.json").write_text(json.dumps(manifest))
    settings = prefix / "settings"
    settings.mkdir(mode=0o700, parents=True)
    old = prefix / "unified-installs/previous-fixture"
    old.mkdir(parents=True)
    (prefix / "unified-current").symlink_to(old)
    h = setup.helper(bundle)
    saved = {
        "product_id": "synthetic-owner", "provider": provider,
        "model": "jev-1.14.0" if provider == "jev" else "legacy-model",
        "mode": "local", "host": "127.0.0.1", "port": 21031, "hindsight_port": 21032,
        "public_url": "http://127.0.0.1:21031", "path": os.defpath, "provider_verified": True,
    }
    h.write_json(settings / "unified.json", saved)
    h.write_json(settings / "mcp-database.json", {"url": "postgresql://unused-synthetic-fixture"})
    key = "synthetic_new_jev_key"
    credential = settings / "jev-credential.json"
    if provider == "jev":
        h.write_json(credential, {"schema_version": 1, "api_key": "synthetic_saved_jev_key"})
        key = None
    credential_before = credential.read_bytes() if credential.exists() else None
    monkeypatch.setattr(h, "owner", lambda path: {"id": "synthetic-owner"})
    monkeypatch.setattr(h, "ensure_database", lambda *args, **kwargs: None)
    monkeypatch.setattr(setup, "helper", lambda path: h)

    def run(command, **kwargs):
        if "-c" in command:
            raise RuntimeError("synthetic provider unavailable")
        return b""

    def ensure(path):
        assert provider == "jev"
        assert (path / "unified-current").resolve() == old
        return {"ready": True}

    monkeypatch.setattr(h, "run", run)
    monkeypatch.setattr(setup, "ensure", ensure)
    args = SimpleNamespace(
        bundle=bundle, prefix=prefix, provider="jev", model=None, public_url=None,
        reranker_dir=source, mode="local", host="127.0.0.1", client=None, project=prefix)
    with pytest.raises(RuntimeError, match="synthetic provider unavailable"):
        setup._install_owned(args, h, key, manifest)
    current = h.read_json(settings / "unified.json")
    if provider == "jev":
        assert current == saved
        assert (prefix / "unified-current").resolve() == old
        assert credential.read_bytes() == credential_before
    else:
        assert current["provider"] == "jev" and current["provider_verified"] is False
        assert (prefix / "unified-current").resolve() != old
        assert not credential.exists()
    assert list(settings.glob(".jev-check-*.json")) == []


def test_unverified_provider_cannot_start_even_from_a_new_current_pointer(assets, monkeypatch):
    prefix, _bundle, _source = assets
    h = SimpleNamespace(locked=lambda *args: nullcontext())
    config = {"provider": "jev", "provider_verified": False}
    monkeypatch.setattr(setup, "read_settings", lambda path: (prefix, h, config))
    monkeypatch.setattr(setup.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("Unverified provider started"))
    with pytest.raises(setup.SetupInputError):
        setup.ensure(prefix)


def test_different_explicit_key_is_rejected_before_bootstrap_and_preserves_saved_key(assets, monkeypatch):
    prefix, bundle, source = assets
    settings = prefix / "settings"
    settings.mkdir(mode=0o700, parents=True)
    h = setup.helper(bundle)
    h.write_json(settings / "unified.json", {
        "provider": "jev", "model": "jev-1.14.0", "public_url": "http://127.0.0.1:21041"})
    credential = settings / "jev-credential.json"
    h.write_json(credential, {"schema_version": 1, "api_key": "synthetic_saved_key"})
    supplied = prefix / "different-key"
    h.write_private(supplied, b"synthetic_different_key")
    before = credential.read_bytes()
    monkeypatch.setattr(setup.subprocess, "run", lambda *args, **kwargs: pytest.fail("Conflicting key reached bootstrap"))
    args = SimpleNamespace(
        bundle=bundle, prefix=prefix, provider=None, model=None, public_url=None,
        reranker_dir=source, jev_key_file=supplied)
    with pytest.raises(setup.SetupInputError):
        setup.install(args)
    assert credential.read_bytes() == before
    assert not (prefix / "unified-current").exists()


def test_pip_redispatch_cannot_load_project_startup_code(assets, tmp_path):
    _prefix, bundle, _source = assets
    base = tmp_path / "pip-base"
    subprocess.run([sys.executable, "-I", "-m", "venv", str(base)],
                   check=True, capture_output=True, timeout=60)
    trap = tmp_path / "untrusted-project"
    trap.mkdir()
    marker = trap / "executed.marker"
    (trap / "sitecustomize.py").write_text(
        "from pathlib import Path\nPath(__file__).with_name('executed.marker').write_text('executed')\n"
    )
    environment = {"HOME": str(tmp_path), "PATH": os.defpath, "PYTHONPATH": str(trap)}
    command = [str(base / "bin/python"), "-I", "-m", "pip", "--python"]
    subprocess.run([*command, sys.executable, "--version"], env=environment,
                   cwd=trap, check=True, capture_output=True, timeout=30)
    assert marker.read_text() == "executed"
    marker.unlink()
    launcher = setup._write_pip_python(setup.helper(bundle), tmp_path, Path(sys.executable))
    result = subprocess.run([*command, str(launcher), "--version"], env=environment,
                            cwd=trap, check=True, capture_output=True, timeout=30)
    assert result.stdout.startswith(b"pip ")
    assert not marker.exists()


@pytest.mark.parametrize("timeout", [False, True])
def test_bootstrap_failure_retains_bounded_private_diagnostics_without_terminal_secret(
        assets, monkeypatch, timeout):
    prefix, bundle, _source = assets
    canary = b"synthetic-private-bootstrap-canary"
    output = b"x" * 600000 + canary
    if timeout:
        def fail(*args, **kwargs):
            raise subprocess.TimeoutExpired(args[0], 1200, output=output, stderr=canary)
    else:
        def fail(*args, **kwargs):
            return subprocess.CompletedProcess(args[0], 1, output, canary)
    monkeypatch.setattr(setup.subprocess, "run", fail)
    with pytest.raises(setup.SetupInputError) as failure:
        setup._bootstrap(prefix, ["synthetic-bootstrap"], {}, setup.helper(bundle))
    assert canary.decode() not in str(failure.value)
    logs = list(prefix.parent.glob("agents-memory-bootstrap-*/bootstrap.log"))
    assert len(logs) == 1
    assert canary in logs[0].read_bytes()
    assert logs[0].stat().st_size <= 1048600
    assert stat.S_IMODE(logs[0].stat().st_mode) == 0o600
    assert stat.S_IMODE(logs[0].parent.stat().st_mode) == 0o700


@pytest.mark.parametrize("endpoint", ["port", "hindsight_port"])
def test_service_ports_allow_replacement_after_server_active_close(endpoint):
    with socket.socket() as previous:
        previous.settimeout(5)
        previous.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        previous.bind(("127.0.0.1", 0))
        previous.listen(1)
        address = previous.getsockname()
        with socket.create_connection(address, timeout=5) as client:
            connection, _ = previous.accept()
            with connection:
                connection.settimeout(5)
                client.sendall(b"?")
                assert connection.recv(1) == b"?"
                connection.sendall(b"previous service\n")
                connection.shutdown(socket.SHUT_WR)
                with client.makefile("rb") as response:
                    assert response.read() == b"previous service\n"
                client.shutdown(socket.SHUT_WR)
                assert connection.recv(1) == b""

    with socket.socket() as plain_probe, pytest.raises(OSError) as occupied:
        plain_probe.bind(address)
    assert occupied.value.errno == errno.EADDRINUSE

    config = {"port": 0, "hindsight_port": 0}
    config[endpoint] = address[1]
    setup._require_free_service_ports(config)

    with socket.socket() as replacement:
        replacement.settimeout(5)
        replacement.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        replacement.bind(address)
        replacement.listen(1)
        with socket.create_connection(address, timeout=5) as client:
            connection, _ = replacement.accept()
            with connection:
                connection.settimeout(5)
                client.sendall(b"?")
                assert connection.recv(1) == b"?"
                connection.sendall(b"replacement service\n")
                connection.shutdown(socket.SHUT_WR)
                with client.makefile("rb") as response:
                    assert response.read() == b"replacement service\n"


@pytest.mark.parametrize("endpoint", ["port", "hindsight_port"])
def test_unreceipted_listener_cannot_be_adopted_as_an_updated_service(assets, monkeypatch, endpoint):
    prefix, _bundle, _source = assets
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        config = {"provider": "jev", "provider_verified": True, "port": 0, "hindsight_port": 0}
        config[endpoint] = listener.getsockname()[1]
        h = SimpleNamespace(locked=lambda *args: nullcontext())
        monkeypatch.setattr(setup, "read_settings", lambda path: (prefix, h, config))
        with pytest.raises(setup.SetupInputError, match="occupied"):
            setup.ensure(prefix)
    assert not (prefix / "settings/unified-pid.json").exists()


def test_stale_ready_cannot_hide_the_selected_service_exiting(assets, monkeypatch):
    prefix, bundle, _source = assets
    h = setup.helper(bundle)
    receipt = {"pid": 550003, "product_id": "synthetic-owner", "instance_id": "a" * 32}
    h.write_json(prefix / "settings/unified-pid.json", receipt)
    config = {"provider": "jev", "provider_verified": True}
    monkeypatch.setattr(setup, "read_settings", lambda path: (prefix, h, config))
    pids = iter([receipt["pid"], receipt["pid"], None])
    monkeypatch.setattr(setup, "owned_pid", lambda *args: next(pids))
    monkeypatch.setattr(setup, "health", lambda config: {"ready": True, "service_instance": "b" * 32})
    monkeypatch.setattr(setup.time, "sleep", lambda seconds: None)
    with pytest.raises(setup.SetupInputError, match="stopped or changed"):
        setup.ensure(prefix)


def test_mac_process_disappearance_between_liveness_and_ps_is_stopped(assets, monkeypatch):
    prefix, bundle, _source = assets
    h = setup.helper(bundle)
    h.write_json(prefix / "settings/unified-pid.json", {"pid": 550003, "product_id": "synthetic-owner"})
    monkeypatch.setattr(h, "owner", lambda path: {"id": "synthetic-owner"})
    is_dir = Path.is_dir
    monkeypatch.setattr(Path, "is_dir", lambda path: False if path == Path("/proc") else is_dir(path))
    probes = iter([None, ProcessLookupError()])
    def kill(pid, sig):
        result = next(probes)
        if result is not None:
            raise result
    monkeypatch.setattr(setup.os, "kill", kill)
    monkeypatch.setattr(setup.subprocess, "run",
                        lambda args, **kwargs: subprocess.CompletedProcess(args, 1, b"", b""))
    assert setup.owned_pid(prefix, h) is None


def test_process_disappearance_before_term_still_clears_its_own_receipt(assets, monkeypatch):
    prefix, bundle, _source = assets
    h = setup.helper(bundle)
    receipt = prefix / "settings/unified-pid.json"
    h.write_json(receipt, {"pid": 550003, "product_id": "synthetic-owner"})
    pids = iter([550003, None])
    monkeypatch.setattr(setup, "owned_pid", lambda *args: next(pids))
    def kill(pid, sig):
        raise ProcessLookupError()
    monkeypatch.setattr(setup.os, "kill", kill)
    setup._stop_locked(prefix, h)
    assert not receipt.exists()


@pytest.mark.parametrize(("later_state", "command", "stopped"), [
    ("Z", b"", True), ("X", b"", True), (None, b"", True),
    ("S", b"", False), ("S", b"/usr/bin/unrelated", False),
])
def test_linux_exit_between_stat_and_cmdline_requires_observed_exit(
    assets, monkeypatch, later_state, command, stopped,
):
    prefix, bundle, _source = assets
    h = setup.helper(bundle)
    h.write_json(prefix / "settings/unified-pid.json", {"pid": 550003, "product_id": "synthetic-owner"})
    monkeypatch.setattr(h, "owner", lambda path: {"id": "synthetic-owner"})
    monkeypatch.setattr(setup.os, "kill", lambda pid, sig: None)
    is_dir, read_text, read_bytes = Path.is_dir, Path.read_text, Path.read_bytes
    monkeypatch.setattr(Path, "is_dir", lambda path: True if path == Path("/proc") else is_dir(path))
    states = iter(["S", later_state])
    def stat_text(path, *args, **kwargs):
        if path == Path("/proc/550003/stat"):
            state = next(states)
            if state is None:
                raise FileNotFoundError()
            return "550003 (synthetic) " + state + " 0"
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", stat_text)
    monkeypatch.setattr(Path, "read_bytes", lambda path: command if path == Path("/proc/550003/cmdline") else read_bytes(path))
    if stopped:
        assert setup.owned_pid(prefix, h) is None
    else:
        with pytest.raises(setup.SetupInputError, match="another process"):
            setup.owned_pid(prefix, h)
