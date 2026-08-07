# Agent Runtime

Concept Generator reuses this runtime with `agent: concept-generator`. Historical `content` and `content-agent` runs are normalized to the Concept Generator display name without rewriting their stored records. Its truthful stages are `prepare`, `research`, `build_brief`, the three format-generation stages, `deduplicate`, `score`, `refine`, `select_finalists`, `save_batch`, and `await_review`. SSE events contain actions, evidence counts, filters, validation results, and saved artifacts—not private model reasoning. Interrupted work is recovered using the same terminal-state rules as Social Intelligence.

## Runtime contract

The Social Intelligence Agent uses a small persistent runtime for provider work. Runs are stored in `app-data/agent_runs.json`; actual work events are stored in `app-data/agent_events.json`. Both use atomic repository writes and remain local.

The runtime does not generate artificial progress percentages. Each event is emitted by a real backend stage such as preflight, scope loading, budget check, provider request, deduplication, analysis, cancellation, warning, or completion.

## Run states

Supported terminal states are Completed, Completed with warnings, Partial, Budget stopped, Rate limited, Provider unavailable, Failed, and Cancelled. A created run begins as Running. Status language is user-facing and must not hide partial results.

## Server-Sent Events

The UI subscribes to:

```text
GET /api/agent-runs/{run_id}/events
```

Events have a stable ID, run ID, timestamp, level, kind, message, and structured data. The endpoint replays persisted events from the start for a new connection, emits keep-alives, and closes after the terminal event has been delivered. The frontend de-duplicates by event ID.

## Cancellation

Cancellation sets a persistent request flag and asks an active provider to cancel its HTTP request when supported. The request guard checks cancellation before the next provider operation. Data already written remains. Cancellation must never roll back valid prior snapshots or posts.

## Recovery

When a runtime service starts, a run left Running for more than 30 minutes is treated as stale and recovered. A run with summary evidence becomes Partial; otherwise it becomes Failed. The delay prevents the API process from corrupting a run that is still active in the independent worker. The runtime records a recovery event and never resumes paid external calls automatically after a crash.

## Security

Runtime requests and events may record handle IDs, scope, safe provider error codes, counts, estimates, and summaries. They must not store tokens, authorization headers, raw secret-file content, or unredacted provider errors.

## Operational endpoints

- `GET /api/agent-runs`
- `GET /api/agent-runs/{run_id}`
- `POST /api/agent-runs/{run_id}/cancel`
- `GET /api/agent-runs/{run_id}/events`

Run history is evidence for operations, not social performance. Do not mix provider usage or runtime outcomes with creative post metrics.
