# Windows 지원 기준 — ego lite 참고

상태: **네이티브 Windows 구현·배포 미완료. WSL2 설치 초안은 별도 프리뷰이며 이 기준을 충족한 것으로 계산하지 않습니다.** 1.0.8은 개발 중이며 현재 안정 릴리즈는 1.0.7입니다.

사용자가 지정한 참고 제품: [citrolabs/ego-lite](https://github.com/citrolabs/ego-lite).
2026-11-04에 확인한 [README](https://github.com/citrolabs/ego-lite/blob/main/README.md)는 Windows **x64 `.exe`**를 배포합니다. [설치 문서](https://github.com/citrolabs/ego-lite/blob/main/skills/ego-browser/references/install.md)는 Windows 설치기를 실행하고 GUI 초기 설정 후 새 PowerShell/cmd에서 명령을 확인하도록 안내합니다. WSL 설치는 요구하지 않습니다. 해당 두 문서는 정확한 최소 Windows 버전이나 RAM을 명시하지 않으므로 아래 사양은 ego lite의 확정 사양을 인용한 것이 아닌 **이 프로젝트의 목표**입니다.

## 첫 네이티브 버전의 목표

| 항목 | 목표 |
| --- | --- |
| OS | Windows 11 x64 우선 검증, Windows 10 22H2 x64 호환성 검증 |
| CPU | Intel/AMD 64비트 |
| 초기 제외 | Windows 7/8/8.1, 32비트 Windows, Windows ARM64 네이티브 |
| 설치 | 사용자별 `.exe` 설치기. WSL·Docker·Python·PostgreSQL 수동 설치 불필요 |
| 실행 앱 | Windows에 설치한 Claude Code / Codex / OMP |
| 터미널 | PowerShell 및 cmd. Bash 문법·Git Bash 설치를 요구하지 않음 |
| 첫 설정 | Jev 또는 구독 Claude/Codex 선택, Jev 키는 로컬 숨김 입력 |
| 기본 포함 | 로컬 DB, pgvector, API, 다국어 E5 검색 임베딩 |
| 생성 모델 | 로컬 생성 LLM 가중치 설치 없음. 지정한 Jev/구독 모델 이용 |
| 업데이트 | 키·모델·프로젝트·기존 DB·기억 보존, 앱별 업데이트 안내 |
| 준비 상태 | MCP는 설치 중에도 응답. 실제 DB/API 준비 후에만 ready=true |
| 자원 | RAM 8GB 최소 / 16GB 권장, 디스크 여유 5GB를 검증 목표로 설정. 최소 사양 확정은 실측 후 |

macOS Intel 지원은 이 Windows 요청에 자동으로 포함하지 않습니다. 기존 Apple Silicon macOS 배포는 유지합니다. 예전 Native 저장소와 Hindsight 기억을 자동 병합하거나 새 빈 DB로 교체하지 않습니다.

## 현재 완료한 부분

- Claude 설치·업데이트와 Codex 직접 MCP 설치·업데이트 경로를 OMP와 함께 문서화했습니다.
- PowerShell에서 WSL2 배포판을 지정해 세 앱을 등록하는 대체 경로를 작성했습니다.
- WSL1·ARM64·미설치 배포판을 설치 전에 거부하고, 경로를 셸 코드로 보간하지 않으며 설치기 SHA256을 고정합니다.
- Linux payload의 실제 DB/벡터/API/MCP와 서비스 시작·중지 및 업데이트 보존을 검증합니다. 이는 Windows 실행 검증과 구별합니다.

## 네이티브 출시 전에 남은 작업

현재 코어 배포물은 macOS arm64와 Linux x64이며 Windows 코어·DB 확장 배포물이 없습니다. 공개 설치기와 서비스 관리도 POSIX 권한·프로세스 API를 사용합니다. 파일 확장자를 `.exe`로 바꾸거나 WSL 설치기를 제공하는 것만으로 네이티브 지원을 선언할 수 없습니다.

Windows용 컴파일 코어·Python/의존성·PostgreSQL/pgvector를 해시로 고정하고 Windows ACL·잠금·프로세스 관리를 구현해야 합니다. Windows 설치·로그인된 Claude/Codex 호출과 세 MCP 앱의 실제 연결, 저장 후 다른 세션에서 검색, 기존 버전 업데이트 및 키/DB 보존을 Windows 10/11에서 검증한 뒤 네이티브 설치기를 공개합니다.

현재 작업 환경은 Linux이며 실제 Windows 실행 환경은 연결되어 있지 않습니다. PowerShell 7 파서와 모의 WSL 경계 검사는 Windows 10/11 실기 검증을 대신하지 않습니다. 이 조건이 해결되기 전에는 Windows 네이티브 안정 릴리즈를 만들지 않습니다. 사용자 지시에 따라 2026-12-01까지 GitHub Actions는 실행하지 않으며 Windows 빌드·검증도 별도 로컬 실행으로 수행해야 합니다.

## Windows PC가 없는 경우

별도 클라우드의 실제 Windows 10/11 x64 VM에서도 검증할 수 있습니다. Linux 호스트를 쓰려면 KVM을 제공하는 클라우드에서 [Docker 기반 Windows VM 구성](../../tools/windows-vm/README.ko.md)을 실행합니다. 일반 관리형 컨테이너나 Mac Docker Desktop에 컨테이너를 하나 더 추가하는 것만으로 KVM이 생기지는 않습니다.

실행 전 현재 환경의 실제 Docker 장치 전달도 검사했으며 `/dev/kvm` 부재로 실패했습니다. 새 클라우드 VM 생성 도구·외부 계정 자격 증명은 이 세션에 연결되어 있지 않습니다. 새 VM이 생성되었다거나 Windows 검증이 끝났다고 주장하지 않습니다. Windows 클라이언트 VM을 직접 제공하는 경우 OS·이미지·라이선스 조건과 비용을 확인하고, Linux VM이라면 중첩 가상화/KVM을 확인한 뒤 선택해야 합니다.
