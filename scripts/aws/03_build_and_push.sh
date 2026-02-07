#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

REGION="${AWS_REGION:-ap-southeast-1}"
if [ "${1:-}" != "" ]; then
  TAG="$1"
elif git rev-parse --short HEAD >/tmp/complyra_git_sha.out 2>/dev/null; then
  TAG="$(cat /tmp/complyra_git_sha.out)"
else
  TAG="$(date +%Y%m%d%H%M%S)"
fi

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
TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build -t complyra-api:"$TAG" .
docker tag complyra-api:"$TAG" "$ECR_REGISTRY"/complyra-api:"$TAG"
docker push "$ECR_REGISTRY"/complyra-api:"$TAG"

docker build -t complyra-web:"$TAG" ./web
docker tag complyra-web:"$TAG" "$ECR_REGISTRY"/complyra-web:"$TAG"
docker push "$ECR_REGISTRY"/complyra-web:"$TAG"

mkdir -p "$ROOT_DIR/releases"
cat > "$ROOT_DIR/releases/${TAG}.json" <<MANIFEST
{
  "release_tag": "$TAG",
  "created_at_utc": "$TIMESTAMP_UTC",
  "region": "$REGION",
  "account_id": "$ACCOUNT_ID",
  "api_image": "$ECR_REGISTRY/complyra-api:$TAG",
  "web_image": "$ECR_REGISTRY/complyra-web:$TAG"
}
MANIFEST

echo "Images pushed:"
echo "  $ECR_REGISTRY/complyra-api:$TAG"
echo "  $ECR_REGISTRY/complyra-web:$TAG"
echo "Release manifest: $ROOT_DIR/releases/${TAG}.json"
