"""NewLife 1.0: focus timer logged minutes on season_day

Revision ID: 949e75cacbf3
Revises: b097c5eb1f02
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '949e75cacbf3'
down_revision: Union[str, Sequence[str], None] = 'b097c5eb1f02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('season_day', schema=None) as batch_op:
        batch_op.add_column(sa.Column('logged_minutes', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('season_day', schema=None) as batch_op:
        batch_op.drop_column('logged_minutes')
