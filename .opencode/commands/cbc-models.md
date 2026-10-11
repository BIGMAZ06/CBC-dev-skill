---
description: Inspect CBC model candidates or run an opt-in single-model connection probe
agent: cbc-coordinator
---
For this model-pool task: $ARGUMENTS

First inspect `.opencode/models/cbc-model-pool.json` and `docs/MODEL_POOL.md`.
Use `python3 .opencode/scripts/cbc_model_pool.py list` without provider calls.
Only use `probe MODEL_ID` when the user explicitly authorizes a call that consumes quota.
A responding model is not evidence of correct code. Do not enable paid models, change provider API keys, install fallback plugins, silently switch models, modify production, or replay side-effecting edits after partial failure.
Preserve a clear distinction between catalog listing, connection tested, coding quality verified, and free access confirmed.
