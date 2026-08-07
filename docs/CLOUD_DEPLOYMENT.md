# Cloud Deployment Boundary

Local mode remains the default. `pnpm dev` starts the web frontend, API, and DINKLY Agent worker; macOS can install the worker as a LaunchAgent.

For cloud mode set `APP_MODE=cloud` and run three long-lived process types:

- Next.js web frontend
- FastAPI backend
- `python -m app.backend.workers.dinkly_agent_worker`

The API exposes `/health`, `/health/agent`, `/health/worker`, and `/health/slack`. A platform should restart a worker whose heartbeat is stale.

The current `AgentStorage` adapter uses atomic repository JSON. A multi-instance cloud deployment must replace it with a transactional Postgres-backed queue and conversation store. Generation assets must move to durable object storage with signed HTTPS URLs; configure `DATABASE_URL`, `DINKLY_OBJECT_STORAGE_URL`, and `DINKLY_PUBLIC_BASE_URL`. These boundaries are configured but a Postgres/object-storage adapter is intentionally not claimed as complete in version one.

Secrets belong in the cloud secret manager. Never bake Slack, Gemini, OpenAI, or social-provider credentials into an image, frontend variable, or repository file.
