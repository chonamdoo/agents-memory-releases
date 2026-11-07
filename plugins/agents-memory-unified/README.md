# Agents Memory 2.0.0 MCP integration

Install `agents-memory-unified@agents-memory` from the maintainer's public marketplace, `chonamdoo/agents-memory-releases`.

- Claude Code and OMP provide a local stdio MCP connector. Before secure runtime setup it exposes only `setup_status` and reports `setup_required`.
- Codex provides a dedicated setup skill. Run the verified public runtime installer with `--client codex --project /actual/project` to register the real project MCP. Installing the marketplace skill alone does not connect a server.

Claude Code one-step installation:

```text
/plugin install agents-memory-unified --marketplace chonamdoo/agents-memory-releases
```

See the [installation guide](https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md#플러그인-연결) and [current release quality status](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0). The release currently remains a prerelease. Marketplace availability does not imply a new Jev storage-quality pass or central directory approval.

The runtime and pinned models are separate verified release assets. Claude/Codex/OMP are frontends; Jev performs storage judgment. Keep keys, databases and pending work outside the plugin cache. Keys belong in private files or hidden terminal entry, never chat. Upgrade preserves the selected Jev model and database; older providers are not silently migrated.

The bundled connector performs no network download or model call before setup. After setup it executes the owned runtime launcher and uses the private local connection. MCP tools read or change authorized memories in that runtime. Optional project hooks/extensions are installed separately and use each host's normal trust review. Remote connections use the documented direct client installer.

MIT; see LICENSE. Maintained by chonamdoo; report issues in the public repository. Linux x86_64 protocol/host verification is recorded separately. macOS arm64 is cross-compiled; no new macOS real-device claim is made.
