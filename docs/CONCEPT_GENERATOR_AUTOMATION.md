# Concept Generator Automation

Concept Generator has one production workflow: `ConceptGeneratorService.generate_daily_concept_batch(...)`. Manual, scheduled, current-day catch-up, and two-minute test runs all enter this method. The scheduler never carries a second prompt, schema, ranking path, or concept generator.

## Why the old 8:00 AM schedule did not run

The previous scheduler was a minute loop created inside FastAPI startup. It stopped whenever the backend stopped and had no macOS LaunchAgent installation or independent worker. Its exceptions were suppressed, scheduler state was not persisted, timezone was hardcoded, and the production provider factory returned an unavailable provider unless test fixtures were explicitly enabled. There was no real scheduled provider path. Consequently, opening the browser or frontend could not make an 8:00 AM background batch reliable, and failures left no durable operational explanation.

## Durable architecture

The macOS LaunchAgent label is:

```text
com.dinkly.creative-studio.concept-generator
```

It runs the project interpreter at `.venv/bin/python` with:

```text
python -m app.backend.workers.concept_generator_worker
```

The plist records the repository as its working directory, sets `DINKLY_REPOSITORY_ROOT`, writes stdout and stderr under `app-data/logs`, starts at login, and restarts after failure. The worker writes a heartbeat every 30 seconds even while a model request is active. FastAPI no longer hosts a parallel Concept Generator polling loop; app startup only performs one safe current-day catch-up check.

The worker reads the same ignored `app-data/secrets/.env.local` file as the backend. A shell-only `OPENAI_API_KEY` is intentionally not considered background-ready because launchd does not reliably inherit interactive shell variables. Save the provider through Settings so both processes resolve the same secret without putting it in the plist or repository.

## Schedule and sleep behavior

The default schedule is 8:00 AM in the detected and persisted IANA timezone. `ZoneInfo` performs local/UTC conversion and daylight-saving transitions. Settings support every day or weekdays, catch-up on wake, and catch-up on app start.

If the Mac is unavailable at 8:00 AM, the next worker check creates at most one catch-up for the current local date. It never creates historical missed batches. A filesystem lock plus persisted primary-batch check prevents the API and worker from creating two primary batches for one date.

State is stored in `app-data/concept_generator_scheduler_state.json` and includes the last check, attempt, successful run, status, error, skip reason, next computed run, and two-minute test result. Worker health is based on both launchd state and the persisted heartbeat.

## Production preflight

Before a scheduled call, the scheduler verifies:

- automatic generation and paid model calls are enabled;
- a real provider is configured from a background-readable secret;
- the provider can return a minimal connection response;
- estimated cost fits the automatic per-batch, daily, and monthly limits;
- a primary batch does not already exist;
- fixtures and demo providers are not in use.

A failed preflight creates a persisted **Skipped** agent run and no batch. Diagnostics perform every non-billable check but do not contact the model.

## Install and diagnose

Open:

```text
Settings → Agents → Concept Generator → Scheduler
```

Save the OpenAI provider, enable paid automatic calls, review the cost limits, save the schedule, and choose **Install Background Agent**. **Run Scheduler Diagnostic** must say `READY FOR 8:00 AM` before a production test can be scheduled.

The **Run 2-Minute Scheduler Test** action persists a due time two minutes ahead. The LaunchAgent—not the frontend—executes the real provider and canonical production workflow, saving a supplemental batch so the daily primary batch is not overwritten. Closing the browser does not cancel it.

## Files and compatibility

Historical `content-agent` identifiers and `app-data/content_agent_settings.json` remain readable and display as Concept Generator. Existing batches, concepts, feedback, preferences, prompts, Used Storylines, events, and timestamps are never rewritten or deleted.
