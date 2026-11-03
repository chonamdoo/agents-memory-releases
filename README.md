# agents-memory releases

[가상 출시 점수표](release-candidates/v1.0.0/RELEASE-READINESS.ko.md) ·
[실환경 추후 검증](release-candidates/v1.0.0/SCORECARD.ko.md) ·
[두 단계 출시 정책](release-candidates/v1.0.0/README.ko.md)

The user-selected policy is stable publication after virtual readiness reaches 100/100;
real-environment verification continues after release. Virtual tests use explicit model-output
doubles and do not establish actual account/CLI/macOS/model quality or SOTA performance.
The virtual release score is **100/100**, including the inspected final compiled artifact,
fresh isolated installation, provider/configuration preservation and application rollback.
Actual progress is personal 50 / company 15 / joint 15; actual macOS/account/model-quality
verification continues after publication. This score does not establish SOTA performance.

## Hindsight local v1.0.0

**Publication pending:** the final artifact and virtual100 validation are complete, but the
current build environment blocks `uploads.github.com` (proxy CONNECT 403). The failed upload
did not publish v1.0.0. Its network allowlist update must take effect before asset upload resumes.
Existing previews remain available. No empty stable release is substituted for the tested artifact.

[Stable release target (available after publication)](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v1.0.0) ·
[설치 안내](distribution/hindsight-local/README.ko.md) ·
[릴리즈 노트](release-candidates/v1.0.0/RELEASE-NOTES.ko.md) ·
[최종 배포물 검증](release-candidates/v1.0.0/ARTIFACT-VERIFICATION.json).

The production target is Apple Silicon macOS 13 or later, local only. The installer asks
**Jev / local LLM (your subscribed Codex CLI)** and preserves that choice on upgrades.
It bundles Python and the pinned E5 assets, installs hash-locked Hindsight dependencies,
and keeps private memory implementation as compiled extensions. A separately provisioned
local PostgreSQL/pgvector database and your selected provider login remain prerequisites.
The bundled Linux path is for explicit virtual validation, not cloud/Linux production support.
macOS execution and real account QA are not claimed; binaries have ad hoc signatures and
no Developer ID/notarization. Public wrappers and licensed upstream Hindsight sources are
included; raw private Python, bytecode and generated C are excluded.

Existing Native previews, marketplace plugins and their pinned automatic installers below
remain separate. This release does not automatically migrate their data or replace their commands.

# Existing previews

The new [Hindsight reference preview](profiles/hindsight-reference/README.ko.md) provides tested official
configuration, a guarded stdlib helper, manual project MCP examples and bounded validation results. It is a **configuration/helper preview**;
Python/Hindsight/PostgreSQL/model artifacts are separate prerequisites. It is not a replacement macOS binary.

[Download the Hindsight reference prerelease](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v0.1.0-hindsight-reference-preview.20261101).
The current [helper instructions](profiles/hindsight-reference/LOCAL.md) and [experimental policy results](profiles/hindsight-reference/POLICY-EXPERIMENT.ko.md)
are reviewable in this repository; the linked immutable prerelease remains the 20261101 bundle.
Pinned E5 assets passed a Darwin/arm64 CPU CI smoke; full Hindsight/PostgreSQL and recipient-machine/macOS installation remain unproven.
SOTA accuracy is unproven. Existing Native installers and
marketplace entries below keep their 20261027 pinned target and do not switch to Hindsight automatically.

---

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

Company one-command installation entrypoint and separate home-Jev guidance: [INSTALL.md](INSTALL.md#one-command-to-start-a-company-installation-macos-arm64). The bootstrap installs the binary and asks for the supported local location/official subscription host; authority/DB/authentication prerequisites remain explicit.
