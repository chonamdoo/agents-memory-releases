# agents-memory 공통 MCP — 1.0.8

로컬·개인 서버·팀 서버·회사 서버에서 같은 Hindsight 엔진과 처리 단계를 사용합니다.
이번 배포는 **정식 v1.0.8**입니다. Linux x64에서 실제 설치·업데이트·공급자 실호출을
검증하며, Apple Silicon Mac 설치는 공개 패키지로 사용자 확인이 남아 있습니다.
Mac 실기기 검증은 사용자가 진행합니다. 기존 사용자 DB의 자동 이전·재처리는 하지 않습니다.

## 로컬 설치: Claude·Codex·OMP

실제 작업 프로젝트 폴더에서 실행하세요. Docker는 필요 없습니다. PostgreSQL·pgvector,
고정 Python·Hindsight·E5 검색 임베딩과 공통 코어를 준비합니다. 별도 생성 모델 가중치는 받지 않습니다.

```bash
curl -fLSs https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.8/distribution/server/install-unified.sh -o /tmp/agents-memory-install.sh
bash /tmp/agents-memory-install.sh --mode local --client all --project "$PWD"
```

기억 공급자를 **Claude CLI / Codex CLI / Jev 중 하나** 선택합니다. Claude·Codex는 이
기억 엔진 호스트에서 먼저 구독 로그인하세요. Jev 키는 터미널 숨김 입력 후 Enter로
확정합니다. 키를 채팅에 보내지 마세요. 처리 단계와 진행 메시지가 표시됩니다.
업데이트 때 같은 명령을 사용하면 저장된 공급자·모델·키·DB·기기 연결을 보존합니다.

개별 연결은 `--client claude`, `--client codex`, `--client omp`입니다.
OMP는 기억 공급자가 아닌 MCP 연결 대상입니다. `--client all`은 세 앱을 등록합니다.
기존 MCP·훅 설정이 충돌하면 덮어쓰지 않고 중단하므로 메시지와 백업을 확인하세요.

- Claude: 프로젝트 `.mcp.json`과 `.claude/settings.local.json`을 사용합니다.
- Codex: `.codex/config.toml`과 `.codex/hooks.json`을 사용합니다.
- OMP: `.omp/mcp.json`과 `.omp/extensions/agents-memory-cloud.ts`를 사용합니다.

설치 후 앱을 다시 열고 `agents-memory-cloud`의 `setup_status`를 확인하세요.
`ready`뿐 아니라 `server_ready`와 미전송·충돌 상태를 함께 봅니다. 준비 중 MCP 초기화는
응답하며 메모리 준비 전 저장을 완료했다고 표시하지 않습니다. 로컬 서비스와 native DB는
MCP 연결 시 다시 시작됩니다. OS 로그인 서비스는 임의로 등록하지 않습니다.

최초 프로젝트·훅 신뢰와 OMP 확장 활성화는 각 앱의 정책을 따릅니다. 자동 후보 저장·회상은
사용자 입력/세션 이벤트와 MCP 백그라운드 작업으로 연결되며, 도구 자동 승인만으로
동작한다고 주장하지 않습니다. 저장마다 별도 승인을 받는 흐름을 기본값으로 강제하지 않습니다.
복구·충돌 해결처럼 데이터에 영향을 주는 관리 도구는 일상 도구와 구분해 검토하세요.

## Claude·OMP 마켓플레이스

기존 `agents-memory-local`을 1.0.8로 업데이트하면 공통 엔진에 연결합니다.
`agents-memory-unified`는 같은 엔진의 별도 이름이므로 둘을 같은 프로젝트에 중복 등록하지 마세요. 연결 전에 공급자 선택이 필요하면 `setup_status`에서 안내합니다.

```bash
claude plugin marketplace add chonamdoo/agents-memory-releases
claude plugin install agents-memory-local@agents-memory
# 같은 설치 명령에서 --client claude-plugin을 사용: 직접 MCP 중복 등록 없이 훅 연결

omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
# 같은 설치 명령에서 --client omp-plugin을 사용
```

Codex는 위 설치기의 `--client codex`를 사용합니다. 다른 앱의 플러그인 명령을
Codex에서 실행하지 않습니다. 플러그인 캐시 밖에 키·DB·설정을 저장합니다.

## 개인·팀·회사 서버

엔진을 설치할 서버에서 `--mode personal-server`, `team-server`, `company-server`를
선택합니다. **세 공급자 중 선택한 하나는 서버에서 실행**됩니다. PC의 구독 인증을
서버로 복사하지 않습니다. 공급자 장애를 원문 저장으로 우회하지 않습니다.
기본 API는 loopback입니다. 직접 인터넷에 DB/Hindsight 포트를 열지 마세요.
개인 시험은 SSH/IAP 터널, 공용 접속은 HTTPS 역방향 프록시와 공개 URL을 준비합니다.
모드 이름만으로 SSO·SCIM·회사 보안 인증을 제공한다는 뜻은 아닙니다.

다른 PC에는 DB·Jev 키가 필요 없습니다. 같은 설치 파일에서 클라이언트만 설치합니다.

```bash
bash /tmp/agents-memory-install.sh --connect-server --client all --project "$PWD" --profile personal --url https://YOUR_GATEWAY
```

키는 터미널에서 숨김 입력합니다. 관리자가 발급한 자기 계정의 기기 키를 사용하세요.
프로필은 서버·계정에 묶입니다. 대상이 다르면 새 프로필을 만들며 대기 전송함을 다른
서버로 몰래 보내지 않습니다. 별도 서버 연결과 로컬 설치를 동시에 중복 등록하지 마세요.
서버 재부팅 후 시작은 운영자가 서비스 사용자로 `unified_setup.py ensure`를 실행하거나
[런타임 안내](UNIFIED-RUNTIME.ko.md)의 user systemd 서비스를 설정해야 합니다.

## 계약·검증·제한

- [공급자별 통합·출처·수정·삭제 계약](GENERATION-CONTRACT.ko.md)
- [런타임·실행 위치·이전·복구 안내](UNIFIED-RUNTIME.ko.md)
- [초기 근거 구간 처리 계약](MEMORY-CONTRACT.md)
- [이전 0.2.1 안내](README-0.2.1.ko.md) — 이번 엔진의 설치 방법이 아닙니다.

기본 설치 위치는 `~/.local/share/agents-memory-unified`입니다. 이전 설치 데이터는
자동 가져오기·재분류·삭제하지 않습니다. 현재 프롬프트 후보를 수집하며 모든 대화 이력·
도구 출력의 자동 수집을 주장하지 않습니다. 서버 운영자는 원문을 읽을 수 있습니다.
개인 기억은 공유 매핑을 설정하기 전 팀에 공개되지 않습니다. 검색 제외·삭제 전파와
백업/과거 로그의 원문 파기는 별개의 정책입니다. E2EE 서비스가 아닙니다.

엔진 번들은 Apple Silicon macOS 15+ 및 glibc Linux x64용입니다. Windows는 WSL2 x64
Linux 홈에 설치하는 경로이며 native Windows는 지원 검증되지 않았습니다. thin 원격
클라이언트는 macOS x64·arm64, glibc Linux x64·arm64용입니다. 실제 실행한 플랫폼과
미검증 플랫폼을 릴리즈 검증 보고서에서 구분합니다. 바이트코드 코어는 원본 Python 소스를
배포하지 않지만 암호화·역공학 방지를 보장하지 않습니다.
