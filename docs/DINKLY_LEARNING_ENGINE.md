# DINKLY Learning Engine

The DINKLY Learning Engine owns memory extraction, production outcome analysis, prompt/QA/creative preference learning, performance snapshots, budget enforcement, and permanent Brain proposals.

## Evidence loop

The durable loop is generate → QA → human approval → publish → performance → learn → memory → future retrieval. The current learning pass is deterministic and checkpointed. It scans only unprocessed approvals, rejections, QA failures, repairs, feedback, used storylines, and performance data. With no changed evidence it performs no model call and incurs no AI cost.

Each learning has a concrete statement, type, evidence IDs, confidence, timestamps, and active/proposal status. A checkpoint keeps previously processed evidence from being relearned. Performance metrics remain time-stamped snapshots, and recommendations must not claim causation from small samples.

## Cost guardrails

Before any future model-assisted analysis, `LearningCostGuardrail` checks per-task, daily, and monthly limits. A blocked job leaves evidence unprocessed for a later run. Spending records never contain credentials.

## Permanent rules

A recurring pattern may produce a Brain Update Proposal only with multiple evidence records. Approval is required. Local mode can apply an approved rule to an allowed curated file. Cloud mode records `approved_pending_git`, because a running cloud container must never silently mutate a Git checkout; a reviewed Git/CI workflow applies the approved patch and records its commit.

Allowed curated targets are the Creative Bible, Character Bible, Style Guide, Nano Banana Rules, and Failure Library.
