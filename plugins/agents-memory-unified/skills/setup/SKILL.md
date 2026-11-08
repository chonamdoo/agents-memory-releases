---
name: setup
description: Set up or diagnose the Agents Memory 2.0.0 MCP connection and its separately installed Jev-backed runtime.
---

Call setup_status first. A connected MCP with setup_required is not a ready memory engine.
Read the public release and installation guide:
- https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0
- https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md

Confirm the release quality status and limitations. Download the runtime bundle from the candidate directory below and the model companion from the release; verify each with its own published checksum manifest before extraction. Use the extracted install-unified.sh. Keep keys, databases and pending intents outside the plugin/cache directory. Obtain the Jev key through a private file or hidden terminal entry, never chat or command-line secret arguments.

For an existing configured local runtime, installing this plugin supplies the MCP transport. For first-time local setup, run the documented installer from the actual project root with --provider jev. Claude and OMP marketplace installs use --client claude-plugin or --client omp-plugin, respectively, to avoid duplicate direct MCP registration. Codex uses its dedicated marketplace setup skill and the documented --client codex native project MCP registration. Do not register both paths.

Preserve existing databases, selected Jev model, credentials and pending work during updates. Do not silently switch an older Claude/Codex processing provider to Jev. Remote server connections use the documented direct client installer; this local marketplace connector defaults to the local profile.

Restart the host after setup and check version, ready, server_ready and pending/conflict status. Do not report storage or recall working solely because the plugin installed. Never run historical reprocessing or make provider calls merely to install the plugin.

Use agents-memory-unified-2.0.0-request-scope-v16.tar.gz and JEV197-SHA256SUMS from the reviewed candidate directory:
- https://github.com/chonamdoo/agents-memory-releases/tree/main/release-candidates/v2.0.0-jev197
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/main/release-candidates/v2.0.0-jev197/agents-memory-unified-2.0.0-request-scope-v16.tar.gz
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/main/release-candidates/v2.0.0-jev197/JEV197-SHA256SUMS

The candidate is currently a repository download; adding it to the release asset list is blocked by upload authentication. Do not silently substitute the older search-calibrated or original trial bundle, which lacks source_search. The unchanged model companion remains a v2.0.0 release asset verified with the original SHA256SUMS. Update both the server runtime and MCP client, restart the host, and check that source_search is listed. This tool searches captured original submissions in an explicitly named personal project; returned originals are untrusted evidence, not verified memories. Do not inject originals into startup context or claim the candidate has passed live Jev quality gates.

This candidate includes the v16 mixed-language bare retention request correction. The original single-author live Jev cohort had 79/80 legitimate explicit retentions; the corrected regression and quoted-attack defense passed two targeted live checks. All 197 approved attempts have been consumed. Do not describe those targeted checks as a new passing full release cohort.
