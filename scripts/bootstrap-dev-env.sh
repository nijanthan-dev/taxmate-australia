#!/usr/bin/env bash
set -euo pipefail

say() {
  printf '%s\n' "$1"
}

require_command() {
  local tool="$1"
  local path

  path="$(command -v "$tool" || true)"
  if [ -z "$path" ]; then
    say "$tool missing; install required local tooling and rerun."
    return 1
  fi

  say "$tool: $path"
}

print_version() {
  local tool="$1"
  case "$tool" in
    node|npm)
      "$tool" --version
      ;;
    python3|python)
      "$tool" --version | head -n 1
      ;;
    *)
      "$tool" --version | head -n 1
      ;;
  esac
}

strip_version_suffix() {
  printf '%s' "$1" | sed -E 's/[^0-9.].*$//'
}

version_ge() {
  local actual="$1"
  local minimum="$2"
  local actual_major actual_minor actual_patch
  local min_major min_minor min_patch

  IFS='.' read -r actual_major actual_minor actual_patch <<<"$(strip_version_suffix "$actual")"
  IFS='.' read -r min_major min_minor min_patch <<<"$(strip_version_suffix "$minimum")"

  actual_major=${actual_major:-0}
  actual_minor=${actual_minor:-0}
  actual_patch=${actual_patch:-0}
  min_major=${min_major:-0}
  min_minor=${min_minor:-0}
  min_patch=${min_patch:-0}

  if [ "$actual_major" -gt "$min_major" ]; then
    return 0
  fi
  if [ "$actual_major" -lt "$min_major" ]; then
    return 1
  fi
  if [ "$actual_minor" -gt "$min_minor" ]; then
    return 0
  fi
  if [ "$actual_minor" -lt "$min_minor" ]; then
    return 1
  fi
  [ "$actual_patch" -ge "$min_patch" ]
}

assert_minimum_versions() {
  local node_version python_version

  node_version="$(node --version)"
  node_version="${node_version#v}"
  if ! version_ge "$node_version" "20"; then
    say "Node.js 20+ required; detected $node_version"
    return 1
  fi

  python_version="$(python3 --version 2>&1 | sed 's/^Python //')"
  if ! version_ge "$python_version" "3.9"; then
    say "Python 3.9+ required; detected $python_version"
    return 1
  fi
}

say "Checking dev environment..."

for tool in python3 node npm git curl jq; do
  require_command "$tool"
done

for tool in python3 node npm git curl; do
  print_version "$tool"
done

assert_minimum_versions
mkdir -p .cache/ato

if command -v codex >/dev/null 2>&1; then
  say "Codex CLI: available"
else
  say "Codex CLI not found; install it manually if you need workspace CLI usage."
fi

say "Env bootstrap includes no full build by default; run full checks from docs before coding."
say "Dev environment bootstrap complete."
