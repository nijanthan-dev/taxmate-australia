#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUIRE_CODEX="${TAXMATE_REQUIRE_CODEX_PLUGIN_SMOKE:-0}"
if ! command -v codex >/dev/null 2>&1; then
  if [[ "$REQUIRE_CODEX" == "1" ]]; then
    echo "error: codex CLI is required for plugin install smoke test" >&2
    exit 1
  fi
  echo "codex CLI not found; skipping plugin install smoke test"
  exit 0
fi

TMP_HOME="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-codex-home.XXXXXX")"
TMP_OUT="$(mktemp -d "${TMPDIR:-/tmp}/taxmate-codex-out.XXXXXX")"
cleanup() {
  rm -rf "$TMP_HOME" "$TMP_OUT"
}
trap cleanup EXIT

MARKETPLACE_JSON="$TMP_OUT/marketplace.json"
INSTALL_JSON="$TMP_OUT/install.json"
ANSWERS_JSON="$TMP_OUT/answers.json"
GUIDE_HTML="$TMP_OUT/guide.html"

CODEX_HOME="$TMP_HOME" codex plugin marketplace add "$ROOT" --json >"$MARKETPLACE_JSON"
MARKETPLACE_NAME="$(node -e "console.log(require(process.argv[1]).marketplaceName)" "$MARKETPLACE_JSON")"
if [[ -z "$MARKETPLACE_NAME" ]]; then
  echo "error: marketplace add did not return marketplaceName" >&2
  exit 1
fi

CODEX_HOME="$TMP_HOME" codex plugin add "taxmate-australia@$MARKETPLACE_NAME" --json >"$INSTALL_JSON"
INSTALLED_PATH="$(node -e "console.log(require(process.argv[1]).installedPath)" "$INSTALL_JSON")"
if [[ -z "$INSTALLED_PATH" || ! -d "$INSTALLED_PATH" ]]; then
  echo "error: plugin add did not return installedPath" >&2
  exit 1
fi

for rel in \
  ".codex-plugin/plugin.json" \
  ".codex-plugin/mcp.json" \
  "mcp/server.cjs" \
  "scripts/taxmate" \
  "scripts/taxmate.py" \
  "scripts/taxmate_intake.py" \
  "runtime/skills/research/SKILL.md" \
  "wrappers/taxmate-australia/SKILL.md"; do
  if [[ ! -e "$INSTALLED_PATH/$rel" ]]; then
    echo "error: installed plugin missing $rel" >&2
    exit 1
  fi
done

if [[ -e "$INSTALLED_PATH/.mcp.json" ]]; then
  echo "error: installed plugin must not include root .mcp.json" >&2
  exit 1
fi

bash "$ROOT/scripts/test-mcp-server.sh" "$INSTALLED_PATH"

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

echo "Codex plugin install smoke test passed"
