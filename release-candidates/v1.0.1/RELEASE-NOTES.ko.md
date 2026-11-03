# Hindsight 로컬 1.0.1

로컬 전용 설치 패치입니다. 검색용 E5 ONNX와 RRF를 유지하고, 로컬 생성 LLM은 설치하지 않습니다.

- 처음 설치할 때 Jev / 구독 LLM을 선택합니다. 구독 LLM은 Claude / Codex를 선택하고 모델 ID를 직접 지정할 수 있습니다.
- 새 구독 설치의 추천 모델: Claude Sonnet 5.5 / GPT-6.1 Terra. 기존 설치의 provider·CLI·모델은 업데이트가 변경하지 않습니다.
- Jev는 터미널에서 API 키를 숨김 입력으로 받아 버전 디렉터리 밖 사용자 전용 0600 파일에 저장합니다. 업데이트는 키·프로젝트·미전송 outbox를 유지합니다.
- 키 변경은 `am-hindsight configure --jev-key`로 명시합니다. 키 본문을 명령 인자나 공개 프로필에 넣지 않습니다.
- 새 설치가 준비된 뒤 current 포인터를 바꿉니다. 의존성 설치 실패 시 기존 설정과 애플리케이션을 유지합니다.

기존 공개 1.0.0의 컴파일 코어를 그대로 사용하고 공개 installer/entry wrapper를 갱신했습니다. private Python 원본·bytecode·생성 C는 배포하지 않습니다.
지원 제품 대상은 Apple Silicon macOS 13 이상이며, Linux는 명시적인 검증 경로입니다. 이번 업데이트에서 Mac 기기 실행을 검증했다는 뜻은 아닙니다. Developer ID/공증 상태는 기존 배포와 같습니다.

로컬 검증: 공개 wrapper 검사 8개 통과, 실제 터미널 키 숨김·권한·업데이트·실패 복구 확인, 공개 컴파일 후보의 실제 Claude Sonnet 5.5 / Codex Terra 저장 판단과 E5/RRF 검색 통과. Jev 키 처리는 합성 키로 검사했고 실제 Jev API 인증·추론은 호출하지 않았습니다. 단일 합성 항목 검사로 모델 정확도/SOTA를 주장하지 않습니다.
GitHub Actions는 실행하지 않았으며 사용량 제한에 따라 2026-12-01까지 보류합니다. 과거 1.0.0 점수표는 그 버전의 기록입니다.

## 설치 / 업데이트

[전체 설치 안내](https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/hindsight-local/README.ko.md)

macOS 터미널에서 다음 명령을 실행하세요. 19개 조각과 재결합한 압축 파일의 SHA256을 확인한 뒤 설치합니다. 기존 사용자는 같은 명령으로 업데이트하며 설정이 유지됩니다.

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

PostgreSQL 18.x / pgvector과 선택한 구독 CLI 로그인은 별도 준비합니다. 키 파일은 비공개 권한의 일반 파일이며 Keychain 암호화 저장은 아닙니다. 실행 중인 API는 정상 종료한 뒤 새 설치를 시작하세요.
