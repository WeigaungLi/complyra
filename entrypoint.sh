#!/usr/bin/env sh
set -e

if [ -f "/app/alembic.ini" ]; then
  alembic upgrade head
fi

exec "$@"
