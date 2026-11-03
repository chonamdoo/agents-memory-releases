# agents-memory Hindsight local 1.0.1

Apple Silicon Mac(macOS 13 이상)에서 Hindsight를 로컬 기억 저장소로 실행합니다.
설치 시 **Jev / 구독 LLM(Claude / Codex)** 중 하나를 선택합니다. Jev를 선택하면 API 키를
화면에 표시하지 않는 입력창으로 받고 사용자 전용 파일에 저장합니다. 배포 위치는 로컬로
고정되어 있으며 업데이트는 provider·모델·프로젝트 outbox를 유지합니다. 로컬 LLM은
다운로드한 모델이 아니라 기존 구독 계정으로 로그인한 Claude 또는 Codex CLI입니다. 자동 대체 경로는 없습니다.

## 설치

GitHub `chonamdoo/agents-memory-releases`의 정식 `v1.0.1` 배포물은 전송을 위해 19개 조각으로
제공합니다. 아래 명령은 조각과 합친 압축 파일의 SHA256을 모두 검사한 뒤 설치합니다. Source code 자동 압축 파일은
실행 제품이 아닙니다. 기존 Native 프리뷰 설치와 DB를 자동 변환하거나 덮어쓰지 않습니다.

```sh
(
  set -eu
  am_install_dir=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-install.XXXXXXXX")
  cd "$am_install_dir"
  am_release=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/release-assets-v1.0.1/files
  curl --fail --location --output SHA256SUMS "$am_release/SHA256SUMS"
  curl --fail --location --output PARTS-SHA256SUMS "$am_release/PARTS-SHA256SUMS"
  am_part=0
  while [ "$am_part" -lt 19 ]; do
    am_name=agents-memory-hindsight-local-1.0.1.tar.gz.part-$(printf '%03d' "$am_part")
    curl --fail --location --output "$am_name" "$am_release/$am_name"
    am_part=$((am_part + 1))
  done
  shasum -a 256 -c PARTS-SHA256SUMS
  cat agents-memory-hindsight-local-1.0.1.tar.gz.part-* > agents-memory-hindsight-local-1.0.1.tar.gz
  shasum -a 256 -c SHA256SUMS
  tar -xzf agents-memory-hindsight-local-1.0.1.tar.gz
  cd agents-memory-hindsight-local-1.0.1
  ./install.sh
)
```

기본 설치 위치는 `~/.local/share/agents-memory-hindsight`입니다. Python 3.13.18과
고정 E5 ONNX 모델을 포함합니다. Python을 별도 설치할 필요는 없습니다. Hindsight 1.1.0과
의존성은 hash가 고정된 lock 파일을 통해 PyPI에서 내려받으므로 첫 설치에 인터넷과
충분한 디스크 공간이 필요합니다. 추가 설치 옵션은 `./install.sh --help`로 확인하세요.

```sh
# 대화형 질문 대신 명시적으로 선택할 때
./install.sh --provider jev
# 또는
./install.sh --provider local-llm --codex /absolute/path/to/codex
```

같은 계정·prefix에 새 배포물을 설치할 때는 `./install.sh`만 실행합니다. 기존 설정이 있으면
provider를 다시 묻지 않습니다. 업데이트 중 오류가 나면 활성 버전은 유지됩니다.
동시에 여러 설치/롤백을 실행하지 마세요. 실행 중인 API와 drain은 업데이트 전에 종료하고
업데이트 후 다시 실행하세요. 자동 background 서비스·자동 host 설정·DB 마이그레이션 롤백은 제공하지 않습니다.

```sh
AM="$HOME/.local/share/agents-memory-hindsight/current/bin/am-hindsight"
"$AM" --version
"$AM" profile
# 명시적으로 provider/모델을 바꿀 때만
"$AM" configure --provider local-llm --host codex --executable /absolute/path/to/codex --model gpt-6.1-terra
# 마지막 설치 직전의 애플리케이션 파일로 복구 (DB·설정·outbox 유지)
"$AM" rollback
```

## 로컬 DB와 계정 준비

별도 관리하는 **PostgreSQL 18.x + pgvector 0.8.7 이상**에 새 전용 DB를 먼저 만드세요.
`DATABASE_URL`은 기존 업무 DB나 기본 postgres DB가 아닌, 127.0.0.1/localhost의 새 전용 DB를
가리켜야 합니다. 서버 시작 시 Hindsight가 스키마를 생성/마이그레이션합니다. 이 설치기는
DB·Docker·클라우드 자원을 생성하지 않습니다. 기존 DB와 backup을 별도 보관하세요.

Jev 첫 설치에서는 API 키를 숨김 입력으로 받습니다. 키는 설치 버전 디렉터리 밖의
`settings/jev-credential.json`에 사용자만 읽고 쓸 수 있는 권한(0600)으로 저장하며, 업데이트와
rollback에서 유지합니다. 이 파일은 암호화된 Keychain 저장소는 아닙니다. 프로필 출력·로그·
명령 인자·프로젝트 본문에는 키를 넣지 않습니다. 교체할 때는 아래 명령을 실행하면 다시 숨김 입력을 받습니다.

```sh
"$AM" configure --jev-key
```

명시적으로 설정한 `HINDSIGHT_API_MEMORY_ADMISSION_API_KEY` 환경 변수가 있으면 저장한 파일보다
우선합니다. 비대화형 설치는 이 환경 변수로 키를 제공해야 하며, 환경 변수 값은 파일로 복사하지 않습니다.
구독 Claude/Codex는 Jev 키를 묻지 않고 기존 CLI의 정상 로그인 상태를 사용하며
인증 파일을 복사하거나 읽어 표시하지 않습니다. API key/대체 endpoint와 구독 인증이
충돌하면 안전하게 중지합니다. 회사 정책상 허용된 계정과 데이터만 사용하세요.

```sh
# DATABASE_URL과 선택한 provider의 인증은 자신의 로컬 보안 환경에서 설정한 뒤
"$AM" project-init /absolute/path/to/project
"$AM" serve --check --bank project-BANK_ID_FROM_PROJECT_INIT
"$AM" bank-init --config /absolute/path/from-project-init/hook.json
"$AM" serve --bank project-BANK_ID_FROM_PROJECT_INIT
```

`--check`는 설정·파일·포트 검사이며 실제 DB 연결/로그인 확인은 아닙니다.
API는 127.0.0.1:18250, 보조 포트는 18251만 사용합니다. 외부 공개·멀티유저 서버는
지원하지 않습니다. 프로젝트 bank 분리는 라우팅이며 사용자별 접근권한 격리가 아닙니다.

## 프로젝트 연결과 비동기 저장

API 시작 전에 `project-init`이 출력한 hook config로 `bank-init`을 실행해 로컬 DB에
privacy screening을 설정하세요. DB 연결과 초기화는 명시적인 이 명령에서만 수행하며,
HTTP 설정 변경 차단은 유지합니다. API 실행 후 별도 터미널에서 drainer를 실행하세요.
**capture 훅에서는 LLM·DB·네트워크·drainer lock을 기다리지 않습니다.**
64 KiB 이하의 입력을 private local outbox에 기록한 뒤 반환하고, drainer가 별도 프로세스에서
Hindsight로 보냅니다. Hindsight 내부에서 Jev/Claude/Codex가 keep/discard/review를 판단합니다.

```sh
"$AM" hook drain --config /absolute/path/from-project-init/hook.json --run
"$AM" hook status --config /absolute/path/from-project-init/hook.json
```

`project-init`이 출력한 `capture_command`를 host의 **UserPromptSubmit JSON(stdin의 prompt)**
명령 훅에 연결하고, `mcp_url`을 Codex의 HTTP MCP로 등록하세요. 기존 Codex 설정 파일은
자동 수정하지 않습니다. 실제 host 버전의 hook 지원/프로토콜은 별도로 확인해야 하며,
지원하지 않는 버전에서는 자동 prompt 수집을 주장하지 않습니다. MCP 수동 기억 경로도 사용할 수 있습니다.
capture는 prompt를 메모리에만 전달한 host 이벤트를 받도록 하고 키·인증 토큰을 입력하지 마세요.

review/실패는 보류하며 성공으로 승격하지 않습니다. 큐가 가득 차거나 64 KiB를 넘으면
조용히 거부하고 원문을 자르지 않습니다. ACK 유실 시 중복 저장 가능성이 있는 at-least-once
전송입니다. 자동 중복 제거·원자적 문서 교체는 보장하지 않습니다. 긴 원문은 공식 Hindsight가
여러 document ID로 나눌 수 있어, 수정·삭제 시 관련 ID 전부를 확인해 처리해야 합니다.

## 제공 범위와 검증

공식 Hindsight chunks + multilingual-E5-small(384차원) + RRF를 사용합니다. 현재 작업 LLM이
회상과 원문을 읽어 답변합니다. 자동 관찰 통합·Reflect·mental model 생성·원격 클라우드·
Native 프리뷰 전체 CLI는 이번 제품 범위에 포함하지 않습니다. Linux 구성은 동일 배포물의
`--virtual-linux` 검증용이며 Linux/cloud 운영 지원을 뜻하지 않습니다.

출시 기준은 가상 검증 100/100이며 실제 Mac·Jev/Claude/Codex 계정·지연·품질 QA는 출시 뒤
별도 표로 계속 측정합니다. 이 점수는 모델 정확도나 SOTA 달성률이 아닙니다.
Mac 바이너리는 ARM64/ABI/서명 구조를 정적으로 검사하며 이 클라우드에서 실행하지 못합니다.
개발자 ID 서명/Apple 공증은 없고 ad hoc 서명입니다. Gatekeeper/격리 속성을 자동 해제하지 않습니다.

자체 구현은 binary extension으로 제공하며 private Python 소스·bytecode·생성 C는 포함하지
않습니다. 공개 installer/entry wrapper와 MIT Hindsight 코드는 포함됩니다. 바이너리 역분석이
불가능하다는 뜻은 아닙니다. `licenses/`, `SBOM.json`, `BUILD.json`, `MANIFEST.json`에
출처·hash·라이선스와 배포 범위를 기록했습니다. 외부 의존성은 원래 라이선스 그대로 설치됩니다.

1.0.1 설치 변경: 첫 설치에서 Jev / 구독 LLM을 선택하고, 구독 LLM이면 Claude / Codex를 선택합니다. 추천 모델은 Claude Sonnet 5.5 / GPT-6.1 Terra입니다. 기존 설치 업데이트에서는 provider·CLI·모델·Jev 키·프로젝트와 outbox를 유지합니다. 키 교체는 am-hindsight configure --jev-key로 명시합니다.
자체 컴파일 코어는 1.0.0과 동일하며 공개 wrapper/installer를 갱신한 버전입니다. 실제 Mac 실행 검증은 이번에도 수행하지 않았습니다. Actions는 실행하지 않았습니다.

Claude 명시 변경: am-hindsight configure --provider local-llm --host claude --executable /absolute/path/to/claude --model claude-sonnet-5-5
