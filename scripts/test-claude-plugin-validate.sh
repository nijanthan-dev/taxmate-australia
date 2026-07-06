#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REQUIRE_CLAUDE="${TAXMATE_REQUIRE_CLAUDE_PLUGIN_VALIDATE:-0}"
if ! command -v claude >/dev/null 2>&1; then
  if [[ "$REQUIRE_CLAUDE" == "1" ]]; then
    echo "error: Claude Code CLI is required for plugin validation" >&2
    exit 1
  fi
  echo "Claude Code CLI not found; skipping Claude plugin validation"
  exit 0
fi

claude plugin validate --strict "$ROOT"

echo "Claude plugin validation passed"
