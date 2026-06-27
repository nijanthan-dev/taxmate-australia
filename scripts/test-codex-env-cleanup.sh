#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-codex-cleanup.XXXXXX")"
WORKTREE="$TMP_PARENT/worktree"

cleanup() {
  git worktree remove --force "$WORKTREE" >/dev/null 2>&1 || true
  rm -rf "$TMP_PARENT"
}
trap cleanup EXIT

git worktree add --detach "$WORKTREE" HEAD >/dev/null
[[ -f "$WORKTREE/.git" ]] || {
  echo "error: expected linked worktree .git file" >&2
  exit 1
}
if ! git diff --quiet HEAD -- .; then
  git diff --binary HEAD -- . | git -C "$WORKTREE" apply
fi

mkdir -p \
  "$WORKTREE/.tmp" \
  "$WORKTREE/.pytest_cache" \
  "$WORKTREE/scripts/__pycache__"
touch \
  "$WORKTREE/.coverage" \
  "$WORKTREE/.tmp/generated" \
  "$WORKTREE/.pytest_cache/generated" \
  "$WORKTREE/scripts/__pycache__/generated.pyc"

TAXMATE_AUSTRALIA_ROOT="$WORKTREE" bash "$ROOT/scripts/codex-env-cleanup.sh" >/dev/null

for path in \
  "$WORKTREE/.coverage" \
  "$WORKTREE/.tmp" \
  "$WORKTREE/.pytest_cache" \
  "$WORKTREE/scripts/__pycache__"; do
  [[ ! -e "$path" ]] || {
    echo "error: cleanup left $path" >&2
    exit 1
  }
done

echo "codex env cleanup worktree test passed"
