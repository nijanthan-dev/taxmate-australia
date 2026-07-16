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
grep -qx 'name: TaxMate Australia Local CI' .github/workflows/local-ci.yml || fail "local workflow must use TaxMate-specific name"
grep -qx '    name: TaxMate Australia Local CI' .github/workflows/local-ci.yml || fail "local job must use TaxMate-specific name"
grep -q "workflow_dispatch:" .github/workflows/ci.yml || fail "CI must stay manually runnable"
grep -q "workflow_dispatch:" .github/workflows/hol-plugin-scanner.yml || fail "HOL scanner must stay manually runnable"
if grep -Eq "^[[:space:]]*(pull_request|push):" .github/workflows/ci.yml; then
  fail "hosted CI must not run automatically"
fi
if grep -Eq "^[[:space:]]*(pull_request|push):" .github/workflows/local-ci.yml; then
  fail "local act workflow must not run automatically on GitHub"
fi
grep -Eq "^[[:space:]]*push:" .github/workflows/release.yml || fail "Release must run from main pushes"
grep -q "branches: \\[main\\]" .github/workflows/release.yml || fail "Release push trigger must target main"
if grep -Eq "workflow_run:|Require green CI|--workflow CI" .github/workflows/release.yml; then
  fail "Release must not depend on hosted CI"
fi

grep -q "bash scripts/check-publication-ready.sh" .github/workflows/local-ci.yml || fail "local act workflow must run publication guardrails"
grep -q "./scripts/taxmate review-guardrails" .github/workflows/local-ci.yml || fail "local act workflow must run review guardrails"
grep -q "bash scripts/test-mcp-server.sh" .github/workflows/local-ci.yml || fail "local act workflow must smoke MCP server"

echo "Local CI act config ready"
