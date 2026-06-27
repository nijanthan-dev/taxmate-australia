#!/usr/bin/env bash
set -euo pipefail

ROOT="${TAXMATE_AUSTRALIA_ROOT:-}"
if [[ -z "$ROOT" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

case "$ROOT" in
  /*) ;;
  *) echo "error: root must be absolute" >&2; exit 1 ;;
esac

if [[ ! -f "$ROOT/.codex-plugin/plugin.json" ]]; then
  echo "error: refusing cleanup outside TaxMate Australia plugin root" >&2
  exit 1
fi

CACHE_DIR="$ROOT/.cache/ato"
if [[ "$CACHE_DIR" != "$ROOT/.cache/ato" ]]; then
  echo "error: refusing unexpected cache path" >&2
  exit 1
fi

rm -rf "$CACHE_DIR"
