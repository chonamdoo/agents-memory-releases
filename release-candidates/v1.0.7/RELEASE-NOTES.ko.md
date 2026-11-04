# v1.0.7 — 기존 pgvector 복구 링크를 실제 파일로 자동 교체

1.0.6은 `vector.dylib` 위치에 심볼릭 링크가 있으면 원본이 정상이어도 거부했습니다. 그래서 1.0.5의 파일 이름 문제를 `vector.dylib -> vector.so` 링크로 수동 복구한 설치가 계속 `setup_failed`에 머물렀습니다.

1.0.7은 같은 런타임 폴더의 원본 `vector.so`를 가리키고, 원본 해시가 배포한 모듈과 일치하는 링크를 확인한 뒤 **동일 내용의 실제 `vector.dylib` 파일로 원자적으로 교체**합니다. 링크를 먼저 지우지 않으며 원본·DB 데이터·키·모델 설정을 유지합니다. 기존 기록이 `.so` 또는 `.dylib` 어느 쪽을 검증하던 복구하고, 검증 기록 갱신 중 중단돼도 재시도할 수 있습니다. 외부·끊어진 링크나 다른 내용의 파일은 바꾸지 않습니다.

터미널에서 두 명령을 순서대로 실행하세요.

```sh
omp plugin marketplace update agents-memory
omp plugin upgrade agents-memory-local@agents-memory
```

업그레이드 출력이 **1.0.7**인지 확인한 뒤 OMP를 완전히 종료하고 다시 실행합니다. `setup_status`의 `version: 1.0.7`, `ready: true`를 확인하세요. 링크를 수동 삭제하거나 키를 다시 입력하고 DB를 재생성할 필요는 없습니다. 마켓 갱신을 생략하면 이전 캐시 버전이 다시 설치될 수 있습니다.

`setup_status`에는 진단 로그의 정확한 경로(`logs`)와 현재 조회 범위(`memory_scope`)도 포함됩니다. 예전 Native 서버(`~/.agents-memory/<namespace>`)와 현재 Hindsight 서버는 별도 저장소입니다. 이번 복구는 기존 Native Docker DB/API를 변경하거나 양쪽 기억을 병합하지 않습니다.

검증: 실제 macOS 배포 아카이브로 기존 링크 상태를 재구성해 자동 교체·반복 실행·키와 데이터 보존을 확인했습니다. Python 87개, Go 8개와 race 검사, 두 플랫폼의 PostgreSQL 모듈 이름 계약 검사를 통과했습니다. Linux의 실제 PostgreSQL에서 확장 생성·벡터 계산·기존 기억 검색과 DB 식별자 보존도 확인했습니다. 설치·검증 중 판단 모델을 호출하지 않았으며 GitHub Actions를 실행하지 않았습니다.

수정본의 **실제 Mac 실행은 아직 확인 전**입니다. macOS 파일 배치 복구 검사는 Linux에서 실제 아카이브를 사용해 수행했습니다. Apple Silicon macOS 15 이상 조건과 E5 검색 임베딩 포함은 유지됩니다.
