# Agents Memory MCP marketplace package 2.0.1

Package 2.0.1 updates marketplace setup instructions for the 2.0.0 prerelease runtime; it does not promote that runtime or change its storage-quality status. A distinct package version is required because Claude keeps the cached instructions when the package version is unchanged.

Install `agents-memory-unified@agents-memory` from the maintainer's public marketplace, `chonamdoo/agents-memory-releases`.

- Claude Code and OMP provide a local stdio MCP connector. Before secure runtime setup it exposes only `setup_status` and reports `setup_required`.
- Codex provides a dedicated setup skill. Run the verified public runtime installer with `--client codex --project /actual/project` to register the real project MCP. Installing the marketplace skill alone does not connect a server.

Claude Code one-step installation:

```text
/plugin install agents-memory-unified --marketplace chonamdoo/agents-memory-releases
```

See the [installation guide](https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md#플러그인-연결) and [current release quality status](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0). The release currently remains a prerelease. Marketplace availability does not imply a new Jev storage-quality pass or central directory approval.

The latest runtime is [`agents-memory-unified-2.0.0-source-search.tar.gz`](https://github.com/chonamdoo/agents-memory-releases/tree/main/release-candidates/v2.0.0-source-search), checked with `SOURCE-SEARCH-SHA256SUMS` in the same candidate directory. It is currently a repository download; adding it to the release asset list is blocked by upload authentication. Both the server and MCP client must be updated to expose `source_search`. The older `search-calibrated` and original trial bundles lack that tool. The unchanged model companion remains a v2.0.0 release asset checked with the original `SHA256SUMS`. Claude/Codex/OMP are frontends; Jev performs storage judgment. Keep keys, databases and pending work outside the plugin cache. Keys belong in private files or hidden terminal entry, never chat. Upgrade preserves the selected Jev model and database; older providers are not silently migrated.

The bundled connector performs no network download or model call before setup. After setup it executes the owned runtime launcher and uses the private local connection. MCP tools read or change authorized memories in that runtime. Optional project hooks/extensions are installed separately and use each host's normal trust review. Remote connections use the documented direct client installer.

MIT; see LICENSE. Maintained by chonamdoo; report issues in the public repository. Linux x86_64 protocol/host verification is recorded separately. macOS arm64 is cross-compiled; no new macOS real-device claim is made.
