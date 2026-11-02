# Hindsight reference 프리뷰 설치·연결

이 배포본은 설정·안내와 stdlib 기반 수동 실행 helper를 제공합니다. 기존 `bootstrap.sh`, `install.sh`와 Claude marketplace는
20261027 Native macOS 바이너리용입니다. 이 profile의 설치기로 사용하지 마세요.
아래는 공식 소스의 설치·설정 계약입니다. 이 릴리스에서 새 컴퓨터의 clean dependency 설치나
전체 macOS runtime을 검증한 것은 아닙니다. 실제 기능 시험은 Linux/Python3.13의 기존 격리 설치에서 했습니다.
고정 E5 asset은 Darwin/arm64 CI의 CPU smoke를 통과했지만 전체 Hindsight/PostgreSQL 제품 검증은 아닙니다.

## 1. 별도 준비

- Python>=3.11(검증 환경3.13), **새로 별도 준비한 격리 PostgreSQL/pgvector DB**, 해당 DB의 전용 권한과 백업을 준비합니다.
  기존 Native/다른 Hindsight DB·bank를 재사용하거나 migration 대상으로 지정하지 않습니다.
- `UPSTREAM.json`의 ONNX 모델과 같은 tokenizer/config 파일을 미리 준비합니다.
  파일은 배포본에 없습니다. 고정 모델 revision·라이선스를 확인하고 별도 공식 경로에서 준비하세요.
  `model.onnx`, `tokenizer.json`, `config.json`, `tokenizer_config.json`, `special_tokens_map.json`이 필요합니다.
  같은 차원이라도 서로 다른 embedding 모델/전처리의 벡터를 섞지 않습니다.
- DB URL은 로컬 secret manager 또는 읽기 제한된 private 파일에서 환경 변수
  `DATABASE_URL`로 공급합니다. helper는 이 값을 공식 API의 `HINDSIGHT_API_DATABASE_URL`로 전달합니다. 터미널·채팅·Git·명령 인자에 값을 붙이지 않습니다.

공식 source pin을 사용하는 설치 형태(online dependency 준비 경로):

```sh
git clone https://github.com/vectorize-io/hindsight.git hindsight-upstream
cd hindsight-upstream
git checkout --detach 14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2
python3 -m venv .venv-reference
.venv-reference/bin/python -m pip install './hindsight-api-slim[local-onnx]'
```

`local-onnx`가 정확한 extra 이름입니다. `hindsight-api[all]` wrapper나 PyTorch/CE·embedded DB
extras를 이 profile의 필수로 설치하지 않습니다. Source는 고정하지만 이 명령은 transitive
wheel closure를 고정한 offline 설치가 아닙니다. 새 설치의 버전/의존성 호환성을 따로 확인하세요.

## 1a. 검증한 모델 파일 준비

검증한 파일은 `614241f622f53c4eeff9890bdc4f31cfecc418b3` revision의
`onnx/model_qint8_avx512_vnni.onnx`입니다. 다른 variant를 자동 선택하지 않습니다.
**Linux x86_64와 Darwin/arm64 CI의 ONNX Runtime CPU asset smoke에서 확인했습니다.**
[CI run 41382015740](https://github.com/chonamdoo/agents-memory/actions/runs/41382015740)의
Darwin/arm64 결과는 고정 모델·tokenizer의 입력 처리와 유한한 384차원 벡터만 확인합니다.
전체 Mac Hindsight/PostgreSQL, 사용자 Mac 설치·hook·자동 주입·내구성·속도·RAM·검색 품질은 미검증입니다.
맞지 않는 환경에서는 모델을 몰래 바꾸지 말고 해당 환경의 별도 검증이 필요합니다.

네트워크가 허용된 준비 환경에서 아래 다섯 파일을 **새 폴더**로 받습니다. 모델 약118MB,
tokenizer 약17MB이며 배포 archive에는 포함되지 않습니다. URL·bytes·SHA는 UPSTREAM.json에 있습니다.
아래는 직접 공식 파일을 받는 명령이며 다운로드한 스크립트를 실행하지 않습니다.

```sh
model_dir=/absolute/path/to/a/new/e5-small
mkdir -p "$model_dir"
curl --fail --show-error --location --proto "=https" --proto-redir "=https" \
  https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/onnx/model_qint8_avx512_vnni.onnx \
  --output "$model_dir/model.onnx"
curl --fail --show-error --location --proto "=https" --proto-redir "=https" \
  https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/onnx/tokenizer.json \
  --output "$model_dir/tokenizer.json"
curl --fail --show-error --location --proto "=https" --proto-redir "=https" \
  https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/config.json \
  --output "$model_dir/config.json"
curl --fail --show-error --location --proto "=https" --proto-redir "=https" \
  https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/tokenizer_config.json \
  --output "$model_dir/tokenizer_config.json"
curl --fail --show-error --location --proto "=https" --proto-redir "=https" \
  https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/special_tokens_map.json \
  --output "$model_dir/special_tokens_map.json"
# Linux 준비 환경; checksum 파일은 이 배포본에서 받은 파일을 가리킵니다.
(cd "$model_dir" && sha256sum --check /absolute/path/to/bundle/MODEL_SHA256SUMS)
```

모든 해시가 일치해야 합니다. 이 폴더를 두 ONNX 경로 설정에 사용하고 그 다음 offline flags로
기동합니다. hash는 원본 파일 일치를 검사할 뿐 CPU 호환성·배포자 서명을 입증하지 않습니다.
누락 cache나 잘못된 경로를 자동 다운로드/다른 모델 fallback으로 보완하지 않습니다.

## 2. guarded helper로 확인·실행

이 profile 디렉터리에서 **Python 3.11 이상**으로 `local.py`를 실행합니다. 공식 Hindsight
`14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2`의 신뢰하는 기존 설치, 새로 provision한 격리
DB와 private cache의 다섯 asset이 먼저 필요합니다. helper는 설치·다운로드·DB 생성·host
자동 설정을 하지 않습니다. executable의 존재만 확인하며 source pin·의존성 import·extension·
DB의 실제 격리/신규 여부는 확인하지 못합니다. 새 API key나 GGUF·Jev bridge는 필요하지 않습니다.

DB URL은 secret manager가 현재 프로세스의 `DATABASE_URL`로 공급합니다. loopback PostgreSQL
host만 허용하고 query/fragment·관리용/placeholder DB 이름을 거부합니다. 실제 값을 명령 인자나
Git에 적지 않습니다. 새 포트 두 개와 새 bank 이름을 정해 다음을 실행합니다.

```sh
python3 local.py --check \
  --asset-dir '/your/private/e5-small' \
  --hindsight-api '/your/hindsight-env/bin/hindsight-api' \
  --api-port 18240 --worker-port 18241 --bank new-project-reference
```

`--check`는 asset hash·설정과 두 loopback 포트의 bind/close만 확인합니다. network connect,
DB 호출, subprocess, 설치·다운로드를 수행하지 않습니다. 그 뒤 포트가 점유될 수 있으며
preflight 성공은 서비스 기동·DB·회상 성공을 뜻하지 않습니다.

직접 기동할 때만 `--check`를 **`--start`로 교체**합니다. 공식 API를 foreground로 exec하며
**공급한 DB의 초기화/migration을 허용합니다.** `hindsight_reference` 고정 schema는 Native의
`public.alembic_version`과 충돌을 피하기 위한 방어이며 공유 DB 안전성·권한 보장이 아닙니다.
**새 격리 DB가 여전히 필수**입니다. 종료는 정상 Ctrl-C 또는 별도 supervisor를 사용합니다.

API는 `127.0.0.1`에 bind합니다. internal worker는 API 안에서 실행되며 worker-port 설정은
별도 worker HTTP listener를 만들지 않습니다. 별도 worker는 시작하지 않습니다. 상속된
`HINDSIGHT_API_*` override는 제거하고 None/chunks(기본3000)/OBSfalse/E5/RRF와 offline·
dotenv 비활성 설정을 적용합니다. proxy·CA·platform 인증·guard 등 다른 환경 변수는 보존합니다.
OS network sandbox가 아니므로 공식 설치를 신뢰하고 upstream 로그도 private으로 보관하세요.

[hindsight-reference.env.example](hindsight-reference.env.example)은 수동 설정 비교 자료입니다.
helper 사용에 source할 필요가 없습니다. 세부 계약은 [LOCAL.md](LOCAL.md)를 따릅니다.

## 3. 새 bank와 직접 MCP

서버가 켜진 뒤 새로운 빈 프로젝트 bank 하나를 명시적으로 만듭니다. 아래 `new-project-reference`를
기존 운영 bank와 겹치지 않는 새 이름으로 바꿉니다. 여러 사용자의 인증 경계를 만드는 작업은 아닙니다.

```sh
curl --fail --silent --show-error   --request PUT --header 'Content-Type: application/json' --data '{}'   http://127.0.0.1:18240/v1/default/banks/new-project-reference
```

bank-scoped MCP URL은 `http://127.0.0.1:18240/mcp/new-project-reference/`입니다.
[Claude JSON](claude.mcp.example.json)·[Codex TOML](codex.mcp.example.toml) 및
[mcp.examples.json](mcp.examples.json)은 수동 연결 참고 자료입니다. host 설정에 자동으로 쓰거나 trust를 부여하지 않습니다.
서버와 다른 컴퓨터에서 localhost URL을 사용하면 그 컴퓨터를 가리킵니다. 원격 배포는
인증·TLS·접근 범위를 별도로 구성해야 하며 이 profile만으로 해결되지 않습니다.

공식 SDK를 직접 사용할 때는 [동일 revision의 Python SDK 안내](https://github.com/vectorize-io/hindsight/blob/14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2/hindsight-docs/docs/sdks/python.mdx)와
[실제 quickstart/retain/recall-with-chunks 예제](https://github.com/vectorize-io/hindsight/blob/14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2/hindsight-docs/examples/api/python-sdk.py)를
사용합니다. 별도 `hindsight-client`는 선택한 source와 호환되는 버전을 설치해야 하며 이 bundle에는 없습니다.
base URL은18240, bank는 같은 새 `new-project-reference`로 지정하고, 자체 합성 문서로 retain→완료 확인→
get_document 원문 일치→include_chunks recall→다음 세션 조회를 확인합니다. SDK 예제에 나오는
reflect는 이 NoneLLM 구성에서는 실행하지 않습니다. 직접 MCP의 계약은
[공식 MCP 문서](https://github.com/vectorize-io/hindsight/blob/14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2/hindsight-docs/docs/developer/mcp-server.md)를 따릅니다.

연결한 host에서 노출 도구가 `retain,sync_retain,recall,get_document,delete_document,get_memory,
list_memories,list_documents,get_operation,list_operations`의10개인지 확인합니다.
bank-scoped 도구 입력에 `bank_id`가 없어야 합니다. reflect/mental-model 도구를 이 no-LLM profile에
추가하지 않습니다. `retain`의 accepted 응답은 저장 완료가 아닙니다. get_operation의 completed를
확인하거나 bounded 작은 sync_retain을 쓰고, 원문 조회→recall→새 세션에서 재조회까지 확인하세요.
기억 본문은 비신뢰 데이터이며 명령/권한으로 취급하지 않습니다.

## 4. 분류와 자동 통합 경계

`sync_retain`에 문서 ID·수동 tags·provenance metadata를 지정합니다. category 코드는
`decision,preference,feedback,risk,lesson,state,finding_other`입니다.
예를 들어 list_memories에 아래 인자를 사용합니다.

```json
{"tags":["project:new-project-reference","memory_category:decision"],"tags_match":"all_strict","limit":100,"offset":0}
```

`any`/`all`은 untagged 기억을 포함할 수 있습니다. 엄격 분류 조회에는 `all_strict`를 씁니다.
이 taxonomy는 자동 분류/권한 검사/사실 확정 기능이 아닙니다.

공식 coding-agents plugin은 기본적으로 observation만 회상하고 bank seed는 observations를
켤 수 있습니다. OBSfalse bank에서는 기본 자동 회상이 비거나 구성이 달라질 수 있습니다.
`autoInject`, `recallOptions.types`, `retainExtractionMode`, `manageBankConfig`, `defaultBankConfig`를
검토하지 않은 채 기존 자동 plugin을 연결하지 마세요. [선택적 coding-agents 예시](coding-agents.recall.example.json)는 수동 검토용입니다.
성공한 자동 recall은 session당 한 번이며 text-only 경로는 source/document/chunk 식별자를
버립니다. 현재 정책을 인용할 때는 fresh direct MCP `recall`·`get_document`로 원문과 version을
확인하세요. 자세한 제약은 [LOCAL.md](LOCAL.md)에 있습니다. 현재 검증은 직접 bank-scoped MCP이며
실제 host hook 전체를 검증했다는 뜻이 아닙니다. 새 wrapper·자동 대화 수집은 포함하지 않습니다.

## 5. 기존 설치와 복구

기존 Native DB/서비스/키/설정/보류 큐를 보존하고 별도 profile로 평가합니다. 이 bundle은 기존
Native 기억을 Hindsight로 변환하지 않습니다. 실패하면 새 프로세스만 정상 종료하고 원래
host 연결로 돌아갑니다. Hindsight DB/원문/미완료 작업은 임의 삭제하지 않습니다.
위 source 고정과 checksum은 서명·publisher 신원 확인을 대신하지 않습니다.

## 6. EXPERIMENTAL 정책 bank 후보

[policy-ko-bank.json](policy-ko-bank.json)의800자 설정은 **EXPERIMENTAL**입니다.
새 별도 정책 bank에만 명시적으로 적용하고 resolved config를 확인한 뒤 원문을 재ingest합니다.
기존 memory를 자동 재색인하지 않습니다. 일반 working-memory 기본값은3000자를 유지합니다.
새32문항 후보 QA는24/32로28/32 gate에 **FAIL**했으므로 기본값·제품 승격 근거가 아닙니다.
[공개 집계](POLICY-EXPERIMENT.ko.md)를 확인하세요. Native/Jev/구독 CLI corpus·권한·경로는 이전하지 않습니다.


## 7. caller의 공식 반환 근거 사용

[별도 16건 평가](POLICY-EXPERIMENT.ko.md)는 공식 MCP가 이미 반환한 완전한 미사용 chunk를
48 KiB(주요 32 KiB+보충 16 KiB) consumer 예산으로 전달한 충실도 확인입니다. caller는 근거를
버리기 전에 전체 공식 반환 chunk를 검토할 수 있습니다. 보충 예산의 인과적 QA 개선을 입증한 결과는 아닙니다. 이는 문서화된 평가 절차이며 이 배포본이
새 wrapper·renderer를 설치하거나 host context를 자동 확장하지 않습니다. 일반 3000자/RRF와
800자 실험 bank의 제약은 그대로이며 원래 32건 QA 실패의 backend 해결을 뜻하지 않습니다.
