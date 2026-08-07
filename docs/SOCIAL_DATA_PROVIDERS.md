# Social Data Providers

## Provider boundary

All public-data retrieval implements the `SocialDataProvider` interface in `app/backend/providers/social_data.py`. Creative analysis depends on normalized records, not provider-specific payloads. This boundary lets the team change vendors without rewriting the DINKLY evidence model.

Every provider must implement credential validation, handle validation, cost estimation, profile and post retrieval, normalization, usage reporting, status, cancellation, and health checking. Provider-specific raw metadata must be minimized and must never contain credentials.

## Available providers

### Manual import

Available by default and free of provider calls. It accepts CSV or JSON containing public post records. Use it for exported analytics, licensed datasets, and provider troubleshooting. The importer de-duplicates by platform and platform post ID and appends a new metric snapshot for each observation.

### Apify

The initial live provider. Instagram and TikTok resolve Actor configuration through the central `ActorRegistry`; business logic never embeds Actor IDs. Blank overrides use maintained recommended defaults, while Advanced Settings accepts a replacement only after its metadata and token access are validated. Authentication is sent in an `Authorization` header; the API token never appears in a URL. See `APIFY_SETUP.md`.

### Scaffolds

Official Instagram, Official TikTok, Bright Data, and Custom providers are explicit unavailable scaffolds. They advertise capability status but cannot run until an implementation is supplied. The UI must never imply that a scaffold is connected.

## Provider states

- **Not configured:** no usable backend credential. Actor verification is not attempted until a token exists.

The **Test connection** action validates the Apify token, Instagram Actor, and TikTok Actor independently. A platform failure is contained and does not crash the Social Intelligence Agent or disable the other healthy platform. Registry metadata lives in `data/social_provider_actors.json`; secrets never do.
- **Configured:** credential is present; this is not proof of a successful paid run.
- **Paused:** a person explicitly paused the provider.
- **Budget paused:** a cost boundary stopped calls.
- **Circuit open:** repeated or permanent errors prevent additional requests.
- **Available:** manual import or another no-credential capability is usable.

Connection tests validate provider credentials without storing the returned profile data. Tests may still be billable under a vendor’s current terms, so the user initiates them explicitly.

## Normalization contract

Common post records may include identifiers, URLs, captions, timestamps, media type, public counters, audio name, follower count, thumbnail URL, and a compact list of provider item keys. Unknown fields are `null`. Values are never inferred from adjacent fields.

Profile records may include username, display name, canonical URL, public follower/following/post counts, verification, and image URL. A profile reference is not a character or creative reference.

## Reliability rules

Provider requests use separate connection, read, Actor-run, and download timeouts. Retries are bounded, use backoff and jitter, and respect `Retry-After`. The budget guard is called before every request and retry. Cancellation is best-effort for an active HTTP request and always prevents the next request.

The circuit breaker opens after three consecutive transient provider failures. Authentication, credit, Actor-unavailable, and schema errors open it immediately because blind retries are unlikely to help. Manual resume requires explicit confirmation.

## Adding a provider

1. Implement `SocialDataProvider` without changing consumer code.
2. Keep credentials in `SecretsService`; never return them from a route.
3. Normalize missing data to `null` and preserve zero.
4. Provide conservative cost estimates and mark whether they are estimates.
5. Add request guards before every external request and retry.
6. Normalize failures to safe provider error codes.
7. Add deterministic transport tests with no live calls.
8. Add the provider to `/api/social-data-providers` only when its state reporting is truthful.

## Prohibited behavior

Do not call a live provider when paid calls are disabled, credentials are absent, preflight fails, confirmation is required but absent, the circuit is open, or a hard budget boundary is reached. Do not fabricate a provider response to make an empty UI look active.
