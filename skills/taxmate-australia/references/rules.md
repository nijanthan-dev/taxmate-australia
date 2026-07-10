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
- Output-layer review queues and context links must keep review items visible even when explanatory text is missing.
- Output layers must preserve valid falsey values such as numeric `0` and boolean `false`; do not drop them through truthy fallbacks or raw string conversion.
- Every rendered row and queue item must preserve atomic labelled facts, a nonblank runtime-owned action, a verified destination or explicit non-entry/review wording, an explanation, and provenance.
- The runtime action taxonomy is: enter reviewed value, answer guided question, retain evidence, resolve before entry, accountant handoff only, not entered directly, and destination requires review.
- Output layers must not infer destinations from row names, broad topic URLs, source coverage, or unverified target labels. Direct destinations require an exact field-and-context mapping to a verified source ID, canonical URL, and content hash.
- Mixed rows require atomic field actions or safe row separation. Missing, malformed, conflicting, unsupported, or stale mappings retain evidence, non-entry, or review wording.
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
