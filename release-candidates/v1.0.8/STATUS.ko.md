# 1.0.8 개발 현황 — 배포 전

안정 릴리즈는 1.0.7입니다. Windows 네이티브 지원은 아직 완료하지 않았으며 1.0.8 태그·안정 릴리즈는 만들지 않았습니다.

Claude·Codex·OMP 설치와 업데이트 안내를 함께 정리했습니다. 세 CLI의 직접 MCP 연결·10개 도구를 Linux에서 확인했습니다. Python 105개, Go 9개와 race 검사, ruff, PowerShell 문법과 모의 WSL 경계, Docker Compose 설정 검사를 통과했습니다. 실제 Linux DB에서 pgvector 0.8.7 로드와 벡터 계산, API/MCP, 소유 프로세스 시작·중지·재시작 및 DB 식별자·키·설정 보존도 확인했습니다.

현재 환경의 중복 테스트 파일·캐시를 정리해 별도 유료 클라우드 없이 Docker/QEMU TCG로 **실제 Windows 10 22H2 x64 데스크톱**을 부팅했습니다. PowerShell 5.1에서 네이티브 프로그램에 경로를 전달할 때 따옴표가 사라지는 문제를 재현·수정하고 공백·따옴표·한글 및 세 앱 선택값 보존을 확인했습니다. 해당 검사는 모의 wsl.exe를 사용했으므로 실제 WSL 설치나 전체 제품 검증을 뜻하지 않습니다.

네이티브 Windows PostgreSQL 프로토타입은 새 OS의 Microsoft VC 런타임 DLL 누락으로 시작하지 못했습니다. pgvector DLL은 교차 컴파일했지만 실제 SQL 로드 검사는 아직 통과하지 않았습니다. 평가판 만료와 재시작 시 임시 디스크 재초기화도 확인했습니다. VM은 중지했고 증거를 보존했으며, 테스트 Compose에 기존 표시 없는 디스크의 자동 덮어쓰기 거부 검사를 추가했습니다. 소스·기존 제품 DB·설정은 보존했습니다.

Windows 목표는 ego-lite와 같이 네이티브 x64 실행입니다. WSL2 경로는 별도 프리뷰로 구분합니다. Windows 코어·의존성 자동 설치·ACL/프로세스 관리·MCP 설치기와 Windows 10/11의 전체 제품 검증은 남았습니다.

GitHub Actions는 실행하지 않았습니다. 세부 증거와 검증 한계는 VERIFICATION.json 및 WINDOWS-VM-PROBES.json에 기록했습니다.
