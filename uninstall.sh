#!/bin/sh
# Delete only pristine files originating from this package; preserve state.
set -eu
[ "$#" -eq 1 ] || { echo "Usage: sh uninstall.sh /path/to/target-project" >&2; exit 2; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET=$1
[ -d "$TARGET" ] || { echo "Target project directory missing" >&2; exit 2; }
(cd "$ROOT" && find .opencode -type d \( -name task-state -o -name __pycache__ -o -name node_modules \) -prune -o -type f ! -name '*.pyc' ! -name '*.pyo' -print | sort) |
while IFS= read -r relative; do
    if [ -f "$TARGET/$relative" ] && cmp -s "$ROOT/$relative" "$TARGET/$relative"; then
        rm "$TARGET/$relative"
        echo "Removed unchanged: $relative"
    elif [ -e "$TARGET/$relative" ]; then
        echo "Preserved modified: $relative"
    fi
done
if [ -f "$TARGET/AGENTS.md" ] && cmp -s "$ROOT/AGENTS.md" "$TARGET/AGENTS.md"; then
    rm "$TARGET/AGENTS.md"
fi
echo "Finished. Private .opencode/task-state/ data preserved."
