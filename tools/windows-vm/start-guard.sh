#!/bin/bash
# Test infrastructure only: refuse the wrapper's destructive unfinished-install path.
set -euo pipefail
am_storage=${STORAGE:-/storage}
for am_disk in "$am_storage/data.qcow2" "$am_storage/data.img"; do
  if [[ -s $am_disk && ! -f $am_storage/windows.boot ]]; then
    echo 'BLOCKED: an existing Windows test disk has no verified boot marker.' >&2
    echo 'Preserve the disk and installation media; inspect or back up the VM before restarting the wrapper.' >&2
    exit 73
  fi
done
if [[ $# == 0 ]]; then
  set -- /run/entry.sh
fi
exec "$@"
