"""baseline_schema

Revision ID: 8050f9547e64
Revises:
Create Date: 2025-10-13 10:55:18.221853

This migration represents the initial schema from init.sql.
The database schema already exists, so this migration does nothing.
It serves as a baseline marker for future migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8050f9547e64'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    This is a baseline migration - the schema already exists from init.sql.
    No changes are made to the database.
    """
    # Schema already exists from init.sql
    # This migration serves only as a baseline marker
    pass


def downgrade() -> None:
    """Downgrade schema.

    Cannot downgrade from baseline - the schema would need to be dropped manually.
    """
    # Cannot downgrade from baseline
    pass
