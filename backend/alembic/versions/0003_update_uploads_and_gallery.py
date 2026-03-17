"""update user_uploads and approved_gallery_items for v2

Revision ID: 0003_update_uploads_and_gallery
Revises: 0002_add_plants_tables
Create Date: 2026-03-17 10:01:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003_update_uploads_and_gallery"
down_revision: Union[str, None] = "0002_add_plants_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- user_uploads changes ---

    # Remove trefle_plant_id (drop index first)
    op.drop_index("idx_uploads_plant", table_name="user_uploads")
    op.drop_column("user_uploads", "trefle_plant_id")

    # Remove v1 forward-identification columns that are no longer needed
    op.drop_column("user_uploads", "plant_scientific_name")
    op.drop_column("user_uploads", "plant_common_name")
    op.drop_column("user_uploads", "plant_type")

    # Rename ai_predicted_name → ai_best_match_name
    op.alter_column("user_uploads", "ai_predicted_name", new_column_name="ai_best_match_name")

    # Rename ai_confidence → ai_best_match_score
    op.alter_column("user_uploads", "ai_confidence", new_column_name="ai_best_match_score")

    # Add new columns
    op.add_column(
        "user_uploads",
        sa.Column("confirmed_plant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "user_uploads",
        sa.Column(
            "user_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "user_uploads",
        sa.Column("ai_project_used", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "user_uploads",
        sa.Column("elevation_meters", sa.Double(), nullable=True),
    )

    # Add FK for confirmed_plant_id → plants.id
    op.create_foreign_key(
        "fk_uploads_confirmed_plant",
        "user_uploads",
        "plants",
        ["confirmed_plant_id"],
        ["id"],
    )

    # Re-create index on confirmed_plant_id
    op.create_index("idx_uploads_plant", "user_uploads", ["confirmed_plant_id"], unique=False)

    # --- approved_gallery_items changes ---

    # Remove trefle_plant_id, add plant_id (UUID FK to plants)
    op.drop_index("idx_gallery_plant", table_name="approved_gallery_items")
    op.drop_column("approved_gallery_items", "trefle_plant_id")

    op.add_column(
        "approved_gallery_items",
        sa.Column("plant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "approved_gallery_items",
        sa.Column("elevation_meters", sa.Double(), nullable=True),
    )
    op.create_foreign_key(
        "fk_gallery_plant",
        "approved_gallery_items",
        "plants",
        ["plant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_gallery_plant", "approved_gallery_items", ["plant_id"], unique=False)


def downgrade() -> None:
    # --- revert approved_gallery_items ---
    op.drop_index("idx_gallery_plant", table_name="approved_gallery_items")
    op.drop_constraint("fk_gallery_plant", "approved_gallery_items", type_="foreignkey")
    op.drop_column("approved_gallery_items", "elevation_meters")
    op.drop_column("approved_gallery_items", "plant_id")
    op.add_column(
        "approved_gallery_items",
        sa.Column("trefle_plant_id", sa.Integer(), nullable=False),
    )
    op.create_index("idx_gallery_plant", "approved_gallery_items", ["trefle_plant_id"], unique=False)

    # --- revert user_uploads ---
    op.drop_index("idx_uploads_plant", table_name="user_uploads")
    op.drop_constraint("fk_uploads_confirmed_plant", "user_uploads", type_="foreignkey")
    op.drop_column("user_uploads", "elevation_meters")
    op.drop_column("user_uploads", "ai_project_used")
    op.drop_column("user_uploads", "user_confirmed")
    op.drop_column("user_uploads", "confirmed_plant_id")

    op.alter_column("user_uploads", "ai_best_match_score", new_column_name="ai_confidence")
    op.alter_column("user_uploads", "ai_best_match_name", new_column_name="ai_predicted_name")

    op.add_column(
        "user_uploads",
        sa.Column("plant_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "user_uploads",
        sa.Column("plant_common_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "user_uploads",
        sa.Column("plant_scientific_name", sa.String(length=255), nullable=False),
    )
    op.add_column(
        "user_uploads",
        sa.Column("trefle_plant_id", sa.Integer(), nullable=False),
    )
    op.create_index("idx_uploads_plant", "user_uploads", ["trefle_plant_id"], unique=False)
