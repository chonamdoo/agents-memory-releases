"""Offline preservation and failure checks; no real credentials/provider/network."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import time

import pytest


spec = importlib.util.spec_from_file_location("repair_omp", Path(__file__).parents[1] / "repair-omp.py")
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def private(path, value):
    repair.write_private(path, value if isinstance(value, bytes) else json.dumps(value).encode())


@pytest.fixture
def existing(tmp_path):
    prefix, project, agent, backup = [tmp_path / x for x in ("owned prefix", "project", "agent", "backup")]
    for p in (prefix, project, agent, backup):
        p.mkdir(mode=0o700)
    private(prefix / "settings/unified.json", {"provider": "jev", "mode": "local", "public_url": "https://example.invalid"})
    private(prefix / "settings/jev-credential.json", {"api_key": "SYNTHETIC_TEST_ONLY"})
    private(prefix / "client/local/connection.json", {"url": "https://example.invalid", "token": "SYNTHETIC_TEST_ONLY"})
    state = prefix / "client/local/replica.sqlite"
    private(state, b"")
    with sqlite3.connect(state) as db:
        db.executescript("CREATE TABLE worker(id INTEGER,owner TEXT,expires REAL,pid INTEGER);"
                         "INSERT INTO worker VALUES(1,NULL,0,NULL);"
                         "CREATE TABLE outbox(op_id TEXT,body TEXT,status TEXT,error TEXT);"
                         "INSERT INTO outbox VALUES('one','original unapproved source','needs_review','prompt_upload_requires_explicit_opt_in');"
                         "CREATE TABLE memories(id TEXT,text TEXT);"
                         "INSERT INTO memories VALUES('old','preserved original memory');")
    return prefix, project, agent, backup


def rows(db):
    with sqlite3.connect(db) as connection:
        return {name: connection.execute('SELECT * FROM "' + name + '"').fetchall()
                for name, in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_snapshot_keeps_every_table_pending_consent_and_credentials(existing):
    prefix, project, agent, backup = existing
    state = prefix / "client/local/replica.sqlite"
    before = rows(state)
    key = (prefix / "settings/jev-credential.json").read_bytes()
    private(project / ".omp/extensions/agents-memory-cloud.ts", b"original hook")
    repair.snapshot_files(prefix, project, agent, backup)
    assert rows(state) == rows(backup / "replica.sqlite") == before
    assert (prefix / "settings/jev-credential.json").read_bytes() == key
    manifest = json.loads((backup / "FILES.json").read_text())
    for item in manifest:
        assert (backup / item["backup"]).read_bytes() == Path(item["source"]).read_bytes()
        assert (backup / item["backup"]).stat().st_mode & 0o777 == 0o600
    assert (backup / "replica.sqlite").stat().st_mode & 0o777 == 0o600
    with sqlite3.connect(state) as db:
        db.execute("INSERT INTO memories VALUES('later','new original')")
    assert rows(backup / "replica.sqlite") == before


def test_live_lease_is_never_broken(existing):
    prefix, *_ = existing
    state = prefix / "client/local/replica.sqlite"
    with sqlite3.connect(state) as db:
        db.execute("UPDATE worker SET owner='another',expires=?,pid=?", (time.time() + 60, os.getpid()))
    before = rows(state)
    with pytest.raises(repair.WorkerBusy, match="replica_worker_busy") as result:
        repair.check_worker(state)
    assert result.value.details['worker_pid'] == os.getpid()
    assert 0 < result.value.details['lease_remaining_seconds'] <= 60
    assert rows(state) == before


@pytest.mark.parametrize("kind", ['dead', 'permission', 'unknown_pid', 'zero_pid'])
def test_worker_liveness_is_conservative_and_never_writes_lease(existing, monkeypatch, kind):
    prefix, *_ = existing
    state = prefix / 'client/local/replica.sqlite'
    pid = None if kind == 'unknown_pid' else 0 if kind == 'zero_pid' else 234567
    with sqlite3.connect(state) as db:
        db.execute("UPDATE worker SET owner='previous',expires=?,pid=?", (time.time()+60, pid))
    before, probes = rows(state), []
    def probe(actual, signal):
        probes.append((actual, signal))
        assert signal == 0 and actual == pid
        raise ProcessLookupError() if kind == 'dead' else PermissionError()
    monkeypatch.setattr(repair.os, 'kill', probe)
    if kind == 'dead':
        repair.check_worker(state)
    else:
        with pytest.raises(repair.WorkerBusy):
            repair.check_worker(state)
    assert rows(state) == before
    assert probes == ([] if pid in (None, 0) else [(pid, 0)])


def test_linux_zombie_owner_is_abandoned_without_clearing_lease(existing, monkeypatch):
    prefix, *_ = existing
    state = prefix / 'client/local/replica.sqlite'
    with sqlite3.connect(state) as db:
        db.execute("UPDATE worker SET owner='exited',expires=?,pid=234567", (time.time()+60,))
    before = rows(state)
    monkeypatch.setattr(repair.sys, 'platform', 'linux')
    monkeypatch.setattr(repair.os, 'kill', lambda pid, signal: None)
    original = Path.read_text
    def stat_text(path, *args, **kwargs):
        if str(path) == '/proc/234567/stat':
            return '234567 (old) worker) Z 1 0'
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', stat_text)
    repair.check_worker(state)
    assert rows(state) == before


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "public"])
def test_unsafe_private_files_refused(tmp_path, kind):
    original, target = tmp_path / "original", tmp_path / "target"
    private(original, {"synthetic": True})
    if kind == "symlink":
        target.symlink_to(original)
    elif kind == "hardlink":
        os.link(original, target)
    else:
        target = original
        target.chmod(0o644)
    with pytest.raises(repair.RepairError):
        repair.read_json(target, private=True)


def test_remove_only_owned_MCP_preserves_codegraph_and_other_settings(existing):
    prefix, project, *_ = existing
    connection, state = [prefix / "client/local" / x for x in ("connection.json", "replica.sqlite")]
    path = project / ".omp/mcp.json"
    codegraph = {"command": "codegraph", "args": ["mcp"], "enabled": True}
    private(path, {"other": 7, "mcpServers": {"codegraph": codegraph,
                 "agents-memory-cloud": {"args": ["--connection", str(connection), "--state", str(state)]}}})
    repair.remove_owned_direct_config(path, connection, state)
    assert json.loads(path.read_text()) == {"other": 7, "mcpServers": {"codegraph": codegraph}}
    repair.remove_owned_direct_config(path, connection, state)


def test_different_profile_registration_is_not_removed(existing):
    prefix, project, *_ = existing
    path = project / ".omp/mcp.json"
    private(path, {"mcpServers": {"agents-memory-cloud": {"args": ["--connection", "/another/profile"]}}})
    before = path.read_bytes()
    with pytest.raises(repair.RepairError, match="other_profile"):
        repair.remove_owned_direct_config(path, prefix / "connection", prefix / "state")
    assert path.read_bytes() == before


def test_bad_release_digest_extracts_nothing(tmp_path):
    archive, target = tmp_path / "bad.tar.gz", tmp_path / "output"
    archive.write_bytes(b"not the release")
    with pytest.raises(repair.RepairError, match="checksum"):
        repair.extract_verified(archive, target)
    assert not target.exists()


@pytest.mark.parametrize("kind", ["parent", "absolute", "symlink", "device"])
def test_archive_rejects_unsafe_members_even_after_digest_check(tmp_path, monkeypatch, kind):
    archive = tmp_path / "fixture.tar.gz"
    with tarfile.open(archive, "w:gz") as out:
        member = tarfile.TarInfo("../outside" if kind == "parent" else "/outside" if kind == "absolute" else "entry")
        if kind == "symlink":
            member.type, member.linkname = tarfile.SYMTYPE, "../outside"
        elif kind == "device":
            member.type = tarfile.CHRTYPE
        out.addfile(member, io.BytesIO())
    monkeypatch.setattr(repair, "ARCHIVE_SHA256", repair.hashlib.sha256(archive.read_bytes()).hexdigest())
    with pytest.raises(repair.RepairError, match="unsafe_release_archive"):
        repair.extract_verified(archive, tmp_path / "output")


def test_failed_command_output_stays_private(tmp_path, capsys):
    log = tmp_path / "failure.log"
    with pytest.raises(repair.RepairError, match="command_failed_failure"):
        repair.run_logged([sys.executable, "-c", "print('SYNTHETIC_NOT_FOR_STDOUT'); raise SystemExit(2)"], log, cwd=tmp_path)
    assert "SYNTHETIC_NOT_FOR_STDOUT" in log.read_text()
    assert "SYNTHETIC_NOT_FOR_STDOUT" not in capsys.readouterr().out
    assert log.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("detail,allowed", [("is not installed", True),
                                           ("is not installed in user scope", False),
                                           ("network error", False)])
def test_repair_resume_only_ignores_missing_plugin(tmp_path, monkeypatch, detail, allowed):
    log = tmp_path / "uninstall.log"
    def failed(*args, **kwargs):
        private(log, ('Plugin "' + repair.PLUGIN + '" ' + detail).encode())
        raise repair.RepairError('command_failed_plugin-uninstall')
    monkeypatch.setattr(repair, 'run_logged', failed)
    if allowed:
        repair.uninstall_transport(log, cwd=tmp_path)
    else:
        with pytest.raises(repair.RepairError):
            repair.uninstall_transport(log, cwd=tmp_path)


def fake_sdk(tmp_path, *, failure=False):
    package = tmp_path / "agents_memory_collab"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "models.py").write_text("class Failure(Exception): pass\n")
    (package / "setup.py").write_text("def write_private(path,text):\n path.parent.mkdir(parents=True,exist_ok=True)\n path.write_text(text)\n")
    (package / "automation_setup.py").write_text("def plan(host,project,connection,state,name,python_launcher):\n p=project/'.omp/extensions/agents-memory-cloud.ts'\n return p,p.read_text() if p.exists() else '', 'restored hook'\n")
    (package / "client.py").write_text("""import pathlib
class Remote:
 def __init__(self,url,token): pass
class Replica:
 def __init__(self,state,remote): self.state=state
 def reset_host_events(self,*args): pass
 def cycle(self,*,pull_only):
  assert pull_only is True, 'UPLOAD_NOT_ALLOWED'
  pathlib.Path(str(self.state)+'.download-only').write_text('yes')
""" + ("  raise OSError('SYNTHETIC_SECRET_IN_EXCEPTION')\n" if failure else "  return {'state':'needs_review'}\n") + " def close(self): pass\n")


@pytest.mark.parametrize("failure", [False, True])
def test_sdk_repair_restores_mapping_without_approving_or_uploading(existing, tmp_path, failure):
    prefix, project, *_ = existing
    fake_sdk(tmp_path, failure=failure)
    settings = {"url": "https://example.invalid", "token": "SYNTHETIC_TEST_ONLY", "automatic_memory": True,
                "automation_projects": {"another": ["codex"]}}
    connection = prefix / "client/local/connection.json"
    private(connection, settings)
    state = prefix / "client/local/replica.sqlite"
    before = rows(state)
    # Run exact embedded code with an explicit offline fake package; -I on the
    # production launcher is unchanged. No provider, network, or real runtime.
    wrapper = "import sys;sys.path.insert(0," + repr(str(tmp_path)) + ");" + repair.SDK_REPAIR
    result = subprocess.run([sys.executable, "-I", "-B", "-c", wrapper, "apply", str(prefix), str(project)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['pull_sync'] == ('failed' if failure else 'passed')
    assert report['full_sync_verified'] is False and report['pending_review_approved'] is False
    assert report['prompt_upload_consent_granted'] is False and report['automatic_execution_verified'] is False
    assert 'SYNTHETIC_SECRET' not in result.stdout
    actual = json.loads(connection.read_text())
    assert actual == {**settings, "automation_projects": {"another": ["codex"], project.name: ["omp"]}}
    assert rows(state) == before
    assert Path(str(state) + '.download-only').read_text() == 'yes'


@pytest.mark.parametrize("runtime_fails", [False, True])
def test_complete_orchestration_backs_up_and_stops_on_installer_failure(existing, tmp_path, monkeypatch, runtime_fails):
    prefix, project, agent, _ = existing
    home = tmp_path / 'home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    for name in ['OMP_PROFILE', 'PI_PROFILE']:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('PI_CODING_AGENT_DIR', str(agent))
    for path in [prefix / 'unified-current/gateway/bin/python', prefix / 'bin/unified-python']:
        private(path, b'owned executable placeholder')
    monkeypatch.setattr(repair.shutil, 'which', lambda name: '/fake/omp')
    archive = Path(__file__).parents[2] / 'release-candidates/v2.0.4-relevance/agents-memory-unified-2.0.0-source-subject-v17.tar.gz'
    monkeypatch.setattr(repair, 'urlopen', lambda *a, **k: io.BytesIO(archive.read_bytes()))
    commands, modes = [], []
    before = rows(prefix / 'client/local/replica.sqlite')
    key = (prefix / 'settings/jev-credential.json').read_bytes()
    def run_sdk(python, mode, owned, actual_project, log):
        assert owned == prefix and actual_project == project
        assert list((home / '.local/state/agents-memory-repair').glob('*/replica.sqlite'))
        modes.append(mode)
        private(log, b'fake SDK; no provider calls')
        return {'plan_ok': True} if mode == 'plan' else {'pull_sync': 'passed', 'full_sync_verified': False}
    def run_logged(command, log, *, cwd):
        commands.append(command)
        private(log, b'fake subprocess; no provider calls')
        if command[0] == 'bash':
            assert '--client' not in command
            assert command[command.index('--prefix') + 1] == str(prefix)
            if runtime_fails:
                raise repair.RepairError('command_failed_runtime-install')
    monkeypatch.setattr(repair, 'run_sdk', run_sdk)
    monkeypatch.setattr(repair, 'run_logged', run_logged)
    monkeypatch.setattr(sys, 'argv', ['repair', '--prefix', str(prefix), '--project', str(project), '--apply'])
    if runtime_fails:
        with pytest.raises(repair.RepairError, match='runtime-install'):
            repair.main()
        assert len(commands) == 1 and modes == ['plan']
    else:
        assert repair.main() == 0
        assert modes == ['plan', 'apply']
        assert [c[:3] for c in commands[1:]] == [['omp', 'plugin', 'uninstall'], ['omp', 'plugin', 'marketplace'], ['omp', 'plugin', 'install']]
    assert rows(prefix / 'client/local/replica.sqlite') == before
    assert (prefix / 'settings/jev-credential.json').read_bytes() == key
