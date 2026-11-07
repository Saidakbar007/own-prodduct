"""NewLife 1.0: profile safety flags (diagnosis/pregnancy/RPP signal)

Revision ID: b7e4d2a6f1c9
Revises: a1d5e8f3c9b4
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b7e4d2a6f1c9'
down_revision: Union[str, Sequence[str], None] = 'a1d5e8f3c9b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.add_column(sa.Column('has_medical_diagnosis', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('is_pregnant', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('disordered_eating_signal', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.drop_column('disordered_eating_signal')
        batch_op.drop_column('is_pregnant')
        batch_op.drop_column('has_medical_diagnosis')
