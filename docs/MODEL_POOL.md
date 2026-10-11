# CBC Model Pool — Phase 1: evidence before routing

The candidate list is based on `opencode models` output provided by the owner on 2026-10-11 and Google's Free Tier pricing they reviewed. **A listed model is not necessarily callable, free for this project, or competent at coding.**

The owner confirmed **NVIDIA completed a task request but produced the wrong outcome**. Treat it as an observed reachable provider with **unverified output quality**; do not blacklist it as offline, or promote any particular NVIDIA model as reliable without knowing which was used.

## Read-only inventory

```sh
python3 .opencode/scripts/cbc_model_pool.py list
```

## Optional one-model connectivity test (uses provider quota)

Run only on a development machine where OpenCode is already authenticated:

```sh
python3 .opencode/scripts/cbc_model_pool.py probe google/gemini-3.8-flash
python3 .opencode/scripts/cbc_model_pool.py probe nvidia/z-ai/glm-5.3
```

The probe sends exactly one short `opencode run --model` request. It does not read or modify credentials. It does **not** run unattended, add automatic provider cycling, or access CBC production. It reports only a status and model ID, and stores timestamped metadata in Git-ignored `.opencode/task-state/model-pool/probes.json`. No raw model response is retained. It requires manual invocation and consumes the provider's quota; a result of `responded` proves a simple reply only, not the quality of any programming action.

## Proposed next stages

1. Verify one representative coding task + independent behavior tests per candidate model; measure error rate, coding quality, latency and token use. NVIDIA's past execution is real evidence of reachability but not correctness.
2. Give each role a tested model shortlist. Use deterministic local memory retrieval before any AI classifier.
3. Implement OpenCode session-aware fallback only for retryable provider failures (e.g. 429/503). Persist session ID/checkpoint and **never replay a side-effecting task if the previous attempt may have partially modified files** without inspecting the diff and test state.
4. Add a timeboxed supervisor with deadline, safe stop, structured handoff, and explicit resume. Stop rather than use paid/unknown-tier models automatically; never bypass provider quotas.
5. Keep production deploy, credential changes, and approval of persistent learning under human control.

No API key belongs in this repository. Free tiers can use submitted data for product improvement; do not send secrets or private user data in tests.
