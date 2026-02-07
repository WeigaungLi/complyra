#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_NAME="${1:-}"
DEPLOYMENT_GROUP="${2:-}"
TASKDEF_ARN="${3:-}"
CONTAINER_NAME="${4:-complyra-api}"
CONTAINER_PORT="${5:-8000}"
REGION="${AWS_REGION:-ap-southeast-1}"

if [ -z "$APP_NAME" ] || [ -z "$DEPLOYMENT_GROUP" ] || [ -z "$TASKDEF_ARN" ]; then
  echo "Usage: $0 <codedeploy_app_name> <deployment_group> <task_definition_arn> [container_name] [container_port]"
  echo "Example: $0 complyra-app complyra-api-dg arn:aws:ecs:...:task-definition/complyra-api:12 complyra-api 8000"
  exit 1
fi

if ! command -v aws >/dev/null 2>&1; then
  echo "aws CLI is required"
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required"
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

python3 - "$TMP_DIR/deployment-input.json" "$APP_NAME" "$DEPLOYMENT_GROUP" "$TASKDEF_ARN" "$CONTAINER_NAME" "$CONTAINER_PORT" <<'PY'
import json
import sys

out_path = sys.argv[1]
app_name = sys.argv[2]
deployment_group = sys.argv[3]
taskdef_arn = sys.argv[4]
container_name = sys.argv[5]
container_port = int(sys.argv[6])

appspec = {
    "version": 1,
    "Resources": [
        {
            "TargetService": {
                "Type": "AWS::ECS::Service",
                "Properties": {
                    "TaskDefinition": taskdef_arn,
                    "LoadBalancerInfo": {
                        "ContainerName": container_name,
                        "ContainerPort": container_port,
                    },
                },
            }
        }
    ],
}

payload = {
    "applicationName": app_name,
    "deploymentGroupName": deployment_group,
    "description": f"Complyra blue/green deployment for {taskdef_arn}",
    "revision": {
        "revisionType": "AppSpecContent",
        "appSpecContent": {
            "content": json.dumps(appspec),
        },
    },
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(payload, f)
PY

deployment_id="$(aws deploy create-deployment --cli-input-json file://$TMP_DIR/deployment-input.json --region "$REGION" --query 'deploymentId' --output text)"

echo "CodeDeploy deployment created"
echo "DEPLOYMENT_ID=$deployment_id"
echo "Track status: aws deploy get-deployment --deployment-id $deployment_id --region $REGION"
