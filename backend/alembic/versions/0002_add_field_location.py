"""Add field-level location metadata without changing farm coordinates."""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_field_location"
down_revision = "0001_database_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("fields", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("fields", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    op.add_column("fields", sa.Column("location_source", sa.String(30), nullable=True))
    op.add_column("fields", sa.Column("location_accuracy_m", sa.Numeric(10, 2), nullable=True))
    op.create_check_constraint("ck_fields_latitude", "fields", "latitude IS NULL OR latitude BETWEEN -90 AND 90")
    op.create_check_constraint("ck_fields_longitude", "fields", "longitude IS NULL OR longitude BETWEEN -180 AND 180")
    op.create_check_constraint("ck_fields_location_accuracy_m", "fields", "location_accuracy_m IS NULL OR location_accuracy_m >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_fields_location_accuracy_m", "fields", type_="check")
    op.drop_constraint("ck_fields_longitude", "fields", type_="check")
    op.drop_constraint("ck_fields_latitude", "fields", type_="check")
    op.drop_column("fields", "location_accuracy_m")
    op.drop_column("fields", "location_source")
    op.drop_column("fields", "longitude")
    op.drop_column("fields", "latitude")
