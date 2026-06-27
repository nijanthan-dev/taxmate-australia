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
[[ -f skill.json ]] || fail "missing OpenAgentSkill skill.json"
[[ -f SECURITY.md ]] || fail "missing SECURITY.md"
[[ -f CONTRIBUTING.md ]] || fail "missing CONTRIBUTING.md"
[[ -f .github/CODEOWNERS ]] || fail "missing CODEOWNERS"
[[ -f .github/pull_request_template.md ]] || fail "missing PR template"
[[ -f .github/ISSUE_TEMPLATE/bug_report.yml ]] || fail "missing bug issue template"
[[ -f .github/ISSUE_TEMPLATE/feature_request.yml ]] || fail "missing feature issue template"
[[ -f .github/ISSUE_TEMPLATE/config.yml ]] || fail "missing issue template config"
[[ -f docs/PUBLICATION_CHECKLIST.md ]] || fail "missing publication checklist"
[[ -f hooks.json ]] || fail "missing hooks.json"
[[ -f scripts/clean-source-cache.sh ]] || fail "missing source-cache cleaner"
[[ -f scripts/codex-env-setup.sh ]] || fail "missing Codex environment setup"
[[ -f scripts/codex-env-cleanup.sh ]] || fail "missing Codex environment cleaner"
[[ -f scripts/codex-env-full-check.sh ]] || fail "missing Codex environment full check"
[[ -f scripts/codex-cloud-post-task-cleanup.sh ]] || fail "missing Codex Cloud cleanup wrapper"
[[ -f .codex/environments/environment.toml ]] || fail "missing Codex environment config"
[[ -f scripts/test-codex-env-cleanup.sh ]] || fail "missing Codex environment cleanup test"
[[ -f scripts/test-codex-env-setup-clean.sh ]] || fail "missing Codex environment setup clean-worktree test"
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

PRIVATE_SCAN_FILES="$(
  git ls-files '*.md' '*.json' '*.toml' '*.yaml' '*.yml' '*.py' '*.sh' '.gitignore' 'scripts/taxmate' \
    ':!:data/ato_knowledge_base/raw/**' \
    ':!:data/ato_knowledge_base/text/**' \
    ':!:scripts/check-publication-ready.sh' \
    ':!:scripts/taxmate_validate.py' \
    ':!:.github/workflows/ci.yml'
)"
if [[ -n "$PRIVATE_SCAN_FILES" ]] && git grep -nE '/Users/[[:alnum:]_.-]+|custom[_]apps/skills[_]and[_]plugins|Developer/custom[_]apps' -- $PRIVATE_SCAN_FILES; then
  fail "private machine path leaked into tracked text files"
fi

if git grep -nE 'taxmate-au($|[^s])|TaxMate AU($|[^s])|TAXMATE_AU_ROOT' -- README.md DISCLAIMER.md SECURITY.md CONTRIBUTING.md skill.json .gitleaks.toml docs .github .codex-plugin .agents agents skills wrappers plugin.lock.json; then
  fail "legacy public identity leaked"
fi

git grep -Eq 'not (professional )?tax, legal, accounting, financial' -- README.md DISCLAIMER.md .codex-plugin skills || fail "missing professional-advice disclaimer"
git grep -q 'not affiliated with' -- README.md DISCLAIMER.md .codex-plugin skills || fail "missing affiliation disclaimer"
git grep -q 'does not lodge' -- DISCLAIMER.md || fail "missing lodgment disclaimer"
git grep -q 'Accountant review' -- DISCLAIMER.md skills || fail "missing accountant-review boundary"
grep -q 'APPENDIX: How to apply the Apache License to your work.' LICENSE || fail "Apache-2.0 license text missing standard appendix"

node <<'NODE'
const fs = require("fs");
const crypto = require("crypto");
const path = require("path");

const root = process.cwd();
const plugin = JSON.parse(fs.readFileSync(".codex-plugin/plugin.json", "utf8"));
const openAgentSkill = JSON.parse(fs.readFileSync("skill.json", "utf8"));
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
if (plugin.interface.websiteURL !== plugin.repository) fail("plugin website must point to repository");
if (!plugin.safety || plugin.safety.humanReviewRequired !== true || plugin.safety.noLodgment !== true || plugin.safety.preserveReviewFlags !== true || !/Never lodge.*ATO/.test(plugin.safety.noLodgmentBoundary || "")) fail("plugin safety boundary metadata missing");
const expectedInstall = "npx skills@1.5.13 add nijanthan-dev/taxmate-australia --agent codex --global --skill '*' --yes";
if (openAgentSkill.slug !== "taxmate-australia") fail("OpenAgentSkill slug mismatch");
if (openAgentSkill.repository !== plugin.repository) fail("OpenAgentSkill repository mismatch");
if (openAgentSkill.homepage !== plugin.homepage) fail("OpenAgentSkill homepage mismatch");
if (openAgentSkill.license !== "Apache-2.0") fail("OpenAgentSkill license mismatch");
if (!/bash/i.test(`${openAgentSkill.description} ${openAgentSkill.tagline}`) || !/python/i.test(`${openAgentSkill.description} ${openAgentSkill.tagline}`)) fail("OpenAgentSkill metadata must describe bash and Python runtime");
if (openAgentSkill.category !== "business") fail("OpenAgentSkill category mismatch");
if (!Array.isArray(openAgentSkill.tags) || openAgentSkill.tags.length === 0 || openAgentSkill.tags.length > 10) fail("OpenAgentSkill tags must be 1-10 entries");
if (!Array.isArray(openAgentSkill.platforms) || !openAgentSkill.platforms.includes("Codex") || !openAgentSkill.platforms.includes("OpenAgentSkill CLI")) fail("OpenAgentSkill platforms missing Codex/CLI");
if (openAgentSkill.install !== expectedInstall) fail("OpenAgentSkill install command mismatch");
if (!Array.isArray(openAgentSkill.install_targets) || !openAgentSkill.install_targets.some((target) => target.value === expectedInstall)) fail("OpenAgentSkill install target missing CLI command");
if (!Array.isArray(openAgentSkill.do_not_use_for) || !openAgentSkill.do_not_use_for.some((item) => /lodgment|filing|submission/i.test(item))) fail("OpenAgentSkill safety boundaries missing lodgment refusal");
if (!openAgentSkill.safety || openAgentSkill.safety.human_review_required !== true) fail("OpenAgentSkill human-review safety missing");

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

const lock = JSON.parse(fs.readFileSync("plugin.lock.json", "utf8"));
const expectedLockPaths = [
  ...publicSkills.map((name) => `skills/${name}`),
  ...packaging.runtimeOnlyPaths.filter((name) => name.startsWith("runtime/skills/")),
].sort();
const lockedPaths = lock.skills.map((entry) => entry.vendoredPath).sort();
if (JSON.stringify(lockedPaths) !== JSON.stringify(expectedLockPaths)) fail("plugin.lock skill paths do not match packaged skills");
for (const entry of lock.skills) {
  if (!entry.source || entry.source.path !== entry.vendoredPath) fail(`plugin.lock source path mismatch ${entry.id}`);
  if (!fs.existsSync(path.join(entry.vendoredPath, "SKILL.md"))) fail(`plugin.lock missing skill path ${entry.vendoredPath}`);
  if (!/^sha256:[a-f0-9]{64}$/.test(entry.integrity || "")) fail(`plugin.lock invalid integrity ${entry.id}`);
  const skillHash = crypto.createHash("sha256").update(fs.readFileSync(path.join(entry.vendoredPath, "SKILL.md"))).digest("hex");
  if (entry.integrity !== `sha256:${skillHash}`) fail(`plugin.lock stale integrity ${entry.id}`);
}

for (const wrapper of packaging.runtimeOnlyPaths.filter((name) => name.startsWith("wrappers/"))) {
  const body = fs.readFileSync(path.join(wrapper, "SKILL.md"), "utf8");
  const fallbackPaths = [...body.matchAll(/\$TAXMATE_AUSTRALIA_ROOT\/([^"`\n]+\/SKILL\.md)/g)].map((match) => match[1]);
  if (!fallbackPaths.length) fail(`wrapper missing fallback path ${wrapper}`);
  for (const fallback of fallbackPaths) {
    if (!fs.existsSync(fallback)) fail(`wrapper fallback path missing ${wrapper}: ${fallback}`);
  }
}

const readme = fs.readFileSync("README.md", "utf8");
const docs = ["docs/INSTALLATION.md", "docs/FULL_PLUGIN_INSTALL.md", "docs/DEVELOPMENT.md", "docs/SKILL_GENERATION.md"];
for (const doc of docs) if (!fs.existsSync(doc)) fail(`missing ${doc}`);
if (!readme.includes("npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list")) fail("README missing primary npx skills list command");
if (!readme.includes("npx skills@1.5.13 add nijanthan-dev/taxmate-australia \\")) fail("README missing primary npx skills install command");
if (!readme.includes("Use the capital-gains-tax skill") || !readme.includes("Use the gst-bas skill")) fail("README missing usage examples");
if (readme.includes("official plugin discovery") || readme.includes("marketplace entry")) fail("README contains unverified marketplace claim");
if (/openagentskill\.com\/badge|OpenAgentSkill badge/i.test(readme)) fail("README should not claim OpenAgentSkill approval before listing");
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
bash -n scripts/codex-env-setup.sh
bash -n scripts/codex-env-cleanup.sh
bash -n scripts/codex-env-full-check.sh
bash -n scripts/codex-cloud-post-task-cleanup.sh
bash -n scripts/test-codex-env-cleanup.sh
bash -n scripts/test-codex-env-setup-clean.sh
bash scripts/test-codex-env-cleanup.sh
bash scripts/test-codex-env-setup-clean.sh
bash scripts/clean-source-cache.sh

echo "publication checks passed"
