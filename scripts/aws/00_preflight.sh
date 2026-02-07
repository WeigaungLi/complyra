#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

failures=0

check_cmd() {
  cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    printf '[OK] %s\n' "$cmd"
  else
    printf '[MISSING] %s\n' "$cmd"
    failures=$((failures + 1))
  fi
}

echo "== Complyra AWS preflight =="
echo "Repository: $ROOT_DIR"

check_cmd aws
check_cmd docker
check_cmd curl

if command -v aws >/dev/null 2>&1; then
  echo "AWS CLI version: $(aws --version 2>&1)"
fi

if command -v docker >/dev/null 2>&1; then
  echo "Docker version: $(docker --version 2>&1)"
fi

if [ -f "$ROOT_DIR/.env.example" ]; then
  echo "[OK] .env.example"
else
  echo "[MISSING] .env.example"
  failures=$((failures + 1))
fi

if [ -f "$ROOT_DIR/Dockerfile" ] && [ -f "$ROOT_DIR/web/Dockerfile" ]; then
  echo "[OK] Dockerfiles"
else
  echo "[MISSING] Dockerfiles"
  failures=$((failures + 1))
fi

if command -v aws >/dev/null 2>&1; then
  if aws sts get-caller-identity >/tmp/complyra_aws_identity.json 2>/tmp/complyra_aws_identity.err; then
    account_id="$(grep -Eo '"Account"\s*:\s*"[0-9]+"' /tmp/complyra_aws_identity.json | grep -Eo '[0-9]+' || true)"
    echo "[OK] AWS credentials configured (Account: ${account_id:-unknown})"
  else
    echo "[WARN] AWS credentials are not configured or invalid"
    echo "       Run: aws configure"
    failures=$((failures + 1))
  fi
fi

if [ "$failures" -gt 0 ]; then
  echo "Preflight finished with $failures issue(s)."
  exit 1
fi

echo "Preflight passed."
