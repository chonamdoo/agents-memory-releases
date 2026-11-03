# agents-memory Hindsight local v1.0.0

가상 출시 검증 **100/100** 기준의 정식 릴리즈입니다. 배포 저장소는
`chonamdoo/agents-memory-releases`이며 draft/prerelease로 게시하지 않습니다.
실제 환경 검증은 개인 50/100 · 회사 15/100 · 공동 15/100으로 별도 유지합니다.
가상 100점은 모델 답변 정확도나 SOTA 달성률이 아닙니다.

## 포함한 개선

- **로컬 전용 설치:** Jev / 로컬 LLM(구독 중인 Codex) 중 하나를 처음에 선택합니다.
  업데이트에서 provider·모델·프로젝트 설정·outbox를 유지하고, 명시적인 configure만 변경합니다.
- **Hindsight 내부 저장 판단:** 선택한 provider가 keep/discard/review를 판단합니다. 실패·review를
  성공으로 승격하거나 다른 provider로 자동 대체하지 않습니다. chunks·고정 E5 ONNX·RRF를 사용합니다.
- **입력을 기다리게 하지 않는 저장:** 입력 훅은 로컬 private outbox에 기록하고 반환합니다.
  별도 drainer가 전송합니다. 64 KiB까지 원문을 보존하며 초과 입력과 탐지한 고신뢰 인증키는
  잘라 저장하지 않고 거부합니다. 모든 민감정보를 탐지한다는 보장은 아닙니다.
  일반·system·서명형 Hindsight 키가 긴 입력 끝에 들어 있는 경우도 수집 전에 검사합니다.
- **설치 무결성·복구:** 고유 버전 디렉터리의 설치와 import 검사가 끝나야 current 포인터를 바꿉니다.
  직전 애플리케이션 파일로 rollback할 수 있고 설정·DB·outbox는 그대로 둡니다. 손상된 배포물,
  누락된 vendor 파일, 잘못된 소유권·권한, 다른 제품의 디렉터리 채택을 거부합니다.
- **고정 upstream과 초기화:** PyPI의 같은 1.1.0 번호를 검토한 Git 코드와 동일하다고 간주하지 않습니다.
  검토한 전체 vendor 코드·리소스와 컴파일한 guard를 사용합니다. bank privacy 설정은 API 시작 전에
  로컬 DB에서 명시적으로 초기화하고, 서버의 HTTP 설정 변경 차단은 유지합니다.

## 배포물과 설치

지원 대상은 **Apple Silicon Mac / macOS 13 이상 / 로컬 실행**입니다. Python 3.13.18,
고정 E5 자산, 컴파일한 자체 구현과 MIT Hindsight vendor를 포함합니다. 외부 Python 의존성은
고정 hash로 PyPI에서 설치합니다. 첫 설치에는 인터넷과 충분한 디스크 공간이 필요합니다.
PostgreSQL 18.x + pgvector 0.8.7 이상인 새 로컬 전용 DB와 Jev 인증 또는 로그인된 Codex CLI는
별도 준비합니다. 클라우드 배포와 다운로드형 로컬 생성 모델은 이번 범위에 포함하지 않습니다.

Mac 터미널에서 아래 블록을 실행하면 릴리즈 파일과 체크섬을 다운로드하고 검증한 뒤 설치합니다.
처음에 Jev / 로컬 LLM(구독 중인 Codex)을 선택합니다. 업데이트할 때 같은 명령을 다시
실행하면 provider·모델·프로젝트 설정·outbox를 유지합니다. 외부 SHA256SUMS는 압축 파일을,
내부 manifest/checksums는 설치 파일·모델·runtime·라이선스·SBOM을 검증합니다.

```sh
(
  set -eu
  am_install_dir=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-install.XXXXXXXX")
  cd "$am_install_dir"
  curl --fail --location --output agents-memory-hindsight-local-1.0.0.tar.gz \
    https://github.com/chonamdoo/agents-memory-releases/releases/download/v1.0.0/agents-memory-hindsight-local-1.0.0.tar.gz
  curl --fail --location --output SHA256SUMS \
    https://github.com/chonamdoo/agents-memory-releases/releases/download/v1.0.0/SHA256SUMS
  shasum -a 256 -c SHA256SUMS
  tar -xzf agents-memory-hindsight-local-1.0.0.tar.gz
  cd agents-memory-hindsight-local-1.0.0
  ./install.sh
)
```

설치 확인:

```sh
"$HOME/.local/share/agents-memory-hindsight/current/bin/am-hindsight" --version
"$HOME/.local/share/agents-memory-hindsight/current/bin/am-hindsight" profile
```

[전체 설치·DB·계정·프로젝트 연결 안내](../../distribution/hindsight-local/README.ko.md)를 따르세요.
기존 Native 프리뷰 설치·plugin·데이터는 자동으로 교체/변환하지 않습니다.
자동 GitHub Source code 압축 파일에는 실행용 private 구현이 없으므로 릴리즈 asset을 사용하세요.

## 확인한 결과와 한계

| 확인 항목 | 결과 | 범위 |
| --- | --- | --- |
| 출시/실환경 점수표 검증 코드 | 40 tests 통과 | 로컬 실행; GitHub CI 미실행 |
| 고정 C3 소스 핵심 회귀 | 421 tests / 1,263 phases, 실패·skip·xfail 0 | 이전 고정 소스 증거 유지; 전체 Native API를 배포한다는 뜻이 아님 |
| 최종 설치본 provider 계약 | 50개씩 통과 | 개인/회사 출력 대역; 실제 인증·의미 이해 검증 아님 |
| 최종 설치본 안전·출처·수정·삭제 | 20개씩 통과, 위반 0 | 실제 Hindsight/PG/E5 + 각 9회 모델 출력 대역 |
| 새 설치·재설치·rollback | 두 provider 통과 | 같은 최종 1.0.0 설치와 애플리케이션 포인터 복구; Native 이전/DB downgrade 아님 |
| 잠긴 drainer/설치와 64 KiB 입력 훅 | 20회씩 원문 보존 | Linux: 개인 p95 110.50ms/max 116.74ms, 회사 p95 147.96ms/max 150.40ms; 실제 Mac 지연 보장 아님 |
| 공개 실행 경로 | 로컬 bank 초기화/API health/설정 확인 통과 | 실제 Linux API/PG/E5, HTTP 설정 변경 422 유지, 실제 모델 호출 0 |
| 배포물 적대적 설치 검사 | 8개 통과 | 손상·누락·미소유 디렉터리·동시 rollback·cloud profile 거부와 기존 설정 보존 |
| Mac 정적 검사 | 자체 확장 12개 + 공식 runtime Mach-O 10개 | ARM64/ABI/로드 경로/최소 OS; 자체 확장 ad hoc 서명 page hash 확인 |

실제 Mac 실행, 사용자 Codex 훅/로그인, 실제 계정별 품질·지연·RAM은 출시 뒤 검증합니다.
Developer ID 서명과 Apple 공증은 없으며 Gatekeeper/격리 속성을 자동 해제하지 않습니다.
프로젝트 bank는 사용자별 ACL이 아닙니다. 전송은 ACK 유실 시 중복 가능성이 있는 at-least-once이며,
긴 원문을 수정/삭제할 때 Hindsight가 만든 관련 document ID 전부를 명시적으로 처리해야 합니다.
자동 Reflect/관찰 통합/mental model 생성과 Native 프리뷰 전체 CLI는 제공하지 않습니다.

자체 구현은 컴파일한 바이너리로 배포하며 원본 private Python/bytecode/생성 C는 제외했습니다.
공개 installer/entry wrapper와 MIT upstream Python은 포함합니다. 바이너리 역분석 방지를 보장하지는 않습니다.
[asset 목록과 SHA256](ARTIFACT-ASSETS.json), [검증 집계와 증거 SHA256](ARTIFACT-VERIFICATION.json),
[가상 점수표](RELEASE-READINESS.ko.md), [실환경 후속 표](SCORECARD.ko.md)를 함께 보관합니다.
