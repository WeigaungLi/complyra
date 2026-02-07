#!/usr/bin/env sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <base_url> [username] [password]"
  echo "Example: $0 https://api.example.com demo demo123"
  exit 1
fi

BASE_URL="${1%/}"
USERNAME="${2:-}"
PASSWORD="${3:-}"

check_endpoint() {
  path="$1"
  status_code="$(curl -s -o /tmp/complyra_smoke_resp.out -w "%{http_code}" "$BASE_URL$path" || true)"
  if [ "$status_code" != "200" ]; then
    echo "[FAIL] $path returned $status_code"
    cat /tmp/complyra_smoke_resp.out || true
    exit 1
  fi
  echo "[OK] $path"
}

check_endpoint "/api/health/live"
check_endpoint "/api/health/ready"

if [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
  login_status="$(curl -s -o /tmp/complyra_login.out -w "%{http_code}" \
    -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" || true)"

  if [ "$login_status" != "200" ]; then
    echo "[FAIL] login endpoint returned $login_status"
    cat /tmp/complyra_login.out || true
    exit 1
  fi

  echo "[OK] /api/auth/login"
fi

echo "Smoke test passed."
