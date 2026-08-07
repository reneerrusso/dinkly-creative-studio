# Deployment templates

These templates demonstrate a scale-to-zero Cloud Run API and a single-concurrency task runner. They are examples, not a business-logic dependency: both containers use `Dockerfile.backend`, while the frontend uses `Dockerfile.frontend` on any Next.js host.

Do not place secrets in these YAML files. Configure every sensitive environment variable in the hosting provider's secret manager. Replace every uppercase URL/image placeholder before applying a template.

The public API receives web and signed Slack Events requests. `CLOUD_TASK_RUNNER_URL` points to the runner. The runner endpoint also requires `CLOUD_TASK_TOKEN`. Cloud Scheduler calls `/api/cloud/schedules/due`, `/learning`, and `/maintenance` on the public API with `X-DINKLY-Scheduler-Token`.
