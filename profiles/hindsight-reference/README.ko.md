# Hindsight 경량 reference 프리뷰 — 2026-11-01

공식 Hindsight를 문서·명시적 작업 기억 저장소로 사용하는 **설정/검증 자료 배포본**입니다.
새 macOS 실행 파일이나 자동 설치기·DB·모델을 포함하지 않습니다. 기존 Native 바이너리는
별도 20261027 프리뷰이며 이번 설정을 설치한다고 Hindsight로 바뀌지 않습니다.

공식 NoneLLM + chunks + local multilingual-E5-small ONNX + RRF를 사용합니다.
현재 코딩 AI가 recall과 원문을 읽고 판단합니다. 로컬 추출 LLM·CE·Native bridge·UI가
필수 서비스가 아니므로, 일반 문서 참조에 필요한 구성을 줄일 수 있습니다.
자동 사실 추출·관찰 통합·Reflect·mental model 기능은 이 profile에서 제공하지 않습니다.

[누적 개선점·배포 포함 범위](PROGRESS.ko.md), [설치·연결 안내](INSTALL.md), [검증 범위](VALIDATION.json), [공식 source/model 식별](UPSTREAM.json)을
먼저 확인하세요. GitHub에 게시한 구성 자료이며 운영 서버 전환·기존 데이터 이전은 하지 않습니다.

| 확인한 개선/기능 | 실제 결과 | 해석 범위 |
|---|---|---|
| 선택적 생성 모델 context 32k→16k | 모델 PSS 7,762,054→5,401,682 KiB, 약2.25 GiB/30.4% 감소; 내부 JSON 출력 동일 | 동일 GGUF·환경·프롬프트의 새 프로세스 한 쌍. 이 no-LLM profile에는 Qwen이 없으며 전체 RAM/QA 향상 수치가 아님 |
| 공식 API+worker+ONNX | 작은 working bank에서 PSS768,850 KiB(약751 MiB) snapshot | DB·보존 비교 서버 제외. peak/최소 RAM·다른 OS 성능 미입증 |
| 실제 정책 원문 참조 | 고정 조건5개·원문 인용 위치5개 일치, 원문 byte 일치 | 같은 알려진 문서1개, 전체 원문 제공. blind/검색-only/SOTA 점수가 아님 |
| 7분류 metadata/조회 | 양성7회+음성2회 strict 조회와 미분류 canary 삭제 통과 | 수동 태그, 자동 분류나 사용자별 권한 아님 |
| 비교 모델/bridge 종료 후 사용 | 새 MCP 세션 원문·회상 재확인 통과 | 별도 Native 모델 provider를 사용하지 않는 로컬 reference 경로 |

추가로 full-generation Hindsight의 작은 core 시험에서 문서 교체·원문/연결된 자동 관찰 삭제·
bank 라우팅, 공식 coding-agents의 ACK 유실 후 동일 operation ID·보류 본문 재전송을 확인했습니다.
그 시험의 observation/복구 결과를 이 no-LLM profile이나 실제 host 자동 hook 전체에 확대하지 않습니다.
기존 full concise 정책 추출과 Reflect 시험의 실패는 해결로 표시하지 않습니다.

공개 GitHub 검색14질의/41페이지의 중복 제거 후보2,259개 중 관련 저장소21개의 소스를
고정 커밋으로 검토했습니다. ai-memory-lab의 ONNX/RRF, Pi 확장의 큐·timeout, TanStack AI,
Vercel Eve, AgentZero/OpenWebUI 등의 실제 통합을 대조했습니다. 공개 코드 존재만으로
성능 이득을 인정하지 않았고, 검증된 추가 이득이 없어 새 외부 adapter/패키지는 넣지 않았습니다.
전체 GitHub 전수조사를 뜻하지 않습니다. 공식 Hindsight 자체와 필수 의존성은 별도로 설치합니다.

Hindsight 이미지94.6%, 논문 v1의91.4%, 이번 known-case5/5는 모델·평가 조건이 다릅니다.
**SOTA 정확도, 모든 실제 host hook, 다중 사용자 ACL, 전원 장애 복구, macOS 실행은 미입증입니다.**
자동 전체 대화 업로드·외부 모델 호출·기존 Native DB 변환을 수행하는 도구는 포함하지 않습니다.
