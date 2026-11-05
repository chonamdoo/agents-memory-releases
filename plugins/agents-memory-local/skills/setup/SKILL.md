---
name: setup
description: Set up agents-memory-local 1.0.8 with the common Hindsight engine for Claude, Codex or OMP.
---

Read setup_status first. An MCP connection is not memory readiness. Use the official 1.0.8 installer and guide:
https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.8/distribution/server/README.ko.md

Run from the actual project root. Select only Claude CLI, Codex CLI or Jev for memory processing; OMP is an MCP client. Use --client claude-plugin or --client omp-plugin for marketplace installs to avoid duplicate direct MCP registration. Codex uses --client codex.

Jev credentials must be entered privately in the user's terminal, never chat or command arguments. Do not read or print their content. Use the selected CLI login on the engine host; never copy OAuth credentials between machines. Do not run legacy 1.0.7 setup.py or download a separate generation model.

After setup, reload MCP and verify version 1.0.8 and server_ready. Preparing, failed or queued is not processing complete. Preserve existing databases, keys and pending intents. No automatic legacy data reprocessing.
