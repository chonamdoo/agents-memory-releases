# 선택형 개인 Cloud Sync · 팀 기억 · 자체 호스팅 MCP

**0.2.1 개발 프리뷰입니다. 기존 로컬 1.0.7과 별도로 설치하며 안정 릴리즈를 대체하지 않습니다.** claude-mem 코드를 복사하지 않고 동기화·공유 기능을 독립적으로 구현했습니다. 서버 코드와 전송 클라이언트는 이 저장소의 MIT 라이선스를 따릅니다. E5 모델은 해당 모델의 라이선스·출처를 함께 확인하세요.

| 기능 | 동작 |
| --- | --- |
| 개인 Cloud Sync | 한 계정의 여러 PC가 개인 기억·요약을 동기화합니다. 팀 가입은 필요 없습니다. PC별 키, 대상 계정 확인, SQLite 전송함, 재시도·중복 방지·이력 해시·충돌 격리·삭제 전파를 포함합니다. |
| 팀 기억 | 팀 생성, 프로젝트 생성, 만료되는 일회용 초대, 프로젝트 접근권한, 공유 프로젝트 선택·중단, 탈퇴·접근 회수, 작성자 표시, 팀 검색·요약을 제공합니다. |
| 자체 호스팅 | PostgreSQL/pgvector와 E5 검색 임베딩을 포함하는 Docker 서버입니다. 개인은 자신의 서버 하나를 여러 PC에서 이용하고, 팀은 팀 서버 하나에 구성원이 접속할 수 있습니다. |

생성 LLM 가중치를 설치하지 않습니다. 이 서버는 Jev 키나 Claude/Codex 로그인 정보를 받지 않습니다. 기존 로컬 판단을 거쳐 저장한 기억이나 사용자가 직접 선택한 기억을 전송합니다. 설정하지 않은 기존 로컬 설치는 업로드하지 않습니다.

## 서버 실행

관리자의 Linux x64 Docker 서버에서 이 디렉터리로 이동해 실행합니다. 구성원 PC에는 DB나 Docker가 필요하지 않습니다.

```sh
bash bootstrap.sh
```

최초 실행은 DB 비밀번호를 `.env`에 생성하고 E5 모델·Python 의존성의 체크섬을 검증해 준비합니다. DB·계정 파일은 Docker 볼륨에 유지합니다. 재실행과 이미지 업데이트가 기존 볼륨을 초기화하지 않습니다. `docker compose down -v`는 데이터를 삭제하므로 업데이트 명령으로 사용하지 마세요.

서버는 기본적으로 이 서버의 `127.0.0.1:18350`에서만 접근됩니다. 다른 PC에서 사용하려면 DNS를 준비하고 `.env`에 다음 두 값을 설정한 뒤 HTTPS 서비스를 시작합니다.

```dotenv
AM_COLLAB_HOST=memory.your-company.example
AM_COLLAB_PUBLIC_URL=https://memory.your-company.example
```

```sh
docker compose --profile https up -d --build
```

Caddy가 HTTPS를 담당합니다. 서버의 DB 포트는 외부에 공개하지 않습니다. 실제 외부 DNS·인증서 발급은 이 프리뷰의 로컬 검증 범위에 포함하지 않습니다.

## 개인 계정과 여러 PC

서버 관리자만 서버 터미널에서 최초 계정을 만듭니다. 개인 사용자 한 명이 여러 PC를 쓸 때 **PC마다 다른 계정을 만들지 않습니다.**

```sh
docker compose exec -T server python -m agents_memory_collab.cli account \
  --name "My account" --output /data/my-account.connection.json
docker compose cp server:/data/my-account.connection.json ./my-account.connection.json
chmod 600 ./my-account.connection.json
```

연결 파일은 비밀 파일입니다. 채팅·Git·공유 프로젝트에 넣지 마세요. 다른 사람은 별도 계정을 만들고, 같은 사람의 다른 PC는 아래 기기 발급 API로 별도 키를 받습니다. 최초 연결 파일은 키 관리 권한을 가진 관리자 키입니다. 보관하고, 각 PC는 setup이 발급한 별도 일반 기기 키를 사용합니다. 일반 쓰기 키는 다른 키를 발급·조회·회수할 수 없습니다. 업데이트는 이미 저장된 기기 키를 재사용합니다.

Python 클라이언트는 이 디렉터리에서 `uv sync --frozen` 후 `uv run agents-memory-cloud`로 실행하거나, 빌드한 wheel을 설치해 `agents-memory-cloud`로 실행합니다.

기억을 로컬 전송함에 저장하고 서버와 동기화합니다. 입력 파일은 사용자가 선택한 기억 텍스트입니다.

```sh
agents-memory-cloud sync --connection my-account.connection.json --state desktop.sqlite \
  remember --project app --file selected-memory.txt
agents-memory-cloud sync --connection my-account.connection.json --state desktop.sqlite once
agents-memory-cloud sync --connection my-account.connection.json --state desktop.sqlite watch
```

두 번째 PC에서는 같은 계정의 기기 키 연결 파일과 **다른 로컬 state 파일**을 사용합니다. `once` 또는 `watch`가 기존 기억을 내려받습니다. 서버가 중단되면 전송함을 보존하고 다시 연결합니다. 같은 기억을 두 PC에서 동시에 편집하면 `needs_review`와 기억 ID를 표시합니다. 해당 충돌만 보류하고 다른 기억의 업로드·다운로드는 계속합니다. `sync ... status`에서 확인할 수 있습니다.

```sh
agents-memory-cloud sync --connection laptop.connection.json --state laptop.sqlite \
  resolve --memory-id MEMORY_UUID --keep local
```

`--keep server`는 서버 버전을 선택합니다. 수정은 `remember --memory-id MEMORY_UUID`, 삭제 전파는 `forget --project app --memory-id MEMORY_UUID` 후 `once`를 사용합니다.

## 기존 Hindsight와 선택형 연결

명시적으로 선택한 로컬 API와 bank의 **저장된 memory unit 텍스트**만 읽습니다. 원본 문서·세션 프롬프트·Claude/Codex 이력 파일·Jev 설정은 읽지 않습니다.

```sh
agents-memory-cloud sync --connection my-account.connection.json --state desktop.sqlite \
  watch --hindsight-url http://127.0.0.1:YOUR_API_PORT --bank YOUR_PROJECT_BANK \
  --project app --enable-cloud-upload
```

위 동의를 주기 전에는 Hindsight를 조회하지 않습니다. 로컬 API 장애나 불완전한 목록에서 삭제를 추정하지 않습니다. 기존 Hindsight의 삭제를 서버에 자동 반영하는 기능은 아직 없으며, 동기화된 항목의 `forget`으로 명시적으로 삭제합니다. 서버에서 삭제한 기억은 로컬 내보내기가 자동 부활시키지 않습니다. 다른 PC는 클라우드 MCP로 조회하거나 개인 replica에서 읽으며, 기존 Hindsight DB에 자동 병합하지 않습니다.

프롬프트 원문 동기화는 기본 거부합니다. 필요한 사용자가 계정의 `PUT /v1/preferences`에서 `upload_prompts: true`를 설정하고 클라이언트에 `--kind prompt --include-prompts`를 함께 지정한 경우에만 허용합니다. 프롬프트는 팀 검색·팀 요약에서 제외합니다.

## 팀 구성

관리 기능은 동일한 인증 REST API와 `agents-memory-cloud request`로 제공합니다. 요청 JSON은 `--input FILE`, 초대·기기 키 응답은 `--secret-output FILE`로 저장합니다.

| 메서드와 경로 | 요청/용도 |
| --- | --- |
| `GET /v1/devices` | 관리자: 기기 ID·이름·권한·회수 상태 조회. 비밀 키는 반환하지 않음 |
| `POST /v1/devices` | `{ "name": "Laptop", "writable": true }` → 같은 계정의 기기 키 |
| `DELETE /v1/devices/KEY_UUID` | 관리자: 해당 키와 그 키에서 파생된 모든 키의 접근 회수 |
| `POST /v1/teams` | `{ "name": "Engineering" }` → 팀 생성 |
| `POST /v1/teams/TEAM_UUID/projects` | `{ "name": "Trading" }` → 프로젝트 생성 |
| `POST /v1/teams/TEAM_UUID/invites` | `{ "role": "member", "projects": ["PROJECT_UUID"], "expires_hours": 24 }` |
| `POST /v1/invites/accept` | `{ "invite": "INVITE_VALUE" }` → 본인 계정으로 초대 수락 |
| `PUT /v1/teams/TEAM_UUID/sharing` | `{ "mappings": [{ "source_project": "app", "project_id": "PROJECT_UUID" }] }` |
| `PUT /v1/teams/TEAM_UUID/sharing` | `{ "mappings": [] }` → 본인 공유 중단 |
| `POST /v1/teams/TEAM_UUID/leave` | `{}` → 탈퇴 |
| `DELETE /v1/teams/TEAM_UUID/members/USER_UUID` | 소유자가 구성원 접근 회수 |

소유자는 팀 프로젝트를 관리하고, member는 허용된 프로젝트의 기억을 공유하며, viewer는 조회만 합니다. 초대 수락만으로 개인 기억을 팀에 공개하지 않습니다. 공유 mapping을 직접 설정해야 합니다. 공유 중단·탈퇴·회수 뒤에는 이후 검색·요약에서 제외하지만 이미 누군가 읽거나 복사한 내용을 되돌리지는 않습니다.

## Claude · Codex · OMP 연결

권장 경로는 **로컬 전송함을 사용하는 stdio MCP**입니다. 서버는 관리자가 한 번 준비하고, 각 PC는 설치 중 서버 주소·기기 키와 연결할 앱을 선택합니다. 클라이언트에 PostgreSQL·Docker·E5·생성 모델을 설치하지 않습니다. 필요한 Python 런타임과 잠긴 의존성은 설치 스크립트가 준비합니다.

```sh
bash distribution/server/install-client.sh --client all --project "$PWD" \
  --project-name app --url https://YOUR_HOST
```

`--client claude`, `--client codex`, `--client omp` 중 하나만 지정해도 됩니다. `--client`를 생략하면 터미널에서 선택합니다. 키는 숨김 입력이고 Enter 이후 확인 진행을 표시합니다. 관리자가 준 연결 파일을 쓰려면 `--credential-file /private/path/connection.json`을 지정합니다. 관리자 키가 들어오면 일반 기기 키를 발급하고 **기기 키만** 저장합니다.

서로 다른 PC에서 같은 프로젝트를 동기화하려면 같은 `--project-name`을 사용합니다. 같은 폴더 이름인 별개 프로젝트는 다른 이름을 지정하세요. 설치는 `.mcp.json`, `.codex/config.toml`, `.omp/mcp.json`에 별도 `agents-memory-cloud` 항목을 추가합니다. 기존 로컬 MCP와 다른 서버 항목은 유지합니다. 동일 이름에 다른 설정이 있으면 덮어쓰지 않습니다.

설정·SQLite·키는 Linux의 `~/.local/share/agents-memory-cloud/personal`, macOS의 `~/Library/Application Support/agents-memory-cloud/personal`에 유지합니다. 업데이트할 때 같은 명령을 다시 실행합니다. 서버·계정을 바꾸려면 새 `--profile NAME`을 사용하고 새 MCP 등록을 명시적으로 선택해야 합니다. 기존 전송함을 새 대상으로 옮기지 않습니다.

Windows에서는 WSL2 안의 Linux 터미널·Linux 홈을 사용합니다. **네이티브 Windows의 비밀 파일 ACL과 Claude/Codex/OMP 실기 동작은 검증하지 않았습니다.** macOS 실기 검증도 별도입니다. 이번 검증은 Linux에서 실제 MCP stdio와 세 앱의 설정 형식까지입니다.

앱을 재시작하거나 MCP를 다시 연결한 뒤 `setup_status`를 호출합니다. `ready`는 로컬 MCP 사용 가능 여부, `server_ready`는 최근 서버 확인 결과입니다. `sync.state`와 `replica.pending`으로 전송 진행 상태를 별도로 확인하세요. `queued`는 기기에 저장됐다는 뜻이며 서버 저장·다른 PC 반영과 다릅니다. `sync_now`로 동기화할 수 있고, 연결된 동안 백그라운드에서 재시도합니다. `needs_review`는 `sync_resolve`에서 local/server를 명시적으로 선택합니다. 복원 오류는 아래 복구 절차를 사용합니다.

MCP 연결 시 실제 동기화를 시작하고 해당 프로젝트에서 최근 적용한 기억·요약을 최대 10개·문자 예산 안에서 읽어 초기 instructions에 전달합니다. 초기 네트워크 확인은 최대 2초까지만 기다리고 백그라운드에서 계속합니다. 다른 앱이 동기화 중이거나 오프라인이면 기존 개인 사본과 그 상태를 표시합니다. 프롬프트 원문과 팀 캐시는 포함하지 않습니다. 질문별 추가 회상은 `session_start_context`/`recall` 도구를 사용합니다. 호스트가 instructions를 소비하거나 모델이 규칙을 따르는 것까지 보장하지 않습니다. Claude/Codex/OMP 대화 이력을 자동 수집하는 훅은 설치하지 않습니다.

명시적 저장·수정·삭제는 `sync_retain`입니다. 재시도에 같은 `op_id`를 사용하고, 수정에는 같은 `memory_id`와 읽은 `base_revision`을 사용합니다. `session_id`, `source_id`를 전달하면 개인 replica에 보존합니다. 임의의 외부 세션 포맷 전체를 자동 변환하는 기능은 아닙니다.

원격 MCP `https://YOUR_HOST/mcp`와 Go `client/main.go` 전송기는 기존 온라인 경로로 남아 있습니다. 이 경로는 SQLite 전송함·기기별 이력 해시 검사를 거치지 않습니다. 복원 후에는 아래 epoch 변경·기존 키 회수·새 키 발급 절차를 반드시 적용해야 합니다. 오프라인 저장이 필요하면 위 설치 경로를 사용하세요. 팀의 `team_search`, `team_brief`는 매번 서버의 현재 권한을 확인하며 오프라인 팀 캐시를 제공하지 않습니다. `team_brief`는 최근 공유 항목 발췌이며 생성 LLM 작업 요약이 아닙니다.

## 백업 복원과 키 복구

DB 복원은 운영자가 API 접속을 막은 상태에서 수행합니다. **백업에는 과거의 키·권한 상태도 포함됩니다.** 복원 뒤 바로 API를 공개하면 과거에 회수된 키가 살아날 수 있습니다. 다음 명령은 동기화 epoch를 바꾸고 모든 기존 키를 회수합니다. 그 뒤 계정별 관리자 키와 기기 키를 다시 발급하고 접근을 엽니다.

```sh
docker compose exec -T server python -m agents_memory_collab.cli restore-epoch
docker compose exec -T server python -m agents_memory_collab.cli recovery-manager \
  --user-id ACCOUNT_UUID --output /data/recovered-manager.connection.json
```

클라이언트에서 같은 설치 명령에 `--replace-credential --recover`를 추가하고 같은 계정의 새 관리자/기기 키를 입력하세요. 연결 파일을 쓰면 `--credential-file /private/path/new-connection.json`도 지정합니다. 다른 계정의 키는 거절하고 기존 설정을 보존합니다. `sync ... recover` 또는 MCP `sync_recover`로 따로 복구할 수도 있습니다. 정상 이력이면 복구는 아무것도 바꾸지 않습니다. 기존 로컬 기억·전송함은 SQLite의 `recovery_archive`에 보관하고 서버 기준으로 다시 내려받습니다. 미전송 변경은 검토 대상으로 유지합니다. 복원에서 사라진 기억을 자동으로 다시 올리지 않습니다. 백업 복원 때문에 잃은 변경은 이 보관본과 별도 백업을 검토해야 합니다.

운영자가 epoch 변경을 빠뜨려도 이미 동기화한 PC는 커서 지점의 이력 해시 차이를 검사합니다. 변경 번호가 같거나 이전 번호를 넘어서도 잘못된 성공을 보고하지 않습니다. 이 검사는 **복원된 권한 상태를 복구해 주지는 않습니다**. 위 키 회수·재발급 절차가 필요합니다.

0.1 프리뷰의 해시 없는 replica는 자동으로 신뢰하지 않고 `legacy_replica_requires_recovery`로 멈춥니다. 같은 계정 확인 후 명시적 복구를 수행합니다. 계정에 묶이지 않은 예전 전송함은 보존하고 거절합니다. `sync ... export-pending --output /private/path/pending.json`으로 내용을 보관한 뒤 선택한 새 프로필에 필요한 항목만 다시 저장하세요. 내보내기는 전송함을 바꾸거나 서버에 올리지 않습니다.

## 운영·검증 범위

클라우드 서버 관리자는 저장된 내용을 볼 수 있습니다. HTTPS와 프로젝트 접근 제한을 사용하지만 종단간 암호화 제품은 아닙니다. 변경 로그와 서버 백업에는 과거 버전이 남을 수 있으므로 운영자가 보존·파기 정책을 관리해야 합니다.

외부 cmem.ai 계정·유료 TeamBrain 서버에 의존하지 않습니다. 결제·이메일 로그인·관리 웹 UI·HA·대규모 부하 검증은 포함하지 않습니다. 현재 서버 이미지는 Linux x64를 대상으로 합니다. 기존 로컬 Windows 지원 완료를 뜻하지 않습니다.

재현 테스트는 별도 PostgreSQL/pgvector DB를 지정합니다. 실제 사용자 DB를 테스트 DSN으로 사용하지 마세요.

```sh
python verify.py --pg-bin /path/to/postgres/bin --e5 /path/to/e5-small --work /private/empty-test-directory
```

실제 E5 검사에는 `AM_COLLAB_TEST_E5`, `AM_COLLAB_TEST_E5_MANIFEST`, 전송 클라이언트 검사에는 `AM_COLLAB_TEST_PROXY`를 지정합니다. 정확한 동작 계약은 [CONTRACT.md](CONTRACT.md), 재실행은 [verify.py](verify.py), 실행 증거는 VERIFICATION.json에 기록합니다. GitHub Actions는 2026-12-01까지 실행하지 않습니다.

Docker 실행 경로도 새 합성 DB로 확인할 수 있습니다. 기존 서버·볼륨은 사용하지 않고 검사 종료 후 생성한 컨테이너·네트워크만 지웁니다. 아래 명령은 이 서버 디렉터리에서 Linux의 로컬 Docker를 대상으로 실행합니다.

```sh
docker build -t agents-memory-collaboration:0.2.1-qa .
PYTHONPATH=src python verify_docker.py --work /private/empty-docker-test-directory
```

실행한 적대적 재검토와 수정 대응은 [REVIEW-RESOLUTION.md](REVIEW-RESOLUTION.md)에 있습니다. 업로드·팀 공개·삭제·복원 보장은 [CONTRACT.md](CONTRACT.md)를 기준으로 읽어 주세요.

0.2.1은 macOS의 OS 소유 `/var`, `/tmp`, `/etc` 루트 별칭을 정규화하는 설치 수정입니다. 일반 사용자 심볼릭 링크·하드 링크·공개 권한 파일 거부는 유지합니다. Linux에서 별칭 시뮬레이션/권한 검사 7개와 전체 64개 검사가 통과했으며, 이 수정의 Mac 실기 재검증은 남았습니다. 0.2.0의 기존 검증은 `VERIFICATION-0.2.0.json`에 보존합니다.
