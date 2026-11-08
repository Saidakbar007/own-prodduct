"""NewLife 1.0: workout_log on season_day (ACSM full-body programs, /workout)

Revision ID: c1b2e4f90a3d
Revises: a9768ac15d93
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c1b2e4f90a3d'
down_revision: Union[str, Sequence[str], None] = 'a9768ac15d93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('season_day', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workout_log', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('season_day', schema=None) as batch_op:
        batch_op.drop_column('workout_log')
