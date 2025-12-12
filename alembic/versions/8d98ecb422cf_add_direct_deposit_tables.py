"""add direct deposit run/process tables

Revision ID: 8d98ecb422cf
Revises: a83476e420e2
Create Date: 2025-12-12 15:45:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d98ecb422cf"
down_revision: Union[str, Sequence[str], None] = "a83476e420e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_bot_direct_deposit_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("runid", sa.String(length=100), nullable=False),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runid"),
    )
    op.create_index(op.f("ix_ai_bot_direct_deposit_runs_id"), "ai_bot_direct_deposit_runs", ["id"], unique=False)
    op.create_index(op.f("ix_ai_bot_direct_deposit_runs_runid"), "ai_bot_direct_deposit_runs", ["runid"], unique=True)

    op.create_table(
        "ai_bot_direct_deposit_process_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("runid", sa.String(length=100), nullable=True),
        sa.Column("emplid", sa.String(length=50), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("routing_number", sa.String(length=50), nullable=True),
        sa.Column("bank_account", sa.String(length=50), nullable=True),
        sa.Column("amount_dollars", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True, server_default=sa.text("0")),
        sa.Column("message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ai_bot_direct_deposit_process_log_id"),
        "ai_bot_direct_deposit_process_log",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_bot_direct_deposit_process_log_runid"),
        "ai_bot_direct_deposit_process_log",
        ["runid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_bot_direct_deposit_process_log_emplid"),
        "ai_bot_direct_deposit_process_log",
        ["emplid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_bot_direct_deposit_process_log_name"),
        "ai_bot_direct_deposit_process_log",
        ["name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_bot_direct_deposit_process_log_status"),
        "ai_bot_direct_deposit_process_log",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_bot_direct_deposit_process_log_status"), table_name="ai_bot_direct_deposit_process_log")
    op.drop_index(op.f("ix_ai_bot_direct_deposit_process_log_name"), table_name="ai_bot_direct_deposit_process_log")
    op.drop_index(op.f("ix_ai_bot_direct_deposit_process_log_emplid"), table_name="ai_bot_direct_deposit_process_log")
    op.drop_index(op.f("ix_ai_bot_direct_deposit_process_log_runid"), table_name="ai_bot_direct_deposit_process_log")
    op.drop_index(op.f("ix_ai_bot_direct_deposit_process_log_id"), table_name="ai_bot_direct_deposit_process_log")
    op.drop_table("ai_bot_direct_deposit_process_log")

    op.drop_index(op.f("ix_ai_bot_direct_deposit_runs_runid"), table_name="ai_bot_direct_deposit_runs")
    op.drop_index(op.f("ix_ai_bot_direct_deposit_runs_id"), table_name="ai_bot_direct_deposit_runs")
    op.drop_table("ai_bot_direct_deposit_runs")
