# EXPERIMENTAL 정책 bank 집계 — 2026-11-02

800자 정책 bank는 **EXPERIMENTAL·미승격** 후보입니다. 공식 고정 Hindsight의 NoneLLM/chunks,
OBSfalse/auto-consolidationfalse, 고정 multilingual-E5-small ONNX(512-token 상한), RRF를
Linux cloud에서 비교했습니다. 일반 working-memory 기본값은3000자를 유지합니다.
[설정 계약](LOCAL.md)과 [검증 JSON](VALIDATION.json)을 함께 읽으세요.

`policy-ko-bank.json`은 새 별도 정책 bank의 선택적 override입니다. 명시적인 공식 bank-config
쓰기와 resolved config 확인 후 원문을 재ingest해야 합니다. 설정 변경은 기존 기억을
재색인하지 않습니다. 기존 Native/Jev/구독 CLI corpus·권한·경로를 이전하지 않습니다.

| 단계 | 3000자 baseline | 800자 후보 | 범위 |
|---|---:|---:|---|
| 알려진 개발14문항 expected-source coverage | 4/14 | 14/14 | 알려진 한국어 원문87개, 검색 개발 관찰 |
| 별도 새32문항 중 답변 가능24건 ranked source coverage | 6/24 | 22/24 | 같은 알려진 corpus; 새 corpus holdout 아님 |
| 후보만의 첫 답변 strict QA | 측정 없음 | 24/32 | 최소28/32 gate에 FAIL; baseline QA delta 없음 |
| 답변 불가의 올바른 유보 | QA 측정 없음 | 8/8 | 답변 가능한 누락 사례의 유보는 성공으로 세지 않음 |
| 정확하고 지지되는 인용 | QA 측정 없음 | 66/66 | 완전한 답변을 보장하지 않음 |
| unsupported 정책 주장 | QA 측정 없음 | 0 | strict QA 실패를 상쇄하지 않음 |

고정 gate는 strict QA≥28/32 AND 답변 불가8/8 AND unsupported 주장0입니다. 첫 조건에
실패했으므로 전체 **FAIL**입니다. 답변 가능한5건은 필요한 근거가 reader packet에 없어
유보했고, 추가3건은 rubric 필수 세부사항이 빠졌습니다. 해당 rubric이 명시적 질문보다
넓은 세부사항을 요구한 한계가 있지만 점수·gate를 변경하지 않았습니다. 검색 coverage와
정확한 인용을 QA 정답률로 바꾸지 않습니다. 절차적 blinding은 OS 격리 증명이 아닙니다.

개발 비교의 baseline237 chunk 중207개가 E5 상한을 넘었고 후보는890 chunk였습니다.
같은 guard를 포함한 DB 크기21,976,767→35,903,167 bytes, Linux API peak RSS
1.045→1.449 GiB였습니다. DB·다른 프로세스를 합친 전체 RAM이나 최소 RAM 수치가 아닙니다.
후보 ingestion은55.29초였으나 baseline을 별도로 재지 않아 속도 비교를 주장하지 않습니다.
확인32회 recall wrapper p95는0.059637→0.077871초였으며 end-to-end QA 시간이나 Mac 수치가 아닙니다.
여섯 matched guard와800자 multi-chunk 교체·삭제는 통과했습니다. 이 profile의 lost-ACK
복구는 backend pin 차이로 BLOCKED이며 전원 장애·outbox 내구성은 입증하지 않았습니다.

[Darwin/arm64 CI asset smoke](https://github.com/chonamdoo/agents-memory/actions/runs/41382015740)는
고정 E5 asset의 CPU 입력 처리·512-token truncation·정규화된 유한384차원 벡터만 확인했습니다.
전체 Hindsight/PostgreSQL 제품,800자 bank의 Mac 품질, 사용자 Mac 설치·hook·자동 주입·내구성·
latency·RAM 검증이 아닙니다. [source PR51](https://github.com/chonamdoo/agents-memory/pull/51)의
최종 [CI41385568603](https://github.com/chonamdoo/agents-memory/actions/runs/41385568603)은
별도 exact-head 8개 check PASS입니다. merge `48793d2331a501efa51b07fcbb8ceaa0799b35a1`의
[main CI 41386502280](https://github.com/chonamdoo/agents-memory/actions/runs/41386502280)도 8개 check PASS입니다.

## 별도 새 16건 consumer-fidelity 확인

같은 알려진 87문서 corpus의 6문서에서 만든 새 16문항을 EXPERIMENTAL 800자 정책 bank의 RRF로 확인했습니다. 12건은 답변 가능,
4건은 요청 정보가 없는 답변 불가였으며, 답변 가능 사례 중 4문항은 날짜가 명시된 동기화·graph 상태를 그대로 물었습니다. 답변 불가 4건과는 별개입니다.
독립 Astra 채점은 **strict 16/16**, 답변 불가의 올바른 유보 **4/4**, 정확하고 지지되는 인용
**28/28**, unsupported 정책 주장 **0**입니다. 최종 독립 기록의 supporting check는 768건 PASS입니다.
[VALIDATION.json](VALIDATION.json)에 집계와 최종 report·grade·integrity·citation의 SHA-256을
논리적 이름으로 고정했습니다. hash는 공개 재현성을 입증하지 않으며 raw 질문·답변·원문은 포함하지 않습니다. 새 corpus·SOTA·전체 Mac 제품 검증은 아닙니다.
기존 32문항의 **24/32, 28/32 gate FAIL**은 그대로입니다. 질문과 consumer 조건이 다르므로
75%→100% 향상 점수나 backend 개선으로 주장하지 않습니다.

이번 평가 consumer는 **48 KiB(주요 32 KiB+보충 16 KiB)**를 허용하고 공식 MCP가 이미 반환한
chunk 중 아직 사용하지 않은 완전한 chunk를 모두 사용했습니다. 공식 응답의 근거를 consumer가
전달하는 충실도를 확인한 것이며 backend 검색 이득이 아닙니다. 16/16은 QA 일관성 관찰이며
보충 16 KiB가 QA를 개선했다는 인과 증거가 아닙니다. caller가 근거를 버리기 전에
완전한 공식 반환 chunk를 확인하고 이 예산을 허용하는 것은 문서화된 평가 절차입니다.
새 wrapper·renderer·host hook를 설치하거나 실제 agent context를 자동 확장한 것이 아닙니다.

| Linux 16건 paired capture | RRF | 공식 CE |
|---|---:|---:|
| recall median, seconds | 0.04546 | 14.0711 |
| recall max, seconds | 0.10697 | 16.9033 |
| API peak RSS, bytes | 814,952,448 | 1,712,435,200 |

RRF run phase 8.001초에는 startup·query가 포함되며 QA 시간은 포함하지 않습니다.
공식 CE capture는 실행상 유효했지만 **CE QA 답변은 생성하지 않았습니다**. 사전 고정한 CE의
양성 기준은 strict 정답이 RRF보다 최소 2건 많아야 한다는 것이었고, RRF 16/16 뒤에는
이 표본에서 충족할 수 없었습니다. **CE 품질 이득은 UNPROVEN이며 채택하지 않습니다.**
이는 RAM 절약을 답변 품질보다 우선한 결정이나 CE가 열등하다는 품질 결론이 아닙니다.
CE 답변 품질을 비교할 증거가 부족하며 새 CE file/config는 포함하지 않습니다.
일반 RRF/3000자 기본과 800자 정책 bank의 EXPERIMENTAL·fresh reingest 제약은 유지합니다.

이 문서는 공개 가능한 집계만 포함합니다. 원문·질문·평가 정답·개별 답변·source UUID·
private 절대 경로·credential·DB 식별자·모델 파일은 배포하지 않습니다. 이번 공개 자료 준비와
검증에서 서비스를 시작하거나 API·DB·모델을 호출하지 않았습니다. 운영 승격이나 SOTA 근거가 아닙니다.
