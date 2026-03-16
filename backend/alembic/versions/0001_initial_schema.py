"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-03-16 19:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column(
            "auth_provider",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'email'"),
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'contributor'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "user_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trefle_plant_id", sa.Integer(), nullable=False),
        sa.Column("plant_scientific_name", sa.String(length=255), nullable=False),
        sa.Column("plant_common_name", sa.String(length=255), nullable=True),
        sa.Column("plant_type", sa.String(length=20), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("image_hash", sa.String(length=64), nullable=True),
        sa.Column("latitude", sa.Double(), nullable=True),
        sa.Column("longitude", sa.Double(), nullable=True),
        sa.Column("location_text", sa.String(length=500), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("continent", sa.String(length=50), nullable=True),
        sa.Column("ai_predicted_name", sa.String(length=255), nullable=True),
        sa.Column("ai_confidence", sa.Double(), nullable=True),
        sa.Column("ai_top_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "ai_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "moderation_status",
            sa.String(length=30),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("moderation_reason", sa.Text(), nullable=True),
        sa.Column("moderator_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["moderator_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_uploads_plant", "user_uploads", ["trefle_plant_id"], unique=False)
    op.create_index("idx_uploads_status", "user_uploads", ["moderation_status"], unique=False)
    op.create_index("idx_uploads_user", "user_uploads", ["user_id"], unique=False)

    op.create_table(
        "approved_gallery_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trefle_plant_id", sa.Integer(), nullable=False),
        sa.Column("latitude", sa.Double(), nullable=True),
        sa.Column("longitude", sa.Double(), nullable=True),
        sa.Column(
            "approved_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["upload_id"], ["user_uploads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_gallery_plant",
        "approved_gallery_items",
        ["trefle_plant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_gallery_plant", table_name="approved_gallery_items")
    op.drop_table("approved_gallery_items")

    op.drop_index("idx_uploads_user", table_name="user_uploads")
    op.drop_index("idx_uploads_status", table_name="user_uploads")
    op.drop_index("idx_uploads_plant", table_name="user_uploads")
    op.drop_table("user_uploads")

    op.drop_table("users")
