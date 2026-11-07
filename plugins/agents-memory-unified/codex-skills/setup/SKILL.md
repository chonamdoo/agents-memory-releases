---
name: setup
description: Install or update the Agents Memory 2.0.0 native project MCP for Codex from the verified public release.
---

This marketplace plugin supplies setup instructions. The real MCP is registered by the runtime installer in the actual project's .codex/config.toml. No memory server is connected solely by installing this plugin.

Read the current release quality status and installation guide:
- https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0
- https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md

Determine the actual project directory. Download the public runtime bundle and model companion, verify SHA256SUMS, then extract them. Follow the runtime guide and use install-unified.sh with --provider jev --client codex --project /actual/project. For a remote connection, use the documented --connect-server --client codex path; do not provision a local engine. Do not register a second transport alongside an existing agents-memory-cloud entry.

Keep credentials, databases and pending work outside the plugin cache. Obtain Jev or device credentials through private files or hidden terminal input, never chat or secret command arguments. Preserve the existing model, database, keys and pending intents on update. Do not silently migrate older providers or reprocess old conversations.

After installation, restart Codex in the project and follow normal project/hook trust review. Check agents-memory-cloud with setup_status; verify version, ready, server_ready and pending/conflict status. A connected installation does not prove model storage quality. Do not make provider calls merely to install the marketplace plugin. Installation prerequisites or unverified quality must be reported accurately.
