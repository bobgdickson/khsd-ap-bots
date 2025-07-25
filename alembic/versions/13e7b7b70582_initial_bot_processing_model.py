"""Initial Bot processing Model

Revision ID: 13e7b7b70582
Revises: 
Create Date: 2025-07-15 10:44:31.685470

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13e7b7b70582'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        'ap_bot_process_log',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('runid', sa.String, nullable=True),
        sa.Column('filename', sa.String, nullable=True),
        sa.Column('voucher_id', sa.String, nullable=True),
        sa.Column('amount', sa.Float, nullable=True),
        sa.Column('invoice', sa.String, nullable=True),
        sa.Column('status', sa.String, nullable=True),
    )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
