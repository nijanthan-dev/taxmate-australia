# Skill Generation

TaxMate Australia uses a Go pipeline to turn approved official Australian government sources into concise topic skills.

## Pipeline

1. `taxmate-australia-refresh` refreshes indexed official URLs.
2. Fetched HTML and extracted text are written only to ignored `.cache/ato/`.
3. `taxmate-australia-skills generate` maps sources to topic skills and writes compact references.
4. `taxmate-australia-skills audit` regenerates `migration/SOURCE_TO_SKILL_REPORT.md` from `migration/source-to-skill-map.json`.
5. `taxmate-australia-skills validate` checks guardrails, source assignment, reverse provenance, dynamic-value periods, and absence of committed raw snapshots.
6. `hooks.json` runs `scripts/clean-source-cache.sh` on `SessionEnd` to remove `.cache/ato/`.

Approved hosts are allowlisted in `internal/skillgen`. Downloaded content is treated as untrusted data and is never allowed to change guardrails.

## Generated Outputs

- `skills/<topic>/SKILL.md`: concise routing, facts, refresh workflow, output states, review flags, and anti-overclaim rules.
- `skills/<topic>/references/rules.md`: source-backed scope and provenance.
- `skills/<topic>/references/evidence.md`: records needed before classification.
- `skills/<topic>/references/sources.json`: source URL, title, last-updated date, checked-at date, and content hash.
- `skills/<topic>/references/current-values.json`: volatile values with provenance and reuse warning.
- `data/ato_knowledge_base/migration_report.json`: every indexed source assigned, duplicated, unsupported, or unassigned.
- `migration/source-to-skill-map.json`: every indexed source classified exactly once.
- `migration/SOURCE_TO_SKILL_REPORT.md`: generated audit summary from the source map.

## Dynamic Values

Skills must not hardcode rates, thresholds, caps, due dates, or similar volatile values. Generated references may include a value only with source URL, title, last-updated date when available, checked-at date, content hash, context, and effective period or income year when detectable.

If a value is stale, unavailable, conflicting, or wrong-year, classify the matter as `Accountant review`.

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
