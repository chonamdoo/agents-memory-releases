#!/bin/bash
set -euo pipefail
umask 077
plugin_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
version=0.1.0-preview.20261027
archive_sha=c727383185a3e7459971cb82a42987f8158ba00e4ad38303023db83f113aeca1
archive_url=https://github.com/chonamdoo/agents-memory-releases/releases/download/v0.1.0-preview.20261027/agents-memory-macos-arm64.tar.gz
fail() { printf 'agents-memory: %s\n' "$1" >&2; exit "${2:-78}"; }
[[ ${AGENTS_MEMORY_MCP_ENABLED:-false} == true ]] || fail 'Onboarding required. Run /agents-memory:setup before enabling MCP.'
[[ ${AGENTS_MEMORY_RECOVERY_ACK:-false} == true ]] || fail 'Explicit acknowledgment of existing managed-service recovery is required.'
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || fail 'This prerelease supports macOS arm64 only.' 64
for value in "${AGENTS_MEMORY_CONFIG:-}" "${AGENTS_MEMORY_AGENT_TOKEN_FILE:-}"; do
  [[ $value == /* && -f $value && ! -L $value ]] || fail 'Select existing absolute private config and scoped token file paths.'
  [[ $value != "$plugin_root"/* && ( -z ${CLAUDE_PLUGIN_DATA:-} || $value != "$CLAUDE_PLUGIN_DATA"/* ) ]] || fail 'Keep authority config and tokens outside plugin/cache directories.'
done
verify_runtime() {
  local root=$1 listing
  [[ -d $root && ! -L $root && -x $root/agents-memory ]] || return 1
  [[ -z $(find "$root" -type l -print -quit) ]] || return 1
  listing=$(find "$root" -type f | while IFS= read -r path; do printf '%s\n' "${path#"$root"/}"; done | LC_ALL=C sort)
  [[ $listing == "$(cat "$plugin_root/runtime-file-list.txt")" ]] || return 1
  (cd "$root" && /usr/bin/shasum -a 256 -c "$plugin_root/runtime-files.sha256" >/dev/null 2>&1)
}
runtime=${AGENTS_MEMORY_RUNTIME_DIR:-}
if [[ -n $runtime ]]; then
  [[ $runtime == /* ]] || fail 'Runtime directory must be absolute.'
  verify_runtime "$runtime" || fail 'Installed runtime differs from the pinned release.' 65
else
  data=${CLAUDE_PLUGIN_DATA:-}
  [[ $data == /* && ! -L $data ]] || fail 'Claude Code must provide an absolute persistent plugin data directory.'
  runtime="$data/runtime/$version/agents-memory-macos-arm64"
  if [[ -e $runtime || -L $runtime ]]; then
    verify_runtime "$runtime" || fail 'Cached runtime differs from the pinned release; no overwrite was performed.' 65
  else
    [[ ${AGENTS_MEMORY_DOWNLOAD_ALLOWED:-false} == true ]] || fail 'Pinned runtime is absent. Explicitly allow its download or select an installed runtime directory.'
    mkdir -p "$data/runtime"
    lock="$data/.runtime-$version.lock"
    mkdir "$lock" 2>/dev/null || fail 'Runtime installation is already active; retry after it finishes.' 75
    temporary=$(mktemp -d "$data/.runtime.XXXXXX")
    cleanup() { rm -rf "$temporary"; rmdir "$lock" 2>/dev/null || true; }
    trap cleanup EXIT
    /usr/bin/curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --tlsv1.2 "$archive_url" -o "$temporary/runtime.tar.gz"
    actual=$(/usr/bin/shasum -a 256 "$temporary/runtime.tar.gz"); actual=${actual%% *}
    [[ $actual == "$archive_sha" ]] || fail 'Downloaded archive checksum mismatch.' 65
    /usr/bin/tar -xzf "$temporary/runtime.tar.gz" -C "$temporary"
    verify_runtime "$temporary/agents-memory-macos-arm64" || fail 'Downloaded runtime file verification failed.' 65
    [[ ! -e "$data/runtime/$version" && ! -L "$data/runtime/$version" ]] || fail 'This runtime version already exists; no overwrite was performed.' 73
    mkdir "$data/runtime/$version"
    mv "$temporary/agents-memory-macos-arm64" "$runtime"
    cleanup
    trap - EXIT
  fi
fi
exec "$runtime/agents-memory" --config "$AGENTS_MEMORY_CONFIG" --token-file "$AGENTS_MEMORY_AGENT_TOKEN_FILE" stdio
