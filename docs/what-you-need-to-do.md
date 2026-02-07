# What You Need To Do (Manual Actions)

This repository now includes all automation that can run without your AWS account credentials.

## 1. Account and billing (must be done by you)

- Create AWS account: `https://aws.amazon.com/`
- Complete phone and payment verification
- Enable root MFA
- Create billing budget and email alerts

## 2. IAM setup (must be done by you)

- Create IAM admin user for daily operations
- Create access key for CLI
- Run `aws configure` locally with that key

## 3. Local tooling install (must be done by you)

- Install AWS CLI v2
- Install Docker Desktop or Docker Engine

After installing:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/00_preflight.sh
```

## 4. Fill production configuration (must be done by you)

- Edit `/Users/liweiguang/aiagent/complyra/.env.prod`
- Replace:
  - `APP_CORS_ORIGINS`
  - `APP_TRUSTED_HOSTS`
  - `APP_DATABASE_URL`
  - `APP_REDIS_URL`
  - `APP_QDRANT_URL`
  - `APP_OLLAMA_BASE_URL`
  - `APP_SENTRY_DSN` (optional)

Validate `.env.prod` after edits:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/04_validate_env_prod.sh
```

## 5. Cloud resources (must be done by you)

- VPC, subnets, route tables, NAT
- Security groups
- RDS PostgreSQL
- ElastiCache Redis
- Qdrant service
- Ollama GPU runtime
- ECS cluster/services
- ALB, Route 53, ACM TLS

Optional Terraform full-stack apply (network + ALB + ECS + RDS + Redis + canary):

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/07_terraform_plan.sh
./scripts/iac/01_conftest_check.sh
```

## 6. Deployment commands (automation already prepared)

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/02_bootstrap_ecr.sh
./scripts/aws/03_build_and_push.sh <release_tag>
./scripts/aws/08_register_taskdefs_from_release.sh <release_tag>
./scripts/aws/09_deploy_services_from_release.sh <cluster_name> <release_tag>
```

## 7. Final verification

- Open `https://api.<your-domain>/api/health/live`
- Open `https://api.<your-domain>/api/health/ready`
- Run login -> ingest -> ask -> approval -> audit flow

Optional automated smoke test:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/05_smoke_test.sh https://api.<your-domain> <username> <password>
```

Rollback preparation (optional):

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/06_prepare_rollback.sh <release_tag>
```

Blue/green deployment trigger (optional, requires CodeDeploy setup):

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/10_trigger_codedeploy_ecs.sh <codedeploy_app_name> <deployment_group_name> <task_definition_arn>
```
