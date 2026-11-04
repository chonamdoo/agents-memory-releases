"""Explicit opt-in export of stored memory units, never original prompts/history."""
from __future__ import annotations

import hashlib
import http.client
import json
from urllib.parse import quote, urlsplit
from uuid import NAMESPACE_URL, uuid5


class HindsightBridge:
    def __init__(self, replica, url, bank, project):
        parsed = urlsplit(url)
        if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.path not in {"", "/"}
                or parsed.query or parsed.fragment):
            raise ValueError("Hindsight source must be an explicitly selected local loopback API")
        if not bank or len(bank) > 128:
            raise ValueError("Choose an explicit Hindsight bank")
        self.replica, self.host, self.port = replica, parsed.hostname, parsed.port or 80
        self.bank, self.project = bank, project
        replica.db.execute("""CREATE TABLE IF NOT EXISTS hindsight_export(
            bank TEXT NOT NULL,project TEXT NOT NULL,source_id TEXT NOT NULL,digest TEXT NOT NULL,
            PRIMARY KEY(bank,project,source_id))""")
        replica.db.commit()

    def page(self, offset):
        connection = http.client.HTTPConnection(self.host, self.port, timeout=15)
        try:
            connection.request("GET", f"/v1/default/banks/{quote(self.bank, safe='')}/memories/list?limit=100&offset={offset}")
            response = connection.getresponse()
            raw = response.read(4_194_305)
            if response.status != 200 or len(raw) > 4_194_304:
                raise ValueError("Local Hindsight memory listing unavailable")
            value = json.loads(raw)
            if not isinstance(value.get("items"), list) or not isinstance(value.get("total"), int):
                raise TypeError("Unexpected Hindsight memory listing")
            return value
        finally:
            connection.close()

    def stage(self):
        offset, staged = 0, 0
        while True:
            page = self.page(offset)
            for item in page["items"]:
                source_id, text = item.get("id"), item.get("text")
                if not isinstance(source_id, str) or not isinstance(text, str) or not text.strip():
                    continue
                content_digest = hashlib.sha256(text.encode()).hexdigest()
                prior = self.replica.db.execute("SELECT digest FROM hindsight_export WHERE bank=? AND project=? AND source_id=?",
                                                (self.bank, self.project, source_id)).fetchone()
                if prior and prior[0] == content_digest:
                    continue
                mid = str(uuid5(NAMESPACE_URL, f"agents-memory:hindsight:{self.bank}:{self.project}:{source_id}"))
                if self.replica.db.execute("SELECT 1 FROM outbox WHERE memory_id=?", (mid,)).fetchone():
                    continue
                existing = self.replica.db.execute("SELECT text,deleted FROM memories WHERE id=?", (mid,)).fetchone()
                # A local export must not resurrect an intentional cloud deletion.
                # Another PC may already have exported this exact memory.
                if not existing or (not existing["deleted"] and existing["text"] != text):
                    self.replica.stage(self.project, text, memory_id=mid, source_id=source_id)
                    staged += 1
                with self.replica.db:
                    self.replica.db.execute("INSERT INTO hindsight_export VALUES(?,?,?,?) ON CONFLICT(bank,project,source_id) DO UPDATE SET digest=excluded.digest",
                                            (self.bank, self.project, source_id, content_digest))
            offset += len(page["items"])
            if offset >= page["total"]:
                break
            if not page["items"] or offset >= 100_000:
                raise ValueError("Incomplete or oversized local listing; no deletion inferred")
        return {"staged": staged, "source": "stored_memory_units", "original_prompts_read": False}
