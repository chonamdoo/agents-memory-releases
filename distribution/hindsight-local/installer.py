"""Public local distribution installer; private memory behavior is in binary extensions."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import uuid

PRODUCT = "agents-memory-hindsight-local"
DEFAULT_PREFIX = Path.home() / ".local/share/agents-memory-hindsight"
MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_./:-]{0,127}\Z")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def private_json(path, value):
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temp.open("x") as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read_private(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Private configuration ownership or permissions are invalid")
    return json.loads(path.read_bytes())


def profile_valid(value):
    required = {"schema_version", "deployment", "provider", "model", "codex_executable", "subscription_workdir", "api_port", "worker_port"}
    if (not isinstance(value, dict) or set(value) != required or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or value["deployment"] != "local" or value["provider"] not in {"jev", "local-llm"}
            or not isinstance(value["model"], str) or not MODEL.fullmatch(value["model"])
            or any(type(value[k]) is not int or not 1024 <= value[k] <= 65535 for k in ("api_port", "worker_port"))
            or value["api_port"] == value["worker_port"]):
        raise ValueError("Unsupported profile; this installer supports local deployment only")
    for key in ("codex_executable", "subscription_workdir"):
        if value[key] is not None and (not isinstance(value[key], str) or not Path(value[key]).is_absolute()):
            raise ValueError("Subscription paths must be absolute")
    if value["provider"] == "jev" and any(value[k] is not None for k in ("codex_executable", "subscription_workdir")):
        raise ValueError("Jev profile cannot contain a subscription route")
    if value["provider"] == "local-llm" and not value["subscription_workdir"]:
        raise ValueError("Subscription workdir is missing")
    return value


def verify_bundle(bundle):
    manifest = json.loads((bundle / "MANIFEST.json").read_bytes())
    if manifest.get("product") != PRODUCT or manifest.get("version") != "1.0.0":
        raise ValueError("Unexpected product/version")
    files = manifest["files"]
    observed = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise ValueError("Bundle must not contain symlinks outside runtime archives")
        if path.is_file():
            relative = path.relative_to(bundle).as_posix()
            if relative not in {"MANIFEST.json", "SHA256SUMS"}:
                observed.add(relative)
    if observed != set(files):
        raise ValueError("Unexpected or missing bundle files")
    for relative, expected in files.items():
        path = bundle / relative
        if not path.resolve().is_relative_to(bundle.resolve()) or digest(path) != expected:
            raise ValueError("Release file integrity check failed")
    return manifest


def check_prefix(prefix):
    if not prefix.is_absolute() or prefix.is_symlink() or prefix.resolve() != prefix:
        raise ValueError("Installation prefix must be an absolute directory without symlinks")
    marker = prefix / "PRODUCT.json"
    if not prefix.exists():
        prefix.mkdir(parents=True, mode=0o700)
    elif not marker.exists() and any(prefix.iterdir()):
        raise ValueError("Refusing to adopt a nonempty directory")
    info = prefix.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("Installation prefix must be private and owned by this user")
    if not marker.exists():
        private_json(marker, {"product": PRODUCT, "schema_version": 1, "id": uuid.uuid4().hex})
    value = read_private(marker)
    if value.get("product") != PRODUCT or type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        raise ValueError("Unexpected installation owner")
    return value


@contextmanager
def install_lock(prefix):
    fd = os.open(prefix / ".install.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Unsafe installer lock")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def active(prefix, owner):
    pointer = prefix / "current"
    if not pointer.is_symlink():
        if pointer.exists():
            raise ValueError("Current installation pointer is invalid")
        return None
    path = pointer.resolve(strict=True)
    if path.parent != prefix / "installs":
        raise ValueError("Current installation escapes owned directory")
    ready = read_private(path / "READY.json")
    if ready["product_id"] != owner["id"] or ready["install_id"] != path.name:
        raise ValueError("Installation identity mismatch")
    return ready


def select_profile(args, prefix):
    path = prefix / "settings/profile.json"
    if path.exists():
        value = profile_valid(read_private(path))
        if any(getattr(args, k) is not None for k in ("provider", "model", "codex")):
            raise ValueError("Existing profile is preserved; use the explicit configure command to change it")
        return value
    provider = args.provider
    if provider is None:
        if not sys.stdin.isatty():
            raise ValueError("First install requires --provider jev or --provider local-llm")
        print("저장 판단에 사용할 LLM을 선택하세요. 배포 방식은 로컬입니다.")
        answer = input("1) Jev  2) 로컬 LLM (구독 중인 Codex): ").strip()
        provider = {"1": "jev", "2": "local-llm"}.get(answer)
        if provider is None:
            raise ValueError("Select 1 or 2")
    workdir = prefix / "settings/subscription-workdir"
    workdir.mkdir(parents=True, mode=0o700, exist_ok=True)
    executable = args.codex or shutil.which("codex")
    return profile_valid({"schema_version": 1, "deployment": "local", "provider": provider,
        "model": args.model or ("jev-1.14.0" if provider == "jev" else "gpt-6.1-sol"),
        "codex_executable": str(Path(executable).absolute()) if provider == "local-llm" and executable else None,
        "subscription_workdir": str(workdir) if provider == "local-llm" else None,
        "api_port": 18250, "worker_port": 18251})


def activate(prefix, install_id):
    temp = prefix / (".current-" + uuid.uuid4().hex)
    temp.symlink_to("installs/" + install_id)
    os.replace(temp, prefix / "current")


def rollback(prefix):
    owner = check_prefix(prefix)
    with install_lock(prefix):
        now = active(prefix, owner)
        previous = now.get("previous_install_id") if now else None
        if not previous or not re.fullmatch(r"[A-Za-z0-9.-]+", previous):
            raise ValueError("No previous owned installation is available")
        target = prefix / "installs" / previous
        ready = read_private(target / "READY.json")
        if target.is_symlink() or ready["product_id"] != owner["id"] or ready["install_id"] != previous:
            raise ValueError("Rollback installation identity mismatch")
        profile_valid(read_private(prefix / "settings/profile.json"))
        activate(prefix, previous)
        print("Rolled back application files; provider, project queues and database were preserved.")
    return 0


def install(args):
    bundle = args.bundle.resolve(strict=True)
    manifest = verify_bundle(bundle)
    prefix = args.prefix.expanduser().absolute()
    owner = check_prefix(prefix)
    target = "darwin-arm64"
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        if not args.virtual_linux or (platform.system(), platform.machine()) != ("Linux", "x86_64"):
            raise ValueError("Production installation requires Apple Silicon macOS")
        target = "linux-x86_64"
    elif tuple(map(int, platform.mac_ver()[0].split(".")[:1])) < (13,):
        raise ValueError("macOS 13 or newer is required")
    with install_lock(prefix):
        profile = select_profile(args, prefix)
        previous = active(prefix, owner)
        install_id = manifest["version"] + "-" + uuid.uuid4().hex
        folder = prefix / "installs" / install_id
        folder.mkdir(parents=True, mode=0o700)
        try:
            payload = folder / "payload"
            shutil.copytree(bundle, payload)
            runtime = folder / "runtime"
            runtime.mkdir(mode=0o700)
            with tarfile.open(payload / "runtimes" / (target + ".tar.gz")) as archive:
                archive.extractall(runtime, filter="data")
            python = runtime / "python/bin/python3"
            subprocess.run([str(python), "-I", "-m", "venv", str(folder / "venv")], check=True)
            python = folder / "venv/bin/python"
            command = [str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check", "--require-hashes",
                       "-r", str(payload / "locks" / (target + ".txt"))]
            if args.wheelhouse:
                command.extend(["--no-index", "--find-links", str(args.wheelhouse.resolve(strict=True))])
            with (folder / "dependency-install.log").open("wb") as stream:
                subprocess.run(command, check=True, stdout=stream, stderr=subprocess.STDOUT, timeout=900)
                subprocess.run([str(python), "-I", "-m", "pip", "install", "--no-index", "--no-deps",
                    str(next((payload / "components" / target).glob("*.whl")))], check=True,
                    stdout=stream, stderr=subprocess.STDOUT, timeout=120)
            probe = "import agents_memory,agents_memory.hindsight_hook as h,_agents_memory_release.local as l;assert agents_memory.__version__=='1.0.0';assert h.__file__.endswith('.so') and l.__file__.endswith('.so')"
            subprocess.run([str(python), "-I", "-c", probe], check=True, timeout=30)
            (folder / "bin").mkdir(mode=0o700)
            launcher = folder / "bin/am-hindsight"
            launcher.write_text("#!/bin/sh\nexec " + shlex.quote(str(python)) + " -I " + shlex.quote(str(payload / "entry.py")) + " \"$@\"\n")
            launcher.chmod(0o700)
            private_json(folder / "READY.json", {"product_id": owner["id"], "install_id": install_id,
                "version": manifest["version"], "source_commit": manifest["source_commit"], "target": target,
                "manifest_sha256": digest(payload / "MANIFEST.json"),
                "previous_install_id": previous["install_id"] if previous else None})
            (prefix / "settings").mkdir(mode=0o700, exist_ok=True)
            if not (prefix / "settings/profile.json").exists():
                private_json(prefix / "settings/profile.json", profile)
            activate(prefix, install_id)
        except BaseException:
            # Only this attempt's newly created application directory is removed.
            shutil.rmtree(folder)
            raise
    print("Installed agents-memory Hindsight local " + manifest["version"])
    print("Command: " + shlex.quote(str(prefix / "current/bin/am-hindsight")))
    print("Provider choice is preserved on update. Database, provider login and project connection remain explicit setup steps.")
    return 0


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--prefix", type=Path, default=DEFAULT_PREFIX)
    parser.add_argument("--provider", choices=("jev", "local-llm"))
    parser.add_argument("--model")
    parser.add_argument("--codex")
    parser.add_argument("--virtual-linux", action="store_true", help="Linux validation only; not production support")
    parser.add_argument("--wheelhouse", type=Path, help="Optional hash-verified offline dependency wheel directory")
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    try:
        return rollback(args.prefix.expanduser().absolute()) if args.rollback else install(args)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, tarfile.TarError):
        print("Installation failed safely. Check release checksums, private prefix, platform and dependency-install.log; existing configuration was preserved.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
