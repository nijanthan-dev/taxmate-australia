#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP_PARENT="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-codex-setup.XXXXXX")"
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

before_status="$(git -C "$WORKTREE" status --short --untracked-files=all)"
bash "$WORKTREE/scripts/codex-env-setup.sh" >/dev/null

if find "$WORKTREE/scripts" -type d -name '__pycache__' | grep -q .; then
  echo "error: setup wrote Python bytecode cache" >&2
  exit 1
fi

status="$(git -C "$WORKTREE" status --short --untracked-files=all)"
[[ "$status" == "$before_status" ]] || {
  echo "error: setup dirtied worktree" >&2
  echo "$status" >&2
  exit 1
}

echo "codex env setup clean-worktree test passed"
