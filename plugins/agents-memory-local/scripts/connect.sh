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
if [[ -x "$prefix/current/venv/bin/python" && -f "$prefix/PRODUCT.json" ]] &&
   "$prefix/current/venv/bin/python" -I -c "import mcp" >/dev/null 2>&1; then
  verify "$root/scripts/setup.py" 08b55bf0c33dcc8d881084e5c9b18905820ed9d8e648f320594b72a69cb5c4b9
  exec "$prefix/current/venv/bin/python" -I "$root/scripts/setup.py" --prefix "$prefix" proxy --project "$project"
fi
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) binary=setup-status-darwin-arm64; checksum=c3a43f670de31561b3ecb9cc5cfe71bde50dcdce7f1e066eaedfa418e7792624 ;;
  Linux:x86_64) binary=setup-status-linux-x86_64; checksum=7dadc3875b8f145e34e78b38e2261f81e2bfea6dc60a1c4374f3a44471dbefaa ;;
  *) echo 'agents-memory-local: Apple Silicon macOS 13+ is required; see the setup guide.' >&2; exit 64 ;;
esac
verify "$root/bin/$binary" "$checksum"
exec "$root/bin/$binary"
