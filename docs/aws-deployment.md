# AWS Deployment Runbook (International, China-Friendly)

This runbook provides a concrete AWS deployment path for production use.

If you do not have an AWS account yet, complete account onboarding first:

- `docs/aws-account-onboarding.md`
- `docs/aws-owner-checklist.md`
- `docs/what-you-need-to-do.md`
- `docs/what-you-need-to-do.zh-CN.md` (Chinese console version)

## 1. Recommended Platform and Region Strategy

### 1.1 Recommended baseline (international-first)

Use this for fastest production rollout if your team is in China but serving global users:

- Region: `ap-southeast-1` (Singapore) as primary
- Compute:
  - API, worker, web: Amazon ECS Fargate
  - Ollama inference: ECS on EC2 GPU instances (`g5.xlarge` or higher)
- Data:
  - PostgreSQL: Amazon RDS for PostgreSQL (Multi-AZ)
  - Redis: Amazon ElastiCache for Redis
  - Vector DB: Qdrant on ECS EC2 (with EBS gp3), or managed Qdrant Cloud
- Edge and security:
  - ALB + ACM TLS certificates
  - CloudFront in front of ALB (optional but recommended)
  - AWS WAF for L7 protection

Why this is recommended:

- ECS is simpler to operate than EKS for this stack size
- Fargate removes host management for stateless services
- GPU workload is isolated to Ollama service where EC2 is required

### 1.2 China mainland compliance path

If you must host inside mainland China (`aws-cn`), you need additional legal/compliance setup:

- Separate AWS China account (`cn-north-1` or `cn-northwest-1`)
- Local business qualification and ICP filing for mainland-hosted public websites
- China-specific domain and compliance operations

For most teams, start in `ap-southeast-1`, then add a China deployment later if required.

## 2. Prerequisites

- AWS CLI v2 configured (`aws configure`)
- Docker installed and logged in to ECR
- Domain managed in Route 53 (or external DNS)
- TLS certificates in ACM for your public domains
- Local `.env` values finalized for production

Repository root used by command examples in this runbook:

```bash
cd /Users/liweiguang/aiagent/complyra
```

Create one production environment file from `.env.example` and set at least:

- `APP_ENV=prod`
- `APP_JWT_SECRET_KEY=<strong-random-secret>`
- `APP_COOKIE_SECURE=true`
- `APP_CORS_ORIGINS=https://<your-web-domain>`
- `APP_TRUSTED_HOSTS=<api-domain>,<web-domain>`
- `APP_DATABASE_URL=postgresql+psycopg://...`
- `APP_REDIS_URL=redis://...`
- `APP_QDRANT_URL=http://<qdrant-service>:6333`
- `APP_OLLAMA_BASE_URL=http://<ollama-service>:11434`

## 3. Step-by-Step Deployment

### Step 0: Validate local prerequisites and prepare production env

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/00_preflight.sh
./scripts/aws/01_prepare_prod_env.sh
./scripts/aws/04_validate_env_prod.sh
```

### Step 1: Create ECR repositories

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/02_bootstrap_ecr.sh
```

### Step 2: Build and push container images

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/03_build_and_push.sh
```

### Step 3: Provision infrastructure with Terraform (recommended)

Terraform now covers ALB, ECS services/task definitions, RDS, ElastiCache, and optional CloudWatch Synthetics.

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/07_terraform_plan.sh
```

Then apply from `infra/terraform` after reviewing `terraform.tfvars`.

Option B: create manually in AWS console

- Create VPC with at least 2 AZs
- Public subnets: ALB/NAT
- Private subnets: ECS services, RDS, Redis
- Security groups:
  - ALB: 80/443 inbound from internet
  - API: allow from ALB SG
  - Worker: no public ingress
  - RDS: allow from API/worker SG
  - Redis: allow from API/worker SG

### Step 4: Verify managed data services

When using Terraform full stack, RDS and ElastiCache are already created.
Verify endpoints and connectivity, then run API health checks.

### Step 5: Provision Qdrant

Option A (recommended): Managed Qdrant Cloud (lower ops overhead)

Option B: Self-host Qdrant on ECS EC2:

- Persistent EBS volume
- Daily snapshots/backup policy
- Private service endpoint only

### Step 6: Provision Ollama inference

For current codebase, Ollama is required.

- Create ECS EC2 capacity provider with GPU instances (for example `g5.xlarge`)
- Run Ollama service in private subnet
- Ensure model availability at startup:
  - keep `APP_OLLAMA_PREPULL=true`
  - pre-pull model in warm-up task if cold start latency is unacceptable
  - optional script-based pre-pull: `./scripts/pull_ollama_model.sh qwen2.5:3b-instruct`

### Step 7: Create ECS task definitions

Create separate tasks:

- `complyra-api` (FastAPI container)
- `complyra-worker` (RQ worker command)
- `complyra-web` (Nginx static web)

Suggested naming for task families and services:

- `complyra-api`
- `complyra-worker`
- `complyra-web`

Inject environment variables through AWS Secrets Manager or SSM Parameter Store, not plaintext task definition values.

For release-based automation, register task definitions directly from release manifests:

```bash
cd /Users/liweiguang/aiagent/complyra
export ECS_TASK_EXECUTION_ROLE_ARN=arn:aws:iam::<ACCOUNT_ID>:role/complyra-ecs-exec
export ECS_TASK_ROLE_ARN=arn:aws:iam::<ACCOUNT_ID>:role/complyra-ecs-task
export APP_DATABASE_URL='postgresql+psycopg://...'
export APP_REDIS_URL='redis://...'
export APP_QDRANT_URL='http://...:6333'
export APP_OLLAMA_BASE_URL='http://...:11434'
export JWT_SECRET_ARN='arn:aws:secretsmanager:...:secret:complyra-jwt'
# Optional:
export SENTRY_DSN_ARN='arn:aws:secretsmanager:...:secret:complyra-sentry'
./scripts/aws/08_register_taskdefs_from_release.sh <release_tag>
```

### Step 8: Create ECS services

- API service behind ALB target group
- Worker service without load balancer
- Web service behind ALB (or CloudFront origin)
- Configure health checks:
  - API: `/api/health/live`
  - Web: `/healthz`

When using Terraform full stack, ECS services are created by Terraform apply.

### Step 9: Configure DNS and TLS

- Request certificate in ACM for API/web domains
- Attach certificate to ALB HTTPS listener
- Route 53 records:
  - `api.<domain>` -> ALB
  - `app.<domain>` -> ALB or CloudFront

### Step 10: Enable observability

- CloudWatch logs for all ECS services
- Prometheus/Grafana deployment in private network or managed alternative
- Set `APP_SENTRY_DSN` for production exception tracking
- Prometheus alert rules are provided in `ops/alert_rules.yml` (error rate, p95 latency, ingest queue backlog)
- Optional CloudWatch Synthetics canary is provisioned via Terraform (`enable_synthetics=true`)

### Step 11: Smoke test and go-live checklist

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/05_smoke_test.sh https://api.<your-domain> <username> <password>
```

- Login works and cookie is secure over HTTPS
- Ingest job transitions: `queued -> processing -> completed`
- Approval flow works end-to-end
- Audit search/export works
- `/api/health/ready` returns all checks `true`
- Rollback plan validated (previous task definition revision)

### Step 12: Deploy ECS services by release tag

After task definitions are ready, deploy all three ECS services and wait for stability:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/09_deploy_services_from_release.sh <cluster_name> <release_tag>
```

By default it deploys services named `complyra-api`, `complyra-worker`, and `complyra-web`.
Override names with environment variables when needed:

- `API_SERVICE_NAME`
- `WORKER_SERVICE_NAME`
- `WEB_SERVICE_NAME`

### Step 13: Manage releases, rollback, and blue/green deployments

`./scripts/aws/03_build_and_push.sh` writes release manifests to `releases/<tag>.json`.

Rollback preparation:

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/06_prepare_rollback.sh <release_tag>
```

Blue/green deployment trigger (when CodeDeploy app + deployment group already exist):

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/aws/10_trigger_codedeploy_ecs.sh <codedeploy_app_name> <deployment_group_name> <task_definition_arn> [container_name] [container_port]
```

### Step 14: Run IaC policy gate before apply

```bash
cd /Users/liweiguang/aiagent/complyra
./scripts/iac/01_conftest_check.sh
```

## 4. CI/CD Recommendation

Use GitHub Actions or GitLab CI:

1. Run backend compile and frontend build
2. Build and tag images by git SHA
3. Push to ECR
4. Deploy new ECS task definition revision
5. Run post-deploy smoke tests
6. Auto-rollback on health check failure

## 5. Security Baseline for Production

- Store secrets in Secrets Manager
- Enforce least-privilege IAM roles per task
- Enable WAF managed rule set on ALB/CloudFront
- Restrict database and Redis to private subnets
- Rotate JWT secrets and DB credentials periodically
- Keep metrics endpoint private or token-protected

## 6. China Connectivity Notes

If your team is in mainland China and users are global:

- Prefer `ap-southeast-1` for lower latency from China compared with US/EU regions
- Use CloudFront and optimized TLS settings for better edge reachability
- Keep operations access through VPN or secure bastion hosts

If mainland users are your primary audience and strict low-latency is required:

- Plan a separate `aws-cn` deployment with legal/compliance readiness
- Keep architecture consistent so global and China stacks share the same code and runbooks

## 7. Suggested Next Improvement

- Extend Terraform to include CodeDeploy blue/green resources
- Expand synthetic checks with additional flows (ingest, audit export)
- Add policy-as-code checks for Terraform/CDK infrastructure changes
