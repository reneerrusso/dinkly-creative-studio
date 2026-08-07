# Apify Setup

## Before connecting

Create or select Instagram and TikTok Actors that are authorized for the public data you intend to retrieve. Review their current input schema, output fields, pricing, and terms in Apify. DINKLY Creative Studio does not claim a fixed Actor price because Actors can change independently.

You need:

- an Apify API token;
- no Actor IDs for normal setup: DINKLY Creative Studio selects verified recommended defaults.

An Apify Actor is a hosted data-retrieval program. DINKLY currently recommends Apify's official Instagram Scraper and Clockworks' TikTok Profile Scraper. Actor IDs are kept under **Advanced Settings** and only need to be entered when deliberately overriding a default.

## Configure in the application

1. Start the local frontend and backend.
2. Open **Settings & health → Social Data Providers**, or Social Intelligence’s **Settings** tab.
3. Paste the token. The app automatically checks the token and each recommended platform Actor independently.
4. Choose **Save securely**. The browser clears the token field after the request.
5. Choose **Test connection**.
6. Review budget limits before enabling paid provider calls.

The token is sent only to `127.0.0.1` unless you intentionally change the backend URL. The backend stores it at `app-data/secrets/.env.local` with restrictive file permissions. The API returns only a mask such as `••••••••••••abcd`.

## Configure with environment variables

For an externally managed local environment, set:

```bash
export APIFY_API_TOKEN="your-token"
export APIFY_INSTAGRAM_ACTOR_ID="owner~instagram-actor"
export APIFY_TIKTOK_ACTOR_ID="owner~tiktok-actor"
```

Environment variables override the local secret file. Do not add real values to `.env.example`, shell history shared with others, screenshots, issues, or Git.

## First refresh

Start with one handle and a small post limit. Preflight shows handle count, maximum items, a conservative cost range, remaining daily/monthly budgets, provider state, warnings, and hard stops. First-run estimates require confirmation because no local actual-cost history exists. Confirming one run does not disable future guardrails.

## Common failures

- **Authentication:** replace or revoke the token, save, then test again. The circuit opens immediately.
- **Insufficient credit:** add credit or change provider; do not repeatedly retry.
- **Default Actor unavailable:** retry the health check; Instagram and TikTok report separately, so one may remain usable. Open Advanced Settings only if a maintained replacement is needed.

Actor Store pricing may change by plan and usage model. The registry records the pricing behavior observed at verification time without promising an exact bill. Every default or override still passes through the per-run, daily, and monthly budget guardrails; changing an Actor never enables paid calls or bypasses confirmation.
- **Schema changed:** inspect the Actor’s current input/output contract and update the adapter with tests.
- **Rate limited:** wait for the provider boundary; retries remain capped.
- **Timeout:** reduce handle/item scope before increasing timeouts.

## Rotate or remove a token

Use **Replace Apify API token** to rotate in place. Use **Remove key** and confirm to delete the managed token while preserving unrelated local environment lines. Each secret-file mutation creates a restricted timestamped backup under the ignored secret directory.

After rotation, test the connection and inspect the provider state. Historical public evidence does not depend on the token and remains available.

## Live-call policy

Automated tests use mocked HTTP transports. Repository validation never calls Apify. A real test or refresh occurs only from an explicit user action with usable configuration. Keep paid calls disabled in cloned or demonstration environments.
