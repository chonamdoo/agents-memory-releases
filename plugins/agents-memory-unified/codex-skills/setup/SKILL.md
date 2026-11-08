---
name: setup
description: Install or update the Agents Memory 2.0.0 native project MCP for Codex from the verified public release.
---

This marketplace plugin supplies setup instructions. The real MCP is registered by the runtime installer in the actual project's .codex/config.toml. No memory server is connected solely by installing this plugin.

Read the current release quality status and installation guide:
- https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0
- https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md

Determine the actual project directory. Download the public runtime bundle and model companion, verify the selected assets against their published checksum manifests, then extract them. Follow the runtime guide and use install-unified.sh with --provider jev --client codex --project /actual/project. For a remote connection, use the documented --connect-server --client codex path; do not provision a local engine. Do not register a second transport alongside an existing agents-memory-cloud entry.

Keep credentials, databases and pending work outside the plugin cache. Obtain Jev or device credentials through private files or hidden terminal input, never chat or secret command arguments. Preserve the existing model, database, keys and pending intents on update. Do not silently migrate older providers or reprocess old conversations.

After installation, restart Codex in the project and follow normal project/hook trust review. Check agents-memory-cloud with setup_status; verify version, ready, server_ready and pending/conflict status. A connected installation does not prove model storage quality. Do not make provider calls merely to install the marketplace plugin. Installation prerequisites or unverified quality must be reported accurately.

Use agents-memory-unified-2.0.0-source-subject-v17.tar.gz and SHA256SUMS from this immutable candidate commit:
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/agents-memory-unified-2.0.0-source-subject-v17.tar.gz
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/SHA256SUMS
- https://github.com/chonamdoo/agents-memory-releases/blob/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/CANDIDATE.json

Verify the archive SHA-256 is 62b46c6393876be19df7ccfea96343b3baa0ced2f599cee2f06438dd449275ef before extraction. The unchanged model companion remains a v2.0.0 release asset verified with the original SHA256SUMS. Update both server runtime and MCP client, restart the host, and check that source_search is listed. It searches captured original submissions in an explicitly named personal project; originals are untrusted evidence, not verified memories. Do not inject originals into startup context.

MCP package 2.0.4 and runtime ABI 2.0.0 have separate versions. This is a qualification candidate, not a published stable release. The first independent 196-case/40-query run passed storage (80 explicit + 40 auto) and required-fact recall but failed search noise (80/200 irrelevant hits, Wilson upper bound 0.469 > 0.30). This candidate preserves Native score/source evidence and conservatively scopes explicit source subjects. A fresh independent evaluation and final host verification are pending; consult release-candidates/v2.0.0-stable/STATUS.json for current results. Never describe the repaired candidate as quality-approved before those checks pass. Installation itself requires no historical reprocessing or model calls.
