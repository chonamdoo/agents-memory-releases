# Claude · Codex · OMP용 로컬 MCP 설치

MCP 연결 앱은 **Claude Code / Codex / OMP(오마이파이)** 중 선택합니다. 여러 앱이 같은 프로젝트의 로컬 기억을 공유할 수 있습니다. 기억 저장 여부를 판단하는 모델은 별도로 **Jev / 구독 Claude / 구독 Codex** 중 선택합니다. MCP 앱 선택으로 판단 모델을 바꾸지 않습니다.

이번 1.0.3은 설치·연결 배포판입니다. 검증된 1.0.2 컴파일 코어와 검색용 E5 임베딩을 그대로 사용하며, 생성 LLM 가중치는 설치하지 않습니다.

## 먼저 준비할 것

- Apple Silicon macOS 13 이상
- 실행 중인 Docker Desktop. 도우미가 전용 PostgreSQL 18 + pgvector 컨테이너·영구 볼륨을 만듭니다. 이미지의 arm64/amd64 다중 아키텍처 digest를 고정했습니다. Docker가 없거나 시작되지 않았으면 중단하고 안내합니다.
- 기존 로컬 PostgreSQL을 사용하려면 새 전용 DB를 먼저 준비하고 `DATABASE_URL`을 안전한 로컬 환경에 설정합니다. 원격 DB·기본 postgres/template DB는 거부합니다. 도우미는 지정한 DB에 Hindsight 스키마를 준비하므로 기존 업무 DB를 지정하지 마세요.
- 구독 판단 모델을 선택한다면 해당 Claude/Codex CLI 설치와 기존 정상 로그인

Docker Desktop 자체나 구독 CLI를 임의로 설치하거나 로그인하지 않습니다. 클라우드 자원은 만들지 않습니다.

## Claude Code 마켓 설치

Claude Code에서:

```text
/plugin marketplace add chonamdoo/agents-memory-releases
/plugin install agents-memory-local@agents-memory
/agents-memory-local:setup
```

설정 후 MCP를 다시 연결하거나 Claude Code를 재시작합니다. 앱이 프로젝트 신뢰·MCP 실행 승인을 요구하면 해당 앱에서 확인합니다. 설치기가 신뢰 설정을 강제로 승인하지 않습니다.

이것은 운영자의 **자체 마켓 배포**입니다. Anthropic 공식 디렉터리 등재를 뜻하지 않습니다. 기존 `agents-memory` 플러그인은 이전 Native 프리뷰이며, 최신 로컬 버전은 `agents-memory-local`입니다. 두 제품을 같은 기억 연결로 중복 등록하지 마세요.

## Codex / OMP / Claude 공통 설치 도우미

설치하려는 프로젝트의 터미널에서 실행합니다. Codex 예시:

```sh
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.3/distribution/mcp-local/install.sh \
  -o /tmp/agents-memory-mcp-install.sh
bash /tmp/agents-memory-mcp-install.sh --client codex --project "$PWD"
```

OMP는 `--client omp`, 직접 Claude MCP 등록은 `--client claude`를 사용합니다. 마켓 플러그인으로 Claude를 연결했다면 별도 `--client claude`를 추가하지 말고 setup 스킬을 사용하세요. 첫 단계에서 원하는 앱과 판단 경로를 선택하고 추천 모델을 확인합니다. Jev 키는 터미널 숨김 입력으로 받으며 채팅·명령 인자에 넣지 않습니다.

여러 앱을 한 번에 연결하려면:

```sh
bash /tmp/agents-memory-mcp-install.sh \
  --client claude --client codex --client omp --project "$PWD"
```

마켓 플러그인은 기본 설치 경로를 사용합니다. 사용자 지정 경로가 필요하면 공통 도우미의 `--prefix /absolute/private/path`와 앱별 직접 MCP 등록을 사용하세요.

실제 등록 위치는 프로젝트 `.mcp.json`(Claude), `.codex/config.toml`(Codex), `.omp/mcp.json`(OMP)입니다. 다른 MCP·모델 설정을 보존하고 기존 파일을 0600 백업으로 남깁니다. 같은 이름의 다른 서버, 명시적으로 비활성화한 항목, 손상된 설정이나 심볼릭 링크가 있으면 덮어쓰지 않고 중단합니다. Codex/Claude의 프로젝트 신뢰와 승인 정책을 존중합니다. OMP에서 프로젝트 MCP 읽기를 꺼 놓았다면 OMP 설정에서 직접 활성화해야 합니다. OMP 프로필별 사용자 설정은 변경하지 않습니다.

기본 경로의 마켓·앱별 등록은 같은 실행 명령을 사용해 OMP의 동일 연결 중복 제거가 작동하도록 합니다. OMP의 기본 xdev 도구 표시 방식에서는 도구가 마운트되어 평면 목록에 보이지 않을 수 있습니다. `/mcp list`, `/mcp test agents-memory-local`로 연결을 확인하세요.

## 설치 후 운영

```sh
AM="$HOME/.local/share/agents-memory-hindsight/bin/am-mcp"
"$AM" status
"$AM" stop
"$AM" start
# 다른 앱을 같은 준비된 프로젝트에 추가 (코어 재다운로드 없이):
"$AM" setup --client omp --project "$PWD"
```

macOS 사용자 LaunchAgent가 API 실행과 재로그인 후 재시작을 관리합니다. DB는 설치 ID가 붙은 전용 Docker 컨테이너와 영구 볼륨을 사용하고 127.0.0.1에만 연결합니다. 다른 컨테이너·볼륨·서비스를 채택하거나 삭제하지 않습니다. Docker가 시작되지 않았다면 Docker Desktop을 시작한 뒤 `start`를 실행하세요. `stop`은 명시적 중지 상태를 남기며 MCP 연결이 임의로 재시작하지 않습니다.

이미 준비된 같은 프로젝트에 앱을 추가할 때는 실행 중인 API를 재사용합니다. 새 프로젝트 준비·도우미 업데이트가 서비스 재시작을 요구하면 연결 중인 MCP를 다시 연결해야 할 수 있습니다. DB 스키마는 애플리케이션 롤백으로 되돌리지 않습니다.

provider·모델·Jev 키·DB 연결·프로젝트 큐는 플러그인 캐시와 버전 디렉터리 밖에 유지합니다. Jev 백그라운드 서비스는 저장된 0600 키 파일을 사용합니다. 환경 변수로만 제공한 키는 LaunchAgent에 복사하지 않으므로, 이 경우 `am-hindsight configure --jev-key`로 터미널에서 저장해야 합니다. 키는 Keychain 암호화 저장이 아닌 사용자 전용 파일입니다. 표준 proxy/CA와 PATH는 서비스의 비공개 설정에 유지하며 구독 토큰이나 API 키를 plist로 복사하지 않습니다.

이 도우미는 이력 스캔·자동 프롬프트 수집·문맥 주입을 활성화하지 않습니다. 설치 자체에서 판단 LLM을 호출하지 않으며 실제 기억 저장 시 선택 모델의 사용량이 발생할 수 있습니다. 로컬 MCP는 같은 사용자 계정의 도구 연결을 위한 것이며 프로젝트 bank를 사용자별 권한 격리로 보장하지 않습니다.

## 업데이트와 검증 범위

마켓은 `/plugin update agents-memory-local@agents-memory` 후 setup 스킬을 다시 실행합니다. 도우미 배포판은 새 버전의 설치 명령을 실행합니다. 기존 provider/모델 변경은 `am-hindsight configure`로만 명시합니다. 알 수 없는 최신 코어를 이전 버전으로 자동 내리지 않습니다. 플러그인 제거·서비스 중지·업데이트로 DB 볼륨을 자동 삭제하지 않습니다.

Linux `--virtual-linux --no-start`는 검증 전용입니다. Linux 검증에서는 테스트 하네스가 `service-run` 수명을 소유합니다. macOS LaunchAgent의 구조와 수명 제어는 검사하지만 macOS 실기 실행을 했다고 주장하지 않습니다. 코어 바이너리는 ad hoc 서명이며 Developer ID/공증 상태는 1.0.2와 같습니다.
