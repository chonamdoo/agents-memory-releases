# Claude · Codex · OMP 자동 로컬 MCP 설치 (1.0.5)

이 버전부터 플러그인의 MCP를 연결하면 실행 환경, E5 검색 임베딩, 앱 전용 PostgreSQL/pgvector와 API를 자동으로 준비합니다. Docker Desktop·Colima·별도 Python 설치는 필요하지 않습니다.

처음 한 번만 브라우저에서 **Jev / 구독 Claude / 구독 Codex**를 선택합니다. Jev는 같은 화면에서 키를 입력합니다. 구독 모델은 설치·로그인된 해당 CLI를 사용합니다. 추천 모델은 Claude Sonnet 5.5(`claude-sonnet-5-5`), Codex 6.1 Terra(`gpt-6.1-terra`)입니다. OMP는 MCP 연결 앱이며 판단 모델 제공자가 아닙니다.

설정·키는 업데이트 후에도 유지됩니다. 이후 프로젝트에서 MCP를 연결하면 저장된 설정을 사용해 준비·시작합니다. 설치 중에도 `setup_status`가 응답하고, 도구 목록을 처음부터 제공해 목록을 캐시하는 앱도 지원하며, 준비 전 호출은 상태를 안내하고 준비 후에는 같은 연결에서 동작합니다. 최초 다운로드에는 네트워크 연결과 수 분이 필요할 수 있습니다. 설치·연결 자체에서는 판단 LLM을 호출하지 않습니다.

## 지원 환경

- **Apple Silicon macOS 15 이상**: 새 자동 DB 런타임의 최소 버전입니다. 이전 1.0.2 코어의 macOS 13 조건과 구별합니다.
- 구독 모델을 고르면 해당 Claude/Codex CLI 설치와 로그인
- Linux x86_64는 검증용입니다. macOS 실기 검증 여부는 릴리즈의 검증 기록을 확인하세요.

검색용 **다국어 E5 임베딩은 포함**됩니다. 생성 LLM 가중치를 설치하지 않습니다.

## OMP

실제 작업 프로젝트에서 실행하세요.

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
```

OMP에서 MCP를 연결하면 최초 설정 페이지가 열립니다. 이미 실행 중인 OMP는 `/mcp reload`로 새 플러그인을 불러옵니다. 브라우저가 열리지 않으면 `agents-memory-local`의 `setup_status`에 나오는 이 PC의 설정 주소를 여세요. 키는 채팅에 보내지 않습니다. 홈 폴더 전체를 기억 프로젝트로 등록하지 않습니다.

## Claude Code

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory-local@agents-memory
```

MCP 실행·프로젝트 신뢰를 앱에서 승인하면 자동 준비가 시작됩니다. 신뢰 설정을 설치기가 강제로 승인하지 않습니다. `/agents-memory-local:setup`은 현재 상태를 확인하는 안내용이며 추가 설치 명령은 보통 필요하지 않습니다.

이 마켓은 운영자의 자체 마켓이며 공식 디렉터리 등재를 뜻하지 않습니다. 예전 `agents-memory` Native 프리뷰와 현재 `agents-memory-local`은 별개입니다.

## Codex 또는 직접 MCP 등록

실제 프로젝트의 터미널에서 한 번 실행합니다.

```sh
curl -fsSL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.5/distribution/mcp-local/install.sh -o /tmp/agents-memory-mcp-install.sh
bash /tmp/agents-memory-mcp-install.sh --client codex --project "$PWD"
```

직접 Claude 연결은 `--client claude`, OMP 직접 연결은 `--client omp`를 사용합니다. 플러그인과 직접 등록을 중복 추가할 필요는 없습니다. 여러 앱은 `--client`를 반복해 연결합니다. 직접 설치의 최초 선택·Jev 키는 터미널에서 입력하며 Enter 뒤 설치 단계가 표시됩니다. 이후 MCP 연결은 같은 자동 연결기를 사용합니다.

프로젝트 `.mcp.json`, `.codex/config.toml`, `.omp/mcp.json`에서 다른 서버·모델 설정을 보존하고 변경 전 백업을 남깁니다. 같은 이름의 다른 명령이나 명시적 비활성화는 덮어쓰지 않습니다. 앱별 프로젝트 신뢰와 MCP 활성화 설정을 존중합니다.

## 저장·중지·업데이트

상태·키·DB 데이터·프로젝트 경로는 `~/.local/share/agents-memory-hindsight`에 사용자 전용으로 저장합니다. 플러그인 캐시와 분리되어 있으며 업데이트나 플러그인 제거가 기억 데이터를 지우지 않습니다. Jev 키는 0600 파일이며 Keychain 암호화 저장은 아닙니다.

```sh
AM="$HOME/.local/share/agents-memory-hindsight/bin/am-mcp"
"$AM" status
"$AM" stop
"$AM" start
```

`stop`은 API와 앱 전용 네이티브 DB를 중지하고 자동 재시작 금지 상태를 남깁니다. 이후 MCP 연결은 이 선택을 존중합니다. `start`로 다시 활성화할 수 있습니다. LaunchAgent는 macOS 로그인 후 API를 관리합니다. 새 프로젝트 초기 준비나 연결기 업데이트 때 API를 재시작할 수 있으며 자동 연결기가 도구 연결을 복구합니다. DB는 127.0.0.1에만 바인딩하며 다른 프로젝트의 DB·Docker 컨텍스트·Colima 프로필을 변경하지 않습니다.

기존 1.0.3/1.0.4의 Docker 또는 외부 DB 영수증이 남아 있으면 데이터를 보존하고 기존 연결을 유지합니다. 자동으로 새 빈 DB로 바꾸거나 Docker 설정을 수정하지 않습니다. 완전히 지운 뒤 새로 설치하는 경우부터 네이티브 DB가 기본입니다.

MCP 연결 준비 상태는 `setup_status`로 확인합니다. 자동 설정 진행·오류는 macOS `~/Library/Caches/agents-memory-setup/setup.log`, 서비스 오류는 런타임의 `integration/logs/service.log`, 명령 오류는 `integration/logs/operations.log`에 비공개로 남습니다. 오류 로그를 공유할 때 키나 개인 경로를 공개하지 마세요. 네트워크 오류 뒤에는 MCP를 다시 연결하면 완료된 실행 환경과 설정을 재사용합니다.

플러그인 업데이트는 앱의 마켓 업데이트 명령을 사용하고 새 MCP 연결을 불러오면 됩니다. provider·모델 변경은 `am-hindsight configure`로 명시합니다. 과거 이력 스캔·자동 프롬프트 수집·문맥 주입은 이 플러그인이 켜지 않습니다. 실제 기억 저장 때는 선택한 모델의 사용량이 발생할 수 있습니다.

자동 연결기와 DB 배포물은 체크섬을 고정합니다. 메모리 코어는 검증된 컴파일 코어 1.0.2를 재사용합니다. macOS 바이너리는 ad hoc 서명이며 Developer ID 서명·공증은 아닙니다.
