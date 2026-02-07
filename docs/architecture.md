# Architecture Specification

## 1. System Goals

This project is designed as a production-ready baseline for enterprise AI assistants that require:

- Private knowledge ingestion and retrieval
- Controlled response release via human approvals
- Real RBAC with tenant isolation
- Compliance audit trails and exportability
- Operational observability and reliability controls

## 2. Service Topology

```text
[React Web]
    |
    v
[FastAPI API]
  |-- Auth/RBAC (JWT + role checks)
  |-- Chat workflow (LangGraph)
  |-- Audit API
  |-- Tenant/User management API
  |-- Ingest API
    |
    | enqueue
    v
[Redis Queue] -> [RQ Worker] -> [Embedding + Qdrant Upsert]

[PostgreSQL]
  |-- users, tenants, user_tenants
  |-- approvals
  |-- audit_logs
  |-- ingest_jobs

[Ollama]
  |-- draft answer generation

[Observability]
  |-- /metrics -> Prometheus -> Grafana
  |-- exceptions -> Sentry (optional)
  |-- CloudWatch Synthetics canary (login/chat/approval journey)
```

## 3. Layered Backend Design

- `app/api/routes`: HTTP interface and request/response contracts
- `app/api/deps`: auth context, tenant scoping, role guards
- `app/services`: domain logic (workflow, LLM, retrieval, ingest, audit)
- `app/db`: persistence models and DB operations
- `app/models`: Pydantic schemas for API boundaries
- `app/core`: config, security utilities, middleware, logging, metrics

This separation supports independent testing, controlled change scope, and clean ownership boundaries.

## 4. Data Isolation and Access Model

- Tenant IDs are explicit in request scope (`X-Tenant-ID`)
- Access is enforced against `user_tenants` assignments
- Approvals and audit queries are restricted to accessible tenants
- Retrieval filters Qdrant results by `tenant_id`

## 5. Workflow Design

### 5.1 Chat Flow

1. Retrieve tenant-scoped chunks from Qdrant
2. Build prompt with injection-aware constraints
3. Generate draft answer from Ollama
4. Apply output policy checks (secret leakage / high-risk pattern detection)
5. Route to approval node when `APP_REQUIRE_APPROVAL=true` and policy allows
6. Return either `pending_approval` or final answer

### 5.2 Approval Flow

- Approvals are persisted with full decision metadata
- Only `admin` or `auditor` can decide pending items
- Users can query decision outcome via approval result endpoint

## 6. Security Controls

- JWT validation with role assertions
- Optional secure session cookie (`HttpOnly`, `SameSite`, configurable domain)
- Trusted host middleware
- Security response headers
- Ingest extension allow-list and sanitized filenames
- CSV export formula injection mitigation in audit export

## 7. Reliability and Operations

- Health endpoints:
  - `/api/health/live`
  - `/api/health/ready` (DB + Qdrant + Ollama)
- Alembic migrations executed on container startup
- Ingest is asynchronous and resumable by job status tracking
- Structured request logging and request ID propagation
- IaC policy gate (OPA/Conftest) for Terraform changes in CI

## 8. Scalability Path

- Horizontal scale API and worker independently
- Move Qdrant to dedicated high-IO nodes
- Use managed PostgreSQL and Redis
- Swap or extend LLM provider through service adapter pattern
- Add policy engine (PBAC/ABAC), DLP, and PII redaction pipeline

## 9. Non-Goals of This Repository

- Full SSO/SAML enterprise identity integration
- Full policy engine and legal retention lifecycle
- Multi-region active-active conflict resolution

These are expected next-stage enhancements after MVP-to-production adoption.
