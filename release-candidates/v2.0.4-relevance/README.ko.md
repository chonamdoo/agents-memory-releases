# MCP 2.0.4 검증 결과와 설치

출시 필수 검증을 완료했습니다. 게시 여부는 [전체 출시 판정](../v2.0.0-stable/STATUS.json)의 `stable_published`와 [최신 정식 릴리즈](https://github.com/chonamdoo/agents-memory-releases/releases/latest)를 확인하세요. MCP 패키지2.0.4, 엔진·SDK ABI2.0.0이며 정확한 바이트는 [CANDIDATE.json](CANDIDATE.json)과 [SHA256SUMS](SHA256SUMS)에 고정합니다.

[공통 설치 안내](../../distribution/server/README.ko.md#로컬-설치-claudecodexomp)를 따라 고정 v17 번들·모델·Jev 키를 준비하고 Claude·Codex·OMP 마켓에서 `agents-memory-unified@agents-memory`를 설치하세요. Codex는 설치된 setup skill로 프로젝트 stdio MCP를 등록해야 합니다.

새 독립 AI 두 명이 사전 검토한196건·40질문 실제 통합 평가는 명시 저장80/80·자동39/40·Hit@5 40/40·필수 근거 전체39/40·잡음0/119입니다. 원래 분모·Wilson 기준을 통과했으며 자동 저장 누락1건은 보존합니다. [결과·한계](live-quality-v2/README.ko.md)를 확인하세요. SDK는 Native 지명 뒤 승인 원문의 명시 주제를 확인하고, 불명확하면 기존 semantic 결과를 유지합니다. 상위3개 고정·골드목록·주제 하드코딩이나 Native0.003 floor 변경은 없습니다.

실제 앱별36/36의 시작·재개·압축 후 복원 검증도 각각 통과했습니다: [Claude](native-live-r4/claude/SAFE-PUBLIC-PROJECTION.json), [Codex](native-live-r8/codex/SAFE-PUBLIC-PROJECTION.json), [OMP](native-live-r8/omp/SAFE-PUBLIC-PROJECTION.json). 기억 backend는 고정 합성 fixture이며 위 실제 통합 품질 평가와 구분합니다. OMP는 공식 soft 압축(keepRecentTokens20000·padding3회) 범위입니다. 과거 기본 remoteV2 HTTP400 원인은 미확인입니다. [최종 호출 기록](native-live-r8/FINAL-BUDGET.json)은 실패·중단·메타데이터도 포함하며 승인된 전체·공급자별 상한을 지켰습니다.

검증 환경은 Ubuntu24.04·Linux x86_64·glibc2.39·Python3.12/3.13입니다. macOS는 사용자 별도 시험이며 검증 완료를 주장하지 않습니다. 중앙 MCP 디렉터리 등재는 별도이며 이 배포는 관리자의 공개 GitHub 마켓입니다.

앞선 v2.0.3 독립 평가 잡음80/200과 Native 실행 실패를 보존합니다. 과거 원본6개 대조·과거 Native HTTP 횟수·최초 대화형 신뢰·일반 구독 권한·생성 답변 품질은 미확인입니다. strict 통합 보고서 UNKNOWN은 그대로이며 이 문서는 별도로 확보한 필수 구성요소 증거를 합쳐 판정합니다. 새 결과로 과거 실패를 덮거나 실제 사용자 모집단 성능을 주장하지 않습니다.
