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
[[ -f .claude-plugin/plugin.json ]] || fail "missing Claude plugin manifest"
[[ -f .claude-plugin/marketplace.json ]] || fail "missing Claude plugin marketplace"
[[ -f .codex-plugin/mcp.json ]] || fail "missing Codex MCP manifest"
[[ ! -f .mcp.json ]] || fail "root .mcp.json conflicts with Claude plugin auto-discovery; use .codex-plugin/mcp.json"
[[ -f mcp/server.cjs ]] || fail "missing MCP server"
[[ -f README.md ]] || fail "missing README"
[[ -f DISCLAIMER.md ]] || fail "missing DISCLAIMER.md"
[[ -f LICENSE ]] || fail "missing LICENSE"
[[ -f skill.json ]] || fail "missing OpenAgentSkill skill.json"
[[ -f SECURITY.md ]] || fail "missing SECURITY.md"
[[ -f CONTRIBUTING.md ]] || fail "missing CONTRIBUTING.md"
[[ -f .github/CODEOWNERS ]] || fail "missing CODEOWNERS"
[[ -f .github/pull_request_template.md ]] || fail "missing PR template"
[[ -f .github/workflows/ci.yml ]] || fail "missing CI workflow"
[[ -f .github/workflows/hol-plugin-scanner.yml ]] || fail "missing HOL plugin scanner workflow"
[[ -f .github/workflows/local-ci.yml ]] || fail "missing local act CI workflow"
[[ -f .github/ISSUE_TEMPLATE/bug_report.yml ]] || fail "missing bug issue template"
[[ -f .github/ISSUE_TEMPLATE/feature_request.yml ]] || fail "missing feature issue template"
[[ -f .github/ISSUE_TEMPLATE/config.yml ]] || fail "missing issue template config"
[[ -f .actrc ]] || fail "missing local act config"
[[ -f docs/PUBLICATION_CHECKLIST.md ]] || fail "missing publication checklist"
[[ -f docs/DISCOVERY.md ]] || fail "missing discovery metadata guide"
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
[[ -f scripts/test-mcp-server.sh ]] || fail "missing MCP server smoke test"
[[ -f scripts/test-codex-plugin-install.sh ]] || fail "missing Codex plugin install smoke test"
[[ -f scripts/test-claude-plugin-validate.sh ]] || fail "missing Claude plugin validation smoke test"
[[ -f scripts/test-claude-plugin-install.sh ]] || fail "missing Claude plugin install smoke test"
[[ -f scripts/check-local-ci-ready.sh ]] || fail "missing local CI readiness check"
[[ -f scripts/run-local-ci-act.sh ]] || fail "missing local act runner"
bash scripts/check-local-ci-ready.sh
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

if git grep -nE 'taxmate-au($|[^s])|TaxMate AU($|[^s])|TAXMATE_AU_ROOT' -- README.md DISCLAIMER.md SECURITY.md CONTRIBUTING.md skill.json .gitleaks.toml docs .github .codex-plugin .claude-plugin .agents agents skills wrappers plugin.lock.json; then
  fail "legacy public identity leaked"
fi

if git grep -nE 'taxmate-australiastralia|TaxMate Australiastralia|TAXMATE_AUSTRALIASTRALIA' -- README.md DISCLAIMER.md SECURITY.md CONTRIBUTING.md skill.json .gitleaks.toml docs .github .codex-plugin .claude-plugin .agents agents skills wrappers plugin.lock.json config; then
  fail "malformed TaxMate Australia rename artifact leaked"
fi

if git grep -nE '^name: (individual-return|employment-deductions|work-from-home|abn-business|gst-bas|payg-employer|capital-gains-tax|shares-etfs-managed-funds|crypto-assets|property-rental-cgt|superannuation|private-health-medicare|records-evidence|workbook|taxpack)$' -- skills wrappers; then
  fail "generic public skill frontmatter leaked"
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
const claudePlugin = JSON.parse(fs.readFileSync(".claude-plugin/plugin.json", "utf8"));
const claudeMarketplace = JSON.parse(fs.readFileSync(".claude-plugin/marketplace.json", "utf8"));
const mcp = JSON.parse(fs.readFileSync(".codex-plugin/mcp.json", "utf8"));
const openAgentSkill = JSON.parse(fs.readFileSync("skill.json", "utf8"));
const publicManifest = JSON.parse(fs.readFileSync("config/public-skills.json", "utf8"));
const packaging = JSON.parse(fs.readFileSync("config/skill-packaging.json", "utf8"));
const publicSkills = publicManifest.portableSkills;
const publicSkillPaths = publicManifest.portableSkillPaths || {};
const publicNameByPath = new Map(Object.entries(publicSkillPaths).map(([name, rel]) => [rel, name]));
const publicSourceDirs = new Set(Object.values(publicSkillPaths).map((rel) => path.basename(rel)));
const emptyHash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
const repoOnly = /(TAXMATE_AUSTRALIA_ROOT|cmd\/|internal\/|data\/ato_knowledge_base|\.codex-plugin|\$taxmate-australia:|taxmate-australia-(skills|refresh|finance|calc|validate))/;
const skillNamePattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}

function frontmatter(body, label) {
  if (!body.startsWith("---\n")) fail(`missing frontmatter ${label}`);
  const frontmatterEnd = body.indexOf("\n---\n", 4);
  if (frontmatterEnd < 0) fail(`invalid frontmatter ${label}`);
  const text = body.slice(4, frontmatterEnd);
  const data = {};
  for (const line of text.split("\n")) {
    if (!line.trim() || /^\s/.test(line)) continue;
    const idx = line.indexOf(":");
    if (idx < 0) fail(`invalid frontmatter line ${label}`);
    data[line.slice(0, idx).trim()] = line.slice(idx + 1).trim().replace(/^"|"$/g, "");
  }
  return { data, text };
}

function skillPaths(base) {
  if (!fs.existsSync(base)) return [];
  return fs.readdirSync(base)
    .map((entry) => path.join(base, entry))
    .filter((entryPath) => fs.statSync(entryPath).isDirectory())
    .map((entryPath) => path.join(entryPath, "SKILL.md"))
    .filter((skillPath) => fs.existsSync(skillPath))
    .sort();
}

function skillDirsWithoutSkill(base) {
  if (!fs.existsSync(base)) return [];
  return fs.readdirSync(base)
    .map((entry) => path.join(base, entry))
    .filter((entryPath) => fs.statSync(entryPath).isDirectory() && !fs.existsSync(path.join(entryPath, "SKILL.md")))
    .sort();
}

function hasReadme(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const entryPath = path.join(dir, entry.name);
    if (entry.isFile() && entry.name === "README.md") return true;
    if (entry.isDirectory() && hasReadme(entryPath)) return true;
  }
  return false;
}

function assertClaudeSkillFrontmatter(skillPath) {
  const body = fs.readFileSync(skillPath, "utf8");
  const folderName = path.basename(path.dirname(skillPath));
  const relDir = path.relative(root, path.dirname(skillPath));
  const expectedName = publicNameByPath.get(relDir) || folderName;
  const parsed = frontmatter(body, expectedName);
  const data = parsed.data;
  const description = data.description || "";
  const compatibility = data.compatibility || "";
  if (data.name !== expectedName) fail(`frontmatter name mismatch ${expectedName}`);
  if (!skillNamePattern.test(data.name || "")) fail(`skill name must be kebab-case ${expectedName}`);
  if (/^(claude|anthropic)/.test(data.name || "")) fail(`reserved skill name prefix ${expectedName}`);
  if (!description || description.length > 1024) fail(`invalid description ${expectedName}`);
  if (!description.startsWith("Use when ")) fail(`description must start with Use when ${expectedName}`);
  if (!compatibility || compatibility.length > 500) fail(`missing compatibility ${expectedName}`);
  if (/[<>]/.test(parsed.text)) fail(`frontmatter XML angle bracket ${expectedName}`);
  if (hasReadme(path.dirname(skillPath))) fail(`README.md inside skill folder ${expectedName}`);
  if (!body.includes("## Quick Reference")) fail(`missing quick reference ${expectedName}`);
  if (!body.includes("## Common Mistakes")) fail(`missing common mistakes ${expectedName}`);
  return body;
}

function pluginEntry(entries, name) {
  if (!Array.isArray(entries)) return undefined;
  return entries.find((entry) => entry && entry.name === name);
}

function claudePluginReady() {
  return claudePlugin.name === "taxmate-australia"
    && claudePlugin.version === plugin.version
    && claudePlugin.skills === "./skills";
}

function claudeMcpReady() {
  const claudeMcp = claudePlugin.mcpServers && claudePlugin.mcpServers.taxmateAustralia;
  return Boolean(claudeMcp)
    && claudeMcp.command === "node"
    && JSON.stringify(claudeMcp.args) === JSON.stringify(["${CLAUDE_PLUGIN_ROOT}/mcp/server.cjs", "--stdio"])
    && claudeMcp.env
    && claudeMcp.env.TAXMATE_AUSTRALIA_ROOT === "${CLAUDE_PLUGIN_ROOT}"
    && claudeMcp.env.PYTHONDONTWRITEBYTECODE === "1";
}

function claudeMarketplaceReady() {
  const marketplacePlugin = pluginEntry(claudeMarketplace.plugins, "taxmate-australia");
  return claudeMarketplace.name === "taxmate-australia"
    && claudeMarketplace.owner
    && claudeMarketplace.owner.name === "TaxMate Australia Maintainers"
    && marketplacePlugin
    && marketplacePlugin.source === "./";
}

if (publicManifest.skillsCliVersion !== "1.5.13") fail("skills CLI version must be pinned to 1.5.13");
if (JSON.stringify(publicSkills) !== JSON.stringify(packaging.publicPortable)) fail("public skill manifests differ");
if (JSON.stringify(publicSkillPaths) !== JSON.stringify(packaging.publicPortablePaths || {})) fail("public skill path manifests differ");
for (const name of publicSkills) {
  if (!name.startsWith("taxmate-australia")) fail(`public skill name missing TaxMate Australia prefix: ${name}`);
  if (!publicSkillPaths[name]) fail(`public skill missing source path: ${name}`);
}
if (plugin.interface.websiteURL !== plugin.repository) fail("plugin website must point to repository");
if (plugin.mcpServers !== "./.codex-plugin/mcp.json") fail("plugin must declare Codex MCP runtime manifest");
const taxmateMcp = mcp.mcpServers && mcp.mcpServers.taxmateAustralia;
if (!taxmateMcp || taxmateMcp.command !== "node" || JSON.stringify(taxmateMcp.args) !== JSON.stringify(["./mcp/server.cjs", "--stdio"]) || taxmateMcp.cwd !== ".") {
  fail("TaxMate MCP server must run mcp/server.cjs from plugin root");
}
if (!claudePluginReady()) fail("Claude plugin manifest mismatch");
if (!claudeMcpReady()) fail("Claude plugin must expose TaxMate MCP server from CLAUDE_PLUGIN_ROOT");
if (!claudeMarketplaceReady()) fail("Claude plugin marketplace must expose taxmate-australia from repo root");
if (!plugin.safety || plugin.safety.humanReviewRequired !== true || plugin.safety.noLodgment !== true || plugin.safety.preserveReviewFlags !== true || !/Never lodge.*ATO/.test(plugin.safety.noLodgmentBoundary || "")) fail("plugin safety boundary metadata missing");
const expectedInstall = "npx skills@1.5.13 add nijanthan-dev/taxmate-australia --agent codex --global --skill '*' --yes";
if (openAgentSkill.slug !== "taxmate-australia") fail("OpenAgentSkill slug mismatch");
if (openAgentSkill.repository !== plugin.repository) fail("OpenAgentSkill repository mismatch");
if (openAgentSkill.homepage !== plugin.homepage) fail("OpenAgentSkill homepage mismatch");
if (openAgentSkill.license !== "Apache-2.0") fail("OpenAgentSkill license mismatch");
if (!/bash/i.test(`${openAgentSkill.description} ${openAgentSkill.tagline}`) || !/python/i.test(`${openAgentSkill.description} ${openAgentSkill.tagline}`) || !/Node\.js/i.test(`${openAgentSkill.description} ${openAgentSkill.tagline}`) || !/Claude Code/i.test(`${openAgentSkill.description} ${openAgentSkill.tagline}`)) fail("OpenAgentSkill metadata must describe Node.js MCP launcher and bash/Python runtime for Claude Code");
if (openAgentSkill.category !== "business") fail("OpenAgentSkill category mismatch");
if (!Array.isArray(openAgentSkill.tags) || openAgentSkill.tags.length === 0 || openAgentSkill.tags.length > 10) fail("OpenAgentSkill tags must be 1-10 entries");
const requiredDiscoveryTags = ["australian-tax", "tax-prep", "ato", "gst", "bas", "cgt", "payg", "superannuation", "accountant", "agent-skills"];
for (const tag of requiredDiscoveryTags) if (!openAgentSkill.tags.includes(tag)) fail(`OpenAgentSkill missing discovery tag ${tag}`);
for (const staleTag of ["australia", "tax", "super"]) if (openAgentSkill.tags.includes(staleTag)) fail(`OpenAgentSkill stale generic tag ${staleTag}`);
if (!Array.isArray(openAgentSkill.platforms) || !openAgentSkill.platforms.includes("Codex") || !openAgentSkill.platforms.includes("Claude Code") || !openAgentSkill.platforms.includes("Cowork") || !openAgentSkill.platforms.includes("OpenAgentSkill CLI")) fail("OpenAgentSkill platforms missing Codex/Claude Code/Cowork/CLI");
if (!Array.isArray(openAgentSkill.agent_compatibility) || !openAgentSkill.agent_compatibility.includes("Codex") || !openAgentSkill.agent_compatibility.includes("Claude Code") || !openAgentSkill.agent_compatibility.includes("Cowork")) fail("OpenAgentSkill agent compatibility missing Codex/Claude Code/Cowork");
if (openAgentSkill.install !== expectedInstall) fail("OpenAgentSkill install command mismatch");
if (!Array.isArray(openAgentSkill.install_targets) || !openAgentSkill.install_targets.some((target) => target.value === expectedInstall)) fail("OpenAgentSkill install target missing CLI command");
if (!Array.isArray(openAgentSkill.install_targets) || !openAgentSkill.install_targets.some((target) => target.id === "claude-code" && /claude plugin marketplace add nijanthan-dev\/taxmate-australia/.test(target.value || "") && /claude plugin install taxmate-australia@taxmate-australia/.test(target.value || ""))) fail("OpenAgentSkill install target missing Claude plugin command");
if (!Array.isArray(openAgentSkill.do_not_use_for) || !openAgentSkill.do_not_use_for.some((item) => /lodgment|filing|submission/i.test(item))) fail("OpenAgentSkill safety boundaries missing lodgment refusal");
if (!openAgentSkill.safety || openAgentSkill.safety.human_review_required !== true) fail("OpenAgentSkill human-review safety missing");

for (const name of publicSkills) {
  const sourcePath = publicSkillPaths[name];
  if (typeof sourcePath !== "string" || !sourcePath.startsWith("skills/")) fail(`invalid public skill path ${name}`);
  const dir = path.join(root, sourcePath);
  const skillPath = path.join(dir, "SKILL.md");
  if (!fs.existsSync(skillPath)) fail(`missing public skill ${name}`);
  const body = fs.readFileSync(skillPath, "utf8");
  const parsed = frontmatter(body, name).data;
  if (parsed.name !== name) fail(`public skill frontmatter mismatch ${name}`);
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

for (const base of ["skills", "runtime/skills", "wrappers"]) {
  const missing = skillDirsWithoutSkill(base);
  if (missing.length) fail(`skill directories without SKILL.md: ${missing.join(", ")}`);
  for (const skillPath of skillPaths(base)) assertClaudeSkillFrontmatter(skillPath);
}

const skillDirs = fs.readdirSync("skills").filter((entry) => fs.existsSync(path.join("skills", entry, "SKILL.md")));
const unexpectedPublic = skillDirs.filter((entry) => !publicSourceDirs.has(entry) && !packaging.runtimeOnly.includes(entry));
if (unexpectedPublic.length) fail(`unexpected skill classification: ${unexpectedPublic.join(", ")}`);

for (const runtimePath of packaging.runtimeOnlyPaths) {
  const skillPath = path.join(runtimePath, "SKILL.md");
  if (!fs.existsSync(skillPath)) fail(`missing runtime-only skill ${runtimePath}`);
  const body = fs.readFileSync(skillPath, "utf8");
  if (!/metadata:\n(?:.*\n)*?\s+internal:\s+true/m.test(body)) fail(`runtime skill not internal: ${runtimePath}`);
}

const lock = JSON.parse(fs.readFileSync("plugin.lock.json", "utf8"));
const expectedLockPaths = [
  ...Object.values(publicSkillPaths),
  ...packaging.runtimeOnlyPaths.filter((name) => name.startsWith("runtime/skills/")),
].sort();
const lockedPaths = lock.skills.map((entry) => entry.vendoredPath).sort();
if (JSON.stringify(lockedPaths) !== JSON.stringify(expectedLockPaths)) fail("plugin.lock skill paths do not match packaged skills");
for (const entry of lock.skills) {
  if (!entry.source || entry.source.path !== entry.vendoredPath) fail(`plugin.lock source path mismatch ${entry.id}`);
  if (publicNameByPath.has(entry.vendoredPath) && entry.id !== publicNameByPath.get(entry.vendoredPath)) fail(`plugin.lock stale public skill id ${entry.id}`);
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
const discovery = fs.readFileSync("docs/DISCOVERY.md", "utf8");
const docs = ["docs/INSTALLATION.md", "docs/FULL_PLUGIN_INSTALL.md", "docs/DEVELOPMENT.md", "docs/SKILL_GENERATION.md", "docs/DISCOVERY.md"];
for (const doc of docs) if (!fs.existsSync(doc)) fail(`missing ${doc}`);
for (const term of ["linked to official ATO sources", "individual tax return", "GST/BAS", "CGT", "accountant handoff", "Codex", "Claude Code", "Cowork"]) {
  if (!readme.includes(term)) fail(`README missing discovery term ${term}`);
}
for (const term of ["GitHub About", "claude-code", "cowork", "openagentskill", "individual tax return prep", "Leave blank until there is a dedicated external landing page."]) {
  if (!discovery.includes(term)) fail(`DISCOVERY missing term ${term}`);
}
for (const staleClaim of ["turn Australian tax records into", "messy tax records", "move from tax records", "tax records into"]) {
  if (readme.includes(staleClaim) || discovery.includes(staleClaim) || JSON.stringify(plugin).includes(staleClaim) || JSON.stringify(openAgentSkill).includes(staleClaim)) {
    fail(`stale positioning claim found: ${staleClaim}`);
  }
}
if (discovery.includes("tax-records")) fail("DISCOVERY must not use tax-records topic");
if (!plugin.interface.shortDescription.includes("Australian tax prep with ATO source links")) fail("plugin short description missing discovery copy");
const atoBackingPattern = new RegExp("ATO[- ]" + "backed|backed by " + "ATO|supported by " + "ATO", "i");
for (const file of ["README.md", "docs/DISCOVERY.md", ".codex-plugin/plugin.json", "skill.json", "agents/openai.yaml", "skills/taxmate-australia/SKILL.md", "wrappers/taxmate-australia/SKILL.md"]) {
  const text = fs.readFileSync(file, "utf8");
  if (atoBackingPattern.test(text)) fail(`${file} implies ATO backing`);
}
if (plugin.keywords.includes("assistant") || plugin.keywords.includes("super")) fail("plugin keywords contain stale generic terms");
if (!readme.includes("Codex plugin install")) fail("README missing Codex plugin install path");
if (!readme.includes("Claude Code plugin install")) fail("README missing Claude Code plugin install path");
if (!readme.includes("Node.js 20+ for the MCP launcher")) fail("README missing Node.js MCP launcher prerequisite");
if (!readme.includes("npx skills") || !readme.includes("guidance only")) fail("README must describe npx skills as guidance only");
if (!readme.includes("Use the taxmate-australia-capital-gains-tax skill") || !readme.includes("Use the taxmate-australia-gst-bas skill")) fail("README missing usage examples");
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
bash scripts/test-mcp-server.sh
bash scripts/test-codex-plugin-install.sh
bash scripts/test-claude-plugin-validate.sh
bash scripts/test-claude-plugin-install.sh
bash scripts/test-install-local-skills.sh
bash -n scripts/codex-env-setup.sh
bash -n scripts/codex-env-cleanup.sh
bash -n scripts/codex-env-full-check.sh
bash -n scripts/codex-cloud-post-task-cleanup.sh
bash -n scripts/test-codex-env-cleanup.sh
bash -n scripts/test-codex-env-setup-clean.sh
bash -n scripts/test-install-local-skills.sh
bash scripts/test-codex-env-cleanup.sh
bash scripts/test-codex-env-setup-clean.sh
bash scripts/clean-source-cache.sh

echo "publication checks passed"
