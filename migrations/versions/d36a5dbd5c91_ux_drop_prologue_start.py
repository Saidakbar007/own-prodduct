"""ux: drop season.prologue_start (пролог убран — сезон стартует сразу)

Revision ID: d36a5dbd5c91
Revises: dee84d20d4b7
Create Date: 2026-10-31 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd36a5dbd5c91'
down_revision: Union[str, Sequence[str], None] = 'dee84d20d4b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('season', schema=None) as batch_op:
        batch_op.drop_column('prologue_start')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('season', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prologue_start', sa.Date(), nullable=True))
