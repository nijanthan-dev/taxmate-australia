#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "error: $*" >&2
  exit 1
}

[[ -f .actrc ]] || fail "missing .actrc"
[[ -f .github/workflows/local-ci.yml ]] || fail "missing local act workflow"
[[ -f scripts/run-local-ci-act.sh ]] || fail "missing local act runner"

grep -q "catthehacker/ubuntu:act-22.04" .actrc || fail ".actrc must pin the local act image"
grep -q "workflow_dispatch:" .github/workflows/ci.yml || fail "CI must stay manually runnable"
grep -q "workflow_dispatch:" .github/workflows/hol-plugin-scanner.yml || fail "HOL scanner must stay manually runnable"

if grep -Eq "^[[:space:]]*(pull_request|push):" .github/workflows/ci.yml; then
  fail "CI automatic pull_request/push triggers are paused; use scripts/run-local-ci-act.sh"
fi
if grep -Eq "^[[:space:]]*(pull_request|push):" .github/workflows/hol-plugin-scanner.yml; then
  fail "HOL scanner automatic pull_request/push triggers are paused"
fi

grep -q "bash scripts/check-publication-ready.sh" .github/workflows/local-ci.yml || fail "local act workflow must run publication guardrails"
grep -q "./scripts/taxmate review-guardrails" .github/workflows/local-ci.yml || fail "local act workflow must run review guardrails"
grep -q "bash scripts/test-mcp-server.sh" .github/workflows/local-ci.yml || fail "local act workflow must smoke MCP server"

echo "Local CI act config ready"
