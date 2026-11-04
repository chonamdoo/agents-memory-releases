# Claude · Codex · OMP 로컬 MCP 설치 (1.0.8)

> **개발 중인 1.0.8 초안입니다. 현재 안정 버전은 1.0.7입니다. Windows 네이티브 배포는 아직 완료되지 않았습니다.** [Windows 목표·진행 상태](WINDOWS-SUPPORT.ko.md)

Apple Silicon macOS 15+에서 자동 로컬 설치를 제공합니다. Windows x64에는 WSL2 설치 경로를 프리뷰로 추가했습니다. 실행 코어·E5 검색 임베딩·전용 PostgreSQL/pgvector·API를 포함하며 Docker·Colima·별도 Python 설치가 필요하지 않습니다.

처음 한 번 **Jev / 구독 Claude / 구독 Codex**를 선택합니다. Jev는 로컬 설정 화면이나 설치 터미널에서 숨김 입력으로 키를 받습니다. 구독 모델은 설치·로그인된 CLI를 사용하며 추천 모델은 Claude Sonnet 5.5(`claude-sonnet-5-5`), Codex 6.1 Terra(`gpt-6.1-terra`)입니다. **MCP 연결 앱 선택과 기억 저장 판단 모델 선택은 별개**입니다. OMP는 판단 모델 제공자가 아닙니다.

설치·업데이트 후 앱을 다시 시작하고 `setup_status`에서 `version: 1.0.8`, `ready: true`를 확인하세요. 설치·연결 자체에서는 판단 LLM을 호출하지 않습니다. 검색용 다국어 E5 임베딩은 포함하며 생성 모델 가중치를 설치하지 않습니다.

## Claude Code 설치와 업데이트

실제 프로젝트에서 실행합니다.

```sh
claude plugin marketplace add chonamdoo/agents-memory-releases
claude plugin install agents-memory-local@agents-memory
```

Claude 대화창에서는 `/plugin marketplace add ...`, `/plugin install ...`을 사용할 수 있습니다.

업데이트:

```sh
claude plugin marketplace update agents-memory
claude plugin update agents-memory-local@agents-memory
```

Claude를 다시 시작하고 프로젝트 신뢰와 MCP 실행을 승인하면 자동 준비합니다. 처음에는 브라우저에서 LLM을 선택하고 Jev라면 키를 입력합니다. 브라우저가 열리지 않으면 `setup_status.setup_url`의 이 PC 주소를 여세요. 설치기가 앱 신뢰 설정을 강제로 승인하지 않습니다.

## Codex 설치와 업데이트

프로젝트에 직접 MCP를 등록하는 도우미를 사용합니다. **설치와 업데이트 명령은 같습니다.**

```sh
curl -fsSL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.8/distribution/mcp-local/install.sh -o /tmp/agents-memory-mcp-install.sh
bash /tmp/agents-memory-mcp-install.sh --client codex --project "$PWD"
```

처음에는 터미널에서 LLM을 선택하며 Jev 키는 숨김 입력입니다. Enter 뒤 설치 단계가 표시됩니다. 완료 후 Codex를 다시 시작하고 프로젝트 신뢰·MCP 사용을 승인합니다. 이후 MCP 연결은 저장된 설정을 재사용합니다.

현재 Codex 0.163.0의 마켓 플러그인은 Claude용 경로 변수를 확장하지 않습니다. 별도 네이티브 플러그인 형식도 프로젝트 경로 대신 플러그인 경로를 전달하므로, 이 배포에서는 위 직접 등록을 안내합니다. `codex plugin add` 설치 성공만으로 메모리 연결 성공을 판단하지 않습니다.

## OMP 설치와 업데이트

```sh
omp plugin marketplace add chonamdoo/agents-memory-releases
omp plugin install agents-memory-local@agents-memory
```

업데이트는 마켓 갱신부터 실행합니다.

```sh
omp plugin marketplace update agents-memory
omp plugin upgrade agents-memory-local@agents-memory
```

마켓 갱신 없이 upgrade만 실행하면 예전 캐시 버전이 다시 설치될 수 있습니다. OMP를 완전히 종료한 뒤 프로젝트에서 다시 실행하세요. 최초 연결은 브라우저에서 LLM을 선택하고 Jev 키를 입력합니다. 브라우저가 열리지 않으면 `setup_status.setup_url`을 확인합니다.

## Windows WSL2 설치 (프리뷰)

이번 Windows 경로는 **Windows x64 + WSL2 + Ubuntu 24.04**, 그리고 **같은 WSL 안에 설치·로그인한 Claude·Codex·OMP CLI**를 대상으로 합니다. 메모리 코어·DB·키도 해당 WSL의 사용자 홈에 저장합니다. Windows에 설치한 네이티브 앱이나 다른 WSL 배포판의 로그인·설정과 자동 공유하지 않습니다. WSL1·Windows ARM64·`/mnt/c` 프로젝트는 이 도우미의 지원 범위가 아닙니다.

WSL이 없다면 관리자 PowerShell에서 한 번 실행합니다. 재시작 안내가 나오면 재시작하고 Ubuntu를 처음 열어 일반 Linux 사용자를 만드세요.

```powershell
wsl --install -d Ubuntu-24.04
```

Ubuntu 안에서 실제 프로젝트를 준비하세요(예: `/home/your-user/projects/app`). PowerShell에서 다음을 실행하면 세 앱의 프로젝트 MCP 설정을 한 번에 등록합니다. `your-user`와 프로젝트 경로는 실제 경로로 바꿉니다.

```powershell
Invoke-WebRequest -Uri https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.8/distribution/mcp-local/install-wsl.ps1 -OutFile "$env:TEMP\agents-memory-install-wsl.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$env:TEMP\agents-memory-install-wsl.ps1" -Project "/home/your-user/projects/app"
```

한 앱만 등록하려면 두 번째 명령에 `-Client claude`, `-Client codex` 또는 `-Client omp`를 추가합니다. 다른 배포판은 `-Distro 배포판이름`을 지정합니다. 도우미는 WSL 버전·CPU·프로젝트를 확인하고 고정된 SHA256으로 Linux 설치기를 검증합니다. WSL/배포판을 몰래 새로 만들거나 기본 배포판·Docker 컨텍스트를 바꾸지 않습니다.

Ubuntu 터미널에서 직접 설치하려면 해당 프로젝트에서 위 Codex 설치 블록의 마지막 줄을 다음처럼 실행할 수도 있습니다.

```sh
bash /tmp/agents-memory-mcp-install.sh --client claude --client codex --client omp --project "$PWD"
```

설치와 업데이트는 같은 명령입니다. Claude·Codex·OMP도 같은 Ubuntu 안에서 실행하고 다시 연결하세요. DB와 API는 WSL 안에서 실행하며 localhost에만 연결합니다. WSL을 종료하면 서비스도 중지되고 다음 MCP 연결에서 다시 준비합니다. 초기 설정 브라우저 자동 열기는 WSL의 Windows interop가 필요하며, 열리지 않으면 `setup_status.setup_url`을 Windows 브라우저에 입력합니다.

**검증 범위:** Linux의 실제 DB/API·MCP 실행과 PowerShell 파서/프로세스 경계 모의 검증을 수행합니다. 실제 Windows의 WSL 설치·브라우저 열기·CLI 실행은 아직 검증하지 않았습니다. WSL 없는 Windows 네이티브 설치는 현재 제공하지 않습니다. 목표 사양은 Windows 11 x64 우선, Windows 10 22H2 호환성 검증, ARM64 추후 검토입니다. 이는 현재 지원 완료를 뜻하지 않습니다.

## 직접 등록과 설정 보존

macOS에서 직접 Claude 연결은 `--client claude`, OMP는 `--client omp`를 사용합니다. `--client`를 반복하면 여러 앱에 등록합니다. 플러그인과 직접 등록을 중복 추가할 필요는 없습니다.

`.mcp.json`, `.codex/config.toml`, `.omp/mcp.json`의 다른 서버·모델·명시적 비활성화를 보존하고 변경 전에 백업합니다. 같은 이름의 다른 명령을 덮어쓰지 않습니다. 홈 폴더 전체를 기억 프로젝트로 등록하지 않습니다.

## 저장·중지·업데이트

키·설정·DB·프로젝트 정보는 macOS 또는 WSL의 `~/.local/share/agents-memory-hindsight`에 사용자 전용으로 저장합니다. 플러그인 캐시와 분리되며 플러그인 업데이트·제거가 기억 데이터를 지우지 않습니다. Jev 키는 0600 파일이며 Keychain 암호화 저장은 아닙니다.

```sh
AM="$HOME/.local/share/agents-memory-hindsight/bin/am-mcp"
"$AM" status
"$AM" stop
"$AM" start
```

`stop`은 전용 DB/API를 중지하고 자동 재시작 금지 상태를 남깁니다. `start`로 다시 활성화합니다. macOS는 LaunchAgent가 API를 관리하며 WSL2는 해당 배포판의 사용자 프로세스로 관리합니다. 최초 다운로드에는 네트워크와 수 분이 필요합니다.

`setup_status.logs`에서 setup / operations / postgres / service 로그 경로를 확인할 수 있습니다. macOS 설정 로그는 `~/Library/Caches/agents-memory-setup/setup.log`, WSL은 `~/.cache/agents-memory-setup/setup.log`입니다. 오류 뒤 MCP를 다시 연결하면 완료한 실행 환경과 저장 설정을 재사용합니다. macOS의 정상 원본 `vector.so`를 가리키는 수동 복구 링크도 검증 후 동일 바이트의 실제 `vector.dylib`로 원자 교체합니다.

과거 Docker/외부 DB 영수증은 보존하며 새 빈 DB로 자동 전환하지 않습니다. 다른 프로젝트의 DB·Docker 컨텍스트·Colima를 수정하지 않습니다. 코어는 컴파일된 1.0.2를 재사용하며 배포물과 네이티브 DB는 SHA256을 고정합니다. macOS 바이너리는 ad hoc 서명이며 Developer ID 서명·공증은 아닙니다.

## 새 세션에서 기억 사용

연결 지침과 `recall` 도구 설명은 새 세션의 첫 본격적인 답변 전에 해당 프로젝트의 관련 장기 기억을 조회하도록 안내합니다. 빈 결과라면 관련 키워드로 `list_memories`를 추가 확인하도록 하며, PR 작업에서는 저장된 리뷰어·담당자 규칙과 실제 결과를 비교하도록 안내합니다. OMP 직접 등록에서는 이 서버의 지침 전달을 활성화합니다.

이는 호스트 모델에 전달하는 조회 지침입니다. MCP 서버가 다른 앱의 모든 응답이나 PR 생성 도구 실행을 강제로 통제하는 것은 아니므로, 저장된 규칙이 반드시 적용됐다는 판단은 실제 조회·작업 결과를 확인해야 합니다. 다른 프로젝트로 세션을 열면 프로젝트별 기억 범위도 달라집니다. 이력 파일 스캔이나 대화 자동 저장을 켜지는 않습니다.

## 별도 Native 기억 서버가 남아 있는 경우

예전 `~/.agents-memory/<namespace>`의 Native 서버와 현재 `~/.local/share/agents-memory-hindsight`의 Hindsight 서버는 별도 저장소입니다. 한쪽에 저장된 기억이 다른 쪽에 자동으로 합쳐지지는 않습니다. 이번 복구는 현재 Hindsight 런타임만 대상으로 하며, 예전 Docker DB·API·기억 데이터는 변경하지 않습니다. 새 세션에서 과거 규칙이 안 보이면 조회한 서버와 프로젝트 범위를 먼저 확인해야 합니다.

1.0.8의 `setup_status.logs`는 설정·키 파일을 열지 않고 확인할 수 있는 setup / operations / postgres / service 로그의 정확한 경로를 제공합니다.
