# Agents Memory MCP

Claude Code·Codex·OMP에서 함께 사용하는 기억 MCP입니다.

**MCP 2.0.5 정식판을 배포했습니다.** [게시 상태·검증 범위](release-candidates/v2.0.5-provider-choice/README.ko.md) · [최신 정식 릴리즈](https://github.com/chonamdoo/agents-memory-releases/releases/latest)

배포 검증 대상은 Ubuntu 24.04의 Linux x86_64입니다. macOS는 사용자 직접 테스트
대상이며 Linux 정식 배포의 필수 검증 조건에서 제외합니다.

## 설치

### Claude Code

```sh
claude plugin marketplace add chonamdoo/agents-memory-releases
claude plugin install agents-memory-unified@agents-memory
```

### Codex

```sh
codex plugin marketplace add chonamdoo/agents-memory-releases
codex plugin add agents-memory-unified@agents-memory
```

설치된 setup skill을 실행해 실제 프로젝트의 MCP를 등록합니다. 마켓 항목 설치만으로 MCP가 연결되지는 않습니다.

### OMP

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-unified@agents-memory
```

## 처음 연결할 때

앱을 다시 시작하고 setup 안내를 따릅니다. [런타임 설치 안내](distribution/server/README.ko.md#로컬-설치-claudecodexomp)에 따라 엔진·모델·키를 준비합니다. Claude·OMP는 플러그인 MCP, Codex는 프로젝트 stdio MCP를 사용합니다. 같은 앱에 두 연결을 중복 등록하지 마세요.

로컬 설치는 로컬 LLM(Ollama·LM Studio 또는 로그인된 Claude·Codex CLI)과 Jev 중 선택합니다. 서버 설치는 Jev를 사용합니다. 구독 CLI 추론은 업체 서버에서 이뤄집니다. Jev를 선택한 경우만 키를 숨김 입력 또는 비공개 파일로 설정합니다. 설치 후 `setup_status`에서 준비 상태를 확인합니다.

## 업데이트

- Claude: `plugin marketplace update` 후 `plugin update`
- Codex: `plugin marketplace upgrade agents-memory` 후 같은 항목을 다시 설치
- OMP: `plugin marketplace update` 후 `plugin upgrade`

2.0.4 사용자는 마켓을 새로고침하고 2.0.5로 업데이트한 뒤, 새 번들 설치기로 런타임도 업데이트하세요. 기존 DB·키·선택 공급자를 보존합니다.

OMP에서 중복 연결·자동 수집 미설정·동기화 오류가 이어지면 [DB 보존 복구 절차](tools/OMP-REPAIR.ko.md)를 사용하세요.

런타임 설치기도 기존 경로와 같은 인자로 다시 실행한 뒤 앱을 재시작합니다. 키·DB·설정은 플러그인 캐시 밖에 보존합니다.

[상세 연결·원격 서버 안내](distribution/server/README.ko.md) · [MCP 패키지](plugins/agents-memory-unified) · [검증 기록과 정식 전환 조건](release-candidates/v2.0.0-stable/CONDITIONS.ko.md)
