# Supabase Setup

## Database

1. Create a Supabase project.
2. Copy the direct Postgres connection string into the deployment secret named `DATABASE_URL`. Use a connection option suitable for the chosen runtime; migration tooling needs a connection accepted by `psql`.
3. Configure backend-only `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` secrets.
4. Run `uv run python scripts/validate_migrations.py` and then `uv run python scripts/apply_migrations.py`.
5. Confirm `schema_migrations` contains `0001_dinkly_cloud`.

The service role is never exposed to Next.js. The migration enables row-level security on user-facing core tables and creates no public policies; the v1 backend is the only data client.

## Storage

Create one private bucket whose name matches `SUPABASE_STORAGE_BUCKET`. Do not make reference sheets or generated work publicly enumerable. The API streams required assets through `/api/assets/{storage_path}` without exposing the service role. Version one has no end-user authentication, so protect the web/API deployment at the hosting layer if the studio must be private.

The object store holds official references, original candidates, final 80/20 layouts, repairs, approvals, exports, and thumbnails. The `assets` table records storage path, content type, checksum, size, and generation/candidate links.

## Local migration

```bash
uv run python scripts/migrate_local_to_cloud.py
uv run python scripts/migrate_local_to_cloud.py --execute
```

The first command is read-only. The execute command creates a timestamped archive before copying, stores a checksum manifest, uploads assets, and never deletes the source files.

## Backup and recovery

Enable Supabase backups appropriate to the plan. Keep the pre-migration archive until the laptop-off acceptance passes. A recovery restores Postgres, keeps object paths stable, and redeploys API/runner from the matching Git revision.
