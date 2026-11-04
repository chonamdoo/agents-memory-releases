---
name: setup
description: Set up this project's local memory MCP connection for Claude, Codex or OMP using the pinned public installer.
disable-model-invocation: true
---

Use the user's language. This plugin connects MCP tools; installing it does not read histories, start paid model requests or create a DB by itself.

When the user invokes this setup skill, explain that setup installs the pinned binary core and E5 search embeddings, prepares a dedicated local PostgreSQL/pgvector Docker volume (or uses their explicitly provided dedicated local DATABASE_URL), installs a macOS LaunchAgent, and adds this project's selected MCP client entry. Docker Desktop must be installed and running for managed DB mode. Production target is Apple Silicon macOS 13+. OMP is a connection target, not an admission model provider.

Ask only for missing choices: MCP app Claude / Codex / OMP (multiple allowed), and memory admission Jev / subscribed Claude / subscribed Codex. Recommend claude-sonnet-5-5 for Claude and gpt-6.1-terra for Codex; let the user choose another exact model. Existing installations preserve their provider, model and Jev key. Do not change providers merely because the MCP app changes. Current session authorization applies; do not ask again for actions the user already requested.

For the Claude marketplace plugin connection, run this project's trusted installer:

```sh
bash "${CLAUDE_PLUGIN_ROOT}/scripts/install.sh" --client claude-plugin --project "$PWD"
```

For noninteractive subscription setup, add `--provider local-llm --judge-host claude --model claude-sonnet-5-5 --executable /absolute/path/to/claude` or the equivalent Codex options. For additional apps, repeat `--client codex` / `--client omp`; the same local service is shared. Never write a duplicate direct Claude MCP entry when the installed marketplace plugin already supplies it.

Jev's key must be entered in the user's own terminal through the hidden prompt. Never request a key in chat, put it in command arguments, copy auth tokens, install another model provider or silently fall back. If a prompt requires a terminal, give the user the exact command for their terminal. Do not claim a working connection from configuration files alone.

After successful setup, ask the user to reconnect MCP/restart the host, and verify tool discovery. Use `~/.local/share/agents-memory-hindsight/bin/am-mcp status` for status; `stop` explicitly disables the LaunchAgent and is respected by the proxy. Existing database volumes, settings and project queues are preserved on updates. History import, automatic prompt capture and host context injection are separate explicit workflows; none is enabled by this plugin.
