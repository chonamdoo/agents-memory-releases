# Installation and explicit onboarding

## Verify and place the binary

Download agents-memory-macos-arm64.tar.gz, SHA256SUMS, install.sh and THIRD_PARTY_NOTICES.md from the same prerelease. In that download directory run:

```sh
shasum -a 256 -c SHA256SUMS
bash install.sh
```

The installer verifies the pinned archive, rejects an existing destination and copies only this versioned bundle. It does not initialize a DB, create credentials, install/start a service, connect an account or call a model. Keep the whole directory together and keep the executable named agents-memory. Use the path printed by the installer. Ad hoc signing is not Developer ID signing/notarization; no security bypass is performed.

## Prepare your own authority

Use an existing PostgreSQL 18.x database with pgvector >= 0.8.7 and private runtime/migrator DSN files prepared by its operator. Do not put a DSN or key in argv, a repository or the plugin. Existing deployments require an inspected migration/recovery plan; schema 0008 has no downgrade and replacing an older runtime is not an executable-only update.

The setup command asks separately for core execution location, DB location and judgment route. This preview initializes a local core with IP-loopback or Unix-socket PostgreSQL only. Cloud execution and cloud DB initialization are explicitly unsupported; they do not fall back to local. An existing approved remote client deployment is a separate flow.

Run `agents-memory setup --help` for all required identity/path arguments. Use `--plan-only` to validate the installation choice without reading DSNs/keys, creating state or contacting models. For unattended selection use `--non-interactive --execution-environment local --database-location local --judge agent` with the required private paths and identity arguments. Actual initialization creates authority data and credentials and must be explicitly authorized. Existing settings are not overwritten; only a matching setup may be resumed.

- Jev: `--judge jev --jev-key-file /absolute/private/key-file --jev-policy allow --ack-jev-egress`. Uses the existing TypeSafe API route.
- Subscription: `--judge subscription --subscription-host claude|codex|omp --subscription-policy allow --ack-subscription-egress`, optionally pinning `--subscription-executable`. Uses an existing official CLI login, never extracts login tokens and never treats a subscription as API credit. Synthetic CLI verification may consume subscription quota.
- Coding agent: `--judge agent` leaves judgment to the agent's existing MCP path. No background model route is enabled implicitly.

Only after explicit operator setup should you register a project and issue a narrowly scoped agent credential. Service installation/start and optional native capture hooks are separate explicit operations. Do not load both a direct native MCP registration and this marketplace MCP transport for the same integration.

## Claude Code marketplace

Requires Claude Code 2.1.310 or later for this tested configuration:

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory@agents-memory
/agents-memory:setup
```

The plugin initially refuses to connect. Read the setup skill, prepare a private config and a scoped agent token file outside the plugin cache, then set plugin configuration in `/plugin configure agents-memory@agents-memory`. The plugin stores paths, not token values. Enable connection and acknowledge that the core transport can recover an already-enabled, receipt-owned service. It never installs a service or changes its stopped latch. Downloading the pinned runtime needs a separate opt-in; otherwise select a verified installed runtime directory.

The plugin supplies on-demand MCP tools, not automatic capture or guaranteed recall. Native capture hooks are a separate opt-in integration. A plugin update/cache relocation does not move authority data or credentials. Plugin data stores only runtime dependencies and may be removed by Claude Code on uninstall; do not store DB state, journals or tokens there.

## Updating this preview

Download/install the new versioned bundle without overwriting the old one. This does not replace a running service or existing native hooks. Use an explicit operator-controlled update and owned host uninstall/reinstall with the same scoped config/token files and original prompt-recall choice. Retain old queues; never replay another generation automatically. No DB reset is required or performed. Validate readiness and MCP before changing your integration.

## Subscription host/model selection

The supported server subscription routes are pinned: Codex uses gpt-6.1-terra; Claude Code uses claude-haiku-5-5. Choose only the host your organization permits and that is already officially signed in. No cross-provider or API-credit fallback is performed. Optional model availability still depends on the account; a configured route is not proof of a successful model response.

For a new, separately authorized authority, setup selection is --judge subscription --subscription-host codex (or claude) --subscription-policy allow --ack-subscription-egress. Keep the required identity/DB/private-path arguments from setup --help. Operator enrollment verifies the selected CLI and creates a scoped local worker credential; it never requests a new provider API key. Do not run enrollment where local credential issuance or source egress is forbidden. Existing installations require explicit operator approval before changing routes. The plugin does not perform these actions automatically.

Check the existing login locally with codex login status or claude auth status. Do not paste credential values or private DSNs into chat, the plugin cache or a repository. New account login remains a separate user action. On this preview, actual Codex MCP model consumption and real E5 quality remain unverified; do not confuse protocol smoke with those checks.
