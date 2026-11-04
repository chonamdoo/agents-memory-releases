# 1.0.8 개발 현황 — 배포 전

안정 릴리즈는 1.0.7입니다. Windows 네이티브 지원은 아직 완료하지 않았으며 1.0.8 태그·안정 릴리즈는 만들지 않았습니다.

Claude·Codex·OMP 설치와 업데이트 안내를 함께 정리했습니다. 세 CLI의 직접 MCP 연결·10개 도구를 Linux에서 확인했습니다. Python 98개, Go 9개와 race 검사, ruff, PowerShell 문법과 모의 WSL 경계, Docker Compose 두 OS 설정 검사를 통과했습니다. 실제 Linux DB에서 pgvector 0.8.7 로드와 벡터 계산, API/MCP, 소유 프로세스 시작·중지·재시작 및 DB 식별자·키·설정 보존도 확인했습니다.

Windows 목표는 ego-lite와 같이 네이티브 x64 실행입니다. WSL2 경로는 별도 프리뷰로 구분합니다. Windows 코어·DB 확장·설치기와 실제 Windows 10/11 검증은 남았습니다. Docker로 Windows VM을 돌릴 구성은 준비했지만 현재 환경에는 KVM이 없고 공간도 부족해 실행하지 못했습니다. 새 클라우드를 만드는 권한이나 외부 계정도 아직 연결되지 않았습니다.

GitHub Actions는 실행하지 않았습니다. 세부 증거와 검증 한계는 VERIFICATION.json에 기록했습니다.
