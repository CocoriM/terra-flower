"""widen plant name columns from varchar to text

Revision ID: 0004_widen_plant_name_columns
Revises: 0003_update_uploads_and_gallery
Create Date: 2026-03-17 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_widen_plant_name_columns"
down_revision: Union[str, None] = "0003_update_uploads_and_gallery"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("plants", "common_name", type_=sa.Text(), existing_nullable=False)
    op.alter_column("plants", "common_name_zh", type_=sa.Text(), existing_nullable=True)
    op.alter_column("plants", "scientific_name", type_=sa.Text(), existing_nullable=False)
    op.alter_column("plants", "family", type_=sa.Text(), existing_nullable=True)
    op.alter_column("plants", "genus", type_=sa.Text(), existing_nullable=True)
    op.alter_column("plants", "bloom_season", type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    op.alter_column("plants", "bloom_season", type_=sa.String(100), existing_nullable=True)
    op.alter_column("plants", "genus", type_=sa.String(100), existing_nullable=True)
    op.alter_column("plants", "family", type_=sa.String(100), existing_nullable=True)
    op.alter_column("plants", "scientific_name", type_=sa.String(255), existing_nullable=False)
    op.alter_column("plants", "common_name_zh", type_=sa.String(255), existing_nullable=True)
    op.alter_column("plants", "common_name", type_=sa.String(255), existing_nullable=False)
