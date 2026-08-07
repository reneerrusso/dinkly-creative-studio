# DINKLY Memory

DINKLY Memory is durable, evidence-linked production knowledge in Postgres. It is separate from conversation history and from the curated Git-versioned Brain.

## Classification

`MemoryExtractor` classifies a message as temporary context, creative preference, feedback, production learning, or not memory. “Generate number 4” remains conversation context. “Stop giving me so many couch scenes” becomes a creative preference linked to its source task and relevant artifacts.

Memory records store type, key, summary, structured value, confidence, source, evidence IDs, active state, and timestamps. Supported types include creative, prompt, QA, generation, failure, concept, layout, model, and performance learnings.

## Retrieval

`KnowledgeRetriever` selects relevant curated Brain files. `MemoryRetriever` ranks active memory against task terms while always considering current creative preferences. `AgentContextBuilder` records both reference lists. Generation prompts receive only a short relevant subset and persist `brain_refs_used` and `memory_refs_used` for traceability.

## UI and control

The Memory page filters durable records and exposes source, confidence, active state, and evidence IDs. A human can edit, deactivate, or delete a record. Evidence-backed records with at least two sources can become a Brain Update Proposal; they do not modify a curated file by themselves.

## Grounded answers

Questions such as “What do you know about coffee comics?” use stored active records and return memory and evidence references. If no supporting memory exists, DINKLY says so instead of inventing an answer.
