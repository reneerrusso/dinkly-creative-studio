# DINKLY Agent Portraits

The seven supplied DINKLY portraits are the only production identities for Creative Studio agents. The canonical registry lives in `app/frontend/lib/agents.ts`; UI surfaces request an `agentId` from the shared `AgentAvatar` component and never select image files independently.

| Agent ID | Display name | Production asset |
| --- | --- | --- |
| `creative-director` | Creative Director | `/agents/creative-director.png` |
| `concept-generator` | Concept Generator | `/agents/concept-generator.png` |
| `prompt-agent` | Prompt Agent | `/agents/prompt-agent.png` |
| `social-intelligence` | Social Intelligence | `/agents/social-intelligence.png` |
| `art-review` | Art Review | `/agents/art-review.png` |
| `brand-integration` | Brand Integration | `/agents/brand-integration.png` |
| `motion-director` | Motion Director | `/agents/motion-director.png` |

Legacy route and run identifiers are aliases only. `prompt-engineer`, `art-reviewer`, `brand-partnerships`, `social-learning`, and `content-agent` resolve to the canonical portraits; they never create duplicate agents or duplicate sidebar entries.

## Rendering contract

- Preserve the full square artwork with `object-contain`; never crop the character or role prop.
- Use the softly rounded portrait container provided by `AgentAvatar`.
- Use the same portrait in the expanded and collapsed sidebar, mobile navigation, room header, chat reply, live-work stream, run history, and status treatment.
- Status is a separate dot and never changes the source image.
- If an asset cannot load, show the neutral initials fallback. Do not substitute an animal, emoji, or unrelated avatar.

The previous generated avatars are retained only in timestamped backup/archive directories under `app-data/` and are not part of the production public asset directory.
