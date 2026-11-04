#!/bin/bash
# Run on the team's server. Never installs a local database on client PCs.
set -euo pipefail
cd -- "$(dirname -- "$0")"
umask 077
if [[ ! -e .env ]]; then
  am_password=$(openssl rand -hex 32)
  printf 'AM_COLLAB_DB_PASSWORD=%s\nAM_COLLAB_PUBLIC_URL=http://127.0.0.1:18350\n' "$am_password" > .env
fi
[[ ! -L .env ]] || { echo 'Refusing a symlinked server environment file' >&2; exit 1; }
chmod 600 .env
docker compose up -d --build db server
echo 'Server starting at http://127.0.0.1:18350; existing volumes and keys are preserved.'
echo 'Create a private account connection file with the account command in README.ko.md.'
