"""Public command routing and persistent local configuration; memory implementation is compiled."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

PAYLOAD = Path(__file__).resolve().parent
INSTALL = PAYLOAD.parent
PREFIX = INSTALL.parent.parent
spec = importlib.util.spec_from_file_location("release_installer", PAYLOAD / "installer.py")
installer = importlib.util.module_from_spec(spec)
sys.dont_write_bytecode = True
spec.loader.exec_module(installer)


def profile():
    owner = installer.check_prefix(PREFIX)
    ready = installer.read_private(INSTALL / "READY.json")
    if ready["product_id"] != owner["id"] or ready["install_id"] != INSTALL.name:
        raise ValueError("Unexpected installation identity")
    return installer.profile_valid(installer.read_private(PREFIX / "settings/profile.json"))


def prepare_vendor():
    ready = installer.read_private(INSTALL / "READY.json")
    manifest = json.loads((PAYLOAD / "MANIFEST.json").read_bytes())
    if installer.digest(PAYLOAD / "MANIFEST.json") != ready["manifest_sha256"]:
        raise ValueError("Installation manifest changed")
    vendor = PAYLOAD / "vendor" / ready["target"]
    for root in (vendor, PAYLOAD / "components" / ready["target"]):
        relative_root = root.relative_to(PAYLOAD).as_posix() + "/"
        expected = {name for name in manifest["files"] if name.startswith(relative_root)}
        observed = {path.relative_to(PAYLOAD).as_posix() for path in root.rglob("*") if path.is_file()}
        if not expected or expected != observed or any(path.is_symlink() for path in root.rglob("*")):
            raise ValueError("Compiled component/vendor files are missing or unexpected")
        for relative in expected:
            if installer.digest(PAYLOAD / relative) != manifest["files"][relative]:
                raise ValueError("Compiled component/vendor integrity check failed")
    # Both API and plugin use this venv. Do not inherit arbitrary import overlays.
    os.environ["PYTHONPATH"] = str(vendor)
    sys.path.insert(0, str(vendor))
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    return vendor


def project(args, selected):
    path = args.path.expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("Project must be an existing directory")
    key = hashlib.sha256(os.fsencode(path)).hexdigest()[:24]
    directory = PREFIX / "projects" / key
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    config = directory / "hook.json"
    if not config.exists():
        bank = "project-" + key
        installer.private_json(config, {"outbox_dir": str(directory / "outbox"),
            "api_url": "http://127.0.0.1:" + str(selected["api_port"]), "bank": bank,
            "max_entries": 128, "max_queue_bytes": 8388608, "api_token_env": None,
            "timeout_seconds": 5, "poll_seconds": 2, "max_attempts": 3})
        installer.private_json(directory / "project.json", {"path": str(path), "bank": bank})
    from agents_memory import hindsight_hook
    loaded = hindsight_hook.load_config(str(config))
    hindsight_hook.initialize(loaded)
    command = str(PREFIX / "current/bin/am-hindsight")
    print(json.dumps({"project": str(path), "bank": loaded.bank, "hook_config": str(config),
        "capture_command": shlex.join([command, "hook", "capture", "--config", str(config)]),
        "drain_command": shlex.join([command, "hook", "drain", "--config", str(config), "--run"]),
        "mcp_url": f"http://127.0.0.1:{loaded.port}/mcp/{loaded.bank}/",
        "next_step": "Before starting the API, run bank-init for this hook config. Capture is local only; run drain separately."}, ensure_ascii=False, indent=2))
    return 0


def bank_init(config, selected):
    from argparse import Namespace
    from agents_memory.hindsight_hook import load_config
    item = load_config(config)
    if item.host != "127.0.0.1" or item.port != selected["api_port"]:
        raise ValueError("Bank provisioning must match the selected local service")
    vendor = prepare_vendor()
    from _agents_memory_release import local
    args = Namespace(install_mode="personal" if selected["provider"] == "jev" else "company",
        judge_model=selected["model"], patched_package=str(vendor),
        subscription_host="codex" if selected["provider"] == "local-llm" else None,
        subscription_executable=selected["codex_executable"], subscription_workdir=selected["subscription_workdir"],
        asset_dir=str(PAYLOAD / "models/e5-small"), host="127.0.0.1", api_port=selected["api_port"],
        worker_port=selected["worker_port"], bank=item.bank, hindsight_api=str(INSTALL / "venv/bin/hindsight-api"))
    # The normal guard validates the local DB, exact vendor/model assets, provider and
    # unused service ports. Configure before serving; HTTP write restrictions stay intact.
    _, child = local.prepare(args, dict(os.environ))
    program = '''import asyncio,os,sys
from pathlib import Path
expected=Path(sys.argv[2]).resolve(strict=True)
sys.path.insert(0,str(expected))
import hindsight_api.engine.memory_engine as implementation
import hindsight_api.extensions.memory_admission as guard
assert Path(implementation.__file__).resolve().is_relative_to(expected)
assert Path(guard.__file__).resolve().is_relative_to(expected) and guard.__file__.endswith(".so")
from hindsight_api.engine.memory_engine import MemoryEngine
from hindsight_api.models import RequestContext
async def run():
    engine=MemoryEngine(db_url=os.environ["HINDSIGHT_API_DATABASE_URL"],memory_llm_provider="none",skip_llm_verification=True)
    try:
        await engine.initialize()
        state=await engine.update_bank_config(sys.argv[1],{"retain_chunk_size":3000,"enable_observations":False,"enable_auto_consolidation":False,"memory_defense":{"enabled":True,"rules":[{"on":"sensitive_data","action":"redact"}]}},request_context=RequestContext())
        assert state.config["memory_defense"]["enabled"] is True
    finally:
        await engine.close()
asyncio.run(run())
'''
    result = subprocess.run([sys.executable, "-I", "-B", "-c", program, item.bank, str(vendor)], env=child, timeout=180)
    if result.returncode:
        raise ValueError("Local bank provisioning failed")
    print("Bank privacy screening enabled locally. Start the API next. Project banks route data; they are not per-user authorization boundaries.")
    return 0


def serve(args, selected):
    vendor = prepare_vendor()
    from _agents_memory_release import local
    command = ["--check" if args.check else "--start", "--asset-dir", str(PAYLOAD / "models/e5-small"),
        "--api-port", str(selected["api_port"]), "--worker-port", str(selected["worker_port"]),
        "--bank", args.bank, "--hindsight-api", str(INSTALL / "venv/bin/hindsight-api"),
        "--install-mode", "personal" if selected["provider"] == "jev" else "company",
        "--judge-model", selected["model"], "--patched-package", str(vendor)]
    if selected["provider"] == "local-llm":
        if not selected["codex_executable"]:
            raise ValueError("Configure an existing signed-in Codex executable first")
        command.extend(["--subscription-host", "codex", "--subscription-executable", selected["codex_executable"],
                        "--subscription-workdir", selected["subscription_workdir"]])
    return local.main(command)


def configure(args, selected):
    with installer.install_lock(PREFIX):
        value = dict(selected)
        if args.provider:
            value["provider"] = args.provider
            if args.provider != selected["provider"]:
                value["model"] = "jev-1.14.0" if args.provider == "jev" else "gpt-6.1-sol"
        if args.model:
            value["model"] = args.model
        if value["provider"] == "jev":
            if args.codex:
                raise ValueError("Jev profile does not accept a Codex path")
            value.update(codex_executable=None, subscription_workdir=None)
        else:
            workdir = PREFIX / "settings/subscription-workdir"
            workdir.mkdir(parents=True, mode=0o700, exist_ok=True)
            value["subscription_workdir"] = str(workdir)
            if args.codex:
                executable = Path(args.codex).expanduser().resolve(strict=True)
                if not executable.is_file() or not os.access(executable, os.X_OK):
                    raise ValueError("Codex must be an existing executable")
                value["codex_executable"] = str(executable)
        installer.private_json(PREFIX / "settings/profile.json", installer.profile_valid(value))
    print("Provider configuration updated explicitly. Existing project outboxes and database were preserved.")
    return 0


def main(argv=None):
    os.umask(0o077)
    argv = sys.argv[1:] if argv is None else argv
    # Capture is stdlib + compiled hook only: no vendor/model/DB/installer lock or service start.
    if argv and argv[0] == "hook":
        from agents_memory.hindsight_hook import main as hook_main
        return hook_main(argv[1:])
    parser = argparse.ArgumentParser(description="agents-memory Hindsight local")
    parser.add_argument("--version", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("profile")
    sub.add_parser("rollback")
    p = sub.add_parser("project-init")
    p.add_argument("path", type=Path)
    b = sub.add_parser("bank-init")
    b.add_argument("--config", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--check", action="store_true")
    s.add_argument("--bank", required=True)
    c = sub.add_parser("configure")
    c.add_argument("--provider", choices=("jev", "local-llm"))
    c.add_argument("--model")
    c.add_argument("--codex")
    args = parser.parse_args(argv)
    if args.version:
        from agents_memory import __version__
        print("agents-memory Hindsight local " + __version__)
        return 0
    selected = profile()
    if args.command == "profile":
        print(json.dumps(selected, ensure_ascii=False, indent=2))
        return 0
    if args.command == "project-init":
        return project(args, selected)
    if args.command == "bank-init":
        return bank_init(args.config, selected)
    if args.command == "serve":
        return serve(args, selected)
    if args.command == "configure":
        return configure(args, selected)
    if args.command == "rollback":
        return installer.rollback(PREFIX)
    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException, subprocess.SubprocessError):
        print("Local command failed safely; check private configuration, credentials and declared prerequisites.", file=sys.stderr)
        raise SystemExit(2)
