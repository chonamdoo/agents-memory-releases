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
  Darwin:arm64) binary=connector-darwin-arm64; checksum=208f7ae90ee0cac7938167864f068f70b1c9db649b7c6d2e99cb71c891de7077 ;;
  Linux:x86_64) binary=connector-linux-x86_64; checksum=7391be74e512e0883b93764fcc4ca35b69ef2f4e8264b63f5d4f235b8541f7fe ;;
  *) echo 'agents-memory-local: Apple Silicon macOS 15+ is required; see the setup guide.' >&2; exit 64 ;;
esac
verify "$root/bin/$binary" "$checksum"
verify "$root/scripts/setup.py" df7df48fb564722a83bfcee66d82ff82f44491d63fee4277df2c0fc1d18e569d
exec "$root/bin/$binary" --prefix "$prefix" --helper "$root/scripts/setup.py" --project "$project"
