"""NewLife 1.0: weekly_reflection_answer table

Revision ID: e3a6f0c2b7d1
Revises: d7f21c5a8e4b
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e3a6f0c2b7d1'
down_revision: Union[str, Sequence[str], None] = 'd7f21c5a8e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'weekly_reflection_answer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('question_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('option_index', sa.Integer(), nullable=False),
        sa.Column('option_text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('answered_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('weekly_reflection_answer', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_weekly_reflection_answer_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_weekly_reflection_answer_question_id'), ['question_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_weekly_reflection_answer_week_start'), ['week_start'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('weekly_reflection_answer', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_weekly_reflection_answer_week_start'))
        batch_op.drop_index(batch_op.f('ix_weekly_reflection_answer_question_id'))
        batch_op.drop_index(batch_op.f('ix_weekly_reflection_answer_uid'))
    op.drop_table('weekly_reflection_answer')
