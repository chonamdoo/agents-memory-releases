from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from .client import Remote, Replica, private_file
from .embedding import E5
from .models import Failure
from .store import Store, canonical
from .web import create_app


def write_secret(path, value):
    path = private_file(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(canonical(value) + "\n")


def parser():
    p = argparse.ArgumentParser(description="Optional personal sync and team memory server")
    sub = p.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=18350)
    serve.add_argument("--public-url", required=True)
    serve.add_argument("--e5-dir", type=Path)
    serve.add_argument("--e5-manifest", type=Path)
    account = sub.add_parser("account", help="Server administrator: create account and private first credential")
    account.add_argument("--name", required=True)
    account.add_argument("--output", type=Path, required=True)
    manager = sub.add_parser("recovery-manager", help="Server operator: issue a replacement account manager")
    manager.add_argument("--user-id", type=UUID, required=True)
    manager.add_argument("--output", type=Path, required=True)
    sub.add_parser("restore-epoch", help="Server operator: rotate sync epoch after restoring a backup")
    setup = sub.add_parser("setup", help="Verify server/device, sync and register selected MCP apps")
    setup.add_argument("--url")
    setup.add_argument("--credential-file", type=Path)
    setup.add_argument("--client", action="append", choices=["claude", "codex", "omp", "all"])
    setup.add_argument("--project", type=Path, default=Path.cwd())
    setup.add_argument("--project-name")
    setup.add_argument("--profile", default="personal")
    setup.add_argument("--root", type=Path)
    setup.add_argument("--device-name")
    setup.add_argument("--replace-credential", action="store_true", help="Verify and replace a revoked/lost key for the same account")
    setup.add_argument("--recover", action="store_true", help="Explicitly archive/rebuild a restored or legacy replica")
    mcp = sub.add_parser("mcp", help="Durable stdio MCP with background sync")
    mcp.add_argument("--connection", type=Path, required=True)
    mcp.add_argument("--state", type=Path, required=True)
    mcp.add_argument("--project", required=True)
    sync = sub.add_parser("sync")
    sync.add_argument("--connection", type=Path, required=True)
    sync.add_argument("--state", type=Path, required=True)
    commands = sync.add_subparsers(dest="action", required=True)
    add = commands.add_parser("remember")
    add.add_argument("--project", required=True)
    add.add_argument("--file", type=Path, required=True)
    add.add_argument("--memory-id")
    add.add_argument("--kind", choices=["memory", "summary", "prompt"], default="memory")
    add.add_argument("--include-prompts", action="store_true")
    add.add_argument("--session-id")
    add.add_argument("--source-id")
    delete = commands.add_parser("forget")
    delete.add_argument("--project", required=True)
    delete.add_argument("--memory-id", required=True)
    commands.add_parser("once")
    commands.add_parser("connect")
    commands.add_parser("status")
    commands.add_parser("recover")
    export = commands.add_parser("export-pending", help="Preserve an old unbound queue for explicit selection; never uploads it")
    export.add_argument("--output", type=Path, required=True)
    watch = commands.add_parser("watch")
    watch.add_argument("--interval", type=int, default=10)
    for target in (watch, commands.add_parser("import-hindsight")):
        target.add_argument("--hindsight-url")
        target.add_argument("--bank")
        target.add_argument("--project")
        target.add_argument("--enable-cloud-upload", action="store_true")
    commands.add_parser("list")
    resolve = commands.add_parser("resolve")
    resolve.add_argument("--memory-id", required=True)
    resolve.add_argument("--keep", choices=["local", "server"], required=True)
    request = sub.add_parser("request", help="Authenticated team/device administration; JSON input file")
    request.add_argument("--connection", type=Path, required=True)
    request.add_argument("--path", required=True)
    request.add_argument("--method", choices=["GET", "POST", "PUT", "DELETE"], default="GET")
    request.add_argument("--input", type=Path)
    request.add_argument("--secret-output", type=Path)
    return p


def remote(path):
    path = private_file(path)
    value = json.loads(path.read_text())
    return Remote(value["url"], value["token"])


def main():
    args = parser().parse_args()
    try:
        if args.command in {"serve", "account", "recovery-manager", "restore-epoch"}:
            dsn = os.environ.get("AM_COLLAB_DATABASE_URL")
            if not dsn:
                raise ValueError("Set AM_COLLAB_DATABASE_URL in the server environment")
            embedder = None
            if args.command == "serve" and args.e5_dir:
                if not args.e5_manifest:
                    raise ValueError("An E5 checksum manifest is required")
                embedder = E5(args.e5_dir, args.e5_manifest)
            store = Store(dsn, embedder)
            if args.command == "serve":
                import uvicorn
                # Access logs may include invite/query identifiers; disable them.
                uvicorn.run(create_app(store, args.public_url), host=args.host, port=args.port,
                            access_log=False, proxy_headers=False, log_level="warning")
                return

            async def account():
                if args.command != "restore-epoch":
                    args.output = private_file(args.output)
                    if args.output.exists():
                        raise Failure(409, "output_already_exists")
                await store.open()
                try:
                    if args.command == "restore-epoch":
                        return await store.rotate_epoch()
                    result = await store.create_account(args.name) if args.command == "account" else await store.recovery_manager(args.user_id)
                    result["url"] = os.environ.get("AM_COLLAB_PUBLIC_URL", "http://127.0.0.1:18350")
                    write_secret(args.output, result)
                    return {"created": True, "credential_file": str(args.output)}
                finally:
                    await store.close()
            result = asyncio.run(account())
        elif args.command == "setup":
            from .setup import install
            result = install(args)
        elif args.command == "mcp":
            from .stdio import LocalMCP
            replica = Replica(args.state, remote(args.connection))
            try:
                asyncio.run(LocalMCP(replica, args.project).run())
            finally:
                replica.close()
            return
        elif args.command == "request":
            if args.method == "POST" and args.path.endswith(("/devices", "/invites")) and not args.secret_output:
                raise ValueError("Use --secret-output before minting a device credential or invitation")
            value = json.loads(args.input.read_text()) if args.input else None
            result = remote(args.connection).request(args.path, value, method=args.method)
            if args.secret_output:
                write_secret(args.secret_output, result)
                result = {"saved": str(args.secret_output)}
            elif any(key in result for key in ("token", "invite")):
                raise ValueError("Use --secret-output to save credentials/invites without printing them")
        else:
            replica = Replica(args.state, remote(args.connection))
            try:
                bridge = None
                if args.action == "import-hindsight" or (args.action == "watch" and args.hindsight_url):
                    from .hindsight import HindsightBridge
                    if not args.enable_cloud_upload or not all((args.hindsight_url, args.bank, args.project)):
                        raise ValueError("Explicit --enable-cloud-upload, local URL, bank and project are required")
                    bridge = HindsightBridge(replica, args.hindsight_url, args.bank, args.project)
                if args.action == "remember":
                    if not replica.status()["bound"]:
                        replica.connect()
                    result = replica.stage(args.project, args.file.read_text(), memory_id=args.memory_id,
                                           kind=args.kind, allow_prompts=args.include_prompts,
                                           session_id=args.session_id, source_id=args.source_id)
                elif args.action == "forget":
                    result = replica.stage(args.project, memory_id=args.memory_id, deleted=True)
                elif args.action == "list":
                    result = {"memories": replica.list_memories()}
                elif args.action == "connect":
                    result = replica.connect()
                elif args.action == "status":
                    result = replica.status()
                elif args.action == "recover":
                    result = replica.recover()
                elif args.action == "export-pending":
                    with replica.lock:
                        value = {"destination": replica._state(), "operations": [json.loads(r[0]) for r in replica.db.execute("SELECT body FROM outbox ORDER BY rowid")]}
                    write_secret(args.output, value)
                    result = {"exported": len(value["operations"]), "path": str(args.output), "uploaded": False, "queue_unchanged": True}
                elif args.action == "import-hindsight":
                    replica.cycle(pull_only=True)
                    result = bridge.stage()
                elif args.action == "resolve":
                    result = replica.resolve(args.memory_id, args.keep)
                elif args.action == "watch":
                    if not 1 <= args.interval <= 3600:
                        raise ValueError("Choose a 1–3600 second interval")
                    while True:
                        try:
                            if bridge:
                                replica.cycle(pull_only=True)
                                bridge.stage()
                            print(canonical(replica.cycle()), flush=True)
                        except Failure as error:
                            print(canonical({"state": "needs_review" if error.status == 409 else "blocked",
                                             "error": error.code, "pending_preserved": True}), flush=True)
                        except Exception:  # noqa: BLE001 - retry transport failures without exposing secrets
                            print('{"state":"retrying","pending_preserved":true}', flush=True)
                        time.sleep(args.interval)
                else:
                    result = replica.cycle()
            finally:
                replica.close()
        print(canonical(result))
    except KeyboardInterrupt:
        return
    except Failure as error:
        print(canonical({"error": error.code, "pending_preserved": True}), file=sys.stderr)
        raise SystemExit(1) from None
    except (ValidationError, UnicodeError):
        print('{"error":"invalid_memory_input","accepted":false}', file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:  # noqa: BLE001 - CLI never prints connection strings or credentials
        print("Operation failed; check server/account configuration. Pending local data was preserved.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
