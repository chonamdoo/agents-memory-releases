# 현재 후보의 실제 CLI 수명주기 검증

2026-11-08, Asia/Seoul. **Claude 2.1.319·Codex 0.167.0·OMP 18.18.0 각각
36/36**이 실제 startup/resume/compact와 압축 후 기억 재주입을 완료했다.
앱별 양측 95% Wilson 하한은 **0.903581371**이다. 108개를 합쳐 앱별 실패를
감추지 않았다. 고정된 원래 36 ID·질문·사실을 바꾸지 않았다.

이 결과는 **오프라인 수명주기 경로**에 한정한다. 실제 공식 CLI와 배포된
source-free CP312 Core·SDK, SDK replica·훅을 사용하지만 공급자 응답과 memory
recall 반환은 loopback 고정 fixture다. 실제 Jev 판단·독립 품질·통합 저장/검색·
실제 선택 공급자의 준수·첫 대화형 신뢰 승인·Mac 설치 결과로 합산하지 않는다.
추가 Jev 사용은 **0/197회**이며 정식 채널 전환 조건은 여전히 미충족이다.

## 결과와 확인 방법

- [NATIVE-LIFECYCLE.json](NATIVE-LIFECYCLE.json): 후보·wheel·검증기·사례·CLI의
  지문, 앱별 전체 분모와 결과, 24개 배치 영수증.
- `claude-batch*.json`, `codex-batch*.json`, `omp-batch*.json`: 실제 훅 이벤트·
  SDK 종료 코드·세션 hash·새 phase marker·완전한 사실이 같은 모델 입력에
  포함됐는지 확인한 기록. 원시 prompt와 credential은 내보내지 않는다.
- [COMMANDS.json](COMMANDS.json): 각 실행 컨테이너의 명령 배열. private Core의
  검증기는 [Core PR #65](https://github.com/chonamdoo/agents-memory/pull/65)에서
  고정했다. 공개 폴더에는 private Core 원본을 복사하지 않는다.
- [NATIVE-GATE-UNIT.xml](NATIVE-GATE-UNIT.xml): 검증기 회귀 29개와 subtest 19개 통과.
- [FAILED-ATTEMPTS.json](FAILED-ATTEMPTS.json): 수정 전 실패와 의도적으로 중단한
  구형 배치를 보존한다. 최종 성공 실행을 독립 holdout 시행이라고 해석하지 않는다.

공개 파일의 일관성은 다음 명령으로 다시 확인한다. SDK나 외부 연결이 필요 없다.

```sh
python3 release-candidates/v2.0.0-native-lifecycle/verify-evidence.py
```

검사기는 앱별 원래 36개 ID·파일 hash·독립 세션·세 단계 marker·실제 훅 및 SDK
종료 코드·동일 사실이 포함된 모델 입력·Codex compact 완료·자원 제한을 대조한다.
[CHECKER-VALIDATION.json](CHECKER-VALIDATION.json)의 여섯 변형(사례 누락, marker 재사용,
사실 미포함, 훅 실패, compact 실패, Wilson 부풀림)을 모두 거부했다.
이것은 자체 내보낸 기록의 일관성 검사이며 실제 실행의 서명·독립 재현·정식 승인기가 아니다.

## 실행 문제의 수정

Docker tmpfs의 `noexec` 때문에 훅 launcher가 실행되지 않는 문제를 사전 검사에서
잡고, SDK launch 실패의 OS errno를 비밀값 없이 남긴다. 기존 계정의 다른
프로세스·스레드가 Linux RLIMIT_NPROC를 소모해 발생한 EAGAIN은 전용 UID로
분리해 해소했다. 실행 컨테이너의 capability는 추가하지 않았다.

OMP의 ARM 전용 기본 경로는 보존하면서 x64 공식 addon의 baseline·modern 두
파일을 모두 SHA-256으로 고정했다. 6개 묶음이 128 요청 상한을 초과한 실패는
보존하고 3개씩 12개 배치로 전체 36개를 다시 실행했다. Codex 0.163.0에서
훅 선언 검사가 실패한 기록도 보존하며, 공식 0.167.0으로 검증한 성공과 구분한다.
누락된 선언 필드를 허용하도록 검사 조건을 낮추지 않았다.

최종 모든 컨테이너는 network-none, 읽기 전용 root·소스·도구, 비특권 전용 UID,
capability 0·no-new-privileges, **2 CPU·4 GiB·swap 0·256 pids·512 MiB scratch**,
128 HTTP 요청 상한을 유지했다. scratch만 검토된 launcher 실행을 위한 exec
tmpfs다. 컨테이너 종료 전 남은 native child가 없는지도 확인했다.

[정식 배포 상태표](../v2.0.0-stable/STATUS.json)의 실제 품질·통합 설치·예산 원장·
릴리즈 자산 전달 항목은 별도로 충족해야 한다.
