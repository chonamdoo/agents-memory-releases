# Jev v16·원문 보존·MCP 수정 후보

엔진·SDK2.0.0 **시험판**, 마켓 패키지2.0.3. 현재 정식은1.0.8이다.
전체 정식 조건은 [상태표](../v2.0.0-stable/STATUS.json)에서 확인한다.

## 수정 후보 설치

[런타임 번들](agents-memory-unified-2.0.0-request-scope-v16.tar.gz)과
[JEV197-SHA256SUMS](JEV197-SHA256SUMS)를 같은 폴더에 내려받는다.
모델 companion은 기존 [v2.0.0 릴리즈](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0)의
`agents-memory-reranker-2.0.0.tar.gz`를 원래 `SHA256SUMS`로 확인한 뒤 사용한다.

```sh
shasum -a 256 -c JEV197-SHA256SUMS
mkdir request-scope-v16
tar -xzf agents-memory-unified-2.0.0-request-scope-v16.tar.gz -C request-scope-v16
bash request-scope-v16/install-unified.sh --bundle "$PWD/request-scope-v16" \
  --reranker-dir /absolute/companion/model --provider jev \
  --client claude-plugin --project /absolute/project
```

Claude 플러그인은 `--client claude-plugin`, OMP는 `--client omp-plugin`,
Codex는 `--client codex`를 사용한다. 마켓 설치 방법은 [처음 화면](../../README.md)을 보라.
최초 설치의 pinned bootstrap·PostgreSQL/pgvector·모델 준비 조건은 기존 설치기와 같다.
실제로 이 전체 bootstrap 설치를 Linux에서 완료한 뒤 같은 경로의 업데이트도 검증했다.

Jev 키는 설치기의 숨김 입력 또는 소유한 비공개 파일로 전달한다. 업데이트는
실제 설치 prefix와 같은 인자로 다시 실행한다. 키·DB·연결·모델은 플러그인 캐시
밖에 보존한다. 앱을 재시작하고 `setup_status`에서 server 준비 상태를 확인한다.
처음 연결은 서비스 준비가 끝나기 전에 응답할 수 있으며 완료될 때까지 상태를 확인한다.
현재 Linux 실측을 새 macOS 설치 검증으로 취급하지 않는다.
격리 실측은 Ubuntu24.04·glibc2.39·Linux x86_64에서 수행했다. Debian12의
glibc2.36에서는 pinned pgvector 로더가 실패한 기록이 있어 지원으로 표시하지 않는다.

## 이번 수정

- v16은 본문의 다른 인용부호와 언어가 바뀐 별도 기억 요청문을 구분하도록
  Jev 질문을 명확히 한다. 수치 임계값·비밀 가드·review 경계는 유지한다.
- Native의 별도 `merge/keep` 중복 관측 요청을 지원한다. 유사한 원문을 다시 쓰거나
  합치지 않고 각각 보존한다. 미지원 스키마와 기존100KB입력 한도는 계속 거절한다.
- SDK의 기본 의미 검색 대기는 Native120초 한도를 수용하도록130초다. 일반 동기화·
  원문 검색은 기존10초이며 호출자가 지정한 대기 시간은 유지한다. 검색 속도 개선 주장은 아니다.
- Linux에서 종료 중 프로세스의 cmdline이 비는 경우 종료 상태를 다시 확인한다.
  살아 있는 다른 PID를 중단하지 않는 기존 경계는 유지한다.
- `Widget.limit` 같은 한정된 이름을 질의하면 Native 후보의 권한 검사를 거친
  전체 원문에서 같은 이름을 확인한 뒤 상위 결과를 제한한다. 유사한 다른 필드가
  정확한 대상을 밀어내는 문제를 줄이며 일반 문장·약어·URL 검색은 유지한다.
- `model Widget`처럼 타입을 명시하면 해당 타입의 설명을 멤버만 언급한 자료보다
  먼저 반환한다. 타입·필드를 함께 지정하면 정확한 필드명이 우선한다.
- 긴 검색에서4GiB를 넘긴 원래 실패를 보존하고 재순위화 배치를8에서1로 줄였다.
  같은 모델·512토큰·전체 후보·완전한 신경망 채점과2CPU·4GiB 한도는 유지한다.

source-free Core는 기존13개 private 모듈 중 policy·source integration·unified runtime bytecode와
RECORD가 바뀌었다. SDK는 client의 대기 정책·store의 한정 이름 검색·stdio의
도구 설명이 바뀌었고 SQL·모델은 같다.
[CP312](CP312-V16-RUNTIME.json)·[CP313](CP313-V16-RUNTIME.json)에서13Core·15SDK모듈과
SQL을 설치본 바이트로 대조했다. 두 shipping wheel에서 관련 Core 회귀36개씩,
최종 SDK의 검색·원문 검색·대기 정책59개씩 통과했다. 직렬 배치 Core 런타임은
소스와 두 설치본에서38개씩 통과했다.

## 실제 결과와 범위

| 검사 | 관측 |
|---|---|
| 누적 승인·예약 | 1,000회 중418예약,582잔여; 전송 전 실패1건도 포함 |
| v15개발 명시 판정 | 79/80, Wilson하한0.932537로 실패 보존 |
| v16개발 전수 | 질문이 바뀐19건만 추가 호출 후80/80; 소비된 개발 자료 |
| 새 고정 자료의 실제 Jev | 194판정+전송 전guard2건, 명시80/80·자동precision/recall40/40·음성keep0 |
| 새 자료의 실제 저장 | 196건 처리,120commit·Native문서120, 명시80/80, guard2건 job미생성 |
| v15실제 Native검색 | 관련 근거40/40·필수3근거전체36/40·잡음8/124반환출처 |
| 새 v16실제 stdio MCP검색, 수정 전 | 관련32/40·필수3근거전체6/40·잡음134/200; 실패 보존 |
| 한정 이름만 적용한 원래40질문 | 관련·전체근거각30/40, 잡음0/90; 오류 질문10건도 분모에서 빼지 않음 |
| 타입 설명 우선순위·직렬 배치 수정 후 | 교정 질문의 격리 실제 MCP40건 실행 중; 다른 후보의 응답 재사용0 |
| 로컬 CI | Core소스5,334·설치wheel899통과; Darwin전용각5미실행 |
| SDK·배포 검사 | 최종 SDK322통과·실패/skip0, 관련59개×두Python통과 |
| 실제 설치 | bootstrap최초설치·업데이트·cold MCP autostart통과, 키·DB·모델·연결보존 |

입력·정답·정책은 최초 호출 전에 지문으로 고정했다. 사용자가 원자료가 없으므로
직접 만들라고 지시해 첫 개발196건과 별도 SDK실행가능JSON Schema기반196건을
작성했다. 두 자료의 원문 SHA-256은 겹치지 않지만 넓은 소프트웨어 주제·템플릿은
공유한다. **작성자는 한 명이고 독립 인적 라벨·Cohen κ·사용자 모집단 성능의
증거는 아니다.** 생성 reader 답변 정확도도 평가하지 않았다.

실제 Jev 판정은 shipping processor에서 수집했고 저장·검색에서는 동일 요청의
기록 응답을 재사용했다. Native·PG·E5·BGE·로컬 원문 보존 어댑터는 실제 경로다.
재사용을 새 공급자 호출이나 새 독립 평가로 세지 않는다. `source_search`는 선별
메모와 별도이며 원문 검색 점수를 Native `recall`의 점수로 바꾸지 않는다.

첫 실제 저장은 Native dedup미지원으로20번째작업에서503이 났다.
[실패](FRESH-FAILED-INTEGRATION.json)를 보존하고 같은 DB·계정·작업ID를 수정 후
재시도한 [저장 결과](FRESH-STORAGE.json)를 분리했다. MCP 평가 실행기의 대기시간
형식·동적 localhost포트/replica귀속 문제도 기록하며 제품의 보안 검사를 완화하지 않았다.

자료 생성기의 오류도 확인했다. 원래40질문 중10건이 JSON Schema 루트용 내부
표시 `.$schema`를 실제 API필드처럼 물었다. 원본 질문·실패를 보존하고 수정
질문의 해시와 변경 이유를 별도 고정했다. 수정된10질문은 개발 인수검사로만
보고하며, 원 계약의 질문 변경 제한이나 독립 평가를 통과한 것으로 표시하지 않는다.

[중간 실패 기록](PRESERVED-INTERMEDIATE-FAILURES.json)은 배치 수정의 부분 진단,
멤버 문서의 순위 문제, 정렬 함수 이름 충돌 및 테스트 실행기의 DB 공유 충돌을
구분한다. 최종 검사는 Python별·전체 SDK별로 다른 임시 DB를 사용한다. 부분 실행이나
구버전의 성공을 현재 후보의 전수 통과로 합치지 않는다.

기존 v43의70/80저장·30/40검색·전체근거2/40실패와 옛 원장은 보존한다.
현재 새 원장이 과거844/1,000의 원장을 복원하거나 초기화한 것은 아니다.
[누적 원장](SESSION-BUDGET.json)·[새 자료](FRESH-COHORT.json)·[판정](FRESH-ADMISSION.json)·
[실제 Jev지연](FRESH-JEV-LATENCY.json)·[Core로컬CI](LOCAL-CI.json)를 확인한다.

공개 체크아웃에서 다음 검사는 배포 바이트·지문·호출 원장·실패 보존의 내부
일관성을 확인한다. 비공개 원문·실험의 독립 인증이나 정식 승인을 대신하지 않는다.

```sh
python3 release-candidates/v2.0.0-jev197/verify-candidate.py
```

실제 키·private Core원본·원시 대화와 공급자 cassette는 공개하지 않는다.
마켓 전달은 이 저장소 링크와 고정 번들 설치로 검증하며 중앙 공식 디렉터리의
등재 완료를 주장하지 않는다. [공개 마켓 업데이트](PUBLIC-MARKETPLACE.json)로 세 앱의2.0.2→2.0.3과 설치파일13개씩을 확인했고, [설치된 커넥터](PUBLIC-CONNECTORS.json)의 실제 MCP연결도 검증했다. [공개 다운로드](PUBLIC-INSTALLED-CP312.json)는 고정커밋 e881375의 번들과 일치한다. 현재 정식 전환은 미완료다.
