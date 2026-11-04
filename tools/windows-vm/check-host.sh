#!/bin/bash
# Run on the Linux Docker host. This probe never starts a VM or downloads Windows.
set -euo pipefail
failed=0
mode=${1:-kvm}
[[ $mode == kvm || $mode == --tcg ]] || { echo 'Usage: bash check-host.sh [--tcg]' >&2; exit 2; }
if [[ $mode == kvm && ( ! -c /dev/kvm || ! -r /dev/kvm || ! -w /dev/kvm ) ]]; then
  echo 'BLOCKED: /dev/kvm must exist and be readable/writable by this account.' >&2
  failed=1
fi
if [[ $mode == kvm && ! -c /dev/net/tun ]]; then
  echo 'BLOCKED: /dev/net/tun is unavailable.' >&2
  failed=1
fi
if [[ $(uname -m) != x86_64 ]]; then
  echo 'BLOCKED: this test configuration requires a Linux x86_64 host.' >&2
  failed=1
fi
if ! command -v docker >/dev/null || ! docker info >/dev/null 2>&1; then
  echo 'BLOCKED: Docker daemon is unavailable.' >&2
  failed=1
elif [[ $(docker info --format '{{.OSType}}') != linux ]]; then
  echo 'BLOCKED: the VM wrapper needs a Linux Docker daemon.' >&2
  failed=1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo 'BLOCKED: Docker Compose v2 is required.' >&2
  failed=1
fi
if [[ $failed != 0 ]]; then
  echo 'Windows VM was not started. No product test has passed.' >&2
  exit 2
fi
echo "Device and Docker checks passed for $mode. Software emulation is much slower than KVM."
echo 'Allow at least 32GB free on Docker storage and 8GB guest RAM where possible; sparse disks still consume real space as installation grows.'
