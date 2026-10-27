#!/bin/bash
set -euo pipefail
umask 077
version=0.1.0-preview.20261027
expected=c727383185a3e7459971cb82a42987f8158ba00e4ad38303023db83f113aeca1
archive=${1:-agents-memory-macos-arm64.tar.gz}
prefix=${2:-"$HOME/.local/share/agents-memory/releases"}
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || { echo 'Requires macOS arm64.' >&2; exit 64; }
[[ $prefix == /* ]] || { echo 'Installation prefix must be absolute.' >&2; exit 64; }
[[ -f $archive && ! -L $archive ]] || { echo 'A regular release archive is required.' >&2; exit 66; }
actual=$(/usr/bin/shasum -a 256 "$archive"); actual=${actual%% *}
[[ $actual == "$expected" ]] || { echo 'Archive checksum mismatch.' >&2; exit 65; }
destination="$prefix/$version"
[[ ! -e $destination && ! -L $destination ]] || { echo 'This version already exists; refusing to overwrite.' >&2; exit 73; }
mkdir -p "$prefix"
temporary=$(mktemp -d "$prefix/.install.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
/usr/bin/tar -xzf "$archive" -C "$temporary"
[[ -x "$temporary/agents-memory-macos-arm64/agents-memory" ]] || exit 65
mv "$temporary/agents-memory-macos-arm64" "$destination"
printf 'Installed binary only: %s/agents-memory\nRead INSTALL.md before explicit authority setup.\n' "$destination"
