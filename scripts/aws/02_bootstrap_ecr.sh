#!/usr/bin/env sh
set -eu

REGION="${AWS_REGION:-ap-southeast-1}"
REPO_API="complyra-api"
REPO_WEB="complyra-web"

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required"
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

ensure_repo() {
  repo="$1"
  if aws ecr describe-repositories --repository-names "$repo" --region "$REGION" >/dev/null 2>&1; then
    echo "[OK] Repository exists: $repo"
  else
    aws ecr create-repository --repository-name "$repo" --region "$REGION" >/dev/null
    echo "[CREATED] Repository: $repo"
  fi
}

ensure_repo "$REPO_API"
ensure_repo "$REPO_WEB"

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "ECR bootstrap complete."
echo "AWS_ACCOUNT_ID=$ACCOUNT_ID"
echo "AWS_REGION=$REGION"
echo "ECR_REGISTRY=$ECR_REGISTRY"
