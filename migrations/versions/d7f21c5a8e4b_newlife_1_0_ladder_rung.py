"""NewLife 1.0: season.ladder_rung (confidence/public speaking ladders)

Revision ID: d7f21c5a8e4b
Revises: c1b2e4f90a3d
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd7f21c5a8e4b'
down_revision: Union[str, Sequence[str], None] = 'c1b2e4f90a3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('season', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ladder_rung', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('season', schema=None) as batch_op:
        batch_op.drop_column('ladder_rung')
