#!/bin/sh
# Extracted, checksum-verified release bundle only. Does not change macOS security settings.
set -eu
bundle=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) target=darwin-arm64 ;;
  Linux:x86_64)
    case " $* " in *" --virtual-linux "*) target=linux-x86_64 ;; *) echo 'Linux is for explicit virtual validation only.' >&2; exit 2 ;; esac ;;
  *) echo 'This release supports Apple Silicon macOS 13 or newer.' >&2; exit 2 ;;
esac
if command -v shasum >/dev/null 2>&1; then
  (cd "$bundle" && shasum -a 256 -c SHA256SUMS >/dev/null)
else
  (cd "$bundle" && sha256sum -c SHA256SUMS >/dev/null)
fi
bootstrap=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-bootstrap.XXXXXXXX")
trap 'rm -rf -- "$bootstrap"' EXIT HUP INT TERM
tar -xzf "$bundle/runtimes/$target.tar.gz" -C "$bootstrap"
"$bootstrap/python/bin/python3" -I "$bundle/installer.py" --bundle "$bundle" "$@"
