#!/usr/bin/env sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
TAG="${1:-}"
REGION="${AWS_REGION:-ap-southeast-1}"

if [ -z "$TAG" ]; then
  echo "Usage: $0 <release_tag>"
  echo "Example: $0 a1b2c3d"
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

MANIFEST="$ROOT_DIR/releases/$TAG.json"
if [ ! -f "$MANIFEST" ]; then
  echo "Release manifest not found: $MANIFEST"
  exit 1
fi

require_env() {
  key="$1"
  val="$(eval "printf %s \"\${$key:-}\"")"
  if [ -z "$val" ]; then
    echo "Missing required environment variable: $key"
    exit 1
  fi
}

require_env ECS_TASK_EXECUTION_ROLE_ARN
require_env ECS_TASK_ROLE_ARN
require_env APP_DATABASE_URL
require_env APP_REDIS_URL
require_env APP_QDRANT_URL
require_env APP_OLLAMA_BASE_URL
require_env JWT_SECRET_ARN

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

python3 - "$MANIFEST" "$ROOT_DIR/infra/ecs/taskdef-api.json" "$ROOT_DIR/infra/ecs/taskdef-worker.json" "$ROOT_DIR/infra/ecs/taskdef-web.json" "$TMP_DIR" \
  "$ECS_TASK_EXECUTION_ROLE_ARN" "$ECS_TASK_ROLE_ARN" "$APP_DATABASE_URL" "$APP_REDIS_URL" "$APP_QDRANT_URL" "$APP_OLLAMA_BASE_URL" "$JWT_SECRET_ARN" "${SENTRY_DSN_ARN:-}" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
api_template_path = Path(sys.argv[2])
worker_template_path = Path(sys.argv[3])
web_template_path = Path(sys.argv[4])
out_dir = Path(sys.argv[5])

exec_role = sys.argv[6]
task_role = sys.argv[7]
database_url = sys.argv[8]
redis_url = sys.argv[9]
qdrant_url = sys.argv[10]
ollama_url = sys.argv[11]
jwt_secret_arn = sys.argv[12]
sentry_dsn_arn = sys.argv[13]

manifest = json.loads(manifest_path.read_text())
api_image = manifest["api_image"]
web_image = manifest["web_image"]

if "/complyra-api:" not in api_image:
    raise SystemExit(f"Unexpected api_image format: {api_image}")

ecr_registry, tag = api_image.split("/complyra-api:", 1)
if not tag:
    raise SystemExit("Could not parse release tag from api_image")

replacements = {
    "<ECS_TASK_EXECUTION_ROLE_ARN>": exec_role,
    "<ECS_TASK_ROLE_ARN>": task_role,
    "<ECR_REGISTRY>": ecr_registry,
    "<TAG>": tag,
    "<DATABASE_URL>": database_url,
    "<REDIS_URL>": redis_url,
    "<QDRANT_URL>": qdrant_url,
    "<OLLAMA_BASE_URL>": ollama_url,
    "<JWT_SECRET_ARN>": jwt_secret_arn,
    "<SENTRY_DSN_ARN>": sentry_dsn_arn,
}

def replace_values(value):
    if isinstance(value, str):
        for src, dst in replacements.items():
            value = value.replace(src, dst)
        return value
    if isinstance(value, list):
        return [replace_values(item) for item in value]
    if isinstance(value, dict):
        return {key: replace_values(item) for key, item in value.items()}
    return value

def render(template_path: Path, output_path: Path, remove_sentry: bool):
    data = json.loads(template_path.read_text())
    rendered = replace_values(data)
    if remove_sentry:
        for container in rendered.get("containerDefinitions", []):
            secrets = container.get("secrets", [])
            container["secrets"] = [item for item in secrets if item.get("name") != "APP_SENTRY_DSN"]
    output_path.write_text(json.dumps(rendered, indent=2) + "\n")

render(api_template_path, out_dir / "taskdef-api.rendered.json", remove_sentry=(not sentry_dsn_arn))
render(worker_template_path, out_dir / "taskdef-worker.rendered.json", remove_sentry=False)
render(web_template_path, out_dir / "taskdef-web.rendered.json", remove_sentry=False)
PY

api_taskdef_arn="$(aws ecs register-task-definition --cli-input-json file://$TMP_DIR/taskdef-api.rendered.json --region "$REGION" --query 'taskDefinition.taskDefinitionArn' --output text)"
worker_taskdef_arn="$(aws ecs register-task-definition --cli-input-json file://$TMP_DIR/taskdef-worker.rendered.json --region "$REGION" --query 'taskDefinition.taskDefinitionArn' --output text)"
web_taskdef_arn="$(aws ecs register-task-definition --cli-input-json file://$TMP_DIR/taskdef-web.rendered.json --region "$REGION" --query 'taskDefinition.taskDefinitionArn' --output text)"

cat > "$ROOT_DIR/releases/${TAG}.taskdefs.json" <<JSON
{
  "release_tag": "$TAG",
  "region": "$REGION",
  "api_task_definition": "$api_taskdef_arn",
  "worker_task_definition": "$worker_taskdef_arn",
  "web_task_definition": "$web_taskdef_arn"
}
JSON

echo "Registered task definitions for release: $TAG"
echo "API_TASKDEF_ARN=$api_taskdef_arn"
echo "WORKER_TASKDEF_ARN=$worker_taskdef_arn"
echo "WEB_TASKDEF_ARN=$web_taskdef_arn"
echo "Task definition manifest: $ROOT_DIR/releases/${TAG}.taskdefs.json"
