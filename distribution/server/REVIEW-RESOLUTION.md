# 페이블 5.1 재검토 결과와 수정 근거

Claude 구독 CLI의 `claude-fable-5-1`로 수정 중간 버전을 읽기 전용 검토했습니다. 모델은 테스트를 실행하지 않았으며, 아래 판정은 이후 실제 재현과 최종 57개 검사에서 확인했습니다. 원래 실패 기록을 통과 기록으로 바꾸지 않았습니다.

| 검토에서 지적한 문제 | 최종 처리 | 실행 근거 |
| --- | --- | --- |
| NUL 입력 하나가 전송을 계속 막음 | 새 입력에서 거부. 예전 잘못된 큐 항목은 검토 대기로 분리 | `test_nul_input_rejected_and_legacy_bad_item_does_not_block_others` |
| 다른 기기에서 재사용한 작업 ID가 다운로드까지 막음 | 서버 항목을 적용하고 다른 의도의 로컬 항목만 충돌로 남김. 새 작업 ID로 명시적 해결 | `test_operation_id_collision_does_not_wedge_pull_or_resolution` |
| 세 앱이 같은 SQLite를 쓰면 작업 중 상태를 실패로 오인 | busy 상태를 구분하고 검증된 기존 개인 사본을 초기 컨텍스트로 전달 | `test_shared_host_lease_still_delivers_recent_startup_context` |
| lease 확인과 적용이 같은 SQLite 트랜잭션이 아님 | BEGIN IMMEDIATE, 같은 트랜잭션 안에서 소유권 재검사, 죽은 프로세스 lease 회수 | `test_lost_worker_lease_cannot_commit_old_projection_page` |
| 복원·예전 버전 업그레이드에서 설치 안내가 막힘 | `setup --replace-credential --recover`, 다른 계정의 키는 거절. 미귀속 큐는 `export-pending`으로 보관 | `test_explicit_key_replacement_and_restore_recovery_in_setup` |
| 정상 상태에서도 recover가 큐와 보관본을 바꿈 | 이력이 일치하면 아무것도 바꾸지 않음 | `test_healthy_recovery_does_not_demote_pending_or_make_archive` |
| 저장 거절 응답이 저장된 것처럼 보임 | `sync_retain` 입력 거절은 accepted/queued=false, 예기치 않은 오류는 결과 미확정으로 표시 | 도구 오류 경로 관찰; 별도 UI 실기 판정은 남음 |
| 초기 기억 선택이 UUID 순서이고 네트워크 대기가 길어짐 | 최근 적용 순서, 제한된 컨텍스트. 초기 네트워크 대기는 2초 후 백그라운드 계속 | `test_silent_network_does_not_delay_mcp_initialize_until_timeout` 및 실제 MCP 초기 컨텍스트 검사 |

추가 실행 검사에서 온라인 부분 수정의 세션·출처 소실, 읽기 전용 키의 로컬 큐 수락, 복원 시 옛 키 재활성화 방지 절차를 보강했습니다. wheel에서 소스가 빠지는 패키징 문제와 컨테이너 비루트 사용자 파일 권한도 실제 설치·기동 검사에서 수정했습니다. 최종 wheel은 57개 검사에 사용한 wheel과 SHA256이 같습니다. 서버 런타임 소스·SQL도 검증 스냅샷과 일치합니다.

최종 검증: 실제 PostgreSQL/pgvector·E5·두 replica·HTTP 장애 주입·실제 stdio MCP·실제 클라이언트 설치/재설치·백업 복원·권한 회수. Hypothesis는 seed 20261104로 20개 예제, 400개 동작, 그중 응답 유실 83회를 실행했습니다. 이것이 모든 동시 실행 순서나 검색 품질을 증명하지는 않습니다.

안정 로컬 제품은 기본값으로 유지합니다. 이번 결과는 개인 서버 개발 프리뷰와 제한된 팀 시험의 근거입니다. Native macOS/Windows, 실제 세 호스트 앱의 instructions 소비, 외부 HTTPS 운영, 부하·HA 검증은 별도이며 정식 범용 지원으로 표시하지 않습니다.
