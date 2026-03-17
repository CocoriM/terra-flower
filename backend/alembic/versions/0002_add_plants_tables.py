"""add plants, plant_distribution_points, plant_images tables

Revision ID: 0002_add_plants_tables
Revises: 0001_initial_schema
Create Date: 2026-03-17 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0002_add_plants_tables"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- plants ---
    op.create_table(
        "plants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("common_name", sa.String(length=255), nullable=False),
        sa.Column("common_name_zh", sa.String(length=255), nullable=True),
        sa.Column("scientific_name", sa.String(length=255), nullable=False),
        sa.Column("family", sa.String(length=100), nullable=True),
        sa.Column("genus", sa.String(length=100), nullable=True),
        sa.Column("plant_type", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("habitat", sa.Text(), nullable=True),
        sa.Column("bloom_season", sa.String(length=100), nullable=True),
        sa.Column("hero_image_url", sa.Text(), nullable=True),
        sa.Column("hero_image_attribution", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scientific_name"),
    )
    op.create_index("idx_plants_type", "plants", ["plant_type"], unique=False)
    op.create_index("idx_plants_scientific", "plants", ["scientific_name"], unique=False)

    # --- plant_distribution_points ---
    op.create_table(
        "plant_distribution_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("latitude", sa.Double(), nullable=False),
        sa.Column("longitude", sa.Double(), nullable=False),
        sa.Column("elevation_meters", sa.Double(), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("region", sa.String(length=200), nullable=True),
        sa.Column("continent", sa.String(length=50), nullable=True),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'gbif'"),
        ),
        sa.Column("source_record_id", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["plant_id"], ["plants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_distribution_plant", "plant_distribution_points", ["plant_id"], unique=False)
    op.create_index("idx_distribution_location", "plant_distribution_points", ["continent", "country"], unique=False)

    # --- plant_images ---
    op.create_table(
        "plant_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column(
            "image_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'reference'"),
        ),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["plant_id"], ["plants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_plant_images_plant", "plant_images", ["plant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_plant_images_plant", table_name="plant_images")
    op.drop_table("plant_images")

    op.drop_index("idx_distribution_location", table_name="plant_distribution_points")
    op.drop_index("idx_distribution_plant", table_name="plant_distribution_points")
    op.drop_table("plant_distribution_points")

    op.drop_index("idx_plants_scientific", table_name="plants")
    op.drop_index("idx_plants_type", table_name="plants")
    op.drop_table("plants")
