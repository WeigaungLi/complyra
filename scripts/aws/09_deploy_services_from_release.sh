#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CLUSTER_NAME="${1:-}"
TAG="${2:-}"
REGION="${AWS_REGION:-ap-southeast-1}"
API_SERVICE="${API_SERVICE_NAME:-complyra-api}"
WORKER_SERVICE="${WORKER_SERVICE_NAME:-complyra-worker}"
WEB_SERVICE="${WEB_SERVICE_NAME:-complyra-web}"

if [ -z "$CLUSTER_NAME" ] || [ -z "$TAG" ]; then
  echo "Usage: $0 <cluster_name> <release_tag>"
  echo "Example: $0 complyra-cluster a1b2c3d"
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required"
  exit 1
fi

register_output="$("$ROOT_DIR/scripts/aws/08_register_taskdefs_from_release.sh" "$TAG")"
printf "%s\n" "$register_output"

api_taskdef="$(printf "%s\n" "$register_output" | grep '^API_TASKDEF_ARN=' | cut -d '=' -f 2-)"
worker_taskdef="$(printf "%s\n" "$register_output" | grep '^WORKER_TASKDEF_ARN=' | cut -d '=' -f 2-)"
web_taskdef="$(printf "%s\n" "$register_output" | grep '^WEB_TASKDEF_ARN=' | cut -d '=' -f 2-)"

if [ -z "$api_taskdef" ] || [ -z "$worker_taskdef" ] || [ -z "$web_taskdef" ]; then
  echo "Failed to parse task definition ARNs from registration output"
  exit 1
fi

aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$API_SERVICE" \
  --task-definition "$api_taskdef" \
  --force-new-deployment \
  --region "$REGION" >/dev/null

aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$WORKER_SERVICE" \
  --task-definition "$worker_taskdef" \
  --force-new-deployment \
  --region "$REGION" >/dev/null

aws ecs update-service \
  --cluster "$CLUSTER_NAME" \
  --service "$WEB_SERVICE" \
  --task-definition "$web_taskdef" \
  --force-new-deployment \
  --region "$REGION" >/dev/null

echo "Waiting for ECS services to become stable..."
aws ecs wait services-stable \
  --cluster "$CLUSTER_NAME" \
  --services "$API_SERVICE" "$WORKER_SERVICE" "$WEB_SERVICE" \
  --region "$REGION"

echo "ECS deployment completed for release: $TAG"
echo "Cluster: $CLUSTER_NAME"
echo "Services: $API_SERVICE, $WORKER_SERVICE, $WEB_SERVICE"
echo "Recommended next step: ./scripts/aws/05_smoke_test.sh https://api.<your-domain> <username> <password>"
