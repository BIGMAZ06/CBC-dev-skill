---
description: Coordinate a scoped CBC development task with reviewer and test gates
agent: cbc-coordinator
---
CBC Engineering task: $ARGUMENTS

Work in the CURRENT DEVELOPMENT REPOSITORY only. First inspect git status and derive objective, dependencies and acceptance checks. Use @cbc-planner where architecture uncertainty matters; use @cbc-coder for implementation, @cbc-qa for actual tests and @cbc-reviewer for independent review. If failed, consult @cbc-debugger, revisit root cause and retry within bounded effort. Prefer sequential writers.

For recurring issues, recall only three verified relevant CBC lessons. Treat .opencode/models/cbc-model-pool.json as provisional model candidates, not verified performance. Do not automatically consume provider quota or switch model in a way that restarts unknown side effects; get scope-appropriate authorization, inspect the diff and record results.

If a runtime budget is supplied, treat it as a target only: no hard timeout exists until an external supervisor enforces it. Report elapsed time if measurable, status COMPLETED/PAUSED/BLOCKED, actual tests, files changed, next action, and unfinished work. No deployment, credentials modification, merge, learning approval or destructive action without specific authorization.
