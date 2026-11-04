# Claude · Codex · OMP MCP 설치 가이드

## 버전과 선택

| 선택 | 설치되는 구성 | 판단용 LLM |
| --- | --- | --- |
| 개인 로컬 | 기존 안정 로컬 MCP 1.0.7, PC의 DB·E5 | 기존 로컬 Claude/Codex CLI 연결 또는 Jev |
| 본인 서버 연결 | 개인 서버 MCP 클라이언트 0.2.1, 로컬 전송함·캐시 | 앱에서 선택한 기억을 직접 저장. 서버가 별도 Jev를 호출하지 않음 |

본인 서버의 PostgreSQL/pgvector·E5는 서버에 설치합니다. PC에 서버 DB나 생성 LLM 가중치를 설치하지 않습니다. 기존 로컬 판단 결과를 내보내려면 서버 README의 Hindsight 연결을 별도로 설정합니다. 모드 선택만으로 기억을 자동 이전하지 않습니다.

공통 설치기는 세 앱의 표준 MCP 설정 파일에 등록합니다. 기존 `agents-memory-local` 마켓플레이스 플러그인은 로컬 전용입니다. 이 배포가 Claude 공식 디렉터리 등재나 새 클라우드 마켓플레이스 플러그인 등록을 뜻하지 않습니다.

## 배포 파일 받기

[정식 릴리즈](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v0.2.1)의 `agents-memory-personal-0.2.1.zip`과 `SHA256SUMS`를 같은 다운로드 폴더에 받습니다. macOS에서 다음을 실행합니다.

```sh
cd "$HOME/Downloads"
grep '  agents-memory-personal-0.2.1.zip$' SHA256SUMS | shasum -a 256 -c -
unzip agents-memory-personal-0.2.1.zip
```

아래 예시는 압축을 푼 `agents-memory-personal-0.2.1` 폴더가 Downloads 안에 있을 때입니다. `--project`에는 실제 작업 프로젝트를 사용하세요. 홈 폴더나 배포 소스 폴더를 작업 프로젝트로 등록하지 마세요.

## Claude Code

실제 작업 프로젝트로 이동한 뒤 둘 중 하나를 실행합니다.

```sh
# 개인 로컬: 이어지는 과정에서 로컬 LLM 또는 Jev 선택
bash "$HOME/Downloads/agents-memory-personal-0.2.1/distribution/install.sh" \
  --mode local --client claude --project "$PWD"

# 본인 서버 연결: YOUR_HOST를 실제 주소로 변경, 기기 키는 숨김 입력
bash "$HOME/Downloads/agents-memory-personal-0.2.1/distribution/install.sh" \
  --mode personal-server --client claude --project "$PWD" \
  --profile personal --project-name my-project --url https://YOUR_HOST
```

프로젝트 `.mcp.json`에 개인 로컬은 `agents-memory-local`, 서버 연결은 `agents-memory-cloud`가 등록됩니다. `claude`를 평소처럼 실행해 해당 프로젝트의 신뢰와 MCP 서버 승인을 확인합니다. `claude mcp list`와 `/mcp`에서 상태를 확인하고 모델에게 해당 서버의 `setup_status` 호출을 요청하세요. Pending approval은 최초 승인 전 상태이며 서버 설치 성공과 구분해야 합니다. 기존 조직 정책은 우회하지 않습니다.

기존 로컬 마켓플레이스 경로를 쓰는 경우는 다음과 같습니다. 공통 설치기와 같은 서버를 중복 등록하지 말고 사용 중인 경로를 유지하세요.

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory-local@agents-memory
```

마켓플레이스 설치만으로 Jev 키 입력이나 모든 프로젝트 설정이 끝났다고 가정하지 말고 `setup_status`의 안내를 따르세요.

## Codex

```sh
# 개인 로컬
bash "$HOME/Downloads/agents-memory-personal-0.2.1/distribution/install.sh" \
  --mode local --client codex --project "$PWD"

# 본인 서버 연결
bash "$HOME/Downloads/agents-memory-personal-0.2.1/distribution/install.sh" \
  --mode personal-server --client codex --project "$PWD" \
  --profile personal --project-name my-project --url https://YOUR_HOST
```

프로젝트 `.codex/config.toml`의 `mcp_servers`에 등록됩니다. 신뢰한 작업 프로젝트에서 Codex를 시작하고 `codex mcp get agents-memory-cloud`, `/mcp`, 실제 `setup_status` 호출로 확인합니다. 개인 로컬 서버 이름은 `agents-memory-local`입니다.

개인 서버의 승인 정책을 명시하려면 아래를 기존 서버 테이블에 **병합**합니다. 같은 테이블을 중복 생성하지 마세요. 전역 approval/sandbox 설정은 이 설치기가 변경하지 않습니다.

```toml
[mcp_servers.agents-memory-cloud]
# 기존 command, args와 timeout은 그대로 유지
# 아래 항목만 필요한 경우 추가
# default_tools_approval_mode = "prompt"
# disabled_tools = ["sync_resolve", "sync_recover"]

[mcp_servers.agents-memory-cloud.tools.setup_status]
approval_mode = "approve"

[mcp_servers.agents-memory-cloud.tools.recall]
approval_mode = "approve"
```

원하는 일상 도구에만 같은 방식으로 설정할 수 있습니다. 이 서버의 일상 도구는 `setup_status`, `recall`, `session_start_context`, `team_search`, `team_brief`, `sync_retain`, `sync_now`입니다. 복구/충돌 해결을 MCP에서 사용하지 않으면 `disabled_tools`로 제외하고 필요 시 명시적으로 CLI에서 처리할 수 있습니다. 전역 `never`·전체 접근 설정에서는 도구별 prompt만으로 승인을 강제할 수 있다고 가정하지 마세요. 목록에서의 제외 역시 전체 접근 에이전트에 대한 보안 경계는 아닙니다.

## OMP

```sh
# 개인 로컬
bash "$HOME/Downloads/agents-memory-personal-0.2.1/distribution/install.sh" \
  --mode local --client omp --project "$PWD"

# 본인 서버 연결
bash "$HOME/Downloads/agents-memory-personal-0.2.1/distribution/install.sh" \
  --mode personal-server --client omp --project "$PWD" \
  --profile personal --project-name my-project --url https://YOUR_HOST
```

프로젝트 `.omp/mcp.json`에 등록됩니다. 해당 프로젝트에서 OMP를 열고 `/mcp reload` 또는 새 세션으로 연결한 뒤 `setup_status`를 호출하세요. 로컬 마켓플레이스 플러그인을 쓰는 기존 경로는 다음과 같습니다.

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
```

이는 로컬 전용 플러그인입니다. 서버 연결은 위 공통 설치기를 사용하세요. `MCP subprocess closed`가 발생하면 키를 대화에 붙이지 말고 설치 로그와 `setup_status`를 확인합니다.

## 세 앱을 함께 쓰기

개인 서버 연결에서는 `--client all`을 사용할 수 있습니다. 개인 로컬에서는 `--client claude --client codex --client omp`로 반복 지정합니다. 같은 서버 계정·프로필·프로젝트 이름을 사용하세요. 여러 앱이 한 SQLite를 공유하면 잠시 `replica_worker_busy`가 보일 수 있습니다. 기존 동기화가 끝난 뒤 회복되는지 확인하고, 이 상태만으로 복구나 데이터 삭제를 실행하지 마세요.

## 연결 확인과 개인 IAP 구성

개인 서버 클라이언트의 `setup_status`에서 클라이언트 `version=0.2.1`, `ready`, `server_ready`, `sync.state`, `replica.pending`을 함께 확인합니다. queued는 로컬 영속 저장을 의미하며 서버 저장·다른 PC 반영과 다릅니다. `sync_now` 후 새 연결에서 선택한 합성 기억을 조회하는 방법으로 실제 흐름을 확인하세요.

Cloud 서버 0.2.0과 Mac 클라이언트 0.2.1을 함께 사용한 사용자 실기 보고가 있습니다. 이 경우 서버 healthz의 0.2.0과 로컬 MCP 상태의 0.2.1은 서로 다른 구성 요소 버전입니다.

도메인이 없는 개인 IAP 시험에서는 SSH 자체를 IAP로 연결하고 `-L 127.0.0.1:18350:127.0.0.1:18350`로 전달한 다음 설치 URL을 `http://127.0.0.1:18350`으로 지정합니다. 다른 프로그램이 포트를 쓰면 종료하지 말고 충돌을 해결하세요. IAP에서 18350으로 직접 연결하는 방식은 루프백 바인딩 서버에 맞지 않습니다. 로그인·SSH 키·자동 터널은 서버 소유자가 구성하며 이 설치기가 클라우드 권한을 만들지 않습니다.

## 업데이트와 지원 범위

새 배포 파일을 받고 같은 모드·프로필·프로젝트로 설치기를 재실행합니다. 기존 키와 SQLite를 지우거나 계정을 새로 만들지 않습니다. 실제 URL/계정을 바꿀 때는 새 프로필을 사용합니다. 기기 키 교체·백업 복원은 서버 README의 별도 절차를 따릅니다.

개인 로컬의 지원 범위는 Apple Silicon macOS 15+입니다. 개인 서버는 Linux x64, 클라이언트는 사용자 제공 Mac 실기 보고를 기준으로 배포합니다. Native Windows 및 다른 미검증 플랫폼을 정식 지원으로 표시하지 않습니다. 대화형 최초 신뢰, Mac 로그인·잠자기·네트워크 변경, 외부 HTTPS와 부하/HA의 검증 한계는 릴리즈 기록을 확인하세요.
