# Slack Cloud Setup

## Mode boundary

Local development supports Socket Mode. Cloud deployment always uses Slack Events API and does not run a persistent Socket Mode connection. Both modes call the same `DinklyAgent`, Postgres task queue, conversations, approvals, and memory.

## Cloud app configuration

1. Store `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in the backend and runner secret managers. `SLACK_APP_TOKEN` is needed only for local Socket Mode.
2. Set the Slack Event Request URL to `API_URL/api/slack/events`.
3. Set the Interactivity Request URL to `API_URL/api/slack/interactions`.
4. Subscribe to the message/app-mention events required by the existing workflow and install the bot with the scopes shown by Settings diagnostics.
5. In DINKLY Settings choose Events API, configure the allowed user list/default channel, and run the real connection test.

Every inbound request is verified against the signing secret and timestamp before JSON or interaction handling. Slack event IDs are deduplicated in persistent storage. Tokens are never logged.

## Event execution

Slack must receive a fast acknowledgement. The signed event is converted into a durable `AgentTask`, then a background dispatch wakes the scale-to-zero task runner. Image generation is not performed inside Slack's acknowledgement path.

## Verification

Check `/health/slack` and Settings diagnostics. Then send a real DM, confirm the matching task in the web UI, approve it on the web, and verify Slack reflects the same persisted state.
