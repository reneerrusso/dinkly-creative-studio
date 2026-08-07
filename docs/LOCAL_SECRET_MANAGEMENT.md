# Local Secret Management

## Storage boundary

Provider credentials are backend-only. The managed file is:

```text
app-data/secrets/.env.local
```

The directory and file are ignored by Git. The service requests owner-only permissions for the directory, secret file, temporary file, and backups. Writes use a temporary file, flush, filesystem sync, and atomic replacement.

## Browser behavior

The browser holds a token only in the password input’s React state until Save is selected. It sends the token to the local backend and clears the field after success. The backend never returns the token. Status responses contain only configuration flags and a last-four mask.

Do not store provider tokens in localStorage, sessionStorage, cookies, query strings, route state, JSON data files, logs, run events, or error messages.

## File preservation

`SecretsService` edits only the managed Apify keys and preserves unrelated environment lines. Before a mutation it creates a timestamped restricted backup inside `app-data/secrets/backups/`. Removing a token removes only `APIFY_API_TOKEN`; Actor IDs and unrelated local settings can remain.

## Environment precedence

Process environment variables override the managed file. This supports external secret tooling without changing application code. A managed-file removal cannot delete a process environment variable; restart or change the launching environment if status remains configured.

## Redaction

Known secret values and bearer credentials are replaced before a provider error can enter persisted run state. Provider adapters must not place tokens in URLs. Automated tests assert that invalid-key responses and request URLs cannot expose the token.

## Rotation

1. Pause provider calls.
2. Revoke or rotate the token at the provider.
3. Save the replacement locally.
4. Test the connection.
5. Review budget and circuit state.
6. Resume with explicit confirmation.

## Repository and support hygiene

Before pushing, confirm `.gitignore` covers the secret directory and `.env.local`. Never attach the secret file to support requests. When sharing diagnostics, use the provider state, safe error code, run ID, and timestamp—not raw headers or vendor responses that might contain credentials.

## Threat boundary

This protects against accidental Git commits, browser persistence, ordinary log leakage, and partial writes. It is not a system keychain or multi-user authorization boundary. Anyone with full access to the local account and repository files may access local secrets. Use operating-system account security and vendor-side least privilege.
