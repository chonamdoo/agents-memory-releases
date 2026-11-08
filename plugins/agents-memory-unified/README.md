# Agents Memory MCP marketplace package 2.0.4

Package 2.0.4 supplies the source-subject recall candidate and updated setup instructions. Runtime ABI stays 2.0.0. Qualification is pending; marketplace installation does not certify storage or recall quality. The package version changes so cached setup instructions update.

Install `agents-memory-unified@agents-memory` from the maintainer's public marketplace, `chonamdoo/agents-memory-releases`.

- Claude Code and OMP provide a local stdio MCP connector. Before secure runtime setup it exposes only `setup_status` and reports `setup_required`.
- Codex provides a dedicated setup skill. Run the verified public runtime installer with `--client codex --project /actual/project` to register the real project MCP. Installing the marketplace skill alone does not connect a server.

Claude Code one-step installation:

```text
/plugin install agents-memory-unified --marketplace chonamdoo/agents-memory-releases
```

See the [installation guide](https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md#플러그인-연결) and [current release quality status](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0). The release currently remains a prerelease. Marketplace availability does not imply a new Jev storage-quality pass or central directory approval.

The runtime is [`agents-memory-unified-2.0.0-source-subject-v17.tar.gz`](https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/agents-memory-unified-2.0.0-source-subject-v17.tar.gz), verified with [`SHA256SUMS`](https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/SHA256SUMS). The archive SHA-256 is `62b46c6393876be19df7ccfea96343b3baa0ced2f599cee2f06438dd449275ef`. See the [candidate identity](https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/CANDIDATE.json) and [current qualification status](../../release-candidates/v2.0.0-stable/STATUS.json). The first independent run passed all 120 positive storage cases and all required recall facts, but failed noise; the repaired candidate awaits a fresh independent run. The model companion remains the v2.0.0 asset verified with its original checksums. Keep keys, databases and pending work outside the plugin cache. Upgrade preserves the selected model and database; older providers are not silently migrated.

The bundled connector performs no network download or model call before setup. After setup it executes the owned runtime launcher and uses the private local connection. MCP tools read or change authorized memories in that runtime. Optional project hooks/extensions are installed separately and use each host's normal trust review. Remote connections use the documented direct client installer.

MIT; see LICENSE. Maintained by chonamdoo; report issues in the public repository. Linux x86_64 protocol/host verification is recorded separately. macOS arm64 is cross-compiled; no new macOS real-device claim is made.
