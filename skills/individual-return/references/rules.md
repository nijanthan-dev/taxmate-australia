# Individual Return Rules

## Verified official-source content

This orchestration skill does not bundle extracted tax-treatment summaries. It coordinates installed topic skills and full-runtime output generation. Treat calculation rates, thresholds, labels, and income-year-specific rules as unverified until a topic skill or current official source supplies provenance with source URL, checked-at date, content hash, and effective period.

## Metadata-only official-source links

- ATO individual tax return instructions: https://www.ato.gov.au/forms-and-instructions/individual-tax-return-instructions-2026
- ATO working from home fixed-rate method: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method
- ATO working from home actual-cost method: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/actual-cost-method
- ATO business activity statements: https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas
- Fair Work 2025 public holidays: https://www.fairwork.gov.au/employment-conditions/public-holidays/2025-public-holidays
- Fair Work 2026 public holidays: https://www.fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays

Metadata-only links are routing and verification leads, not enough by themselves for a copy-ready tax treatment.

## TaxMate conservative summary

Individual-return intake is a coordinator. It should collect facts, preserve evidence gaps, route to the most specific installed skill, and assemble an HTML preparation handoff. It should not duplicate detailed tax logic from PAYG, WFH, ABN, GST/BAS, private-health, superannuation, investment, records, workbook, or taxpack skills. If full-runtime tooling is available, use it for deterministic calendars, candidate rows, queues, and HTML rendering; keep portable skill output as guidance when no checkout/runtime exists.

## Accountant review

Use `Accountant review` for ambiguity, missing evidence, mixed-use items, GST/BAS uncertainty, PSI, non-commercial losses, business-versus-hobby, home-business occupancy, CGT, FBT, uncommon income, unsupported AI extraction, unknown required facts, and any source conflict. Review status wins over evidence, used, skipped, ATO-label, tab-kind, status-kind, or styling fields in all rendered queues and guide rows.
