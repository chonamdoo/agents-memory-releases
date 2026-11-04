# Windows PC 없이 Docker로 검증하기

[dockur/windows](https://github.com/dockur/windows)는 **Linux 컨테이너 안에서 QEMU/KVM으로 실제 Windows VM을 실행**합니다. 일반 Linux 컨테이너에서 Windows 바이너리를 실행하는 방식과 다릅니다. 설치된 실제 Windows에서 네이티브 설치·MCP·DB·업데이트를 검증할 수 있으므로 물리 Windows PC가 꼭 필요하지 않습니다.

## 필요한 테스트 호스트

- KVM과 `/dev/kvm`, `/dev/net/tun`을 사용할 수 있는 Linux x86_64 호스트
- Docker Compose v2, 한 번에 한 VM에 RAM 8GB·CPU 4개 할당
- Docker 저장소 여유 최소 32GB. 가상 디스크 크기는 VM마다 64GB이며 두 OS는 별도 볼륨 사용
- 정상적인 Windows 설치 미디어 다운로드와 적절한 사용 라이선스

가상 Linux 서버라면 중첩 가상화를 제공해야 합니다. **Mac의 Docker Desktop과 현재 관리형 작업 컨테이너는 이 조건을 충족하지 않습니다.** Wine은 보조 검사로 사용할 수 있지만 Windows 설치·ACL·프로세스·MCP의 최종 검증으로 계산하지 않습니다.

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

2026-11-04 현재 작업 환경 확인: Docker Linux x86_64는 동작하지만 실제 `--device=/dev/kvm` 실행은 `no such file or directory`로 실패했습니다. 여유 디스크도 약 0.5GB로 부족합니다. **Windows VM은 실행하지 않았고 네이티브 Windows 테스트도 통과하지 않았습니다.** GitHub Actions도 실행하지 않았습니다.
