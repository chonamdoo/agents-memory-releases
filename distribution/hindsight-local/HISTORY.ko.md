# 선택형 기록 후보와 사용량 원장 (1.0.2)

기본 설치·업데이트는 과거 대화를 읽지 않습니다. 기존 Jev/Claude/Codex 선택, 로그인, 키와 설정을 유지합니다. E5 검색 임베딩은 포함됩니다. 이 기능은 LLM 모델 가중치를 설치하지 않으며, 사용자가 선택한 구독 CLI 또는 Jev를 사용합니다.

## 기록 후보 검토

`am-hindsight history` 뒤의 공통 인자는 하위 명령 **앞에** 넣습니다.

```sh
AM="$HOME/.local/share/agents-memory-hindsight/current/bin/am-hindsight"
# project-init 출력의 절대 project/config 경로를 사용합니다.
"$AM" history --project /absolute/project --config /absolute/private/hook.json preview \
  --host claude --history-dir /absolute/selected/history \
  --since 2026-11-01T00:00:00+00:00 --until 2026-11-02T00:00:00+00:00
```

Codex는 `--host codex`를 사용합니다. 해당 디렉터리 안 JSONL만 제한적으로 읽습니다. 원본은 현재 사용자 소유 일반 파일, 권한 0600, 하드링크 1개여야 합니다. 심볼릭 링크·다른 프로젝트·분기 세션·비밀값·주입 문맥·과대 메시지는 거부합니다. Claude의 직접 user 이벤트와 Codex의 canonical `event_msg.user_message`만 지원합니다. 알려지지 않은 형식은 읽지 못할 수 있습니다. 다른 cwd가 섞인 Codex 파일은 전체 거부합니다.

최대 파일 8MiB, 회차 총량 64MiB, 기본 200파일, 메시지 8192바이트, 날짜 범위 최대 366일입니다. `complete:false`이면 같은 범위로 `sync`를 반복해 미처리 파일을 확인합니다. 성공적으로 읽은 변경 없는 파일과 동일 내용은 중복 처리하지 않습니다. `complete:true`는 제한된 스캔 완료이며 모든 CLI 로그 버전 인식을 보장하지 않습니다.

```sh
# 위와 같은 공통 인자를 모든 명령에 사용합니다.
"$AM" history --project /absolute/project --config /absolute/private/hook.json inspect CANDIDATE_ID
"$AM" history --project /absolute/project --config /absolute/private/hook.json analyze CANDIDATE_ID --approve-egress
# inspect가 보여준 정확한 payload와 현재 적용 가능성을 검토한 뒤:
"$AM" history --project /absolute/project --config /absolute/private/hook.json approve CANDIDATE_ID \
  --confirm-digest INSPECT_DIGEST --confirm-current
"$AM" history --project /absolute/project --config /absolute/private/hook.json send CANDIDATE_ID
```

preview/sync/inspect는 모델 호출 0회입니다. analyze는 선택한 원문을 **현재 설정된 모델**로 전송하며 사용량이 발생할 수 있습니다. 과거 제공자를 자동 선택하지 않습니다. keep 판정만으로 저장하지 않습니다. 모델·프로젝트/환경·원문이 바뀌면 재검토해야 합니다. 공통 `--environment LABEL`로 배포환경을 구별할 수 있습니다.

## 불확실한 저장·정정·삭제

send는 같은 항목을 자동 재전송하지 않습니다. 응답 유실은 `unknown`이며 `reconcile ID`로 원문 해시와 소유 마커가 일치하는 문서를 조회합니다. 문서가 없다는 조회만으로 재전송을 허용하지 않습니다. `--backend-timeout SECONDS`(기본30, 최대120)는 명시적인 HTTP 작업 대기 시간입니다.

`forget ID`는 재수입 방지 표식을 먼저 남기고 이 원장이 정확히 식별한 문서만 삭제합니다. 지연 저장·조회 장애는 `forget_pending`으로 남고 reconcile로 후속 확인합니다. 원격 문서가 변경되거나 여러 개이면 자동 삭제하지 않습니다. 기존 방식으로 저장한 기억·별도 원장·외부 복사·백업을 전역 삭제하는 기능은 아닙니다.

새 후보를 분석·검토한 뒤 `replace OLD_ID NEW_ID --confirm-digest DIGEST --confirm-current`로 정정합니다. 이전 문서의 삭제가 확인돼야 새 문서를 보냅니다. 원격 작업은 원자적이지 않으며 중간 실패 상태를 확인해야 합니다. 과거 기억을 현재 실행 규칙으로 자동 주입하지 않습니다.

## 사용량과 수동 조언

`usage --event-file /absolute/private/event.json`은 본문 없는 현재 실행의 CLI 보고 토큰을 기록합니다. JSON 필드: `id, session, model, input_tokens, cached_tokens, output_tokens, state, origin`. origin은 live, state는 completed/failed/unknown이며 미확인 토큰은 null입니다. 아래와 같은 JSON을 0600 파일로 저장합니다: `{"id":"call-1","session":"s1","model":"gpt-6.1-terra","input_tokens":100,"cached_tokens":20,"output_tokens":30,"state":"completed","origin":"live"}`. 이전 이력 재생을 청구량으로 집계하지 않습니다. `stats`는 알려진 토큰·분석 호출·미확인 사용량을 보여주며 비용/쿼터 절감률을 만들어내지 않습니다.

`observe --event-file /absolute/private/event.json` 필드는 `id, session, turn, tool, outcome, signature`이며 outcome은 success/failure/expected-failure/available입니다. 프롬프트·명령·도구 결과 본문은 받지 않습니다. signature에는 비밀이 없는 분류 ID를 넣으세요. `advice`는 같은 세션·턴·도구·서명의 반복 실패와 충분한 세션의 미사용 도구만 수동 검토 대상으로 제시합니다. 정상 TDD의 expected-failure는 반복 실패에서 제외합니다. 필수 읽기/쓰기/메모리/복구 도구는 비활성화 대상으로 제안하지 않습니다.

자동 도구 삭제, stop 강제, host 설정 수정, telemetry hook 자동 설치는 하지 않습니다. 이벤트 수집을 연결하려면 별도 명시적 설정이 필요합니다. 로컬 원장은 항목 참조와 해시를 저장하며 원문 본문은 저장하지 않습니다. 원본/DB/키 권한은 유지하세요.

검증 범위: Linux x86_64 합성 입력과 실제 선택 CLI 연동. macOS arm64 바이너리는 교차 빌드했으며 macOS 실기 실행은 수행하지 않았습니다.
