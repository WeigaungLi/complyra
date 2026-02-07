#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.prod}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing environment file: $ENV_FILE"
  exit 1
fi

required_keys="
APP_ENV
APP_JWT_SECRET_KEY
APP_COOKIE_SECURE
APP_CORS_ORIGINS
APP_TRUSTED_HOSTS
APP_DATABASE_URL
APP_REDIS_URL
APP_QDRANT_URL
APP_OLLAMA_BASE_URL
"

missing=0

for key in $required_keys; do
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    echo "[MISSING] $key"
    missing=$((missing + 1))
    continue
  fi

  value="$(grep "^${key}=" "$ENV_FILE" | head -n1 | cut -d'=' -f2-)"
  if [ -z "$value" ]; then
    echo "[EMPTY] $key"
    missing=$((missing + 1))
    continue
  fi

  echo "[OK] $key"
done

if grep -Eq 'example\.com|change-me|app_password@postgres|redis://redis:6379|http://qdrant:6333|http://ollama:11434' "$ENV_FILE"; then
  echo "[WARN] $ENV_FILE still contains placeholder or local-only values."
fi

if [ "$missing" -gt 0 ]; then
  echo "Environment validation failed with $missing missing/empty value(s)."
  exit 1
fi

echo "Environment validation passed."
