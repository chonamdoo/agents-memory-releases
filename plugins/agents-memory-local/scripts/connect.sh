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
  Darwin:arm64) binary=connector-darwin-arm64; checksum=bb360af7bc456735059e3fc534760113075b6c2d97b075eedc68d5b8053a4762 ;;
  Linux:x86_64) binary=connector-linux-x86_64; checksum=e423eeeb591b49445d8f86bf9539749b68f335d61899733d96ce53386b02e1db ;;
  *) echo 'agents-memory-local: Apple Silicon macOS 15+ is required; see the setup guide.' >&2; exit 64 ;;
esac
verify "$root/bin/$binary" "$checksum"
verify "$root/scripts/setup.py" e692f9f4edc323c455e019223194b5bbbe3e32d563f071e743a91be084cd48d9
exec "$root/bin/$binary" --prefix "$prefix" --helper "$root/scripts/setup.py" --project "$project"
