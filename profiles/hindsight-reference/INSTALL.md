# Hindsight reference 프리뷰 설치·연결

이 배포본은 설정과 안내만 제공합니다. 기존 `bootstrap.sh`, `install.sh`와 Claude marketplace는
20261027 Native macOS 바이너리용입니다. 이 profile의 설치기로 사용하지 마세요.
아래는 공식 소스의 설치·설정 계약입니다. 이 릴리스에서 새 컴퓨터의 clean dependency 설치나
macOS runtime을 검증한 것은 아닙니다. 실제 기능 시험은 Linux/Python3.13의 기존 격리 설치에서 했습니다.

## 1. 별도 준비

- Python>=3.11(검증 환경3.13), 별도 PostgreSQL/pgvector DB, 해당 DB의 전용 권한과 백업을 준비합니다.
  기존 Native/다른 Hindsight DB·bank를 재사용하거나 migration 대상으로 지정하지 않습니다.
- `UPSTREAM.json`의 ONNX 모델과 같은 tokenizer/config 파일을 미리 준비합니다.
  파일은 배포본에 없습니다. 고정 모델 revision·라이선스를 확인하고 별도 공식 경로에서 준비하세요.
  `model.onnx`, `tokenizer.json`, `config.json`, `tokenizer_config.json`, `special_tokens_map.json`이 필요합니다.
  같은 차원이라도 서로 다른 embedding 모델/전처리의 벡터를 섞지 않습니다.
- DB URL은 로컬 secret manager 또는 읽기 제한된 private 파일에서 환경 변수
  `HINDSIGHT_API_DATABASE_URL`로 공급합니다. 터미널·채팅·Git·명령 인자에 값을 붙이지 않습니다.

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
**Linux x86_64에서만 검증했고 이 CPU 최적화 variant의 macOS/ARM/다른 CPU 동작을 인증하지 않습니다.**
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

## 2. 로컬 실행

배포본의 `hindsight-reference.env.example`을 private 작업 디렉터리에 복사하고 **두 모델 경로**를
실제 절대 경로로 바꿉니다. tokenizer 경로는 tokenizer.json 하나가 아니라 위 파일들이 있는 폴더입니다.
이 파일은 신뢰하는 운영자만 편집하며 권한을 제한합니다. 이전 HINDSIGHT_API_* override를
상속하지 않는 전용 프로세스 환경을 사용합니다. NoneLLM/OBSfalse/chunks/RRF와 offline flags를 유지합니다.
DB URL이 없는 상태에서는 실행하지 않습니다. 테스트 cache만으로 완전 offline 설치를 주장하지 않습니다.

Bash에서 DB URL은 이미 secret manager로 공급됐다고 가정합니다. example의 나머지 값은 shell 문법입니다.
프로파일을 읽은 뒤 DB URL·override·파일 경로를 확인하고 아래처럼 loopback으로만 실행합니다.

```sh
: "${HINDSIGHT_API_DATABASE_URL:?Provide a dedicated new database via your secret manager}"
set -a
. ./hindsight-reference.env
set +a
/path/to/hindsight-upstream/.venv-reference/bin/hindsight-api --host 127.0.0.1 --port 8116
```

API와 internal worker는 DB schema를 초기화할 수 있습니다. dedicated DB를 다시 확인하세요.
8116과 worker 기본 포트가 비어 있어야 합니다. 우리 검증은 worker HTTP8118을 사용했습니다.
필요하면 공식 `HINDSIGHT_API_WORKER_HTTP_PORT=8118`을 별도 설정하세요.
`GET http://127.0.0.1:8116/health`의200은 기동 신호이며 DB·회상 성공/host 통합을 대신하지 않습니다.
공용 네트워크로 bind하지 않습니다. 별도 인증·권한 검증 없이 bank/tag를 팀 ACL로 사용하지 않습니다.

## 3. 새 bank와 직접 MCP

서버가 켜진 뒤 새로운 빈 프로젝트 bank 하나를 명시적으로 만듭니다. 아래 `my-project`를
기존 운영 bank와 겹치지 않는 새 이름으로 바꿉니다. 여러 사용자의 인증 경계를 만드는 작업은 아닙니다.

```sh
curl --fail --silent --show-error   --request PUT --header 'Content-Type: application/json' --data '{}'   http://127.0.0.1:8116/v1/default/banks/my-project
```

bank-scoped MCP URL은 `http://127.0.0.1:8116/mcp/my-project/`입니다.
`mcp.examples.json`은 수동 연결 참고 자료입니다. host 설정에 자동으로 쓰거나 trust를 부여하지 않습니다.
서버와 다른 컴퓨터에서 localhost URL을 사용하면 그 컴퓨터를 가리킵니다. 원격 배포는
인증·TLS·접근 범위를 별도로 구성해야 하며 이 profile만으로 해결되지 않습니다.

공식 SDK를 직접 사용할 때는 [동일 revision의 Python SDK 안내](https://github.com/vectorize-io/hindsight/blob/14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2/hindsight-docs/docs/sdks/python.mdx)와
[실제 quickstart/retain/recall-with-chunks 예제](https://github.com/vectorize-io/hindsight/blob/14e7306e27cdbd03ad5f17cf46f22a5f6d6ec5a2/hindsight-docs/examples/api/python-sdk.py)를
사용합니다. 별도 `hindsight-client`는 선택한 source와 호환되는 버전을 설치해야 하며 이 bundle에는 없습니다.
base URL은8116, bank는 같은 새 `my-project`로 지정하고, 자체 합성 문서로 retain→완료 확인→
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
{"tags":["project:my-project","memory_category:decision"],"tags_match":"all_strict","limit":100,"offset":0}
```

`any`/`all`은 untagged 기억을 포함할 수 있습니다. 엄격 분류 조회에는 `all_strict`를 씁니다.
이 taxonomy는 자동 분류/권한 검사/사실 확정 기능이 아닙니다.

공식 coding-agents plugin은 기본적으로 observation만 회상하고 bank seed는 observations를
켤 수 있습니다. OBSfalse bank에서는 기본 자동 회상이 비거나 구성이 달라질 수 있습니다.
`autoInject`, `recallOptions.types`, `retainExtractionMode`, `manageBankConfig`, `defaultBankConfig`를
검토하지 않은 채 기존 자동 plugin을 연결하지 마세요. 현재 검증은 직접 bank-scoped MCP이며
실제 host hook 전체를 검증했다는 뜻이 아닙니다. 새 wrapper·자동 대화 수집은 포함하지 않습니다.

## 5. 기존 설치와 복구

기존 Native DB/서비스/키/설정/보류 큐를 보존하고 별도 profile로 평가합니다. 이 bundle은 기존
Native 기억을 Hindsight로 변환하지 않습니다. 실패하면 새 프로세스만 정상 종료하고 원래
host 연결로 돌아갑니다. Hindsight DB/원문/미완료 작업은 임의 삭제하지 않습니다.
위 source 고정과 checksum은 서명·publisher 신원 확인을 대신하지 않습니다.
