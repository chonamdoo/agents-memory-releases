# 가상 검증 후 정식 출시, 실환경 검증은 이후 진행

2026-11-03(UTC). 사용자가 **가상 환경과 실환경을 분리하고, 가상 100/100이면 정식 릴리즈한 뒤
실환경을 검증**하도록 지시하고 재확인했다. 이전의 실제 두 프로필 100점 선행 출시에 관한
정책을 대체한다. [이전 계약](history/ACTUAL-RELEASE-CONTRACT-before-dual.ko.md)과 모든 실패·
실행 이력은 보존한다. 실제 Mac/회사 계정 검증을 정식 게시의 선행 조건으로 다시 요구하지 않는다.

현재 소스는 c3 `30706fc1c1e6a7d5aaccee3bf643b0370bbaf5be`다. Hindsight pin·v2 patch·제품 코드는
유지한다. 새 코드 후보는 **2/3 사용**, 최종 실제 QA 확인은 **0/1**이다. 검증 방식 변경으로
횟수를 초기화하지 않는다. GitHub CI는 실행하지 않는다.

## 두 점수표

- **[가상 출시 점수표](RELEASE-READINESS.ko.md):** 정식 게시 기준이다. 개인·회사 모델 응답을
  명시적인 대역으로 바꾸고 기능·계약·저장·복구·안전·설치·배포물을 확인한다. 가상 100점은
  실제 모델 이해도·정책 정답률·SOTA 점수가 아니다.
- **[실환경 점수표](SCORECARD.ko.md):** 출시 후에도 계속 채운다. 실제 Jev/구독 CLI·Mac·계정·
  모델 품질·성능·운영 조건을 확인한다. 기존 수용 조건과 실행 증거 검증은 낮추지 않는다.
  가상 receipt가 이 표에 자동 합산되지 않는다.

| 가상 출시 항목 | 배점 | 수용 조건 |
| --- | ---: | --- |
| 고정 소스 회귀 | 20 | 현재 소스 관련 시험 225개 이상, 모든 setup/call/teardown 통과, 실패·skip·xfail·xpass 0 |
| 모델 응답 대역 계약 | 20 | 개인·회사 각각 고정 50개: keep/discard/review, 잘못된 응답, 권한 철회·오류 처리, fallback 금지, 원문 보존. 실제 모델 정확도를 채점하지 않음 |
| 공통 서비스·프로필 대역 결합 | 20 | 같은 소스/설정의 실제 공통 backend 저장/검색·시각·재시작·장애 복구·삭제 증거와, 각 mode의 실제 ASGI/DB 및 모델 대역 결과를 함께 검증. 회사 CLI 전체 경로의 직접 시험이라고 주장하지 않음 |
| 안전·출처 | 20 | 각 mode의 모델 대역과 실제 서비스에서 20개 이상 출처·bank 경계·명시적 정정/삭제·민감정보/악성 지시 경계 확인, 관측 위반 0. 모델이 악성 지시를 스스로 식별한다는 품질 보증 아님 |
| 격리 설치·복구 | 10 | 새 Linux 격리 설치, 버전·설치 경로, 두 명시적 프로젝트 설정, 업그레이드/rollback·설정/원문 보존. 실제 Mac/호스트 로그인 설치를 뜻하지 않음 |
| 최종 배포물 | 10 | 현재 소스·목표 버전·최종 artifact 해시/크기 일치, 라이선스·SBOM·설치/복구·설명 일치, 실제 artifact 검사. 비공개 구현 원문/bytecode 공개 금지, 옛 preview를 이름만 바꾸지 않음 |

대역은 `AdmissionJudge._client`의 client 생성/모델 출력을 대체한다. 실제 `decide`의 permit·
권한 callback·원문 요청·응답 검증·판단 기준·실패 처리는 실행한다. 회사 계정 로그인·실제
CLI subprocess·실제 모델 추론은 이 대역 범위에 없다. 프로필 증거는 canonical runtime/host/
모델 설정에 결합한다. 결합 검증의 공통 runtime·모드별 서비스 참조는 실제 현재 receipt의
파일·해시·source/config·결과 SHA와 일치해야 한다. 임의 SHA 문자열만으로 통과하지 않는다.

## 현재 상태

가상 **90/100**, 실환경 **개인 50 / 회사 15 / 공동 15점**이다. 새 계약 시험은 개인·회사
각 50개, 실제 ASGI/DB와 응답 대역을 쓴 안전 시험은 각 20개 통과했다. 공통 backend·64 KiB
전체-ID 수명주기를 모드별 결과와 명시적으로 결합했다. 새 실제 모델 호출은 0이다.

새 Linux 환경에 선언된 Python 의존성과 **비공개 시험용 wheel**을 설치하고 CLI/훅, 두 설정의
원문 접수, 1.0.0→0.1.0→1.0.0 복구와 설정 보존을 확인했다. 최초 오프라인 캐시 설치 실패도
보존했고 허용된 패키지 저장소에서 의존성을 받아 완료했다. 이 wheel은 공개 배포물이 아니다.

남은 가상 **10점은 최종 배포물**이다. 현재 소스에 맞는 게시 가능한 artifact를 아직 빌드하고
검사하지 않았다. 소스 저장소가 비공개이고 기존 배포 방식도 비공개 Python 구현을 공개하지
않으므로, private wheel을 공개해 점수를 채우지 않는다. 최종 배포물 없이 문서나 mock 결과만
100점으로 표시하거나 정식 tag를 발행하지 않는다.

## 실행과 정식 게시

```sh
python3 tools/release_readiness.py render > release-candidates/v1.0.0/RELEASE-READINESS.ko.md
python3 tools/release_readiness.py check --track virtual
python3 tools/release_readiness.py check --track actual
```

기본 track은 virtual이다. check는 해당 track 완료 시 0, 미완료 시 3, 잘못된 증거 시 2다.
`release_ready`는 가상 100점을, `actual_complete`는 별도의 실제 100점을 뜻한다. 검사기는
게시를 실행하거나 JSON/해시만으로 실제 실행의 진위를 증명하지 않는다. 원래 실행 receipt·
독립 검토·최종 artifact를 확인한 뒤 게시한다. 단위시험의 synthetic 100점 fixture는 임시
디렉터리에서만 사용하고 실제 점수표에 복사하지 않는다.

**가상 100점과 최종 artifact를 확인하면 추가 승인 없이** `chonamdoo/agents-memory-releases`에
새 `v1.0.0`, `prerelease=false`, `draft=false`로 정식 게시한다. 릴리즈 본문에는 가상 점수·
실제 점수·대역 범위·실환경 검증 대기를 명시한다. 실제 QA/SOTA나 회사/Mac 운영 검증 완료로
표시하지 않는다. 기존 preview tag/asset·Native 자동 설치 대상을 임의로 덮어쓰지 않는다.

## 출시 후 실제 검증

회사 Mac + Codex 대상은 확정됐다. 실제 회사 구독 CLI와 두 프로필의 Mac 설치·두 프로젝트·
worktree·로그인 재개·업그레이드/복구, 실제 지연·사용량을 이후 확인한다. 프로필별 고정 정책
100문항(답 가능 80·답 없음 20)의 첫 답변을 잠근 뒤 독립 채점한다. 정답 ≥90, 모름 ≥19/20,
같은 조건 공식 Hindsight보다 정답 수 감소 없음, 근거 없는 정책 단정·중대 회귀·누락·오류 0을
유지한다. 실제 저장 판단 50사례·안전 20사례·수명주기·성능 조건도 기존 validator 그대로다.
가상 계약 시험을 실제 모델 품질 점수로 쓰지 않는다.

[C52](PREPARATION-C52-20261103.ko.md) · [C53](VERIFICATION-C53-20261103.ko.md) ·
[C54 공통 backend](VERIFICATION-C54-CLOUD-SURROGATE.ko.md) · [C55 두 단계 검증](VERIFICATION-C55-DUAL.ko.md).
이전 이슈 #5·#10·#22의 방향 전환 종료와 요구도 보존한다. 특히 PC당 한 번 설치·두 프로젝트·
worktree 구분은 실제 검증에서 확인하며 옛 연구/기능을 완료로 재분류하지 않는다.
