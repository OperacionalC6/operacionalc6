"""schema inicial: teams, users, audit_logs, pipeline_runs, metrics

Revision ID: 0001_init
Revises:
Create Date: 2026-08-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "teams",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Não chamar user_role.create(...) explicitamente aqui: create_table já cria o
    # tipo enum sozinho ao usá-lo numa coluna. Criar os dois é justamente o que
    # causa "type already exists" se a migration for reexecutada depois de uma
    # falha parcial (aconteceu no primeiro deploy real, por isso este comentário).
    user_role = postgresql.ENUM("admin", "gestor", "membro", name="user_role")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="membro"),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_email_snapshot", sa.String(255), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(200), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("extra", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    pipeline_status = postgresql.ENUM("running", "success", "failed", name="pipeline_status")
    pipeline_trigger = postgresql.ENUM("schedule", "manual", name="pipeline_trigger")

    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", pipeline_status, nullable=False, server_default="running"),
        sa.Column("trigger", pipeline_trigger, nullable=False, server_default="schedule"),
        sa.Column("records_ingested", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "team_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("metric_date", sa.Date, nullable=False),
        sa.Column("metric_name", sa.String(120), nullable=False),
        sa.Column("value", sa.Numeric(18, 2), nullable=False),
        sa.Column("dimensions", postgresql.JSONB, nullable=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column(
            "pipeline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("pipeline_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_metrics_team_id", "metrics", ["team_id"])
    op.create_index("ix_metrics_metric_date", "metrics", ["metric_date"])
    op.create_index("ix_metrics_metric_name", "metrics", ["metric_name"])


def downgrade() -> None:
    op.drop_index("ix_metrics_metric_name", table_name="metrics")
    op.drop_index("ix_metrics_metric_date", table_name="metrics")
    op.drop_index("ix_metrics_team_id", table_name="metrics")
    op.drop_table("metrics")

    op.drop_table("pipeline_runs")
    postgresql.ENUM(name="pipeline_trigger").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="pipeline_status").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)

    op.drop_table("teams")
