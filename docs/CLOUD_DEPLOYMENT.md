# DINKLY Cloud Deployment

## Production shape

DINKLY remains one agent, with six deliberately separate concerns:

| Concern | Production home |
|---|---|
| Code | GitHub |
| Brain | Git-versioned curated Markdown and templates |
| Memory | Supabase Postgres |
| Artifacts | Private Supabase Storage bucket |
| Runtime | Stateless FastAPI API plus scale-to-zero task runner |
| Channels | Cloud Next.js web app plus Slack Events API |

No dynamic learning is committed to Git. No LLM is treated as memory. The public API and task runner may scale to zero; work wakes them through web, Slack, approval, or scheduler events.

## Deployment order

1. Create the Supabase project and private storage bucket described in `SUPABASE_SETUP.md`.
2. Export `DATABASE_URL` in a secure terminal and run `uv run python scripts/apply_migrations.py`.
3. Run `uv run python scripts/migrate_local_to_cloud.py` first as a dry run. Run again with `--execute` only after reviewing counts.
4. Build `Dockerfile.backend` once. Deploy it as the public API and as a separate single-concurrency task runner. Both use the same Git revision and Supabase secrets.
5. Set `CLOUD_TASK_RUNNER_URL` on the API to the runner's HTTPS origin. Give API and runner the same `CLOUD_TASK_TOKEN` through the host secret manager.
6. Build `Dockerfile.frontend` with `NEXT_PUBLIC_API_URL` equal to the public API HTTPS origin, then deploy it to the Next.js host.
7. Configure Slack Events API using `SLACK_CLOUD_SETUP.md`.
8. Configure scheduler POST requests for `due`, `learning`, and `maintenance`, authenticated with `CLOUD_SCHEDULER_TOKEN`.

## Runtime variables

The canonical list is `.env.example`. Cloud mode specifically requires public HTTPS `APP_URL` and `API_URL`, Supabase credentials, the private storage bucket, task/scheduler tokens, model credentials, and Slack credentials. Sensitive values belong only in the host secret manager.

## Build commands

```bash
docker build -f Dockerfile.backend -t dinkly-backend .
docker build -f Dockerfile.frontend --build-arg NEXT_PUBLIC_API_URL=$API_URL -t dinkly-frontend .
```

The example Cloud Run service templates are under `deploy/`. Other hosts can use the same containers and HTTP contracts.

## Health and truthful status

Probe `/health`, `/health/database`, `/health/storage`, `/health/slack`, `/health/gemini`, and `/health/agent`. `ONLINE` is appropriate only when database, storage, and the task executor are healthy. It never implies a model is continuously running.

## Release and rollback

Run CI before deploying. Apply additive migrations before the application revision. Keep the prior API/runner image available. A rollback switches both runtime services to the prior image; Postgres and Storage remain persistent. Migration `0001` is additive and intentionally has no destructive rollback.

## Laptop-off acceptance

Do not sign off based only on local tests. Complete the 20-step acceptance sequence in the project brief using public web and Slack endpoints, stop every local DINKLY process, restart the cloud services, and verify the same memory again. Record URLs, run IDs, asset IDs, and timestamps without recording tokens.
