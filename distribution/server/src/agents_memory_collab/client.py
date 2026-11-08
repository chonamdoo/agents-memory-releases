"""Cross-device SQLite outbox. Network failures never discard pending writes."""
from __future__ import annotations

import json
import os
import re
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

_DEFAULT_TIMEOUT = object()


def _reject_source_secrets(text):
    try:
        from agents_memory.capture_guard import contains_source_secret
        rejected = contains_source_secret(text)
        if type(rejected) is not bool:
            raise TypeError("Invalid source guard result")
    except Exception:
        raise Failure(503, "memory_source_guard_unavailable") from None
    if rejected:
        raise Failure(400, "memory_source_contains_credentials")


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
    def __init__(self, url: str, token: str, *, timeout=_DEFAULT_TIMEOUT):
        parsed = urlsplit(url)
        if (parsed.scheme not in {"https", "http"} or not parsed.netloc or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}
                or (parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"})):
            raise ValueError("Choose an HTTPS server origin; HTTP is loopback-only")
        if not token.startswith("amc_") or len(token) > 100 or any(c.isspace() for c in token):
            raise ValueError("Invalid credential format")
        self.url, self.token = url.rstrip("/"), token
        # Native recall has a 120s backend request deadline. A shorter default
        # would turn a healthy, slower search into an empty offline-cache hit.
        # Initialization, synchronization and lexical source lookup stay fast;
        # callers that supply a deadline retain control of every request.
        self.timeout = 10 if timeout is _DEFAULT_TIMEOUT else timeout
        self.search_timeout = 130 if timeout is _DEFAULT_TIMEOUT else timeout
        self.http = urllib.request.build_opener(NoRedirect(), urllib.request.ProxyHandler({}))

    def request(self, path, value=None, *, method=None):
        if not path.startswith("/v1/") or path.startswith("//"):
            raise ValueError("Invalid service path")
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode() if value is not None else None
        request = urllib.request.Request(self.url + path, data, method=method or ("POST" if data else "GET"),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            search = path == "/v1/recall" or re.fullmatch(r"/v1/teams/[0-9a-fA-F-]+/search", path)
            with self.http.open(request, timeout=self.search_timeout if search else self.timeout) as stream:
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
    def __init__(self, path: Path, remote: Remote, *, busy_timeout=10):
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
        self.db = sqlite3.connect(path, timeout=busy_timeout, check_same_thread=False, isolation_level=None)
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
            CREATE TABLE IF NOT EXISTS operation_intents(op_id TEXT PRIMARY KEY,intent TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS host_events(scope TEXT NOT NULL,project TEXT NOT NULL,host TEXT NOT NULL,event TEXT NOT NULL,source TEXT NOT NULL,capture_enabled INTEGER NOT NULL,context_prepared INTEGER NOT NULL,captured INTEGER NOT NULL,observed_at REAL NOT NULL,PRIMARY KEY(scope,project,host,event,source));
        """)
        additions_by_table = {
            "state": {"epoch": "TEXT", "chain_hash": "TEXT", "credential": "TEXT", "writable": "INTEGER NOT NULL DEFAULT 0", "memory_ready": "INTEGER NOT NULL DEFAULT 0", "memory_contract": "TEXT", "origin_aware": "INTEGER NOT NULL DEFAULT 0"},
            "memories": {"session_id": "TEXT", "source_id": "TEXT", "applied_sequence": "INTEGER NOT NULL DEFAULT 0", "processing_state": "TEXT NOT NULL DEFAULT 'legacy_pending'"},
            "outbox": {"status": "TEXT NOT NULL DEFAULT 'pending'", "error": "TEXT"},
            "worker": {"pid": "INTEGER"},
            "receipts": {"outcome": "TEXT NOT NULL DEFAULT 'applied'", "reason": "TEXT"},
            "operation_intents": {"memory_id": "TEXT", "digest": "TEXT"},
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
            memory = identity.get("memory", {})
            self.db.execute("UPDATE state SET memory_ready=?,memory_contract=?,origin_aware=? WHERE id=1",
                            (bool(memory.get("ready")), memory.get("contract"), memory.get("origin_aware") is True))
        return identity

    def stage(self, project, text=None, *, memory_id=None, kind="memory", deleted=False,
              allow_prompts=False, op_id=None, base_revision=None, session_id=None, source_id=None,
              origin=None):
        with self.transaction():
            saved = self._state()
            if not saved or not saved["epoch"]:
                raise Failure(409, "setup_required_before_queueing")
            if saved["server"] != self.remote.url or saved["credential"] != digest(self.remote.token):
                raise Failure(409, "verify_destination_before_queueing")
            if not saved["writable"]:
                raise Failure(403, "read_only_credential")
            identifier = UUID(str(op_id)) if op_id else uuid4()
            known = self.db.execute("SELECT intent,memory_id,digest FROM operation_intents WHERE op_id=?", (str(identifier),)).fetchone()
            frozen = self.db.execute("SELECT body FROM outbox WHERE op_id=?", (str(identifier),)).fetchone()
            frozen = json.loads(frozen["body"]) if frozen else None
            if memory_id:
                mid = str(UUID(str(memory_id)))
            elif known and known["memory_id"]:
                mid = known["memory_id"]
            elif frozen:
                mid = frozen["memory_id"]
            else:
                mid = str(uuid4())
            intent = digest(canonical({"memory_id": mid, "project": project, "kind": kind,
                                       "text": text, "deleted": deleted, "base_revision": base_revision,
                                       "session_id": session_id, "source_id": source_id, "origin": origin}))
            if known:
                if known["intent"] != intent:
                    raise Failure(409, "operation_id_reused")
                if known["digest"]:
                    received = self.db.execute("SELECT digest FROM receipts WHERE op_id=?", (str(identifier),)).fetchone()
                    if received and received["digest"] != known["digest"]:
                        raise Failure(409, "operation_id_reused")
                    result = self.outcome(identifier)
                    if result["state"] == "unknown":
                        raise Failure(409, "operation_history_requires_review")
                    return {"memory_id": mid, "op_id": str(identifier),
                            "queued": result["state"] in {"processing", "needs_review"},
                            "state": result["state"], "reason": result["reason"]}
                if not frozen:
                    raise Failure(409, "operation_history_requires_review")
            if frozen:
                if base_revision is None:
                    base_revision = frozen["base_revision"]
                if session_id is None:
                    session_id = frozen.get("session_id")
                if source_id is None:
                    source_id = frozen.get("source_id")
                if deleted:
                    kind, project = frozen["kind"], frozen["project"]
            old = None if frozen else self.db.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
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
            # An older server rejects unknown fields; never queue an operation it cannot accept.
            conveyed = origin is not None and not deleted and bool(saved["origin_aware"])
            if frozen and frozen.get("origin") is None:
                conveyed = False
            op = Operation(op_id=identifier, memory_id=UUID(mid),
                           project=project, kind=kind, base_revision=base_revision if base_revision is not None else old["revision"] if old else 0,
                           text=None if deleted else text, deleted=deleted, session_id=session_id, source_id=source_id,
                           origin=origin if conveyed else None)
            fingerprint = operation_digest(op.model_dump(mode="json"))
            self.db.execute("""INSERT INTO operation_intents(op_id,intent,memory_id,digest) VALUES(?,?,?,?)
                ON CONFLICT(op_id) DO UPDATE SET memory_id=excluded.memory_id,digest=excluded.digest""",
                (str(identifier), intent, mid, fingerprint))
            received = self.db.execute("SELECT digest,outcome,reason FROM receipts WHERE op_id=?", (str(op.op_id),)).fetchone()
            if received:
                if received[0] != fingerprint:
                    raise Failure(409, "operation_id_reused")
                return {"memory_id": mid, "op_id": str(op.op_id), "queued": False, "state": received["outcome"],
                        "reason": received["reason"]}
            pending = self.db.execute("SELECT op_id,body FROM outbox WHERE memory_id=? OR op_id=?", (mid, str(op.op_id))).fetchone()
            if pending:
                if pending["op_id"] != str(op.op_id):
                    raise Failure(409, "pending_operation_exists_resolve_first")
                if operation_digest(json.loads(pending["body"])) != fingerprint:
                    raise Failure(409, "operation_id_reused")
            else:
                _reject_source_secrets(canonical(op.model_dump(mode="json")))
                self.db.execute("INSERT INTO outbox(op_id,memory_id,body) VALUES(?,?,?)",
                                (str(op.op_id), mid, op.model_dump_json(exclude=None if op.origin else {"origin"})))
        result = {"memory_id": mid, "op_id": str(op.op_id), "queued": True, "state": "received", "memory_ready": False}
        if origin is not None:
            result["origin_conveyed"] = conveyed
        return result

    def _claim(self):
        owner = str(uuid4())
        with self.transaction():
            previous = self.db.execute("SELECT owner,expires,pid FROM worker WHERE id=1").fetchone()
            abandoned = False
            if previous["pid"] and os.name == "posix":
                try:
                    os.kill(previous["pid"], 0)
                    # A container's PID 1 may not reap exited host/MCP children.
                    # kill(pid, 0) also succeeds for zombies; they cannot renew a
                    # lease. Do not make every other client wait for expiry.
                    if sys.platform.startswith("linux"):
                        try:
                            process = (Path("/proc") / str(previous["pid"]) / "stat").read_text()
                            abandoned = process.rpartition(")")[2].split()[0] in {"Z", "X"}
                        except FileNotFoundError:
                            abandoned = True
                        except (PermissionError, IndexError):
                            pass
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
            if self._state()["memory_contract"] != "agents-memory-grounded-v1":
                raise Failure(409, "server_memory_contract_upgrade_required")
            # Detect restored or replaced histories before any pending upload.
            pulled = self._pull(owner)
            pushed = 0
            with self.lock:
                rows = self.db.execute("SELECT op_id,body FROM outbox WHERE status IN ('pending','acked') ORDER BY rowid").fetchall()
            attempted = []
            for row in [] if pull_only else rows:
                attempted.append(row["op_id"])
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
                discarded = result.get("discarded", [])
                if discarded:
                    if (result.get("epoch") != self._state()["epoch"] or ack or len(discarded) != 1
                            or discarded[0] != {"op_id": row["op_id"], "digest": operation_digest(body), "state": "discarded"}):
                        raise Failure(502, "invalid_discard_receipt")
                    reason = result.get("reasons", {}).get(row["op_id"]) if isinstance(result.get("reasons"), dict) else None
                    if not isinstance(reason, str) or not re.fullmatch(r"[a-z_]{1,64}", reason):
                        reason = "reason_not_reported_by_server"
                    with self.transaction():
                        self.db.execute("INSERT OR REPLACE INTO receipts(op_id,digest,outcome,reason) VALUES(?,?,'discarded',?)", (row["op_id"], operation_digest(body), reason))
                        self.db.execute("DELETE FROM outbox WHERE op_id=?", (row["op_id"],))
                    continue
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
            # Queue state is not a save result: report each attempted operation's own outcome.
            return {"pushed": pushed, "pulled": pulled, "cursor": self._state()["cursor"],
                    "outcomes": [self.outcome(op_id) for op_id in attempted], **self.status()}
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
                    self.db.execute("INSERT OR REPLACE INTO receipts(op_id,digest) VALUES(?,?)", (change["op_id"], change["digest"]))
                    self.db.execute("UPDATE memories SET processing_state=? WHERE id=?", (change.get("processing_state", "legacy_pending"), change["memory_id"]))
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
                fields = [row[1] for row in self.db.execute("PRAGMA table_info(memories)")]
                self.db.executemany("INSERT INTO memories(" + ",".join(fields) + ") VALUES(" + ",".join("?" for _ in fields) + ")",
                                    [tuple(row[field] for field in fields) for row in shadow.db.execute("SELECT * FROM memories")])
                self.db.execute("DELETE FROM receipts")
                self.db.executemany("INSERT INTO receipts(op_id,digest,outcome) VALUES(?,?,?)", [tuple(r) for r in shadow.db.execute("SELECT op_id,digest,outcome FROM receipts")])
                self.db.execute("UPDATE state SET epoch=?,cursor=?,chain_hash=?,credential=?,writable=? WHERE id=1",
                                (target["epoch"], target["cursor"], target["chain_hash"], target["credential"], target["writable"]))
                self.db.execute("UPDATE state SET memory_ready=?,memory_contract=?,origin_aware=? WHERE id=1",
                                (target["memory_ready"], target["memory_contract"], target["origin_aware"]))
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

    def outcome(self, op_id):
        """One operation's result. `applied` means committed on the server and in this replica."""
        with self.lock:
            receipt = self.db.execute("SELECT digest,outcome,reason FROM receipts WHERE op_id=?", (str(op_id),)).fetchone()
            pending = self.db.execute("SELECT body,status,error FROM outbox WHERE op_id=?", (str(op_id),)).fetchone()
        if receipt and pending and receipt["digest"] != operation_digest(json.loads(pending["body"])):
            return {"op_id": str(op_id), "state": "needs_review", "reason": "operation_id_reused"}
        if receipt:
            return {"op_id": str(op_id), "state": receipt["outcome"], "reason": receipt["reason"]}
        if pending:
            # acked: committed on the server, not yet pulled into this replica.
            return {"op_id": str(op_id), "state": "needs_review" if pending["status"] == "needs_review" else "processing",
                    "reason": pending["error"]}
        return {"op_id": str(op_id), "state": "unknown", "reason": None}

    def _host_event_scope(self):
        saved = self._state() or {}
        return digest(canonical({"server": self.remote.url, "credential": digest(self.remote.token),
                                 "epoch": saved.get("epoch"), "installation": saved.get("installation")}))

    def reset_host_events(self, project, hosts):
        from .automation_setup import host_capabilities
        hosts = list(dict.fromkeys(hosts))
        for host in hosts:
            host_capabilities(host)
        with self.transaction():
            self.db.executemany("DELETE FROM host_events WHERE scope=? AND project=? AND host=?",
                                [(self._host_event_scope(), project, host) for host in hosts])

    def record_host_event(self, project, host, event, *, capture_enabled, context_delivered, captured, source=None):
        from .automation_setup import host_capabilities
        if event not in host_capabilities(host)["events"]:
            raise ValueError("Unsupported host event")
        source = source or ""
        if source not in {"", "startup", "resume", "clear", "compact", "fork", "new", "manual", "auto"}:
            raise ValueError("Unsupported event source")
        if any(type(value) is not bool for value in (capture_enabled, context_delivered, captured)):
            raise ValueError("Invalid host event receipt")
        if captured and (not capture_enabled or event not in {"UserPromptSubmit", "before_agent_start"}):
            raise ValueError("Lifecycle events cannot capture")
        with self.transaction():
            self.db.execute(
                "INSERT INTO host_events VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(scope,project,host,event,source) DO UPDATE SET "
                "capture_enabled=excluded.capture_enabled,context_prepared=excluded.context_prepared,"
                "captured=excluded.captured,observed_at=excluded.observed_at",
                (self._host_event_scope(), project, host, event, source, int(capture_enabled),
                 int(context_delivered), int(captured), time.time()))

    def host_automation_status(self, project, hosts=None, *, capture_enabled=True):
        from .automation_setup import host_capabilities
        hosts = list(dict.fromkeys(hosts or []))
        with self.lock:
            rows = [dict(row) for row in self.db.execute(
                "SELECT host,event,source,capture_enabled,context_prepared,captured,observed_at "
                "FROM host_events WHERE scope=? AND project=? ORDER BY observed_at",
                (self._host_event_scope(), project))]
        result = {}
        for host in hosts:
            capabilities = host_capabilities(host)
            events = [row for row in rows if row["host"] == host]
            observed = bool(events)
            captured = any(row["captured"] for row in events)
            prepared = any(row["context_prepared"] for row in events)
            result[host] = {"execution": "observed" if observed else "unverified",
                            "capture": "disabled" if not capture_enabled else "observed" if captured else "unverified",
                            "context": "prepared" if prepared else "unverified",
                            "capabilities": capabilities, "observed_events": events}
        return {"hosts": result, "capture_enabled": capture_enabled,
                "automation_ready": bool(result) and all(
                    row["execution"] == "observed" and row["context"] == "prepared"
                    and row["capture"] in {"disabled", "observed"} for row in result.values()),
                "evidence_scope": "adapter_execution_and_context_preparation_only",
                "native_trust": "unverified", "model_compliance": "unverified"}

    def status(self):
        with self.lock:
            pending = [dict(r) for r in self.db.execute("SELECT op_id,memory_id,status,error FROM outbox ORDER BY rowid")]
            recent = [{"op_id": r["op_id"], "state": r["outcome"], "reason": r["reason"]}
                      for r in self.db.execute("SELECT op_id,outcome,reason FROM receipts ORDER BY rowid DESC LIMIT 10")]
            saved = self._state()
        bound = bool(saved and saved["epoch"])
        # `state` describes the local queue and `memory_ready` the server engine; neither is
        # the result of a particular save. `recent` lists terminal per-operation results.
        return {"bound": bound, "pending": pending, "recent": recent,
                "memory_ready": bool(saved and saved["memory_ready"]), "memory_contract": saved["memory_contract"] if saved else None,
                "cache_identity_verified": bool(bound and saved["server"] == self.remote.url and saved["credential"] == digest(self.remote.token)),
                "state": "setup_required" if not bound else "needs_review" if any(r["status"] == "needs_review" for r in pending) else "queued" if pending else "synced"}

    def list_memories(self, project=None):
        with self.lock:
            return [dict(row) for row in self.db.execute(
                "SELECT * FROM memories WHERE NOT deleted AND processing_state='ready' AND (? IS NULL OR project=?) ORDER BY applied_sequence DESC,id", (project, project))]
