---
name: setup
description: Set up or diagnose the Agents Memory 2.0.0 MCP connection and its separately installed Jev-backed runtime.
---

Call setup_status first. A connected MCP with setup_required is not a ready memory engine.
Read the public release and installation guide:
- https://github.com/chonamdoo/agents-memory-releases/blob/main/release-candidates/v2.0.0-stable/STATUS.json
- https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/server/README.ko.md

Confirm the release quality status and limitations. Download the runtime bundle from the candidate directory below and the model companion from the release; verify each with its own published checksum manifest before extraction. Use the extracted install-unified.sh. Keep keys, databases and pending intents outside the plugin/cache directory. Obtain the Jev key through a private file or hidden terminal entry, never chat or command-line secret arguments.

For an existing configured local runtime, installing this plugin supplies the MCP transport. For first-time local setup, run the documented installer from the actual project root with --provider jev. Claude and OMP marketplace installs use --client claude-plugin or --client omp-plugin, respectively, to avoid duplicate direct MCP registration. Codex uses its dedicated marketplace setup skill and the documented --client codex native project MCP registration. Do not register both paths.

Preserve existing databases, selected Jev model, credentials and pending work during updates. Do not silently switch an older Claude/Codex processing provider to Jev. Remote server connections use the documented direct client installer; this local marketplace connector defaults to the local profile.

Restart the host after setup and check version, ready, server_ready and pending/conflict status. Do not report storage or recall working solely because the plugin installed. Never run historical reprocessing or make provider calls merely to install the plugin.

Use agents-memory-unified-2.0.0-source-subject-v17.tar.gz and SHA256SUMS from this immutable candidate commit:
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/agents-memory-unified-2.0.0-source-subject-v17.tar.gz
- https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/SHA256SUMS
- https://github.com/chonamdoo/agents-memory-releases/blob/1903a3d379983883c6069692f249fe470d7d0a61/release-candidates/v2.0.4-relevance/CANDIDATE.json

Verify the archive SHA-256 is 62b46c6393876be19df7ccfea96343b3baa0ced2f599cee2f06438dd449275ef before extraction. The unchanged model companion remains a v2.0.0 release asset verified with the original SHA256SUMS. Update both server runtime and MCP client, restart the host, and check that source_search is listed. It searches captured original submissions in an explicitly named personal project; originals are untrusted evidence, not verified memories. Do not inject originals into startup context.

MCP package 2.0.4 and runtime ABI 2.0.0 have separate versions. Check the [published release status](https://github.com/chonamdoo/agents-memory-releases/blob/main/release-candidates/v2.0.0-stable/STATUS.json) for current qualification and publication results. Artifact identity and a successful plugin installation alone do not certify model quality. The earlier independent run passed positive storage and required-fact recall but failed search noise; its failure is preserved in the release evidence. Use the registered repaired-candidate results in STATUS.json, rather than assuming a pass from this setup skill. Installation requires no historical reprocessing or model calls.
