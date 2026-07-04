#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-local-skills.XXXXXX")"
TMP_BIN="$TMP_DIR/bin"
NPX_LOG="$TMP_DIR/npx.log"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

fail() {
  echo "error: $*" >&2
  exit 1
}

mkdir -p "$TMP_BIN"
cat >"$TMP_BIN/npx" <<'SH'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$NPX_LOG"
SH
chmod +x "$TMP_BIN/npx"

PATH="$TMP_BIN:$PATH" NPX_LOG="$NPX_LOG" bash scripts/install-local-skills.sh \
  taxmate-release-closeout \
  --agent claude \
  codex-simplify

grep -q -- 'skills@1.5.13 add .*/local-skills/taxmate-release-closeout --agent claude-code --global --yes' "$NPX_LOG" || {
  cat "$NPX_LOG" >&2
  fail "taxmate-release-closeout did not use claude-code"
}

grep -q -- 'skills@1.5.13 add .*/local-skills/codex-simplify --agent claude-code --global --yes' "$NPX_LOG" || {
  cat "$NPX_LOG" >&2
  fail "codex-simplify did not use claude-code"
}

echo "local skills install test passed"
