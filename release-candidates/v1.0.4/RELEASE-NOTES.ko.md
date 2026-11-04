# MCP 초기 설정 안내 수정 1.0.4

1.0.3에서 마켓 설치 후 로컬 런타임이 아직 없으면 `MCP subprocess closed stdout before responding`으로 종료되던 문제를 수정했습니다.

- 초기 설정 전에는 별도 Python·Node가 없어도 `setup_status` MCP가 연결됩니다. 기억이 준비되지 않았음을 `ready:false`로 명시하고 실제 프로젝트에서 수행할 설정 단계를 안내합니다. 연결만으로 다운로드·DB 생성·모델 호출·이력 읽기를 수행하지 않습니다.
- 런타임이 있지만 프로젝트가 미설정이거나 API가 꺼진 경우에도 상태와 다음 단계를 안내합니다. 명시적 중지는 존중합니다. 준비가 끝나면 기존 기억 도구 9개를 제공합니다.
- Jev 키 입력은 숨김임을 안내하고, Enter 확정 후 실행 환경·의존성 설치의 진행 상태를 표시합니다. DB 준비·프로젝트 초기화·API 시작도 진행 중인 단계를 주기적으로 표시합니다. 키와 로그 내용은 표시하지 않습니다.
- `~` 또는 `/`를 프로젝트로 지정하면 다운로드·키 입력 전에 중단하고 실제 프로젝트를 지정하도록 안내합니다. 과거 홈 폴더 설정을 모든 프로젝트의 기억 대상으로 사용하지 않습니다. 기존 설정과 데이터는 자동 삭제하지 않습니다.
- OMP 직접 등록은 이 플러그인의 가져온 별칭만 비활성화해 중복 연결을 막습니다. 다른 MCP와 모델·키 설정은 보존합니다. 판단 모델 선택은 여전히 Jev / 구독 Claude / 구독 Codex이며 OMP는 연결 대상입니다.

## 기존 OMP 설치 업데이트

일반 터미널에서:

```sh
omp plugin marketplace update agents-memory
omp plugin upgrade agents-memory-local@agents-memory
```

그다음 OMP에서 `/mcp reload`를 실행하세요. reload만으로 플러그인 버전이 업데이트되지는 않습니다.

초기 설정이 아직 끝나지 않았다면 Docker Desktop을 실행하고, **홈 폴더가 아닌 실제 작업 프로젝트**의 터미널에서:

```sh
curl -fsSL https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.4/distribution/mcp-local/install.sh -o /tmp/agents-memory-mcp-install.sh
bash /tmp/agents-memory-mcp-install.sh --client omp --project "$PWD"
```

Jev 키는 입력 중 보이지 않습니다. Enter로 확정한 뒤 설치 완료 메시지를 기다리세요. 이미 설치가 진행 중이면 중복 실행하지 마세요. 설치에 성공해 저장된 키와 provider/모델은 다시 묻거나 변경하지 않습니다.

[전체 설치 안내](https://github.com/chonamdoo/agents-memory-releases/blob/v1.0.4/distribution/mcp-local/README.ko.md)

로컬 검사 103개와 하위 검사 62개가 통과했습니다. OMP 18.16.0의 초기 런타임 없는 상태에서 안내 MCP 연결과 설정 후 9개 기억 도구 연결을 확인했습니다. 실제 터미널과 합성 설치기로 숨김 키 입력·Enter 확정·진행 표시를 검증했으며 실제 Jev API는 호출하지 않았습니다. Mac arm64 안내 실행 파일은 구조·최소 OS·ad hoc 서명 페이지 해시를 검사했습니다. macOS 실기 실행은 수행하지 않았습니다. 기반 기억 코어는 1.0.2로 유지합니다. GitHub Actions는 실행하지 않으며 2026-12-01까지 보류합니다.
