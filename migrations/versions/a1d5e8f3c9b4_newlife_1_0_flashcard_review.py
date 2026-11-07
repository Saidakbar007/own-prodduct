"""NewLife 1.0: flashcard_review table (F5 spaced repetition)

Revision ID: a1d5e8f3c9b4
Revises: f4c9d1e6a2b8
Create Date: 2026-11-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a1d5e8f3c9b4'
down_revision: Union[str, Sequence[str], None] = 'f4c9d1e6a2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'flashcard_review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('deck_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('card_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('stage', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('introduced_on', sa.Date(), nullable=False),
        sa.Column('last_reviewed_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('flashcard_review', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_flashcard_review_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_flashcard_review_deck_id'), ['deck_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_flashcard_review_card_id'), ['card_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_flashcard_review_due_date'), ['due_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('flashcard_review', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_flashcard_review_due_date'))
        batch_op.drop_index(batch_op.f('ix_flashcard_review_card_id'))
        batch_op.drop_index(batch_op.f('ix_flashcard_review_deck_id'))
        batch_op.drop_index(batch_op.f('ix_flashcard_review_uid'))
    op.drop_table('flashcard_review')
