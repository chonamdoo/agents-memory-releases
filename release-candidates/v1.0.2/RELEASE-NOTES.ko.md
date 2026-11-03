# Hindsight 로컬 1.0.2

선택형 과거 대화 후보·사용량 원장·수동 조언을 추가했습니다. E5 검색 임베딩을 포함하며, 생성 LLM 가중치는 설치하지 않습니다.

- Claude/Codex 기록은 프로젝트·기간·디렉터리를 지정해 로컬 미리보기합니다. 설치와 업데이트는 과거 이력을 자동으로 읽지 않습니다.
- 선택한 후보만 현재 설정된 모델로 분석합니다. 저장은 정확한 본문과 현재 적용 가능성을 확인한 뒤 별도로 실행합니다.
- 응답 유실 시 자동 재전송하지 않습니다. 정확한 원격 문서 매핑으로 조정·정정·삭제하며 불확실한 상태는 보류합니다.
- 본문 없는 현재 사용량과 반복 실패를 기록하고 수동 조언을 제공합니다. 비용·구독 쿼터 절감률을 만들어내지 않습니다. 자동 도구 삭제·stop 강제·host 설정 수정은 없습니다.
- Jev/Claude/Codex 선택, 모델·키·프로젝트 설정을 업데이트 시 유지합니다. 새 설치 추천은 Claude Sonnet 5.5 / GPT-6.1 Terra이며 자동 모델 변경은 없습니다.

[기록·사용량 기능 사용법](https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/hindsight-local/HISTORY.ko.md)

1.0.0 컴파일 기반 코어를 재사용하고 새 기능 3개를 양 플랫폼 바이너리 확장으로 추가했습니다. private Python 원본·bytecode·생성 C는 배포하지 않습니다. Apple Silicon macOS 13 이상이 제품 대상이며 Linux는 명시적인 검증 경로입니다. macOS 바이너리는 교차 빌드와 구조·ad hoc 서명 해시를 검사했으며 Mac 기기 실행·Developer ID·공증은 검증하지 않았습니다.

검증: 전체 로컬 CI **5,059개 통과**, 신규 기록 기능은 소스·설치된 바이너리에서 각각 41개 통과, 공개 wrapper/gate 검사 48개와 하위 검사 62개 통과. 실제 Claude Sonnet 5.5와 Codex GPT-6.1 Terra로 후보 분석·명시적 저장·E5/RRF 검색·정확한 문서 삭제를 확인했습니다. 합성 이력만 사용했으며 실제 사용자 대화는 읽지 않았습니다. 단일 합성 흐름으로 모델 품질이나 비용 절감률을 주장하지 않습니다.

GitHub Actions는 실행하지 않으며 2026-12-01까지 보류합니다. 이전 버전 점수표를 이번 버전 검증으로 재사용하지 않습니다. Jev 키 처리는 합성 키로 검증하며 실제 Jev API 호출은 하지 않습니다.

## 설치 / 업데이트

[전체 설치 안내](https://github.com/chonamdoo/agents-memory-releases/blob/main/distribution/hindsight-local/README.ko.md)

macOS 터미널에서 다음 명령을 실행하세요. 19개 조각과 재결합한 압축 파일의 SHA256을 확인한 뒤 설치합니다. 기존 사용자는 같은 명령으로 업데이트하며 설정이 유지됩니다.

```sh
(
  set -eu
  am_install_dir=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-install.XXXXXXXX")
  cd "$am_install_dir"
  am_release=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/release-assets-v1.0.2/files
  curl --fail --location --output SHA256SUMS "$am_release/SHA256SUMS"
  curl --fail --location --output PARTS-SHA256SUMS "$am_release/PARTS-SHA256SUMS"
  am_part=0
  while [ "$am_part" -lt 19 ]; do
    am_name=agents-memory-hindsight-local-1.0.2.tar.gz.part-$(printf '%03d' "$am_part")
    curl --fail --location --output "$am_name" "$am_release/$am_name"
    am_part=$((am_part + 1))
  done
  shasum -a 256 -c PARTS-SHA256SUMS
  cat agents-memory-hindsight-local-1.0.2.tar.gz.part-* > agents-memory-hindsight-local-1.0.2.tar.gz
  shasum -a 256 -c SHA256SUMS
  tar -xzf agents-memory-hindsight-local-1.0.2.tar.gz
  cd agents-memory-hindsight-local-1.0.2
  ./install.sh
)
```

PostgreSQL 18.x / pgvector과 선택한 구독 CLI 로그인은 별도 준비합니다. 키 파일은 비공개 권한의 일반 파일이며 Keychain 암호화 저장은 아닙니다. 실행 중인 API는 정상 종료한 뒤 새 설치를 시작하세요.
