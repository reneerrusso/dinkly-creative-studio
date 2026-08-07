# DINKLY Generation Engine

## Purpose

The Generation Engine is the focused buyer-facing production loop for DINKLY:

`Concept → Story Brief → Prompt Compilation → Candidates → QA → Repair → Human Approval → History`

It reuses the canonical Story Library, Prompt Builder, templates, Character Bible, Style Guide, Nano Banana rules, Failure Library, official character model sheet, Used Storylines, local repository storage, and SSE event runtime. There is no parallel simplified prompt system.

## Routes

- `POST /api/generation-engine/brief`
- `POST /api/generation-engine/generate`
- `GET /api/generation-engine/runs/{id}`
- `GET /api/generation-engine/runs/{id}/stream`
- `GET /api/generation-engine/runs/{id}/candidates`
- `POST /api/generation-engine/candidates/{id}/select`
- `POST /api/generation-engine/candidates/{id}/qa`
- `POST /api/generation-engine/candidates/{id}/retry`
- `POST /api/generation-engine/candidates/{id}/repair`
- `POST /api/generation-engine/runs/{id}/approve`
- `POST /api/generation-engine/runs/{id}/reject`
- `POST /api/generation-engine/model-compare`
- `GET /api/generation-engine/history`
- `GET /api/generation-engine/model-stats`
- `GET /api/generation-engine/runs/{id}/download/final?format=png|jpg`
- `GET /api/generation-engine/runs/{id}/download/candidates`
- `GET /api/generation-engine/runs/{id}/download/qa`
- `GET /api/generation-engine/runs/{id}/download/summary`
- `GET /api/generation-engine/runs/{id}/download/all`
- `GET /api/image-models`
- `GET /api/image-provider/status`
- `POST /api/image-provider/test`

## Canonical prompt compilation

`GenerationEngineService` passes the editable Story Brief into the existing `PromptService`, which delegates to the repository-native prompt templates and scene-aware failure rules. Every recipe records:

- prompt ID
- template and template version
- Character Bible version
- Failure Library version
- creation time

Demo Mode returns only the applied recipe summary. Developer Mode may return the raw prompt. The raw prompt is still preserved locally for reproducibility.

## Model registry

`ImageModelRegistry` is the only place where image model IDs and capabilities are defined. The IDs were verified against official Google Gemini documentation on 2026-08-07.

| Product label | Registry key | Model ID | Default role |
|---|---|---|---|
| FAST · Nano Banana 2 Lite | `nano_banana_2_lite` | `gemini-3.1-flash-lite-image` | simple one-character scenes |
| BALANCED · Nano Banana 2 | `nano_banana_2` | `gemini-3.1-flash-image` | Dinko + Dinka, multiple references, split scenes, five-comic continuity |
| MAX · Nano Banana Pro | `nano_banana_pro` | `gemini-3-pro-image` | approved complex repairs and brand-sensitive precision |

Automatic mode is rule-based. It does not use a black-box performance model and does not expose chain-of-thought. Pro is never selected without both an applicable rule and explicit budget permission.

## Official references

The locked production model sheet is `references/dinkly_young.png`. Each run records independent Dinko and Dinka version hashes. The current file contains both characters, so the provider receives it once even when both identities are required. Separate future model sheets can replace the manifest paths without changing generation business logic.

## Candidate persistence

Every candidate and repair is immutable:

```text
app-data/generation-engine/
  prompts.json
  settings.json
  runs/
    <run-id>/
      candidates/
      repairs/
      metadata.json
      final.png
```

Partial success is preserved. A failed candidate can be retried without deleting successful candidates. Repairs create child candidates with `repair_parent_id`; approval copies the selected source into a final asset without overwriting the source.

## Visual QA and ranking

When Gemini visual analysis is available, QA checks character identity, anatomy, scene actions, settings, captions, shared background, composition, and prop scale. Findings are normalized to Pass, Warning, or Fail.

If visual analysis is unavailable, the UI says **Automated visual QA unavailable** and permits manual findings. It never fabricates a pass.

Ranking uses only detected production quality and scene alignment. It never predicts virality. Model comparison reports only measured runtime, QA, repairs, approval, and estimated/reported cost from the recorded runs.

## Cost controls

Settings include paid-generation enablement, maximum cost per run, daily budget, monthly budget, 80% warning threshold, 100% hard stop, and automatic Pro use. Cost values are estimates unless the provider returns a reported charge. Current 1K output estimates are centralized with the registry and should be re-verified when Google changes pricing.

## Real acceptance test

Use `COFFEE. / COFFEE WITH YOU.` in `/generate`:

1. Build and inspect the Story Brief.
2. Confirm official references and automatic model selection.
3. Generate four real candidates.
4. Confirm successful files exist under the run directory.
5. Review QA and recommendation.
6. Select a candidate and repair a real issue if necessary.
7. Re-run QA.
8. Approve at the human checkpoint.
9. Confirm the final run appears in History.
10. Run Lite versus Balanced comparison with the same brief.

Do not report this acceptance test as passed when `GEMINI_API_KEY` is absent, paid generation is disabled, the provider rejects the key, or no real image is returned.

## Persisted Generation Progress

The loader is reconstructed from stored `progress` events; it never invents percentages. Every event records a stage, state, concise message, timestamp, and any real candidate or QA counters.

Stages are Story, Compile, References, Generate, QA, Repair, and Human Review. Candidate images are persisted immediately after each provider response, and the frontend polls the run while replaying SSE events. Leaving and returning to `/generate` restores the last run ID and replays its stored event history.

## Approved Exports

Approved runs support lossless PNG, high-quality JPG, candidate ZIP, structured QA JSON, structured Generation Summary JSON, and five-comic ZIP exports. WEBP finals are normalized to PNG when requested. Export filenames are sanitized and stored under the run's `exports/` directory with a numeric suffix rather than silently overwriting an earlier export.

Image normalization uses Pillow when it is installed through the existing `requirements-sprites.txt`; the local macOS build can also use the native image converter.

All source paths must resolve inside the validated generation run directory. Raw prompts, credentials, and raw model IDs are excluded from Demo Mode summaries.
