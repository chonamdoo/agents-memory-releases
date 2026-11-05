#!/bin/bash
# Common Hindsight release 1.0.8. Never executes the legacy memory binary.
set -euo pipefail
umask 077
am_version=v1.0.8
am_asset=agents-memory-unified-1.0.8.tar.gz
am_bundle_sha=056d7c5628d6183afc8c21e7538fd2e5439443799bb2b745be993c9577d51d70
am_bootstrap_sha=3324b7fb06618a0c9d466bb4876e1d810eb4ef03b92f66ae996118f04d632b34
am_bootstrap_base=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/eb80f6277f6d712a89e854f0f54b7067a9bfc9cc/files
am_remote=false
am_args=()
am_prefix="$HOME/.local/share/agents-memory-unified"
am_next_prefix=false
for am_arg in "$@"; do
  if [[ $am_next_prefix == true ]]; then am_prefix=$am_arg; am_next_prefix=false; fi
  case "$am_arg" in
    --connect-server) am_remote=true ;;
    --help|-h)
      echo 'Local/server engine: bash install-unified.sh --mode local|personal-server|team-server|company-server --client claude|codex|omp|all --project /absolute/project'
      echo 'Existing server client only: add --connect-server --url https://YOUR_GATEWAY --profile personal'
      echo 'Engine provider: --provider claude|codex|jev [--model ID] [--executable PATH] [--jev-key-file PRIVATE_FILE]'
      echo 'Keys use hidden terminal input; never paste keys into chat. Existing credentials and DB are preserved.'
      exit 0 ;;
    --prefix) am_next_prefix=true; am_args+=("$am_arg") ;;
    --prefix=*) am_prefix=${am_arg#--prefix=}; am_args+=("$am_arg") ;;
    *) am_args+=("$am_arg") ;;
  esac
done
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) am_target=darwin-arm64 ;;
  Linux:x86_64) am_target=linux-x86_64 ;;
  Darwin:x86_64|Linux:aarch64) [[ $am_remote == true ]] || { echo 'This engine bundle requires Apple Silicon macOS or Linux/WSL2 x64.' >&2; exit 2; }; am_target=client-only ;;
  *) echo 'Windows: use a WSL2 Linux terminal and Linux home directory. Native Windows is not validated.' >&2; exit 2 ;;
esac
am_work=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-unified.XXXXXXXX")
trap 'rm -rf -- "$am_work"' EXIT HUP INT TERM
am_fetch() { curl --fail --silent --show-error --location --retry 2 --connect-timeout 20 --max-time 600 --proto '=https' --proto-redir '=https' --tlsv1.2 "$1" --output "$2"; }
am_check() {
  local am_actual
  if command -v shasum >/dev/null 2>&1; then am_actual=$(shasum -a 256 "$1"); else am_actual=$(sha256sum "$1"); fi
  [[ ${am_actual%% *} == "$2" ]] || { echo 'Release integrity check failed; nothing was executed.' >&2; exit 2; }
}
echo 'Preparing the verified common memory package...' >&2
am_fetch "https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/4661c5173de6abf61c9dbe94cb2cc8a43ccb3c42/release-candidates/v1.0.8/assets/$am_asset" "$am_work/unified.tar.gz"
am_check "$am_work/unified.tar.gz" "$am_bundle_sha"
mkdir "$am_work/unified"
tar -xzf "$am_work/unified.tar.gz" -C "$am_work/unified"
if [[ $am_remote == true ]]; then
  if [[ -t 0 ]]; then bash "$am_work/unified/install-client.sh" "${am_args[@]}"
  elif { true </dev/tty; } 2>/dev/null; then bash "$am_work/unified/install-client.sh" "${am_args[@]}" </dev/tty
  else bash "$am_work/unified/install-client.sh" "${am_args[@]}"; fi
  exit $?
fi
am_python="$am_prefix/current/venv/bin/python"
am_bootstrap_args=()
if [[ ! -x $am_python || ! -f "$am_prefix/PRODUCT.json" ]]; then
  echo 'Downloading the pinned Python/Hindsight runtime and E5 search embeddings (first installation only)...' >&2
  for ((am_part=0;am_part<19;am_part++)); do
    am_name=agents-memory-hindsight-local-1.0.2.tar.gz.part-$(printf '%03d' "$am_part")
    am_fetch "$am_bootstrap_base/$am_name" "$am_work/$am_name"
  done
  cat "$am_work"/*.tar.gz.part-* > "$am_work/bootstrap.tar.gz"
  am_check "$am_work/bootstrap.tar.gz" "$am_bootstrap_sha"
  tar -xzf "$am_work/bootstrap.tar.gz" -C "$am_work"
  am_bootstrap="$am_work/agents-memory-hindsight-local-1.0.2"
  mkdir "$am_work/python"
  tar -xzf "$am_bootstrap/runtimes/$am_target.tar.gz" -C "$am_work/python"
  am_python="$am_work/python/python/bin/python3"
  am_bootstrap_args=(--bootstrap-bundle "$am_bootstrap")
fi
am_command=("$am_python" -I "$am_work/unified/unified_setup.py" install --bundle "$am_work/unified" "${am_bootstrap_args[@]}" "${am_args[@]}")
if [[ -t 0 ]]; then "${am_command[@]}"
elif { true </dev/tty; } 2>/dev/null; then "${am_command[@]}" </dev/tty
else "${am_command[@]}"; fi
