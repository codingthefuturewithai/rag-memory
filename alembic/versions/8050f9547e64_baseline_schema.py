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

    Create initial schema from init.sql.
    """
    # Read and execute init.sql
    import os
    from pathlib import Path

    init_sql_path = Path(__file__).parent.parent.parent / "init.sql"
    with open(init_sql_path, 'r') as f:
        sql_commands = f.read()

    # Execute the SQL
    op.execute(sql_commands)


def downgrade() -> None:
    """Downgrade schema.

    Cannot downgrade from baseline - the schema would need to be dropped manually.
    """
    # Cannot downgrade from baseline
    pass
