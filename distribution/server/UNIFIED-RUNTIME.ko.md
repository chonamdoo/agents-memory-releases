# 공통 Hindsight 런타임 — 0.3.0.dev1, 미배포

로컬·개인 서버·팀 서버·회사 서버는 같은 `agents_memory.unified_runtime`과
`HindsightEngine`을 사용한다. `--mode`는 설치 위치·표시와 로컬 바인딩 제약을
선택하며 저장 판단 알고리즘을 바꾸지 않는다. 팀·프로젝트 권한은 기존 인증
게이트웨이가 처리한다. 별도의 관리형 서비스나 그래프 DB를 추가하지 않는다.

이 문서는 소스 실행·검증 안내다. **기존 1.0.7 코어와 v0.2.1 Docker 이미지는
새 공통 런타임을 포함하지 않는다. 다음 코어의 플랫폼별 패키징·새 설치 시험이
끝나기 전에는 이 개발 버전을 정식 배포하지 않는다.** 기존 릴리즈와 사용자
설치는 이번 작업에서 변경하지 않았다.

## 공통 처리

```text
Claude / Codex / OMP 사용자 입력 훅 → 비공개 SQLite 전송함
  → 인증된 공통 게이트웨이 → 영속 received 작업
  → 선택 공급자의 저장 판단·근거 구간 선택 → extracted
  → Hindsight 동기 저장·본문/메타데이터 재조회 → indexed
  → 현재 revision과 변경 로그 공개 → ready → 다른 PC 적용·회상
```

접수 응답은 `state=received, memory_ready=false`다. 저장 거절은 별도
`discarded` 영수증이며, 거절된 수정은 기존 기억을 지우지 않는다.
공급자 장애는 재시도하고, 판단 보류는 `memory_requires_review`로 남겨
자동 과금 재시도를 반복하지 않는다. 원문 저장으로 우회하지 않는다.

추출은 원문의 정확한 구간을 선택하는 방식이다. 부정·조건·출처를 임의로
다시 쓰지 않는다. Hindsight는 선택된 기억의 저장·색인·회상을 맡는다.
생성형 재서술·문서 간 자동 관찰 통합은 이 계약에서 구현·완료로 주장하지
않는다. 입력은 UTF-8 32,000바이트, 현재 구간 후보 최대 16개다. 초과 입력을
잘라 저장하지 않으며 명시적인 입력 오류로 보존·분리한다.

## 엔진 실행 위치와 공급자

| 선택 | 실행 위치 | 외부 전송 | 인증 |
|---|---|---|---|
| Jev | 엔진 호스트에서 HTTPS 호출 | 판단 대상 원문·선택 후보 | 호스트의 비공개 키 파일 또는 명시적 환경변수 |
| Claude 구독 CLI | 엔진 호스트의 설치된 CLI | 해당 구독 서비스에 판단 입력 전송 가능 | 그 호스트·서비스 사용자로 직접 로그인 |
| Codex 구독 CLI | 엔진 호스트의 설치된 CLI | 해당 구독 서비스에 판단 입력 전송 가능 | 그 호스트·서비스 사용자로 직접 로그인 |
| 실제 로컬 가중치 모델 | 새 공통 어댑터 미구현 | 미정 | 자동 호환·대체를 주장하지 않음 |

서버 모드를 택해도 Jev/CLI 판단이 필요하다. Mac의 OAuth 파일을 서버에
복사하지 않는다. 서버 운영자는 DB의 후보 원문·처리된 기억과 서버 키를
읽을 수 있다. 종단간 암호화 서비스가 아니다. 기기에는 서버의 Jev 키를
배포하지 않으며 각 기기는 자기 계정의 기기 키만 사용한다.

검토된 코어와 게이트웨이 패키지, 기존 PostgreSQL/pgvector, 고정 E5가
준비된 격리 환경에서 다음과 같이 실행한다. 비밀값을 명령 인자에 넣지 않는다.

```sh
export AM_MEMORY_PROVIDER=jev
export AM_MEMORY_MODEL=jev-1.14.0
export AM_MEMORY_JEV_KEY_FILE=/absolute/private/jev-credential.json
# AM_COLLAB_DATABASE_URL은 서비스의 비공개 환경 설정에서 제공한다.
python -m agents_memory.unified_runtime \
  --mode personal-server \
  --hindsight-python /absolute/hindsight-venv/bin/python \
  --gateway-python /absolute/gateway-venv/bin/python \
  --e5-dir /absolute/pinned-e5 \
  --e5-manifest /absolute/e5-assets.sha256.json \
  --public-url http://127.0.0.1:18350
```

`--mode local|personal-server|team-server|company-server`에서 같은 경로를
실행한다. 로컬은 게이트웨이도 loopback에 제한한다. Hindsight API는 모든
모드에서 loopback 내부 전용이고, 외부 연결은 인증된 게이트웨이만 사용한다.
`--check`는 파일·구성만 검사하며 서비스나 모델을 호출하지 않는다.

CLI 공급자는 `AM_MEMORY_PROVIDER=claude|codex`, `AM_MEMORY_MODEL`,
`AM_MEMORY_EXECUTABLE`, `AM_MEMORY_WORKDIR`를 지정한다. 실행 파일과
작업 폴더는 명시적인 절대 경로다. 공급자·API 경로가 충돌하면 거절한다.
생성 모델 가중치를 자동 설치하지 않는다. 모든 공급자는 같은 근거 구간
선택 정책을 사용하며, 모델 출력의 문장 단위 동일성을 보장하지 않는다.

## 세 앱 연결과 자동 동작

엔진을 준비한 뒤 새 `distribution/install.sh --mode ...`는 모든 위치에서
같은 클라이언트를 설치한다. 이전 로컬 엔진으로 자동 대체하지 않는다.
최초 계정·기기 키 생성은 기존 관리자 `account`/`devices` 절차를 사용한다.

```sh
bash distribution/install.sh --mode personal-server \
  --client all --project /absolute/project \
  --url https://YOUR_GATEWAY --credential-file /absolute/private/device.json
```

로컬의 기본 연결 주소는 `http://127.0.0.1:18350`이다. 서비스 준비와
클라이언트 연결은 별개이며, 엔진 없는 설치를 ready로 표시하지 않는다.
v0.2.1 서버에 새 클라이언트를 연결하면 계약 업그레이드를 요구하고 원문을
그대로 업로드하지 않는다.

설정 파일은 `.mcp.json`, `.codex/config.toml`, `.omp/mcp.json`이다.
자동 동작은 `.claude/settings.local.json`의 입력·세션 훅,
`.codex/hooks.json`의 입력·세션 훅, `.omp/extensions/agents-memory-cloud.ts`의
`before_agent_start`로 연결한다. 기존 항목과 키·연결 주소는 보존한다.

- 현재 사용자 프롬프트를 후보로 수집한다. 전체 세션 이력이나 모든 도구
  출력·답변을 자동 수집하는 구현은 아니다.
- MCP 프로세스가 실행되는 동안 백그라운드 전송·수신한다. 접수·처리·적용은
  서로 다른 상태다. 앱이 모두 종료되면 다음 실행 때 재시도를 이어간다.
- 질문 시점에 현재 권한으로 회상하고 문맥을 전달한다. 단순 허용 목록이나
  “회상하라”는 지침만으로 자동 동작을 주장하지 않는다.
- 최초 프로젝트/훅 신뢰, 확장 활성화는 호스트 앱의 정책을 따른다. 특히
  Codex는 프로젝트 신뢰가 없으면 훅을 발견하지 않는다. 매 저장 시 승인과
  최초 설치 신뢰를 구분한다. 이 설치기는 사용자 전역 신뢰를 변경하지 않는다.
- Mac 실기기·로그인/절전 복귀·네이티브 Windows는 이번 Linux 검증으로
  입증되지 않았다. 사용자의 Mac 설치 시험은 정식 패키지 준비 후 진행한다.

## 기존 데이터 전환

기존 SQL 기억과 변경 로그, 계정·키를 삭제하거나 자동 재분류하지 않는다.
기존 원문형 행은 `legacy_pending`이며 처리된 기억으로 검색하지 않는다.
계정 본인의 읽기 전용 계획은 다음과 같다. 원문 대신 ID·귀속·해시만 출력한다.

```sh
agents-memory-cloud sync --connection /private/device.json --state /private/replica.sqlite legacy-plan
```

영향을 확인하고 명시적으로 재처리할 때만 다음 명령을 사용한다. 이 작업에서는
합성 데이터로만 실행했다. 실제 사용자 데이터에는 적용하지 않았다.

```sh
agents-memory-cloud sync --connection /private/device.json --state /private/replica.sqlite \
  reprocess-legacy --memory-id MEMORY_UUID --apply
```

같은 기억 ID·귀속을 유지하고 새 revision을 추가한다. 중간 실패와 재실행은
같은 작업 ID·준비 결과·Hindsight 문서로 복구한다. 거절된 과거 원문은
`legacy_rejected`로 보존하며 검색하지 않는다. 이전 로컬 Hindsight bank를
계정·프로젝트에 대응시키는 일괄 이전은 별도 검토가 필요하다. 기존 bank를
삭제하거나 수동 내보내기를 일상 저장의 기본 경로로 요구하지 않는다.

검색 제외·동기화 삭제·Hindsight 문서 삭제는 시험한다. 과거 SQL 로그와 백업의
원문까지 파기했다고 주장하지 않는다. 복원할 때는 애플리케이션 스키마와
Hindsight 스키마를 함께 복원하고 epoch를 교체·기존 키를 폐기한다. 이미 받은
사본과 진행 중 요청을 원격 회수한다고 주장하지 않는다.

## 배포 전 남은 경계

새 코어의 플랫폼별 바이너리/의존성 잠금과 실제 새 설치·업데이트 패키지를
만들어야 한다. 기존 Docker/bootstrap은 0.2.1 자료이며 새 런타임을 담지
않으므로 아래 과거 안내로 공통 계약을 충족했다고 주장할 수 없다.
개인 서버·팀 서버·회사 서버는 배치 형태이며, 회사용 SSO·SCIM·세밀한 관리형
과금·사용자별 LLM 키 선택 기능을 추가로 제공한다는 뜻이 아니다.
