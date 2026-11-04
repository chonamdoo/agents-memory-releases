#!/bin/bash
# MCP installer 1.0.3. Memory core and E5 assets remain the verified binary release 1.0.2.
set -euo pipefail
umask 077
base=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/eb80f6277f6d712a89e854f0f54b7067a9bfc9cc/files
helper_url=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.3/distribution/mcp-local/setup.py
helper_sha=9da880a3c2ad70288ade26fe9413f06c2fa499535d87ec8979147b8cf0f30ab5
archive_sha=3324b7fb06618a0c9d466bb4876e1d810eb4ef03b92f66ae996118f04d632b34
for argument in "$@"; do
  if [[ $argument == --help || $argument == -h ]]; then
    echo 'Usage: bash install.sh --client claude|codex|omp --project /absolute/project'
    echo 'Repeat --client to connect multiple apps. Claude marketplace setup uses --client claude-plugin.'
    echo 'Optional: --provider jev|local-llm --judge-host claude|codex --model ID --executable PATH --prefix PATH'
    echo 'Requires Apple Silicon macOS 13+ and running Docker Desktop, or a dedicated local DATABASE_URL.'
    exit 0
  fi
done
virtual=false
for argument in "$@"; do
  [[ $argument != --virtual-linux ]] || virtual=true
done
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) target=darwin-arm64 ;;
  Linux:x86_64) [[ $virtual == true ]] || { echo 'Linux is for explicit validation only.' >&2; exit 2; }; target=linux-x86_64 ;;
  *) echo 'Requires Apple Silicon macOS 13 or newer.' >&2; exit 2 ;;
esac
work=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-mcp.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
fetch() { curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 "$1" --output "$2"; }
check() {
  local actual
  if command -v shasum >/dev/null 2>&1; then actual=$(shasum -a 256 "$1"); else actual=$(sha256sum "$1"); fi
  [[ ${actual%% *} == "$2" ]] || { echo 'Release integrity verification failed.' >&2; exit 2; }
}
echo 'Downloading the pinned local memory core and E5 search embeddings...' >&2
part=0
while [[ $part -lt 19 ]]; do
  name=agents-memory-hindsight-local-1.0.2.tar.gz.part-$(printf '%03d' "$part")
  fetch "$base/$name" "$work/$name"
  part=$((part + 1))
done
cat "$work"/*.tar.gz.part-* > "$work/core.tar.gz"
check "$work/core.tar.gz" "$archive_sha"
fetch "$helper_url" "$work/setup.py"
check "$work/setup.py" "$helper_sha"
tar -xzf "$work/core.tar.gz" -C "$work"
bundle="$work/agents-memory-hindsight-local-1.0.2"
mkdir "$work/bootstrap"
tar -xzf "$bundle/runtimes/$target.tar.gz" -C "$work/bootstrap"
# A piped shell script must not steal stdin from provider/model prompts or hidden key input.
if [[ -t 0 ]]; then
  "$work/bootstrap/python/bin/python3" -I "$work/setup.py" setup --bundle "$bundle" "$@"
elif { true </dev/tty; } 2>/dev/null; then
  "$work/bootstrap/python/bin/python3" -I "$work/setup.py" setup --bundle "$bundle" "$@" </dev/tty
else
  "$work/bootstrap/python/bin/python3" -I "$work/setup.py" setup --bundle "$bundle" "$@"
fi
