# Database Migration Guide

This guide describes the complete, step-by-step process for managing database schema changes in the RAG Memory project using Alembic migrations.

**Target Audience:** Developers who need to modify the database schema and apply those changes to production databases.

**Assumption:** You have made changes to the database schema and need to create and apply a migration.

---

## Prerequisites

Before following this guide, ensure:

1. **Alembic is installed:** Already included in `pyproject.toml` as `alembic>=1.17.0`
2. **Database is running:** Docker container on port 54320
3. **Environment configured:** `.env` file has correct `DATABASE_URL`
4. **Python environment activated:** Use `uv sync` to ensure all dependencies are installed

---

## Step 1: Identify Your Schema Change

**What are you changing?**

Common scenarios:
- Adding a new column to an existing table
- Adding a NOT NULL constraint
- Adding a CHECK constraint
- Creating a new table
- Adding or dropping an index
- Modifying column types

**Example:** We need to make the `collections.description` column NOT NULL and prevent empty strings.

**Write down your change clearly before proceeding.**

---

## Step 2: Check Current Database State

Before creating a migration, verify the current state of the database.

### 2.1: Connect to Database

```bash
PGPASSWORD=ragpassword psql -h localhost -p 54320 -U raguser -d rag_memory
```

### 2.2: Inspect Relevant Tables

```sql
-- View table structure
\d collections

-- View existing constraints
\d+ collections

-- Check current data
SELECT name, description FROM collections;
```

### 2.3: Check Current Migration Version

```sql
-- See which migration is currently applied
SELECT version_num FROM alembic_version;
```

**Exit psql:** Type `\q` or press `Ctrl+D`

**Document what you found:**
- Current column definitions
- Current constraints
- Current data that might be affected
- Current migration version

---

## Step 3: Create a New Migration File

Alembic will generate a migration file template for you.

### 3.1: Generate Migration File

```bash
uv run alembic revision -m "descriptive_migration_name"
```

**Example:**
```bash
uv run alembic revision -m "require_collection_description"
```

**What this does:**
- Creates a new file in `alembic/versions/` with format: `{revision_id}_{migration_name}.py`
- The revision ID is a random alphanumeric string (e.g., `555255565f74`)
- Links to the previous migration automatically (sets `down_revision`)

### 3.2: Locate Your Migration File

```bash
ls -lt alembic/versions/
```

You'll see something like:
```
555255565f74_require_collection_description.py
```

---

## Step 4: Edit the Migration File

Open the generated migration file and implement your schema changes.

### 4.1: Migration File Structure

Every migration file has this structure:

```python
"""descriptive_migration_name

Revision ID: 555255565f74
Revises: 8050f9547e64
Create Date: 2025-10-13 10:57:11.694631

Add a detailed description here explaining:
- What this migration does
- Why it's needed
- Any data transformations performed
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

    This function is called when running: uv run rag migrate
    """
    # TODO: Add your schema changes here
    pass


def downgrade() -> None:
    """Downgrade schema.

    This function is called when running: uv run alembic downgrade
    """
    # TODO: Add reverse operations here
    pass
```

### 4.2: Implement the `upgrade()` Function

**IMPORTANT:** The `upgrade()` function must:
1. Handle existing data FIRST (if adding NOT NULL constraints)
2. Apply schema changes
3. Be idempotent (safe to run multiple times)

**Example: Adding NOT NULL constraint**

```python
def upgrade() -> None:
    """Upgrade schema.

    Step 1: Update any existing collections with NULL or empty descriptions
    Step 2: Add NOT NULL constraint to collections.description
    Step 3: Add CHECK constraint to prevent empty strings
    """
    # Step 1: Update existing NULL/empty descriptions
    # CRITICAL: Do this BEFORE adding NOT NULL constraint
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
```

**Common Alembic Operations:**

```python
# Add a column
op.add_column('table_name', sa.Column('new_column', sa.String(255), nullable=True))

# Drop a column
op.drop_column('table_name', 'column_name')

# Modify a column (make NOT NULL)
op.alter_column('table_name', 'column_name',
               existing_type=sa.TEXT(),
               nullable=False)

# Create a new table
op.create_table(
    'new_table',
    sa.Column('id', sa.Integer(), primary_key=True),
    sa.Column('name', sa.String(255), nullable=False),
)

# Add an index
op.create_index('idx_table_column', 'table_name', ['column_name'])

# Add a check constraint
op.create_check_constraint('constraint_name', 'table_name', 'column_name > 0')

# Execute raw SQL (use for data migrations)
op.execute("UPDATE table_name SET column = value WHERE condition")
```

### 4.3: Implement the `downgrade()` Function

**IMPORTANT:** The `downgrade()` function must reverse ALL operations in reverse order.

**Example: Reversing NOT NULL constraint**

```python
def downgrade() -> None:
    """Downgrade schema.

    Remove constraints in reverse order.
    """
    # Remove check constraint (added last, removed first)
    op.drop_constraint('description_not_empty', 'collections', type_='check')

    # Make description nullable again (added second, removed second)
    op.alter_column('collections', 'description',
                   existing_type=sa.TEXT(),
                   nullable=True)

    # Note: We do NOT reverse the UPDATE statement
    # Collections with "No description provided" will keep that value
```

**Common Downgrade Operations:**

```python
# Reverse: Add column → Drop column
op.drop_column('table_name', 'new_column')

# Reverse: Drop column → Add column
op.add_column('table_name', sa.Column('column_name', sa.String(255)))

# Reverse: Make NOT NULL → Make nullable
op.alter_column('table_name', 'column_name',
               existing_type=sa.TEXT(),
               nullable=True)

# Reverse: Create table → Drop table
op.drop_table('new_table')

# Reverse: Add index → Drop index
op.drop_index('idx_table_column', 'table_name')

# Reverse: Add constraint → Drop constraint
op.drop_constraint('constraint_name', 'table_name', type_='check')
```

---

## Step 5: Test the Migration Locally

**CRITICAL:** Always test migrations on a local database before production.

### 5.1: Backup Your Local Database (Optional but Recommended)

```bash
docker exec -it rag-postgres pg_dump -U raguser rag_memory > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 5.2: Check Migration Status

```bash
uv run alembic current
```

**Expected output:**
```
555255565f74 (head)
```

If your new migration is not shown:

```bash
uv run alembic history
```

This shows all available migrations.

### 5.3: Run the Migration

**Using the CLI (Recommended):**
```bash
uv run rag migrate
```

**Using Alembic directly:**
```bash
uv run alembic upgrade head
```

**Using Alembic with SQL preview (doesn't apply changes):**
```bash
uv run alembic upgrade head --sql
```

### 5.4: Verify the Migration Applied

```bash
PGPASSWORD=ragpassword psql -h localhost -p 54320 -U raguser -d rag_memory
```

```sql
-- Check migration version
SELECT version_num FROM alembic_version;
-- Should show your new revision ID

-- Check table structure
\d collections

-- Verify constraints exist
\d+ collections

-- Test that constraints work (should fail)
INSERT INTO collections (name, description) VALUES ('test', NULL);
-- Expected: ERROR:  null value in column "description" violates not-null constraint

INSERT INTO collections (name, description) VALUES ('test', '   ');
-- Expected: ERROR:  new row for relation "collections" violates check constraint "description_not_empty"

-- Check existing data was updated correctly
SELECT name, description FROM collections;
```

**If the migration failed:**
1. Check the error message
2. Fix the migration file
3. Rollback: `uv run alembic downgrade -1`
4. Re-run: `uv run rag migrate`

---

## Step 6: Test the Downgrade (Optional but Recommended)

Ensure your downgrade function works correctly.

### 6.1: Downgrade One Migration

```bash
uv run alembic downgrade -1
```

### 6.2: Verify Downgrade

```bash
PGPASSWORD=ragpassword psql -h localhost -p 54320 -U raguser -d rag_memory
```

```sql
-- Check migration version (should be previous revision)
SELECT version_num FROM alembic_version;

-- Check constraints were removed
\d+ collections

-- Test that NULL values are now allowed
INSERT INTO collections (name, description) VALUES ('test', NULL);
-- Should succeed

-- Clean up test data
DELETE FROM collections WHERE name = 'test';
```

### 6.3: Re-apply the Migration

```bash
uv run rag migrate
```

---

## Step 7: Commit Your Migration

Once you've verified the migration works correctly, commit it to version control.

### 7.1: Stage the Migration Files

```bash
git add alembic/versions/{revision_id}_{migration_name}.py
```

**Example:**
```bash
git add alembic/versions/555255565f74_require_collection_description.py
```

### 7.2: Commit with Descriptive Message

```bash
git commit -m "Add migration: require_collection_description

- Add NOT NULL constraint to collections.description
- Add CHECK constraint to prevent empty descriptions
- Update existing NULL descriptions to default value"
```

### 7.3: Push to Remote

```bash
git push origin main
```

---

## Step 8: Apply Migration to Production

**IMPORTANT:** Always coordinate with your team before applying production migrations.

### 8.1: Pre-Migration Checklist

- [ ] Migration tested locally
- [ ] Downgrade tested locally
- [ ] Migration committed to version control
- [ ] Team notified of upcoming schema change
- [ ] Production database backed up
- [ ] Downtime scheduled (if necessary)

### 8.2: Backup Production Database

```bash
# Connect to production environment
ssh production-server

# Create backup
pg_dump -U raguser -h localhost -p 54320 rag_memory > prod_backup_$(date +%Y%m%d_%H%M%S).sql
```

### 8.3: Check Current Migration State

```bash
uv run alembic current
```

### 8.4: Apply Migration

```bash
uv run rag migrate
```

### 8.5: Verify Production Migration

```bash
PGPASSWORD=$PRODUCTION_PASSWORD psql -h production-host -p 54320 -U raguser -d rag_memory
```

```sql
-- Verify migration version
SELECT version_num FROM alembic_version;

-- Verify schema changes
\d+ collections

-- Verify data integrity
SELECT COUNT(*) FROM collections WHERE description IS NULL;
-- Should return 0
```

---

## Common Scenarios

### Scenario 1: Adding a New Column

**Step 4.2 - Implement upgrade():**
```python
def upgrade() -> None:
    """Add new_column to table_name."""
    op.add_column('table_name',
        sa.Column('new_column', sa.String(255), nullable=True)
    )
```

**Step 4.3 - Implement downgrade():**
```python
def downgrade() -> None:
    """Remove new_column from table_name."""
    op.drop_column('table_name', 'new_column')
```

### Scenario 2: Adding NOT NULL Constraint to Existing Column

**Step 4.2 - Implement upgrade():**
```python
def upgrade() -> None:
    """Make column NOT NULL."""
    # Step 1: Update NULL values FIRST
    op.execute("""
        UPDATE table_name
        SET column_name = 'default_value'
        WHERE column_name IS NULL
    """)

    # Step 2: Add constraint
    op.alter_column('table_name', 'column_name',
                   existing_type=sa.TEXT(),
                   nullable=False)
```

**Step 4.3 - Implement downgrade():**
```python
def downgrade() -> None:
    """Remove NOT NULL constraint."""
    op.alter_column('table_name', 'column_name',
                   existing_type=sa.TEXT(),
                   nullable=True)
```

### Scenario 3: Creating a New Table

**Step 4.2 - Implement upgrade():**
```python
def upgrade() -> None:
    """Create new_table."""
    op.create_table(
        'new_table',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # Add index for performance
    op.create_index('idx_new_table_name', 'new_table', ['name'])
```

**Step 4.3 - Implement downgrade():**
```python
def downgrade() -> None:
    """Drop new_table."""
    # Drop index first
    op.drop_index('idx_new_table_name', 'new_table')

    # Drop table
    op.drop_table('new_table')
```

### Scenario 4: Data Migration (Transforming Existing Data)

**Step 4.2 - Implement upgrade():**
```python
def upgrade() -> None:
    """Transform data from old format to new format."""
    # Add new column
    op.add_column('table_name',
        sa.Column('new_column', sa.String(255), nullable=True)
    )

    # Transform data
    op.execute("""
        UPDATE table_name
        SET new_column = CONCAT('prefix_', old_column)
        WHERE old_column IS NOT NULL
    """)

    # Make new column NOT NULL
    op.alter_column('table_name', 'new_column',
                   existing_type=sa.String(),
                   nullable=False)

    # Drop old column (if no longer needed)
    # op.drop_column('table_name', 'old_column')
```

**Step 4.3 - Implement downgrade():**
```python
def downgrade() -> None:
    """Reverse data transformation."""
    # Re-add old column if dropped
    # op.add_column('table_name',
    #     sa.Column('old_column', sa.String(255))
    # )

    # Reverse transformation
    # op.execute("""
    #     UPDATE table_name
    #     SET old_column = SUBSTRING(new_column FROM 8)
    #     WHERE new_column LIKE 'prefix_%'
    # """)

    # Drop new column
    op.drop_column('table_name', 'new_column')
```

---

## Troubleshooting

### Problem: Migration fails with "column already exists"

**Cause:** Migration was partially applied or run multiple times.

**Solution:**
```bash
# Check current state
PGPASSWORD=ragpassword psql -h localhost -p 54320 -U raguser -d rag_memory -c "\d table_name"

# If column exists but migration version is wrong:
uv run alembic stamp head
```

### Problem: Migration fails with "cannot drop column because other objects depend on it"

**Cause:** Foreign key constraints or indexes reference the column.

**Solution:** Drop dependent objects first:
```python
def upgrade() -> None:
    # Drop dependent index first
    op.drop_index('idx_name', 'table_name')

    # Drop dependent foreign key constraint
    op.drop_constraint('fk_name', 'table_name', type_='foreignkey')

    # Now drop the column
    op.drop_column('table_name', 'column_name')
```

### Problem: Migration fails with "relation does not exist"

**Cause:** Trying to modify a table that doesn't exist yet.

**Solution:** Check migration order:
```bash
uv run alembic history
```

Ensure migrations are applied in correct order. The `down_revision` in your migration file must point to an already-applied migration.

### Problem: Need to rollback multiple migrations

**Solution:**
```bash
# Rollback to specific revision
uv run alembic downgrade {revision_id}

# Rollback all migrations
uv run alembic downgrade base
```

### Problem: Migration runs forever (hanging)

**Cause:** Migration requires a table lock that's currently held.

**Solution:**
```bash
# Check for locks
PGPASSWORD=ragpassword psql -h localhost -p 54320 -U raguser -d rag_memory -c "
  SELECT pid, state, query
  FROM pg_stat_activity
  WHERE datname = 'rag_memory'
"

# Kill blocking queries
# SELECT pg_terminate_backend(pid) WHERE pid = 12345;
```

---

## Best Practices

### 1. **Always handle existing data**

If adding a NOT NULL constraint, update existing NULL values first.

### 2. **Write reversible migrations**

Always implement both `upgrade()` and `downgrade()` functions.

### 3. **Test locally first**

Never apply untested migrations to production.

### 4. **Use descriptive migration names**

Good: `add_user_email_verification_column`
Bad: `update_users`

### 5. **Keep migrations small and focused**

One migration = one logical change. Don't bundle unrelated changes.

### 6. **Document data transformations**

If your migration transforms data, document the transformation logic clearly.

### 7. **Backup before migrating**

Always have a backup before applying production migrations.

### 8. **Coordinate with your team**

Communicate schema changes that might affect other developers or services.

### 9. **Use raw SQL for complex data migrations**

For complex data transformations, use `op.execute()` with raw SQL rather than SQLAlchemy ORM.

### 10. **Check constraint violations before adding constraints**

Before adding a NOT NULL or CHECK constraint, verify existing data satisfies the constraint.

---

## Quick Reference

### Common Commands

```bash
# Check current migration version
uv run alembic current

# Show migration history
uv run alembic history

# Create new migration
uv run alembic revision -m "migration_name"

# Apply all pending migrations
uv run rag migrate
# OR
uv run alembic upgrade head

# Preview SQL without applying
uv run alembic upgrade head --sql

# Rollback one migration
uv run alembic downgrade -1

# Rollback to specific revision
uv run alembic downgrade {revision_id}

# Rollback all migrations
uv run alembic downgrade base

# Stamp database without running migrations (use with caution)
uv run alembic stamp head
```

### Database Inspection

```bash
# Connect to database
PGPASSWORD=ragpassword psql -h localhost -p 54320 -U raguser -d rag_memory

# Inside psql:
\d                          # List all tables
\d table_name              # Show table structure
\d+ table_name             # Show table structure with constraints
\q                         # Exit psql
```

---

## Summary

**Complete workflow from schema change to production:**

1. **Identify change:** Know exactly what you're modifying
2. **Check database:** Inspect current state and data
3. **Create migration:** `uv run alembic revision -m "name"`
4. **Edit migration:** Implement `upgrade()` and `downgrade()`
5. **Test locally:** Run migration, verify results, test downgrade
6. **Commit code:** `git add` → `git commit` → `git push`
7. **Backup production:** Create database backup
8. **Apply to production:** `uv run rag migrate`
9. **Verify production:** Check schema and data

**Remember:** Migrations are code. Treat them with the same care and testing as any other code change.
