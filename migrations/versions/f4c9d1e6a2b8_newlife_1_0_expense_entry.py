"""NewLife 1.0: expense_entry table (finance category tracker)

Revision ID: f4c9d1e6a2b8
Revises: e3a6f0c2b7d1
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f4c9d1e6a2b8'
down_revision: Union[str, Sequence[str], None] = 'e3a6f0c2b7d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'expense_entry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('logged_on', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('expense_entry', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_expense_entry_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_expense_entry_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_expense_entry_logged_on'), ['logged_on'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('expense_entry', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_expense_entry_logged_on'))
        batch_op.drop_index(batch_op.f('ix_expense_entry_category'))
        batch_op.drop_index(batch_op.f('ix_expense_entry_uid'))
    op.drop_table('expense_entry')
