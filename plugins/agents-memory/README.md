# agents-memory Claude Code plugin

In Claude Code, install with `/plugin install agents-memory --marketplace chonamdoo/agents-memory-releases`, then read `/agents-memory:setup`. This is the maintainer’s own marketplace, not an Anthropic directory listing.

Read `/agents-memory:setup` before connecting. macOS arm64 only, tested Claude Code 2.1.310. This plugin provides on-demand MCP tools, not automatic chat capture or guaranteed recall. It does not bootstrap an authority, issue credentials, install a service or select a model provider.

In `/plugin configure agents-memory@agents-memory`, select an existing private authority config and a scoped agent-token file outside plugin/cache directories. Choose a verified installed runtime directory, or separately opt in to the pinned archive download. Connection is disabled until explicitly enabled and managed-service recovery is acknowledged. An explicit core service stop is respected.

Runtime dependencies live under CLAUDE_PLUGIN_DATA, not CLAUDE_PLUGIN_ROOT. Plugin updates can move the root. Config, tokens, PostgreSQL state and deletion journals must stay outside both directories. Paths are passed as separate arguments/environment values, so spaces in cache paths are supported.

Core setup asks independently for execution location, DB location and judgment route. This release initializes a local authority with existing loopback/Unix PostgreSQL18.x + pgvector>=0.8.7. Cloud initialization is explicitly unsupported. Jev requires an existing key file and independent consent; official subscription CLIs require their existing login and independent consent, and verification can use quota. No subscription token extraction or implicit fallback is used.

Download is pinned to version and SHA256; cached/installed files are checked against a complete file/hash list before execution. Core is ad hoc signed, not Developer ID signed or notarized. The plugin does not bypass Gatekeeper. The Python implementation is not shipped; the included runtime means no separate Python installation is needed. See the release README and license notices for validation limits and reverse-engineering limitations.
