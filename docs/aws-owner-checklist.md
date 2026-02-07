# AWS Deployment Ownership Checklist

This checklist separates what Complyra automation can do and what you must do manually.

## Done by repository automation (you can run these scripts)

- [ ] Validate local prerequisites: `./scripts/aws/00_preflight.sh`
- [ ] Generate production env template: `./scripts/aws/01_prepare_prod_env.sh`
- [ ] Validate `.env.prod`: `./scripts/aws/04_validate_env_prod.sh`
- [ ] Create ECR repositories and login: `./scripts/aws/02_bootstrap_ecr.sh`
- [ ] Build and push API/Web images: `./scripts/aws/03_build_and_push.sh`
- [ ] Run Terraform plan for full stack IaC: `./scripts/aws/07_terraform_plan.sh`
- [ ] Run Terraform policy gate before apply: `./scripts/iac/01_conftest_check.sh`
- [ ] Register ECS task definitions from a release manifest: `./scripts/aws/08_register_taskdefs_from_release.sh <release_tag>`
- [ ] Deploy ECS services by release tag: `./scripts/aws/09_deploy_services_from_release.sh <cluster_name> <release_tag>`
- [ ] Run post-deploy smoke checks: `./scripts/aws/05_smoke_test.sh`
- [ ] Prepare rollback target from release manifest: `./scripts/aws/06_prepare_rollback.sh`
- [ ] Trigger CodeDeploy blue/green rollout (optional): `./scripts/aws/10_trigger_codedeploy_ecs.sh`
- [ ] Configure CloudWatch Synthetics canary credentials and enable canary start

## Must be done by you (console or account-level decisions)

- [ ] Create AWS account and verify payment method
- [ ] Enable root MFA and secure root credentials
- [ ] Create IAM admin user and access keys
- [ ] Configure AWS budget and billing alerts
- [ ] Create VPC, subnets, route tables, NAT gateways
- [ ] Create security groups for ALB/API/Worker/RDS/Redis/Ollama
- [ ] Provision RDS PostgreSQL
- [ ] Provision ElastiCache Redis
- [ ] Provision Qdrant (managed or self-hosted)
- [ ] Provision Ollama runtime (GPU EC2 or equivalent)
- [ ] Create ECS cluster, task definitions, and services
- [ ] Create ALB listeners and target groups
- [ ] Configure Route 53 DNS records and ACM certificates
- [ ] Configure Secrets Manager/SSM for runtime secrets
- [ ] Run production smoke tests

## Recommended order

1. Finish account and IAM hardening.
2. Finish networking and data services.
3. Push images and deploy ECS services.
4. Configure DNS/TLS and run smoke tests.
5. Enable monitoring and alerting.
