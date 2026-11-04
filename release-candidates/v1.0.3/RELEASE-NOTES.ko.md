# 로컬 MCP 설치 배포판 1.0.3

Claude Code · Codex · OMP(오마이파이)를 같은 로컬 기억 서버에 연결하는 설치 배포판입니다. 검증된 1.0.2 컴파일 코어와 E5 임베딩을 재사용합니다.

## Claude Code

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory-local@agents-memory
/agents-memory-local:setup
```

## Codex · OMP 공통 도우미

프로젝트 터미널에서 실행하세요. OMP는 `--client omp`, 직접 Claude 연결은 `--client claude`로 바꿉니다.

```sh
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.3/distribution/mcp-local/install.sh \
  -o /tmp/agents-memory-mcp-install.sh
bash /tmp/agents-memory-mcp-install.sh --client codex --project "$PWD"
```

OMP 마켓에서도 `omp plugin marketplace add chonamdoo/agents-memory-releases`와 `omp plugin install agents-memory-local@agents-memory`로 같은 플러그인을 설치할 수 있습니다. 초기 DB·provider 준비는 공통 도우미의 `--client omp`를 사용합니다.

설치 대상 앱과 판단 LLM은 별개입니다. 판단은 Jev / 구독 Claude / 구독 Codex 중 선택하고, 새 설치에서는 Sonnet 5.5 / GPT-6.1 Terra를 추천합니다. OMP를 판단 모델 제공자로 추가하지 않습니다. 기존 provider·모델·키·DB·큐를 보존하며 키는 터미널 숨김 입력으로 받습니다.

Apple Silicon macOS 13+와 실행 중인 Docker Desktop, 또는 전용 기존 로컬 PostgreSQL 18 + pgvector가 필요합니다. 도우미가 전용 DB 볼륨·로컬 API LaunchAgent·프로젝트 MCP 등록을 준비합니다. Docker Desktop 자체나 구독 CLI를 임의 설치·로그인하지 않습니다. 호스트의 프로젝트 신뢰와 MCP 실행 승인은 유지합니다. 같은 이름의 다른 서버나 비활성화 상태를 덮어쓰지 않습니다. 기본 경로에서는 OMP의 마켓/직접 등록 중복을 제거합니다.

[전체 설치·업데이트·중지 안내](https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.3/distribution/mcp-local/README.ko.md) · [검증 결과](https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.3/release-candidates/v1.0.3/VERIFICATION.json)

검증: 로컬 배포 검사 **83개 + 하위 검사 62개 통과**, Claude 마켓 설치·연결, Codex 앱 서버와 OMP CLI의 실제 도구 9개 로드, OMP 마켓/직접 등록 중복 제거, 실제 Codex 판단을 거친 MCP 저장·E5 검색·문서 검증·삭제를 확인했습니다. bootstrap의 실제 압축·런타임 추출은 로컬 다운로드 대역으로 검사하고 고정 해시·변조 거부를 확인했습니다. 1.0.2의 전체 CI 5,059개 통과 기록은 기반 코어의 이전 검증이며 이번 변경에서 다시 실행한 점수가 아닙니다.

자체 마켓 배포이며 공식 Anthropic/기타 디렉터리 심사 등재는 아닙니다. Linux에서 검증했으며 macOS 실기 실행은 수행하지 않았습니다. Mac 바이너리는 기존 ad hoc 서명 상태이고 Developer ID/공증을 주장하지 않습니다. 실제 사용자 이력·Jev API는 사용하지 않았습니다. 자동 이력 스캔·프롬프트 수집·문맥 주입·도구 삭제는 활성화하지 않습니다. GitHub Actions는 2026-12-01까지 실행하지 않습니다.

공개 GitHub 주소에서도 Claude·OMP 마켓 설치에 성공했고, 설치 도우미·helper·MCP 정의를 로그인 없이 내려받아 검증한 해시와 일치함을 확인했습니다. [공개 설치 검증](https://github.com/chonamdoo/agents-memory-releases/blob/main/release-candidates/v1.0.3/PUBLIC-INSTALL-VERIFICATION.json).
