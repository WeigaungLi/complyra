#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE_FILE="$ROOT_DIR/.env.example"
TARGET_FILE="$ROOT_DIR/.env.prod"

if [ ! -f "$SOURCE_FILE" ]; then
  echo "Missing $SOURCE_FILE"
  exit 1
fi

cp "$SOURCE_FILE" "$TARGET_FILE"

generate_secret() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
    return
  fi
  date +%s | sha256sum | cut -d' ' -f1
}

set_key() {
  key="$1"
  value="$2"
  file="$3"

  if grep -q "^${key}=" "$file"; then
    awk -v k="$key" -v v="$value" '
      BEGIN { FS = OFS = "=" }
      $1 == k { print k, v; next }
      { print }
    ' "$file" > "${file}.tmp"
    mv "${file}.tmp" "$file"
  else
    echo "${key}=${value}" >> "$file"
  fi
}

jwt_secret="$(generate_secret)"

set_key "APP_ENV" "prod" "$TARGET_FILE"
set_key "APP_JWT_SECRET_KEY" "$jwt_secret" "$TARGET_FILE"
set_key "APP_COOKIE_SECURE" "true" "$TARGET_FILE"
set_key "APP_CORS_ORIGINS" "https://app.example.com" "$TARGET_FILE"
set_key "APP_TRUSTED_HOSTS" "api.example.com,app.example.com" "$TARGET_FILE"
set_key "APP_SENTRY_ENVIRONMENT" "prod" "$TARGET_FILE"

echo "Generated $TARGET_FILE"
echo "Next: replace example domains and connection strings before deployment."
