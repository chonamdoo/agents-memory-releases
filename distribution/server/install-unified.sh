#!/bin/bash
# The unpublished 2.0.0 release runs only from an operator-verified local bundle.
set -euo pipefail
umask 077
am_bootstrap_sha=3324b7fb06618a0c9d466bb4876e1d810eb4ef03b92f66ae996118f04d632b34
am_bootstrap_manifest_sha=8064471a6d50140451fed9e675b4072de243f453d212bff0a732bd4637dbeffe
am_bootstrap_base=https://raw.githubusercontent.com/chonamdoo/agents-memory-releases/eb80f6277f6d712a89e854f0f54b7067a9bfc9cc/files
am_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
am_bundle=
am_bootstrap=
am_remote=false
am_args=()
am_local_options=()
am_remote_options=()
am_prefix="$HOME/.local/share/agents-memory-unified"
am_client_root=
am_fail() { printf '%s\n' "$*" >&2; exit 2; }
am_value() { [[ $# -ge 2 && -n $2 && $2 != -* ]] || am_fail "Missing value for $1"; }
while [[ $# -gt 0 ]]; do
  am_option=${1%%=*}
  case "$am_option" in
    --bootstrap-bundle|--reranker-dir|--provider|--model|--jev-key-file|--mode|--host|--public-url) am_local_options+=("$am_option") ;;
    --url|--profile|--credential-file|--project-name|--python-launcher|--root|--device-name|--no-automatic-memory|--replace-credential|--recover) am_remote_options+=("$am_option") ;;
  esac
  case "$am_option" in
    --help|-h)
      printf '%s\n' \
        'Unpublished 2.0.0: use an extracted, operator-verified local bundle; no unified bundle is downloaded.' \
        'Local/server: bash install-unified.sh [--bundle PATH] [--bootstrap-bundle PATH] --reranker-dir PATH --mode local|personal-server|team-server|company-server --client claude|codex|omp|all --project /absolute/project' \
        'Existing server client only: bash install-unified.sh [--bundle PATH] --connect-server --url https://YOUR_GATEWAY --profile personal --client all' \
        '--bundle defaults to the adjacent bundle only when ASSETS.json validates. --bootstrap-bundle is an extracted genuine 1.0.2 bundle or its pinned .tar.gz.' \
        'Jev is the only judgment backend: --provider jev [--model ID] [--jev-key-file PRIVATE_FILE]. Frontends remain Claude, Codex and omp.' \
        'First local installation requires a prepared six-file reranker directory. Updates may reuse the owned verified model cache. No model is downloaded.' \
        'Remote clients need no bootstrap/model; a working python3 is required to validate the local release before client provisioning.' \
        'Keys use hidden terminal input; never paste keys into chat. Existing credentials and DB are preserved.'
      exit 0 ;;
    --connect-server|--no-automatic-memory|--replace-credential|--recover)
      [[ $1 == "$am_option" ]] || am_fail "$am_option does not take a value"
      if [[ $am_option == --connect-server ]]; then am_remote=true; else am_args+=("$1"); fi
      shift ;;
    --bundle|--bootstrap-bundle|--prefix|--reranker-dir|--provider|--model|--jev-key-file|--mode|--host|--public-url|--client|--project|--url|--profile|--credential-file|--project-name|--python-launcher|--root|--device-name)
      if [[ $1 == *=* ]]; then am_parameter=${1#*=}; am_value "$am_option" "$am_parameter"; shift
      else am_value "$am_option" "${2-}"; am_parameter=$2; shift 2; fi
      case "$am_option" in
        --bundle) am_bundle=$am_parameter ;;
        --bootstrap-bundle) am_bootstrap=$am_parameter ;;
        --prefix) am_prefix=$am_parameter; am_client_root=$am_parameter ;;
        --root) am_client_root=$am_parameter; am_args+=("$am_option" "$am_parameter") ;;
        *) am_args+=("$am_option" "$am_parameter") ;;
      esac ;;
    *) am_fail "Unknown installer argument: $1" ;;
  esac
done
if [[ $am_remote == true ]]; then
  [[ -z ${am_local_options[0]-} ]] || am_fail "Local-only option is not supported with --connect-server: ${am_local_options[0]}"
else
  [[ -z ${am_remote_options[0]-} ]] || am_fail "Remote-only option requires --connect-server: ${am_remote_options[0]}"
fi
[[ -n $am_bundle ]] || am_bundle=$am_source
[[ -d $am_bundle && ! -L $am_bundle && -s "$am_bundle/ASSETS.json" && ! -L "$am_bundle/ASSETS.json" ]] || am_fail 'A valid extracted 2.0.0 bundle with ASSETS.json is required; supply --bundle PATH. No public bundle download is available.'
am_bundle="$(cd -- "$am_bundle" && pwd -P)"
case "$(uname -s):$(uname -m)" in
  Darwin:arm64) am_target=darwin-arm64 ;;
  Linux:x86_64) am_target=linux-x86_64 ;;
  Darwin:x86_64|Linux:aarch64) [[ $am_remote == true ]] || am_fail 'This engine bundle requires Apple Silicon macOS or Linux/WSL2 x64.'; am_target=client-only ;;
  *) am_fail 'Windows: use a WSL2 Linux terminal and Linux home directory. Native Windows is not validated.' ;;
esac
am_fetch() { curl --fail --silent --show-error --location --retry 2 --connect-timeout 20 --max-time 600 --proto '=https' --proto-redir '=https' --tlsv1.2 "$1" --output "$2"; }
am_check() {
  local am_actual
  if command -v shasum >/dev/null 2>&1; then am_actual=$(shasum -a 256 "$1"); else am_actual=$(sha256sum "$1"); fi
  [[ ${am_actual%% *} == "$2" ]] || am_fail 'Release integrity check failed; nothing was executed.'
}
am_verify_bootstrap() {
  [[ -d $am_bootstrap && ! -L $am_bootstrap && -f "$am_bootstrap/MANIFEST.json" && ! -L "$am_bootstrap/MANIFEST.json" && -d "$am_bootstrap/runtimes" && ! -L "$am_bootstrap/runtimes" ]] || am_fail 'Invalid genuine bootstrap bundle.'
  am_check "$am_bootstrap/MANIFEST.json" "$am_bootstrap_manifest_sha"
  local am_member am_line am_digest am_count am_pattern
  for am_member in installer.py "runtimes/$am_target.tar.gz"; do
    [[ -f "$am_bootstrap/$am_member" && ! -L "$am_bootstrap/$am_member" ]] || am_fail 'A required genuine bootstrap asset is missing.'
    am_count=0
    am_digest=
    am_pattern='^[[:space:]]*"'"${am_member//./\\.}"'"[[:space:]]*:[[:space:]]*"([0-9a-f]{64})"[[:space:]]*,?[[:space:]]*$'
    while IFS= read -r am_line || [[ -n $am_line ]]; do
      if [[ $am_line =~ $am_pattern ]]; then
        am_digest=${BASH_REMATCH[1]}
        am_count=$((am_count + 1))
      fi
    done < "$am_bootstrap/MANIFEST.json"
    [[ $am_count == 1 ]] || am_fail 'Pinned bootstrap manifest entry is invalid.'
    am_check "$am_bootstrap/$am_member" "$am_digest"
  done
}
am_verify_bundle() {
if ! "$am_python" -I - "$am_bundle" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path
sys.excepthook = lambda *_: print('Release asset validation failed.', file=sys.stderr)

bundle = Path(sys.argv[1]).resolve(strict=True)
try:
    manifest = json.loads((bundle / 'ASSETS.json').read_text())
except (OSError, ValueError):
    raise SystemExit('Invalid release manifest.')
if not isinstance(manifest, dict) or manifest.get('version') != '2.0.0' or not isinstance(manifest.get('files'), dict):
    raise SystemExit('A valid 2.0.0 ASSETS.json is required; supply --bundle PATH.')
files = manifest['files']
required = {'unified_setup.py', 'install-unified.sh', 'install-client.sh', 'runtime-helper.py', 'client-requirements.lock', 'reranker-assets.sha256.json'}
for label in ('sdk', 'core_312', 'core_313'):
    member = manifest.get(label)
    if not isinstance(member, str) or not member.startswith('packages/') or not member.endswith('.whl'):
        raise SystemExit('Release manifest is missing a reviewed wheel: ' + label)
    required.add(member)
if not required.issubset(files):
    raise SystemExit('Release manifest is missing required installer assets.')
actual_files = set()
for path in bundle.rglob('*'):
    if path.is_symlink():
        raise SystemExit('Release assets must not be symbolic links.')
    if path.is_file():
        actual_files.add(path.relative_to(bundle).as_posix())
    elif not path.is_dir():
        raise SystemExit('Release assets must be regular files.')
if actual_files - {'ASSETS.json'} != set(files):
    raise SystemExit('Release asset set does not match ASSETS.json.')
for name, digest in files.items():
    if not isinstance(name, str) or not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise SystemExit('Invalid release manifest member.')
    member = Path(name)
    if not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_./-]*', name) or member.as_posix() != name or member.is_absolute() or not member.parts or any(part in ('.', '..') for part in member.parts):
        raise SystemExit('Release asset escaped bundle.')
    path = bundle
    for part in member.parts:
        path = path / part
        if path.is_symlink():
            raise SystemExit('Release assets must not be symbolic links.')
    try:
        if not path.is_file():
            raise SystemExit('Release asset is missing: ' + name)
        actual = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                actual.update(chunk)
        if actual.hexdigest() != digest:
            raise SystemExit('Release integrity check failed: ' + name)
    except OSError:
        raise SystemExit('Release asset cannot be read: ' + name)
PY
then
  am_fail 'Bundle validation failed. Supply --bundle PATH pointing to the extracted, operator-verified 2.0.0 release.'
fi
}
am_python="$am_prefix/current/venv/bin/python"
am_owned_python=$am_python
am_verified=false
if [[ ! -x $am_python ]] || ! "$am_python" -I -c 'import hashlib, json' >/dev/null 2>&1; then
  am_python=$(command -v python3 || true)
fi
if [[ -n $am_python && -x $am_python ]] && "$am_python" -I -c 'import hashlib, json' >/dev/null 2>&1; then
  am_verify_bundle
  am_verified=true
fi
am_bootstrap_args=()
if [[ $am_remote == true ]]; then
  [[ $am_verified == true ]] || am_fail 'A working python3 is required to verify ASSETS.json for this remote client installation; no model or bootstrap is needed.'
elif [[ ! -x $am_owned_python || ! -f "$am_prefix/PRODUCT.json" ]]; then
  am_work=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-unified.XXXXXXXX")
  trap 'rm -rf -- "$am_work"' EXIT HUP INT TERM
  if [[ -z $am_bootstrap ]]; then
    echo 'Downloading the pinned genuine 1.0.2 Python/Hindsight runtime and E5 embeddings (first installation only)...' >&2
    for ((am_part=0;am_part<19;am_part++)); do
      am_name=agents-memory-hindsight-local-1.0.2.tar.gz.part-$(printf '%03d' "$am_part")
      am_fetch "$am_bootstrap_base/$am_name" "$am_work/$am_name"
    done
    cat "$am_work"/*.tar.gz.part-* > "$am_work/bootstrap.tar.gz"
    am_bootstrap="$am_work/bootstrap.tar.gz"
  fi
  if [[ -f $am_bootstrap && ! -L $am_bootstrap ]]; then
    am_check "$am_bootstrap" "$am_bootstrap_sha"
    mkdir "$am_work/bootstrap"
    tar -xzf "$am_bootstrap" -C "$am_work/bootstrap"
    am_bootstrap="$am_work/bootstrap/agents-memory-hindsight-local-1.0.2"
  fi
  [[ -d $am_bootstrap && ! -L $am_bootstrap && -f "$am_bootstrap/installer.py" && ! -L "$am_bootstrap/installer.py" && -f "$am_bootstrap/runtimes/$am_target.tar.gz" && ! -L "$am_bootstrap/runtimes/$am_target.tar.gz" ]] || am_fail '--bootstrap-bundle must be the extracted genuine 1.0.2 bundle or its pinned archive.'
  am_bootstrap="$(cd -- "$am_bootstrap" && pwd -P)"
  am_verify_bootstrap
  mkdir "$am_work/python"
  tar -xzf "$am_bootstrap/runtimes/$am_target.tar.gz" -C "$am_work/python"
  am_python="$am_work/python/python/bin/python3"
  am_bootstrap_args=(--bootstrap-bundle "$am_bootstrap")
elif [[ -n $am_bootstrap ]]; then
  if [[ -f $am_bootstrap && ! -L $am_bootstrap ]]; then
    am_check "$am_bootstrap" "$am_bootstrap_sha"
    am_work=$(mktemp -d "${TMPDIR:-/tmp}/agents-memory-unified.XXXXXXXX")
    trap 'rm -rf -- "$am_work"' EXIT HUP INT TERM
    mkdir "$am_work/bootstrap"
    tar -xzf "$am_bootstrap" -C "$am_work/bootstrap"
    am_bootstrap="$am_work/bootstrap/agents-memory-hindsight-local-1.0.2"
  fi
  am_verify_bootstrap
  am_bootstrap_args=(--bootstrap-bundle "$am_bootstrap")
fi
if [[ $am_verified != true ]]; then am_verify_bundle; fi
if [[ $am_remote == true ]]; then
  am_command=(bash "$am_bundle/install-client.sh" "${am_args[@]+"${am_args[@]}"}")
  if [[ -n $am_client_root ]]; then export AM_COLLAB_CLIENT_ROOT="$am_client_root"; fi
else
  am_command=("$am_python" -I "$am_bundle/unified_setup.py" install --bundle "$am_bundle" --prefix "$am_prefix" "${am_bootstrap_args[@]+"${am_bootstrap_args[@]}"}" "${am_args[@]+"${am_args[@]}"}")
fi
if [[ -t 0 ]]; then "${am_command[@]}"
elif { true </dev/tty; } 2>/dev/null; then "${am_command[@]}" </dev/tty
else "${am_command[@]}"; fi
