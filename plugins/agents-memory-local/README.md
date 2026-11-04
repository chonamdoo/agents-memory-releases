# agents-memory-local 1.0.6

macOS hotfix: matches PostgreSQL's `vector.dylib` filename and automatically repairs verified 1.0.5 installations without changing keys, model settings or database data. Existing OMP users: `omp plugin marketplace update agents-memory`, then `omp plugin upgrade agents-memory-local@agents-memory`. Confirm version 1.0.6 and restart OMP. Upgrading without refreshing the marketplace may reinstall the cached old version.

Automatic local memory MCP for Claude Code, Codex and OMP. On first MCP connection, the connector immediately answers `setup_status`, opens a local browser form for your one-time Jev / subscribed Claude / subscribed Codex choice, then installs the pinned binary core, E5 search embeddings, native PostgreSQL/pgvector and API. No Docker, Colima or system Python is required. Existing choices and saved keys are reused on updates.

Requires Apple Silicon **macOS 15+** and the selected subscription CLI's existing installation/login. Jev's key is entered only in the local form and stored in a user-private file. OMP is a connection target, not a judgment provider. Setup makes no paid model calls and scans no histories. Session and recall guidance now requests project memory before the first substantive answer, with a keyword fallback and saved PR-rule checks. These are host-model instructions, not enforcement over other tools.

Claude Code:

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory-local@agents-memory
```

OMP:

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
```

Connect MCP in your project. If the browser does not open, call `setup_status` for its local address. The stable tool list is available immediately for clients that cache it; memory calls remain gated on actual readiness and work on the same connection after setup finishes. Host trust/approval still applies. The default runtime is `~/.local/share/agents-memory-hindsight`; it stays outside the plugin cache. Explicit `am-mcp stop` is respected. Existing Docker/external database receipts are preserved rather than silently migrated.

[Codex setup and full Korean guide](https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.6/distribution/mcp-local/README.ko.md). This is the maintainer's own marketplace, not an official directory listing. The older `agents-memory` plugin remains a separate Native preview. Linux end-to-end verification does not establish physical macOS execution; release evidence states that limit. Binaries use ad hoc signing without Developer ID/notarization.
