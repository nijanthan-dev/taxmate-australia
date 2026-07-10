# Taxpack Rules

## Verified official-source content

- No verified official-source summaries are stored in this output layer.

## Metadata-only official-source links

- Taxpack coordinates topic references for review and packaging workflows.
- ATO how to lodge your tax return: https://www.ato.gov.au/individuals-and-families/your-tax-return/how-to-lodge-your-tax-return
- ATO records you need to keep: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/records-you-need-to-keep

## TaxMate conservative summary

- Taxpack is output-only. It does not lodge, file, or create final advice.
- Include reviewed summaries, source URLs, evidence status, income-year labels, open questions, and `Accountant review` queues.
- If guide input fields conflict, preserve the most conservative state: explicit or review-like `Accountant review` overrides stale evidence, used, ATO-label, skipped, status-kind, tab-kind, or styling fields.
- Guide rows with supplied source URLs or checked-at dates must keep that provenance visible in the worksheet.
- Review queues and context links must keep review items visible even when explanatory text is missing.
- Guide display fields must preserve valid falsey values such as numeric `0` and boolean `false`; do not drop them through truthy fallbacks or raw string conversion.
- Every rendered row and queue item must preserve the runtime-owned handoff action, destination or explicit non-entry/review wording, explanation, facts, and provenance.
- Output layers must not infer destination logic from row names, broad topic URLs, source coverage alone, or unverified AI target labels.
- Mixed rows require field-level actions or safe row separation. Missing, malformed, conflicting, unsupported, or stale mappings fail closed.
- Manual-copy guidance must be custom preparation guidance, not rendered files or filled/modified official ATO PDFs. Use the full runtime for print-first HTML handoff generation.
- Reference ATO labels only to help users copy reviewed answers into myTax, paper ATO forms, or an accountant handoff.
- Do not silently drop uncertain rows.

## Accountant review required

- Any unresolved treatment, missing evidence, BAS/GST, CGT, FBT, home-business, pre-revenue, mixed-use, non-commercial-loss, business-versus-hobby, or lodgment-position item.
- Validation must cover conflicts or blanks that could hide an accountant-review flag from the row badge, context index, review-only filter, or review queue.
- Fixes from independent review must cover parsed input, file-backed guide data, and direct renderer paths before another review is requested.
- Falsey-value regressions must cover top-level guide metadata, row fields, source URL lists, checked-at provenance, fallback tab text, anchors, and direct `GuideItem` construction.
