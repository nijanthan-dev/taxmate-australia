#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUIRE_CLAUDE="${TAXMATE_REQUIRE_CLAUDE_PLUGIN_SMOKE:-0}"
if ! command -v claude >/dev/null 2>&1; then
  if [[ "$REQUIRE_CLAUDE" == "1" ]]; then
    echo "error: Claude Code CLI is required for plugin install smoke test" >&2
    exit 1
  fi
  echo "Claude Code CLI not found; skipping plugin install smoke test"
  exit 0
fi

TMP_HOME="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-claude-home.XXXXXX")"
TMP_OUT="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-claude-out.XXXXXX")"
cleanup() {
  rm -rf "$TMP_HOME" "$TMP_OUT"
}
trap cleanup EXIT

HOME="$TMP_HOME" claude plugin marketplace add "$ROOT" >/dev/null
HOME="$TMP_HOME" claude plugin install taxmate-australia@taxmate-australia >/dev/null

INSTALLED_PATH="$(
  find "$TMP_HOME/.claude/plugins/cache/taxmate-australia/taxmate-australia" -mindepth 1 -maxdepth 1 -type d 2>/dev/null \
    | sort \
    | tail -1 \
    || true
)"
if [[ -z "$INSTALLED_PATH" || ! -d "$INSTALLED_PATH" ]]; then
  echo "error: Claude plugin cache path not found" >&2
  exit 1
fi

for rel in \
  ".claude-plugin/plugin.json" \
  ".claude-plugin/marketplace.json" \
  ".codex-plugin/plugin.json" \
  ".mcp.json" \
  "mcp/server.cjs" \
  "scripts/taxmate" \
  "scripts/taxmate.py" \
  "scripts/taxmate_intake.py" \
  "runtime/skills/research/SKILL.md" \
  "runtime/skills/finance-review/SKILL.md" \
  "runtime/skills/calculators/SKILL.md" \
  "wrappers/taxmate-australia/SKILL.md" \
  "wrappers/taxmate-australia-taxpack/SKILL.md" \
  "skills/taxmate-australia/SKILL.md" \
  "skills/individual-return/SKILL.md"; do
  if [[ ! -e "$INSTALLED_PATH/$rel" ]]; then
    echo "error: installed Claude plugin missing $rel" >&2
    exit 1
  fi
done

if [[ -e "$INSTALLED_PATH/.codex-plugin/mcp.json" ]]; then
  echo "error: installed Claude plugin must not include stale .codex-plugin/mcp.json" >&2
  exit 1
fi

bash "$ROOT/scripts/test-mcp-server.sh" "$INSTALLED_PATH"

ANSWERS_JSON="$TMP_OUT/answers.json"
GUIDE_HTML="$TMP_OUT/guide.html"
"$INSTALLED_PATH/scripts/taxmate" intake sample-json --output "$ANSWERS_JSON"
"$INSTALLED_PATH/scripts/taxmate" intake individual --answers "$ANSWERS_JSON" --output "$GUIDE_HTML"

grep -q "Self-prepared HTML guide" "$GUIDE_HTML" || {
  echo "error: generated HTML missing guide title" >&2
  exit 1
}
grep -q "Accountant review" "$GUIDE_HTML" || {
  echo "error: generated HTML missing accountant review marker" >&2
  exit 1
}
grep -q "Manual copy only" "$GUIDE_HTML" || {
  echo "error: generated HTML missing manual copy marker" >&2
  exit 1
}

echo "Claude plugin install smoke test passed"
