#!/usr/bin/env bash
set -euo pipefail

cd /opt/backend

if [[ "${RUN_MIGRATIONS:-true}" == "true" ]]; then
  alembic upgrade head
fi

exec "$@"
