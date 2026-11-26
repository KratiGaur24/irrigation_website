"""Retain requested coordinates with each forecast; unknown legacy provenance stays null."""
from alembic import op
import sqlalchemy as sa

revision = '0005_weather_location'
down_revision = '0004_agronomic_profiles'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('weather_records', sa.Column('request_latitude', sa.Numeric(9, 6), nullable=True))
    op.add_column('weather_records', sa.Column('request_longitude', sa.Numeric(9, 6), nullable=True))
    op.create_check_constraint('ck_weather_request_latitude', 'weather_records', 'request_latitude IS NULL OR request_latitude BETWEEN -90 AND 90')
    op.create_check_constraint('ck_weather_request_longitude', 'weather_records', 'request_longitude IS NULL OR request_longitude BETWEEN -180 AND 180')


def downgrade():
    op.drop_constraint('ck_weather_request_longitude', 'weather_records', type_='check')
    op.drop_constraint('ck_weather_request_latitude', 'weather_records', type_='check')
    op.drop_column('weather_records', 'request_longitude')
    op.drop_column('weather_records', 'request_latitude')
