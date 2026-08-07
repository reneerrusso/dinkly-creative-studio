# Social Intelligence Agent

## Purpose

The Social Intelligence Agent is the evidence specialist responsible for turning real public-post evidence into original DINKLY creative direction. It expands the owned-account Social Learning workflow; it does not replace it. Owned DINKLY results remain in `data/social_posts.json`, while monitored public accounts live in the separate competitor datasets.

The agent must answer three different questions without blending them:

1. What was measured on a public post?
2. What creative trait can be observed from the supplied metadata or a human classification?
3. What might DINKLY test as an original interpretation?

A correlation can support a hypothesis. It cannot prove why a post performed.

## First run

Open `/agents/social-intelligence`. The first-run state is intentionally empty. Choose one of two evidence paths:

- Configure Apify in the **Settings** tab, enable paid calls, add Actor IDs, set budget limits, add handles, review preflight, and explicitly confirm a refresh.
- Import a public CSV or JSON export manually. Manual import remains available with no provider token and no provider cost.

The application never inserts sample metrics into production data.

## Workspace tabs

- **Handles** stores normalized Instagram and TikTok public profiles to monitor. Removing monitoring preserves all historical posts, snapshots, learnings, and directions.
- **Live Work** renders only persisted backend events over Server-Sent Events. It does not simulate provider progress.
- **Posts** shows metrics, missing-field completeness, per-account baselines, and snapshot-backed velocity when enough observations exist.
- **Learnings** separates a measured fact, hypothesis, recommendation, and data limitation. A person must approve or reject each learning.
- **Concept Directions** translates approved reusable principles into new DINKLY scenes and includes a must-not-copy boundary.
- **Runs** records status, warnings, summaries, cancellation, and interrupted-worker recovery.
- **Settings** manages providers, actors, timeouts, local schedules, and cost guardrails.

## Recommended workflow

1. Add a small, coherent group of handles.
2. Run preflight and reduce scope if the upper estimate is uncomfortable.
3. Confirm the refresh only after reviewing provider health and remaining budgets.
4. Check Posts for metric completeness and account sample size.
5. Add human classification where public metadata does not describe the creative.
6. Analyze existing data.
7. Approve only defensible learnings.
8. Generate original directions from approved learnings.
9. Open a direction in Prompt Builder, which creates a normal DINKLY concept and prepopulates the existing workflow.

## Evidence standards

High confidence requires multiple strong examples or a clear performance gap across an adequate sample. One standout is always Low confidence. Missing metrics stay `null`; a true zero stays `0`. Ratios are not calculated when their required denominator is missing or zero. Velocity is unavailable until two or more time-separated snapshots exist.

The metadata classifier is deliberately conservative. It may label a caption-derived topic at Low confidence, but it does not claim to have seen a visual, camera angle, character pose, or video narrative. A configured future model classifier must retain that provenance and uncertainty.

## Provider failure behavior

Authentication, insufficient credit, rate limits, unavailable Actors, timeouts, schema changes, and cancellation use structured states. Successful platform results are preserved when another platform fails. Interrupted runs become Failed or Partial after restart. Secrets are redacted before errors are persisted.

## Data ownership

Canonical records are portable JSON:

- `data/monitored_handles.json`
- `data/competitor_profiles.json`
- `data/competitor_posts.json`
- `data/competitor_snapshots.json`
- `data/competitor_learnings.json`
- `data/competitor_concept_directions.json`
- `data/provider_usage.json`

Operational run state is under `app-data/`. Provider secrets are under ignored `app-data/secrets/` and must never be committed.

## Exporting or deleting collected data

The canonical JSON files are already portable exports. Stop the local backend before making an external archive, then copy the relevant `data/competitor_*.json`, `data/monitored_handles.json`, and `data/provider_usage.json` files to an approved secure location. Include their schemas when another system will validate them. Never include `app-data/secrets/`.

Removing a handle in the UI stops monitoring but deliberately preserves history. To delete collected public history, stop the backend, create a versioned backup, and remove the intended records from posts, snapshots, profiles, learnings, and directions together so references do not become misleading. Replace an entire dataset with an empty JSON array only when the team intends to erase that whole category. Run `python3 scripts/validate_project.py --skip-tests` before restarting. Secret deletion is separate and must use **Remove key** in Settings.

## Honest limitations

Public platforms and providers can change fields, access rules, availability, and costs. Provider output is normalized defensively, but field absence is expected. A stopped laptop cannot execute local schedules. The system studies supplied public data; it does not bypass authentication, scrape private data, download protected media, or establish permission to reuse another creator’s work.
