"""Owned common-runtime installation and lifecycle; credentials never enter stdout."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

DEFAULT = Path.home() / ".local/share/agents-memory-unified"
MODELS = {"claude": "claude-fable-5-1", "codex": "gpt-6.1-terra", "jev": "jev-1.14.0"}


def module(path, name):
    # Execute verified source bytes, never an unverified adjacent __pycache__.
    value = ModuleType(name)
    value.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), "exec"), value.__dict__)  # noqa: S102 - verified, owned release source
    return value


def helper(bundle):
    return module(bundle / "runtime-helper.py", "unified_runtime_helper")


def verify(bundle):
    manifest = json.loads((bundle / "ASSETS.json").read_text())
    for name, digest in manifest["files"].items():
        path = bundle / name
        if path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()):
            raise ValueError("Release asset escaped bundle")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("Release integrity check failed")
    return manifest


def read_settings(prefix):
    # The copied helper is verified at install time and lives in the owned
    # integration directory, outside any plugin cache.
    pointer = prefix / "unified-current"
    if not pointer.is_symlink():
        raise ValueError("Setup required")
    current = pointer.resolve(strict=True)
    if not current.is_relative_to(prefix / "unified-installs"):
        raise ValueError("Invalid runtime pointer")
    verify(current / "bundle")
    h = helper(current / "bundle")
    config = h.read_json(prefix / "settings/unified.json")
    if config["product_id"] != h.owner(prefix)["id"]:
        raise ValueError("Installation identity mismatch")
    return current, h, config


def service_environment(prefix, h, config):
    environment = dict(os.environ)
    environment.update(
        AM_COLLAB_DATABASE_URL=h.read_json(prefix / "settings/mcp-database.json")[
            "url"
        ],
        AM_MEMORY_PROVIDER=config["provider"],
        AM_MEMORY_MODEL=config["model"],
        AM_MEMORY_WORKDIR=str(prefix / "settings/judge-runs"),
        PATH=config["path"],
    )
    environment.pop("PYTHONPATH", None)
    if config["provider"] == "jev":
        environment["AM_MEMORY_JEV_KEY_FILE"] = str(
            prefix / "settings/jev-credential.json"
        )
    else:
        environment["AM_MEMORY_EXECUTABLE"] = config["executable"]
    return environment


def run_service(prefix):
    current, h, config = read_settings(prefix)
    # This validates ownership before starting/reusing the existing native DB.
    h.ensure_database(prefix, provision=False)
    python = current / "gateway/bin/python"
    command = [
        str(python),
        "-m",
        "agents_memory.runtime_launcher",
        "--mode",
        config["mode"],
        "--hindsight-python",
        str(prefix / "current/venv/bin/python"),
        "--gateway-python",
        str(python),
        "--e5-dir",
        str(prefix / "current/payload/models/e5-small"),
        "--e5-manifest",
        str(current / "bundle/e5-assets.sha256.json"),
        "--port",
        str(config["port"]),
        "--hindsight-port",
        str(config["hindsight_port"]),
        "--host",
        config["host"],
        "--public-url",
        config["public_url"],
    ]
    os.execve(python, command, service_environment(prefix, h, config))


def health(config):
    request = urllib.request.Request(
        "http://127.0.0.1:" + str(config["port"]) + "/healthz",
        headers={"Host": urlsplit(config["public_url"]).netloc},
    )
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(
        request, timeout=2
    ) as reply:
        return json.load(reply)


def owned_pid(prefix, h):
    path = prefix / "settings/unified-pid.json"
    if not path.exists():
        return None
    receipt = h.read_json(path)
    pid = receipt["pid"]
    if receipt["product_id"] != h.owner(prefix)["id"]:
        raise ValueError("PID ownership mismatch")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    if Path("/proc").is_dir():
        try:
            proc = Path("/proc") / str(pid)
            if (proc / "stat").read_text().rsplit(") ", 1)[1].split()[0] in {"Z", "X"}:
                return None
            command = (proc / "cmdline").read_bytes()
        except FileNotFoundError:
            return None
    else:
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="], capture_output=True, check=True
        ).stdout
    if str(prefix).encode() not in command or not any(
        name in command for name in (b"runtime_launcher", b"unified_setup.py")
    ):
        raise ValueError("Saved PID now belongs to another process")
    return pid


def stop(prefix):
    _, h, _ = read_settings(prefix)
    pid = owned_pid(prefix, h)
    if pid:
        os.kill(pid, signal.SIGTERM)
        for _ in range(600):
            if owned_pid(prefix, h) is None:
                break
            time.sleep(0.1)
        else:
            raise ValueError("Owned service did not stop")
    (prefix / "settings/unified-pid.json").unlink(missing_ok=True)


def ensure(prefix):
    current, h, config = read_settings(prefix)
    with h.locked(prefix, "unified-service-start.lock"):
        if owned_pid(prefix, h) is None:
            log = prefix / "settings/unified-service.log"
            if not log.exists():
                h.write_private(log, b"")
            with log.open("ab") as output:
                process = subprocess.Popen(
                    [
                        str(prefix / "current/venv/bin/python"),
                        "-I",
                        str(current / "bundle/unified_setup.py"),
                        "service",
                        "--prefix",
                        str(prefix),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            h.write_json(
                prefix / "settings/unified-pid.json",
                {"pid": process.pid, "product_id": config["product_id"]},
            )
    for _ in range(1200):
        try:
            state = health(config)
            if state.get("ready"):
                return state
        except (OSError, ValueError):
            pass
        if owned_pid(prefix, h) is None:
            raise ValueError("Service stopped; inspect the private service log")
        time.sleep(0.1)
    raise ValueError(
        "Service preparation deadline; configuration and keys were preserved"
    )


def install(args):
    bundle = args.bundle.resolve(strict=True)
    manifest = verify(bundle)
    h = helper(bundle)
    prefix = args.prefix.expanduser().absolute()
    saved_path = prefix / "settings/unified.json"
    saved = h.read_json(saved_path) if saved_path.exists() else None
    provider = args.provider or (saved["provider"] if saved else None)
    if provider is None:
        if not sys.stdin.isatty():
            raise ValueError(
                "Select --provider claude|codex|jev; keys are never requested in chat"
            )
        provider = {"1": "claude", "2": "codex", "3": "jev"}.get(
            input("기억 처리 공급자: 1) Claude CLI  2) Codex CLI  3) Jev: ").strip()
        )
    if provider not in MODELS:
        raise ValueError("Select Claude, Codex or Jev")
    model = args.model or (saved["model"] if saved else MODELS[provider])
    if saved and (provider, model) != (saved["provider"], saved["model"]):
        raise ValueError(
            "Update preserves the saved provider/model; it cannot silently switch suppliers"
        )
    executable = (
        None
        if provider == "jev"
        else args.executable
        or (saved["executable"] if saved else shutil.which(provider))
    )
    if provider != "jev" and (not executable or not Path(executable).is_file()):
        raise ValueError(
            "Install and log in to the selected CLI on this host; no OAuth files are copied"
        )
    key = None
    if provider == "jev" and not (prefix / "settings/jev-credential.json").exists():
        if args.jev_key_file:
            raw = h.private_read(args.jev_key_file).decode().strip()
            key = json.loads(raw)["api_key"] if raw.startswith("{") else raw
        elif sys.stdin.isatty():
            key = getpass.getpass("Jev API 키 (입력 숨김, Enter로 확정): ")
        else:
            raise ValueError(
                "A private --jev-key-file or secure terminal input is required"
            )
    # Reuse the pinned, hash-locked Python/Hindsight/E5 bootstrap. Its old
    # memory binary is never started: the new package supplies the actual engine.
    bootstrap = [
        sys.executable,
        "-I",
        str((args.bootstrap_bundle or Path("/nonexistent")) / "installer.py"),
        "--bundle",
        str(args.bootstrap_bundle),
        "--prefix",
        str(prefix),
        "--provider",
        "jev" if provider == "jev" else "local-llm",
        "--model",
        model,
    ]
    if provider != "jev":
        bootstrap.extend(
            ["--host", provider, "--executable", str(Path(executable).absolute())]
        )
    if platform.system() == "Linux":
        bootstrap.append("--virtual-linux")
    environment = dict(os.environ)
    if key is not None:
        environment["HINDSIGHT_API_MEMORY_ADMISSION_API_KEY"] = key
    prefix.parent.mkdir(parents=True, exist_ok=True)
    existing = (prefix / "PRODUCT.json").exists()
    if existing:
        h.owner(prefix)
    with h.phase("Python 실행환경과 검색 임베딩 준비"):
        # Suppress the bootstrap component's version banner, never hidden input.
        if not existing:
            if args.bootstrap_bundle is None:
                raise ValueError(
                    "A verified bootstrap bundle is required for first installation"
                )
            result = subprocess.run(
                bootstrap,
                check=False,
                env=environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=1200,
            )
            if result.returncode:
                raise ValueError(
                    "Runtime bootstrap failed; existing files were preserved"
                )
    h.owner(prefix)
    if key is not None:
        h.write_json(
            prefix / "settings/jev-credential.json",
            {"schema_version": 1, "api_key": key},
        )
    prefix.joinpath("settings/judge-runs").mkdir(mode=0o700, exist_ok=True)
    # Native DB setup must never silently adopt an inherited DATABASE_URL.
    inherited = os.environ.pop("DATABASE_URL", None)
    try:
        with h.phase("로컬 데이터베이스 준비"):
            h.ensure_database(prefix, provision=True)
    finally:
        if inherited is not None:
            os.environ["DATABASE_URL"] = inherited
    install_id = manifest["version"] + "-" + uuid.uuid4().hex[:12]
    target = prefix / "unified-installs" / install_id
    target.mkdir(parents=True, mode=0o700)
    shutil.copytree(bundle, target / "bundle")
    base = prefix / "current/venv/bin/python"
    python = target / "gateway/bin/python"
    with h.phase("공통 기억 엔진 설치"):
        h.run([str(base), "-m", "venv", "--without-pip", str(target / "gateway")])
        h.run(
            [
                str(base),
                "-m",
                "pip",
                "--python",
                str(python),
                "install",
                "--disable-pip-version-check",
                "--require-hashes",
                "-r",
                str(target / "bundle/client-requirements.lock"),
            ],
            timeout=600,
        )
        h.run(
            [
                str(base),
                "-m",
                "pip",
                "--python",
                str(python),
                "install",
                "--no-deps",
                str(target / "bundle" / manifest["core_313"]),
                str(target / "bundle" / manifest["sdk"]),
            ],
            timeout=120,
        )
    config = saved or {
        "product_id": h.owner(prefix)["id"],
        "provider": provider,
        "model": model,
        "executable": str(Path(executable).absolute()) if executable else None,
        "mode": args.mode,
        "host": args.host,
        "port": h.available_port(),
        "hindsight_port": h.available_port(),
        "path": os.environ.get("PATH", os.defpath),
    }
    config.setdefault(
        "public_url", args.public_url or "http://127.0.0.1:" + str(config["port"])
    )
    if args.public_url and saved and args.public_url != saved["public_url"]:
        raise ValueError("Saved connection URL is preserved on update")
    old = (
        (prefix / "unified-current").resolve()
        if (prefix / "unified-current").exists()
        else None
    )
    if old:
        stop(prefix)
    h.write_json(saved_path, config)
    pointer = prefix / (".unified-current-" + uuid.uuid4().hex)
    pointer.symlink_to("unified-installs/" + install_id)
    os.replace(pointer, prefix / "unified-current")
    try:
        with h.phase("기억 서비스 시작"):
            state = ensure(prefix)
        with h.phase("선택한 공급자 인증 확인"):
            env = service_environment(prefix, h, config)
            h.run(
                [
                    str(python),
                    "-c",
                    (
                        "import asyncio; from agents_memory.memory_processor import from_environment; "
                        "result=asyncio.run(from_environment().process('The synthetic verification application uses PostgreSQL 18 for its database.')); "
                        "assert result['decision']=='keep'"
                    ),
                ],
                env=env,
                timeout=180,
            )
    except BaseException:
        stop(prefix)
        if old:
            pointer.symlink_to(old.relative_to(prefix))
            os.replace(pointer, prefix / "unified-current")
            ensure(prefix)
        raise
    manager = prefix / "settings/unified-manager.json"
    env = service_environment(prefix, h, config)
    if not manager.exists():
        h.run(
            [
                str(python),
                "-m",
                "agents_memory_collab.cli",
                "account",
                "--name",
                "Personal memory",
                "--output",
                str(manager),
            ],
            env=env,
        )
        credentials = h.read_json(manager)
        h.write_json(
            manager, {"url": config["public_url"], "token": credentials["token"]}
        )
    if args.client:
        launcher = prefix / "bin/unified-python"
        control = [
            str(prefix / "current/venv/bin/python"),
            "-I",
            str(prefix / "unified-current/bundle/unified_setup.py"),
            "ensure",
            "--prefix",
            str(prefix),
        ]
        script = (
            "#!/bin/sh\n"
            + shlex.join(control)
            + " >>"
            + shlex.quote(str(prefix / "settings/unified-ensure.log"))
            + " 2>&1 &\n"
        )
        script += (
            "exec "
            + shlex.quote(str(prefix / "unified-current/gateway/bin/python"))
            + ' "$@"\n'
        )
        h.write_private(launcher, script.encode())
        launcher.chmod(0o700)
        command = [
            str(python),
            "-m",
            "agents_memory_collab.cli",
            "setup",
            "--root",
            str(prefix / "client"),
            "--profile",
            "local",
            "--url",
            config["public_url"],
            "--credential-file",
            str(manager),
            "--project",
            str(args.project),
            "--python-launcher",
            str(launcher),
        ]
        for client in args.client:
            command.extend(["--client", client])
        h.run(command, env=env, timeout=120)
    print(
        json.dumps(
            {
                "ready": True,
                "version": state["version"],
                "provider": provider,
                "mode": config["mode"],
                "url": config["public_url"],
                "generation_enabled": state["memory"].get("generation_enabled", False),
                "integration_enabled": state["memory"].get(
                    "integration_enabled", False
                ),
                "keys_preserved": True,
                "service_autostart": "on MCP connection; OS login service not configured",
            }
        )
    )


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["install", "service", "ensure", "stop"])
    parser.add_argument("--prefix", type=Path, default=DEFAULT)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--bootstrap-bundle", type=Path)
    parser.add_argument("--provider", choices=tuple(MODELS))
    parser.add_argument("--model")
    parser.add_argument("--executable")
    parser.add_argument("--jev-key-file", type=Path)
    parser.add_argument(
        "--mode",
        choices=["local", "personal-server", "team-server", "company-server"],
        default="local",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--public-url")
    parser.add_argument(
        "--client",
        action="append",
        choices=["claude", "codex", "omp", "all", "claude-plugin", "omp-plugin"],
    )
    parser.add_argument("--project", type=Path, default=Path.cwd())
    args = parser.parse_args()
    args.prefix = args.prefix.expanduser().absolute()
    if args.action == "install":
        install(args)
    elif args.action == "service":
        run_service(args.prefix)
    elif args.action == "ensure":
        print(json.dumps(ensure(args.prefix)))
    else:
        stop(args.prefix)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception:  # noqa: BLE001 - never print credential-bearing provider exceptions
        print(
            "Setup failed; configuration and credentials were preserved. Inspect the private installation/service logs.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
