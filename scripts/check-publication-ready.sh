#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$ROOT/.cache}"

fail() {
  echo "error: $*" >&2
  exit 1
}

[[ -f .codex-plugin/plugin.json ]] || fail "missing plugin manifest"
[[ -f README.md ]] || fail "missing README"
[[ -f DISCLAIMER.md ]] || fail "missing DISCLAIMER.md"
[[ -f LICENSE ]] || fail "missing LICENSE"
[[ -f SECURITY.md ]] || fail "missing SECURITY.md"
[[ -f CONTRIBUTING.md ]] || fail "missing CONTRIBUTING.md"
[[ -f docs/PUBLICATION_CHECKLIST.md ]] || fail "missing publication checklist"
[[ -f hooks.json ]] || fail "missing hooks.json"
[[ -f scripts/clean-source-cache.sh ]] || fail "missing source-cache cleaner"
[[ -f data/ato_knowledge_base/source_registry.json ]] || fail "missing source_registry.json"
[[ -f data/ato_knowledge_base/source_coverage.json ]] || fail "missing source_coverage.json"
[[ -f config/public-skills.json ]] || fail "missing public skills manifest"
[[ -f config/skill-packaging.json ]] || fail "missing skill packaging manifest"
[[ -f skills/taxmate-australia/SKILL.md ]] || fail "missing portable entry-point skill"
[[ -f scripts/test-skills-install.sh ]] || fail "missing skills install smoke test"
if [[ -d migration ]] || [[ -f data/ato_knowledge_base/source_index.json ]] || [[ -f data/ato_knowledge_base/source_manifest.json ]] || [[ -f data/ato_knowledge_base/migration_report.json ]]; then
  fail "legacy migration artifacts present"
fi

if git ls-files 'bin/*' | grep -q .; then
  fail "built binaries are tracked"
fi

if git grep -nE 'public[-]work|taxmate-australia-public[-]work' -- . ':!data/ato_knowledge_base/raw/**' ':!data/ato_knowledge_base/text/**'; then
  fail "temporary staging name leaked"
fi

if git grep -nE '/Users/[[:alnum:]_.-]+|custom[_]apps/skills[_]and[_]plugins|Developer/custom[_]apps' -- README.md .codex-plugin agents skills docs; then
  fail "private machine path leaked into public docs"
fi

if git grep -nE 'taxmate-au($|[^s])|TaxMate AU($|[^s])|TAXMATE_AU_ROOT' -- README.md DISCLAIMER.md SECURITY.md CONTRIBUTING.md docs .github .codex-plugin .agents agents skills wrappers plugin.lock.json; then
  fail "legacy public identity leaked"
fi

git grep -Eq 'not (professional )?tax, legal, accounting, financial' -- README.md DISCLAIMER.md .codex-plugin skills || fail "missing professional-advice disclaimer"
git grep -q 'not affiliated with' -- README.md DISCLAIMER.md .codex-plugin skills || fail "missing affiliation disclaimer"
git grep -q 'does not lodge' -- DISCLAIMER.md || fail "missing lodgment disclaimer"
git grep -q 'Accountant review' -- DISCLAIMER.md skills || fail "missing accountant-review boundary"

node <<'NODE'
const fs = require("fs");
const path = require("path");

const root = process.cwd();
const publicManifest = JSON.parse(fs.readFileSync("config/public-skills.json", "utf8"));
const packaging = JSON.parse(fs.readFileSync("config/skill-packaging.json", "utf8"));
const publicSkills = publicManifest.portableSkills;
const publicSet = new Set(publicSkills);
const emptyHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
const repoOnly = /(TAXMATE_AUSTRALIA_ROOT|cmd\/|internal\/|data\/ato_knowledge_base|\.codex-plugin|\$taxmate-australia:|taxmate-australia-(skills|refresh|finance|calc|validate))/;

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}

if (publicManifest.skillsCliVersion !== "1.5.13") fail("skills CLI version must be pinned to 1.5.13");
if (JSON.stringify(publicSkills) !== JSON.stringify(packaging.publicPortable)) fail("public skill manifests differ");

for (const name of publicSkills) {
  const dir = path.join(root, "skills", name);
  const skillPath = path.join(dir, "SKILL.md");
  if (!fs.existsSync(skillPath)) fail(`missing public skill ${name}`);
  const body = fs.readFileSync(skillPath, "utf8");
  if (!body.startsWith("---\n")) fail(`missing frontmatter ${name}`);
  const frontmatterEnd = body.indexOf("\n---", 4);
  if (frontmatterEnd < 0) fail(`invalid frontmatter ${name}`);
  if (!new RegExp(`^name:\\s*${name}$`, "m").test(body.slice(0, frontmatterEnd))) fail(`frontmatter name mismatch ${name}`);
  if (repoOnly.test(body)) fail(`repository-only reference in ${name}`);
  const refs = [...body.matchAll(/`([^`\n]+)`/g)].map((m) => m[1]).filter((p) => p.startsWith("references/"));
  for (const ref of refs) if (!fs.existsSync(path.join(dir, ref))) fail(`missing reference ${name}/${ref}`);
  const refDir = path.join(dir, "references");
  const rulesPath = path.join(refDir, "rules.md");
  if (!fs.existsSync(rulesPath)) fail(`missing rules.md ${name}`);
  const rules = fs.readFileSync(rulesPath, "utf8");
  if (rules.includes(emptyHash)) fail(`empty-content hash in ${name}`);
  if (repoOnly.test(rules)) fail(`repository-only reference in ${name}/references`);
  if (!rules.includes("Verified official-source content")) fail(`missing verified provenance heading ${name}`);
  if (!rules.includes("Metadata-only official-source links")) fail(`missing metadata-only provenance heading ${name}`);
  if (!rules.includes("TaxMate conservative summary")) fail(`missing conservative summary ${name}`);
  if (!rules.includes("Accountant review")) fail(`missing accountant review rules ${name}`);
  if (rules.length < 300) fail(`placeholder-only rules ${name}`);
}

const sourceCoverage = JSON.parse(fs.readFileSync("data/ato_knowledge_base/source_coverage.json", "utf8"));
if (!Array.isArray(sourceCoverage.sources) || sourceCoverage.sources.length === 0) fail("missing or empty source_coverage");
if (sourceCoverage.sources.some((entry) => entry.status === "needs_review")) fail("source_coverage contains needs_review entries");

const skillDirs = fs.readdirSync("skills").filter((entry) => fs.existsSync(path.join("skills", entry, "SKILL.md")));
const unexpectedPublic = skillDirs.filter((entry) => !publicSet.has(entry) && !packaging.runtimeOnly.includes(entry));
if (unexpectedPublic.length) fail(`unexpected skill classification: ${unexpectedPublic.join(", ")}`);

for (const runtimePath of packaging.runtimeOnlyPaths) {
  const skillPath = path.join(runtimePath, "SKILL.md");
  if (!fs.existsSync(skillPath)) fail(`missing runtime-only skill ${runtimePath}`);
  const body = fs.readFileSync(skillPath, "utf8");
  if (!/metadata:\n(?:.*\n)*?\s+internal:\s+true/m.test(body)) fail(`runtime skill not internal: ${runtimePath}`);
}

const readme = fs.readFileSync("README.md", "utf8");
const docs = ["docs/INSTALLATION.md", "docs/FULL_PLUGIN_INSTALL.md", "docs/DEVELOPMENT.md", "docs/SKILL_GENERATION.md"];
for (const doc of docs) if (!fs.existsSync(doc)) fail(`missing ${doc}`);
if (!readme.includes("npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list")) fail("README missing primary npx skills list command");
if (!readme.includes("npx skills@1.5.13 add nijanthan-dev/taxmate-australia \\")) fail("README missing primary npx skills install command");
if (readme.includes("official plugin discovery") || readme.includes("marketplace entry")) fail("README contains unverified marketplace claim");
for (const name of publicSkills) if (!readme.includes(`\`${name}\``)) fail(`README missing public skill ${name}`);
NODE

if git grep -nE 'taxmate-australia-re[d]act|internal/pri[v]acy|RE[D]ACTED' -- . ':!data/ato_knowledge_base/raw/**' ':!data/ato_knowledge_base/text/**'; then
  fail "legacy file-sanitisation artifact found"
fi

./scripts/taxmate skills validate >/tmp/taxmate-australia-skills-validate.json
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
./scripts/taxmate skills audit --format markdown --output /tmp/source-coverage.md
./scripts/taxmate validate >/tmp/taxmate-australia-validate.json
bash scripts/test-skills-install.sh
bash scripts/clean-source-cache.sh

echo "publication checks passed"
