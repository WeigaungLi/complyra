# Terraform Infrastructure (Complyra)

This module now provisions a production-oriented AWS stack for Complyra.

## What it creates

- Networking: VPC, internet gateway, public/private subnets, NAT, route tables
- Security groups for ALB, API, web, worker, RDS, Redis, and Ollama access
- ECS cluster with Container Insights
- IAM roles for ECS task execution and task runtime
- Secrets Manager entries for JWT (and optional Sentry DSN)
- ALB, target groups, listener rules, and optional HTTPS listener
- ECS task definitions and ECS services for API, worker, and web
- RDS PostgreSQL instance with private subnet placement
- ElastiCache Redis replication group with private subnet placement
- CloudWatch log groups for ECS services
- Optional CloudWatch Synthetics canary (login/chat/approval chain)

## Input highlights

- Container image source: `ecr_registry`, `image_tag`
- Runtime endpoints: `app_qdrant_url`, `app_ollama_base_url`
- DB/cache sizing and protection flags
- Synthetics schedule/credentials and start behavior

Review all variables in `variables.tf` before apply.

## Usage

```bash
cd /Users/liweiguang/aiagent/complyra/infra/terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars with production values
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
```

## Policy-as-code gate (OPA/Conftest)

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/iac/01_conftest_check.sh
```

Policy files are located in `infra/policy/terraform/`.

## Notes

- Keep `db_password`, `jwt_secret_value`, and `synthetics_password` out of git.
- Set `acm_certificate_arn` to enable HTTPS listener on ALB.
- `enable_synthetics=true` creates canary resources and incurs CloudWatch Synthetics cost.
- This module assumes Qdrant/Ollama are reachable via configured internal endpoints.
