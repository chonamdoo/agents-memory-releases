# 새 독립 AI 평가 사전 등록과 실제 CLI 검증

[ANNOTATION-PREFLIGHT.json](ANNOTATION-PREFLIGHT.json)은 새196건·40질문과 각7840관련성 쌍을 두 독립 AI가 검토한 결과다. 분류·관련성 κ=1.00, 질문 변경0건, 직접 작성한 사전 승인 확인. 실제 제품 평가는 아직 실행 전이다. 원문·원시 라벨은 승인받은 비공개 Core PR75에 고정했고 이곳에는 해시와 범위만 공개한다.

[REFERENCE-AUTHORIZATION.json](REFERENCE-AUTHORIZATION.json)은 사용자 승인 예외를 특정한다. 과거 원본6개는 미검증이며 전체 과거 비중복 통과를 주장하지 않는다. 확보된528참조에서는 정확히 같은 텍스트0건이다. 다른 품질·안전·자원·호출 기준과 소진 이력은 유지한다.

[REAL-CODEX.json](REAL-CODEX.json)은 공식 Codex0.167.0과 실제 gpt-6.1-sol의 원래36사례 결과다. 전체 사실·새 marker72개, 실제 compact36회를 확인했다. 최종 설치 SDK14ba/CoreCP312bb,2CPU·4GiB·swap0·OOM0이며 합성 기억 backend의 앱 구성요소 검증이다. 실제 통합 저장/검색 품질이나 Claude·OMP 공급자 검증을 대신하지 않는다. 이전 인증·관측기 실패와112새 native operation(실패 run4 포함), 이전 pilot5를 보존한다. 내부 HTTP 재시도·비용은 알 수 없으며0으로 세지 않는다. Jev호출0회다.

정식 배포는 아직 대기 중이다. [전체 조건](../v2.0.0-stable/CONDITIONS.ko.md)을 모두 충족한 뒤 게시한다.

[OFFLINE-FAULTS.json](OFFLINE-FAULTS.json)은 최종 SDK wheel의 임시 복사본에 원래4종 결함과 도구origin/빈회상 범위 결함을 실제로 넣어 해당 소비자 계약이 깨지는지 확인한 결과다. 깨끗한6개 기준은 모두 통과했고6개 변이는 모두 탐지했다. 소켓 연결을 차단한 오프라인 검사이며 실제 Native/DB/공급자 품질의 증거가 아니다.
