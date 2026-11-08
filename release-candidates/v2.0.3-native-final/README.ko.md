# 최종 배포 wheel의 CLI 수명주기 검증

이전 수명주기 기록은 SDK `f36a2118…`·Core `48406a54…`의 결과다. 이 폴더는
최종 배포본 SDK `14ba4978…`·Core CP312 `bb4307f7…`를 실제 설치하고 같은
원래 36개 사례를 Claude·Codex·OMP에서 각각 다시 실행한 기록이다.

각 CLI **36/36**, 앱별 양측95% Wilson 하한 **0.903581371**이다. 세 앱의
결과를 합쳐 실패를 가리지 않는다. 초기화·재개·native compact 완료·압축 후
같은 완전한 사실과 새 phase marker가 모델 입력에 전달되는 경로를 확인했다.

이는 **오프라인 기능 검증**이다. 실제 공식 CLI와 최종 설치 wheel·SDK 훅을
사용하지만 모델 응답과 memory recall 반환은 고정 fixture다. 실제 공급자 준수,
독립 라벨·κ·사전 승인·실제 통합 저장/검색 품질의 통과로 사용하지 않는다.
외부 Jev 호출은0회다. macOS는 사용자 직접 시험 대상으로 Linux 출시의 필수
조건에서 제외한다. 전체 정식 전환 상태는 여전히 미충족이다.

## 바이트와 실행 범위

- [INSTALLED-WHEELS.json](INSTALLED-WHEELS.json): 새 비편집 설치의 Core13개
  bytecode, SDK15개 소스 모듈·SQL을 최종 wheel의 실제 바이트와 대조했다.
- [NATIVE-LIFECYCLE.json](NATIVE-LIFECYCLE.json): 최종 번들·wheel·검증기·원래
  36사례의 지문, 앱별 전체 분모와 결과, 새24개 배치 영수증.
- [COMMANDS.json](COMMANDS.json): 실제 실행한 컨테이너 명령. 세 앱은 순차
  실행했고 각 컨테이너는 network-none·읽기 전용 런타임·비특권 UID31057·
  capability0·no-new-privileges·2CPU·4GiB·swap0·256pids를 유지했다.
- 이전 실패·이전 후보 기록은 [기존 기록](../v2.0.0-native-lifecycle/README.ko.md)에
  보존한다. 같은 자료의 기능 재실행을 새 독립 holdout이라고 부르지 않는다.

## 내보낸 기록의 일관성 확인

저장소 루트에서 다음 명령을 실행한다. 외부 서비스나 SDK 설치는 필요 없다.

```sh
python3 release-candidates/v2.0.0-native-lifecycle/verify-evidence.py release-candidates/v2.0.3-native-final
```

v2 기록은 최종 후보 VERIFICATION의 실제 지문, Core·SDK wheel 동일성,
설치 바이트 대조 기록과 모든 배치의 동일 설치 prefix도 요구한다.
[CHECKER-VALIDATION.json](CHECKER-VALIDATION.json)은 원래6종 변형 외에
최종 wheel 불일치·설치 증거 누락·설치 모듈 수 오류·이전 설치 prefix 혼용도
거절하는지 확인한다. 과거 v1 기록의 검사도 유지한다.

이 검사기는 내보낸 메타데이터의 일관성만 확인한다. 실행의 독립 인증이나
원본 실험 재현, 독립 저자 증거 또는 정식 배포 승인을 대신하지 않는다.
