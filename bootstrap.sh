#!/bin/bash
# Public binary installer/onboarding entrypoint; never changes an existing authority.
set -euo pipefail
umask 077
version=0.1.0-preview.20261027
base=https://github.com/chonamdoo/agents-memory-releases/releases/download/v0.1.0-preview.20261027
archive_sha=c727383185a3e7459971cb82a42987f8158ba00e4ad38303023db83f113aeca1
installer_sha=4bab364b91daef8ffbb679dedca0c9100cf46d86b62f93d5debd07e9dcb3ba73
mode= host= execution= database= noninteractive=false config= initialize=false
usage() { echo 'Usage: bootstrap.sh --company|--home [--host codex|claude] [--execution local] [--database local] [--non-interactive] [--config /private/config.json] [--initialize] [-- setup identity/private-path arguments]'; }
fail() { printf 'agents-memory: %s\n' "$1" >&2; exit "${2:-64}"; }
while (($#)); do
  case $1 in
    --company) mode=company; shift;;
    --home) mode=home; shift;;
    --host|--execution|--database|--config)
      (($# >= 2)) || fail 'Missing option value.'
      case $1 in --host) host=$2;; --execution) execution=$2;; --database) database=$2;; --config) config=$2;; esac; shift 2;;
    --non-interactive) noninteractive=true; shift;;
    --initialize) initialize=true; shift;;
    --help|-h) usage; exit 0;;
    --) shift; break;;
    *) fail 'Unknown bootstrap option. Use --help.';;
  esac
done
[[ $(uname -s) == Darwin && $(uname -m) == arm64 ]] || fail 'This preview requires macOS arm64.'
choose() {
  local current=$1 prompt=$2 answer
  if [[ -n $current ]]; then printf '%s' "$current"; return; fi
  [[ $noninteractive == false && -t 0 ]] || fail "Explicit choice required: $prompt"
  printf '%s: ' "$prompt" >&2; IFS= read -r answer || fail 'Input ended.'; printf '%s' "$answer"
}
mode=$(choose "$mode" '환경 선택 company(회사·구독 LLM) / home(집·기존 Jev 유지)')
[[ $mode == company || $mode == home ]] || fail 'Choose company or home.'
execution=$(choose "$execution" '코어 실행 위치 local / cloud(이 설치기는 미지원)')
database=$(choose "$database" 'DB 위치 local / cloud(이 초기화 경로는 미지원)')
[[ $execution == local && $database == local ]] || fail 'Cloud core/DB initialization is unsupported; no local fallback or resources were created.'
if [[ $mode == company ]]; then
  host=$(choose "$host" '공식 로그인된 구독 CLI codex(Terra) / claude(Haiku)')
  case $host in codex) model=gpt-6.1-terra;; claude) model=claude-haiku-5-5;; *) fail 'Choose codex or claude; no cross-provider fallback.';; esac
  printf 'Company selection: subscription / %s / %s. Jev is not selected.\n' "$host" "$model"
else
  [[ -z $host && $initialize == false && $# == 0 ]] || fail 'Home mode only installs the binary and preserves existing Jev; use explicit operator onboarding separately.'
  echo 'Home selection: preserve existing Jev, keys, DB and settings.'
fi
[[ $HOME == /* && -d $HOME && ! -L $HOME ]] || fail 'An existing absolute HOME directory is required.'
temporary=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-bootstrap.XXXXXX")
trap 'rm -rf "$temporary"' EXIT
fetch() { /usr/bin/curl --fail --silent --show-error --location --connect-timeout 15 --max-time 180 --proto '=https' --proto-redir '=https' --tlsv1.2 "$base/$1" -o "$temporary/$1"; }
verify() { local actual; actual=$(/usr/bin/shasum -a 256 "$temporary/$1"); [[ ${actual%% *} == "$2" ]] || fail 'Public release checksum mismatch.' 65; }
fetch install.sh; verify install.sh "$installer_sha"
fetch agents-memory-macos-arm64.tar.gz; verify agents-memory-macos-arm64.tar.gz "$archive_sha"
prefix="$HOME/.local/share/agents-memory/releases"
destination="$prefix/$version"
if [[ -e $destination || -L $destination ]]; then
  [[ -d $destination && ! -L $destination && -x $destination/agents-memory ]] || fail 'Existing version is not a regular runtime directory; nothing overwritten.' 73
  /usr/bin/tar -xzf "$temporary/agents-memory-macos-arm64.tar.gz" -C "$temporary"
  [[ -z $(find "$destination" -type l -print -quit) ]] || fail 'Existing runtime has symlinks; nothing overwritten.' 73
  /usr/bin/diff -qr "$temporary/agents-memory-macos-arm64" "$destination" >/dev/null || fail 'Existing runtime differs; nothing overwritten.' 73
  echo 'Identical version already installed; no overwrite.'
else
  /bin/bash "$temporary/install.sh" "$temporary/agents-memory-macos-arm64.tar.gz" "$prefix"
fi
binary="$destination/agents-memory"
"$binary" --version
printf 'Distribution version: %s\nBinary: %s\n' "$version" "$binary"
echo 'Binary placement only does not activate MCP, replace a running service/hooks, issue credentials, reset DB or call a model.'
echo "Onboarding: https://github.com/chonamdoo/agents-memory-releases/blob/main/INSTALL.md"
if [[ $mode == home || $# == 0 ]]; then
  [[ $initialize == false ]] || fail 'Initialization requires explicit setup identity and private-path arguments after --.'
  echo 'Keep existing settings. New authority requires an operator-prepared PostgreSQL18.x/pgvector>=0.8.7 and private DSN files.'
  if [[ $mode == company ]]; then
    printf 'Selected route for explicit setup: --judge subscription --subscription-host %s --subscription-policy allow --ack-subscription-egress\n' "$host"
    echo 'Check official login with codex login status or claude auth status. Never paste keys/DSNs in the command or chat.'
  fi
  exit 0
fi
[[ $config == /* && ! -e $config && ! -L $config ]] || fail 'New setup requires --config at a new absolute private path; existing config was preserved.' 73
for argument in "$@"; do
  case $argument in --resume|--non-interactive|--plan-only|--execution-environment*|--database-location*|--judge*|--jev*|--subscription*|--ack-subscription-egress|--ack-jev-egress|--config*|--token-file*) fail 'Route/consent options are controlled by this bootstrap; do not repeat them after --.';; esac
done
route=(--non-interactive --execution-environment local --database-location local --judge subscription --subscription-host "$host" --subscription-policy allow --ack-subscription-egress)
"$binary" --config "$config" setup "$@" "${route[@]}" --plan-only
[[ $initialize == true ]] || { echo 'Plan only: no authority/model/credential changes. Explicit --initialize with terminal confirmation is required for effects.'; exit 0; }
[[ $noninteractive == false && -t 0 ]] || fail 'Initialization requires a terminal confirmation; no automatic enrollment.'
echo 'Initialization creates scoped local authority credentials and schema0008 in the supplied dedicated DB; subscription verification consumes quota and sends synthetic input to the selected official provider. It does not reset DB or request a provider API key.'
printf 'If your organization permits these effects, type INITIALIZE: ' >&2
IFS= read -r answer
[[ $answer == INITIALIZE ]] || fail 'Initialization not authorized; binary retained, authority unchanged.' 78
"$binary" --config "$config" setup "$@" "${route[@]}"
echo 'Authority setup finished. Project registration/scoped agent enrollment, service start and native hook installation remain explicit operator actions in INSTALL.md.'
