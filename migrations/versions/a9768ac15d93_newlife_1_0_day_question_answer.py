"""NewLife 1.0: day_question_answer table (F7 question of the day)

Revision ID: a9768ac15d93
Revises: 949e75cacbf3
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a9768ac15d93'
down_revision: Union[str, Sequence[str], None] = '949e75cacbf3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'day_question_answer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('question_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('sphere_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('option_index', sa.Integer(), nullable=False),
        sa.Column('option_text', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('answered_on', sa.Date(), nullable=False),
        sa.Column('answered_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('day_question_answer', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_day_question_answer_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_day_question_answer_question_id'), ['question_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('day_question_answer', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_day_question_answer_question_id'))
        batch_op.drop_index(batch_op.f('ix_day_question_answer_uid'))
    op.drop_table('day_question_answer')
