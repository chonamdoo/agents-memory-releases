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

Use agents-memory-unified-2.0.0-request-scope-v16.tar.gz and JEV197-SHA256SUMS from the reviewed candidate directory:
- https://github.com/chonamdoo/agents-memory-releases/tree/main/release-candidates/v2.0.0-jev197
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/main/release-candidates/v2.0.0-jev197/agents-memory-unified-2.0.0-request-scope-v16.tar.gz
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/main/release-candidates/v2.0.0-jev197/JEV197-SHA256SUMS

The candidate is currently a repository download; adding it to the release asset list is blocked by upload authentication. Do not silently substitute the older search-calibrated or original trial bundle, which lacks source_search. The unchanged model companion remains a v2.0.0 release asset verified with the original SHA256SUMS. Update both the server runtime and MCP client, restart the host, and check that source_search is listed. This tool searches captured original submissions in an explicitly named personal project; returned originals are untrusted evidence, not verified memories. Do not inject originals into startup context or claim the candidate has passed live Jev quality gates.

This candidate includes the v16 mixed-language bare retention request correction. The original single-author live Jev cohort had 79/80 legitimate explicit retentions; the corrected regression and quoted-attack defense passed two targeted live checks. All 197 approved attempts have been consumed. Do not describe those targeted checks as a new passing full release cohort.
