# 새 독립 AI 평가 사전 등록과 실제 CLI 검증

[ANNOTATION-PREFLIGHT.json](ANNOTATION-PREFLIGHT.json)은 새196건·40질문과 각7840관련성 쌍을 두 독립 AI가 검토한 결과다. 분류·관련성 κ=1.00, 질문 변경0건, 직접 작성한 사전 승인 확인. 실제 제품 평가는 아직 실행 전이다. 원문·원시 라벨은 승인받은 비공개 Core PR75에 고정했고 이곳에는 해시와 범위만 공개한다.

[REFERENCE-AUTHORIZATION.json](REFERENCE-AUTHORIZATION.json)은 사용자 승인 예외를 특정한다. 과거 원본6개는 미검증이며 전체 과거 비중복 통과를 주장하지 않는다. 확보된528참조에서는 정확히 같은 텍스트0건이다. 다른 품질·안전·자원·호출 기준과 소진 이력은 유지한다.

[REAL-CODEX.json](REAL-CODEX.json)은 공식 Codex0.167.0과 실제 gpt-6.1-sol의 원래36사례 결과다. 전체 사실·새 marker72개, 실제 compact36회를 확인했다. 최종 설치 SDK14ba/CoreCP312bb,2CPU·4GiB·swap0·OOM0이며 합성 기억 backend의 앱 구성요소 검증이다. 실제 통합 저장/검색 품질이나 Claude·OMP 공급자 검증을 대신하지 않는다. 이전 인증·관측기 실패와112새 native operation(실패 run4 포함), 이전 pilot5를 보존한다. 내부 HTTP 재시도·비용은 알 수 없으며0으로 세지 않는다. Jev호출0회다.

정식 배포는 아직 대기 중이다. [전체 조건](../v2.0.0-stable/CONDITIONS.ko.md)을 모두 충족한 뒤 게시한다.

[OFFLINE-FAULTS.json](OFFLINE-FAULTS.json)은 최종 SDK wheel의 임시 복사본에 원래4종 결함과 도구origin/빈회상 범위 결함을 실제로 넣어 해당 소비자 계약이 깨지는지 확인한 결과다. 깨끗한6개 기준은 모두 통과했고6개 변이는 모두 탐지했다. 소켓 연결을 차단한 오프라인 검사이며 실제 Native/DB/공급자 품질의 증거가 아니다.

## 실제 전송 계측 준비

[Linux 비유료 사전 검사](LINUX-ZERO-PAID-PREFLIGHT.json)는 최종 source-free Core·SDK로 새PG/Native/E5/BGE와196/40/49pins를 검증했다.2CPU/4GiB/swap0/OOM0이며 새 자료의 실제 저장·회상은 실행하지 않았다. 승인 없는 --execute는 일회성 자료를 소진하기 전에 거부하도록 Core PR76 리뷰도 수정했다.

[Codex](CODEX-ACCOUNTED-PREPARATION.json)36/36·108전송, [Claude](CLAUDE-ACCOUNTED-PREPARATION.json)36/36·144전송은 로컬 가짜 공급자로 검증한 새 계측 경로다. 실제 공급자 성공이 아니다. 각 경로는 network-none native→UDS→단일 upstream relay로 전송을 강제하며 합계2CPU/4GiB hardlimit를 지킨다.

[과거 호출 수의 한계](PAST-CALL-COUNT-LIMITATIONS.json)를 명시한다. 이전 Codex117native 작업과 OMP3fetch 진입 기록으로 실제 wire HTTP/재시도 상한을 복구할 수 없다. 초과 과금이나 상한 준수를 단정하지 않고 미검증으로 남긴다. 이를0으로 리셋하거나 새 호출 승인으로 사용하지 않는다. 전체 정식 배포는 실제 새 평가와 검증 완료 후 진행한다.

[OMP 계측 준비](OMP-ACCOUNTED-PREPARATION.json)도 원래36사례·144개 로컬 전송을 통과했다. 이후 근거 없는 optional orgId 메타데이터만 제거했고 최종 코드로1사례·4전송을 추가 확인했다. 실제 native soft 압축의 두 요약 요청과 resume hook을 확인했으며, 과거 remoteV2 HTTP400은 해결된 것으로 바꾸지 않는다. 실제 공급자·OAuth 호환성은 미검증이다.

[다음 실제 호출 계획](FUTURE-CALL-PLAN.json)은 **미승인 제안**이다. 새 계측 경로에서 앞으로 최대1000회, Jev582·Codex150·Claude150·OMP147의 하위 상한을 함께 적용하며 전체1000이 우선한다. 기존 Jev 누적1000·이미418예약·독립 코호트197 한도는 유지한다. 실패·중단·재시도도 차감하고 과거 알 수 없는 호출을0으로 재설정하지 않는다. 과거 전체 잔여량이나 상한 준수를 입증하는 문서가 아니며 비용 금액 상한을 보장하지 않는다. 실제 승인 후 새196/40의 품질 평가부터 실행한다.
