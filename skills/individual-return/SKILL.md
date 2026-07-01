---
name: individual-return
description: Guide V1 Australian individual tax return intake, including PAYG, ESS, ETP, lump sum in arrears, super income, foreign income, PSI deep, crypto CGT, rental property worksheet, sole-trader ABN, BAS worksheet, WFH, assets, spouse, dependants, and HTML handoff. Use when the user wants an individual return prep pack or a broad individual tax checklist.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
metadata:
  priority: 4
  promptSignals:
    phrases:
      - "individual tax return"
      - "individual return"
      - "ABN and BAS"
      - "employee share scheme"
      - "ESS statement"
      - "employment termination payment"
      - "ETP payment summary"
      - "lump sum in arrears"
      - "super income stream"
      - "foreign income"
      - "foreign income tax offset"
      - "personal services income"
      - "PSI"
      - "crypto"
      - "crypto CGT"
      - "staking rewards"
      - "wallet records"
      - "rental property"
      - "rental income"
      - "net rental loss"
      - "tax intake"
      - "HTML tax pack"
---

# Individual Return

Use this skill to orchestrate V1 individual tax-return preparation. It is a preparation aid only, not tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, investment advice, lodgment software, or a substitute for a qualified professional. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency.

Read `references/rules.md` before building an intake or handoff.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Produce preparation output only: missing facts, evidence requests, copy guidance, review flags, and an HTML handoff when a full runtime is available.
- Do not call any output file lodgment-ready, filing-ready, submit-ready, or final.
- Keep `Accountant review` flags visible.
- Do not auto-use AI-extracted values. Show the value, document, page or context, confidence, and target label; use it only after the user confirms it.

## V1 Scope

Handle individual tax return prep for the selected income year, normally 2025-26, including:

- taxpayer identity facts, residency, state or territory, date of birth, under-18, final-return, and TFN-present checks;
- spouse, spouse period, spouse income-test labels, dependant children or students, private health, Medicare levy, and surcharge facts;
- PAYG salary and wages, employer ABN, gross, tax withheld, occupation, allowances, RFBA, and reportable super;
- common income gates: interest, dividends or ETF distributions, government payments, super touchpoints, and uncommon income routing;
- employee share scheme statement facts, employer or scheme labels, taxed-upfront discount, deferred discount, foreign-source discount, TFN amount withheld, itemized statement rows, and evidence/review routing;
- employment termination payment, lump sum in arrears, super lump sum, and super income stream facts, including statement evidence, payer or fund, payment kind, payment dates, taxable and tax-free components, prior-year allocation, tax withheld, and evidence/review routing;
- foreign income facts, including foreign employment, pensions, country, payer, amount, foreign tax paid, exchange-rate support, foreign income tax offset claims, exempt foreign employment claims, residency-specific or temporary-resident context, and evidence/review routing;
- PSI deep facts, including personal services income amount and type, contract or invoice evidence, results test, 80% client concentration, unrelated clients test, employment test, business premises test, personal services business determination, attribution, deductions, business structure, and evidence/review routing;
- crypto CGT prep facts, including event type such as sale, swap, exchange, conversion, transfer, spend, gift, staking, or reward, asset, quantity, acquisition and disposal dates, cost base, capital proceeds, staking or rewards income, wallet/exchange records, ownership entity, own-wallet transfers, and both business and private use context flags;
- rental property worksheet facts, including property identity, ownership, rental income, loan interest, repairs versus capital, capital works, depreciation, other expenses, private-use or holiday-home days, available-for-rent days, records, net rental loss, and evidence/review routing;
- sole-trader ABN income and expenses, GST registration, accounting basis, business-versus-hobby, PSI review, and profit or loss;
- BAS worksheet facts: period, GST collected, GST credits, GST-free or input-taxed sales, PAYG withholding or instalments, adjustments, and tax invoices;
- employee and ABN deductions, reimbursement, evidence, GST, work/private split, and mixed-use review;
- WFH calendar facts, state-wide public holidays, limited regional/sector/partial-day public holidays, leave, weekends worked, hours, records, fixed-rate and actual-cost support;
- assets such as monitors and laptops, including cost, date, owner, work use, method facts, evidence, and review status.

## Out Of Scope

Do not fully handle company, trust, partnership, full supplementary, complete CGT schedule, or advanced OCR/template extraction workflows. Detect and route those topics to the most specific installed skill or mark `Accountant review`.

## Method

1. Confirm income year and residency period first.
2. Ask a long checklist, not a short interview. Cover the sections in V1 Scope before calculating or rendering.
3. Route tax-treatment decisions to specific installed topic skills: `payg-employer`, `abn-business`, `gst-bas`, `employment-deductions`, `work-from-home`, `private-health-medicare`, `superannuation`, `shares-etfs-managed-funds`, `capital-gains-tax`, `crypto-assets`, `property-rental-cgt`, and `records-evidence`.
4. Keep missing required facts in a missing-facts queue. If the user marks a fact unknown, keep it visible and not copy-ready.
5. Keep missing records in an evidence queue. Show draft values with evidence warnings, not copy-ready status.
6. Put ambiguous, mixed-use, GST/BAS, PSI, non-commercial-loss, home-business, FBT, CGT, business-versus-hobby, and uncommon-income items in `Accountant review`.
7. For WFH, exclude leave and state-wide public holidays unless the user worked. Keep regional, capital-city-only, sector-only, and partial-day holidays as Evidence or `Accountant review` unless the user supplies facts that resolve them. Include weekends only when the user says they worked. Compare fixed-rate and actual-cost candidates only when facts and records support it.
8. For ESS, collect the ESS statement, taxed-upfront and deferred discounts, foreign-source split, TFN amount withheld, and per-employer or per-scheme item rows. Missing statements, malformed or conflicting amounts, foreign-source splits, and deferred taxing-point facts stay Evidence or `Accountant review`; never call them copy-ready.
9. For ETP, lump sum in arrears, super lump sum, and super income stream, collect source statements, payer or fund, payment type, taxable and tax-free components, prior-year allocation where relevant, and withholding. Missing statements, unknown or malformed amounts, and contradictory no-payment plus amount facts stay Evidence or `Accountant review`; never call them copy-ready.
10. For foreign income, collect source statements, country, income type, amount, foreign tax paid, exchange-rate support, residency-specific or temporary-resident evidence, foreign income tax offset claims, and exempt foreign employment claims. Explicit no-foreign-income answers without facts should skip the workflow; no-foreign-income plus amount facts, missing statements, unknown or malformed amounts, exchange-rate gaps, missing residency or temporary-resident evidence, and offset claims without foreign tax paid evidence stay Evidence or `Accountant review`; never call them copy-ready.
11. For PSI deep, collect personal services income amount and type, contract or invoice evidence, results test, 80% client concentration, unrelated clients test, employment test, business premises test, personal services business determination, attribution, deductions, and business structure. Explicit no-PSI answers without facts should skip the workflow; no-PSI plus facts, missing contracts, unknown or malformed income, unknown tests, missing attribution, missing deduction facts, and missing business structure stay Evidence or `Accountant review`; never decide final PSI treatment or call it copy-ready.
12. For crypto CGT prep, collect event type such as sale, swap, exchange, conversion, transfer, spend, gift, staking, or reward, asset, quantity, acquisition/disposal dates, cost base, proceeds, staking/rewards income, wallet or exchange records, ownership/entity, own-wallet transfer support, and both business and private use context flags. Explicit no-crypto answers without facts should skip the workflow; no-crypto plus facts, missing records, unknown or malformed amounts/dates, missing asset or exchange identity, missing ownership/entity, transfer ambiguity, exchange/convert/conversion disposal-like gaps, and missing either business or private use context stay Evidence or `Accountant review`; never decide final CGT treatment or call it copy-ready.
13. For rental property worksheet prep, collect property identity, ownership, income, loan interest, repairs, capital works, depreciation, other expenses, records, private-use or holiday-home days, available-for-rent days, and net rental loss facts. Explicit no-rental-property answers without facts should skip the workflow; no-rental plus facts, missing records, unknown or malformed amounts, repairs-versus-capital ambiguity, missing private-use apportionment, capital works, depreciation, and net rental loss stay Evidence or `Accountant review`; never decide final rental treatment or call it copy-ready.
14. For assets, never claim full cost by default. Ask work-use and method facts, then present immediate, depreciation, low-value-pool, or review outcomes only when source-backed.
15. For BAS, prepare a worksheet only. Calculate totals where facts are complete, but do not lodge or support BAS lodgment.
16. When full runtime execution is available, use the runtime intake command and output one print-first HTML pack only. Do not expose internal Python script names to users.

## Output Contract

The final handoff is HTML only. It must include prep-only boundary, manual-copy warning, intake summary, AI extraction confirmation table, individual return field guide, ABN prep, BAS worksheet, missing facts, evidence queue, accountant-review queue, and source/provenance appendix.
