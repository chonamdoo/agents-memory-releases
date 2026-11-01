# 누적 개선점과 이번 배포 범위

숫자는 서로 다른 실험의 결과입니다. 합산하거나 전체 정확도/SOTA 향상률로 바꾸지 않습니다.
기존 Native 개발 소스의 개선은 20261027 배포 바이너리를 새로 빌드했다는 뜻이 아닙니다.
이번 배포는 검증된 공식 Hindsight reference 구성과 자료입니다.

| 개선 | 확인한 변화 | 한계/비용 | 이번 배포와의 관계 |
|---|---|---|---|
| Native 의미 검색·CE | 합성48기억/8질문에서 목표 후보 포함0/8→8/8, E5 대비 top5포함4/8→8/8 | 작은 합성 검색시험, 답변/SOTA 아님 | 이전 개발 소스 결과; 새 Native 바이너리로 배포하지 않음 |
| Native 후보 일괄 조회 | 후보20개 조회20→2호출, p50115.26→79.31ms | 후보 조회 구간만 측정 | 이전 개발 소스 결과; Hindsight 공식 API를 별도 사용 |
| 원문 창의 조건·예외 보존 | 공개272세션/첨부87문서에서 분할 문장·행102→0/72→0, byte유실0 | 고정16KiB 표현 비교, 답변 정확도 아님 | 이전 개발 소스의 보존 개선. 이번 profile도 원문/chunk 일치 검증 유지 |
| Native 최종 문맥의 주어 보존 | 같은4B reader 합성24질문18→24정답, 누락6개0→6개 | 입력token+2.6%, reader p504.93→5.24초; 공개 QA 아님 | 이전 개발 소스 결과; 새 Native 바이너리 미포함 |
| 모델 context 축소 | 같은 GGUF32k→16k matched쌍에서 모델PSS약2.25GiB/30.4%감소, 내부JSON동일 | 단일쌍, 장기문맥·속도·일반QA 미입증 | 선택적 생성 profile의 결과. 이번 no-LLM profile에는 생성모델 자체가 필수 아님 |
| 공식 Hindsight 직접 사용 | NoneLLM/chunks/공식ONNX/RRF 기동·수동MCP·원문/정책 일관성 확인 | 자동추출·관찰·Reflect 기능 축소; full benchmark 성능과 다름 | 이번 설정 배포에 포함 |
| 저장·조회·수정·삭제 검증 | 실제 core 시험의 이전source ID4개 제거, source5+연결관찰5개 삭제 후 각각조회불가 | 별도 full-generation 작은 합성bank; MM철회/ACL 아님 | 검증 자료로 설명; 이번 reference의 generated OBS 기능이란 뜻 아님 |
| 공식 전송 복구 확인 | accepted 뒤 ACK유실→freshprocess가 같은 operationID/본문 재전송;3retainPOST→고유op2개완료, source중복/pending0 | 같은 공식client bounded시나리오; 전원손실·교차세션 전체복구 아님 | 공식 통합 선택 근거. 새 자동hosthook 설치는 포함하지 않음 |
| 7분류 메타데이터 | 수동7분류, strict양성7/음성2조회·미분류canary삭제 | NLP자동분류/팀권한 아님 | 설정·직접 MCP 안내 포함 |
| 불필요한 확장 억제 | 관련OSS21개와 공식옵션·이슈·미병합PR 대조 후 새adapter/엔진0 | 외부프로젝트를 전부 실행한 검증은 아님 | 검증된 최소 구성 유지 |

현재 공개 Hindsight94.6%와 같은 모델·dataset/judge/예산으로 정확도를 입증하지 않았습니다.
알려진 정책 한 건5/5는 fullsource를 읽는 통합 일관성 검사이며 검색-only 점수가 아닙니다.
전체 생성 추출/Reflect 실패를 경량 profile의 성공으로 덮지 않았습니다.

기존 설치에 대한 자동 DB 변환·기존 바이너리 교체·서비스/host hook 변경·새 외부 모델 전송은
이번 배포가 수행하지 않습니다. 실제 수치는 VALIDATION.json의 profile별 범위와 함께 읽으세요.
