# Windows PC 없이 Docker로 검증하기

[dockur/windows](https://github.com/dockur/windows)는 **Linux 컨테이너 안에서 QEMU/KVM으로 실제 Windows VM을 실행**합니다. 일반 Linux 컨테이너에서 Windows 바이너리를 실행하는 방식과 다릅니다. 설치된 실제 Windows에서 네이티브 설치·MCP·DB·업데이트를 검증할 수 있으므로 물리 Windows PC가 꼭 필요하지 않습니다.

## 필요한 테스트 호스트

- KVM과 `/dev/kvm`, `/dev/net/tun`을 사용할 수 있는 Linux x86_64 호스트
- Docker Compose v2, 한 번에 한 VM에 RAM 8GB·CPU 4개 할당
- Docker 저장소 여유 최소 32GB. 가상 디스크 크기는 VM마다 64GB이며 두 OS는 별도 볼륨 사용
- 정상적인 Windows 설치 미디어 다운로드와 적절한 사용 라이선스

가상 Linux 서버에서 KVM 가속을 쓰려면 중첩 가상화를 제공해야 합니다. Mac Docker Desktop과 현재 관리형 작업 컨테이너에는 KVM이 없습니다. **가속이 없어도 아래 TCG 경로로 실제 Windows를 실행할 수 있으며 훨씬 느립니다.** Wine은 보조 검사로 사용할 수 있지만 Windows 설치·ACL·프로세스·MCP의 최종 검증으로 계산하지 않습니다.

이 폴더는 테스트 인프라입니다. 제품 사용자에게 Docker나 WSL 설치를 요구하는 네이티브 Windows 배포물이 아닙니다.

## 실행

Linux Docker 호스트에서:

```sh
cd tools/windows-vm
bash check-host.sh
docker compose --profile win11 up -d win11
```

호스트의 `http://127.0.0.1:8006`에서 Windows 자동 설치 진행을 봅니다. 원격 서버에서는 SSH 포트 전달로 접근합니다. 데스크톱의 `agents-memory-test/HOST.json`은 Windows 환경 정보만 기록하며 제품 검증 성공을 뜻하지 않습니다. 초기화 계정은 upstream 기본값이므로 필요하면 upstream 안내에 따라 테스트 계정을 지정합니다.

Windows 11 검증 후 중지하고 10을 별도로 시작합니다. 둘은 같은 포트를 사용하므로 동시에 띄우지 않습니다.

```sh
docker compose --profile win11 stop win11
docker compose --profile win10 up -d win10
```

`stop`이나 `down`은 테스트 볼륨을 유지합니다. `down -v`는 저장된 Windows 설치와 테스트 DB를 지우므로 업데이트·보존 검증 도중 사용하지 않습니다. Docker wrapper의 Linux amd64 이미지는 OCI digest로 고정했습니다. Windows 설치 미디어와 실제 OS 빌드는 별도로 검증 기록에 남겨야 합니다.

## 제품 검증은 별도

현재 agents-memory Windows 네이티브 코어·설치기는 없습니다. 이 VM 구성만으로 Windows 지원 완료를 선언하지 않습니다. 네이티브 빌드가 준비되면 Windows 자체에 설치한 Claude·Codex·OMP에서 최초 설치, Jev/구독 모델 선택, E5 검색, 실제 DB 준비 후 ready=true, 기억 저장/새 세션 검색, 재시작, 업데이트 후 키·DB 보존을 실행하고 결과를 기록해야 합니다. 대상은 [Windows 지원 기준](../../distribution/mcp-local/WINDOWS-SUPPORT.ko.md)입니다.

## KVM이 없는 현재 환경: TCG 대체 경로

```sh
bash check-host.sh --tcg
docker compose -f compose.tcg.yaml up -d
```

TCG는 `KVM=N`과 `NETWORK=user`를 사용합니다. `/dev/kvm`, `/dev/net/tun`, `NET_ADMIN` 없이 Windows 자체를 실행합니다. `http://127.0.0.1:18006`에서 설치 화면을 확인합니다. 기본 OS는 Windows 10 Enterprise 평가판(`10e`)이며 `AM_WINDOWS_VERSION=11` 등으로 새 VM의 OS를 고를 수 있습니다. 서로 다른 OS에 같은 저장 볼륨을 재사용하지 마세요.

2026-11-04 현재 환경에서는 작업 중복 파일·패키지 캐시를 정리했고, Docker vfs의 중복 레이어도 고정된 원본 이미지의 파일시스템을 export/import하여 줄였습니다. 원본 OCI digest와 로컬 이미지 ID를 기록했으며 Docker 저장 드라이버는 바꾸지 않았습니다. **TCG로 실제 Windows 10 22H2 x64(빌드 19045)의 데스크톱까지 부팅했습니다.** Windows PowerShell 5.1에서 네이티브 실행 파일로 인자를 전달할 때 따옴표가 사라지는 문제를 재현하고, 프로젝트 경로를 UTF-8/base64로 전달해 수정했습니다. 공백·따옴표·한글 경로와 세 앱 선택값 보존을 확인했습니다. 이 검사는 가짜 wsl.exe를 사용한 인자 전달 검사이며 실제 WSL 설치나 메모리 제품 검증이 아닙니다.

새 Windows의 PostgreSQL 프로토타입은 Microsoft VC 런타임 DLL 누락으로 시작하지 못했습니다(`0xc0000135`). 제품 설치기가 해당 의존성을 자동 준비하도록 구현·검증해야 합니다. 평가판 만료도 확인되어 Windows 11의 적절한 새 평가 환경과 전체 제품 검증이 남았습니다. [검사 증거](../../release-candidates/v1.0.8/WINDOWS-VM-PROBES.json)를 참고하세요.

### 테스트 디스크 재시작 보호

첫 VM에서는 설치 래퍼의 `windows.boot` 표시가 없는 상태에서 다시 시작하면서 임시 테스트 디스크가 재초기화됐습니다. 검사 결과는 별도 파일로 보존했습니다. 현재 Compose는 `start-guard.sh`를 통해 기존 디스크가 있는데 표시가 없으면 시작을 거부합니다. 설치 미디어나 `windows.*` 상태 파일을 수동 삭제하지 마세요. 이 오류에서는 디스크를 백업하고 실제 부팅 상태를 조사한 뒤 복구해야 합니다. 확인 없이 표시 파일을 만들어 검사를 우회하지 마세요.

현재 VM은 중지 상태입니다. 디스크 여유가 3GiB 미만으로 줄면 이 VM만 일시 정지해 다른 데이터에 영향을 주지 않도록 감시했습니다. GitHub Actions와 외부 유료 클라우드는 사용하지 않았습니다.
