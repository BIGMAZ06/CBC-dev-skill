# CBC Coordinator: native-agent pilot (not the final autonomous runner)

## What was learned from existing systems

- OpenCode's native primary/subagents and Task tool support per-role prompts and permissions without installing another orchestration platform.
- Claude Code Agent Teams demonstrate lead/teammate separation, a shared task ledger and direct messaging, but have documented process/resume limitations.
- OpenCode Ensemble demonstrates session-isolated teammates, task dependencies, worktrees, status tracking and crash recovery. It is a reference, not a dependency.
- OpenCode Swarm demonstrates architect-led gated code review, independent tests and persistent evidence. It is a reference, not a dependency.
- OpenCode fallback plugins demonstrate provider cooldown and multi-model retry; naive last-message replay can re-run partially completed tool effects.

References:
- https://opencode.ai/docs/agents/
- https://code.claude.com/docs/en/agent-teams
- https://github.com/hueyexe/opencode-ensemble
- https://github.com/ZaxbyHub/opencode-swarm
- https://github.com/Sharper-Flow/opencode-model-routing
- https://opencode.ai/docs/sdk/

## Phase 1: what is committed NOW

`/cbc-team <task>` uses `cbc-coordinator`, with five native OpenCode subagents: planner, coder, reviewer, qa, debugger. The coordinator chooses which to call. In a small task it can skip specialist overhead. All role definitions are in `.opencode/agents/`.

They provide **role delegation and review instructions**, not a background daemon, live model scoring, provider switching, shared task database, enforced deadline, or automatic resumption. No provider settings are modified. OpenCode itself must be running to invoke agents.

## Phase 2: coordinator-controlled model trials (NOT IMPLEMENTED)

A small service using the OpenCode SDK should evaluate candidate models in isolated sessions on a handful of deterministic read-only and controlled coding fixtures:
- Preflight OpenCode server/session readiness and provider reachability before model tests. A subprocess timeout is ambiguous, not proof the model is bad.
- Separate checks: connection response; tool calling; correctness on a tiny fixture with real independent tests; time to first token; error class and quotas.
- Track model identity, provider, fixture version, test receipts, latency and token usage locally. Never record API keys, code from private tasks, or raw credentials.
- Rank by **verified pass rate within task category**, reliability, time/token efficiency and recent failures. Prefer the smallest suitable active model, with bound concurrency and usage budget.
- Fail over on retryable provider failures, not coding errors. Before retry, compare git state and recorded tool side effects; use a new model/session with a concise explicit handoff to avoid replaying edits.

## Phase 3: durable execution (NOT IMPLEMENTED)

Use SQLite TaskState with a task ID, source revision, acceptance criteria, stage, model, working branch, dirty-file list, tested evidence, start/deadline, cost, and next instruction. Use atomic checkpoints and one writer per overlapping scope. A separate supervisor enforces the requested 2-hour wall-clock deadline, cancels active sessions, waits for safe shutdown, then marks COMPLETED, PAUSED or BLOCKED. A resume command must verify HEAD, diff and test freshness before acting. No auto-merge or production deploy.

## Operator guidance

Install this kit only into an isolated development copy (the installer deliberately rejects conflicts). Do not install third-party plugins on the production runtime based solely on README claims. Test CBC agents with a non-production repo first and capture at least one real task with a failing regression before promoting any model as reliable.

Live account credentials and model free-tier status remain the operator's responsibility. No model is considered verified for autonomy merely because it appears in `opencode models` or replies to a probe.
