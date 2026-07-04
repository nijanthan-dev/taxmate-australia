#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_SKILLS_DIR="$ROOT/local-skills"
CONFIG_PATH="$ROOT/config/public-skills.json"
TARGET_AGENT="codex"
REQUESTED_SKILLS=()

if ! command -v npx >/dev/null 2>&1; then
  echo "error: npx missing; install Node.js/npm first" >&2
  exit 1
fi

if [[ -f "$CONFIG_PATH" ]]; then
  SKILLS_CLI_VERSION="$(node -e "console.log(require('$CONFIG_PATH').skillsCliVersion || '1.5.13')")"
else
  SKILLS_CLI_VERSION="1.5.13"
fi
SKILLS=(npx --yes "skills@${SKILLS_CLI_VERSION}")

install_skill() {
  local skill_dir="$1"
  local skill_name
  skill_name="$(basename "$skill_dir")"

  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    echo "skip: $skill_name (missing SKILL.md)"
    return
  fi

  echo "installing local skill: $skill_name"
  if [[ "$TARGET_AGENT" == "none" ]]; then
    "${SKILLS[@]}" add "$skill_dir" --global --yes
  else
    "${SKILLS[@]}" add "$skill_dir" --agent "$TARGET_AGENT" --global --yes
  fi
}

if [[ ! -d "$LOCAL_SKILLS_DIR" ]]; then
  echo "error: local skill folder missing: $LOCAL_SKILLS_DIR" >&2
  exit 1
fi

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --agent)
      [[ "${2:-}" == "" ]] && { echo "error: --agent requires a value" >&2; exit 1; }
      TARGET_AGENT="$2"
      shift 2
      ;;
    --help|-h)
      echo "usage: install-local-skills.sh [--agent <agent>] [skill-name ...]"
      echo "  --agent: codex | claude-code | none (default: codex)"
      exit 0
      ;;
    --*)
      echo "error: unknown option $1" >&2
      echo "usage: install-local-skills.sh [--agent <agent>] [skill-name ...]" >&2
      exit 1
      ;;
    *)
      REQUESTED_SKILLS=("${REQUESTED_SKILLS[@]}" "$1")
      shift
      ;;
  esac
done

if [[ "$TARGET_AGENT" == "claude" ]]; then
  TARGET_AGENT="claude-code"
fi

if [[ "${#REQUESTED_SKILLS[@]}" -eq 0 ]]; then
  for skill_dir in "$LOCAL_SKILLS_DIR"/*; do
    [[ -d "$skill_dir" ]] || continue
    install_skill "$skill_dir"
  done
else
  for requested in "${REQUESTED_SKILLS[@]}"; do
    install_skill "$LOCAL_SKILLS_DIR/$requested"
  done
fi
