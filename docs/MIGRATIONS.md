# Database Migration Strategy

Alembic is the source of truth for new schema changes.

## Rules

- Add every new schema change as an Alembic revision under `alembic/versions/`.
- Keep `novel_writer/schema.sql` as the bootstrap schema for fresh local SQLite databases until a clean Alembic baseline replaces it.
- Keep the defensive `ALTER TABLE ... except: pass` blocks in `Database._init()` only as a legacy compatibility layer for existing local databases.
- Do not add new runtime migrations to `Database._init()` unless the app must repair an already released local schema during startup.
- Review generated Alembic revisions before committing them. Autogenerate output must not drop app tables unless that is the explicit migration goal.

## Current State

`alembic/versions/105afcb393f8_init.py` was generated from an existing database/model mismatch and contains many destructive `drop_table` and `drop_column` operations. Treat it as unsafe for production/local user data until it is replaced with a reviewed baseline.

Recommended next migration cleanup:

1. Create an empty SQLite database from `novel_writer/schema.sql`.
2. Align `novel_writer/db_models.py` with that schema.
3. Replace the current initial revision with a reviewed baseline that creates the schema without destructive operations.
4. Move future schema additions out of `Database._init()` and into Alembic revisions.

## Commands

```bash
pip install -e ".[dev]"
alembic current
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
