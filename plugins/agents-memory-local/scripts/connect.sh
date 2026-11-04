#!/bin/bash
set -euo pipefail
umask 077
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
prefix="$HOME/.local/share/agents-memory-hindsight"
project=${CLAUDE_PROJECT_DIR:-$PWD}
verify() {
  local actual
  if command -v shasum >/dev/null 2>&1; then actual=$(shasum -a 256 "$1"); else actual=$(sha256sum "$1"); fi
  [[ ${actual%% *} == "$2" ]] || { echo 'agents-memory-local: connector integrity check failed; update this plugin.' >&2; exit 65; }
}
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) binary=connector-darwin-arm64; checksum=12d086652913c03de837437248a205980f9d997ff489ba60681ce5177d532979 ;;
  Linux:x86_64) binary=connector-linux-x86_64; checksum=b547489c5abd8b50defb471ffe160dc98f6e3a5bf199e522cdc14a636da8e795 ;;
  *) echo 'agents-memory-local: Apple Silicon macOS 15+ is required; see the setup guide.' >&2; exit 64 ;;
esac
verify "$root/bin/$binary" "$checksum"
verify "$root/scripts/setup.py" f2530e989a93d682974fd2d660ee3b158abd82ef136c2123c37423759927aa9a
exec "$root/bin/$binary" --prefix "$prefix" --helper "$root/scripts/setup.py" --project "$project"
