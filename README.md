# DINKLY Generation Engine

**Original IP. Scalable content. Human taste.**

DINKLY Generation Engine is the workspace and memory of one persistent creative employee: **DINKLY Agent**. Give the Agent a natural-language assignment in the web workspace or Slack. It plans the work, calls the existing concept, Story Library, prompt, Gemini image, QA, repair, history, and learning services, then returns for approval when human taste is required.

The primary routes are deliberately small:

- **DINKLY Agent** (`/agent`) is the Agent's desk: conversation, current work, Story Library assignment, waiting decisions, recent work, and Brain updates.
- **Approvals** (`/approvals`) contains only concepts, comics, and Brain updates that need human judgment.
- **History** (`/history`) reads like the Agent's employee work log across web, Slack, scheduled work, and learning.

The DINKLY Brain remains available in the sidebar: Memory, Story Library, Used Storylines, Examples, Failure Library, and Knowledge Base. Existing specialist services, social evidence, motion tooling, local data, tests, schemas, prompts, and generated assets remain preserved internal capabilities, not separate visible employees.

## Cloud mode and persistent memory

`APP_MODE=local` preserves the existing JSON/filesystem worker workflow. `APP_MODE=cloud` uses Supabase Postgres for tasks, conversations, generation metadata, checkpoints, preferences, and evidence-linked memory; Supabase Storage holds references and generated assets; a stateless FastAPI API dispatches durable work to a scale-to-zero task runner. Web and Slack therefore use one backend source of truth without treating an LLM or Git checkout as dynamic memory.

Begin with [`docs/CLOUD_DEPLOYMENT.md`](docs/CLOUD_DEPLOYMENT.md), then follow [`docs/SUPABASE_SETUP.md`](docs/SUPABASE_SETUP.md), [`docs/SLACK_CLOUD_SETUP.md`](docs/SLACK_CLOUD_SETUP.md), [`docs/DINKLY_MEMORY.md`](docs/DINKLY_MEMORY.md), and [`docs/DINKLY_LEARNING_ENGINE.md`](docs/DINKLY_LEARNING_ENGINE.md). Deployment is not complete until the laptop-off acceptance in the cloud guide passes.

## Generation Engine quick start

From the folder containing this README:

```bash
pnpm install
uv sync
pnpm dev
```

Open [http://127.0.0.1:3000/agent](http://127.0.0.1:3000/agent), then configure image generation:

```text
Settings → Image Generation → Add GEMINI_API_KEY → Save → Test connection
```

The key is stored only in the ignored backend secret file at `app-data/secrets/.env.local`, or read from the backend `GEMINI_API_KEY` environment variable. It is never returned to the browser, stored in frontend state after submission, written to JSON, or committed to Git.

Enable paid generation only after reviewing the per-run, daily, and monthly limits. Automatic Pro use is off by default. Demo Mode still performs real Gemini calls, but hides raw prompts, model IDs, provider diagnostics, and debug details.

The current centralized registry uses these Google Gemini image models, verified against official Google documentation on 2026-08-07:

- Nano Banana 2 Lite: `gemini-3.1-flash-lite-image`
- Nano Banana 2: `gemini-3.1-flash-image`
- Nano Banana Pro: `gemini-3-pro-image`

See [`docs/DINKLY_AGENT_RUNTIME.md`](docs/DINKLY_AGENT_RUNTIME.md), [`docs/SLACK_INTEGRATION.md`](docs/SLACK_INTEGRATION.md), and [`docs/CLOUD_DEPLOYMENT.md`](docs/CLOUD_DEPLOYMENT.md) for queue, channel, worker, security, and deployment behavior. [`docs/GENERATION_ENGINE.md`](docs/GENERATION_ENGINE.md) remains the source for model selection, QA, repair escalation, and cost handling.

## Sprite Studio

Sprite Studio is the local frame-by-frame motion library for approved Dinko, Dinka, shared-action, prop, and environmental-effect animation. It supports transparent frame uploads, sprite-sheet slicing, simple timeline timing, bottom-center anchors, onion skin alignment, structured character review, reusable compositions, immutable sheet and code exports, and Motion Studio handoff.

Open `/sprite-studio` after starting the existing frontend and backend. The first-run library includes locked Dinko and Dinka cards plus motion definitions marked **Frames needed**. Definitions never include invented character artwork. Upload illustrator- or designer-approved frames, review every frame, then approve the loop before it becomes available in production selectors.

Detailed operations are documented in:

- [`docs/SPRITE_STUDIO.md`](docs/SPRITE_STUDIO.md)
- [`docs/SPRITE_CHARACTER_RULES.md`](docs/SPRITE_CHARACTER_RULES.md)
- [`docs/SPRITE_ANIMATION_GUIDE.md`](docs/SPRITE_ANIMATION_GUIDE.md)
- [`docs/SPRITE_EXPORT_GUIDE.md`](docs/SPRITE_EXPORT_GUIDE.md)

Sprite image processing uses Pillow. The local Codex runtime is detected automatically. For a standalone environment, install `requirements-sprites.txt` into a Python interpreter and set `DINKLY_PILLOW_PYTHON` to that interpreter. This keeps the existing locked backend environment unchanged. Remotion is optional and is used only for final MP4 composition, never for default sprite creation.

The preserved DINKLY Creative Studio is the permanent operating system behind the focused Generation Engine. It combines brand strategy, locked character rules, social-performance learning, storyline scoring, Nano Banana prompt engineering, art QA, and brand-integration workflows in one version-controlled project.

This is an opinionated production system. It is designed to help a real creative team make consistent decisions—not to collect disconnected prompts.

## Local web application

The repository now includes a private, local-first web interface over the existing creative system. The Next.js frontend lives in `app/frontend/`; the FastAPI backend lives in `app/backend/`. The root bibles, examples, schemas, templates, scripts, and JSON records remain the source of truth.

The primary interface is organized around one visible DINKLY Agent. Historical specialist routes remain available for internal operations and compatibility, but they are hidden from buyer-facing navigation.

### Focused information architecture

The sidebar has three deliberate layers:

- **DINKLY Agent, Approvals, and History** are the entire primary working area.
- **Brain** is collapsed by default. It holds Story Library, Used Storylines, approved examples, failures, and the Knowledge Base.
- **Settings** holds the always-on worker, providers, Slack, notifications, and budget guardrails.

The Agent acts on the Brain; it does not replace it. The Brain is version-controlled evidence and rules. Existing internal tool URLs remain available so saved links and preserved workflows continue to work.

Internally, DINKLY Agent can generate and rank thirty-concept daily batches, compile prompts, run image generation, review and repair art, study social evidence, plan brand placement, and preserve motion assets. These remain implementation tools behind one personality and one inbox. Legacy rooms and their portraits remain available for compatibility, but the user does not need to choose between agents.

The underlying production loop remains complete:

1. **Learn:** ingest measured social results, preserve missing metrics, and generate evidence reports.
2. **Ideate:** browse the story library, record concepts, and run directional creative scoring.
3. **Build:** produce concise scene-aware Nano Banana prompts using the existing templates and scripts.
4. **Review:** classify artwork failures and generate a targeted edit or regeneration recommendation.
5. **Integrate:** build story-first branded, placeholder, second-pass, and evergreen prompts.

It also provides repository search, a failure library, approved examples, a Markdown knowledge editor, system health, and local preferences. Cloud mode adds backend-only Supabase persistence and object storage; authentication and analytics remain outside version one.

### Social Intelligence Agent

Open `/agents/social-intelligence` for monitored public-account research. The workspace includes Handles, Live Work, Posts, Learnings, Concept Directions, Runs, and Settings. It is empty by default and never invents demo metrics.

Manual CSV/JSON import is always available. Live Instagram and TikTok retrieval is optional through Apify. Provider credentials remain in the local backend, paid calls default off, and every refresh requires backend preflight against per-run, daily, monthly, handle, post, request, retry, confirmation, and circuit-breaker boundaries.

DINKLY automatically selects maintained recommended Actors for Instagram and TikTok. Normal settings use simple platform toggles; optional Actor overrides are under **Advanced Settings** and are validated before saving. **Test connection** reports token, Instagram, and TikTok health separately. Actor pricing can vary, but defaults and overrides always remain inside the same budget and confirmation controls. See `docs/APIFY_SETUP.md` and `docs/SOCIAL_DATA_PROVIDERS.md`.

Start with manual data:

```text
Social Intelligence Agent → Import data → choose .csv or .json
```

Or configure a live provider:

```text
Settings → Social Data Providers → Apify → Save securely → Test connection
```

Then enable paid calls only after reviewing the safe defaults, add a small set of handles, choose **Refresh handles**, inspect the preflight estimate and hard stops, and explicitly confirm. Runs stream persisted backend events; stopped workers are marked honestly and never resume paid work automatically.

Operational documentation:

- [`docs/SOCIAL_INTELLIGENCE_AGENT.md`](docs/SOCIAL_INTELLIGENCE_AGENT.md)
- [`docs/SOCIAL_DATA_PROVIDERS.md`](docs/SOCIAL_DATA_PROVIDERS.md)
- [`docs/APIFY_SETUP.md`](docs/APIFY_SETUP.md)
- [`docs/PROVIDER_BUDGET_GUARDRAILS.md`](docs/PROVIDER_BUDGET_GUARDRAILS.md)
- [`docs/LOCAL_SECRET_MANAGEMENT.md`](docs/LOCAL_SECRET_MANAGEMENT.md)
- [`docs/PUBLIC_DATA_LIMITATIONS.md`](docs/PUBLIC_DATA_LIMITATIONS.md)
- [`docs/COMPETITOR_ORIGINALITY_RULES.md`](docs/COMPETITOR_ORIGINALITY_RULES.md)
- [`docs/AGENT_RUNTIME.md`](docs/AGENT_RUNTIME.md)

### Screenshots

Add approved product screenshots here after the first local team review:

- Studio Lobby and one agent briefing room
- Concept evaluation
- Prompt builder
- Art QA review
- Social evidence table

### macOS setup

Install Node.js 20+ and pnpm. If Node was installed with Homebrew:

```bash
brew install node pnpm uv
```

Then, from the repository root:

```bash
pnpm install
uv sync
pnpm dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). The local API runs at [http://127.0.0.1:8000](http://127.0.0.1:8000), and its health endpoint is `/health`.

The defaults require no environment file. `.env.example` documents optional overrides; export backend overrides in the shell and place frontend overrides in `app/frontend/.env.local`.

### Always-on DINKLY Agent

Start the app once, then open:

```text
Settings → Always-on worker
```

Install or start the one background worker. It owns the shared web, Slack, scheduled, and learning inbox, writes a heartbeat, recovers stale in-progress tasks after restart, and remains idle at zero model cost when there is no work. Automatic concept jobs still obey the paid-call setting, per-run limit, daily budget, monthly budget, and real-provider requirement. The macOS LaunchAgent uses this repository's `.venv`; cloud mode runs the same worker module as a persistent process.

Always run these commands from the folder containing this README and the root `package.json`:

```bash
cd /path/to/dinkly-creative-studio
```

### Development commands

```bash
pnpm dev             # frontend, backend, and DINKLY Agent worker together
pnpm dev:frontend    # Next.js only, port 3000
pnpm dev:backend     # FastAPI only, port 8000
pnpm test            # Vitest and pytest
pnpm lint            # ESLint and Ruff
pnpm build           # production Next.js build
pnpm validate        # tests, lint, build, and repository validator
```

### First run

The root opens the DINKLY Agent desk. Type an assignment, choose a Story Library record, or ask what is waiting. DINKLY routes the work internally and returns to Approvals when your judgment is required. Use Brain only when you want to inspect the durable evidence and production rules behind the Agent's recommendation.

Story Library records use the version-2 scene model in `data/story_library_v2.json`. New stories carry panel-specific actions, settings, props, emotions, a shared environment, environmental contrast, and a required Boy/Girl left-panel choice. Older records are normalized at read time, keep their original scene summaries, receive empty arrays for missing panel props, default safely to Boy DINKLY when identity is unclear, and are marked `migration_version: 2` without rewriting or deleting the source record.

The scene-richness indicator is directional: **Sparse** means the setting or visual context is missing; **Balanced** is the target of one setting and two to five purposeful props per panel; **Detailed** signals more than five props in either panel or competing settings.

### Local data and backups

- Existing canonical evidence remains under `data/` and is validated against `schemas/`.
- App-created concepts, prompt drafts, art reviews, preferences, and stories live under `app-data/`.
- Uploaded PNG, JPG, JPEG, and WEBP files stay in `app-data/uploads/` and never leave the machine.
- Before an existing JSON or Markdown file is changed, the backend writes a timestamped copy to `app-data/backups/`.
- Writes use temporary files and atomic replacement. Paths outside the repository are rejected.
- `app-data/backups/`, `app-data/uploads/`, and generated reports are ignored by Git by default.

### Port conflicts

If port 3000 or 8000 is busy, identify the local process:

```bash
lsof -nP -iTCP:3000 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

Stop only the PID you recognize, or run one service on another port and update `NEXT_PUBLIC_API_URL` / `DINKLY_FRONTEND_ORIGIN` in `.env`. If the UI reports **Check API**, confirm `pnpm dev:backend` is running and open `/health` directly.

## What the studio does

- Generates emotionally clear comic concepts adjacent to proven winners without copying them.
- Scores concepts directionally across creative, social, brand, and execution criteria.
- Converts approved concepts into concise, modular Nano Banana briefs.
- Reviews generated artwork against locked character and style rules.
- Records known generation failures and targeted repair language.
- Ingests post metrics without inventing missing data.
- Separates measured facts, observed traits, hypotheses, and assumptions.
- Maintains living social learnings as more evidence is added.
- Supports natural product placement without weakening the story or character model.

## Creative source order

Before producing a comic, use these sources in order:

1. [`references/dinkly_young.png`](references/dinkly_young.png) for character identity and appearance.
2. [`CHARACTER_BIBLE.md`](CHARACTER_BIBLE.md) for production-model rules.
3. [`CREATIVE_BIBLE.md`](CREATIVE_BIBLE.md) for the emotional and strategic North Star.
4. [`SOCIAL_LEARNING.md`](SOCIAL_LEARNING.md) and `data/social_learnings.json` for evidence-based performance patterns.
5. [`VIRAL_FRAMEWORK.md`](VIRAL_FRAMEWORK.md), [`STORY_LIBRARY.md`](STORY_LIBRARY.md), and [`FAILURES.md`](FAILURES.md) for concept development.
6. [`NANO_BANANA_RULES.md`](NANO_BANANA_RULES.md) and the appropriate `PROMPT_TEMPLATES/` file for production.
7. [`QA_CHECKLIST.md`](QA_CHECKLIST.md) before approval or editing.

The most recent explicit creative direction wins when an older example conflicts with a newer rule. Character references remain absolute for character identity.

## CLI requirements

- Python 3.11 or newer
- No database
- No database or cloud service

Confirm Python:

```bash
python3 --version
```

## Install and run

Clone the repository and enter it:

```bash
git clone https://github.com/reneerrusso/dinkly-creative-studio.git
cd dinkly-creative-studio
```

Run the full validation suite:

```bash
python3 scripts/validate_project.py
```

Run tests directly:

```bash
python3 -m unittest discover -s tests -v
```

## Add character references

Store approved model sheets in `references/`. Never overwrite an existing model sheet silently. Use stable, descriptive filenames and update `CHARACTER_BIBLE.md` when a new approved view or expression sheet is added.

The current locked reference is:

```text
references/dinkly_young.png
```

Character references define character identity only. Product references define the product only. Never let one reference influence the other.

## Ingest a social post

The preferred input is a JSON file containing every known field. Unknown values should be `null`; do not estimate them.

```bash
python3 scripts/ingest_social_post.py --json-file incoming/coffee_post.json
```

You may also provide command-line fields:

```bash
python3 scripts/ingest_social_post.py \
  --title "Coffee With You" \
  --platform instagram \
  --post-date 2026-08-01 \
  --views 5100000 \
  --shares 112000 \
  --format x-with-you \
  --storyline coffee \
  --uploaded-asset-reference uploads/coffee-2026-08-01.png
```

The ingester validates the record, generates an ID when necessary, normalizes missing fields to `null`, prevents likely duplicates, and atomically updates `data/social_posts.json`.

## Analyze top-performing posts

```bash
python3 scripts/analyze_social_posts.py
```

The analyzer calculates rates only when the required values exist and views are greater than zero. It updates the generated evidence tables in `SOCIAL_LEARNING.md` while preserving the manually reviewed learning history in `data/social_learnings.json`.

## Generate and score storylines

Create a storyline JSON record from the fields described in [`schemas/storyline_score.schema.json`](schemas/storyline_score.schema.json), then run:

```bash
python3 scripts/score_storyline.py drafts/rainy_walk.json
```

The result is a directional creative evaluation—not a performance forecast. It records the score, weakest criterion, improvement recommendation, and any social learnings that influenced the evaluation in `data/storyline_scores.json`.

## Create a Nano Banana prompt

```bash
python3 scripts/generate_prompt_brief.py drafts/rainy_walk.json --output work/rainy_walk_prompt.md
```

The generator chooses the appropriate template and inserts only relevant character, composition, and failure-prevention rules. Review the result with the Prompt Engineer agent instructions before generation.

In the local Prompt Builder, captions, scene descriptions, and emotional insight are optional. Leaving a caption blank explicitly tells the image model to render no text. A source comic can also be uploaded for private on-device analysis: the studio converts it into an editable written scene brief and embeds that brief in the finished prompt, so the source image does not need to be attached in Nano Banana. Always review the detected brief before generation when the studio reports limited visual detection.

Concept Generator handoffs preserve the source batch, exact approved scene structure, props, emotions, environment, colors, camera angle, evidence references, preferences, and execution risks. Prompt Agent owns final prompt creation through Prompt Service. Five-comic stories produce five independently generatable Prompt Service records with one continuity instruction instead of one overloaded five-panel image.

## Review generated art

1. Compare the output with the official model sheet at full size.
2. Run every applicable check in `QA_CHECKLIST.md`.
3. Classify issues as critical, major, or minor.
4. Use the Art QA agent workflow to write a narrow edit prompt.
5. Regenerate instead of editing when the composition is structurally wrong or two precise edits have failed.

## Update the Social Learning system

1. Add post records with `ingest_social_post.py`.
2. Run `analyze_social_posts.py`.
3. Have the Social Learning agent inspect the actual comic assets.
4. Add or update evidence-backed entries in `data/social_learnings.json`.
5. Preserve contradicted learnings; mark the contradiction and update confidence instead of deleting history.

## Add approved prompts and examples

- Put approved production prompts in `data/approved_prompts.json` using `schemas/prompt_record.schema.json`.
- Add human-readable case studies to `EXAMPLES/`.
- Record why the example is approved, which risks it handles, and which parts are reusable.
- Never label a prompt approved until the generated result has passed art QA.

## Record failures

Add recurring failures to `FAILURES.md` with:

- Failure
- Likely misunderstanding
- Prevention language
- When to simplify
- When to edit
- When to regenerate

If the failure is scene-specific, also reference it in the relevant template or example. Avoid adding the entire failure library to every prompt.

## Repository map

- Root Bibles and guides: brand, character, style, viral, social, story, prompt, QA, integration, and failure systems.
- `data/`: portable source-of-truth JSON records.
- `schemas/`: JSON Schema contracts for records.
- `PROMPT_TEMPLATES/`: modular Nano Banana production templates.
- `EXAMPLES/`: approved concept and prompt case studies.
- `agents/`: role-specific operating instructions.
- `scripts/`: ingestion, analysis, scoring, prompt generation, and validation tools.
- `tests/`: data-integrity, scoring, brand-rule, and structure tests.
- `brain/`: preserved source Brand Bible material.
- `references/`: locked production-model artwork.

## Operating principle

Every comic should make an ordinary moment feel warmer because it is shared. If the concept is difficult to understand, depends on dialogue, weakens the character model, or feels built around an advertisement, simplify it before production.
