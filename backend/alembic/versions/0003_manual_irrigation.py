"""Persist command provenance and a measured baseline; prevent concurrent open sessions.

Legacy rows retain null provenance. Duplicate open events require explicit review;
this migration intentionally does not rewrite or delete historical records.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_manual_irrigation'
down_revision = '0002_add_field_location'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('irrigation_events', sa.Column('control_mode', sa.String(20), nullable=True))
    op.add_column('irrigation_events', sa.Column('start_reading_id', sa.BigInteger(), nullable=True))
    op.add_column('irrigation_events', sa.Column('command_acknowledged', sa.Boolean(), nullable=True))
    op.create_foreign_key('fk_event_start_reading', 'irrigation_events', 'sensor_readings', ['start_reading_id'], ['reading_id'], ondelete='RESTRICT')
    op.create_check_constraint('ck_event_control_mode', 'irrigation_events', "control_mode IS NULL OR control_mode IN ('simulated','hardware')")
    op.create_index('uq_irrigation_open_field', 'irrigation_events', ['field_id'], unique=True, postgresql_where=sa.text('ended_at IS NULL'))


def downgrade():
    op.drop_index('uq_irrigation_open_field', table_name='irrigation_events')
    op.drop_constraint('ck_event_control_mode', 'irrigation_events', type_='check')
    op.drop_constraint('fk_event_start_reading', 'irrigation_events', type_='foreignkey')
    op.drop_column('irrigation_events', 'command_acknowledged')
    op.drop_column('irrigation_events', 'start_reading_id')
    op.drop_column('irrigation_events', 'control_mode')
