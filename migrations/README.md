# Migrations Directory - DEPRECATED

⚠️ **This directory is no longer used for active migrations.**

## Current Migration System

As of October 13, 2025, this project uses **Alembic** for database migrations.

- **Migration location:** `alembic/versions/`
- **Configuration:** `alembic.ini` and `alembic/env.py`
- **Apply migrations:** `uv run rag migrate`
- **Documentation:** See `docs/DATABASE_MIGRATION_GUIDE.md`

## Archive

The `archive/` subdirectory contains old SQL migration files that were created before Alembic integration:

- `001_add_fulltext_search.sql` - Added full-text search support (applied manually)
- `002_require_collection_description.sql` - Initial version before Alembic (superseded by Alembic migration `555255565f74`)

These files are preserved for historical reference only and should not be executed directly.

## Migration History

All schema changes from this point forward are tracked in Alembic migrations under `alembic/versions/`.

To see the complete migration history:
```bash
uv run alembic history
```

To see the current migration version:
```bash
uv run alembic current
```
