# Provider Budget Guardrails

## Default posture

Paid provider calls default to off. Initial limits are deliberately small:

| Guardrail | Default |
| --- | ---: |
| Maximum estimated cost per run | $1.00 |
| Daily provider budget | $2.00 |
| Monthly provider budget | $5.00 |
| Maximum handles per refresh | 5 |
| Maximum posts per handle | 20 |
| Maximum provider requests per run | 10 |
| Maximum retries | 2 |
| Confirmation above estimated cost | $0.50 |
| Automatic pause threshold | 80% |
| Hard stop | 100% |
| Paid overage | Off |
| Schedule | Off |

These are application boundaries, not a claim about provider prices.

## Cost accounting

When a provider reports an actual USD cost, the usage record stores it and budget accounting uses it. When actual cost is absent, the record keeps `actual_cost: null` and the conservative pre-run estimate counts toward local budget consumption. The UI must label that value as estimated, not actual.

Usage records live in `data/provider_usage.json`. Each record can include provider, Actor, run, estimate, actual cost, requests, compute units, item count, handle count, source, and status. Unknown billing fields remain `null`.

## Preflight

Every live refresh receives preflight before a run is created. It checks:

- enabled handle and platform scope;
- per-run handle/item/request limits;
- configured credential and required Actor IDs;
- circuit and manual pause state;
- conservative cost range;
- daily and monthly remaining amounts;
- scheduled-run confirmation rules;
- first-run or unknown-cost uncertainty.

Preflight returns `can_run`, `requires_confirmation`, warnings, and hard stops. The frontend presents these values; it does not recalculate or soften them.

## Request-time enforcement

Preflight is not the only boundary. The backend rechecks budget before each provider request, Actor poll, download, and retry. This protects against a long run consuming a changed budget after it began. Reaching 80% automatically pauses when configured. Reaching 100% is a hard stop unless a person has deliberately enabled paid overage.

## Scheduling

Scheduling defaults off. A scheduled attempt that needs first-run, unknown-cost, or threshold confirmation is skipped rather than silently charged. Local scheduling works only while the application worker or installed service is running and never wakes a stopped computer.

## Changing limits

Increase one boundary at a time after inspecting actual usage. Keep per-run limits below daily limits and daily limits well below monthly limits. A high monthly ceiling does not justify a high request or retry ceiling.

## Incident procedure

If usage looks wrong:

1. Pause the provider.
2. Cancel the active run.
3. Inspect `data/provider_usage.json` and the Runs tab.
4. Compare provider-reported billing directly in the provider console.
5. Correct Actor or scope configuration.
6. Lower budgets if uncertainty remains.
7. Resume only with explicit confirmation, then test before refreshing.

The local budget is a defense-in-depth control, not a replacement for vendor-side spending limits.
