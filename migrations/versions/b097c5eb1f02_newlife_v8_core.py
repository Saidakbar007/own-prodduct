"""NewLife v8 core: profile, sphere, commitment, task, goal, habit, bad_habit,
checkin, schedule_block, method_event (§4 NEWLIFE_V8_SPEC.md)

Revision ID: b097c5eb1f02
Revises: d36a5dbd5c91
Create Date: 2026-10-31 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b097c5eb1f02'
down_revision: Union[str, Sequence[str], None] = 'd36a5dbd5c91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('height_cm', sa.Integer(), nullable=True),
        sa.Column('weight_kg', sa.Float(), nullable=True),
        sa.Column('wake_time', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('sleep_time', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('chronotype', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('daily_minutes', sa.Integer(), nullable=True),
        sa.Column('constraints_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('main_obstacle', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('onboarding_done_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=True),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_profile_uid'), ['uid'], unique=True)

    op.create_table(
        'sphere_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('sphere_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('sphere_state', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sphere_state_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_sphere_state_sphere_id'), ['sphere_id'], unique=False)

    op.create_table(
        'sphere_level_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('sphere_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.Column('recorded_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('sphere_level_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sphere_level_history_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_sphere_level_history_sphere_id'), ['sphere_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_sphere_level_history_recorded_at'), ['recorded_at'], unique=False)

    op.create_table(
        'commitment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('weekdays_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('start_time', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('end_time', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('commitment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_commitment_uid'), ['uid'], unique=False)

    op.create_table(
        'task',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('task_date', sa.Date(), nullable=False),
        sa.Column('start_time', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=False),
        sa.Column('priority', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_task_date'), ['task_date'], unique=False)

    op.create_table(
        'goal',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('sphere_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('template_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('metric_key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('baseline', sa.Float(), nullable=False),
        sa.Column('target', sa.Float(), nullable=False),
        sa.Column('safe_rate', sa.Float(), nullable=True),
        sa.Column('projected_date', sa.Date(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_goal_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_goal_sphere_id'), ['sphere_id'], unique=False)

    op.create_table(
        'habit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('catalog_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('spheres_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('days_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('time_pref', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('exact_time', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=False),
        sa.Column('minimal_version', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('anchor_text', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('if_then_text', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('habit', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_habit_uid'), ['uid'], unique=False)

    op.create_table(
        'habit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('habit_id', sa.Integer(), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['habit_id'], ['habit.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('habit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_habit_log_habit_id'), ['habit_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_habit_log_log_date'), ['log_date'], unique=False)

    op.create_table(
        'bad_habit',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('catalog_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('triggers_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('replacement_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('baseline_per_day', sa.Float(), nullable=False),
        sa.Column('target_per_day', sa.Float(), nullable=False),
        sa.Column('unit', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('bad_habit', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bad_habit_uid'), ['uid'], unique=False)

    op.create_table(
        'bad_habit_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bad_habit_id', sa.Integer(), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('trigger_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['bad_habit_id'], ['bad_habit.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('bad_habit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_bad_habit_log_bad_habit_id'), ['bad_habit_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_bad_habit_log_log_date'), ['log_date'], unique=False)

    op.create_table(
        'checkin',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('checkin_date', sa.Date(), nullable=False),
        sa.Column('energy', sa.Integer(), nullable=False),
        sa.Column('stress', sa.Integer(), nullable=False),
        sa.Column('mood', sa.Integer(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('checkin', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_checkin_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_checkin_checkin_date'), ['checkin_date'], unique=False)

    op.create_table(
        'schedule_block',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('block_date', sa.Date(), nullable=False),
        sa.Column('start_time', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('end_time', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('ref_type', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('ref_id', sa.Integer(), nullable=True),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('moved_by_user', sa.Boolean(), nullable=False),
        sa.Column('created_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('schedule_block', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_schedule_block_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_schedule_block_block_date'), ['block_date'], unique=False)

    op.create_table(
        'method_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Integer(), nullable=False),
        sa.Column('method_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('trigger', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('shown_at', sqlmodel.sql.sqltypes.UTCDateTime(), nullable=False),
        sa.Column('accepted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['uid'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('method_event', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_method_event_uid'), ['uid'], unique=False)
        batch_op.create_index(batch_op.f('ix_method_event_method_id'), ['method_id'], unique=False)

    with op.batch_alter_table('season', schema=None) as batch_op:
        batch_op.add_column(sa.Column('goal_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_season_goal_id'), ['goal_id'], unique=False)
        batch_op.create_foreign_key('fk_season_goal_id', 'goal', ['goal_id'], ['id'])

    with op.batch_alter_table('measurement', schema=None) as batch_op:
        batch_op.add_column(sa.Column('metric_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('extra_metrics_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('measurement', schema=None) as batch_op:
        batch_op.drop_column('extra_metrics_json')
        batch_op.drop_column('metric_key')

    with op.batch_alter_table('season', schema=None) as batch_op:
        batch_op.drop_constraint('fk_season_goal_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_season_goal_id'))
        batch_op.drop_column('goal_id')

    with op.batch_alter_table('method_event', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_method_event_method_id'))
        batch_op.drop_index(batch_op.f('ix_method_event_uid'))
    op.drop_table('method_event')

    with op.batch_alter_table('schedule_block', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_schedule_block_block_date'))
        batch_op.drop_index(batch_op.f('ix_schedule_block_uid'))
    op.drop_table('schedule_block')

    with op.batch_alter_table('checkin', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_checkin_checkin_date'))
        batch_op.drop_index(batch_op.f('ix_checkin_uid'))
    op.drop_table('checkin')

    with op.batch_alter_table('bad_habit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bad_habit_log_log_date'))
        batch_op.drop_index(batch_op.f('ix_bad_habit_log_bad_habit_id'))
    op.drop_table('bad_habit_log')

    with op.batch_alter_table('bad_habit', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bad_habit_uid'))
    op.drop_table('bad_habit')

    with op.batch_alter_table('habit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_habit_log_log_date'))
        batch_op.drop_index(batch_op.f('ix_habit_log_habit_id'))
    op.drop_table('habit_log')

    with op.batch_alter_table('habit', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_habit_uid'))
    op.drop_table('habit')

    with op.batch_alter_table('goal', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_goal_sphere_id'))
        batch_op.drop_index(batch_op.f('ix_goal_uid'))
    op.drop_table('goal')

    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_task_date'))
        batch_op.drop_index(batch_op.f('ix_task_uid'))
    op.drop_table('task')

    with op.batch_alter_table('commitment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_commitment_uid'))
    op.drop_table('commitment')

    with op.batch_alter_table('sphere_level_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sphere_level_history_recorded_at'))
        batch_op.drop_index(batch_op.f('ix_sphere_level_history_sphere_id'))
        batch_op.drop_index(batch_op.f('ix_sphere_level_history_uid'))
    op.drop_table('sphere_level_history')

    with op.batch_alter_table('sphere_state', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sphere_state_sphere_id'))
        batch_op.drop_index(batch_op.f('ix_sphere_state_uid'))
    op.drop_table('sphere_state')

    with op.batch_alter_table('profile', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_profile_uid'))
    op.drop_table('profile')
