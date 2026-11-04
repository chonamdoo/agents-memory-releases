#!/bin/bash
# MCP installer 1.0.6. Memory core and E5 assets remain the verified binary release 1.0.2.
set -euo pipefail
umask 077
base=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/eb80f6277f6d712a89e854f0f54b7067a9bfc9cc/files
helper_url=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.6/distribution/mcp-local/setup.py
helper_sha=df7df48fb564722a83bfcee66d82ff82f44491d63fee4277df2c0fc1d18e569d
archive_sha=3324b7fb06618a0c9d466bb4876e1d810eb4ef03b92f66ae996118f04d632b34
for argument in "$@"; do
  if [[ $argument == --help || $argument == -h ]]; then
    echo 'Usage: bash install.sh --client claude|codex|omp --project /absolute/project'
    echo 'Repeat --client to connect multiple apps. Claude marketplace setup uses --client claude-plugin.'
    echo 'Optional: --provider jev|local-llm --judge-host claude|codex --model ID --executable PATH --prefix PATH'
    echo 'Requires Apple Silicon macOS 15+. The native PostgreSQL database is prepared automatically; Docker is not needed.'
    exit 0
  fi
done
project_argument=""
next_project=false
for argument in "$@"; do
  if [[ $next_project == true ]]; then project_argument=$argument; next_project=false; fi
  case "$argument" in --project) next_project=true ;; --project=*) project_argument=${argument#--project=} ;; esac
done
if [[ -n $project_argument && -d $project_argument ]]; then
  selected_project=$(cd "$project_argument" && pwd -P)
  selected_home=$(cd "$HOME" && pwd -P)
  if [[ $selected_project == "$selected_home" || $selected_project == / ]]; then
    echo '실제 작업 프로젝트에서 실행하세요. 홈 폴더(~)는 프로젝트로 사용할 수 없습니다.' >&2
    echo 'cd /absolute/path/to/project 후 --project "$PWD"로 다시 실행하세요.' >&2
    exit 2
  fi
fi
virtual=false
for argument in "$@"; do
  [[ $argument != --virtual-linux ]] || virtual=true
done
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) target=darwin-arm64; connector_sha=208f7ae90ee0cac7938167864f068f70b1c9db649b7c6d2e99cb71c891de7077 ;;
  Linux:x86_64) [[ $virtual == true ]] || { echo 'Linux is for explicit validation only.' >&2; exit 2; }; target=linux-x86_64; connector_sha=7391be74e512e0883b93764fcc4ca35b69ef2f4e8264b63f5d4f235b8541f7fe ;;
  *) echo 'Requires Apple Silicon macOS 15 or newer.' >&2; exit 2 ;;
esac
work=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-mcp.XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
fetch() { curl --fail --silent --show-error --location --retry 2 --connect-timeout 20 --max-time 600 --proto '=https' --proto-redir '=https' --tlsv1.2 "$1" --output "$2"; }
check() {
  local actual
  if command -v shasum >/dev/null 2>&1; then actual=$(shasum -a 256 "$1"); else actual=$(sha256sum "$1"); fi
  [[ ${actual%% *} == "$2" ]] || { echo 'Release integrity verification failed.' >&2; exit 2; }
}
fetch "$helper_url" "$work/setup.py"
check "$work/setup.py" "$helper_sha"
fetch "https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/v1.0.6/plugins/agents-memory-local/bin/connector-$target" "$work/connector-$target"
check "$work/connector-$target" "$connector_sha"
selected_prefix="$HOME/.local/share/agents-memory-hindsight"
next_prefix=false
for argument in "$@"; do
  if [[ $next_prefix == true ]]; then selected_prefix=$argument; next_prefix=false; fi
  case "$argument" in --prefix) next_prefix=true ;; --prefix=*) selected_prefix=${argument#--prefix=} ;; esac
done
python="$selected_prefix/current/venv/bin/python"
if [[ -x $python && -f "$selected_prefix/PRODUCT.json" ]] &&
   "$python" -I -c 'import json,sys; from pathlib import Path; sys.exit(json.loads(Path(sys.argv[1]).read_bytes()).get("version") != "1.0.2")' "$selected_prefix/current/READY.json"; then
  if [[ -t 0 ]]; then
    "$python" -I "$work/setup.py" setup "$@"
  elif { true </dev/tty; } 2>/dev/null; then
    "$python" -I "$work/setup.py" setup "$@" </dev/tty
  else
    "$python" -I "$work/setup.py" setup "$@"
  fi
  exit $?
fi
echo 'Downloading the pinned local memory core and E5 search embeddings...' >&2
part=0
while [[ $part -lt 19 ]]; do
  name=agents-memory-hindsight-local-1.0.2.tar.gz.part-$(printf '%03d' "$part")
  fetch "$base/$name" "$work/$name"
  part=$((part + 1))
done
cat "$work"/*.tar.gz.part-* > "$work/core.tar.gz"
check "$work/core.tar.gz" "$archive_sha"
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
