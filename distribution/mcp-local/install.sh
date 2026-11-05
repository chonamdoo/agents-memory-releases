#!/bin/bash
# Compatible entry for the common 1.0.8 installer. Never starts the old engine.
set -euo pipefail
am_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --provider)
      [[ $# -gt 1 ]] || exit 2
      if [[ $2 == local-llm ]]; then shift 2; else am_args+=("$1" "$2"); shift 2; fi ;;
    --provider=local-llm) shift ;;
    --judge-host=*) am_args+=(--provider "${1#--judge-host=}"); shift ;;
    --judge-host)
      [[ $# -gt 1 ]] || exit 2
      am_args+=(--provider "$2"); shift 2 ;;
    --virtual-linux) shift ;;
    *) am_args+=("$1"); shift ;;
  esac
done
am_work=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-1.0.8.XXXXXXXX")
trap 'rm -rf -- "$am_work"' EXIT HUP INT TERM
curl --fail --silent --show-error --location --retry 2 --connect-timeout 20 --max-time 120 --proto '=https' --proto-redir '=https' --tlsv1.2 \
  https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.8/distribution/server/install-unified.sh -o "$am_work/install.sh"
if [[ -t 0 ]]; then bash "$am_work/install.sh" "${am_args[@]}"
elif { true </dev/tty; } 2>/dev/null; then bash "$am_work/install.sh" "${am_args[@]}" </dev/tty
else bash "$am_work/install.sh" "${am_args[@]}"; fi
