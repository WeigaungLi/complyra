#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v conftest >/dev/null 2>&1; then
  echo "conftest is required (https://www.conftest.dev/)"
  exit 1
fi

conftest test --policy infra/policy --parser hcl2 infra/terraform/*.tf

if [ -f infra/terraform/terraform.tfvars.example ]; then
  conftest test --policy infra/policy --parser hcl2 infra/terraform/terraform.tfvars.example
fi

echo "Conftest policy checks passed."
