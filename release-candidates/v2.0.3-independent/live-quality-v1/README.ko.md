# 실제 Linux integrated 평가 — FAIL

원래 동결된 196사례와 40질의를 끝까지 실행했다. 원래 strict 판정은 **FAIL**이며, 실패한 지표는 `top5_noise` 하나다. 실행 exit0은 사례·질의 전수 완료를 뜻하며 품질 통과를 뜻하지 않는다.

- 실제 저장: explicit 80/80, auto 40/40. chatter32·unsafe24·quote20은 저장되지 않았다. Native/server/local 저장 확인120, 저장 실패0, false success0.
- 실제 recall: hit40/40, 전체 required evidence 충족40/40. 불필요한 source occurrences80/returned source occurrences200=40%. Wilson95 상한0.46916327960737997로 원래 최대0.30을 넘었다. 생성 답변의 품질은 이 평가에서 측정하지 않았다.
- Background judgment p95는196표본에서21.522241705999477초로 원래 최대30초 이내다.
- 새 Jev 시도는196회 모두 완료됐다. child197 중1회가 남았다. 기존 Jev418+이번196=614, 기존 Jev 누적1000 중386이 남았다. 같은 새 계측 원장1000에서는196 소진/804 잔여이며, 그 원장의 Jev582 중386 잔여다. 새1000을 추가로 겹쳐 만든 것이 아니다.
- 금융 승인 문서SHA는 `31636c1cdb02970c35a617118765fc3210cd7134c041edd960e4ea8f9ac59b32` 그대로다. 원본 문서·원장 identity·소진 수를 초기화하거나 실패를 다시 실행하지 않았다. 종료 시점 원장은 private SQLite backup으로 고정했다. 이 묶음에는 원장 집계와 backup 해시만 있다.
- 같은 Docker cgroup에서2CPU/4GiB/swap0/pids256/nonroot/read-only로 실행했다. Memory peak4,180,643,840bytes, OOM/oom-kill0. 컨테이너 exit0/OOMKilledfalse, Native·PostgreSQL residual PID0, postmaster PID 파일 없음으로 정리를 확인했다.

원문·질문·라벨·필터·threshold·분모·원래 strict 계산을 수정하지 않았다. 이 196/40 코호트는 실제로 소진됐으므로 새 독립 release 코호트로 다시 쓸 수 없다. 실패 원본·private raw payload·원장·PG data·로그는 원래 private 실행 경로에 보존했다. 이 묶음에는 원문/라벨/모델 payload/실제 승인 원문/credentials/auth/profile/DB/wheel/venv/container payload를 포함하지 않는다.

과거 Codex117 native operations와 OMP3 observed fetch dispatches의 정확한 underlying HTTP 수는 여전히 unknown이다. 이번 계측으로 이를0으로 만들거나 과거 상한 준수를 입증하지 않는다. 실제 공급자 청구 금액도 추정하지 않았다. 이 묶음은 출시 승인이 아니다.

`STRICT-METRICS.json`은 원래 strict 수치를 그대로 담고, `CALL-LEDGER-196.json`은 이 run 종료 시점의 집계를 고정한다. 이후 같은 공용 원장에 다른 승인된 작업이 추가되더라도 이 종료 시점 집계가 그 이후의 전체 잔액을 나타낸다고 주장하지 않는다. `REGISTRATION-HASHES.json`은 코드·설치 wheel·원문/라벨의 해시만 보관한다. `FINISH-SIGNAL.json`과 `RESOURCES-CLEANUP.json`은 판정과 자원 해제 신호다.
