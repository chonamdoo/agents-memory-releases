# agents-memory binary preview

A local memory authority and MCP transport for macOS Apple Silicon. The application is compiled; Python source and bytecode are not shipped. The Python runtime and native libraries are included, so a separate Python installation is not required for the core. Optional semantic encoding uses a separately managed runtime/model.

This is a prerelease, not a stable release. It was tested on macOS 26.6.2 arm64. All bundled Mach-O files declare macOS 11.0 as their minimum, but other macOS versions and a separate physical Mac were not tested. Intel, Windows and Linux/cloud binaries are not provided.

The bundle is ad hoc signed. It has no Developer ID signature or notarization and no verified publisher identity. macOS may block a downloaded executable. The installer does not disable Gatekeeper, remove quarantine or change security settings.

Read INSTALL.md before running setup. PostgreSQL 18.x with pgvector >= 0.8.7 is an independently managed prerequisite; no database or cloud resource is provisioned. Service, host integration, credentials and model access are separate explicit setup steps.

The core remains under its existing MIT notice in LICENSE; dependencies retain their own notices in licenses/ and THIRD_PARTY_NOTICES.md. No new proprietary or commercial license is imposed. Native code can be reverse engineered. The OMP adapter, schemas, prompts and protocol behavior remain observable. Earlier public source copies cannot be recalled.

The current preview passed a source-denied compiled smoke (fresh setup/migration, delayed DB readiness, MCP stdio, generated background capture and deterministic recall/correction/retraction), two actual compiled upgrade cases and 78 committed Mac regressions. Real E5/model quality, actual Codex model consumption, live interactive host acceptance and another physical Mac remain unverified. Four pre-existing source CI skips remain; this is not an all-gates or stable-release claim. See RELEASE_NOTES.md for exact source and binary hashes. Evaluation engineering commands require a source checkout and are unsupported by this binary.

The distribution repository contains only public wrappers, installation documents, manifests and notices. Automatic Source code archives contain that metadata, not the private Python implementation. Use the binary asset from the release.

## Download and Claude Code installation

Use the [prerelease binary assets](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v0.1.0-preview.20261027) and follow [INSTALL.md](INSTALL.md). The installer only places files; authority setup and all model/service operations require explicit choices.

In Claude Code 2.1.310 or later:

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory@agents-memory
/agents-memory:setup
```

This is the maintainer’s own marketplace; it has not been submitted to Anthropic’s directory. Configure with `/plugin configure agents-memory@agents-memory` only after preparing your own authority.
