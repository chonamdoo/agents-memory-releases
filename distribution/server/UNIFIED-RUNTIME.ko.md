# 2.0.0 공통 Hindsight 런타임

로컬·개인 서버·팀 서버·회사 서버는 같은 `agents_memory.unified_runtime`과
`HindsightEngine`을 사용한다. `--mode`는 설치 위치·표시와 로컬 바인딩 제약을
선택하며 저장 판단 알고리즘을 바꾸지 않는다. 팀·프로젝트 권한은 기존 인증
게이트웨이가 처리한다. 별도의 관리형 서비스나 그래프 DB를 추가하지 않는다.

2.0.0은 사용자가 품질 실패를 확인하고 배포를 선택한 공개 시험 릴리즈(prerelease)다. 원래 새 독립 v43에서 정당한 명시 저장
70/80·이어가기 Hit@5 30/40은 고정 Wilson 하한 기준에 실패했고 필수 근거 전체 회수는
2/40이다. 이전 v22/v27·현재 실패를 보존한다. 실제 CLI·소유 Mac·Linux·MCP 실행은
검증했지만 실제 회사 모델 추론이나 독립 품질 통과를 대신하지 않는다.

공통 엔진은 수정하지 않은 `hindsight-api-slim==1.1.0` 휠
(`sha256:d19a323afb7f9820e738ac9372f7a59ded21c1329b379195e7933a7dcefd2481`)로
고정한다. 시작할 때 실제 Python 소스 366개의 트리 해시를 확인하고, 다른 빌드나
기존 실험 포크가 섞이면 서비스를 준비 완료로 표시하지 않고 자식 프로세스를 종료한다. 과거 `14e7306` 실험 포크와
이번 공통 경로의 실행 증거를 혼용하지 않는다.

이 문서는 공통 런타임과 데이터 계약 안내다. 새 설치는 [시험 릴리즈 수동 번들 설치기](README.ko.md)를 사용한다. 기존 1.0.7 코어와 0.2.1 Docker/bootstrap은 새 런타임이 아니다.

## 공통 처리

```text
Claude / Codex / OMP 사용자 입력 훅 → 비공개 SQLite 전송함
  → 인증된 공통 게이트웨이 → 영속 received 작업
  → Jev 저장 판단·근거 구간 선택 → extracted
  → Hindsight 저장·본문/메타데이터 재조회·원문 보존 통합 완료 → indexed
  → 현재 revision과 변경 로그 공개 → ready → 다른 PC 적용·회상
```

접수 응답은 `state=received, memory_ready=false`다. 저장 거절은 별도
`discarded` 영수증이며, 거절된 수정은 기존 기억을 지우지 않는다.
공급자 장애는 재시도하고, 판단 보류는 `memory_requires_review`로 남겨
자동 과금 재시도를 반복하지 않는다. 원문 저장으로 우회하지 않는다.

추출은 원문의 정확한 구간을 선택하는 방식이다. 부정·조건·출처를 임의로
다시 쓰지 않는다. Hindsight는 선택된 기억의 저장·색인·회상을 맡는다.
기본 경로는 추가 모델 판정 없이 원문 전체가 같은 사실만 출처를 합치는
원문 보존 통합이다. 부정·조건·시점이 다르면 별도로 둔다.
[공급자별 처리 계약](GENERATION-CONTRACT.ko.md)을 따른다. 입력은 UTF-8
32,000바이트, 현재 구간 후보 최대 16개다. 초과 입력을 잘라 저장하지 않는다.

## 엔진 실행 위치와 판단 공급자

Claude·Codex·omp는 MCP·훅·압축 문맥 연결 앱이며 판단 공급자가 아니다.
판단은 엔진 호스트의 Jev HTTPS API만 사용한다. 구독 CLI 추론과 공급자 선택
메뉴는 제거했다. native CLI 자동 fallback·과거 엔진으로의 복귀는 하지 않는다.
기존 Jev 선택 모델을 보존하며 과거 native 설정은 설치기에 `--provider jev`를
명시해 전환한다. 키는 비공개 파일 또는 숨김 입력으로 제공하고 stdout에 출력하지 않는다.
전환 중인 설정은 `provider_verified=false`이며 MCP가 서비스를 시작할 수 없다.
선택한 키의 실제 API 확인 뒤에만 `true`로 공개한다. 새 키의 임시 파일은 성공·실패
모두 제거하며, 기존 키를 다른 입력으로 묵시적으로 교체하지 않는다. 설치는 소유
activation lock, 서비스 시작·중지는 공통 service lock을 사용한다. native→Jev
전환 실패는 native를 복원하지 않으며, 기존 Jev의 업데이트 실패만 같은 Jev로
되돌릴 수 있다. 실패한 작업 로그가 생성됐다면 prefix의
`settings/unified-operations.log`와 `settings/unified-service.log`에 비공개로 남긴다.
bootstrap 실패·시간 초과의 stdout/stderr는 각 최대 512 KiB를 비공개 임시
디렉터리에 보존하며 오류에는 위치만 표시한다.
직접 `service` 실행도 같은 lock과 PID·instance 영수증을 사용한다. `ensure`는
자식의 영수증 기록 후 시작 장벽을 해제하며 선택한 instance의 health만 인정한다.
추적되지 않는 서비스가 포트를 점유하면 기존 응답을 채택하지 않고 중단한다.
소유 Python과 pip의 target interpreter 모두 `-I`로 cwd·`PYTHONPATH` 주입을 막는다.
bootstrap·설치 subprocess의 Python 주입 변수도 제거하고, ambient admission 키
대신 명시적으로 선택·검증한 키 파일을 사용한다.

서버 운영자는 DB의 후보 원문·처리된 기억과 서버 키를 읽을 수 있다.
종단간 암호화 서비스가 아니다. 기기에는 서버의 Jev 키를 배포하지 않으며
각 기기는 자기 계정의 기기 키만 사용한다. OAuth 파일을 서버에 복사하지 않는다.

최초 엔진 설치는 [번들 설치기](README.ko.md)를 사용한다. lean 번들과 별도의
모델 companion에서 준비한 정확한 6파일 디렉터리를 `--reranker-dir`로 지정한다.
출처·라이선스는 밖에 두고, 그래프·tokenizer는 canonical
`reranker-assets.sha256.json`으로 검증한다. 모델 자동 다운로드는 하지 않는다.
기존 원격 `--connect-server` 클라이언트는 모델·bootstrap 없이 설치한다.
제품은 2.0.0이며 genuine bootstrap의 역사적 소유권 버전 1.0.2는 그대로다.

검토된 코어와 게이트웨이 패키지, 기존 PostgreSQL/pgvector, 고정 E5와 ONNX
재순위 모델이 준비된 격리 환경의 직접 실행 예시다. 비밀값을 명령 인자에 넣지 않는다.

```sh
export AM_MEMORY_PROVIDER=jev
# AM_MEMORY_MODEL에는 기존에 선택한 Jev 모델을 유지한다.
export AM_MEMORY_JEV_KEY_FILE=/absolute/private/jev-credential.json
# AM_COLLAB_DATABASE_URL은 서비스의 비공개 환경 설정에서 제공한다.
python -m agents_memory.unified_runtime \
  --mode personal-server \
  --hindsight-python /absolute/hindsight-venv/bin/python \
  --gateway-python /absolute/gateway-venv/bin/python \
  --e5-dir /absolute/pinned-e5 \
  --e5-manifest /absolute/e5-assets.sha256.json \
  --reranker-dir /absolute/prepared-reranker \
  --reranker-manifest /absolute/bundle/reranker-assets.sha256.json \
  --public-url http://127.0.0.1:18350
```

`AM_MEMORY_JEV_KEY_FILE`을 지정하면 그 파일이 환경변수
`HINDSIGHT_API_MEMORY_ADMISSION_API_KEY`보다 우선한다. 파일이 없거나 안전하지
않으면 중단하며 환경변수 키로 대체하지 않는다. 파일 변수를 지정하지 않은 경우에만
환경변수 키를 사용할 수 있다.

`--mode local|personal-server|team-server|company-server`에서 같은 경로를
실행한다. 로컬은 게이트웨이도 loopback에 제한한다. Hindsight API는 모든
모드에서 loopback 내부 전용이고, 외부 연결은 인증된 게이트웨이만 사용한다.
`--check`는 파일·구성만 검사하며 서비스나 모델을 호출하지 않는다.

Jev 판단과 별도로 로컬 ONNX cross-encoder는 검색 후보를 재순위화한다.
모델·그래프·tokenizer 고정값은 [판단·검색 계약](GENERATION-CONTRACT.ko.md)을 따른다.
CPU 실제 batch 8, threads 2, `max_tokens=512`, native reranker timeout `0`을 사용해
미채점 후보 fallback을 피한다. 외부 HTTP timeout만으로 추론 취소를 보장하지 않는다.
E5/RRF passthrough는 현재 경로가 아니다. ONNX 점수는 보편적 관련성 확률이 아니다.
공유 SDK 회상 경계의 native `min_scores.reranker=0.003`은 사전 고정한 새 개발 세트에서만 선택한
경험적 기준이며 SQL cosine 기준이나 독립 출시 품질 증명이 아니다. 거부된 전역
E5 `0.84` 기준은 적용하지 않는다. FP32와 FP16 기준 모델의 6쌍 최대 절대 오차
`0.00022161006927490234`는 검색 품질 증명이 아니다. ONNX와 같은 정밀도의
기준 모델 간 비교는 `atol=rtol=1e-4`에서 실패했고, 원래 FP32 기준 모델과의
비교는 같은 허용오차에서 통과했다. 실제 오차와 두 판정은 `reranker-provenance.json`에
각각 기록하며, 어느 결과도 검색 품질 통과로 바꾸지 않는다.
모델 이름이나 다국어 표기만으로 한국어 검색 품질을 보장하지 않는다.

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

같은 프로필·프로젝트를 다시 설정하면 SDK가 생성한 MCP 항목과 입력·세션
훅의 실행기 경로를 갱신한다. 이전 실행기를 가리키는 동일한 관리 훅은
하나로 정리하고, 사용자 훅이나 다른 프로필의 명령은 그대로 둔다.
OMP의 이전 SDK 확장은 공개된 본문 전체와 연결·사본·프로젝트 인자가
일치할 때만 현재 확장으로 교체한다. 관리 표제만 같거나 사용자가 수정한
확장은 소유한 것으로 간주하지 않으며 `existing_omp_automation_differs`로
중단한다. 연결 주소·기기 키·자동 수집 설정과 기존 작업 ID는 바꾸지 않는다.

이전 코어의 `.omp/extensions/agents-memory.ts`는 별도 소유권 영수증을
사용한다. SDK 설정기는 파일 이름만 보고 이를 삭제하지 않는다. 원래 코어
설정과 영수증으로 `host-uninstall --project /absolute/project --host omp`를
완료한 뒤 공통 클라이언트를 설정해야 한다. 원래 설정이나 영수증이 없으면
이 이전 경로의 자동 전환을 보장할 수 없다.

폐기 가능한 회귀 시나리오는 SDK 디렉터리에서
`python -m pytest tests/test_managed_hook_upgrade.py`로 실행한다.
격리한 프로젝트에 이전 SDK 설치를 만들고 실행기를 변경한 뒤 설치된 훅과
OMP 확장 콜백을 호출한다. 합성 loopback 서비스와 실제 SQLite 전송함을
사용하며 공급자를 호출하지 않는다. OMP에는 Bun이 필요하다. 이 시험은
실제 호스트 앱의 최초 신뢰 승인이나 Linux arm64 소스·런타임 실행기의
설치 지원을 입증하지 않는다.

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

## 서버 재시작과 지원 경계

MCP 연결 시 자동 시작은 같은 호스트의 로컬 엔진에 적용한다. 원격 서버의 OS 재시작은
서버 운영자가 서비스 사용자로 설정한다. Linux user systemd 예시(경로를 자신의 설치 경로로 변경):

```ini
[Unit]
Description=agents-memory unified Hindsight
After=network-online.target
[Service]
Type=simple
ExecStart=/home/USER/.local/share/agents-memory-unified/current/venv/bin/python -I /home/USER/.local/share/agents-memory-unified/unified-current/bundle/unified_setup.py service --prefix /home/USER/.local/share/agents-memory-unified
Restart=on-failure
RestartSec=5
UMask=0077
[Install]
WantedBy=default.target
```

`~/.config/systemd/user/agents-memory-unified.service`에 저장한 뒤
`systemctl --user enable --now agents-memory-unified`를 사용한다. 처음 등록하기 전
동일 설치의 수동 서비스는 설치기의 `stop`으로 종료한다. 로그아웃 후 실행은 운영자가
`loginctl enable-linger USER` 권한과 정책을 확인한다. 설치기는 sudo·방화벽·GCP 리소스를
자동 변경하지 않는다. 이 user unit과 Mac 로그인·절전 복귀는 이번 컨테이너 실험의 검증 범위 밖이다.

개인·팀·회사 서버는 배치와 기존 권한 기능을 뜻하며 SSO·SCIM·관리형 과금·사용자별
LLM 키 자동 분배를 추가 제공한다는 뜻이 아니다. 바이트코드 코어는 Python minor별로
고정하며 원본 소스를 제외하지만 역공학 방지를 보장하지 않는다.
