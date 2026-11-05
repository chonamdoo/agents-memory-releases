#!/bin/bash
set -euo pipefail
am_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) am_target=darwin-arm64 ;;
  Linux:x86_64) am_target=linux-x86_64 ;;
  *) echo '이 플러그인은 Apple Silicon macOS 또는 Linux/WSL2 x64용입니다. 다른 Mac은 원격 MCP 클라이언트 설치 안내를 사용하세요.' >&2; exit 2 ;;
esac
am_binary="$am_root/bin/connector-$am_target"
am_expected=$(awk -v name="connector-$am_target" '$2 == name {print $1}' "$am_root/bin/SHA256SUMS")
if command -v shasum >/dev/null 2>&1; then am_actual=$(shasum -a 256 "$am_binary"); else am_actual=$(sha256sum "$am_binary"); fi
[[ -n $am_expected && ${am_actual%% *} == "$am_expected" ]] || { echo 'MCP connector integrity check failed.' >&2; exit 2; }
exec "$am_binary" "$@"
