# Workbook Rules

## Verified official-source content

- No verified official-source summaries are stored in this output layer.

## Metadata-only official-source links

- Workbook pulls records and treated outputs from topic references that include official-source metadata.
- ATO records you need to keep: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/records-you-need-to-keep
- ATO business records: https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/record-keeping-for-business

## TaxMate conservative summary

- Workbook is output-only. Do not invent tax treatment.
- Preserve reviewed treatment, source URLs, income year, effective period, evidence status, and `Accountant review` flags.
- If reviewed output fields conflict, preserve the most conservative state: explicit or review-like `Accountant review` overrides stale evidence, used, ATO-label, skipped, status-kind, tab-kind, or styling fields.
- Review queues must keep review items visible even when explanatory text is missing.
- Workbook display fields must preserve valid falsey values such as numeric `0` and boolean `false`; do not drop them through truthy fallbacks or raw string conversion.
- Convert raw intake answers through the canonical intake-to-pack contract before export. Prefix formula-like CSV cells so spreadsheet applications display supplied text instead of evaluating it.
- Separate taxpayer, spouse/partner, joint, entity, employee, ABN/business, GST/BAS, investment, super, private health, and property records.
- Keep source rows visible. Use formulas only for transparent totals.
- Do not mark BAS nil when GST credits or GST collected are present.

## Accountant review required

- Any row with missing facts, missing evidence, source conflict, mixed-use, GST/BAS, CGT, home-business, FBT, pre-revenue, non-commercial-loss, or business-versus-hobby uncertainty.
- Fixes from independent review must cover parsed input, file-backed data, and direct workbook-row paths before another review is requested.
