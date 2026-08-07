# DINKLY Agent Architecture

DINKLY Creative Studio uses seven primary agents. Each agent owns one decision boundary and hands structured work to the next specialist.

1. **Creative Director** sets high-level creative direction, campaign thinking, and brand strategy.
2. **Concept Generator** researches available signals; reads Social Intelligence, the DINKLY Brain, preferences, and Used Storylines; then generates, ranks, refines, schedules, and manages storyline concepts.
3. **Prompt Agent** turns approved concepts into production-ready Nano Banana prompts.
4. **Social Intelligence** owns performance analysis, public-data retrieval, competitor and trend monitoring, evidence, and pattern discovery.
5. **Art Review** checks generated artwork for character, scene, text, scale, and style consistency.
6. **Brand Integration** adds natural product placements without turning the comic into an advertisement.
7. **Motion Director** animates approved artwork while protecting the locked character model.

## Canonical identity registry

`app/frontend/lib/agents.ts` is the single source of truth for agent IDs, names, roles, routes, status colors, and portrait paths. All UI surfaces render identity through `AgentAvatar`; they do not hardcode image paths. The seven supplied DINKLY portraits in `app/frontend/public/agents/` are the official visual identities. Legacy IDs remain aliases for saved links and historical runs but never create a separate visible agent. See `AGENT_PORTRAITS.md` for the complete mapping and fallback contract.

## Operational handoff

```text
Social Intelligence
        ↓
DINKLY Brain and Social Learnings
        ↓
Concept Generator
        ↓
Prompt Agent
        ↓
Art Review
        ↓
Publish
        ↓
Social Intelligence
```

Creative Director can influence the Concept Generator brief—for example, more outdoor stories, a seasonal emphasis, or more brand-friendly moments—but does not duplicate the daily thirty-concept workflow. Concept Generator decides **what to make**; Prompt Agent decides **how Nano Banana should render it**. Concept Generator consumes social outputs but never independently scrapes a platform.

The former Content Agent is not a separate agent. Its workflow is now the operational core of Concept Generator. Legacy route, API, import, runtime, and storage identifiers exist only as compatibility layers and never create a second queue or data store.
