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
- ATO-aligned guide PDFs must be custom manual guides, not filled or modified official ATO PDFs.
- Reference ATO labels only to help users copy reviewed answers into myTax, paper ATO forms, or an accountant handoff.
- Do not silently drop uncertain rows.

## Accountant review required

- Any unresolved treatment, missing evidence, BAS/GST, CGT, FBT, home-business, pre-revenue, mixed-use, non-commercial-loss, business-versus-hobby, or lodgment-position item.
- Validation must cover conflicts that could hide an accountant-review flag from the row badge, side tab, review-only filter, or review queue.
