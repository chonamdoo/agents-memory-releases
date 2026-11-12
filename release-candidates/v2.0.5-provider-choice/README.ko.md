# MCP 2.0.5 로컬 공급자 선택 릴리즈

로컬 설치는 로컬 LLM 또는 Jev, 서버는 Jev로 동작합니다. 엔진·SDK ABI는 2.0.0입니다.

- [고정 번들](https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/895de0e51f85ef90a1607b99545f0966091966f7/release-candidates/v2.0.5-provider-choice/agents-memory-unified-2.0.0-local-provider-v18.tar.gz) · [체크섬](https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/895de0e51f85ef90a1607b99545f0966091966f7/release-candidates/v2.0.5-provider-choice/SHA256SUMS)
- SHA-256: `bf08321c8bffcc57edf92fc3d991c9427a3dc13e21218587bf18513c8840d408`
- [설치 안내](../../distribution/server/README.ko.md) · [현재 게시 상태](STATUS.json) · [패키지·코어 출처](CANDIDATE.json)

검증: 코어 246건 통과·기존 native 통합 fixture 2건 건너뜀, 설치기 52건 통과. CPython 3.12.14/3.13.16의 실제 소스 제외 휠을 설치해 15개 private 모듈 import, HTTP 공급자 처리, CLI wrapper, 서버 모드 차단을 확인했습니다. 모두 로컬 프로토콜 대역이며 새 실제 모델 호출은 0회입니다. macOS는 사용자 실기기 검증입니다. GitHub Actions는 실행하지 않았습니다.

기존 SDK SHA-256 `1a8d2c9603cdcf6fba96b69fc4dfa64788ffb72b3f55272e1d0e0eace839a1db`와 모델 companion을 유지합니다. Jev transport와 원문 보존 통합은 바꾸지 않았습니다.
[v2.0.4의 Jev 독립196건·40질문/앱 수명주기 결과](../v2.0.4-relevance/README.ko.md)는 당시 버전의 기록입니다. 이를 새 로컬·구독 모델의 품질 결과로 적용하지 않습니다. 누락 원본 6개와 과거 실패는 공개 기록대로 보존합니다.

재현: private core PR #92와 #93의 테스트를 실행하고 CANDIDATE.json의 각 소스 해시로 휠을 빌드합니다. 공개 설치기 검사는 `python -m pytest distribution/server/tests/test_unified_setup.py distribution/server/tests/test_local_provider_setup.py`입니다. 설치 휠 검사는 번들 압축을 푼 뒤 해당 CPython minor에서 `verify-installed-core.py WHEEL BUILD.json`을 실행합니다. BUILD.json은 CANDIDATE.json의 core_builds 항목과 같습니다.
