#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
mkdir -p "$TMP/project" "$TMP/existing/.opencode/skills/cbc-learning"
echo 'keep my V2' > "$TMP/existing/.opencode/skills/cbc-learning/SKILL.md"
# Conflicts must leave no partial installation.
if sh "$ROOT/install.sh" "$TMP/existing"; then echo "FAIL: overwrote V2" >&2; exit 1; fi
test ! -e "$TMP/existing/.opencode/scripts/cbc_learning_v3.py"
test -f "$TMP/existing/.opencode/skills/cbc-learning/SKILL.md"
sh "$ROOT/install.sh" "$TMP/project"
test -f "$TMP/project/.opencode/scripts/cbc_learning_v3.py"
test -f "$TMP/project/.opencode/skills/cbc-learning/SKILL.md"
# After Python tests, __pycache__ may exist in the source; it must never be installed.
if find "$TMP/project/.opencode" -type f \( -name '*.pyc' -o -name '*.pyo' \) | grep -q .; then
    echo "FAIL: installer copied runtime Python bytecode" >&2
    exit 1
fi
test ! -e "$TMP/project/.opencode/scripts/__pycache__"
mkdir -p "$TMP/project/.opencode/task-state/learning-v3"
echo 'PERSONAL LESSON' > "$TMP/project/.opencode/task-state/learning-v3/personal.json"
echo '# private change' >> "$TMP/project/.opencode/commands/cbc-dev.md"
sh "$ROOT/uninstall.sh" "$TMP/project"
test ! -e "$TMP/project/.opencode/scripts/cbc_learning_v3.py"
test -f "$TMP/project/.opencode/commands/cbc-dev.md"
test -f "$TMP/project/.opencode/task-state/learning-v3/personal.json"
echo "INSTALLER_SMOKE_OK"
