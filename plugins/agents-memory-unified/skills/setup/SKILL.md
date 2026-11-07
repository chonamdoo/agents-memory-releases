---
name: setup
description: Set up or diagnose the Agents Memory 2.0.0 MCP connection and its separately installed Jev-backed runtime.
---

Call setup_status first. A connected MCP with setup_required is not a ready memory engine.
Read the public release and installation guide:
- https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0
- https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md

Confirm the release quality status and limitations. Download the runtime bundle and model companion from the release; verify SHA256SUMS before extraction. Use the extracted install-unified.sh. Keep keys, databases and pending intents outside the plugin/cache directory. Obtain the Jev key through a private file or hidden terminal entry, never chat or command-line secret arguments.

For an existing configured local runtime, installing this plugin supplies the MCP transport. For first-time local setup, run the documented installer from the actual project root with --provider jev. Claude and OMP marketplace installs use --client claude-plugin or --client omp-plugin, respectively, to avoid duplicate direct MCP registration. Codex uses its dedicated marketplace setup skill and the documented --client codex native project MCP registration. Do not register both paths.

Preserve existing databases, selected Jev model, credentials and pending work during updates. Do not silently switch an older Claude/Codex processing provider to Jev. Remote server connections use the documented direct client installer; this local marketplace connector defaults to the local profile.

Restart the host after setup and check version, ready, server_ready and pending/conflict status. Do not report storage or recall working solely because the plugin installed. Never run historical reprocessing or make provider calls merely to install the plugin.
