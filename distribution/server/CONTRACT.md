# Collaboration 0.2 contract and release boundary

This is the implementation contract for the accepted minimal-change plan. Independent audit counterexamples are preserved in the earlier audit directories; their failing evidence is not rewritten as passing evidence. Regression tests now assert the desired behavior explicitly.

## Data and identity

A personal replica is bound online to an HTTPS origin, installation UUID and account UUID before the first durable enqueue. A new account/server needs a separate profile and SQLite file. Pending data is never silently adopted by a different destination. A changed credential must be verified against the bound identity. An old unbound 0.1 queue is preserved and refused; the operator must explicitly export/select its intended destination.

Each intent has an immutable operation UUID, memory UUID, project, kind, base revision, text/deletion and optional session/source IDs. Operation UUID reuse with different content is rejected. Memory/summary/prompt remain distinct kinds. Existing entity project/kind cannot be changed by an update. The client preserves session/source IDs on edits unless explicitly supplied. This does not claim lossless import of arbitrary external transcript formats.

Raw prompt upload requires explicit account opt-in and explicit client consent. Prompts sync privately but are excluded from personal semantic recall, team search, team brief and automatic MCP context. A bridge upload opt-in is different from a team sharing mapping. Server operators can read uploaded content: this is not end-to-end encryption.

## Persistence and progress

1. `queued`: the intent is committed to the local SQLite outbox (FULL synchronous).
2. Server acknowledgement: the account transaction committed data, change record, sequence and hash checkpoint. A dropped response is an uncertain outcome, not a failed write.
3. `applied`: a verified change and its cursor were committed atomically to the local projection; only then is the matching intent removed from the outbox.
4. Available: that client can read the projection, and online recall uses the server search path. Search completeness/semantic quality is not proven by a successful result.

Convergence assumes writes eventually stop, connectivity and authorized credentials are restored, and normal retry cycles run. One revision conflict is surfaced as `needs_review`; unrelated uploads and downloads proceed. Conflicts require an explicit local/server choice. No automatic last-writer-wins or semantic merge is claimed. Old and pending intents are not rewritten after an uncertain acknowledgement.

A checkpoint contains epoch, cursor and the deterministic hash of the prefix of the account log. The client validates the prefix before uploading and the server rechecks it under its account transaction lock. A restored history must not become accepted merely by growing past an old cursor. Hashes detect divergent histories from a trusted server; they do not authenticate a malicious server.

Explicit recovery rebuilds from sequence zero and archives the previous projection and queue locally. Pending intents remain for review unless the rebuilt history proves the identical operation was committed. Restored-away acknowledged data is retained in the archive, not automatically resurrected. A recovery request against matching history is a no-op. Recovery is not full backup restoration or conflict resolution.

Deletion excludes the current record from search and propagates a tombstone. Historical logs, local recovery archives and backups may still contain prior text. Permanent erasure is a separate operator retention task.

## Authorization

New HTTP requests and MCP tool calls authenticate against current credentials/account state. Team candidates require current reader membership and project grants, active author membership/account and a current sharing mapping. Completed unshare/leave/removal/key revocation must exclude content from new search/brief calls. In-flight requests and already delivered copies are outside revocation guarantees. Team data is never served from an offline client cache.

Device keys are account-scoped read-only or read/write. Current team/project authorization applies in addition. A data write key cannot list/mint/revoke credentials. The operator restore-epoch command rotates the epoch and revokes all restored credentials before access is reopened; it serializes with key issuance. Restoring externally without this procedure cannot preserve post-backup revocations. Local operator-issued manager keys can inventory credentials and revoke a credential subtree. There is no per-device project whitelist, expiry policy or hosted identity provider in this preview. Native Windows ACL security is not claimed; use WSL2 Linux storage.

## Supported paths and release gates

Default registered stdio MCP uses the persistent replica and runs periodic sync. It reads bounded recent personal project memory at MCP initialization, without waiting more than two seconds for the initial sync and delivers it in `instructions`; host consumption and the model's use of that context remain unverified. Question-specific recall is a tool call, not guaranteed prompt interception. No automatic transcript collection is added. Hindsight bridge reads explicitly selected stored units only and does not merge cloud changes back into Hindsight.

Direct HTTP MCP and the legacy Go proxy are online paths; their writes bypass the client outbox. Stable operation IDs make retries idempotent, but those paths cannot promise durable offline capture or replica checkpoint checks. They rely on the mandatory operator epoch reset and credential reissue after a restore.

Mandatory local gates: actual PostgreSQL/pgvector, two SQLite replicas, lost committed ACK, account/server switch, low/equal/regrown restore cursor, pending-write restore case, independent progress past conflict, metadata preservation, new requests after revocation, manager separation, reference-model negative controls, subprocess stdio restart and client registration retention. OS-native host app behavior, external TLS, semantic retrieval benchmarks, load/HA and permanent erasure require separate validation. Passing this suite qualifies a developer preview for personal-server trials, not a managed service or cross-platform stable release.
