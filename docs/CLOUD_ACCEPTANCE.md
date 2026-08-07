# Cloud Acceptance Record

Do not mark cloud persistence complete until this record is executed against public services with every local DINKLY process stopped.

First run `uv run python scripts/verify_cloud_deployment.py`. Then record non-secret evidence below.

| Step | Required observation | Evidence to record |
|---|---|---|
| Public app | Web app opens from another device/network | Frontend URL and timestamp |
| Local shutdown | Local frontend, API, and worker are stopped | Timestamp |
| Slack instruction | Send `Generate COFFEE / COFFEE WITH YOU.` | Slack event/task IDs |
| Shared queue | Same task appears in web | Task ID and screenshot |
| Generation | Cloud runner creates candidates | Generation and candidate IDs |
| Approval | Web approval completes | Approval ID |
| Artifact | Approved composition is in private object storage | Asset ID/path (not a signed secret URL) |
| Learning | New evidence is processed once | Learning ID and evidence IDs |
| Grounded answer | Ask `What did you learn?` | Memory IDs returned |
| Restart | Redeploy/restart API and runner | Revision and timestamp |
| Persistence | Ask the same question again | Same memory IDs |
| Laptop off | Send another Slack instruction while laptop is off | Slack event and task IDs |

Store this acceptance record outside the public repository if it contains workspace identifiers or private URLs.
