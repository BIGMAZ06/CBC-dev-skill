#!/bin/sh
# Install project-local CBC V3 without overwriting an existing kit/V2.
set -eu
[ "$#" -eq 1 ] || { echo "Usage: sh install.sh /path/to/target-project" >&2; exit 2; }
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
TARGET=$1
[ -d "$TARGET" ] || { echo "Target project directory missing: $TARGET" >&2; exit 2; }
FILES=$(mktemp)
trap 'rm -f "$FILES"' EXIT HUP INT TERM
(cd "$ROOT" && find .opencode -type d \( -name task-state -o -name __pycache__ -o -name node_modules \) -prune -o -type f ! -name '*.pyc' ! -name '*.pyo' -print | sort) > "$FILES"
# Atomic-ish preflight: all conflicts checked before the first copy.
while IFS= read -r relative; do
    if [ -e "$TARGET/$relative" ]; then
        echo "CONFLICT: $TARGET/$relative (preserved; nothing installed)" >&2
        exit 1
    fi
done < "$FILES"
while IFS= read -r relative; do
    mkdir -p "$(dirname "$TARGET/$relative")"
    cp "$ROOT/$relative" "$TARGET/$relative"
done < "$FILES"
if [ -e "$TARGET/AGENTS.md" ]; then
    echo "Existing AGENTS.md left unchanged. Manually integrate V3 guidance if desired."
else
    cp "$ROOT/AGENTS.md" "$TARGET/AGENTS.md"
fi
echo "CBC Learning V3 installed. Memory remains LOCAL; V2 data was not read or changed."
