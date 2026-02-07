# Operations Runbook

## 1. Production Readiness Checklist

- [ ] `APP_ENV=prod`
- [ ] Strong `APP_JWT_SECRET_KEY`
- [ ] `APP_COOKIE_SECURE=true`
- [ ] `APP_CORS_ORIGINS` restricted to trusted web origins
- [ ] `APP_TRUSTED_HOSTS` set to real hostnames
- [ ] PostgreSQL and Redis running in private subnets
- [ ] Alembic migration tested in staging
- [ ] Prometheus, Grafana, and alerting configured
- [ ] Sentry DSN configured and tested
- [ ] Backup and restore procedure validated

## 2. Health and SLO Signals

### Core health checks

- Live: `GET /api/health/live`
- Ready: `GET /api/health/ready`
- Synthetic journey: CloudWatch Synthetics canary (`login -> chat -> approval-result`)

### Suggested SLO targets

- API availability: >= 99.9%
- P95 chat response time: <= 3 seconds (excluding human approval wait)
- Ingest job success rate: >= 99%
- Approval decision latency: business-defined target (for example <= 30 minutes)

### Key metrics to track

- HTTP request rate, latency, and error rate
- Queue depth and ingest job duration
- Qdrant query latency
- Ollama generation latency and failure rate
- Count of `chat_blocked_by_policy` events and top matched policy rules

Alert rules are defined in `ops/alert_rules.yml`.

## 3. Incident Response Playbook

### Incident class A: API unavailable

1. Check ECS task health and ALB target health
2. Validate `/api/health/live` and `/api/health/ready`
3. Check recent deployments and rollback if needed
4. Review CloudWatch logs and Sentry events

### Incident class B: Ingest backlog

1. Check Redis connectivity and queue depth
2. Check worker task count and worker logs
3. Scale worker replicas up temporarily
4. Confirm Qdrant and embedding service performance

### Incident class C: Approval flow stuck

1. Query pending approvals via API
2. Check DB connectivity and write permissions
3. Validate role assignments (`admin`/`auditor`)
4. Check audit log entries for failed decision actions

### Incident class D: Excessive policy blocks

1. Query audit logs for `chat_blocked_by_policy` actions and affected tenants
2. Inspect `policy_violations` metadata to identify the dominant regex rule
3. Confirm whether the block is expected or a false positive
4. Tune `APP_OUTPUT_POLICY_BLOCK_PATTERNS` and retest in staging before production rollout

## 4. Backup and Recovery

### PostgreSQL

- Use automated RDS snapshots
- Retain daily backups and point-in-time recovery
- Test restore quarterly in staging

### Qdrant

- If self-hosted, snapshot persistent volume daily
- Test collection restore on a non-production environment

### Application config and secrets

- Store in versioned Secrets Manager / Parameter Store
- Track changes with audited IAM access

## 5. Deployment Safety

- Deploy immutable image tags by commit SHA
- Roll out API and worker first, then web
- Run smoke tests before promoting traffic
- Keep previous task definition revision for immediate rollback

## 6. Security Operations

- Rotate credentials and tokens on a regular schedule
- Monitor failed login spikes and unusual tenant access patterns
- Review audit exports and access to export endpoints
- Ensure dependencies are patched on a monthly cadence

## 7. Change Management for Enterprise Teams

- Maintain architecture decision records for major changes
- Require code review for auth, tenancy, and audit modules
- Enforce CI checks for compile/build and migration validation
- Maintain a release note per deployment with rollback instructions
