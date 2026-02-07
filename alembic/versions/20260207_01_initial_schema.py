"""Initial schema for enterprise knowledge assistant.

Revision ID: 20260207_01
Revises:
Create Date: 2026-02-07 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260207_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.String(length=128), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=128), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("default_tenant_id", sa.String(length=128), sa.ForeignKey("tenants.tenant_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=False)

    op.create_table(
        "user_tenants",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(length=128), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),
    )
    op.create_index("ix_user_tenants_user_id", "user_tenants", ["user_id"], unique=False)
    op.create_index("ix_user_tenants_tenant_id", "user_tenants", ["tenant_id"], unique=False)

    op.create_table(
        "approvals",
        sa.Column("approval_id", sa.String(length=128), primary_key=True),
        sa.Column("user_id", sa.String(length=128), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("draft_answer", sa.Text(), nullable=False),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_by", sa.String(length=128), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
    )
    op.create_index("ix_approvals_tenant_status", "approvals", ["tenant_id", "status"], unique=False)
    op.create_index("ix_approvals_user", "approvals", ["user_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("user", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=False),
        sa.Column("metadata", sa.Text(), nullable=False),
    )
    op.create_index("ix_audit_logs_tenant_ts", "audit_logs", ["tenant_id", "timestamp"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)

    op.create_table(
        "ingest_jobs",
        sa.Column("job_id", sa.String(length=128), primary_key=True),
        sa.Column("tenant_id", sa.String(length=128), sa.ForeignKey("tenants.tenant_id"), nullable=False),
        sa.Column("created_by", sa.String(length=128), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ingest_jobs_tenant_created", "ingest_jobs", ["tenant_id", "created_at"], unique=False)
    op.create_index("ix_ingest_jobs_status", "ingest_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingest_jobs_status", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_tenant_created", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")

    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_ts", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_approvals_user", table_name="approvals")
    op.drop_index("ix_approvals_tenant_status", table_name="approvals")
    op.drop_table("approvals")

    op.drop_index("ix_user_tenants_tenant_id", table_name="user_tenants")
    op.drop_index("ix_user_tenants_user_id", table_name="user_tenants")
    op.drop_table("user_tenants")

    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

    op.drop_table("tenants")
