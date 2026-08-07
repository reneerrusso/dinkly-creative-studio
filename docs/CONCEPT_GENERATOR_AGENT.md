# Concept Generator Agent

Concept Generator is DINKLY Creative Studio’s daily creative desk. It turns current evidence, durable DINKLY rules, explicit user preferences, and originality history into three reviewable groups: ten **X / X WITH YOU** concepts, ten **BEFORE / AFTER** concepts, and ten connected **5-COMIC STORIES**.

## Daily workflow

1. Load the Creative, Character, Style, Social Learning, Prompt, and Failure knowledge, plus Story Library, preferences, recent candidates, passed concepts, and Used Storylines.
2. Load measured owned-post evidence and approved Social Intelligence or trend findings when they exist. Missing current signals remain missing; evergreen generation continues without fabricated trends.
3. Build a compact brief identifying supported opportunities, overused topics, explicit preferences, and format balance.
4. Request 20–30 structured raw candidates per format from the configured model provider.
5. validate with Pydantic, remove exact and meaningfully similar stories, rank directionally, refine, and save exactly ten finalists per format. Scores guide editing and do not predict views.
6. Wait for review. Approval moves a concept to Production Queue; Pass preserves it in history; Replace changes one slot only.

Only one primary batch is allowed per local date. A second request must explicitly replace unreviewed candidates or create a supplemental batch. Approved work is never deleted. Scheduled generation uses the persisted 8:00 AM local schedule and independent macOS LaunchAgent described in `CONCEPT_GENERATOR_AUTOMATION.md`.

## Provider truthfulness

Concept creation requires a configured concept model provider. The legacy `ContentModelProvider` import remains available for compatibility. Without a provider, the page shows an honest provider-required state while Story Library, prior batches, preferences, queue, and Used Storylines remain available. `DINKLY_CONTENT_FIXTURES=1` enables deterministic records exclusively for tests and demonstrations; fixture batches are labeled in every concept and batch record.

## Review and production

Each category allows up to five approvals per batch, but zero to five is valid. Generate Prompt hands the approved scenes, props, emotions, setting, colors, camera, evidence references, and execution risks to Prompt Agent through the existing Prompt Service. Concept Generator does not maintain separate prompt-generation logic. A five-comic story creates five independently generatable prompts with a shared continuity lock.

## Compatibility and preserved data

The canonical route is `/agents/concept-generator` and the canonical API is `/api/concept-generator`. `/agents/content` permanently redirects, while `/api/content-agent` remains a deprecated alias. Existing `data/content_*.json` and `app-data/content_agent_*.json` filenames are intentionally retained, so no batch, feedback, preference, chat message, Used Storyline, timestamp, or ID is rewritten.

Generating the production prompt or explicitly marking work Used removes it from Today and Ready to Make, saves the complete source concept and prompt IDs in Used Storylines, and adds it to future semantic duplicate checks.
