#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SKILLS_CLI_VERSION="$(node -e "console.log(require('./config/public-skills.json').skillsCliVersion)")"
SKILLS=(npx --yes "skills@${SKILLS_CLI_VERSION}")
TMP_HOME="$(mktemp -d)"
TMP_PROJECT="$(mktemp -d)"
LIST_OUT="$TMP_PROJECT/list.txt"
LIST_JSON="$TMP_PROJECT/list.json"
USE_OUT="$TMP_PROJECT/use.txt"

cleanup() {
  rm -rf "$TMP_HOME" "$TMP_PROJECT"
}
trap cleanup EXIT

fail() {
  echo "error: $*" >&2
  exit 1
}

HOME="$TMP_HOME" "${SKILLS[@]}" add "$ROOT" --list >"$LIST_OUT"

node - "$LIST_OUT" "$ROOT/config/public-skills.json" <<'NODE'
const fs = require("fs");
const listPath = process.argv[2];
const manifestPath = process.argv[3];
const text = fs.readFileSync(listPath, "utf8").replace(/\x1b\[[0-9;?]*[A-Za-z]/g, "");
const expected = JSON.parse(fs.readFileSync(manifestPath, "utf8")).portableSkills;
const found = [...text.matchAll(/^│ {4}([a-z0-9][a-z0-9-]*)$/gm)].map((m) => m[1]).sort();
const exp = [...expected].sort();
const missing = exp.filter((name) => !found.includes(name));
const extra = found.filter((name) => !exp.includes(name));
if (missing.length || extra.length) {
  console.error(JSON.stringify({ missing, extra }, null, 2));
  process.exit(1);
}
NODE

HOME="$TMP_HOME" "${SKILLS[@]}" add "$ROOT" --skill "*" --agent codex --global --yes --copy
HOME="$TMP_HOME" "${SKILLS[@]}" list --agent codex --global --json >"$LIST_JSON"

node - "$LIST_JSON" "$ROOT/config/public-skills.json" "$TMP_HOME/.agents/skills" <<'NODE'
const fs = require("fs");
const path = require("path");
const listPath = process.argv[2];
const manifestPath = process.argv[3];
const installRoot = process.argv[4];
const expected = JSON.parse(fs.readFileSync(manifestPath, "utf8")).portableSkills.sort();
const listed = JSON.parse(fs.readFileSync(listPath, "utf8"));
const names = listed.map((item) => item.name).sort();
const missing = expected.filter((name) => !names.includes(name));
const extra = names.filter((name) => !expected.includes(name));
if (missing.length || extra.length) {
  console.error(JSON.stringify({ missing, extra }, null, 2));
  process.exit(1);
}
for (const name of expected) {
  const skillDir = path.join(installRoot, name);
  const skillPath = path.join(skillDir, "SKILL.md");
  if (!fs.existsSync(skillPath)) throw new Error(`missing ${skillPath}`);
  const body = fs.readFileSync(skillPath, "utf8");
  if (!body.startsWith("---\n")) throw new Error(`missing frontmatter: ${name}`);
  const end = body.indexOf("\n---", 4);
  if (end < 0) throw new Error(`invalid frontmatter: ${name}`);
  if (!new RegExp(`^name:\\s*${name}$`, "m").test(body.slice(0, end))) throw new Error(`frontmatter name mismatch: ${name}`);
  if (/(TAXMATE_AUSTRALIA_ROOT|bin\/taxmate-australia-|cmd\/|internal\/|data\/ato_knowledge_base|\.codex-plugin|\$taxmate-australia:|taxmate-australia-(skills|refresh|finance|calc|validate))/.test(body)) {
    throw new Error(`repository dependency in ${name}`);
  }
  const refs = [...body.matchAll(/`([^`\n]+)`/g)].map((m) => m[1]).filter((p) => p.startsWith("references/"));
  for (const ref of refs) {
    if (!fs.existsSync(path.join(skillDir, ref))) throw new Error(`missing reference ${name}/${ref}`);
  }
}
NODE

for dir in "$TMP_HOME/.agents/skills"/*; do
  [[ -d "$dir" ]] || continue
  if grep -R -nE 'TAXMATE_AUSTRALIA_ROOT|bin/taxmate-australia-|cmd/|internal/|data/ato_knowledge_base|\.codex-plugin|\$taxmate-australia:|taxmate-australia-(skills|refresh|finance|calc|validate)' "$dir"; then
    fail "installed public skill references repository runtime"
  fi
  if grep -R -n 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' "$dir"; then
    fail "empty-content provenance found in installed public skill"
  fi
done

test -f "$TMP_HOME/.agents/skills/taxmate-australia/SKILL.md"
HOME="$TMP_HOME" "${SKILLS[@]}" use "$ROOT" --skill taxmate-australia-capital-gains-tax >"$USE_OUT"
grep -q "TaxMate Australia Capital Gains Tax" "$USE_OUT" || fail "skills use did not render taxmate-australia-capital-gains-tax"

echo "skills install smoke test passed"
