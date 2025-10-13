"""require_collection_description

Revision ID: 555255565f74
Revises: 8050f9547e64
Create Date: 2025-10-13 10:57:11.694631

Enforce NOT NULL constraint on collections.description to ensure all collections
have meaningful descriptions for better organization.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '555255565f74'
down_revision: Union[str, Sequence[str], None] = '8050f9547e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Step 1: Update any existing collections with NULL or empty descriptions
    Step 2: Add NOT NULL constraint to collections.description
    Step 3: Add CHECK constraint to prevent empty strings
    """
    # Step 1: Update existing NULL/empty descriptions
    op.execute("""
        UPDATE collections
        SET description = 'No description provided'
        WHERE description IS NULL OR description = ''
    """)

    # Step 2: Add NOT NULL constraint
    op.alter_column('collections', 'description',
                   existing_type=sa.TEXT(),
                   nullable=False)

    # Step 3: Add check constraint to prevent empty strings
    op.create_check_constraint(
        'description_not_empty',
        'collections',
        "length(trim(description)) > 0"
    )


def downgrade() -> None:
    """Downgrade schema.

    Remove constraints in reverse order.
    """
    # Remove check constraint
    op.drop_constraint('description_not_empty', 'collections', type_='check')

    # Make description nullable again
    op.alter_column('collections', 'description',
                   existing_type=sa.TEXT(),
                   nullable=True)
