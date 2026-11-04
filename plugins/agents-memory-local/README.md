# agents-memory-local

Current local Hindsight MCP plugin for Claude Code. The same setup helper connects Codex and OMP. Memory admission remains a separate choice of Jev or your signed-in Claude/Codex CLI. OMP is a connection target.

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory-local@agents-memory
/agents-memory-local:setup
```

Requires Apple Silicon macOS 13+, running Docker Desktop (or an explicitly provisioned dedicated loopback PostgreSQL 18 + pgvector DB), and the selected provider's existing login/key. Setup downloads the SHA256-pinned 1.0.2 binary core and E5 search assets, prepares owned local state and installs a macOS user LaunchAgent. No generation model weights, cloud resources, history scan, automatic chat capture or context injection are installed. The initial plugin connection can report unavailable until setup completes; reconnect MCP afterward and approve the host's project trust prompt.

This plugin uses the default `~/.local/share/agents-memory-hindsight` installation. Config, keys, queues, database receipts and the MCP gateway stay outside the plugin/cache. Updating or removing the plugin does not erase persistent state. For custom prefixes use the common helper with direct client registration instead. Explicit `am-mcp stop` is respected.

OMP also accepts this marketplace with `omp plugin marketplace add chonamdoo/agents-memory-releases` and `omp plugin install agents-memory-local@agents-memory`; run the common setup helper with `--client omp` for initial runtime preparation.

This is the maintainer's own marketplace, not an official Anthropic directory listing. The old `agents-memory` plugin remains the separate Native preview. Read the [full setup and operating guide](https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.3/distribution/mcp-local/README.ko.md).

Linux validates the same binary core, gateway and native client formats. macOS device execution is not claimed. The binary core is ad hoc signed, not Developer ID signed/notarized. Jev keys are stored privately (0600), not in an encrypted Keychain.
