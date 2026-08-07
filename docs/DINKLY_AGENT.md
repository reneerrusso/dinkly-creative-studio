# DINKLY Agent Runtime

The Generation Engine has one visible studio operator: the canonical `social_intelligence` DINKLY portrait. Its motion and status always come from persisted backend activity.

## Truthful states

- `idle`: online and ready.
- `learning`: the checkpointed local learning job or an explicit chat preference write is active.
- `preparing`: story, prompt, or reference preparation is active.
- `generating`: a real image candidate request is active.
- `reviewing`: visual QA is active or a completed repair is being checked.
- `repairing`: a targeted image edit is active.
- `waiting_for_human`: a persisted run is at the human checkpoint.
- `success`: a real approval or completed learning job, followed by a short return to idle.
- `error`: a persisted provider or generation failure.

`AgentVisualStateService` is the only raw-event mapping layer. Frontend components consume its public runtime state and do not infer work from timers.

## Expressions and motion

CSS supplies subtle breathing, tilt, bounce, look, and success motions. `prefers-reduced-motion` disables every transform animation. Optional official PNG expressions live in `app/frontend/public/agents/dinkly-agent/`. Missing files use `/agents/social-intelligence.png`; the application never generates substitute expression art.

## Learning loop

The local scheduler checks once per hour. It fingerprints approvals, rejections, QA findings, repairs, used storylines, explicit feedback, and published metrics. When the checkpoint contains all evidence IDs, the job records no activity, keeps the agent idle, and makes zero provider calls.

New evidence produces concrete, evidence-linked proposals in:

- `data/generation_learnings.json`
- `data/prompt_learnings.json`
- `data/qa_learnings.json`
- `data/user_preferences.json`

Automated production-rule changes are disabled by default. Learnings remain proposed unless existing human approval rules promote them.

## Chat

The live-work drawer accepts concise feedback such as “Less couch content” or “Keep backgrounds simpler.” The write is stored as a structured high-confidence user preference. The brief learning state is the real persistence operation, not a simulated model response.
