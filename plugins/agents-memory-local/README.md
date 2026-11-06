# agents-memory-local 2.0.0

기존 플러그인 이름으로 공통 Hindsight 엔진에 연결합니다. Claude·Codex·omp는
MCP·훅·압축 문맥 연결 앱이며, 저장 판단은 Jev만 사용합니다. 구독 CLI 판단과
공급자 선택 메뉴는 제거했습니다. native CLI 자동 대체나 과거 엔진으로의 복귀는 없습니다.
`agents-memory-unified`와 같은 프로젝트에 중복 설치하지 마세요.

[2.0.0 설치·업데이트·세 앱 안내](../../distribution/server/README.ko.md)를 따르세요.
2.0.0은 미공개·비공개 QA이며 마켓플레이스 공개나 실제 앱 설치 성공을 주장하지 않습니다.
기존 Jev 선택 모델을 보존하며, 과거 native 공급자 설정은 번들 설치기에
`--provider jev`를 명시해 전환합니다. 키는 비공개 파일·숨김 입력으로 제공하고
stdout·채팅에 출력하지 않습니다. 기존 DB·키를 삭제하거나 과거 데이터를 자동 재처리하지 않습니다.

최초 엔진 설치에는 별도 companion의 정확한 6파일 모델 디렉터리를
`--reranker-dir`로 제공해야 합니다. 원격 `--connect-server` 클라이언트에는
모델·bootstrap이 필요 없습니다. 모델 자동 다운로드는 하지 않습니다.
과거 독립 v22 품질 기준은 실패했고 새 ONNX 경로의 독립 품질 검증도 남아 있습니다.
