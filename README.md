# CBC Dev Skill — CBC Learning V3

A lightweight, **project-local OpenCode skill toolkit** with evidence-gated learning. Open-source Python standard library only: no model training, no background daemon, no secret collection, and **zero extra AI-provider calls** by the learning engine.

> Status: V3 development prototype. Do not activate in a live CBC project until tests, review and migration dry-run are complete.

## Architecture

```
Task → scoped inspection → manual pending episode
                       → user-authorized test (exit code + SHA256 receipt)
                       → human review → approved verified SQLite memory
                       → bounded relevant recall (up to 5)
                       → helpful/harmful feedback
                       → 3 distinct verified tasks → inert candidate version
                       → paired baseline/candidate test evaluations
                       → human-reviewed publish → versioned rollback
```

**Key restrictions:** Failing experiments are recorded but not automatically recalled as trusted instructions. A text note or formatting-only test does not verify a coding fix. A human must review the actual test output, approve the lesson and approve publication. These are workflow gates: a command-line `--confirm` flag cannot authenticate a person. Do not let an AI invoke human-only confirmation flags.

## Install (development project only)

```sh
git clone https://github.com/BIGMAZ06/CBC-dev-skill.git
cd CBC-dev-skill
# From a branch with V3, run:
sh install.sh /path/to/isolated-test-project
```

The installer **refuses to overwrite** existing .opencode files, including V2. It never copies or touches `.opencode/task-state/`, global configuration, providers, credentials or CBC production. Stop and manually plan a staged upgrade if any conflict appears. `sh uninstall.sh /path/to/project` removes only unchanged kit files and preserves private memories.

## Quick CLI example

Run commands **from the project root**. All state is stored in `.opencode/task-state/learning-v3/learning.sqlite3` (ignored by Git). Optionally set `CBC_LEARNING_HOME` to another private directory for tests/backups.

```sh
PY=python3
LOOP=.opencode/scripts/cbc_learning_v3.py
$PY "$LOOP" status
$PY "$LOOP" record --project CBC --pattern nextjs-preview \
  --task 'Fix sandbox preview' --outcome success \
  --problem 'Preview route fails after import' \
  --lesson 'Verify compiled route within the sandbox before changing global config' \
  --evidence 'Local regression noted; independent test pending'
# Save the returned pending ID; actual testing is opt-in and executes project code:
$PY "$LOOP" verify --id PENDING_ID --preset python-unittest --confirm-run
# Only after human inspection of the actual test results:
$PY "$LOOP" review --id PENDING_ID --decision approve --confirm
$PY "$LOOP" recall --project CBC --query 'nextjs preview' --limit 3
$PY "$LOOP" feedback --id PENDING_ID --outcome helpful \
  --evidence 'Verified during later preview regression'
```

Built-in test presets (subprocess execution without shell expansion):
- `python-unittest` — `python3 -m unittest discover -s tests -p test_*.py -v`
- `npm-test` — `npm test`
- `git-diff-check` — `git diff --check` (supplemental only, **not** behavioral verification).

Tests may run untrusted project code, access local files, or call networks through the project's own scripts. Run only after reviewing the project and granting permission. The engine itself has no network client or third-party packages.

## Skill evolution and rollback

After **three distinct approved and behaviorally verified tasks** in the same pattern:
```sh
python3 .opencode/scripts/cbc_learning_v3.py draft --project CBC --pattern nextjs-preview
# Returns a candidate ID; nothing is installed automatically.
python3 .opencode/scripts/cbc_learning_v3.py evaluate --candidate CANDIDATE_ID \
  --variant baseline --case-id case-one --preset python-unittest --confirm-run
python3 .opencode/scripts/cbc_learning_v3.py evaluate --candidate CANDIDATE_ID \
  --variant candidate --case-id case-one --preset python-unittest --confirm-run
# Repeat on two more genuinely distinct cases with the same named preset.
python3 .opencode/scripts/cbc_learning_v3.py compare --candidate CANDIDATE_ID
# Human-only, after checking meaningful test reports and candidate content:
python3 .opencode/scripts/cbc_learning_v3.py publish --candidate CANDIDATE_ID --confirm
# Previous active skill version can later be restored:
python3 .opencode/scripts/cbc_learning_v3.py rollback --candidate PRIOR_ACTIVE_ID --confirm
```

The comparison gate requires 3 paired cases, at least one improvement, no regressions, and all 3 candidate cases passing. **These checks alone cannot demonstrate that a generated agent skill is better at reasoning:** use actual coding tasks, controlled baselines, code review and real regression tests. Evaluation records store exit codes and output digests, not full stdout/stderr. Publishing changes only `.opencode/skills/cbc-adaptive-{pattern}/SKILL.md`; existing unowned or externally edited files cannot be overwritten.

## Safe import from legacy V2 / memory JSON

```sh
python3 .opencode/scripts/cbc_learning_v3.py migrate --file /path/to/legacy.json
# Preview counts first. This is deliberate and never automatic:
python3 .opencode/scripts/cbc_learning_v3.py migrate --file /path/to/legacy.json --apply --confirm
```

Accepts bounded JSON arrays, or objects with `lessons`, `entries`, or `records` arrays. Unknown and unsafe records are skipped. **Every imported record stays pending and unverified**, regardless of legacy status. The source file is unchanged. The format is deliberately conservative; different V2 schemas may need an explicit reviewed converter, not assumptions.

## Verification

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
sh tests/test_installer.sh
```

The CI workflow runs the tests and checks that runtime memory isn't committed. No token saving or quality improvement is guaranteed: compare tokens and *verified* outcomes per task, not token counts alone.

License: this new V3 toolkit is intended for permissive open source; add an explicit license before distributing copies outside the repository.
