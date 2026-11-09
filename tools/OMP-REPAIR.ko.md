# OMP 연결·자동 수집 복구

마켓 플러그인 설치는 기존 엔진의 업데이트가 아닙니다. 기존 직접 MCP와 플러그인이 함께 있거나, 새 플러그인이 사용하는 프로젝트에 자동 수집 설정이 없으면 이 절차를 사용합니다.

현재 도구는 **기존 local 모드 Jev 설치**, 기본 OMP 사용자 프로필, 같은 프로젝트의 기본 설치 경로를 대상으로 합니다. 원격·팀 서버나 다른 프로필로 자동 전환하지 않습니다. 사용자 설치에서 실제 원인과 복구 성공은 실행 결과로 확인해야 합니다. 이 도구의 오프라인 검증이 사용자 환경의 복구 완료를 뜻하지 않습니다.

OMP를 완전히 종료하고, 사용하던 프로젝트의 터미널에서 실행하세요. `python3`, `curl`, `omp`가 필요합니다.

```bash
am_repair_file="$(mktemp)"
curl -fsSL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/main/tools/repair-omp.py -o "$am_repair_file"
python3 -c 'import hashlib,sys; assert hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest()==sys.argv[2], "repair checksum mismatch"' "$am_repair_file" 172089b0b3bf0f7aead32f4162bd7af4ac3074fc105a336a0dc7cc31246bea6b && python3 "$am_repair_file" --project "$PWD" --apply
```

기존 설치 경로가 기본값 `~/.local/share/agents-memory-unified`와 다르면 마지막 명령에 `--prefix /기존/설치/경로`를 추가합니다. DB를 새 위치로 복사해 연결하지 않습니다.

도구는 다음 순서로 동작합니다.

1. 기존 설치와 작업 잠금을 확인하고, 비공개 디렉터리 `~/.local/state/agents-memory-repair/…`에 연결·설정·키·훅과 일관된 SQLite 백업을 만듭니다. 실제 PostgreSQL DB·모델 디렉터리·전송함을 삭제하거나 초기화하지 않습니다.
2. SHA-256 `62b46c6393876be19df7ccfea96343b3baa0ced2f599cee2f06438dd449275ef`의 고정 v17 번들을 검증하고 표준 설치기로 **같은 위치**의 런타임을 재설치합니다. 기존 Jev 모델·키·DB를 재사용합니다.
3. 배포 SDK의 설정 생성기로 현재 프로젝트의 OMP 확장과 `automation_projects`를 복구합니다. 다른 프로젝트, 사용자 정의 확장 또는 다른 프로필과 충돌하면 덮어쓰지 않고 중단합니다. 기존 자동 수집 켜기/끄기 선택을 보존합니다.
4. 대기 작업을 올리지 않는 `pull_only` 동기화로 점검합니다. 예외의 종류 또는 검증된 오류 코드만 결과에 표시합니다. 원문 업로드 동의와 검토 대기를 승인하거나 `sync_recover`를 실행하지 않습니다.
5. 같은 연결·state 경로를 사용하는 직접 OMP 등록만 제거하고, 사용자 범위의 마켓 플러그인을 재설치합니다. `codegraph`와 다른 연결은 보존합니다.

OMP를 같은 프로젝트에서 다시 열고 일반 입력을 한 번 보낸 뒤 `setup_status`와 `source_search` 도구를 확인하세요. 자동화 실행 증거는 실제 입력 이후에 확인하며 도구가 만들어 넣지 않습니다. `full_sync_verified=false`는 복구 점검이 업로드를 포함한 전체 동기화를 수행하지 않았다는 뜻입니다. 내려받기 점검도 실패하면 완료로 표시하지 않고 오류와 비공개 백업 위치를 남깁니다. 보고서의 오류 코드/종류는 공유할 수 있지만 비공개 로그·키·DB·원문은 공유하지 마세요.

이 작업은 보존형 재설치입니다. 기존 이력을 전부 삭제하는 초기화가 아닙니다. 과거 `needs_review`는 원인별 검토가 필요합니다. `native_trust`·`model_compliance`는 별도 검증 항목이며 연결 설정 복구만으로 true로 바꾸지 않습니다.

검증: 오프라인 보존·오류 처리 25개, 고정 실제 번들 검증·압축 해제, 실제 shipping SDK 설정 생성기를 사용한 외부 호출 없는 합성 설치 점검. 실제 사용자 환경·새 유료 평가·새 macOS 실행 검증을 주장하지 않습니다. 기존 v2.0.4 번들·wheel·마켓 파일과 출시 판정 증거는 변경하지 않습니다.

`replica_worker_busy`에서는 OMP와 같은 기억 MCP를 사용하는 다른 앱을 종료하세요. 도구는 기록된 PID의 존재만 확인하며 프로세스를 종료하거나 DB 잠금을 지우지 않습니다. 종료가 확인된 PID(또는 Linux zombie)는 SDK의 기존 복구 절차로 넘깁니다. 살아 있거나 확인할 수 없는 PID는 `worker_pid`·`lease_remaining_seconds`와 함께 차단합니다. 이 값은 진단용이며 해당 PID를 무조건 종료하라는 뜻이 아닙니다.
