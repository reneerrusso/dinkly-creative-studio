# DINKLY Creative Studio

DINKLY Creative Studio is the permanent creative operating system for DINKLY comics and character-IP development. It combines brand strategy, locked character rules, social-performance learning, storyline scoring, Nano Banana prompt engineering, art QA, and brand-integration workflows in one version-controlled project.

This is an opinionated production system. It is designed to help a real creative team make consistent decisions—not to collect disconnected prompts.

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

## Requirements

- Python 3.11 or newer
- No database
- No required third-party packages for version one

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
