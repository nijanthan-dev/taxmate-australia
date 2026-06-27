#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "error: gitleaks required for full check" >&2
  exit 1
fi

bash scripts/codex-env-setup.sh
bash scripts/check-publication-ready.sh
gitleaks detect --source . --redact --no-banner
