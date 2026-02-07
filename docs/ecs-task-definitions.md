# ECS Task Definition Templates

This document explains how to use the ECS task definition templates under `infra/ecs/`.

## Files

- `infra/ecs/taskdef-api.json`
- `infra/ecs/taskdef-worker.json`
- `infra/ecs/taskdef-web.json`

## Placeholders to replace

- `<ECS_TASK_EXECUTION_ROLE_ARN>`
- `<ECS_TASK_ROLE_ARN>`
- `<ECR_REGISTRY>`
- `<TAG>`
- `<DATABASE_URL>`
- `<REDIS_URL>`
- `<QDRANT_URL>`
- `<OLLAMA_BASE_URL>`
- `<JWT_SECRET_ARN>`
- `<SENTRY_DSN_ARN>`

## Register task definitions

```bash
cd /Users/liweiguang/aiagent/complyra
aws ecs register-task-definition --cli-input-json file://infra/ecs/taskdef-api.json --region ap-southeast-1
aws ecs register-task-definition --cli-input-json file://infra/ecs/taskdef-worker.json --region ap-southeast-1
aws ecs register-task-definition --cli-input-json file://infra/ecs/taskdef-web.json --region ap-southeast-1
```

## Automated registration from release manifest

For production releases, prefer the script-based registration flow:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/08_register_taskdefs_from_release.sh <release_tag>
```

## Notes

- Keep secrets in AWS Secrets Manager and reference them via `secrets`.
- Use immutable image tags in production, for example commit SHA tags.
- API and web services should attach to ALB target groups with health checks.
