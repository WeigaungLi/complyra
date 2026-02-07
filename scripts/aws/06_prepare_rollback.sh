#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TAG="${1:-}"

if [ -z "$TAG" ]; then
  echo "Usage: $0 <release_tag>"
  echo "Example: $0 a1b2c3d"
  exit 1
fi

MANIFEST="$ROOT_DIR/releases/$TAG.json"
if [ ! -f "$MANIFEST" ]; then
  echo "Release manifest not found: $MANIFEST"
  exit 1
fi

api_image="$(grep -E '"api_image"' "$MANIFEST" | sed -E 's/.*"api_image"\s*:\s*"([^"]+)".*/\1/')"
web_image="$(grep -E '"web_image"' "$MANIFEST" | sed -E 's/.*"web_image"\s*:\s*"([^"]+)".*/\1/')"

cat <<OUT
Rollback target release: $TAG
API image: $api_image
Web image: $web_image

Next actions:
1. Update task definitions to use these image tags.
2. Deploy updated task definitions to ECS services.
3. Verify /api/health/live and /api/health/ready.

Example update command skeleton:
aws ecs update-service --cluster <cluster> --service complyra-api --force-new-deployment
aws ecs update-service --cluster <cluster> --service complyra-web --force-new-deployment
OUT
