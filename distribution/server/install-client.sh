#!/usr/bin/env bash
set -euo pipefail
umask 077
# Run from the downloaded/reviewed server distribution. No DB or model is
# installed on the client; uv manages the small Python runtime automatically.
am_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$am_source/ASSETS.json" ]; then
  printf '%s\n' 'ASSETS.json과 core·SDK wheel이 포함된 unified client bundle에서 실행하세요.' >&2
  exit 1
fi
case "$(uname -s)" in
  Darwin) am_default="$HOME/Library/Application Support/agents-memory-cloud" ;;
  Linux) am_default="${XDG_DATA_HOME:-$HOME/.local/share}/agents-memory-cloud" ;;
  *) printf '%s\n' 'Windows에서는 WSL2의 Linux 터미널에서 실행하세요.' >&2; exit 1 ;;
esac
am_prefix="${AM_COLLAB_CLIENT_ROOT:-$am_default}"
if [ -L "$am_prefix" ]; then
  printf '%s\n' '클라이언트 설치 폴더는 심볼릭 링크일 수 없습니다.' >&2; exit 1
fi
mkdir -p "$am_prefix"
chmod 700 "$am_prefix"
am_uv="$(command -v uv || true)"
if [ -z "$am_uv" ]; then
  # Pinned upstream binary, checked before execution. No remote shell script.
  case "$(uname -s)/$(uname -m)" in
    Darwin/arm64) am_target=aarch64-apple-darwin; am_sha=50487ae565ccd96e499056b4674d438f4c53170202617b4c759defe0c6a1b544 ;;
    Darwin/x86_64) am_target=x86_64-apple-darwin; am_sha=960da44cb4b73685206ddd250b19e0a117fa41095710c1038f081f5cb613efb4 ;;
    Linux/x86_64) am_target=x86_64-unknown-linux-gnu; am_sha=9167d72b3319674b6303c4cbe071854bba13ebdf3d76b1a7cbdc175471fb66d6 ;;
    Linux/aarch64) am_target=aarch64-unknown-linux-gnu; am_sha=6524bd338177ed50d035d39354e12545e993bbeba2ecbddf0480c5b3a81d313f ;;
    *) printf '%s\n' '지원 대상은 macOS와 glibc Linux/WSL2 x64·arm64입니다.' >&2; exit 1 ;;
  esac
  am_tmp="$(mktemp -d "$am_prefix/uv-download.XXXXXX")"
  trap 'rm -rf -- "$am_tmp"' EXIT
  curl -fLSs --retry 2 --connect-timeout 15 --max-time 180 \
    "https://github.com/astral-sh/uv/releases/download/0.12.23/uv-$am_target.tar.gz" -o "$am_tmp/uv.tar.gz"
  if command -v sha256sum >/dev/null 2>&1; then
    am_actual="$(sha256sum "$am_tmp/uv.tar.gz" | cut -d ' ' -f 1)"
  else
    am_actual="$(shasum -a 256 "$am_tmp/uv.tar.gz" | cut -d ' ' -f 1)"
  fi
  [ "$am_actual" = "$am_sha" ] || { printf '%s\n' 'uv 체크섬 검증 실패' >&2; exit 1; }
  tar -xzf "$am_tmp/uv.tar.gz" -C "$am_tmp"
  mkdir -p "$am_prefix/tools"
  [ ! -L "$am_prefix/tools" ] && [ ! -L "$am_prefix/tools/uv" ] || exit 1
  cp "$am_tmp/uv-$am_target/uv" "$am_prefix/tools/uv"
  chmod 700 "$am_prefix/tools/uv"
  am_uv="$am_prefix/tools/uv"
  rm -rf -- "$am_tmp"
  trap - EXIT
fi
printf '%s\n' '클라우드 MCP 클라이언트를 준비합니다. 기존 연결 설정과 기억은 유지합니다.' >&2
"$am_uv" venv --python 3.12 --allow-existing "$am_prefix/venv"
am_wheels="$(mktemp "$am_prefix/client-wheels.XXXXXX")"
trap 'rm -f -- "$am_wheels"' EXIT
"$am_prefix/venv/bin/python" -I - "$am_source" > "$am_wheels" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

bundle = Path(sys.argv[1]).resolve(strict=True)
manifest = json.loads((bundle / "ASSETS.json").read_text())
script = bundle / "unified_setup.py"
source = script.read_bytes()
if script.is_symlink() or hashlib.sha256(source).hexdigest() != manifest["files"].get("unified_setup.py"):
    raise SystemExit("Release helper integrity check failed")
namespace = {"__file__": str(script), "__name__": "unified_client_asset_review"}
exec(compile(source, str(script), "exec"), namespace)
sys.stdout.write(namespace["client_requirements"](bundle))
PY
"$am_uv" pip sync --python "$am_prefix/venv/bin/python" --link-mode copy \
  --reinstall-package agents-memory-collaboration --require-hashes "$am_source/client-requirements.lock" "$am_wheels"
rm -f -- "$am_wheels"
trap - EXIT
exec "$am_prefix/venv/bin/python" -I -m agents_memory_collab.cli setup --root "$am_prefix" "$@"
