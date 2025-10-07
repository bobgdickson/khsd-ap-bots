"""Rename ap_bot tables to ai_bot

Revision ID: b2c3d4e5f6a7
Revises: 13e7b7b70582
Create Date: 2025-10-06 17:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = '13e7b7b70582'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE_OLD = 'ap_bot_process_log'
TABLE_NEW = 'ai_bot_process_log'
INDEXES = (
    'ix_ap_bot_process_log_filename',
    'ix_ap_bot_process_log_invoice',
    'ix_ap_bot_process_log_runid',
    'ix_ap_bot_process_log_status',
    'ix_ap_bot_process_log_voucher_id',
)


def _rename_indexes(table_name: str, mapping: dict[str, str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {idx['name'] for idx in inspector.get_indexes(table_name)}
    for old_name, new_name in mapping.items():
        if old_name in existing:
            op.rename_index(old_name, new_name)


def upgrade() -> None:
    op.rename_table(TABLE_OLD, TABLE_NEW)
    mapping = {idx: idx.replace('ap_bot_process_log', 'ai_bot_process_log') for idx in INDEXES}
    _rename_indexes(TABLE_NEW, mapping)


def downgrade() -> None:
    mapping = {idx.replace('ap_bot_process_log', 'ai_bot_process_log'): idx for idx in INDEXES}
    _rename_indexes(TABLE_NEW, mapping)
    op.rename_table(TABLE_NEW, TABLE_OLD)
