"""Public installation and MCP transport wrapper; memory behavior stays in the pinned binary core."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import http.client
import json
import os
import platform
import plistlib
import pwd
import re
import secrets
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import tomllib
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import unquote, urlsplit

VERSION = "1.0.3"
CORE_VERSION = "1.0.2"
PRODUCT = "agents-memory-hindsight-local"
PREFIX = Path.home() / ".local/share/agents-memory-hindsight"
PG_IMAGE = "pgvector/pgvector@sha256:c29f30688a9ad961691bdf0ec1650717cc132a5814619d80f80463d6e4c42e47"
LABEL = "io.agents-memory.product-id"
NAME = "agents-memory-local"
DEFAULT_CONNECT = ["-c", 'exec "$HOME/.local/share/agents-memory-hindsight/bin/am-mcp" proxy']
MAX_FILE = 2 * 1024 * 1024


class Refused(Exception):
    pass


def private_read(path: Path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > MAX_FILE):
        raise Refused("Private installation file ownership/permissions are invalid")
    return path.read_bytes()


def read_json(path):
    return json.loads(private_read(path))


def safe_parents(path):
    for parent in (path, *path.parents):
        if parent.is_symlink():
            raise Refused("Symbolic links are not allowed in configuration paths")


def write_private(path, data):
    safe_parents(path.parent)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        private_read(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("xb") as stream:
            os.chmod(temporary, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path, data):
    write_private(path, (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode())


def run(args, *, env=None, cwd=None, input_data=None, timeout=180):
    result = subprocess.run(args, env=env, cwd=cwd, input=input_data, capture_output=True,
                            timeout=timeout, check=False)
    if result.returncode:
        # Provider, database and Docker errors may contain credentials. Keep the details private.
        raise Refused("Operation failed; inspect the private service log or run status")
    return result.stdout


def owner(prefix, *, versions=(CORE_VERSION,)):
    if not prefix.is_absolute() or prefix.resolve() != prefix:
        raise Refused("Choose an absolute installation prefix without symbolic links")
    info = prefix.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise Refused("Installation directory must be owned by you and private")
    marker = read_json(prefix / "PRODUCT.json")
    if (marker.get("product") != PRODUCT or not isinstance(marker.get("id"), str)
            or len(marker["id"]) != 32 or any(c not in "0123456789abcdef" for c in marker["id"])):
        raise Refused("Unexpected installation identity")
    current = (prefix / "current").resolve(strict=True)
    if not current.is_relative_to(prefix / "installs"):
        raise Refused("Installation pointer escaped its owned directory")
    ready = read_json(current / "READY.json")
    if (ready.get("product_id") != marker["id"] or ready.get("install_id") != current.name
            or ready.get("version") not in versions):
        raise Refused("Install the pinned local binary core 1.0.2 first")
    manifest = current / "payload/MANIFEST.json"
    if hashlib.sha256(manifest.read_bytes()).hexdigest() != ready["manifest_sha256"]:
        raise Refused("Installation manifest changed")
    return marker


@contextmanager
def locked(prefix):
    path = prefix / "settings/mcp-setup.lock"
    if path.exists() or path.is_symlink():
        private_read(path)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Refused("Another MCP setup operation is active") from None
        yield
    finally:
        os.close(descriptor)


def available_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def database_valid(value):
    try:
        parsed = urlsplit(value)
        name = unquote(parsed.path.removeprefix("/"))
        valid = (parsed.scheme in {"postgres", "postgresql"}
                 and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                 and parsed.port != 0 and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,62}", name)
                 and name.lower() not in {"postgres", "template0", "template1", "database", "your_database"}
                 and not parsed.query and not parsed.fragment and not any(c.isspace() for c in value))
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise Refused("DATABASE_URL must select a dedicated existing loopback PostgreSQL database")
    return value


def docker(prefix, *args, timeout=180):
    state = read_json(prefix / "settings/mcp-database.json")
    endpoint = state["docker_endpoint"]
    if not endpoint.startswith("unix:///"):
        raise Refused("Managed PostgreSQL requires a local Unix Docker socket")
    environment = {k: v for k, v in os.environ.items() if k not in {
        "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH"}}
    return run([state["docker_executable"], "--host=" + endpoint, *args], env=environment, timeout=timeout)


def docker_endpoint(executable):
    if os.environ.get("DOCKER_HOST"):
        endpoint = os.environ["DOCKER_HOST"]
    else:
        context = os.environ.get("DOCKER_CONTEXT")
        args = [executable, "context", "inspect"] + ([context] if context else [])
        args.extend(["--format", "{{json .Endpoints.docker.Host}}"])
        endpoint = json.loads(run(args, timeout=15))
    if not isinstance(endpoint, str) or not endpoint.startswith("unix:///"):
        raise Refused("Select a local Docker context; remote Docker is not supported")
    return endpoint


def inspect_docker(prefix, kind, name):
    # docker inspect errors are not proof that the resource is absent (daemon might be down).
    docker(prefix, "info", "--format", "{{.ServerVersion}}", timeout=20)
    names = docker(prefix, kind, "ls", "--format", "{{.Name}}" if kind == "volume" else "{{.Names}}",
                   *([] if kind == "volume" else ["--all"])).decode().splitlines()
    if name not in names:
        return None
    return json.loads(docker(prefix, kind, "inspect", name))[0]


def ensure_database(prefix, *, provision=False):
    identity = owner(prefix)["id"]
    path = prefix / "settings/mcp-database.json"
    if not path.exists():
        if not provision:
            raise Refused("Run MCP setup before connecting")
        external = os.environ.get("DATABASE_URL")
        if external:
            write_json(path, {"mode": "external", "url": database_valid(external), "product_id": identity})
        else:
            executable = shutil.which("docker")
            if not executable:
                raise Refused("Start Docker Desktop, or provide a dedicated local DATABASE_URL, then rerun setup")
            endpoint = docker_endpoint(executable)
            password = secrets.token_urlsafe(32)
            port = available_port()
            name = "am-hindsight-" + identity[:16]
            write_json(path, {"mode": "docker", "product_id": identity, "image": PG_IMAGE,
                             "docker_endpoint": endpoint, "docker_executable": str(Path(executable).resolve()),
                             "container": name, "volume": name + "-data", "port": port,
                             "url": f"postgresql://am_local:{password}@127.0.0.1:{port}/am_hindsight_local"})
            write_private(prefix / "settings/mcp-postgres.env",
                          f"POSTGRES_USER=am_local\nPOSTGRES_PASSWORD={password}\nPOSTGRES_DB=am_hindsight_local\n".encode())
    state = read_json(path)
    if state.get("product_id") != identity:
        raise Refused("Database receipt identity mismatch")
    database_valid(state["url"])
    if state["mode"] == "external":
        return state["url"]
    if state.get("mode") != "docker" or state.get("image") != PG_IMAGE:
        raise Refused("Unsupported database receipt; existing state was preserved")
    parsed = urlsplit(state["url"])
    if (parsed.hostname != "127.0.0.1" or parsed.port != state["port"] or parsed.username != "am_local"
            or parsed.path != "/am_hindsight_local" or not re.fullmatch(r"[A-Za-z0-9_-]{20,128}", parsed.password or "")):
        raise Refused("Managed database URL no longer matches its owned receipt")
    environment_path = prefix / "settings/mcp-postgres.env"
    environment_data = ("POSTGRES_USER=am_local\nPOSTGRES_PASSWORD=" + parsed.password
                        + "\nPOSTGRES_DB=am_hindsight_local\n").encode()
    if not environment_path.exists() and provision:
        write_private(environment_path, environment_data)
    if private_read(environment_path) != environment_data:
        raise Refused("Managed database credential file changed; existing data was preserved")
    volume = inspect_docker(prefix, "volume", state["volume"])
    if volume is None:
        if not provision:
            raise Refused("Managed database volume is absent; rerun setup")
        docker(prefix, "volume", "create", "--label", LABEL + "=" + identity, state["volume"])
    elif volume.get("Labels", {}).get(LABEL) != identity:
        raise Refused("Refusing to adopt an unrelated database volume")
    container = inspect_docker(prefix, "container", state["container"])
    if container is None:
        if not provision:
            raise Refused("Managed database container is absent; rerun setup")
        docker(prefix, "create", "--name", state["container"], "--label", LABEL + "=" + identity,
               "--env-file", str(prefix / "settings/mcp-postgres.env"),
               "--publish", f"127.0.0.1:{state['port']}:5432",
               "--mount", f"type=volume,source={state['volume']},target=/var/lib/postgresql", PG_IMAGE,
               timeout=600)
        container = inspect_docker(prefix, "container", state["container"])
    labels = container["Config"].get("Labels") or {}
    bindings = container["HostConfig"].get("PortBindings", {}).get("5432/tcp")
    mounts = [m for m in container.get("Mounts", []) if m.get("Name") == state["volume"]
              and m.get("Destination") == "/var/lib/postgresql" and m.get("Type") == "volume"]
    if (labels.get(LABEL) != identity or container["Config"]["Image"] != PG_IMAGE
            or bindings != [{"HostIp": "127.0.0.1", "HostPort": str(state["port"])}] or len(mounts) != 1):
        raise Refused("Managed container identity, image, storage or loopback binding changed")
    if not container["State"]["Running"]:
        docker(prefix, "start", state["container"])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            docker(prefix, "exec", state["container"], "pg_isready", "-U", "am_local", "-d", "am_hindsight_local",
                   timeout=10)
            return state["url"]
        except Refused:
            time.sleep(.5)
    raise Refused("PostgreSQL is not ready; persistent data was preserved")


def install_core(args):
    prefix = args.prefix
    if (prefix / "PRODUCT.json").exists():
        owner(prefix, versions=("1.0.0", "1.0.1", CORE_VERSION))
        installed = read_json((prefix / "current").resolve() / "READY.json")["version"]
        if installed == CORE_VERSION:
            profile = read_json(prefix / "settings/profile.json")
            for key, value in (("provider", args.provider), ("subscription_host", args.judge_host), ("model", args.model)):
                default = "codex" if key == "subscription_host" else None
                if value and profile.get(key, default) != value:
                    raise Refused("Existing provider/model is preserved; use am-hindsight configure to change it explicitly")
            if args.executable and Path(args.executable).expanduser().resolve() != Path(profile.get("codex_executable") or "/").resolve():
                raise Refused("Existing judge executable is preserved; use am-hindsight configure to change it explicitly")
            return
    if args.bundle is None:
        raise Refused("Use the published install.sh to download and verify the pinned binary core")
    command = [sys.executable, "-I", str(args.bundle / "installer.py"), "--bundle", str(args.bundle),
               "--prefix", str(prefix)]
    for option, value in (("--provider", args.provider), ("--host", args.judge_host),
                          ("--model", args.model), ("--executable", args.executable)):
        if value:
            command.extend([option, value])
    if args.virtual_linux:
        command.append("--virtual-linux")
    subprocess.run(command, check=True, timeout=1200)
    owner(prefix)


def install_helper(prefix):
    source = Path(__file__).read_bytes()
    directory = prefix / "integration" / (VERSION + "-" + uuid.uuid4().hex)
    directory.mkdir(parents=True, mode=0o700)
    write_private(directory / "setup.py", source)
    temporary = prefix / "integration" / (".current-" + uuid.uuid4().hex)
    temporary.symlink_to(directory.name)
    os.replace(temporary, prefix / "integration/current")
    command = prefix / "bin/am-mcp"
    python = str(prefix / "current/venv/bin/python")
    helper = str(prefix / "integration/current/setup.py")
    write_private(command, ("#!/bin/sh\nexec " + shlex.quote(python) + " -I " + shlex.quote(helper)
                            + " --prefix " + shlex.quote(str(prefix)) + " \"$@\"\n").encode())
    command.chmod(0o700)


def project_record(prefix, project):
    records = read_json(prefix / "settings/mcp-projects.json")
    # A host may launch its plugin from a subdirectory of the explicitly configured project.
    for candidate in (project, *project.parents):
        item = records.get(str(candidate))
        if item:
            expected = hashlib.sha256(os.fsencode(candidate)).hexdigest()[:24]
            if item.get("bank") != "project-" + expected or item.get("project") != str(candidate):
                raise Refused("Project routing receipt changed")
            profile = read_json(prefix / "settings/profile.json")
            url = f"http://127.0.0.1:{profile['api_port']}/mcp/{item['bank']}/"
            if item.get("mcp_url") != url:
                raise Refused("Project service binding changed; rerun setup")
            return item
    raise Refused("This project is not configured; run agents-memory-local setup for this project")


def ready(prefix):
    profile = read_json(prefix / "settings/profile.json")
    connection = http.client.HTTPConnection("127.0.0.1", profile["api_port"], timeout=2)
    try:
        connection.request("GET", "/health/ready")
        response = connection.getresponse()
        response.read(8192)
        return response.status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def launch_details(prefix):
    identity = owner(prefix)["id"]
    label = "io.agents-memory.local." + identity[:16]
    path = Path.home() / "Library/LaunchAgents" / (label + ".plist")
    return label, path


def stop_agent(prefix):
    label, path = launch_details(prefix)
    if path.exists():
        configured = plistlib.loads(private_read(path))
        expected = [str(prefix / "bin/am-mcp"), "service-run"]
        if configured.get("Label") != label or configured.get("ProgramArguments") != expected:
            raise Refused("LaunchAgent receipt changed; refusing to stop an unrelated service")
    domain = f"gui/{os.getuid()}/{label}"
    exists = subprocess.run(["launchctl", "print", domain], capture_output=True, check=False).returncode == 0
    if exists:
        if not path.exists():
            raise Refused("An unowned LaunchAgent uses this label; refusing to stop it")
        run(["launchctl", "bootout", domain], timeout=30)
        deadline = time.monotonic() + 30
        while ready(prefix) and time.monotonic() < deadline:
            time.sleep(.2)
        if ready(prefix):
            raise Refused("Owned service has not stopped; configuration was preserved")
    return exists



def wait_service_ports(prefix):
    profile = read_json(prefix / "settings/profile.json")
    deadline = time.monotonic() + 90
    while True:
        try:
            for port in (profile["api_port"], profile["worker_port"]):
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", port))
            return
        except OSError:
            if time.monotonic() >= deadline:
                raise Refused("Previous local API connections have not released their ports; retry setup shortly") from None
            time.sleep(.5)


def require_service_credentials(prefix):
    profile = read_json(prefix / "settings/profile.json")
    if profile["provider"] != "jev":
        return
    credential = prefix / "settings/jev-credential.json"
    if credential.exists():
        value = read_json(credential)
        if value.get("schema_version") != 1 or not isinstance(value.get("api_key"), str) or not value["api_key"].strip():
            raise Refused("Saved Jev credential is invalid; replace it using hidden terminal input")
        return
    if not sys.stdin.isatty():
        raise Refused("Jev background service needs a saved key: run am-hindsight configure --jev-key in your terminal")
    subprocess.run([str(prefix / "current/bin/am-hindsight"), "configure", "--jev-key"], check=True, timeout=300)


def start_agent(prefix):
    label, path = launch_details(prefix)
    logs = prefix / "integration/logs"
    logs.mkdir(parents=True, mode=0o700, exist_ok=True)
    account = pwd.getpwuid(os.getuid()).pw_name
    environment = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(Path.home()),
                   "USER": account, "LOGNAME": account}
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "http_proxy", "https_proxy",
                "all_proxy", "no_proxy", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
                "NODE_EXTRA_CA_CERTS", "CURL_CA_BUNDLE"):
        if os.environ.get(key):
            environment[key] = os.environ[key]
    config = {"Label": label, "EnvironmentVariables": environment, "ProgramArguments": [str(prefix / "bin/am-mcp"), "service-run"],
              "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 15,
              "WorkingDirectory": str(prefix), "StandardOutPath": str(logs / "service.log"),
              "StandardErrorPath": str(logs / "service.log"), "Umask": 0o077}
    write_private(path, plistlib.dumps(config))
    write_json(prefix / "settings/mcp-service.json", {"enabled": True, "product_id": owner(prefix)["id"]})
    run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], timeout=30)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if ready(prefix):
            return
        time.sleep(.5)
    raise Refused("Service is not ready; inspect am-mcp status and its private log")


def configure_client(project, prefix, client, *, dry_run=False):
    if client == "claude-plugin":
        if prefix != PREFIX:
            raise Refused("Marketplace plugin uses the default prefix; use --client claude for a custom prefix")
        # Installed plugin discovers the per-project receipt through its stdio launcher.
        return {"client": client, "registration": "marketplace plugin transport; install the plugin and reconnect MCP"}
    paths = {"claude": project / ".mcp.json", "codex": project / ".codex/config.toml",
             "omp": project / ".omp/mcp.json"}
    path = paths[client]
    safe_parents(path)
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_size > MAX_FILE:
            raise Refused("Existing host configuration ownership/type is invalid")
        raw = path.read_bytes()
    else:
        raw = b""
    command = str(prefix / "bin/am-mcp")
    arguments = ["proxy", "--project", str(project)]
    if prefix == PREFIX:
        command, arguments = "/bin/bash", DEFAULT_CONNECT
    desired = {"command": command, "args": arguments}
    data = tomllib.loads(raw.decode()) if client == "codex" else json.loads(raw or b"{}")
    key = "mcp_servers" if client == "codex" else "mcpServers"
    servers = data.get(key, {})
    if not isinstance(servers, dict):
        raise Refused("Existing MCP configuration is malformed")
    existing = servers.get(NAME)
    if existing is not None:
        if (existing.get("command") != command or existing.get("args") != arguments
                or existing.get("enabled") is False or NAME in data.get("disabledServers", [])):
            raise Refused("Existing same-name MCP entry differs or is disabled; no overwrite performed")
        return {"client": client, "path": str(path), "changed": False}
    if NAME in data.get("disabledServers", []):
        raise Refused("This MCP server is explicitly disabled; enable it in the host before connecting")
    if client == "codex":
        appended = ("\n[mcp_servers." + NAME + "]\ncommand = " + json.dumps(command, ensure_ascii=False)
                    + "\nargs = " + json.dumps(arguments, ensure_ascii=False) + "\nstartup_timeout_sec = 30\n"
                    + "tool_timeout_sec = 120\n")
        output = raw + appended.encode()
        tomllib.loads(output.decode())
    else:
        data.setdefault(key, {})[NAME] = {"type": "stdio", **desired}
        if client == "omp":
            data[key][NAME]["timeout"] = 120000
            data[key][NAME]["instructions"] = False
        output = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()
    if dry_run:
        return {"client": client, "path": str(path), "changed": True}
    # Preserve all unrelated fields. Back up exactly the bytes we are replacing.
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if raw:
        write_private(path.with_name(path.name + ".am-backup-" + uuid.uuid4().hex), raw)
    # Host-owned JSON/TOML may be 0644; it contains no credentials added by this installer.
    if path.exists():
        if path.read_bytes() != raw:
            raise Refused("Host configuration changed during setup; retry without overwriting it")
        path.chmod(0o600)
    write_private(path, output)
    return {"client": client, "path": str(path), "changed": True}


def setup(args):
    if not args.project.is_absolute() or not args.project.is_dir():
        raise Refused("Choose an existing absolute project directory")
    args.project = args.project.resolve()
    if platform.system() != "Darwin" and not args.virtual_linux:
        raise Refused("Production support is Apple Silicon macOS; Linux requires --virtual-linux")
    if args.virtual_linux and not args.no_start:
        raise Refused("Virtual Linux setup uses --no-start; run service-run explicitly in the test harness")
    clients = args.client
    if not clients:
        if not sys.stdin.isatty():
            raise Refused("Pass --client claude, --client codex or --client omp")
        answer = input("MCP 연결 앱 [claude / codex / omp / all]: ").strip().lower()
        clients = ["claude", "codex", "omp"] if answer == "all" else [answer]
        if any(client not in {"claude", "codex", "omp"} for client in clients):
            raise Refused("Choose Claude, Codex or OMP")
    for client in clients:
        configure_client(args.project, args.prefix, client, dry_run=True)
    install_core(args)
    with locked(args.prefix):
        receipt = args.prefix / "settings/mcp-projects.json"
        installed = args.prefix / "integration/current/setup.py"
        service_receipt = args.prefix / "settings/mcp-service.json"
        reusable = (receipt.exists() and installed.exists() and service_receipt.exists()
                    and hashlib.sha256(private_read(installed)).digest() == hashlib.sha256(Path(__file__).read_bytes()).digest()
                    and read_json(service_receipt) == {"enabled": True, "product_id": owner(args.prefix)["id"]})
        if reusable and str(args.project) in read_json(receipt) and ready(args.prefix):
            project_record(args.prefix, args.project)
            configured = [configure_client(args.project, args.prefix, client) for client in clients]
            return {"version": VERSION, "core_version": CORE_VERSION, "project": str(args.project),
                    "clients": configured, "service_ready": True, "service_reused": True,
                    "provider_settings_preserved": True, "next": "Reconnect MCP in the selected app."}
        was_running = False
        if platform.system() == "Darwin":
            was_running = stop_agent(args.prefix)
            if was_running:
                wait_service_ports(args.prefix)
        elif ready(args.prefix):
            raise Refused("Stop the virtual test API before provisioning another project")
        try:
            require_service_credentials(args.prefix)
            database = ensure_database(args.prefix, provision=True)
            install_helper(args.prefix)
            environment = dict(os.environ) | {"DATABASE_URL": database}
            command = str(args.prefix / "current/bin/am-hindsight")
            item = json.loads(run([command, "project-init", str(args.project)], env=environment))
            run([command, "bank-init", "--config", item["hook_config"]], env=environment, timeout=240)
            path = args.prefix / "settings/mcp-projects.json"
            records = read_json(path) if path.exists() else {}
            records[str(args.project)] = {k: item[k] for k in ("project", "bank", "hook_config", "mcp_url")}
            write_json(path, records)
            write_json(args.prefix / "settings/mcp-service.json",
                       {"enabled": True, "product_id": owner(args.prefix)["id"]})
            if not args.no_start:
                start_agent(args.prefix)
            configured = [configure_client(args.project, args.prefix, client) for client in clients]
            return {"version": VERSION, "core_version": CORE_VERSION, "project": str(args.project),
                    "clients": configured, "service_ready": ready(args.prefix),
                    "virtual_no_start": args.no_start, "provider_settings_preserved": True,
                    "next": "Restart/reconnect MCP in the selected app; trust this project when the host asks."}
        except BaseException:
            if was_running and not ready(args.prefix):
                try:
                    start_agent(args.prefix)
                except (Refused, OSError, subprocess.SubprocessError):
                    print("Previous service could not be restarted; inspect am-mcp status.", file=sys.stderr)
            raise


def service_run(prefix):
    identity = owner(prefix)["id"]
    receipt = read_json(prefix / "settings/mcp-service.json")
    if receipt != {"enabled": True, "product_id": identity}:
        raise Refused("Service was explicitly stopped; run am-mcp start to enable it")
    records = read_json(prefix / "settings/mcp-projects.json")
    if not records:
        raise Refused("Configure a project before starting the API")
    database = ensure_database(prefix)
    bank = next(iter(records.values()))["bank"]
    child = subprocess.Popen([str(prefix / "current/bin/am-hindsight"), "serve", "--bank", bank],
                             env=dict(os.environ) | {"DATABASE_URL": database}, start_new_session=True)

    def terminate(signum, frame):
        del signum, frame
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)

    old = {sig: signal.signal(sig, terminate) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        return child.wait()
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)
        if child.poll() is None:
            terminate(None, None)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


async def proxy(prefix, project):
    owner(prefix)
    item = project_record(prefix, project.resolve())
    if not ready(prefix):
        raise Refused("Local API is not ready; run am-mcp status or am-mcp start")
    import httpx2
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server

    async with httpx2.AsyncClient(trust_env=False, follow_redirects=False, timeout=120) as http:  # noqa: SIM117 - keep transport/session lifetimes explicit
        async with streamable_http_client(item["mcp_url"], http_client=http) as streams:
            read, write = streams[:2]
            async with ClientSession(read, write, read_timeout_seconds=120) as session:
                await session.initialize()

                async def list_tools(ctx, params):
                    del ctx, params
                    return await session.list_tools()

                async def call_tool(ctx, params):
                    del ctx
                    return await session.call_tool(params.name, params.arguments)

                server = Server(NAME, version=VERSION, on_list_tools=list_tools, on_call_tool=call_tool)
                async with stdio_server() as (incoming, outgoing):
                    await server.run(incoming, outgoing, server.create_initialization_options())


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--prefix", type=Path, default=PREFIX)
    commands = result.add_subparsers(dest="command", required=True)
    command = commands.add_parser("setup", help="Install core, prepare DB/service and register the selected MCP apps")
    command.add_argument("--prefix", type=Path, default=argparse.SUPPRESS)
    command.add_argument("--project", type=Path, required=True)
    command.add_argument("--client", action="append", choices=("claude", "codex", "omp", "claude-plugin"))
    command.add_argument("--bundle", type=Path)
    command.add_argument("--provider", choices=("jev", "local-llm"))
    command.add_argument("--judge-host", choices=("claude", "codex"))
    command.add_argument("--model")
    command.add_argument("--executable")
    command.add_argument("--virtual-linux", action="store_true")
    command.add_argument("--no-start", action="store_true", help="Prepare only; does not claim a working MCP connection")
    command = commands.add_parser("proxy", help="Stdio MCP transport to the configured project's local API")
    command.add_argument("--project", type=Path, default=Path.cwd())
    for name in ("status", "start", "stop", "service-run"):
        commands.add_parser(name)
    return result


def main(argv=None):
    os.umask(0o077)
    args = parser().parse_args(argv)
    args.prefix = args.prefix.expanduser().absolute()
    try:
        if args.command == "setup":
            output = setup(args)
        elif args.command == "proxy":
            asyncio.run(proxy(args.prefix, args.project))
            return 0
        elif args.command == "service-run":
            return service_run(args.prefix)
        elif args.command == "status":
            owner(args.prefix)
            output = {"version": VERSION, "service_ready": ready(args.prefix),
                      "service": read_json(args.prefix / "settings/mcp-service.json"),
                      "projects": list(read_json(args.prefix / "settings/mcp-projects.json")),
                      "log": str(args.prefix / "integration/logs/service.log")}
        else:
            if platform.system() != "Darwin":
                raise Refused("start/stop manage macOS LaunchAgents; virtual harnesses own service-run directly")
            with locked(args.prefix):
                owner(args.prefix)
                if args.command == "stop":
                    write_json(args.prefix / "settings/mcp-service.json",
                               {"enabled": False, "product_id": owner(args.prefix)["id"]})
                    stop_agent(args.prefix)
                    _, path = launch_details(args.prefix)
                    if path.exists():
                        stopped = plistlib.loads(private_read(path))
                        stopped.update(RunAtLoad=False, KeepAlive=False)
                        write_private(path, plistlib.dumps(stopped))
                else:
                    stop_agent(args.prefix)
                    start_agent(args.prefix)
            output = {"service_ready": ready(args.prefix), "command": args.command}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print("MCP setup cancelled; existing data was preserved.", file=sys.stderr)
        return 130
    except Refused as error:
        print("agents-memory-local: " + str(error), file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001 - third-party errors can include credentials or source text
        print("agents-memory-local: operation refused; inspect private configuration and service status.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
