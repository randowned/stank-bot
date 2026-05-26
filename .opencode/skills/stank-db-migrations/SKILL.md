---
name: stank-db-migrations
description: Enforces Alembic migration conventions when creating or editing migrations, models, or running alembic commands. Trigger when touching migrations/versions/, db/models.py, or adding/removing columns.
---

# stank-bot database migration invariants

## Rules when creating migrations

1. **`down_revision` must match the current head.** Run `alembic history` to confirm the latest revision ID before writing a new migration. The chain has broken twice from incorrect `down_revision` — this is non-negotiable.

2. **Every migration must have both `upgrade()` and `downgrade()`.** Even if downgrade is destructive (drops a column with data), it must exist for rollback capability.

3. **Naming convention:** `YYYYMMDD_HHMM_short_description.py`. Revision IDs are 12-char alphanumeric strings (e.g. `a1b2c3d4e5f6`).

4. **Never modify a deployed migration.** Once a migration has been pushed to `main` and deployed, it is immutable. Create a new migration to fix issues. The only exception is fixing a typo in a comment before the next deploy.

5. **Partial indexes need both `postgresql_where` and `sqlite_where`.** The project runs SQLite in dev and PostgreSQL in production. Any conditional index must specify the WHERE clause for both dialects.

6. **Test reversibility locally:** After creating a migration, run `alembic upgrade head` then `alembic downgrade -1` to verify the round-trip works on the dev SQLite DB.

7. **Column additions on large tables should be nullable or have server defaults.** Adding a `NOT NULL` column without a default requires a backfill — do that in a separate migration step or use `server_default` and remove it in a follow-up.

8. **Import models inside the migration function**, not at module top level. This avoids model-import-order issues when Alembic runs migrations in sequence.
