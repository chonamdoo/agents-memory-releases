#!/usr/bin/env bash
# All locations use the common authenticated Hindsight gateway/client contract.
set -euo pipefail
am_distribution="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
am_mode=""
am_arguments=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 && -z "$am_mode" ]] || { echo 'Use --mode once.' >&2; exit 2; }
      am_mode="$2"; shift 2 ;;
    --mode=*)
      [[ -z "$am_mode" ]] || { echo 'Use --mode once.' >&2; exit 2; }
      am_mode="${1#--mode=}"; shift ;;
    --help|-h)
      cat <<'HELP'
Usage: bash distribution/install.sh --mode local|personal-server|team-server|company-server [client options]
All modes require the same common Hindsight engine contract.
  local           Connect to the local gateway (default http://127.0.0.1:18350).
  personal-server Connect to your personal gateway: URL + device key.
  team-server     Connect to your team's gateway: URL + device key.
  company-server  Connect to your company's gateway: URL + device key.
Without --mode, choose interactively. Other options pass to the selected installer.
Client: --client claude|codex|omp|all --project /absolute/project --url https://YOUR_HOST
The engine host selects Claude/Codex CLI or Jev; clients never bypass its judgment.
This client installer does not provision the engine or cloud infrastructure.
See distribution/server/UNIFIED-RUNTIME.ko.md before starting the engine.
Existing memory is not reprocessed automatically. The legacy 1.0.7 engine is not
an equivalent fallback for this unreleased common contract.
HELP
      exit 0 ;;
    *) am_arguments+=("$1"); shift ;;
  esac
done
if [[ -z "$am_mode" ]]; then
  if [[ ! -t 0 ]]; then
    echo 'Pass --mode local|personal-server|team-server|company-server.' >&2
    exit 2
  fi
  echo '기억 저장·연결 방식을 선택하세요.' >&2
  echo '1) 개인 로컬  2) 개인 서버  3) 팀 서버  4) 회사 서버' >&2
  echo '모두 같은 Hindsight 처리 엔진에 연결합니다.' >&2
  read -r -p '선택 [1]: ' am_choice
  case "$am_choice" in
    ''|1) am_mode=local ;;
    2) am_mode=personal-server ;;
    3) am_mode=team-server ;;
    4) am_mode=company-server ;;
    *) echo 'Choose 1, 2, 3 or 4.' >&2; exit 2 ;;
  esac
fi
case "$am_mode" in
  local) am_arguments=(--url http://127.0.0.1:18350 --profile local "${am_arguments[@]}") ;;
  personal-server) ;;
  team-server|company-server) am_arguments=(--profile "$am_mode" "${am_arguments[@]}") ;;
  *) echo 'Unknown deployment location.' >&2; exit 2 ;;
esac
am_entry="$am_distribution/server/install-client.sh"
[[ -f "$am_entry" ]] || { echo 'Extract the complete release package before running this installer.' >&2; exit 2; }
exec bash "$am_entry" "${am_arguments[@]}"
