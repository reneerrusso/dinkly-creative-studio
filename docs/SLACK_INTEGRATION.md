# Slack Integration

Slack is an `AgentChannel`, not a second agent. Mentions and direct messages enter the same persisted inbox as web assignments. Replies stay in the originating thread, status updates edit the existing Slack message when possible, and interactive approvals call the same backend action as `/approvals`.

## Modes

- **Events API** is the cloud mode. Configure the public HTTPS endpoint at `/api/slack/events` and the interactive endpoint at `/api/slack/interactions`.
- **Socket Mode** is the local-development mode. Add an `xapp-` token and run the persistent Agent worker. Only one mode is required.

Required Slack credentials are `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET`; Socket Mode additionally requires `SLACK_APP_TOKEN`. Settings writes them to the ignored backend secret store. They are masked in status responses and never sent to frontend code.

Saving the connection runs Slack `auth.test`; DINKLY only persists `Connected` after that real API call succeeds. **Test Slack** performs `auth.test` again and then sends `DINKLY Agent is connected.` to the configured channel or DM. A failed delivery persists an Error state instead of presenting a false success. Workspace name, bot name, connection mode, last received event, and last sent message remain visible without returning any saved secret.

## Security

Events API requests require Slack HMAC signature verification, a timestamp within five minutes, replay protection, and an owner user-ID allowlist. Bot and subtype events are ignored. Slack assignments use the same Gemini and concept-generation budget gates as web assignments.

## App permissions

Use the smallest scopes needed for the chosen installation, normally `app_mentions:read`, `chat:write`, and `im:history`. Enable direct messages and interactivity. If artwork should render inline, cloud deployment must provide an HTTPS asset URL accessible to Slack; local-only paths are never represented as public.

## Honest acceptance

Automated tests use a recording transport to verify routing, threading, deduplication, signatures, progress updates, and actions without contacting Slack. A production acceptance remains incomplete until the real workspace, real provider, accessible image URL, and interactive click path are exercised end to end.
