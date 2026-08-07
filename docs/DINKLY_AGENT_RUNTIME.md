# DINKLY Agent Runtime

The product exposes one persistent employee: **DINKLY Agent**. Concept generation, prompt compilation, image generation, art review, repair, Story Library lookup, history, and learning remain internal tools. Web and Slack never choose a tool directly; they submit a natural-language assignment to one durable inbox.

## Canonical flow

1. `receive_instruction()` normalizes the assignment and resolves safe structured context.
2. `plan_task()` classifies the assignment without making a provider call.
3. `AgentTaskService` saves it atomically with a priority and deduplication key.
4. The persistent worker claims one task, then `invoke_tool()` calls the existing production service.
5. Real service events drive the shared animated state: Preparing, Generating, Reviewing, Repairing, Waiting, Success, or Error.
6. `request_approval()` puts a human checkpoint in `/approvals` and the originating Slack thread.
7. Approval, rejection, and feedback update the same generation history and Brain evidence.

Queued, running, waiting, terminal, and conversational state survive process restarts in `app-data/dinkly-agent/`. JSON remains the local v1 adapter; the `AgentStorage` boundary permits a transactional cloud implementation later.

The Agent desk immediately renders the accepted queued task, then subscribes to its persisted SSE feed. Story, prompt, references, candidate generation, 80/20 layout, QA, repair, human-review, completion, and failure events are derived from the production generation service. Returning to the page restores the active task, linked run, elapsed time, prior events, and current candidate count from storage; terminal failures replace the loader with Retry and diagnostic actions.

## Priority

Explicit web and Slack assignments are first, then approvals, generation work, scheduled concepts, learning, and maintenance. Learning makes no model call when no evidence changed. An online idle worker therefore has zero AI cost.

## Story Library continuity

The Agent desk's Story Library selector sends the selected `story_id`. The generation service loads the canonical record and builds the brief from its scene, emotion, prop, color, and placement fields. A title-only instruction can still match a Story Library pair; unknown titles receive a generic brief instead of silently using another story.
