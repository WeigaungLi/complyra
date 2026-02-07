# Release and Rollback Strategy

Complyra release automation is image-tag based and manifest-driven.

## Release tagging

`./scripts/aws/03_build_and_push.sh` uses the following tag strategy:

1. Explicit tag argument if provided
2. Git short SHA if available
3. UTC timestamp fallback

Each release writes metadata to `releases/<tag>.json`.

## Release deployment flow

1. Build and push release images:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/03_build_and_push.sh <release_tag>
```

Before deployment, run IaC policy checks:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/iac/01_conftest_check.sh
```

2. Register task definitions from release metadata:

```bash
./scripts/aws/08_register_taskdefs_from_release.sh <release_tag>
```

3. Deploy ECS services by release:

```bash
./scripts/aws/09_deploy_services_from_release.sh <cluster_name> <release_tag>
```

## Release metadata

A release manifest contains:

- `release_tag`
- `created_at_utc`
- `region`
- `account_id`
- `api_image`
- `web_image`

This metadata is used as rollback source of truth.

## Rollback workflow

1. Pick a known-good release tag from `releases/`.
2. Run:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/06_prepare_rollback.sh <release_tag>
```

3. Update ECS task definitions to the release images.
4. Force ECS service deployments.
5. Run smoke tests using `./scripts/aws/05_smoke_test.sh`.

## Optional blue/green release trigger

Use this when CodeDeploy ECS blue/green is configured:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/10_trigger_codedeploy_ecs.sh <codedeploy_app_name> <deployment_group_name> <task_definition_arn>
```

## Operational guidance

- Use immutable tags in production, never `latest`.
- Keep at least the last 10 release manifests for quick rollback.
- Store release manifests in source control if your release process allows it.
