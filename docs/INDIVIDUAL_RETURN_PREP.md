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
- `shares-etfs-managed-funds`, `capital-gains-tax`, `crypto-assets`, and `property-rental-cgt` for investment, crypto, rental, and CGT review.
- `records-evidence` for missing records and substantiation gaps.
- `workbook` or `taxpack` only for output rendering, not tax logic.

Ask a full intake, not a short interview. Keep unknown, ambiguous, mixed-use, GST/BAS, CGT, PSI, foreign, ESS, ETP/lump sum, rental, company, trust, partnership, and entity-return items in Evidence or `Accountant review` unless official sources clearly resolve the prep step.

## Runtime Path

From a full checkout:

```bash
./scripts/taxmate intake individual --help
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
```

Open the HTML in a browser and print or save as PDF. The guide keeps source URLs, checked-at dates, missing facts, evidence rows, and accountant-review queues visible.

## Review Rules

- Explicit no-income, no-crypto, no-PSI, or no-payment answers skip only when no other facts exist.
- No-answer plus facts stays Evidence and must remain visible in answer text and review queues.
- Valid falsey values such as `0` and `false` stay visible.
- AI-extracted values are not used unless the user confirms them.
- Output layers stay output-only; runtime intake and topic skills own tax-prep logic.
