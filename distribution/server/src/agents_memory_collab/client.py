"""Cross-device SQLite outbox. Network failures never discard pending writes."""
from __future__ import annotations

import json
import os
import sqlite3
import stat
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from .models import Failure, Operation
from .protocol import GENESIS, canonical, chain_hash, digest, operation_digest


def private_file(path: Path):
    path = path.absolute()
    # macOS exposes these OS-owned roots as aliases. Normalize only those
    # verified roots, then retain the leaf/parent symlink and ownership checks.
    # Resolving the whole path would also follow user-controlled symlinks.
    if sys.platform == "darwin":
        for alias in ("/var", "/tmp", "/etc"):
            target = "/private" + alias
            if (path.is_relative_to(alias) and Path(alias).is_symlink()
                    and os.lstat(alias).st_uid == 0 and os.path.realpath(alias) == target):
                path = Path(target) / path.relative_to(alias)
                break
    if path.is_symlink():
        raise ValueError("Private files must not be symbolic links")
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Expected a private regular file")
        if os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077):
            raise ValueError("Private files must be owned by you with mode 0600")
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError("Private paths must not contain symbolic links")
    return path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Remote:
    def __init__(self, url: str, token: str, *, timeout=10):
        parsed = urlsplit(url)
        if (parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
                or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"})):
            raise ValueError("Choose an HTTPS server origin; HTTP is loopback-only")
        if not token.startswith("amc_") or len(token) > 100 or any(c.isspace() for c in token):
            raise ValueError("Invalid credential format")
        self.url, self.token = url.rstrip("/"), token
        self.timeout = timeout
        self.http = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))

    def request(self, path, value=None, *, method=None):
        if not path.startswith("/v1/") or path.startswith("//"):
            raise ValueError("Invalid service path")
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() if value is not None else None
        request = urllib.request.Request(self.url + path, data, method=method or ("POST" if data else "GET"),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.http.open(request, timeout=self.timeout) as stream:
                raw = stream.read(4_194_305)
                if len(raw) > 4_194_304:
                    raise ValueError("Service response too large")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            # Error bodies can contain private diagnostics; expose a stable code only.
            code = "service_request_failed"
            try:
                value = json.loads(exc.read(2048))
                if isinstance(value.get("error"), str) and len(value["error"]) < 100:
                    code = value["error"]
            except (ValueError, AttributeError):
                pass
            raise Failure(exc.code, code) from None


class Replica:
    """A verified destination, durable intent queue, and checked local projection.

    A queue acknowledgement is not a server commit or a successful local apply.
    The outbox is removed only when the committed operation is pulled and verified.
    """
    def __init__(self, path: Path, remote: Remote):
        path = private_file(path)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                private_file(path)
        self.path, self.remote = path, remote
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, timeout=10, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=DELETE")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1),server TEXT,user TEXT,installation TEXT,cursor INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY,project TEXT NOT NULL,kind TEXT NOT NULL,text TEXT,deleted INTEGER NOT NULL,revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(op_id TEXT PRIMARY KEY,memory_id TEXT NOT NULL UNIQUE,body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS worker(id INTEGER PRIMARY KEY CHECK(id=1),owner TEXT,expires REAL NOT NULL DEFAULT 0);
            INSERT OR IGNORE INTO worker(id) VALUES(1);
            CREATE TABLE IF NOT EXISTS receipts(op_id TEXT PRIMARY KEY,digest TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS recovery_archive(id TEXT PRIMARY KEY,created_at REAL NOT NULL,body TEXT NOT NULL);
        """)
        additions_by_table = {
            "state": {"epoch": "TEXT", "chain_hash": "TEXT", "credential": "TEXT", "writable": "INTEGER NOT NULL DEFAULT 0"},
            "memories": {"session_id": "TEXT", "source_id": "TEXT", "applied_sequence": "INTEGER NOT NULL DEFAULT 0"},
            "outbox": {"status": "TEXT NOT NULL DEFAULT 'pending'", "error": "TEXT"},
            "worker": {"pid": "INTEGER"},
        }
        with self.transaction():
            for table, additions in additions_by_table.items():
                fields = {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}
                for field, declaration in additions.items():
                    if field not in fields:
                        self.db.execute(f"ALTER TABLE {table} ADD COLUMN {field} {declaration}")
        saved = self._state()
        if saved and saved["server"] != remote.url:
            self.close()
            raise Failure(409, "destination_changed_use_separate_state")

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.commit()
            except BaseException:
                self.db.rollback()
                raise

    def _state(self):
        with self.lock:
            row = self.db.execute("SELECT * FROM state WHERE id=1").fetchone()
            return dict(row) if row else None

    def close(self):
        with self.lock:
            self.db.close()

    def connect(self):
        identity = self.remote.request("/v1/me")
        expected = (self.remote.url, identity["user_id"], identity["installation_id"])
        with self.transaction():
            saved = self._state()
            if saved and (saved["server"], saved["user"], saved["installation"]) != expected:
                raise Failure(409, "destination_changed_use_separate_state")
            if not saved:
                if self.db.execute("SELECT 1 FROM outbox LIMIT 1").fetchone():
                    raise Failure(409, "legacy_unbound_queue_requires_explicit_export")
                self.db.execute("""INSERT INTO state(id,server,user,installation,epoch,chain_hash,credential,writable)
                    VALUES(1,?,?,?,?,?,?,?)""", (*expected, identity["epoch"], GENESIS, digest(self.remote.token), identity["writable"]))
            elif saved["epoch"] is None:
                # Old projections have no verifiable checkpoint. Never bless a
                # cursor against whatever server history happens to exist now.
                raise Failure(409, "legacy_replica_requires_recovery")
            elif saved["epoch"] != identity["epoch"]:
                raise Failure(409, "server_history_changed")
            else:
                self.db.execute("UPDATE state SET credential=?,writable=? WHERE id=1", (digest(self.remote.token), identity["writable"]))
        return identity

    def stage(self, project, text=None, *, memory_id=None, kind="memory", deleted=False,
              allow_prompts=False, op_id=None, base_revision=None, session_id=None, source_id=None):
        with self.transaction():
            saved = self._state()
            if not saved or not saved["epoch"]:
                raise Failure(409, "setup_required_before_queueing")
            if saved["server"] != self.remote.url or saved["credential"] != digest(self.remote.token):
                raise Failure(409, "verify_destination_before_queueing")
            if not saved["writable"]:
                raise Failure(403, "read_only_credential")
            mid = str(UUID(str(memory_id))) if memory_id else str(uuid4())
            old = self.db.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
            if old:
                if deleted:
                    kind, project = old["kind"], old["project"]
                if session_id is None:
                    session_id = old["session_id"]
                if source_id is None:
                    source_id = old["source_id"]
            if kind == "prompt" and not deleted and not allow_prompts:
                raise Failure(403, "prompt_upload_requires_explicit_opt_in")
            if not deleted and (not text or not text.strip()):
                raise Failure(400, "memory_text_required")
            op = Operation(op_id=UUID(str(op_id)) if op_id else uuid4(), memory_id=UUID(mid),
                           project=project, kind=kind, base_revision=base_revision if base_revision is not None else old["revision"] if old else 0,
                           text=None if deleted else text, deleted=deleted, session_id=session_id, source_id=source_id)
            fingerprint = operation_digest(op.model_dump(mode="json"))
            received = self.db.execute("SELECT digest FROM receipts WHERE op_id=?", (str(op.op_id),)).fetchone()
            if received:
                if received[0] != fingerprint:
                    raise Failure(409, "operation_id_reused")
                return {"memory_id": mid, "op_id": str(op.op_id), "queued": False, "state": "applied"}
            pending = self.db.execute("SELECT op_id,body FROM outbox WHERE memory_id=? OR op_id=?", (mid, str(op.op_id))).fetchone()
            if pending:
                if pending["op_id"] != str(op.op_id):
                    raise Failure(409, "pending_operation_exists_resolve_first")
                if operation_digest(json.loads(pending["body"])) != fingerprint:
                    raise Failure(409, "operation_id_reused")
            else:
                self.db.execute("INSERT INTO outbox(op_id,memory_id,body) VALUES(?,?,?)", (str(op.op_id), mid, op.model_dump_json()))
        return {"memory_id": mid, "op_id": str(op.op_id), "queued": True, "state": "queued"}

    def _claim(self):
        owner = str(uuid4())
        with self.transaction():
            previous = self.db.execute("SELECT owner,expires,pid FROM worker WHERE id=1").fetchone()
            abandoned = False
            if previous["pid"] and os.name == "posix":
                try:
                    os.kill(previous["pid"], 0)
                except ProcessLookupError:
                    abandoned = True
                except PermissionError:
                    pass  # A live process owned by someone else must not be reclaimed.
            if previous["expires"] >= time.time() and not abandoned:
                raise Failure(409, "replica_worker_busy")
            self.db.execute("UPDATE worker SET owner=?,expires=?,pid=? WHERE id=1", (owner, time.time() + 90, os.getpid()))
        return owner

    def _release(self, owner):
        with self.transaction():
            self.db.execute("UPDATE worker SET owner=NULL,expires=0,pid=NULL WHERE id=1 AND owner=?", (owner,))

    def _renew(self, owner):
        def update():
            if not self.db.execute("UPDATE worker SET expires=? WHERE id=1 AND owner=? AND expires>?",
                                   (time.time() + 90, owner, time.time())).rowcount:
                raise Failure(409, "replica_worker_lost")
        with self.lock:
            if self.db.in_transaction:
                update()  # Keep ownership validation in the caller's transaction.
            else:
                with self.transaction():
                    update()

    def _checkpoint(self):
        saved = self._state()
        return {"epoch": saved["epoch"], "cursor": saved["cursor"], "chain_hash": saved["chain_hash"]}

    def cycle(self, *, pull_only=False):
        owner = self._claim()
        try:
            self.connect()
            # Detect restored or replaced histories before any pending upload.
            pulled = self._pull(owner)
            pushed = 0
            with self.lock:
                rows = self.db.execute("SELECT op_id,body FROM outbox WHERE status IN ('pending','acked') ORDER BY rowid").fetchall()
            for row in [] if pull_only else rows:
                self._renew(owner)
                body = json.loads(row["body"])
                try:
                    result = self.remote.request("/v1/sync/ops", {"operations": [body], "checkpoint": self._checkpoint()})
                except Failure as error:
                    if error.status in {400, 413, 422} or error.code in {"revision_conflict", "operation_id_reused", "memory_scope_is_immutable",
                                      "prompt_upload_requires_explicit_opt_in", "memory_text_required"}:
                        with self.transaction():
                            self.db.execute("UPDATE outbox SET status='needs_review',error=? WHERE op_id=?", (error.code, row["op_id"]))
                        continue
                    raise
                ack = result.get("acked", [])
                if (result.get("epoch") != self._state()["epoch"] or len(ack) != 1
                        or ack[0].get("op_id") != row["op_id"]
                        or ack[0].get("digest") != operation_digest(body)
                        or ack[0].get("revision") != body["base_revision"] + 1
                        or type(ack[0].get("sequence")) is not int
                        or not 0 < ack[0]["sequence"] <= result.get("head", -1)):
                    raise Failure(502, "invalid_acknowledgement")
                with self.transaction():
                    self.db.execute("UPDATE outbox SET status='acked',error=NULL WHERE op_id=?", (row["op_id"],))
                pushed += 1
            pulled += self._pull(owner)
            return {"pushed": pushed, "pulled": pulled, "cursor": self._state()["cursor"], **self.status()}
        finally:
            self._release(owner)

    def _pull(self, owner):
        pulled = 0
        # Bound a cycle under a continuous writer; normal watch retries advance it.
        for _ in range(1000):
            self._renew(owner)
            saved = self._state()
            page = self.remote.request("/v1/sync/changes?after=" + str(saved["cursor"]))
            if (page.get("epoch") != saved["epoch"] or page.get("anchor") != saved["chain_hash"]
                    or page["head"] < saved["cursor"]):
                raise Failure(409, "server_history_changed")
            last, previous = saved["cursor"], saved["chain_hash"]
            with self.transaction():
                # Confirm ownership in the same transaction as projection updates.
                self._renew(owner)
                for change in page["changes"]:
                    body = {k: v for k, v in change.items() if k not in {"sequence", "digest", "chain_hash"}}
                    if change["sequence"] != last + 1 or chain_hash(previous, last + 1, body, change["digest"]) != change["chain_hash"]:
                        raise Failure(502, "invalid_sync_chain")
                    last, previous = change["sequence"], change["chain_hash"]
                    self.db.execute("""INSERT INTO memories(id,project,kind,text,deleted,revision,session_id,source_id,applied_sequence)
                        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET project=excluded.project,kind=excluded.kind,
                        text=excluded.text,deleted=excluded.deleted,revision=excluded.revision,
                        session_id=excluded.session_id,source_id=excluded.source_id,applied_sequence=excluded.applied_sequence""",
                        (change["memory_id"], change["project"], change["kind"], change["text"], change["deleted"],
                         change["revision"], change.get("session_id"), change.get("source_id"), last))
                    self.db.execute("INSERT OR REPLACE INTO receipts VALUES(?,?)", (change["op_id"], change["digest"]))
                    pending = self.db.execute("SELECT body FROM outbox WHERE op_id=?", (change["op_id"],)).fetchone()
                    if pending:
                        if operation_digest(json.loads(pending[0])) != change["digest"]:
                            self.db.execute("UPDATE outbox SET status='needs_review',error='operation_id_reused' WHERE op_id=?", (change["op_id"],))
                        else:
                            self.db.execute("DELETE FROM outbox WHERE op_id=?", (change["op_id"],))
                if last != page["cursor"] or last > page["head"] or (not page["changes"] and last < page["head"]):
                    raise Failure(502, "invalid_sync_page")
                self.db.execute("UPDATE state SET cursor=?,chain_hash=? WHERE id=1", (last, previous))
            pulled += len(page["changes"])
            if last == page["head"]:
                return pulled
        raise Failure(503, "sync_cycle_budget_reached")

    def recover(self):
        """Explicitly replace a restored projection; archive the old local state.

        Pending intents require a user's local/server choice unless the restored
        log proves that exact operation was committed. No automatic resurrection.
        """
        owner = self._claim()
        shadow_path = self.path.with_name(self.path.name + ".recovery-" + str(uuid4()))
        shadow = None
        try:
            identity = self.remote.request("/v1/me")
            saved = self._state()
            if not saved or (saved["server"], saved["user"], saved["installation"]) != (self.remote.url, identity["user_id"], identity["installation_id"]):
                raise Failure(409, "destination_changed_use_separate_state")
            page = self.remote.request("/v1/sync/changes?after=" + str(saved["cursor"]))
            if (saved["epoch"] == identity["epoch"] == page.get("epoch")
                    and saved["chain_hash"] == page.get("anchor") and saved["cursor"] <= page["head"]):
                return {"recovered": False, "reason": "history_matches_use_normal_sync", **self.status()}
            shadow = Replica(shadow_path, self.remote)
            shadow.connect()
            # Renew original worker while rebuilding any number of pages.
            original_renew = shadow._renew
            def renew(borrower):
                self._renew(owner)
                original_renew(borrower)
            shadow._renew = renew
            shadow.cycle(pull_only=True)
            target = shadow._state()
            archive_id = str(uuid4())
            with self.transaction():
                archive = {"state": saved, "memories": [dict(r) for r in self.db.execute("SELECT * FROM memories")],
                           "outbox": [dict(r) for r in self.db.execute("SELECT * FROM outbox")]}
                self.db.execute("INSERT INTO recovery_archive VALUES(?,?,?)", (archive_id, time.time(), canonical(archive)))
                self.db.execute("DELETE FROM memories")
                self.db.executemany("INSERT INTO memories VALUES(?,?,?,?,?,?,?,?,?)", [tuple(r) for r in shadow.db.execute("SELECT * FROM memories")])
                self.db.execute("DELETE FROM receipts")
                self.db.executemany("INSERT INTO receipts VALUES(?,?)", [tuple(r) for r in shadow.db.execute("SELECT * FROM receipts")])
                self.db.execute("UPDATE state SET epoch=?,cursor=?,chain_hash=?,credential=?,writable=? WHERE id=1",
                                (target["epoch"], target["cursor"], target["chain_hash"], target["credential"], target["writable"]))
                self.db.execute("UPDATE outbox SET status='needs_review',error='history_recovered_review_required'")
                for row in self.db.execute("SELECT op_id,body FROM outbox").fetchall():
                    receipt = self.db.execute("SELECT digest FROM receipts WHERE op_id=?", (row["op_id"],)).fetchone()
                    if receipt and receipt[0] == operation_digest(json.loads(row["body"])):
                        self.db.execute("DELETE FROM outbox WHERE op_id=?", (row["op_id"],))
            return {"recovered": True, "archive_id": archive_id, **self.status()}
        finally:
            if shadow:
                shadow.close()
            if shadow_path.exists():
                shadow_path.unlink()
            self._release(owner)

    def resolve(self, memory_id, keep):
        mid = str(UUID(memory_id))
        self.cycle(pull_only=True)
        owner = self._claim()
        try:
            with self.transaction():
                pending = self.db.execute("SELECT body,status FROM outbox WHERE memory_id=?", (mid,)).fetchone()
                if not pending:
                    raise Failure(404, "no_pending_operation")
                if pending["status"] != "needs_review":
                    raise Failure(409, "pending_operation_may_be_committed_retry_first")
                if keep == "server":
                    self.db.execute("DELETE FROM outbox WHERE memory_id=?", (mid,))
                elif keep == "local":
                    old = json.loads(pending["body"])
                    latest = self.db.execute("SELECT revision FROM memories WHERE id=?", (mid,)).fetchone()
                    old.update(op_id=str(uuid4()), base_revision=latest[0] if latest else 0)
                    self.db.execute("UPDATE outbox SET op_id=?,body=?,status='pending',error=NULL WHERE memory_id=?",
                                    (old["op_id"], canonical(old), mid))
                else:
                    raise ValueError("Explicitly choose local or server")
            return {"memory_id": mid, "kept": keep}
        finally:
            self._release(owner)

    def status(self):
        with self.lock:
            pending = [dict(r) for r in self.db.execute("SELECT op_id,memory_id,status,error FROM outbox ORDER BY rowid")]
            saved = self._state()
        bound = bool(saved and saved["epoch"])
        return {"bound": bound, "pending": pending,
                "cache_identity_verified": bool(bound and saved["server"] == self.remote.url and saved["credential"] == digest(self.remote.token)),
                "state": "setup_required" if not bound else "needs_review" if any(r["status"] == "needs_review" for r in pending) else "queued" if pending else "synced"}

    def list_memories(self, project=None):
        with self.lock:
            return [dict(row) for row in self.db.execute(
                "SELECT * FROM memories WHERE NOT deleted AND (? IS NULL OR project=?) ORDER BY applied_sequence DESC,id", (project, project))]
