# v1.0.5 — MCP 연결 시 자동 설치와 네이티브 로컬 DB

초기 키 입력 뒤 설치가 멈춘 것처럼 보이고 Docker·Colima 설정 때문에 DB 준비가 실패하던 흐름을 바꿨습니다. 새 설치는 플러그인의 MCP 연결만으로 실행 환경·E5 검색 임베딩·전용 PostgreSQL/pgvector·API를 자동 준비합니다.

- 처음 한 번 브라우저에서 Jev / 구독 Claude / 구독 Codex를 선택합니다. Jev 키는 이 PC의 설정 페이지에서 입력하고 0600 파일로 보관합니다. 추천 모델은 Sonnet 5.5 / Codex 6.1 Terra입니다.
- 기존 모델·키·기억 데이터를 업데이트 후에도 유지합니다. OMP는 MCP 연결 대상이며 판단 제공자는 기존 세 가지입니다.
- `setup_status`가 설치 단계와 오류를 안내합니다. 도구 목록을 처음부터 제공해 목록을 캐시하는 앱도 지원하며, 기억 호출은 실제 API 준비가 끝나야 실행됩니다. 설치 후 수동 MCP 재연결이 필요하지 않습니다.
- 신규 DB는 Docker 없이 로컬 프로세스로 실행됩니다. PostgreSQL 18.6·pgvector 0.8.7을 고정하고 127.0.0.1에만 바인딩합니다. 생성 LLM 가중치는 설치하지 않으며 검색용 다국어 E5는 포함됩니다.
- 설치·연결 중에는 판단 모델을 호출하거나 과거 대화를 읽지 않습니다. 명시적 서비스 중지를 존중합니다. 다른 Docker 컨텍스트·Colima 프로필을 변경하지 않습니다.
- 실제 저장 프로필에서 지원하지 않는 문서/전략 옵션은 도구 스키마에서 제외하고 저장 오류를 오류로 전달합니다.

**새 자동 DB의 지원 대상은 Apple Silicon macOS 15 이상입니다.** 기존 1.0.3/1.0.4 Docker·외부 DB 영수증이 남아 있으면 데이터를 보존하고 기존 연결을 유지하며, 새 빈 DB로 자동 전환하지 않습니다.

OMP 설치:

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
```

Claude Code도 같은 마켓과 `agents-memory-local@agents-memory`를 사용합니다. Codex의 직접 연결은 [공통 안내](../../distribution/mcp-local/README.ko.md)를 따르세요. 앱의 프로젝트 신뢰·MCP 실행 승인은 그대로 적용됩니다.

로컬 검증: Python 72개, Go 7개와 race 검사, 설정/이전 배포 계약·체크섬 검증을 통과했습니다. Docker 없는 새 설치에서 Codex 경로는 약 108초, Jev 경로는 약 82초 만에 같은 MCP 세션에서 준비됐습니다. 실제 Codex 판단을 거친 합성 기억 저장과 E5 검색, Claude 연결 상태, Codex의 실제 MCP 검색 호출, OMP 도구 탐색을 확인했습니다. Jev 키 저장 검증에는 합성 키를 사용했으며 실제 Jev 인증 성공을 뜻하지 않습니다.

macOS 바이너리·DB 아카이브의 형식과 최소 버전은 검사했지만 **macOS 실기 실행은 아직 검증하지 않았습니다.** Developer ID 서명·공증은 아닙니다. 상세 범위는 VERIFICATION.json에 기록했습니다. GitHub Actions는 실행하지 않았으며 2026-12-01까지 실행하지 않습니다.
