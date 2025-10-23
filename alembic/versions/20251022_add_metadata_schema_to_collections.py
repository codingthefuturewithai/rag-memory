"""add_metadata_schema_to_collections

Revision ID: 20251022000001
Revises: 8050f9547e64
Create Date: 2025-10-22 00:00:00.000000

Add metadata_schema JSONB column to collections table to support
collection-level metadata schema declaration. Make description mandatory.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251022000001'
down_revision: Union[str, Sequence[str], None] = '8050f9547e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to add metadata_schema support."""
    # Add metadata_schema JSONB column with default value
    op.add_column(
        'collections',
        sa.Column(
            'metadata_schema',
            sa.JSON(),
            nullable=False,
            server_default='{"custom": {}, "system": []}'
        )
    )

    # Make description NOT NULL (set default for existing rows)
    op.alter_column(
        'collections',
        'description',
        existing_type=sa.TEXT(),
        nullable=False,
        server_default='Collection'
    )


def downgrade() -> None:
    """Downgrade schema by removing metadata_schema column."""
    # Remove metadata_schema column
    op.drop_column('collections', 'metadata_schema')

    # Revert description to nullable
    op.alter_column(
        'collections',
        'description',
        existing_type=sa.TEXT(),
        nullable=True,
        server_default=None
    )
