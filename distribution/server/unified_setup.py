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
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from types import ModuleType
from urllib.parse import urlsplit

DEFAULT = Path.home() / ".local/share/agents-memory-unified"
DEFAULT_MODEL = "jev-1.14.0"


class SetupInputError(ValueError):
    pass


class ProviderMigrationRequired(SetupInputError):
    pass


def require_jev(provider):
    if provider != "jev":
        raise ProviderMigrationRequired(
            "Subscription judgment was removed. Reinstall explicitly with --provider jev "
            "--model jev-1.14.0 --jev-key-file PRIVATE_FILE; existing memories are preserved."
        )


def _require_verified_provider(config):
    require_jev(config["provider"])
    if config.get("provider_verified") is not True:
        raise SetupInputError("Jev configuration is awaiting explicit provider validation")


def _python_environment():
    return {name: value for name, value in os.environ.items() if not name.startswith("PYTHON")}


def _write_pip_python(h, target, python):
    # pip --python redispatches without the calling interpreter's -I.
    launcher = target / "pip-python"
    h.write_private(launcher, ("#!/bin/sh\nexec " + shlex.quote(str(python)) + ' -I "$@"\n').encode())
    launcher.chmod(0o700)
    return launcher


def _bootstrap(prefix, command, environment, h):
    try:
        result = subprocess.run(command, check=False, env=environment,
                                stdin=subprocess.DEVNULL, capture_output=True, timeout=1200)
    except subprocess.TimeoutExpired as error:
        result = error
    else:
        if result.returncode == 0:
            return
    diagnostic = Path(tempfile.mkdtemp(prefix="agents-memory-bootstrap-", dir=prefix.parent))
    output = bytearray()
    for name in ("stdout", "stderr"):
        value = getattr(result, name, None) or b""
        if isinstance(value, str):
            value = value.encode()
        output.extend(name.encode() + b":\n" + value[-524288:] + b"\n")
    log = diagnostic / "bootstrap.log"
    h.write_private(log, bytes(output))
    raise SetupInputError(f"Runtime bootstrap failed; private diagnostic: {log}")


def _require_free_service_ports(config):
    for name in ("port", "hindsight_port"):
        with socket.socket() as probe:
            try:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                probe.bind(("127.0.0.1", config[name]))
            except OSError:
                raise SetupInputError(
                    "A service endpoint is occupied without the selected owned process; stop that service first"
                ) from None


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
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise SetupInputError("Invalid release manifest")
    members = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise SetupInputError("Release asset escaped bundle")
        if path.is_file() and path != bundle / "ASSETS.json":
            members.add(path.relative_to(bundle).as_posix())
    if set(manifest["files"]) != members:
        raise SetupInputError("Release manifest must cover every bundled file")
    for label in ("sdk", "core_312", "core_313"):
        if label not in manifest:
            continue
        member = manifest[label]
        if (not isinstance(member, str) or not member.startswith("packages/")
                or not member.endswith(".whl") or member not in manifest["files"]):
            raise SetupInputError("Release wheel is not a reviewed manifest member")
    for name, digest in manifest["files"].items():
        path = bundle / name
        if path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()):
            raise SetupInputError("Release asset escaped bundle")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise SetupInputError("Release integrity check failed")
    return manifest


def client_requirements(bundle):
    manifest = verify(bundle)
    if ("client-requirements.lock" not in manifest["files"]
            or any(label not in manifest for label in ("sdk", "core_312"))):
        raise SetupInputError("Unified client bundle is missing required assets")
    requirements = []
    for label in ("sdk", "core_312"):
        member = manifest[label]
        distribution = Path(member).name.partition("-")[0].replace("_", "-")
        uri = (bundle / member).resolve(strict=True).as_uri()
        requirements.append(f"{distribution} @ {uri} --hash=sha256:{manifest['files'][member]}")
    return "\n".join(requirements) + "\n"


def reranker_directory(prefix, bundle):
    assets = json.loads((bundle / "reranker-assets.sha256.json").read_text())
    return prefix / "models/reranker" / assets["model.onnx"]


def install_reranker(prefix, bundle, source):
    expected = json.loads((bundle / "reranker-assets.sha256.json").read_text())
    target = reranker_directory(prefix, bundle)

    def check_files(root, *, hashes):
        if root.is_symlink() or not root.is_dir() or {p.name for p in root.iterdir()} != set(expected):
            raise SetupInputError("Choose the exact reviewed reranker asset directory")
        for name, digest in expected.items():
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise SetupInputError("Reranker assets must be regular files")
            if hashes:
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                        raise SetupInputError("Reranker integrity check failed")

    if target.exists() or target.is_symlink():
        check_files(target, hashes=True)
        return
    if source is None:
        raise SetupInputError("First installation requires --reranker-dir with the reviewed model assets")
    check_files(source, hashes=False)
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = target.parent / (".install-" + uuid.uuid4().hex)
    temporary.mkdir(mode=0o700)
    try:
        for name in expected:
            shutil.copyfile(source / name, temporary / name)
        check_files(temporary, hashes=True)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def read_settings(prefix):
    # The copied helper is verified at install time and lives in the owned
    # integration directory, outside any plugin cache.
    pointer = prefix / "unified-current"
    if not pointer.is_symlink():
        raise SetupInputError("Setup required")
    current = pointer.resolve(strict=True)
    if not current.is_relative_to(prefix / "unified-installs"):
        raise SetupInputError("Invalid runtime pointer")
    verify(current / "bundle")
    h = helper(current / "bundle")
    config = h.read_json(prefix / "settings/unified.json")
    if config["product_id"] != h.owner(prefix)["id"]:
        raise SetupInputError("Installation identity mismatch")
    return current, h, config


def service_environment(prefix, h, config):
    require_jev(config["provider"])
    environment = _python_environment()
    environment.update(
        AM_COLLAB_DATABASE_URL=h.read_json(prefix / "settings/mcp-database.json")[
            "url"
        ],
        AM_MEMORY_PROVIDER="jev",
        AM_MEMORY_MODEL=config["model"],
        AM_MEMORY_PROCESSING="integrated",
        PATH=config["path"],
    )
    for name in ("AM_MEMORY_EXECUTABLE", "AM_MEMORY_WORKDIR", "AM_MEMORY_SERVICE_INSTANCE",
                 "HINDSIGHT_API_MEMORY_ADMISSION_API_KEY"):
        environment.pop(name, None)
    environment["AM_MEMORY_JEV_KEY_FILE"] = str(prefix / "settings/jev-credential.json")
    return environment


def run_service(prefix, startup_fd=None):
    current, h, config = read_settings(prefix)
    _require_verified_provider(config)
    receipt_path = prefix / "settings/unified-pid.json"
    if startup_fd is not None:
        try:
            if os.read(startup_fd, 1):
                raise SetupInputError("Invalid service startup barrier")
        finally:
            os.close(startup_fd)
        receipt = h.read_json(receipt_path)
        if receipt["pid"] != os.getpid() or receipt["product_id"] != config["product_id"]:
            raise SetupInputError("Service startup ownership changed")
    else:
        with h.locked(prefix, "unified-service-start.lock"):
            current, h, config = read_settings(prefix)
            _require_verified_provider(config)
            if owned_pid(prefix, h) is not None:
                raise SetupInputError("The owned service is already running")
            _require_free_service_ports(config)
            receipt = {"pid": os.getpid(), "product_id": config["product_id"],
                       "instance_id": uuid.uuid4().hex}
            h.write_json(receipt_path, receipt)
    instance = receipt.get("instance_id")
    if not isinstance(instance, str) or len(instance) != 32:
        raise SetupInputError("Service instance identity is missing")
    # This validates ownership before starting/reusing the existing native DB.
    h.ensure_database(prefix, provision=False)
    python = current / "gateway/bin/python"
    command = [
        str(python),
        "-I",
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
        "--reranker-dir",
        str(reranker_directory(prefix, current / "bundle")),
        "--reranker-manifest",
        str(current / "bundle/reranker-assets.sha256.json"),
        "--port",
        str(config["port"]),
        "--hindsight-port",
        str(config["hindsight_port"]),
        "--host",
        config["host"],
        "--public-url",
        config["public_url"],
    ]
    environment = service_environment(prefix, h, config)
    environment["AM_MEMORY_SERVICE_INSTANCE"] = instance
    os.execve(python, command, environment)


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
    if type(pid) is not int or pid <= 1:
        raise SetupInputError("Invalid service PID")
    if receipt["product_id"] != h.owner(prefix)["id"]:
        raise SetupInputError("PID ownership mismatch")
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
            if not command:
                # Linux can clear cmdline while a verified process is exiting,
                # between the first stat read and the following cmdline read.
                # Require observed exit; an empty live/unrelated PID stays denied.
                if (proc / "stat").read_text().rsplit(") ", 1)[1].split()[0] in {"Z", "X"}:
                    return None
        except FileNotFoundError:
            return None
    else:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat=", "-o", "command="], capture_output=True, check=False
        )
        if result.returncode:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return None
            raise SetupInputError("Cannot verify the live owned process")
        fields = result.stdout.split(maxsplit=1)
        if not fields or fields[0].startswith((b"Z", b"X")):
            return None
        command = fields[1] if len(fields) == 2 else b""
    if str(prefix).encode() not in command or not any(
        name in command for name in (b"runtime_launcher", b"unified_setup.py")
    ):
        raise SetupInputError("Saved PID now belongs to another process")
    return pid


def stop(prefix):
    _, h, _ = read_settings(prefix)
    with h.locked(prefix, "unified-service-start.lock"):
        _stop_locked(prefix, h)


def _stop_locked(prefix, h):
    path = prefix / "settings/unified-pid.json"
    receipt = h.read_json(path) if path.exists() else None
    pid = owned_pid(prefix, h)
    if pid:
        if receipt is None or receipt["pid"] != pid:
            raise SetupInputError("Service ownership changed before stopping")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        for _ in range(600):
            if owned_pid(prefix, h) != pid:
                break
            time.sleep(0.1)
        else:
            raise SetupInputError("Owned service did not stop")
    if receipt is not None and path.exists() and h.read_json(path) == receipt:
        path.unlink()


def ensure(prefix):
    _, h, _ = read_settings(prefix)
    receipt_path = prefix / "settings/unified-pid.json"
    with h.locked(prefix, "unified-service-start.lock"):
        current, h, config = read_settings(prefix)
        _require_verified_provider(config)
        if owned_pid(prefix, h) is None:
            _require_free_service_ports(config)
            log = prefix / "settings/unified-service.log"
            if not log.exists():
                h.write_private(log, b"")
            # Release the child only after its PID and instance receipt is durable.
            read_fd, write_fd = os.pipe()
            try:
                with log.open("ab") as output:
                    process = subprocess.Popen(
                        [str(prefix / "current/venv/bin/python"), "-I",
                         str(current / "bundle/unified_setup.py"), "service", "--prefix",
                         str(prefix), "--startup-fd", str(read_fd)],
                        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                        start_new_session=True, pass_fds=(read_fd,),
                    )
                h.write_json(receipt_path, {"pid": process.pid, "product_id": config["product_id"],
                                            "instance_id": uuid.uuid4().hex})
            finally:
                os.close(read_fd)
                os.close(write_fd)
        receipt = h.read_json(receipt_path)
        instance = receipt.get("instance_id")
        if not isinstance(instance, str) or len(instance) != 32:
            raise SetupInputError("Restart the owned service to establish its instance identity")
    for _ in range(1200):
        if owned_pid(prefix, h) != receipt["pid"] or h.read_json(receipt_path) != receipt:
            raise SetupInputError("Service stopped or changed; inspect the private service log")
        try:
            state = health(config)
            if state.get("ready") and state.get("service_instance") == instance:
                return state
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    raise SetupInputError("Service preparation deadline; configuration and keys were preserved")



def _selected_configuration(args, h, prefix):
    saved_path = prefix / "settings/unified.json"
    saved = h.read_json(saved_path) if saved_path.exists() else None
    require_jev(args.provider or (saved["provider"] if saved else "jev"))
    migrating = saved is not None and saved["provider"] != "jev"
    model = args.model or (saved["model"] if saved and not migrating else DEFAULT_MODEL)
    if saved and not migrating and model != saved["model"]:
        raise SetupInputError("Update preserves the saved Jev model")
    if args.public_url and saved and args.public_url != saved["public_url"]:
        raise SetupInputError("Saved connection URL is preserved on update")
    return saved, migrating, model


def _key_value(raw):
    try:
        value = json.loads(raw)["api_key"] if raw.startswith("{") else raw
    except (ValueError, KeyError, TypeError):
        raise SetupInputError("Choose a private Jev key file containing a key or api_key JSON field") from None
    if (not isinstance(value, str) or not 1 <= len(value) <= 4096
            or any(not 33 <= ord(character) <= 126 for character in value)):
        raise SetupInputError("Jev key must contain 1..4096 visible ASCII characters")
    return value


def _read_key_file(path, h):
    return _key_value(h.private_read(path).decode().strip())


def install(args):
    bundle = args.bundle.resolve(strict=True)
    manifest = verify(bundle)
    h = helper(bundle)
    prefix = args.prefix.expanduser().absolute()
    _, _, model = _selected_configuration(args, h, prefix)
    if args.reranker_dir is None and not reranker_directory(prefix, bundle).exists():
        raise SetupInputError("First installation requires --reranker-dir with the reviewed model assets")
    credential = prefix / "settings/jev-credential.json"
    key = _read_key_file(args.jev_key_file, h) if args.jev_key_file else None
    if credential.exists():
        if key is not None and key != _read_key_file(credential, h):
            raise SetupInputError("A different --jev-key-file cannot replace the saved credential implicitly")
    elif key is None:
        if sys.stdin.isatty():
            key = _key_value(getpass.getpass("Jev API 키 (입력 숨김, Enter로 확정): ").strip())
        else:
            raise SetupInputError("A private --jev-key-file or secure terminal input is required")
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
        "jev",
        "--model",
        model,
    ]
    if platform.system() == "Linux":
        bootstrap.append("--virtual-linux")
    environment = _python_environment()
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
                raise SetupInputError("A verified bootstrap bundle is required for first installation")
            _bootstrap(prefix, bootstrap, environment, h)
    h.owner(prefix)
    with h.locked(prefix, "unified-install.lock"):
        return _install_owned(args, h, key, manifest)


def _install_owned(args, h, key, manifest):
    prefix = args.prefix.expanduser().absolute()
    bundle = args.bundle.resolve(strict=True)
    if verify(bundle) != manifest:
        raise SetupInputError("The release bundle changed during preparation")
    saved_path = prefix / "settings/unified.json"
    saved, migrating, model = _selected_configuration(args, h, prefix)
    provider = "jev"
    h.OPERATION_LOG = prefix / "settings/unified-operations.log"


    h.safe_parents(prefix / "models/reranker")
    with h.locked(prefix, "reranker-install.lock"), h.phase("검색 재정렬 모델 준비"):
        install_reranker(prefix, bundle, args.reranker_dir)
    credential = prefix / "settings/jev-credential.json"
    if credential.exists():
        if key is not None and key != _read_key_file(credential, h):
            raise SetupInputError("A different key cannot replace the saved credential implicitly")
        key = None
    elif key is None:
        raise SetupInputError("The saved credential disappeared; supply a private --jev-key-file")
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
    if verify(target / "bundle") != manifest:
        raise SetupInputError("The release bundle changed while copying")
    base = prefix / "current/venv/bin/python"
    python = target / "gateway/bin/python"
    with h.phase("공통 기억 엔진 설치"):
        h.run([str(base), "-I", "-m", "venv", "--without-pip", str(target / "gateway")])
        pip_python = _write_pip_python(h, target, python)
        pip_environment = _python_environment()
        h.run(
            [
                str(base),
                "-I",
                "-m",
                "pip",
                "--python",
                str(pip_python),
                "install",
                "--disable-pip-version-check",
                "--require-hashes",
                "-r",
                str(target / "bundle/client-requirements.lock"),
            ],
            env=pip_environment,
            timeout=600,
        )
        h.run(
            [
                str(base),
                "-I",
                "-m",
                "pip",
                "--python",
                str(pip_python),
                "install",
                "--no-deps",
                str(target / "bundle" / manifest["core_313"]),
                str(target / "bundle" / manifest["sdk"]),
            ],
            timeout=120,
            env=pip_environment,
        )
    config = dict(saved) if saved else {
        "product_id": h.owner(prefix)["id"],
        "provider": provider,
        "model": model,
        "mode": args.mode,
        "host": args.host,
        "port": h.available_port(),
        "hindsight_port": h.available_port(),
        "path": os.environ.get("PATH", os.defpath),
    }
    config.update(provider="jev", model=model, provider_verified=False)
    config.pop("executable", None)
    config.setdefault(
        "public_url", args.public_url or "http://127.0.0.1:" + str(config["port"])
    )
    pointer = prefix / (".unified-current-" + uuid.uuid4().hex)
    with h.locked(prefix, "unified-service-start.lock"):
        old = (prefix / "unified-current").resolve() if (prefix / "unified-current").exists() else None
        if old:
            _stop_locked(prefix, h)
        _require_free_service_ports(config)
        h.write_json(saved_path, config)
        pointer.symlink_to("unified-installs/" + install_id)
        os.replace(pointer, prefix / "unified-current")
    pending = None
    try:
        if key is not None:
            pending = prefix / "settings" / (".jev-check-" + uuid.uuid4().hex + ".json")
            h.write_json(pending, {"schema_version": 1, "api_key": key})
        with h.phase("선택한 공급자 인증 확인"):
            env = service_environment(prefix, h, config)
            if pending is not None:
                env["AM_MEMORY_JEV_KEY_FILE"] = str(pending)
            h.run(
                [
                    str(python),
                    "-I",
                    "-c",
                    (
                        "import asyncio,json; from agents_memory.memory_processor import from_environment; "
                        "result=asyncio.run(from_environment().process('The synthetic verification application uses PostgreSQL 18 for its database.')); "
                        "raise SystemExit(None if result['decision']=='keep' else json.dumps(result,ensure_ascii=False))"
                    ),
                ],
                env=env,
                timeout=180,
            )
        if key is not None:
            if credential.exists() and _read_key_file(credential, h) != key:
                raise SetupInputError("The saved credential changed during validation")
            if not credential.exists():
                h.write_json(credential, {"schema_version": 1, "api_key": key})
        with h.locked(prefix, "unified-service-start.lock"):
            config["provider_verified"] = True
            h.write_json(saved_path, config)
        with h.phase("기억 서비스 시작"):
            state = ensure(prefix)
    except BaseException:
        with h.locked(prefix, "unified-service-start.lock"):
            _stop_locked(prefix, h)
            if old and not migrating:
                h.write_json(saved_path, saved)
                pointer.symlink_to(old.relative_to(prefix))
                os.replace(pointer, prefix / "unified-current")
        if old and not migrating:
            h.run([str(prefix / "current/venv/bin/python"), "-I",
                   str(old / "bundle/unified_setup.py"), "ensure", "--prefix", str(prefix)], timeout=180)
        raise
    finally:
        if pending is not None:
            pending.unlink(missing_ok=True)
    manager = prefix / "settings/unified-manager.json"
    env = service_environment(prefix, h, config)
    if not manager.exists():
        h.run(
            [
                str(python),
                "-I",
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
            + ' -I "$@"\n'
        )
        h.write_private(launcher, script.encode())
        launcher.chmod(0o700)
        command = [
            str(python),
            "-I",
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
    parser.add_argument("--startup-fd", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--bootstrap-bundle", type=Path)
    parser.add_argument("--reranker-dir", type=Path)
    parser.add_argument("--provider", choices=["jev"])
    parser.add_argument("--model")
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
    if args.startup_fd is not None and args.action != "service":
        parser.error("--startup-fd is only valid for the owned service child")
    if args.action == "install":
        install(args)
    elif args.action == "service":
        run_service(args.prefix, args.startup_fd)
    elif args.action == "ensure":
        print(json.dumps(ensure(args.prefix)))
    else:
        stop(args.prefix)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except SetupInputError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
    except Exception:  # noqa: BLE001 - never print credential-bearing provider exceptions
        print(
            "Setup failed; provider diagnostics are private. Inspect settings/unified-operations.log or unified-service.log if created.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
