"""One-time device setup; persistent secrets live outside client plugin caches."""
from __future__ import annotations

import getpass
import json
import os
import re
import socket
import sys
import tomllib
from pathlib import Path
from uuid import uuid4

from .client import Remote, Replica, private_file
from .models import Failure
from .protocol import canonical

NAME = "agents-memory-cloud"


def default_root():
    if os.name == "nt":
        return Path(os.environ["LOCALAPPDATA"]) / NAME
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / NAME
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / NAME


def write_private(path, text, *, exclusive=False):
    path = path.absolute()
    private_file(path)
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if exclusive and path.exists():
        raise Failure(409, "output_already_exists")
    temp = path.with_name(path.name + ".tmp-" + uuid4().hex)
    try:
        with os.fdopen(os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temp, path)
            temp.unlink()
        else:
            os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def host_config(client, project, connection, state, project_name):
    paths = {"claude": project / ".mcp.json", "codex": project / ".codex/config.toml", "omp": project / ".omp/mcp.json"}
    path = paths[client]
    # Host config is allowed to be publicly readable, but never a symlink or a
    # shared/hardlinked file. It contains paths only, never a key.
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise Failure(400, "unsafe_host_config_path")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1
                          or (os.name != "nt" and path.stat().st_uid != os.getuid())):
        raise Failure(400, "unsafe_host_config_path")
    raw = path.read_text() if path.exists() else ""
    data = tomllib.loads(raw) if client == "codex" else json.loads(raw or "{}")
    key = "mcp_servers" if client == "codex" else "mcpServers"
    args = ["-m", "agents_memory_collab.cli", "mcp", "--connection", str(connection), "--state", str(state), "--project", project_name]
    desired = {"command": sys.executable, "args": args}
    existing = data.get(key, {}).get(NAME)
    if existing is not None:
        if any(existing.get(k) != v for k, v in desired.items()) or existing.get("enabled") is False:
            raise Failure(409, "existing_mcp_config_differs")
        return path, raw, None
    if client == "codex":
        output = raw + f"\n[mcp_servers.{NAME}]\ncommand = {json.dumps(sys.executable)}\nargs = {json.dumps(args)}\nstartup_timeout_sec = 120\ntool_timeout_sec = 120\n"
        tomllib.loads(output)
    else:
        data.setdefault(key, {})[NAME] = {"type": "stdio", **desired}
        if client == "omp":
            data[key][NAME].update(instructions=True, timeout=120000)
        output = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return path, raw, output


def install(args):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.profile):
        raise Failure(400, "invalid_profile")
    # Native Windows ACL protection has not been validated. WSL2 takes the
    # Linux path and stores secrets in its Linux home, not /mnt/c.
    if os.name == "nt":
        raise Failure(400, "use_wsl2_for_private_client_state")
    clients = args.client
    if not clients:
        if not sys.stdin.isatty():
            raise Failure(400, "choose_client_claude_codex_omp_or_all")
        clients = [input("MCP 연결 앱 [claude / codex / omp / all]: ").strip()]
    clients = ["claude", "codex", "omp"] if "all" in clients else list(dict.fromkeys(clients))
    if any(c not in {"claude", "codex", "omp"} for c in clients):
        raise Failure(400, "invalid_client")
    root = (args.root or default_root()).absolute() / args.profile
    connection, state = root / "connection.json", root / "replica.sqlite"
    project = args.project.absolute()
    if not project.is_dir():
        raise Failure(400, "project_directory_required")
    project_name = args.project_name or project.name
    # Validate every host destination before issuing or writing a credential.
    plans = [host_config(c, project, connection, state, project_name) for c in clients]
    private_file(connection)
    replacing = connection.exists() and getattr(args, "replace_credential", False)
    previous = None
    if replacing:
        saved = json.loads(connection.read_text())
        old = Replica(state, Remote(saved["url"], saved["token"]))
        try:
            previous = old._state()
        finally:
            old.close()
        if not previous:
            raise Failure(409, "unbound_profile_cannot_replace_credential")
    if connection.exists() and not replacing:
        saved = json.loads(connection.read_text())
        if args.url and args.url.rstrip("/") != saved["url"]:
            raise Failure(409, "destination_changed_choose_new_profile")
        remote = Remote(saved["url"], saved["token"])
        identity = remote.request("/v1/me")
    else:
        if args.credential_file:
            private_file(args.credential_file)
            value = json.loads(args.credential_file.read_text())
            url, token = args.url or value["url"], value["token"]
        else:
            url = args.url or (previous["server"] if previous else input("서버 HTTPS 주소: ").strip())
            if not sys.stdin.isatty():
                raise Failure(400, "credential_file_or_interactive_terminal_required")
            token = getpass.getpass("이 PC의 기기 키 (숨김 입력, Enter로 확인): ").strip()
        print("서버와 계정을 확인하고 있습니다…", file=sys.stderr, flush=True)
        remote = Remote(url, token)
        identity = remote.request("/v1/me")
        if previous and (previous["server"], previous["user"], previous["installation"]) != (remote.url, identity["user_id"], identity["installation_id"]):
            raise Failure(409, "destination_changed_choose_new_profile")
        if identity["manage_keys"]:
            device = remote.request("/v1/devices", {"name": args.device_name or socket.gethostname(), "writable": True})
            remote = Remote(remote.url, device["token"])
        write_private(connection, canonical({"url": remote.url, "token": remote.token}) + "\n", exclusive=not replacing)
    replica = Replica(state, remote)
    try:
        if getattr(args, "recover", False) and replica._state():
            replica.recover()
        else:
            replica.connect()
        result = replica.cycle()
    except Failure as error:
        if error.code not in {"server_history_changed", "legacy_replica_requires_recovery", "legacy_unbound_queue_requires_explicit_export"}:
            raise
        result = {"state": "recovery_required", "error": error.code, "queue_preserved": True,
                  "next": "Run this setup command again with --recover. An unbound legacy queue must first be saved with sync export-pending."}
    finally:
        replica.close()
    for path, raw, output in plans:
        if output is None:
            continue
        if (path.read_text() if path.exists() else "") != raw:
            raise Failure(409, "host_config_changed_retry_setup")
        if raw:
            write_private(path.with_name(path.name + ".am-backup-" + uuid4().hex), raw, exclusive=True)
        # Only paths are in host config. Preserve a private backup before replacing.
        if path.exists():
            path.chmod(0o600)
        write_private(path, output)
    return {"ready": result["state"] == "synced", "profile": args.profile, "clients": clients,
            "project": project_name, "config_files": [str(p[0]) for p in plans],
            "next": "Reload MCP or restart the selected app. Settings persist across upgrades.", "sync": result}
