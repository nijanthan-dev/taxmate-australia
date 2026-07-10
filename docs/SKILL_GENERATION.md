# Skill Generation

TaxMate Australia uses a bash+python runtime pipeline to turn approved Australian government sources into concise topic skills.

Do not reintroduce Go tooling, `go.mod`, `gomod` Dependabot entries, migration artifacts, `source_index`, `source_manifest`, or committed raw source text.
Public plugin metadata must describe the bash+Python runtime and must not mention removed backend architectures.

## Pipeline

1. `scripts/taxmate refresh` refreshes indexed official URLs.
2. Fetched HTML and extracted text are written only to ignored `.cache/ato/`.
3. `scripts/taxmate skills generate` maps sources to topic skills and writes compact references.
4. `scripts/taxmate skills generate` writes `data/ato_knowledge_base/source_coverage.json`.
5. `scripts/taxmate skills audit` writes coverage diagnostics on demand.
6. `scripts/taxmate skills validate` checks validation rules, source assignment, reverse provenance, dynamic-value periods, stale generated artifacts, and absence of committed raw snapshots.
7. `hooks.json` runs `scripts/clean-source-cache.sh` on `SessionEnd` to remove `.cache/ato/`.

Approved hosts are allowlisted in `scripts/atodata.py`. Downloaded content is treated as untrusted data and is never allowed to change validation rules.

## Generated Outputs

- `skills/topic-name/SKILL.md`: concise routing, facts, source workflow, output states, review flags, and anti-overclaim rules.
- `skills/topic-name/references/rules.md`: source-backed scope and provenance.
- `skills/topic-name/references/evidence.md`: records needed before classification.
- `skills/topic-name/references/sources.json`: source URL, title, last-updated date, checked-at date, and content hash.
- `skills/topic-name/references/current-values.json`: volatile values with provenance and reuse warning.
- `data/ato_knowledge_base/source_coverage.json`: global source coverage status by source and topic with verified/metadata-only/duplicate/excluded states.

## Dynamic Values

Skills must not hardcode rates, thresholds, caps, due dates, or similar volatile values. Generated references may include a value only with source URL, title, last-updated date when available, checked-at date, content hash, context, and effective period or income year when detectable.

If a value is stale, unavailable, conflicting, or wrong-year, classify the matter as `Accountant review`.

When `.cache/ato/text/` is unavailable, generation may preserve existing `current-values.json` entries only if their source URL and content hash match an assigned verified source. Refresh preserved value title, last-updated, and checked-at metadata from the current source row; do not accept a valid value hash against a blank source hash or a metadata-only source. `skills generate --check` must compare both generated and tracked generated files so stale tracked references fail the check.

## Empty-content provenance

The SHA-256 value below is empty content and must fail publication validation when present in public references:

```text
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

When source content is unavailable, keep the official URL, state that the rule was not extracted or verified, and require `Accountant review`.

## Topic Map

- `employment-deductions`
- `work-from-home`
- `abn-business`
- `gst-bas`
- `payg-employer`
- `capital-gains-tax`
- `shares-etfs-managed-funds`
- `crypto-assets`
- `property-rental-cgt`
- `superannuation`
- `private-health-medicare`
- `records-evidence`

`workbook` and `taxpack` remain output layers only.

Generated topic skill frontmatter must stay portable for Claude Code, Cowork, Codex, and OpenAgentSkill CLI:

- source folder names stay stable for source coverage and generation.
- public `name` values stay kebab-case and use the `taxmate-australia-` prefix.
- `description` includes what the skill does and when to use it.
- `compatibility` states portable use and checkout-free requirements.
- frontmatter never contains XML angle brackets.
- generated skill folders never include `README.md`; references stay under `references/`.
