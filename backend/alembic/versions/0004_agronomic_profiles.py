"""Normalized regional profiles and optional variety compatibility, no scientific timing seeds."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '0004_agronomic_profiles'
down_revision = '0003_manual_irrigation'
branch_labels = None
depends_on = None


def provenance():
    return [sa.Column('verification_status', sa.String(30), nullable=False),
            sa.Column('source_organization', sa.String(150), nullable=False),
            sa.Column('source_url', sa.Text(), nullable=False),
            sa.Column('source_identifier', sa.String(255), nullable=False),
            sa.Column('verified_on', sa.Date()),
            sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true())]


def upgrade():
    op.create_table('agronomic_profiles',
        sa.Column('code', sa.String(150), primary_key=True),
        sa.Column('crop_id', UUID(), sa.ForeignKey('crops.crop_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('country', sa.String(80), nullable=False), sa.Column('state', sa.String(100), nullable=False),
        sa.Column('region', sa.String(150), nullable=False), sa.Column('zone_code', sa.String(20), nullable=False),
        sa.Column('zone_name', sa.String(150), nullable=False), sa.Column('sowing_condition', sa.String(30), nullable=False),
        sa.Column('irrigation_condition', sa.String(40), nullable=False), sa.Column('fertility_condition', sa.String(40)),
        sa.Column('agricultural_timezone', sa.String(80), nullable=False), sa.Column('scope_note', sa.Text(), nullable=False),
        *provenance())
    op.create_table('crop_varieties', sa.Column('code', sa.String(100), primary_key=True),
        sa.Column('crop_id', UUID(), sa.ForeignKey('crops.crop_id', ondelete='RESTRICT'), nullable=False),
        sa.Column('display_name', sa.String(150), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table('variety_profiles',
        sa.Column('profile_code', sa.String(150), sa.ForeignKey('agronomic_profiles.code', ondelete='RESTRICT'), primary_key=True),
        sa.Column('variety_code', sa.String(100), sa.ForeignKey('crop_varieties.code', ondelete='RESTRICT'), primary_key=True),
        sa.Column('release_year', sa.Integer()), sa.Column('sowing_window_start', sa.String(5)),
        sa.Column('sowing_window_end', sa.String(5)), sa.Column('first_irrigation_about_das', sa.Integer()),
        sa.Column('irrigation_note', sa.Text()), *provenance())
    for table in ('crop_cycles', 'crop_stage_parameters'):
        op.add_column(table, sa.Column('agronomic_profile_code', sa.String(150),
            sa.ForeignKey('agronomic_profiles.code', name=f'fk_{table}_agronomic_profile', ondelete='RESTRICT')))
    op.add_column('crop_stage_parameters', sa.Column('variety_code', sa.String(100),
        sa.ForeignKey('crop_varieties.code', name='fk_stage_variety', ondelete='RESTRICT')))
    op.add_column('crop_stage_parameters', sa.Column('verification_status', sa.String(30), nullable=False, server_default='experimental'))
    op.add_column('crop_stage_parameters', sa.Column('verified_on', sa.Date()))


def downgrade():
    for column in ('verified_on', 'verification_status', 'variety_code', 'agronomic_profile_code'):
        op.drop_column('crop_stage_parameters', column)
    op.drop_column('crop_cycles', 'agronomic_profile_code')
    op.drop_table('variety_profiles')
    op.drop_table('crop_varieties')
    op.drop_table('agronomic_profiles')
