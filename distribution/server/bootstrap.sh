#!/bin/bash
# The old image contains no common Hindsight processor. Do not deploy a raw store.
set -euo pipefail
printf '%s\n' \
  '0.3.0.dev1: the legacy Docker bootstrap is retired.' \
  'Use the reviewed common runtime described in UNIFIED-RUNTIME.ko.md.' \
  'A new packaged core and cold-install verification are required before release.' >&2
exit 2
