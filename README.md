# Agents Memory MCP

Claude Code·Codex·OMP에서 함께 사용하는 기억 MCP입니다.

**MCP 2.0.4의 출시 검증을 완료했습니다.** [게시 상태·검증 범위](release-candidates/v2.0.4-relevance/README.ko.md) · [최신 정식 릴리즈](https://github.com/chonamdoo/agents-memory-releases/releases/latest)

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

Jev 키는 설치기의 숨김 입력 또는 비공개 파일로 설정합니다. 설치 후 `setup_status`에서 준비 상태를 확인합니다.

## 업데이트

- Claude: `plugin marketplace update` 후 `plugin update`
- Codex: `plugin marketplace upgrade agents-memory` 후 같은 항목을 다시 설치
- OMP: `plugin marketplace update` 후 `plugin upgrade`

이미 같은 2.0.4 시험 패키지를 설치했다면 [동일 버전 갱신 안내](plugins/agents-memory-unified/README.md)를 확인하세요.

런타임 설치기도 기존 경로와 같은 인자로 다시 실행한 뒤 앱을 재시작합니다. 키·DB·설정은 플러그인 캐시 밖에 보존합니다.

[상세 연결·원격 서버 안내](distribution/server/README.ko.md) · [MCP 패키지](plugins/agents-memory-unified) · [검증 기록과 정식 전환 조건](release-candidates/v2.0.0-stable/CONDITIONS.ko.md)
