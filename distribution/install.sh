#!/usr/bin/env bash
# Select storage/connection mode; generation-provider choice stays local.
set -euo pipefail
am_distribution="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
am_mode=""
am_arguments=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      [[ $# -ge 2 && -z "$am_mode" ]] || { echo 'Use --mode local|personal-server once.' >&2; exit 2; }
      am_mode="$2"; shift 2 ;;
    --mode=*)
      [[ -z "$am_mode" ]] || { echo 'Use --mode once.' >&2; exit 2; }
      am_mode="${1#--mode=}"; shift ;;
    --help|-h)
      cat <<'HELP'
Usage: bash distribution/install.sh --mode local|personal-server [client options]
  local           Personal local memory: existing local LLM or Jev, stable 1.0.7 installer.
  personal-server Connect to your own server: URL + device key, collaboration 0.2.1 client.
Without --mode, choose interactively. Other options pass to the selected installer.
Local:  --client claude|codex|omp --project /absolute/project --provider jev|local-llm
Server: --client claude|codex|omp|all --project /absolute/project --url https://YOUR_HOST
This package does not create or bill cloud infrastructure. Server operators use
distribution/server/bootstrap.sh. Existing memory is not moved automatically.
HELP
      exit 0 ;;
    *) am_arguments+=("$1"); shift ;;
  esac
done
if [[ -z "$am_mode" ]]; then
  if [[ ! -t 0 ]]; then
    echo 'Pass --mode local|personal-server, or run the downloaded package in a terminal.' >&2
    exit 2
  fi
  echo '기억 저장·연결 방식을 선택하세요.' >&2
  echo '1) 개인 로컬 — 기존 로컬 LLM 또는 Jev 사용' >&2
  echo '2) 본인 서버 연결 — 서버 주소·기기 키 사용' >&2
  read -r -p '선택 [1]: ' am_choice
  case "$am_choice" in
    ''|1) am_mode=local ;;
    2) am_mode=personal-server ;;
    *) echo 'Choose 1 or 2.' >&2; exit 2 ;;
  esac
fi
case "$am_mode" in
  local) am_entry="$am_distribution/mcp-local/install.sh" ;;
  personal-server) am_entry="$am_distribution/server/install-client.sh" ;;
  *) echo 'Unknown mode. Choose local or personal-server.' >&2; exit 2 ;;
esac
[[ -f "$am_entry" ]] || { echo 'Extract the complete release package before running this installer.' >&2; exit 2; }
exec bash "$am_entry" "${am_arguments[@]}"
