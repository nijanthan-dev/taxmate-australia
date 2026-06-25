#!/usr/bin/env bash
set -euo pipefail

echo "Checking dev environment..."
go version
node --version
npm --version
git --version
curl --version

mkdir -p .cache/gocache .cache/gomod

if [ -f go.mod ]; then
  go mod download
else
  echo "No go.mod found; skipping go mod download."
fi

echo "Env bootstrap includes no full build by default; run full checks from docs before coding."

if command -v codex >/dev/null; then
  echo "Codex CLI: available"
else
  echo "Codex CLI not found; install via your normal path if you need in-container usage."
fi

echo "Dev environment bootstrap complete."
