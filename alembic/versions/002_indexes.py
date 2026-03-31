"""Add database indexes for performance.

Revision ID: 002_indexes
Revises: 001_initial
Create Date: 2025-03-29

"""

from typing import Sequence, Union

from alembic import op


revision: str = "002_indexes"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Jobs table indexes
    op.create_index("ix_jobs_problem_type", "jobs", ["problem_type"])
    op.create_index("ix_jobs_backend", "jobs", ["backend"])
    op.create_index("ix_jobs_user_status", "jobs", ["user_id", "status"])
    op.create_index("ix_jobs_created_status", "jobs", ["created_at", "status"])

    # Users table indexes
    op.create_index("ix_users_is_active", "users", ["is_active"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # Keys table indexes
    op.create_index("ix_keys_is_active", "keys", ["is_active"])
    op.create_index("ix_keys_expires_at", "keys", ["expires_at"])
    op.create_index("ix_keys_user_type", "keys", ["user_id", "key_type"])

    # Tokens table indexes
    op.create_index("ix_tokens_revoked", "tokens", ["revoked_at"])
    op.create_index("ix_tokens_type", "tokens", ["token_type"])

    # Audit log indexes
    op.create_index("ix_audit_log_resource", "audit_log", ["resource_type", "resource_id"])
    op.create_index("ix_audit_log_action_time", "audit_log", ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_action_time", table_name="audit_log")
    op.drop_index("ix_audit_log_resource", table_name="audit_log")
    op.drop_index("ix_tokens_type", table_name="tokens")
    op.drop_index("ix_tokens_revoked", table_name="tokens")
    op.drop_index("ix_keys_user_type", table_name="keys")
    op.drop_index("ix_keys_expires_at", table_name="keys")
    op.drop_index("ix_keys_is_active", table_name="keys")
    op.drop_index("ix_users_created_at", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_index("ix_jobs_created_status", table_name="jobs")
    op.drop_index("ix_jobs_user_status", table_name="jobs")
    op.drop_index("ix_jobs_backend", table_name="jobs")
    op.drop_index("ix_jobs_problem_type", table_name="jobs")
