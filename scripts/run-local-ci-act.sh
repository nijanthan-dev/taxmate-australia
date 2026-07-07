#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v act >/dev/null 2>&1; then
  echo "error: act is required. Install with: brew install act" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "error: Docker must be running for act" >&2
  exit 1
fi

bash scripts/check-local-ci-ready.sh
act workflow_dispatch -W .github/workflows/local-ci.yml

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks dir . --redact --no-banner
  gitleaks detect --source . --redact --no-banner
else
  echo "warning: gitleaks not found; run secret scans before merge" >&2
fi
