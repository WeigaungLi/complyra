# Optimization Roadmap

This roadmap prioritizes improvements that provide the highest production value for Complyra.

## P0 (implemented)

- CI pipeline for backend compile, tests, and frontend build
- Integration tests for auth, tenant isolation, and approval workflow
- AWS deployment automation scripts for preflight, env validation, smoke tests, and rollback preparation
- ECS task definition templates for API/worker/web
- Prometheus alert rules for error rate, latency, and queue backlog
- Structured JSON request logging with request ID correlation
- Release-based ECS deployment automation (`08`/`09`) and CodeDeploy trigger (`10`)
- Output policy guard for generated responses with configurable regex rules
- Full-stack Terraform for ALB, ECS services/task definitions, RDS, and ElastiCache
- CloudWatch Synthetics canary for login/chat/approval chain
- OPA/Conftest policy gate for Terraform in CI

## P1 (next 1-2 weeks)

- Expand Terraform to include CodeDeploy blue/green resources
- Add more Synthetics journeys (ingest pipeline and audit export)
- Add regression tests for deployment scripts in CI (shellcheck + dry-run harness)

## P2 (next 2-4 weeks)

- Add retrieval evaluation harness with golden set and quality score gating
- Add prompt input policy checks and jailbreak scoring before LLM invocation
- Add policy-as-code checks for Kubernetes/Helm manifests if EKS is introduced

## P3 (scaling phase)

- Introduce API rate limiting and bot protection
- Add SSO/SAML support for enterprise identity providers
- Add multi-region disaster recovery strategy
- Add cost observability dashboards per service and per tenant
