---
description: Inspect and operate CBC Learning V3 safely, with human review for any promotion
agent: cbc-coordinator
---
Handle this V3 learning request: $ARGUMENTS

Start with `python3 .opencode/scripts/cbc_learning_v3.py status` and, when a specific task is provided, `recall --project CBC --query "<task terms>" --limit 3`. Check code and tests before inferring a fix.

If asked to propose an experience, explain the exact record command using short sanitized fields. A model may record a pending experience, but must not act as the human reviewer or invoke `review --confirm`, `publish --confirm`, `rollback --confirm`, `migrate --apply --confirm` or tests that have not been authorized.

If asked to build a new skill, enforce three independent approved verified lessons, evaluated baseline-versus-candidate results and explicit manual review; don't assert skill improvement from a text-only score. Report evidence and blockers.
