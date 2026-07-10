# TaxMate Australia Routing Rules

## Verified official-source content

- No tax-treatment claim is made directly in this entry-point skill.
- Topic routing and boundaries are enforced by the active topic skill references.
- This skill uses no verified source-backed summaries.

## Metadata-only official-source links

- No topic-specific coverage is encoded here.
- Topic skills expose metadata-only and verified source context for each topic.
- Use topic skill references for provenance checks.

## Official-source metadata

- ATO home: https://www.ato.gov.au/

## TaxMate conservative summary

- This entry-point skill routes to the most specific installed topic skill.
- It does not make tax-treatment decisions by itself.
- It preserves source URLs, effective periods, evidence status, and `Accountant review` flags.
- If output fields conflict, preserve the most conservative state: explicit or review-like `Accountant review` overrides stale evidence, used, ATO-label, skipped, status-kind, tab-kind, or styling fields.
- Output-layer review queues and side tabs must keep review items visible even when explanatory text is missing.
- Output layers must preserve valid falsey values such as numeric `0` and boolean `false`; do not drop them through truthy fallbacks or raw string conversion.
- It requires current verification for volatile values when web access is available.
- If a needed topic skill or reliable source is unavailable, state the limitation and mark the item `Accountant review`.
- It must not use repository binaries, local repository data, plugin manifests, marketplace JSON, or environment variables.

## Additional routing notes

- If a user query maps cleanly to one topic, route to that topic.
- If a query spans multiple topics, route to the first matching topic with highest confidence and include the limitation.
- If a source is unavailable, preserve `Accountant review` and do not convert missing evidence into a claim.

## Accountant review required

- Any ambiguous, mixed-use, pre-revenue, home-business, FBT, CGT, GST/BAS, non-commercial-loss, business-versus-hobby, missing-source, conflicting-source, or incomplete-fact issue.
- Fixes from independent review must cover the same failure pattern across parser paths, direct renderer/workbook-row paths, file-backed data, generated artifacts, tests, validator, plugin lock, and documentation and instruction validation rules before another review is requested.
