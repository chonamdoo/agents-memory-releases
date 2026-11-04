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
  Darwin:arm64) binary=connector-darwin-arm64; checksum=a8f45bdfab3ea38a8671e295ce13bd08c084ae411ae0683954385bc96d87c2c2 ;;
  Linux:x86_64) binary=connector-linux-x86_64; checksum=12f395e7f7bbde97a3f53fe974117eaecc27c137c3b45e7ab359df22e0b4abef ;;
  *) echo 'agents-memory-local: Apple Silicon macOS 15+ or Windows x64 WSL2 is required; see the setup guide.' >&2; exit 64 ;;
esac
verify "$root/bin/$binary" "$checksum"
verify "$root/scripts/setup.py" 92bdbada9691402748a607955c0242f00b44598536e153b5b6bc3c12982bf7cd
exec "$root/bin/$binary" --prefix "$prefix" --helper "$root/scripts/setup.py" --project "$project"
