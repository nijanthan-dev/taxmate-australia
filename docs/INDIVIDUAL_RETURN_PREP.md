# Individual Return Prep

Use this path when someone asks how to prepare an Australian individual tax return with TaxMate.

## Boundary

TaxMate is prep-only. It helps collect facts, preserve source links, show missing evidence, and build a manual-copy handoff for myTax, paper ATO form, or accountant handoff. It does not lodge, submit, finalise, fill official ATO PDFs, or give final tax advice.

## Portable Skill Path

Use `taxmate-australia-individual-return` first for a broad checklist. Route specialist sections to installed TaxMate Australia topic skills when facts appear:

- `taxmate-australia-employment-deductions` for PAYG and work deductions.
- `taxmate-australia-work-from-home` for WFH hours, records, holidays, and fixed-rate or actual-cost support.
- `taxmate-australia-private-health-medicare` for private health, Medicare levy, and surcharge facts.
- `taxmate-australia-abn-business` for sole-trader, PSI, business-versus-hobby, and losses.
- `taxmate-australia-gst-bas` for BAS worksheets only.
- `taxmate-australia-shares-etfs-managed-funds`, `taxmate-australia-capital-gains-tax`, `taxmate-australia-crypto-assets`, and `taxmate-australia-property-rental-cgt` for investment, crypto, rental property worksheet, and CGT review.
- `taxmate-australia-records-evidence` for missing records and substantiation gaps.
- `taxmate-australia-workbook` or `taxmate-australia-taxpack` only for output rendering, not tax logic.

Ask a full intake, not a short interview. Keep unknown, ambiguous, mixed-use, GST/BAS, CGT, PSI, foreign, ESS, ETP/lump sum, rental, company, trust, partnership, and entity-return items in Evidence or `Accountant review` unless official sources clearly resolve the prep step.

For PAYG salary and wages prep, collect each income statement by payer, employer or payer ABN, occupation, gross salary/wages, tax withheld, allowances, reportable fringe benefits, reportable employer super contributions, lump sum A/B/D/E labels, statement evidence, and finalised/tax-ready status. Reconcile item totals to supplied aggregate PAYG gross and withholding. Keep missing or unfinalised statements, unknown payer details, malformed amounts, ambiguous allowances/RFBA/RESC/lump sum labels, no-PAYG answers plus facts, and mismatched totals in Evidence or `Accountant review`.

For investment income prep, collect itemized bank interest by payer/account, dividends with franked/unfranked amounts, franking credits and withholding, managed fund/ETF/AMIT distribution statement components, and trust distribution statement facts for individual beneficiaries. Reconcile item totals to supplied aggregate interest/dividend totals. Keep missing statements, AMIT/cost-base adjustments, foreign components, trust distributions, franking uncertainty, and mismatched totals in Evidence or `Accountant review`.

For rental property prep, collect property identity, ownership, income, loan interest, repairs, capital works, depreciation, other expenses, private-use or holiday-home days, available-for-rent days, records, and net rental loss facts. Treat repairs-versus-capital ambiguity, private use, depreciation, capital works, and net rental loss as review-first; TaxMate prepares a worksheet only.

For general non-crypto/non-rental CGT event prep, collect top-level facts or itemized event rows with event type, asset description, owner or ownership share, acquisition date, disposal date, proceeds, cost base, incidental costs, losses, records, and basic review signals such as mixed/private/business use, exemption, discount, and concession flags. Explicit no-CGT answers skip only when no CGT facts exist. No-CGT plus facts, missing records, unknown or malformed dates or amounts, ownership uncertainty, item/top-level conflicts, partial item totals, and review flags stay visible in Evidence or `Accountant review`. TaxMate may reconcile supplied totals to item totals as prep evidence only; it does not calculate a final capital gain or loss.

## Runtime Path

From a full checkout:

```bash
./scripts/taxmate intake individual --help
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
```

Open the HTML in a browser and print or save as PDF. The guide keeps the prep-only boundary, manual-copy warning, intake summary, AI extraction confirmation table, individual return field guide, PAYG income statement rows, itemized investment income rows, CGT schedule and item rows, ABN prep section, BAS worksheet, missing facts queue, evidence queue, accountant-review queue, source URLs, checked-at dates, and source/provenance appendix visible.

## Review Rules

- Explicit no-income, no-crypto, no-PSI, or no-payment answers skip only when no other facts exist.
- No-answer plus facts stays Evidence and must remain visible in answer text and review queues.
- Valid falsey values such as `0` and `false` stay visible.
- `0` withholding, `0` allowances, `0` RFBA, `0` RESC, and false finalised/tax-ready flags stay visible in PAYG rows.
- `0` franking credits, `0` withholding, and `false` foreign components stay visible in investment rows.
- `0` CGT proceeds, cost base, incidental costs, or losses and `false` exemption, discount, concession, business-use, and private-use flags stay visible in CGT schedule and item rows.
- AI-extracted values are not used unless the user confirms them.
- Output layers stay output-only; runtime intake and topic skills own tax-prep logic.
