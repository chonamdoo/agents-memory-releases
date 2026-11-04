# agents-memory releases

## MCP 자동 설치: Claude · Codex · OMP (1.0.7)

[1.0.7 릴리즈](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v1.0.7) · [설치·운영 안내](distribution/mcp-local/README.ko.md)

1.0.7은 macOS pgvector 모듈 이름 오류를 수정하고, 1.0.5의 실패한 설치를 키·설정·DB 데이터 변경 없이 자동 복구합니다. 기존 사용자는 아래 앱별 업데이트 명령을 실행하고, 1.0.7 설치를 확인한 뒤 앱을 다시 시작하세요.

플러그인을 설치하고 MCP를 연결하면 로컬 실행 환경, **검색용 E5 임베딩**, 앱 전용 PostgreSQL/pgvector와 API가 자동으로 준비됩니다. **Docker·Colima 수동 설정은 필요하지 않습니다. Apple Silicon macOS 15 이상**이 필요합니다.

처음 한 번만 브라우저에서 Jev 또는 구독 중인 Claude·Codex를 선택합니다. Jev는 같은 화면에서 키를 입력하고 이후 업데이트에서도 설정을 유지합니다. 설치 진행은 `setup_status`로 확인하며 도구 목록은 처음부터 제공하며, 준비 전 호출은 진행 상태를 안내하고 준비가 끝나면 같은 연결에서 자동으로 동작합니다.

### OMP 설치

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
```

OMP 업데이트:

```sh
omp plugin marketplace update agents-memory
omp plugin upgrade agents-memory-local@agents-memory
```

마켓 정보를 먼저 갱신해야 이전 버전이 다시 설치되지 않습니다. 업데이트 후 OMP를 완전히 종료하고 다시 실행하세요.

### Claude Code 설치

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory-local@agents-memory
```

Claude Code 터미널에서는 `claude plugin marketplace add ...`, `claude plugin install ...`도 사용할 수 있습니다.

Claude 업데이트 후 앱을 다시 시작하세요.

```sh
claude plugin marketplace update agents-memory
claude plugin update agents-memory-local@agents-memory
```

### Codex 설치·업데이트

실제 프로젝트의 터미널에서 아래 두 줄을 실행합니다. 업데이트도 같은 명령이며 기존 키·모델·DB를 유지합니다.

```sh
curl -fsSL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.7/distribution/mcp-local/install.sh -o /tmp/agents-memory-mcp-install.sh
bash /tmp/agents-memory-mcp-install.sh --client codex --project "$PWD"
```

Codex를 다시 시작하고 프로젝트 신뢰·MCP 사용을 승인한 뒤 `setup_status`에서 `version: 1.0.7`, `ready: true`를 확인하세요. Codex는 프로젝트 경로를 정확히 전달하는 직접 MCP 등록을 사용합니다. 세 앱의 [전체 설치·운영 안내](distribution/mcp-local/README.ko.md)를 확인하세요. OMP는 MCP 연결 대상이며 기억 저장 판단은 Jev / 구독 Claude / 구독 Codex가 담당합니다. 설치·연결은 판단 모델을 호출하거나 과거 이력을 읽지 않습니다. 예전 Docker/외부 DB 설정이 남아 있으면 데이터를 보존하고 자동 변환하지 않습니다.

기존 Native 프리뷰 `agents-memory`와 최신 `agents-memory-local`은 별개입니다. 자체 마켓 배포이며 공식 디렉터리 등재를 뜻하지 않습니다. Linux E2E와 macOS 파일 구조 검증의 범위는 릴리즈 기록에 명시하며 macOS 실기 실행을 주장하지 않습니다.

## 로컬 코어 릴리즈 1.0.2

[로컬 설치 파일 받기](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v1.0.2) · [설치·업데이트 안내](distribution/hindsight-local/README.ko.md) · [선택형 기록·사용량 안내](distribution/hindsight-local/HISTORY.ko.md)

프로젝트·기간을 지정한 과거 대화 후보 검토, 명시적 모델 분석과 저장, 정정·삭제, 본문 없는 사용량 원장과 수동 조언을 추가했습니다. 설치는 과거 이력을 자동으로 읽지 않으며 기존 Jev/Claude/Codex 선택·키·모델을 유지합니다. 검색용 E5 임베딩은 포함됩니다. 자동 도구 삭제·stop 강제·host 설정 변경은 하지 않습니다. GitHub Actions는 2026-12-01까지 실행하지 않습니다.

아래 1.0.0 점수표와 설명은 해당 버전의 역사적 기록이며 1.0.2 검증 결과가 아닙니다.

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

**Stable v1.0.0 is published.** Download the release assets with the installation command below. The command verifies all 19 parts and the reconstructed archive before installation.

[Download the stable local release](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v1.0.0) ·
[설치 안내](distribution/hindsight-local/README.ko.md) ·
[릴리즈 노트](release-candidates/v1.0.0/RELEASE-NOTES.ko.md) ·
[최종 배포물 검증](release-candidates/v1.0.0/ARTIFACT-VERIFICATION.json).

### 설치 명령어

Apple Silicon Mac(macOS 13 이상)의 터미널에 아래 블록을 붙여 넣으세요. 배포 파일과
체크섬을 다운로드하고 검증한 뒤 설치합니다. 처음에 **Jev / 로컬 LLM(구독 중인 Codex)**
중 하나를 선택합니다. Jev는 API 키를 숨김 입력으로 받고 사용자 전용 파일에 보관합니다.
업데이트할 때 같은 명령을 실행하면 기존 provider·모델·키 설정을 유지합니다.

```sh
(
  set -eu
  am_install_dir=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-install.XXXXXXXX")
  cd "$am_install_dir"
  am_release=https://github.com/chonamdoo/agents-memory-releases/releases/download/v1.0.0
  curl --fail --location --output SHA256SUMS "$am_release/SHA256SUMS"
  curl --fail --location --output PARTS-SHA256SUMS "$am_release/PARTS-SHA256SUMS"
  am_part=0
  while [ "$am_part" -lt 19 ]; do
    am_name=agents-memory-hindsight-local-1.0.0.tar.gz.part-$(printf '%03d' "$am_part")
    curl --fail --location --output "$am_name" "$am_release/$am_name"
    am_part=$((am_part + 1))
  done
  shasum -a 256 -c PARTS-SHA256SUMS
  cat agents-memory-hindsight-local-1.0.0.tar.gz.part-* > agents-memory-hindsight-local-1.0.0.tar.gz
  shasum -a 256 -c SHA256SUMS
  tar -xzf agents-memory-hindsight-local-1.0.0.tar.gz
  cd agents-memory-hindsight-local-1.0.0
  ./install.sh
)
```

설치 확인:

```sh
"$HOME/.local/share/agents-memory-hindsight/current/bin/am-hindsight" --version
"$HOME/.local/share/agents-memory-hindsight/current/bin/am-hindsight" profile
```

설치는 파일을 배치합니다. 로컬 PostgreSQL/pgvector, 선택한 provider의 인증,
프로젝트 연결과 별도 drainer 시작은 [전체 설치 안내](distribution/hindsight-local/README.ko.md)를 따르세요.

The production target is Apple Silicon macOS 13 or later, local only. The installer asks
**Jev / local LLM (your subscribed Codex CLI)** and preserves that choice on upgrades.
It uses the official **`hindsight-api-slim`** distribution. Jev or subscribed Codex performs
memory admission; no local generation LLM, PyTorch, Ollama or GGUF generation weights are installed.
The pinned local **E5 embedding model remains for semantic search**: the current Jev/Codex
integration supplies admission decisions, not an embedding API.
It bundles Python and those E5 assets, installs hash-locked Hindsight dependencies,
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

## Optional personal sync and team server preview

[Collaboration 0.2 developer preview](distribution/server/README.ko.md) adds an optional PostgreSQL/pgvector server, personal multi-PC sync, project-scoped team sharing, and durable MCP clients for Claude, Codex and OMP. The local product remains the default. This preview has a [separate behavior contract](distribution/server/CONTRACT.md) and [local verification record](distribution/server/VERIFICATION.json); it does not replace the stable local release or claim native Windows/macOS host validation.
