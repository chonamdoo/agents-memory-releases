# Agents Memory 2.0.0 배포·중앙 제출 자료

현재 제품 릴리스는 prerelease입니다. 검색 수정은 별도 고정 검증과 SDK 278 통과로 확인됐고 실제 Jev 저장 품질 재검증은 수행하지 않았습니다. 정식 품질 통과나 공식 중앙 디렉터리 등재를 주장하지 않습니다.

## 자체 공개 마켓

저장소: https://github.com/chonamdoo/agents-memory-releases
항목: agents-memory-unified@agents-memory
Claude/OMP: 플러그인 stdio MCP 및 setup 안내.
Codex: 전용 setup skill에서 검증된 런타임 설치기를 실행해 프로젝트 MCP 등록. 마켓 설치 자체는 MCP 연결이 아닙니다.

## 제출 패키지

agents-memory-unified-plugin-2.0.0.zip: 공개 플러그인, 양쪽 manifest, 설치 skill, 아이콘, MIT 고지, 두 대상 connector.
agents-memory-unified-2.0.0-search-calibrated.tar.gz: 검증된 검색 SDK와 기존 source-free Core를 사용한 런타임 후보.
별도 SEARCH-MARKETPLACE-SHA256SUMS 및 SEARCH-MARKETPLACE-SOURCE-VERIFICATION.json을 검증합니다. 모델 companion은 기존 v2.0.0 자산과 동일합니다.

## 중앙 디렉터리

OpenAI: https://platform.openai.com/plugins
로컬 실행 제출 요건: https://developers.openai.com/plugins/deploy/desktop-only
실행이 필요한 skill-only manifest에 requires_local_executor=true를 선언했습니다. 제출 조직의 승인 파트너 자격/허용 목록, 제출 권한과 신원 확인이 필요합니다. 현재 조직 ID와 승인 여부가 제공되지 않아 제출하지 않았습니다. 승인 후 포털에서 검토·게시가 별도입니다.

Anthropic: 자체 Git marketplace 설치·manifest 검증과 실제 연결을 확인했습니다. 중앙 공식 디렉터리 제출·심사 완료를 주장하지 않습니다. 제출 포털에서 개발자 계정과 공개 릴리스 상태를 확인해야 합니다.

## 실제 검증 범위

Linux x86_64에서 Claude Code 2.1.319 설치·MCP health, Codex CLI 0.163.0 마켓 설치·별도 정식 MCP initialize/tools, OMP 18.18.0/Bun 1.4.4 설치·RPC MCP tool discovery를 확인했습니다. 외부 모델 호출 0회입니다. 이 검증은 키 없는 setup_required 연결이며 준비된 Jev 엔진의 실사용 품질 검증은 아닙니다. macOS arm64는 cross compile만 했습니다.
