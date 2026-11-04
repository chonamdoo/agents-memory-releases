# agents-memory-local 1.0.8

> **1.0.8 development draft; stable remains 1.0.7. Native Windows is not released.**

Local memory MCP for Claude Code, Codex and OMP. The selected MCP client is independent from the one-time Jev / subscribed Claude / subscribed Codex admission provider. E5 search embeddings, native PostgreSQL/pgvector and the compiled API core are included. Saved keys, model choices and DB data survive updates.

Apple Silicon macOS 15+ is the current release target. Windows x64 adds a **WSL2/Ubuntu 24.04 preview path** with the CLI and all runtime components inside the same WSL distribution. Windows-native clients and ARM64 are not supported by that installer. Physical Windows/WSL execution is not yet verified.

## Claude Code

```sh
claude plugin marketplace add chonamdoo/agents-memory-releases
claude plugin install agents-memory-local@agents-memory
```

Update and restart Claude:

```sh
claude plugin marketplace update agents-memory
claude plugin update agents-memory-local@agents-memory
```

## Codex

Use the project MCP installer for both installation and updates, then restart Codex:

```sh
curl -fsSL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.8/distribution/mcp-local/install.sh -o /tmp/agents-memory-mcp-install.sh
bash /tmp/agents-memory-mcp-install.sh --client codex --project "$PWD"
```

The marketplace plugin's Claude path variable is not expanded by Codex 0.163.0. Its native plugin format also changes the subprocess cwd to the plugin, not the project. Direct MCP registration preserves project routing and other settings; native marketplace installation success alone does not establish MCP readiness.

## OMP

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
```

Update and fully restart OMP:

```sh
omp plugin marketplace update agents-memory
omp plugin upgrade agents-memory-local@agents-memory
```

Connect MCP from the actual project. The plugin immediately answers `setup_status`, opens a local browser form once and prepares the runtime. If the browser does not open, use `setup_status.setup_url`. The first tool list is stable; memory calls stay gated until ready. Check **version 1.0.8, ready true**. Explicit stop and host project trust are respected.

[Windows PowerShell installer, supported scope and full guide](https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.8/distribution/mcp-local/README.ko.md). These are maintainer marketplace packages, not official directory listings. The old Native preview remains separate. The verified macOS pgvector symlink repair is retained. Setup makes no paid model calls and scans no histories. New-session recall guidance requests saved project rules but cannot enforce the host model's actions. Physical macOS/Windows execution is not claimed.
