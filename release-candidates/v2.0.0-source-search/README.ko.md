# v2.0.0 원문 독립 검색 후보

선별 메모에서 빠진 사실은 기존 `recall` 경로로 찾을 수 없었다. 서버에 이미
보존된 제출 작업의 원문을 직접 찾는 `source_search`를 REST·서버 MCP·설치된
stdio MCP에 추가했다. **현재 공개 채널은 prerelease이며 정식 품질 통과가 아니다.**

`{"project":"app","query":"What is the cache namespace?","limit":5}`처럼
프로젝트를 지정한다. 본인 계정의 완료된 keep/discard 원문만 대상으로 한다.
현재 revision·삭제·프로젝트 경계를 적용하고 저장 당시 해시도 확인한다.
보류·처리 중·prompt 업로드 자료는 제외한다. 전체 본문과 ID·시각·revision·
SHA-256을 반환하며, 원문은 미검증 자료로 표시한다. 팀 공유·오프라인 캐시·
시작 문맥 자동 주입은 지원하지 않는다. 영어 어간 기반 어휘 검색이며,
수집하지 않은 대화를 복원하지 않는다. 상세 계약은
[CONTRACT.md](../../distribution/server/CONTRACT.md)를 따른다.

## 로컬 검증

- 최종 전체 SDK: **293 passed, 0 failed, 1 skipped**, 194.29초.
  [전체 실행 기록](LOCAL-CI.xml). Skip 1개는 별도 소유 설치물을 지정해야 하는
  configured unified plugin 경로이며, 이 실행에서 해당 설치물을 준비하지 않았다.
  실제 설치·반복 설치·HTTP/MCP·Go proxy·Bun 호스트·Hindsight 경로는 실행했다.
- 새 wheel만 설치한 별도 환경: **26 passed, 0 failed, 0 skipped**, 7.50초.
  [설치본 실행 기록](INSTALLED-WHEEL.xml). 원문 검색 25개와 실제 설치기 검증이다.
  같은 2.0.0의 낡은 모듈을 다시 설치해 교체하면서 기존 연결 설정을 보존한다.
- 첫 전체 실행은 번들·proxy·Bun 설정 누락으로 **280 passed, 1 failed,
  10 skipped**였다. 필요한 자산과 도구를 지정한 뒤 위의 최종 실행을 완료했다.
- GitHub Actions 대신 로컬 CI를 사용한다는 사용자 지시는 **2026-12-01까지**
  적용한다. 이를 실제 Jev 품질 통과로 해석하지 않는다.

업로드 인증 오류에 대응해 다운로드 안내만 바꿔 최종 번들을 다시 조립했다.
SDK·Core 코드는 같으며 최종 번들의 실제 설치·반복 설치도
[1 passed](FINAL-BUNDLE-INSTALL.xml)로 재확인했다.

## 실제 검색 경로의 최소 재현

기존 테스트의 원문 `The cache TTL is 37 seconds.\nThe namespace is cache-v7.`를
두 조건에 똑같이 넣었다. 실제 Core processor에 고정 확률을 응답해 둘째 문장을
제외한 조건과 보존한 대조 조건을 만들었다. PostgreSQL 18.6.1/pgvector 0.8.7,
고정 Hindsight 1.1.0·E5·BGE를 실행했다. integration은 로컬 원문 보존 어댑터다.
실제 Jev 판단이나 외부 생성 호출은 하지 않았다.

제외 조건에서는 둘째 문장이 선별 메모·Hindsight 문서·`recall` 결과에 없지만,
동일 질문의 `source_search` 결과에는 전체 원문과 해당 구절이 있다.
보존 대조 조건에서는 `recall`에도 있다. 원문 조회는 engine을 비활성화해도
동작하고 추가 판단 호출은 0회였다. [실제 결과와 여섯 가지 판정](MECHANISM.json),
[재현 코드](probe.py)를 확인할 수 있다. 이는 한 가지 검색 경로를 검증한 결과이며
새 벤치마크 점수나 일반적인 검색 품질 향상의 증거는 아니다.

격리 synthetic 런타임의 실제 receipt와 Core가 있는 환경에서, 설치된 후보 SDK를
사용해 실행한다. 키 값이나 실제 사용자 데이터를 receipt에 넣지 않는다.

```sh
python release-candidates/v2.0.0-source-search/probe.py \
  --receipt /absolute/synthetic-runtime/receipt.json --output /absolute/result.json
```

## 후보 파일과 정식 전환 조건

[이 폴더의 후보 파일](agents-memory-unified-2.0.0-source-search.tar.gz)과
[SOURCE-SEARCH-SHA256SUMS](SOURCE-SEARCH-SHA256SUMS)를 받는다. GitHub 파일 화면의
Raw/Download를 사용하거나 다음 공개 주소로 내려받는다. 릴리즈 자산 업로드는
GitHub 업로드 서버의 401 인증 오류로 대기 중이며 기존 자산은 유지한다.

```sh
curl -fL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/main/release-candidates/v2.0.0-source-search/agents-memory-unified-2.0.0-source-search.tar.gz -o agents-memory-unified-2.0.0-source-search.tar.gz
curl -fL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/main/release-candidates/v2.0.0-source-search/SOURCE-SEARCH-SHA256SUMS -o SOURCE-SEARCH-SHA256SUMS
shasum -a 256 -c SOURCE-SEARCH-SHA256SUMS
```

모델 companion과 source-free Core wheel은 그대로이고,
새 SDK의 Python 15개 파일과 SQL schema가 검증한 소스와 바이트 단위로 같다.
서버와 클라이언트 양쪽을 갱신해야 새 도구를 사용할 수 있다.

후보 커밋의 체크아웃에서 다운로드 파일과 소스·기록의 동일성을 확인한다.

```sh
python release-candidates/v2.0.0-source-search/verify.py \
  /absolute/agents-memory-unified-2.0.0-source-search.tar.gz
```

[검증 지문](VERIFICATION.json)에 파일 해시·검증 수·제약을 남겼다.
기존 v43 명시 저장 70/80 실패를 이 수정으로 통과 처리하지 않는다.
실제 Jev 재평가는 별도 연결한 키와 기존 private 원본·정답·ledger가 필요하다.
**추가 197회 승인 유지, 실제 추가 호출 0회.** macOS 실기기와 중앙 공식 마켓
등재도 이 Linux 검증으로 완료했다고 하지 않는다.

## 마켓 안내와 릴리즈 자산 게시

Claude·OMP의 setup skill과 Codex 전용 setup skill도 이 후보를 선택하도록
수정했다. 세 앱의 실제 격리 로컬 마켓 설치본에서 안내 파일의 일치를 확인했다.
공개 마켓 업데이트에서 Claude는 같은 2.0.0 버전의 예전 안내를 유지하는 문제가
재현됐다. 새 안내가 전달되도록 **마켓 패키지만 2.0.1**로 올렸다. 엔진·SDK와
connector는 2.0.0 그대로이며 이 변경은 엔진의 정식 승격을 뜻하지 않는다.
[설치·게시 검증 기록](MARKETPLACE-UPDATE.json)에 범위를 구분한다.

이 저장소의 v2.0.0에 자산을 추가하는 로컬 명령은 아래와 같다. 기본 실행은
검증과 게시 계획 조회만 한다. 인증 연결 뒤 `--publish`를 붙이면 기존 9개 자산을
보존하며 새 후보·체크섬·검증 기록을 추가한다. 다른 해시의 동명 파일이 있으면
덮어쓰지 않고 중단한다. Actions 실행·tag 이동·정식 전환은 수행하지 않는다.

```sh
python .github/ci/publish-source-search-assets.py
python .github/ci/publish-source-search-assets.py --publish
```

업로드에는 `uploads.github.com`에서 유효한 GitHub 인증이 필요하다.
현재 조회·머지는 가능하지만 해당 업로드 인증은 HTTP 401을 반환한다.
