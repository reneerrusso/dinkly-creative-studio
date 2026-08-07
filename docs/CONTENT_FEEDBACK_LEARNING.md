# Content Feedback Learning

Concept Generator stores creative preferences, not personal profiling.

Chat feedback is converted into records in `data/content_agent_preferences.json`. Each record names its type, topic, value, strength, source, reference, confidence, timestamps, and active state. The user can edit, deactivate, or delete records under **Brain → Content Preferences**. Explicit user feedback always outranks behavioral inference.

Concept actions are stored separately in `data/content_feedback.json`: approved, rejected, skipped, used, or published. One pass is weak evidence and never becomes a universal rule. When the same rejection reason recurs at least six times across three batches, Concept Generator may create an inactive, medium-confidence possible preference. The user must activate it.

Published-post metrics remain measured Social Learning evidence. Linking a used concept to a published record can strengthen or challenge hypotheses, but Concept Generator never invents metrics or claims that a creative score predicts performance.
