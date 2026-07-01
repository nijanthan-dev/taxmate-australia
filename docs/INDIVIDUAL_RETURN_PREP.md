# Individual Return Prep

Use this path when someone asks how to prepare an Australian individual tax return with TaxMate.

## Boundary

TaxMate is prep-only. It helps collect facts, preserve source links, show missing evidence, and build a manual-copy handoff for myTax, paper ATO form, or accountant handoff. It does not lodge, submit, finalise, fill official ATO PDFs, or give final tax advice.

## Portable Skill Path

Use `individual-return` first for a broad checklist. Route specialist sections to installed topic skills when facts appear:

- `employment-deductions` for PAYG and work deductions.
- `work-from-home` for WFH hours, records, holidays, and fixed-rate or actual-cost support.
- `private-health-medicare` for private health, Medicare levy, and surcharge facts.
- `abn-business` for sole-trader, PSI, business-versus-hobby, and losses.
- `gst-bas` for BAS worksheets only.
- `shares-etfs-managed-funds`, `capital-gains-tax`, `crypto-assets`, and `property-rental-cgt` for investment, crypto, rental property worksheet, and CGT review.
- `records-evidence` for missing records and substantiation gaps.
- `workbook` or `taxpack` only for output rendering, not tax logic.

Ask a full intake, not a short interview. Keep unknown, ambiguous, mixed-use, GST/BAS, CGT, PSI, foreign, ESS, ETP/lump sum, rental, company, trust, partnership, and entity-return items in Evidence or `Accountant review` unless official sources clearly resolve the prep step.

For investment income prep, collect itemized bank interest by payer/account, dividends with franked/unfranked amounts, franking credits and withholding, managed fund/ETF/AMIT distribution statement components, and trust distribution statement facts for individual beneficiaries. Reconcile item totals to supplied aggregate interest/dividend totals. Keep missing statements, AMIT/cost-base adjustments, foreign components, trust distributions, franking uncertainty, and mismatched totals in Evidence or `Accountant review`.

For rental property prep, collect property identity, ownership, income, loan interest, repairs, capital works, depreciation, other expenses, private-use or holiday-home days, available-for-rent days, records, and net rental loss facts. Treat repairs-versus-capital ambiguity, private use, depreciation, capital works, and net rental loss as review-first; TaxMate prepares a worksheet only.

## Runtime Path

From a full checkout:

```bash
./scripts/taxmate intake individual --help
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
```

Open the HTML in a browser and print or save as PDF. The guide keeps the prep-only boundary, manual-copy warning, intake summary, AI extraction confirmation table, individual return field guide, itemized investment income rows, ABN prep section, BAS worksheet, missing facts queue, evidence queue, accountant-review queue, source URLs, checked-at dates, and source/provenance appendix visible.

## Review Rules

- Explicit no-income, no-crypto, no-PSI, or no-payment answers skip only when no other facts exist.
- No-answer plus facts stays Evidence and must remain visible in answer text and review queues.
- Valid falsey values such as `0` and `false` stay visible.
- `0` franking credits, `0` withholding, and `false` foreign components stay visible in investment rows.
- AI-extracted values are not used unless the user confirms them.
- Output layers stay output-only; runtime intake and topic skills own tax-prep logic.
