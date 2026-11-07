# agents-memory 공통 MCP 2.0.0

**2.0.0은 공개 시험 릴리즈(prerelease)이며 출시 품질 기준을 통과하지 않았습니다.**
로컬·개인 서버·팀 서버·회사 서버에서 같은 Hindsight 엔진을 사용합니다.
Claude·Codex·omp는 MCP·훅·압축 문맥 연결 앱이고, 저장 판단 공급자는 **Jev 하나**입니다.
구독 CLI 추론과 공급자 선택 메뉴는 제거했습니다. 장애 때 native CLI로 대체하지
않습니다. native→Jev 전환 실패 뒤에도 native를 다시 시작하지 않으며, 같은 Jev
업데이트의 실패만 이전 Jev 설정·번들로 복구합니다. 기존 DB를 자동 이전·재처리하지 않습니다.

## 로컬 설치: Claude·Codex·omp

[v2.0.0 공개 릴리즈](https://github.com/chonamdoo/agents-memory-releases/releases/tag/v2.0.0)에서
lean 번들·모델 companion·`SHA256SUMS`를 직접 내려받아 SHA-256을 확인하고 압축을 푸세요.
설치기는 압축 해제한 로컬 번들을 사용하며 제품 번들·모델을 자동 다운로드하지 않습니다.
이전 정식 최신 버전 v1.0.8은 그대로 유지합니다. Docker는 필요 없습니다.
최초 엔진 설치에는 PostgreSQL·pgvector, 고정 Python·Hindsight·E5와 별도의
준비된 ONNX 재순위 모델 디렉터리가 필요합니다.

```bash
bash /path/to/extracted-bundle/install-unified.sh \
  --bundle /path/to/extracted-bundle \
  --bootstrap-bundle /path/to/bootstrap-bundle \
  --reranker-dir /path/to/prepared-reranker \
  --mode local --provider jev --client all --project "$PWD"
```

`--bundle`을 생략하면 설치기 옆에 유효한 `ASSETS.json`이 있는 번들만 사용합니다.
없으면 명시적 `--bundle PATH`가 필요하며 과거 공개 번들로 대체하지 않습니다.
`--bootstrap-bundle`은 준비된 로컬 bootstrap을 쓸 때 지정합니다. 생략하면 기존에
고정·검증된 genuine 1.0.2 bootstrap 다운로드를 사용할 수 있습니다. 이 1.0.2는
bootstrap의 역사적 소유권 버전이며 제품 버전 2.0.0과 다릅니다.
로컬 `--bootstrap-bundle`은 고정 해시를 확인하는 genuine 1.0.2 `.tar.gz` 또는
그 압축을 푼 디렉터리입니다. 로컬 최초 설치의 Python은 이 bootstrap에서 준비합니다.

기존 Jev 설치의 선택 모델·키·DB·기기 연결을 보존합니다. 기존 `claude`/`codex`
공급자 설정은 같은 설치 명령에 **`--provider jev`를 명시**하여 전환하세요.
Jev 키는 비공개 키 파일 또는 터미널 숨김 입력으로 제공하며 stdout·채팅에 출력하지
않습니다. 비밀값을 명령 인자에 넣지 마세요. 설치가 기존 Jev 모델을 임의로 바꾸지 않습니다.

설치기 소유 activation lock으로 설치를 직렬화하고, 서비스 시작·중지는 같은
서비스 lock으로 보호합니다. 새 키는 비공개 임시 파일에서 실제 공급자 확인을
거친 뒤에만 저장하며 실패 시 제거합니다. `provider_verified=false`인 새 설정으로는
MCP 자동 시작도 거절합니다. 기존 키와 다른 `--jev-key-file`은 조용히 무시하거나
덮어쓰지 않고 설치 전에 중단합니다. 실패 진단은 생성된 경우 prefix의
`settings/unified-operations.log`와 `settings/unified-service.log`에서 확인하세요.
bootstrap 실패·시간 초과는 오류에 표시된 비공개 임시 디렉터리의 `bootstrap.log`에
각 출력 최대 512 KiB를 남깁니다. 직접 `service` 실행도 PID·instance 영수증을
기록하며, 선택한 instance의 health 응답만 준비 완료로 인정합니다. 영수증 없는
점유 포트는 기존 서비스로 조용히 채택하지 않습니다.

개별 연결은 `--client claude`, `--client codex`, `--client omp`입니다.
`--client all`은 세 앱을 등록하며 판단 공급자를 세 개 설치한다는 뜻이 아닙니다.
기존 MCP·훅 설정이 충돌하면 덮어쓰지 않고 중단하므로 메시지와 백업을 확인하세요.

- Claude: 프로젝트 `.mcp.json`과 `.claude/settings.local.json`을 사용합니다.
- Codex: `.codex/config.toml`과 `.codex/hooks.json`을 사용합니다.
- OMP: `.omp/mcp.json`과 `.omp/extensions/agents-memory-cloud.ts`를 사용합니다.

설치 후 앱을 다시 열고 `agents-memory-cloud`의 `setup_status`를 확인하세요.
`ready`뿐 아니라 `server_ready`와 미전송·충돌 상태를 함께 봅니다. 준비 중 MCP 초기화는
응답하며 메모리 준비 전 저장을 완료했다고 표시하지 않습니다. 로컬 서비스와 native DB는
MCP 연결 시 다시 시작됩니다. OS 로그인 서비스는 임의로 등록하지 않습니다.

최초 프로젝트·훅 신뢰와 OMP 확장 활성화는 각 앱의 정책을 따릅니다. 자동 후보 저장·회상은
사용자 입력/세션 이벤트와 MCP 백그라운드 작업으로 연결되며, 도구 자동 승인만으로
동작한다고 주장하지 않습니다. 저장마다 별도 승인을 받는 흐름을 기본값으로 강제하지 않습니다.
복구·충돌 해결처럼 데이터에 영향을 주는 관리 도구는 일상 도구와 구분해 검토하세요.

## 플러그인 연결

`agents-memory-unified@agents-memory` 2.0.0을 자체 공개 마켓에서 배포합니다.
`agents-memory-local` 1.0.8은 이전 공급자를 유지하는 별도 항목입니다. 둘을 같은
프로젝트에 중복 등록하지 마세요. 아래 마켓 설치는 엔진·모델·키 준비와 별도이며,
현재 2.0.0 릴리스의 시험 배포 상태와 저장 품질 제한을 바꾸지 않습니다.

Claude Code:

```sh
claude plugin marketplace add chonamdoo/agents-memory-releases
claude plugin install agents-memory-unified@agents-memory
```

OMP(oh-my-pi):

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-unified@agents-memory
```

위 두 앱은 플러그인 MCP를 제공하고 미설정 상태에서 `setup_status`를 안내합니다.
엔진 준비는 같은 설치 명령에 `--client claude-plugin` 또는 `--client omp-plugin`을
사용합니다. 직접 MCP를 중복 등록하지 않습니다.

Codex CLI:

```sh
codex plugin marketplace add chonamdoo/agents-memory-releases
codex plugin add agents-memory-unified@agents-memory
```

Codex 마켓 항목은 **설치 안내 skill**입니다. 호스트 간 플러그인 경로 변수 호환을
가정하지 않으며 MCP를 자동 연결하지 않습니다. 해당 skill에서 위의 검증된 번들
설치기를 `--client codex --project /실제/프로젝트`로 실행해 `.codex/config.toml`에
정식 stdio MCP를 등록합니다. 이 단계 이후 `agents-memory-cloud`로 연결합니다.

업데이트는 Claude의 `plugin marketplace update` 후 `plugin update`, OMP의
`plugin marketplace update` 후 `plugin upgrade`를 사용합니다. Codex는
`plugin marketplace upgrade agents-memory` 후 해당 항목을 다시 설치하고 런타임
설치기를 같은 인자로 실행합니다. 업데이트 후 호스트를 다시 시작하세요.
키·DB·설정은 플러그인 캐시 밖에 둡니다. 앱별 hooks 신뢰는 정상 절차를 따릅니다.

자체 마켓 설치 가능 상태는 Anthropic 또는 OpenAI의 중앙 공식 디렉터리 심사·등재와
다릅니다. 중앙 디렉터리 등재 완료를 주장하지 않습니다.

## 개인·팀·회사 서버

엔진을 설치할 서버에서 `--mode personal-server`, `team-server`, `company-server`를
선택합니다. **Jev 판단 호출과 ONNX 재순위 추론은 엔진 호스트에서 실행**됩니다.
PC의 구독 인증을 서버로 복사하지 않습니다. 공급자 장애를 원문 저장으로 우회하지 않습니다.
기본 API는 loopback입니다. 직접 인터넷에 DB/Hindsight 포트를 열지 마세요.
개인 시험은 SSH/IAP 터널, 공용 접속은 HTTPS 역방향 프록시와 공개 URL을 준비합니다.
모드 이름만으로 SSO·SCIM·회사 보안 인증을 제공한다는 뜻은 아닙니다.

다른 PC의 기존 원격 연결에는 모델·bootstrap·DB·Jev 키가 필요 없습니다.
같은 lean 번들의 설치기로 클라이언트만 설치합니다.
원격 설치는 `ASSETS.json` 전체 해시 검증을 실행할 기존 설치 소유 Python 또는
사용 가능한 `python3`가 필요합니다. 없으면 명확히 중단하며 모델·bootstrap을
대신 다운로드하지 않습니다. 원격 모드의 `--prefix`는 클라이언트 설치 루트입니다.

```bash
bash /path/to/extracted-bundle/install-unified.sh --bundle /path/to/extracted-bundle \
  --connect-server --client all --project "$PWD" --profile personal --url https://YOUR_GATEWAY
```

키는 터미널에서 숨김 입력합니다. 관리자가 발급한 자기 계정의 기기 키를 사용하세요.
프로필은 서버·계정에 묶입니다. 대상이 다르면 새 프로필을 만들며 대기 전송함을 다른
서버로 몰래 보내지 않습니다. 별도 서버 연결과 로컬 설치를 동시에 중복 등록하지 마세요.
서버 재부팅 후 시작은 운영자가 서비스 사용자로 `unified_setup.py ensure`를 실행하거나
[런타임 안내](UNIFIED-RUNTIME.ko.md)의 user systemd 서비스를 설정해야 합니다.

## 최초 엔진 설치용 모델 자산

모델 companion archive는 lean 클라이언트 번들과 별도입니다. 승인된 준비 디렉터리
또는 설치기가 소유·검증한 캐시를 사용하며 모델을 자동으로 네트워크 다운로드하지 않습니다.
companion을 풀면 `model/`을 `--reranker-dir`로 전달합니다. 바깥의
`reranker-assets.sha256.json`, `LICENSE.Apache-2.0.txt`, `PROVENANCE.json`은
모델 디렉터리에 넣지 않습니다.

native `min_scores.reranker=0.003`은 사전 고정한 새 개발 세트에서만 선택한 경험적 기준입니다.
SQL cosine cutoff나 보편적으로 보정된 관련성 확률이 아니며 독립 출시 품질을
입증하지 않습니다. 과거 전역 E5 `0.84` 기준은 적용하지 않습니다.
모델 이름이나 다국어 표기만으로 한국어 검색 품질을 보장하지 않습니다.

`--reranker-dir`에는 정확히 다음 6개 파일만 있어야 합니다. 출처·라이선스는 밖에 둡니다.

```text
config.json
model.onnx
sentencepiece.bpe.model
special_tokens_map.json
tokenizer.json
tokenizer_config.json
```

그래프와 tokenizer는 번들의 `reranker-assets.sha256.json`으로 모두 고정합니다.
모델은 `BAAI/bge-reranker-v2-m3`,
revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`입니다.
최종 `model.onnx` SHA-256은
`cfc1a4de75f13cd68467b84bddbe2f9b87033782e9bbef43f7f85292758c0af1`입니다.
고정 원본 safetensors를 Core의 `python deploy/unified-core/prepare_reranker.py --source /absolute/pinned-source --output /absolute/prepared-reranker`로 준비합니다.
FP16 가중치·eager encoder·FP32 Sigmoid 출력의 단일 파일 그래프이며 외부 런타임 텐서는 없습니다.
준비된 6개 파일은 `python build-reranker-bundle.py --model-dir /absolute/prepared-reranker --output /absolute/new-companion`으로 포장합니다.
자세한 실행·점수 계약은 [판단·검색 계약](GENERATION-CONTRACT.ko.md)을 따릅니다.

## 계약·검증·제한

- [공급자별 통합·출처·수정·삭제 계약](GENERATION-CONTRACT.ko.md)
- [런타임·실행 위치·이전·복구 안내](UNIFIED-RUNTIME.ko.md)
- [초기 근거 구간 처리 계약](MEMORY-CONTRACT.md)
- [이전 0.2.1 안내](README-0.2.1.ko.md) — 이번 엔진의 설치 방법이 아닙니다.

기본 설치 위치는 `~/.local/share/agents-memory-unified`입니다. 이전 설치 데이터는
자동 가져오기·재분류·삭제하지 않습니다. 현재 프롬프트 후보를 수집하며 모든 대화 이력·
도구 출력의 자동 수집을 주장하지 않습니다. 서버 운영자는 원문을 읽을 수 있습니다.
개인 기억은 공유 매핑을 설정하기 전 팀에 공개되지 않습니다. 검색 제외·삭제 전파와
백업/과거 로그의 원문 파기는 별개의 정책입니다. E2EE 서비스가 아닙니다.

사용자는 독립 품질 실패를 확인한 뒤 시험 릴리즈 배포만 승인했습니다.
새 독립 v43의 정당한 명시 저장 70/80·이어가기 Hit@5 30/40은 고정 Wilson 하한
기준에 실패했고 필수 근거 전체 회수는 2/40입니다. 이전 v22/v27 실패도 보존합니다.
수치 일치나 패키지 구성은 검색 품질 증명이 아니며 정식 출시·100점·품질 통과가 아닙니다.
소유한 임시 Mac에서 genuine 설치·업데이트와 실제 shipping connector의 저장·회상,
업데이트 후 세 앱 등록 명령의 동일 ID·revision·전체 원문 회상을 검증했습니다.
이는 GUI·실제 회사 모델 추론이나 각 앱의 자동화 실행 증거가 아닙니다.
`service_ready/server_ready=true`라도 요청한 자동화 실행이 미검증이면 `ready=false`입니다.

엔진 번들은 Apple Silicon macOS 15+ 및 glibc Linux x64용입니다. Windows는 WSL2 x64
Linux 홈에 설치하는 경로이며 native Windows는 지원 검증되지 않았습니다. thin 원격
클라이언트는 macOS x64·arm64, glibc Linux x64·arm64용입니다. 실제 실행한 플랫폼과
미검증 플랫폼을 릴리즈 검증 보고서에서 구분합니다. 바이트코드 코어는 원본 Python 소스를
배포하지 않지만 암호화·역공학 방지를 보장하지 않습니다.
