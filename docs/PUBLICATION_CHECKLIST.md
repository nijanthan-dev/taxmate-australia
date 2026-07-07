# Publication Checklist

Use this before publishing TaxMate Australia outside a local install.

- Confirm legal license and repository URL.
- Confirm `skill.json` is present for OpenAgentSkill submission readiness.
- Confirm `skill.json` declares Codex, Claude Code, Cowork, and OpenAgentSkill CLI compatibility.
- Confirm GitHub About description and topics match `docs/DISCOVERY.md`; leave homepage blank unless there is a dedicated external landing page.
- Confirm root `LICENSE` is detected as Apache-2.0 by GitHub.
- Confirm `DISCLAIMER.md` is present and linked from README.
- Confirm no wording implies ATO, Commonwealth, state revenue office, insurer, super fund, or financial-institution endorsement.
- Confirm plugin manifest matches marketplace schema:
  - required metadata present in `.codex-plugin/plugin.json`.
  - required Claude Code metadata present in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
  - all path fields are relative (`./...`).
  - optional app/MCP files are present only if actually used.
  - plugin entry in marketplace is explicit (`name`, `source`, `policy`, `category`).
- if publishing, keep `.agents/plugins/marketplace.json` scanner-safe by pointing `source.path` to a repo-local `./...` path.
- Confirm plugin docs include installation notes and plugin structure for onboarding.
- Confirm README has install commands and usage examples suitable for OpenAgentSkill review.
- Confirm README first paragraph includes Australian tax prep, linked official ATO source wording, GST/BAS, CGT, accountant handoff, and supported agent surfaces.
- Confirm every packaged public skill has exact `SKILL.md`, kebab-case `taxmate-australia-*` public name, source-folder mapping in `config/public-skills.json`, trigger-ready description, compatibility frontmatter, no XML angle brackets in frontmatter, and no skill-folder `README.md`.
- Do not add an OpenAgentSkill badge until the listing is approved.
- Run `./scripts/taxmate validate` and require every check to pass (`score: 100.0`).
- Refresh or recrawl ATO sources near release date.
- Confirm source pack contains only official ATO pages and expected state revenue routing notes.
- Confirm plugin lock/scan posture if the release process requires artifact trust:
  - no unresolved placeholders in `plugin.json` / docs.
  - `plugin.lock.json` exists and includes each packaged public skill plus each `runtime/skills/*` skill with integrity metadata.
  - scanner verification notes are tracked in `docs/PLUGIN_SCANNER.md` if this repo is released publicly.
- Confirm no private paths in publication-facing docs or plugin skills.
- Confirm compatibility wrappers are clearly marked as local install helpers.
- Confirm no legacy file-sanitisation code or binaries.
- Confirm workbook and taxpack skills cannot make independent tax treatment calls.
- Confirm every high-risk area defaults to `Accountant review` when facts are incomplete.
