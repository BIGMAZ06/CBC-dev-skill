# CBC Dev Skill — repository guidance

Keep changes project-scoped; inspect → plan → implement → run authorized checks → report actual outcome. This repository is an OpenCode toolkit, **not** CBC production. No deployments, provider-key changes, credential access, or execution of untrusted commands without explicit approval.

CBC Learning V3 stores experience locally under ignored `.opencode/task-state/learning-v3/`, runs no AI/network calls, and never automatically approves/publishes learning. Never expose secrets or place private conversations, source code or raw logs in memory. Human review is required for test execution, lesson approval and skill publishing. Do not assume a successful subprocess exit proves the target behavior unless the preset tests that behavior. Preserve V2 and existing memory until users explicitly perform reviewed migration.
