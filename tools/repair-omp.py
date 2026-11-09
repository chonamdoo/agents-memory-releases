#!/usr/bin/env python3
"""Repair an existing local Jev installation without resetting its data.

Close OMP first. Downloads only the immutable, checksum-pinned v2.0.4 bundle.
The normal installer owns runtime rollback; this helper never removes a prefix,
database, model, pending operation, credential, or review decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.request import urlopen
from uuid import uuid4

ARCHIVE_SHA256 = "62b46c6393876be19df7ccfea96343b3baa0ced2f599cee2f06438dd449275ef"
ARCHIVE_URL = ("https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/"
               "1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/"
               "v2.0.4-relevance/agents-memory-unified-2.0.0-source-subject-v17.tar.gz")
PLUGIN = "agents-memory-unified@agents-memory"


class RepairError(Exception):
    pass


class WorkerBusy(RepairError):
    def __init__(self, pid, remaining):
        super().__init__("replica_worker_busy_close_OMP_and_retry_after_90_seconds")
        self.details = {"worker_pid": pid if type(pid) is int and pid > 0 else None,
                        "lease_remaining_seconds": max(0, round(remaining))}


def safe(path: Path, *, private=False):
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise RepairError("symlink_path_refused")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
        raise RepairError("unsafe_file_refused")
    if private and info.st_mode & 0o077:
        raise RepairError("private_file_permissions_required")
    return path


def read_json(path, *, private=False):
    value = json.loads(safe(path, private=private).read_text())
    if not isinstance(value, dict):
        raise RepairError("configuration_object_required")
    return value


def write_private(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid4().hex)
    try:
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def sqlite_ro(path):
    return sqlite3.connect(safe(path, private=True).as_uri() + "?mode=ro", uri=True, timeout=5)


def check_worker(path):
    with sqlite_ro(path) as db:
        row = db.execute("SELECT owner,expires,pid FROM worker WHERE id=1").fetchone()
    if row and row[0] and row[1] >= time.time():
        pid = row[2]
        if type(pid) is int and pid > 0 and os.name == "posix":
            try:
                os.kill(pid, 0)  # Liveness check only, never terminate a process.
            except ProcessLookupError:
                return  # The SDK itself permits reclaiming abandoned owners.
            except PermissionError:
                pass  # Alive or unverified: preserve the lease and stop.
            else:
                if sys.platform.startswith("linux"):
                    try:
                        process = (Path("/proc") / str(pid) / "stat").read_text()
                        if process.rpartition(")")[2].split()[0] in {"Z", "X"}:
                            return
                    except FileNotFoundError:
                        return
                    except (PermissionError, IndexError):
                        pass
        # Do not overwrite, release or otherwise edit the recorded owner.
        raise WorkerBusy(pid, row[1] - time.time())


def snapshot_files(prefix, project, agent_dir, backup):
    """Create private, consistent backups before any install/config mutation."""
    files = [prefix / "client/local/connection.json",
             project / ".omp/mcp.json", project / ".omp/extensions/agents-memory-cloud.ts",
             agent_dir / "mcp.json"]
    settings = prefix / "settings"
    if settings.exists():
        if settings.is_symlink():
            raise RepairError("symlink_settings_refused")
        files += [p for p in settings.iterdir() if p.is_file() or p.is_symlink()]
    manifest = []
    for index, path in enumerate(dict.fromkeys(files)):
        if not path.exists() and not path.is_symlink():
            continue
        safe(path)
        data = path.read_bytes()
        target = backup / "files" / str(index)
        write_private(target, data)
        manifest.append({"source": str(path), "backup": str(target.relative_to(backup)),
                         "sha256": hashlib.sha256(data).hexdigest()})
    source = prefix / "client/local/replica.sqlite"
    target = backup / "replica.sqlite"
    with sqlite_ro(source) as original:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        with sqlite3.connect(target) as copy:
            original.backup(copy)
            if copy.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise RepairError("replica_backup_check_failed")
    write_private(backup / "FILES.json", json.dumps(manifest, indent=2).encode())


def extract_verified(archive, destination):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise RepairError("release_archive_checksum_failed")
    # The archive digest is fixed, and extraction also rejects links/paths/devices.
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for item in members:
            parts = Path(item.name).parts
            if (Path(item.name).is_absolute() or ".." in parts
                    or not (item.isfile() or item.isdir())):
                raise RepairError("unsafe_release_archive")
        filters = {"filter": "data"} if hasattr(tarfile, "data_filter") else {}
        tar.extractall(destination, members=members, **filters)
    installers = list(destination.rglob("install-unified.sh"))
    if len(installers) != 1:
        raise RepairError("release_installer_not_unique")
    return installers[0].parent


def run_logged(command, log, *, cwd):
    # Tool output can include configuration and must stay in the private backup.
    if not log.exists():
        write_private(log, b"")
    with log.open("ab") as out:
        result = subprocess.run(command, cwd=cwd, stdout=out, stderr=out)
    log.chmod(0o600)
    if result.returncode:
        raise RepairError("command_failed_" + log.stem)


def uninstall_transport(log, *, cwd):
    try:
        run_logged(["omp", "plugin", "uninstall", PLUGIN, "--scope", "user"], log, cwd=cwd)
    except RepairError:
        # Permit resumption after a completed uninstall and interrupted install.
        # Wrong scope, transport errors and every other failure still stop.
        output = log.read_bytes()
        missing = ('Plugin "' + PLUGIN + '" is not installed').encode()
        if missing not in output or b"scope" in output:
            raise


# Executed by the installed isolated SDK interpreter, never system/site packages.
SDK_REPAIR = r'''
import json, pathlib, re, sys
from agents_memory_collab.automation_setup import plan
from agents_memory_collab.setup import write_private
from agents_memory_collab.client import Replica, Remote
from agents_memory_collab.models import Failure
mode, raw_prefix, raw_project = sys.argv[1:]
prefix, project = pathlib.Path(raw_prefix), pathlib.Path(raw_project)
connection = prefix / "client/local/connection.json"
state = prefix / "client/local/replica.sqlite"
settings = json.loads(connection.read_text())
launcher = prefix / "bin/unified-python"
path, original, replacement = plan("omp", project, connection, state, project.name,
                                   python_launcher=launcher)
projects = settings.get("automation_projects", {})
if not isinstance(projects, dict):
    raise ValueError("invalid_automation_projects")
hosts = projects.get(project.name, [])
if not isinstance(hosts, list) or any(x not in {"omp", "claude", "codex"} for x in hosts):
    raise ValueError("invalid_automation_hosts")
if mode == "plan":
    print(json.dumps({"plan_ok": True, "project_already_configured": project.name in projects}))
else:
    if (path.read_text() if path.exists() else "") != original:
        raise ValueError("host_config_changed")
    if replacement is not None:
        write_private(path, replacement)
    projects[project.name] = list(dict.fromkeys([*hosts, "omp"]))
    settings["automation_projects"] = projects
    write_private(connection, json.dumps(settings) + "\n")
    replica = Replica(state, Remote(settings["url"], settings["token"]))
    report = {"automation_configured": True, "capture_preference_preserved": True,
              "automatic_execution_verified": False, "full_sync_verified": False,
              "pending_review_approved": False, "prompt_upload_consent_granted": False}
    try:
        if replacement is not None:
            replica.reset_host_events(project.name, {"omp"})
        # Download only. Pending writes are never submitted by the repair probe.
        result = replica.cycle(pull_only=True)
        report.update(pull_sync="passed", replica_state=result["state"])
    except Failure as error:
        code = error.code if isinstance(error.code, str) and re.fullmatch(r"[a-z0-9_]{1,120}", error.code) else "redacted_error"
        report.update(pull_sync="failed", error=code, http_status=error.status)
    except Exception as error:
        # Never stringify exceptions: URLs, credentials and source text may occur.
        report.update(pull_sync="failed", error_type=type(error).__name__)
    finally:
        replica.close()
    print(json.dumps(report))
'''


def run_sdk(python, mode, prefix, project, log):
    result = subprocess.run([str(python), "-I", "-B", "-c", SDK_REPAIR,
                             mode, str(prefix), str(project)], capture_output=True)
    write_private(log, result.stdout + b"\n" + result.stderr)
    if result.returncode:
        raise RepairError("sdk_" + mode + "_failed_see_private_log")
    try:
        return json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise RepairError("invalid_sdk_repair_report") from None


def remove_owned_direct_config(path, connection, state):
    if not path.exists():
        return
    data = read_json(path)
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise RepairError("invalid_mcp_configuration")
    old = servers.get("agents-memory-cloud")
    if old is None:
        return
    args = old.get("args", []) if isinstance(old, dict) else []
    def argument(name):
        return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None
    if (argument("--connection") != str(connection) or argument("--state") != str(state)):
        raise RepairError("other_profile_direct_MCP_preserved")
    del servers["agents-memory-cloud"]
    write_private(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--prefix", type=Path, default=Path.home() / ".local/share/agents-memory-unified")
    parser.add_argument("--apply", action="store_true", help="Back up and repair; otherwise only inspect")
    args = parser.parse_args()
    os.umask(0o077)
    prefix, project = args.prefix.expanduser().absolute(), args.project.expanduser().absolute()
    for directory in (prefix, project):
        if not directory.is_dir() or any(p.is_symlink() for p in [directory, *directory.parents]):
            raise RepairError("existing_real_installation_and_project_required")
    # Scope is an existing local Jev installation, never a fresh or remote profile.
    saved = read_json(prefix / "settings/unified.json", private=True)
    if saved.get("provider") != "jev" or saved.get("mode") != "local":
        raise RepairError("existing_local_jev_installation_required")
    connection = prefix / "client/local/connection.json"
    bound = read_json(connection, private=True)
    if not isinstance(bound.get("url"), str) or bound["url"].rstrip("/") != str(saved.get("public_url", "")).rstrip("/"):
        raise RepairError("existing_runtime_and_client_destination_differ")
    state = prefix / "client/local/replica.sqlite"
    safe(state, private=True)
    python = prefix / "unified-current/gateway/bin/python"
    if not python.is_file() or not (prefix / "bin/unified-python").is_file():
        raise RepairError("existing_owned_runtime_required")
    agent_dir = Path(os.environ.get("PI_CODING_AGENT_DIR", str(Path.home() / ".omp/agent"))).expanduser().absolute()
    if os.environ.get("OMP_PROFILE") or os.environ.get("PI_PROFILE"):
        raise RepairError("named_OMP_profile_requires_explicit_profile_repair")
    print(json.dumps({"existing_data": True, "apply": args.apply,
                      "database_reset": False, "project": str(project)}), flush=True)
    if not args.apply:
        return
    if not shutil.which("omp"):
        raise RepairError("omp_executable_required")
    check_worker(state)
    root = Path.home() / ".local/state/agents-memory-repair"
    if any(p.is_symlink() for p in [root, *root.parents]):
        raise RepairError("unsafe_backup_directory")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    backup = root / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8])
    backup.mkdir(mode=0o700)
    print("Private backup: " + str(backup), flush=True)
    snapshot_files(prefix, project, agent_dir, backup)
    # Reject a different project's/custom extension before changing the runtime.
    run_sdk(python, "plan", prefix, project, backup / "sdk-plan.log")
    with tempfile.TemporaryDirectory(prefix="agents-memory-omp-repair-") as temporary:
        temp = Path(temporary)
        archive = temp / "release.tar.gz"
        with urlopen(ARCHIVE_URL, timeout=60) as incoming:
            data = incoming.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            raise RepairError("oversized_release_archive")
        write_private(archive, data)
        bundle = extract_verified(archive, temp / "bundle")
        print("Reinstalling the verified runtime at its existing prefix...", flush=True)
        # No --client: normal setup would upload the pending queue before writing
        # host automation. Repair that binding separately and probe download-only.
        run_logged(["bash", str(bundle / "install-unified.sh"), "--bundle", str(bundle),
                    "--prefix", str(prefix), "--provider", "jev", "--mode", "local"],
                   backup / "runtime-install.log", cwd=project)
    report = run_sdk(python, "apply", prefix, project, backup / "sdk-repair.log")
    for path in (project / ".omp/mcp.json", agent_dir / "mcp.json"):
        remove_owned_direct_config(path, connection, state)
    print("Reinstalling the OMP marketplace transport...", flush=True)
    uninstall_transport(backup / "plugin-uninstall.log", cwd=project)
    run_logged(["omp", "plugin", "marketplace", "update", "agents-memory"],
               backup / "marketplace-update.log", cwd=project)
    run_logged(["omp", "plugin", "install", PLUGIN, "--scope", "user"],
               backup / "plugin-install.log", cwd=project)
    report.update(backup=str(backup), database_reset=False,
                  next="Restart OMP in this project, send one normal input, then check setup_status and source_search.")
    write_private(backup / "REPORT.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pull_sync"] == "passed" else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RepairError as error:
        print(json.dumps({"repair_error": str(error), "database_reset": False,
                          **(error.details if isinstance(error, WorkerBusy) else {})}), file=sys.stderr)
        sys.exit(1)
    except Exception as error:
        print(json.dumps({"repair_error_type": type(error).__name__, "database_reset": False}), file=sys.stderr)
        sys.exit(1)
