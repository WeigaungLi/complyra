#!/usr/bin/env sh
set -eu

MODEL_NAME="${1:-qwen2.5:3b-instruct}"
OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"

echo "Pulling model '${MODEL_NAME}' from ${OLLAMA_BASE_URL} ..."
curl --fail --show-error --silent \
  -X POST "${OLLAMA_BASE_URL}/api/pull" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"${MODEL_NAME}\",\"stream\":false}" >/dev/null

echo "Model '${MODEL_NAME}' is ready."
