# 저장 판단과 분리한 검색 개발·검증

Jev 키나 외부 판단 API를 사용하지 않는다. 사전에 고정한 합성 문서만 그대로
저장하고 실제 고정 Hindsight/E5/BGE·SQL 권한/현재 revision·상위 5개 결과를
실행한다. 개발과 검증은 각각 20개 다른 주제, 문서 60개, 한·영 질문 40개와
서로 다른 무관 질문 12개다. 한 저자가 제품 출력 전에 작성한 source-ID gold다.
별도 미사용 검증셋이며 독립 인간 라벨·일반 사용자 분포의 표본이라고 하지 않는다.

등록된 개발 후보는 `registration.json`에 고정한다. Native 후보를 한 번 회수한
뒤 floor별 source 회수·필수 근거 전체 회수·잡음·무관 질문의 반환 중단을 비교한다.
개발셋에서만 선택하고, 제품 source 지문과 선택 floor를 고정한 뒤 검증은 실제
제품의 필터 경로로 한 번만 실행한다. 이전 실패·원래 v43·이유·한도는 유지한다.

```sh
python run.py --receipt /absolute/synthetic-runtime/receipt.json \
  --split development --output /absolute/new-development-output
python run.py --receipt /absolute/synthetic-runtime/receipt.json \
  --split validation --candidate /absolute/frozen-candidate.json \
  --output /absolute/new-validation-output
```

검증 marker는 `~/.local/state/am-search-evaluation`에 먼저 예약한다. 같은 fixture의
검증을 새 후보에 맞춰 재실행하지 않는다. 개발 출력만 비교한 실행은 validation
증거가 아니다. 양쪽 언어 질문이 같은 주제에 묶이므로 Wilson 수치를 독립 사용자
질문 40건의 신뢰구간으로 일반화하지 않는다. 이번 검색 자료는 저장 판단·실제
회사 모델·세 앱 native 소비·전체 배포 검증의 통과를 대신하지 않는다.
