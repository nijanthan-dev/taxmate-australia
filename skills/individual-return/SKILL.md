---
name: taxmate-australia-individual-return
description: Use when the user wants a TaxMate Australia individual return prep pack, broad individual tax checklist, or full-runtime HTML handoff setup.
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
      - "income statement"
      - "PAYG income statement"
      - "ETP payment summary"
      - "lump sum in arrears"
      - "super income stream"
      - "foreign income"
      - "foreign income tax offset"
      - "bank interest"
      - "franking credit"
      - "managed fund distribution"
      - "AMIT"
      - "trust distribution"
      - "personal services income"
      - "PSI"
      - "crypto"
      - "crypto CGT"
      - "staking rewards"
      - "wallet records"
      - "CGT schedule"
      - "capital gains tax event"
      - "capital loss"
      - "CGT discount"
      - "asset disposal"
      - "rental property"
      - "rental income"
      - "net rental loss"
      - "tax intake"
      - "manual copy tax pack"
---

# TaxMate Australia Individual Return

Use this skill to orchestrate V1 individual tax-return preparation, including PAYG, ESS, ETP, investment income, general CGT event review, crypto, rental, ABN, BAS, WFH, phone plan/device facts, and review queues. It is a preparation aid only, not tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, investment advice, lodgment software, or a substitute for a qualified professional. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency.

Read `references/rules.md` before building an intake or handoff.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Produce preparation output only: missing facts, evidence requests, copy guidance, review flags, and an HTML handoff when a full runtime is available.
- Do not call any output file lodgment-ready, filing-ready, submit-ready, or final.
- Keep `Accountant review` flags visible.
- Do not auto-use AI-extracted values. Show the value, document, page or context, confidence, and target label; use it only after the user confirms it.

## Quick Reference

| Situation | Action |
| --- | --- |
| Broad individual return | Ask the full checklist before calculating or rendering. |
| Topic-specific tax treatment | Route to the installed TaxMate Australia topic skill. |
| Missing or unknown facts | Keep a missing-facts or evidence queue item visible. |
| Full runtime is available | Use it only for deterministic handoff rendering after review. |
| Manual-copy handoff | Use manual-copy handoff guidance; use full runtime for HTML handoff generation when a full runtime is available. |

## Common Mistakes

- Running a short interview and missing uncommon income, spouse, BAS, or review facts.
- Treating AI-extracted values as confirmed before the user confirms them.
- Letting generic evidence fields remove an `Accountant review` status.
- Calling manual-copy output lodged, final, or advice.

## V1 Scope

Handle individual tax return prep for the selected income year, normally 2025-26, including:

- taxpayer identity facts, residency, state or territory, date of birth, under-18, final-return, and TFN-present checks;
- spouse, spouse period, spouse income-test labels, dependant children or students, private health, Medicare levy, and surcharge facts;
- PAYG salary and wages, multi-employer income statements, payer name, employer ABN, gross, tax withheld, occupation, allowances, RFBA, reportable employer super, lump sum A/B/D/E labels, statement evidence, and aggregate reconciliation;
- common income gates: interest, dividends or ETF distributions, government payments, super touchpoints, and uncommon income routing;
- investment income distribution facts: itemized bank interest, dividend/franking statements, managed fund/ETF/AMIT components, and trust distribution statement routing for individual beneficiaries;
- general non-crypto/non-rental CGT schedule and item rows with event type, asset, owner, acquisition date, disposal date, proceeds, cost base, incidental costs, losses, current-year and carried-forward capital loss facts, records, discount claim, discount timing or review signals, foreign-resident discount signals, main residence claim, ownership and occupancy periods, rental/business use, absence periods, spouse or partner main-residence conflict, small-business concession signals, property-record evidence, source provenance, reconciliation prompts, and amount-not-worked-out wording;
- employee share scheme statement facts, employer or scheme labels, taxed-upfront discount, deferred discount, foreign-source discount, TFN amount withheld, itemized statement rows, and evidence/review routing;
- employment termination payment, lump sum in arrears, super lump sum, and super income stream facts, including statement evidence, payer or fund, payment kind, payment dates, taxable and tax-free components, prior-year allocation, tax withheld, and evidence/review routing;
- foreign income facts, including foreign employment, pensions, country, payer, amount, foreign tax paid, exchange-rate support, foreign income tax offset claims, exempt foreign employment claims, residency-specific or temporary-resident context, and evidence/review routing;
- PSI deep facts, including personal services income amount and type, contract or invoice evidence, results test, 80% client concentration, unrelated clients test, employment test, business premises test, personal services business determination, attribution, deductions, business structure, and evidence/review routing;
- crypto CGT prep facts, including event type such as sale, swap, exchange, conversion, transfer, spend, gift, staking, or reward, asset, quantity, acquisition and disposal dates, cost base, capital proceeds, staking or rewards income, wallet/exchange records, ownership entity, own-wallet transfers, and both business and private use context flags;
- rental property worksheet facts, including property identity, ownership, rental income, loan interest, repairs versus capital, capital works, depreciation, other expenses, private-use or holiday-home days, available-for-rent days, records, net rental loss, and evidence/review routing;
- sole-trader ABN profile, income streams, expense categories, GST registration status/date, accounting basis, record system, business-versus-hobby, PSI review, private-use apportionment, home-business, motor vehicle, depreciation/capital expense, and profit or loss;
- BAS worksheet facts: period, coverage, 1A GST collected, 1B GST credits, GST-free or input-taxed sales, PAYG withholding or instalments, adjustments, accounting basis, GST registration date, and tax invoice evidence;
- employee and ABN deductions, reimbursement, evidence, GST, work/private split, and mixed-use review;
- phone plan/data/device and incidental-use facts, including employee/ABN/both context, user-paid status, employer paid/reimbursed/provided flags, WFH method, bills, 4-week records, work-use percentage, device cost/date, changed work-use facts, insurance, and ABN/GST/BAS routing;
- WFH calendar facts, state-wide public holidays, limited regional/sector/partial-day public holidays, leave, weekends worked, hours, records, fixed-rate and actual-cost support;
- assets such as monitors and laptops, including cost, date, owner, work use, method facts, evidence, and review status.

## Out Of Scope

Do not fully handle company, trust, partnership, full supplementary, complete CGT schedule, or advanced OCR/template extraction workflows. Detect and route those topics to the most specific installed skill or mark `Accountant review`.

## Method

1. Confirm income year and residency period first.
2. Ask a long checklist, not a short interview. Cover the sections in V1 Scope before calculating or rendering.
3. Route tax-treatment decisions to specific installed TaxMate Australia topic skills: `taxmate-australia-payg-employer`, `taxmate-australia-abn-business`, `taxmate-australia-gst-bas`, `taxmate-australia-employment-deductions`, `taxmate-australia-work-from-home`, `taxmate-australia-private-health-medicare`, `taxmate-australia-superannuation`, `taxmate-australia-shares-etfs-managed-funds`, `taxmate-australia-capital-gains-tax`, `taxmate-australia-crypto-assets`, `taxmate-australia-property-rental-cgt`, and `taxmate-australia-records-evidence`.
4. Keep missing required facts in a missing-facts queue. If the user marks a fact unknown, keep it visible and not copy-ready.
5. Keep missing records in an evidence queue. Show draft values with evidence warnings, not copy-ready status.
6. Put ambiguous, mixed-use, GST/BAS, PSI, non-commercial-loss, home-business, FBT, CGT, business-versus-hobby, and uncommon-income items in `Accountant review`.
7. For WFH, exclude leave and state-wide public holidays unless the user worked. Keep regional, capital-city-only, sector-only, and partial-day holidays as Evidence or `Accountant review` unless the user supplies facts that resolve them. Include weekends only when the user says they worked. Compare fixed-rate and actual-cost candidates only when facts and records support it.
8. For PAYG salary and wages, collect primary and secondary income statement rows with payer name, employer ABN, occupation, gross salary/wages, tax withheld, allowances, RFBA, RESC, lump sum A/B/D/E labels, statement evidence, and finalised/tax-ready status. Reconcile item totals to supplied aggregate PAYG gross and withholding. Missing or unfinalised statements, unknown payer details, malformed amounts, direct alias conflicts, ambiguous allowance/RFBA/RESC/lump sum labels, no-PAYG answers plus facts, and mismatched totals stay Evidence or `Accountant review`; never call them copy-ready.
9. For ESS, collect the ESS statement, taxed-upfront and deferred discounts, foreign-source split, TFN amount withheld, and per-employer or per-scheme item rows. Missing statements, malformed or conflicting amounts, foreign-source splits, and deferred taxing-point facts stay Evidence or `Accountant review`; never call them copy-ready.
10. For ETP, lump sum in arrears, super lump sum, and super income stream, collect source statements, payer or fund, payment type, taxable and tax-free components, prior-year allocation where relevant, and withholding. Missing statements, unknown or malformed amounts, and contradictory no-payment plus amount facts stay Evidence or `Accountant review`; never call them copy-ready.
11. For foreign income, collect source statements, country, income type, amount, foreign tax paid, exchange-rate support, residency-specific or temporary-resident evidence, foreign income tax offset claims, and exempt foreign employment claims. Explicit no-foreign-income answers without facts should skip the workflow; no-foreign-income plus amount facts, missing statements, unknown or malformed amounts, exchange-rate gaps, missing residency or temporary-resident evidence, and offset claims without foreign tax paid evidence stay Evidence or `Accountant review`; never call them copy-ready.
12. For PSI deep, collect personal services income amount and type, contract or invoice evidence, results test, 80% client concentration, unrelated clients test, employment test, business premises test, personal services business determination, attribution, deductions, and business structure. Explicit no-PSI answers without facts should skip the workflow; no-PSI plus facts, missing contracts, unknown or malformed income, unknown tests, missing attribution, missing deduction facts, and missing business structure stay Evidence or `Accountant review`; never decide final PSI treatment or call it copy-ready.
13. For investment income distributions, collect itemized bank interest by payer/account, dividends with franked and unfranked amounts, franking credits, TFN withholding, managed fund/ETF/AMIT distribution components, and trust distribution statements for individual beneficiaries. Reconcile item totals to supplied aggregate interest or dividend/distribution totals. Missing statements, AMIT/cost-base adjustments, foreign components, trust distributions, franking uncertainty, and mismatched totals stay Evidence or `Accountant review`; never provide investment advice, broker integration, final CGT disposal calculation, or full trust return prep.
14. For general non-crypto/non-rental CGT event prep, collect top-level facts or itemized event rows with event type, asset description, owner or ownership share, acquisition date, disposal date, proceeds, cost base, incidental costs, losses, current-year and carried-forward capital loss facts, records, discount claim, discount timing or review signals, foreign-resident discount signals, and review signals such as mixed/private/business use, exemption, discount, concession, and main residence flags. For main residence review, collect claim status, ownership period, occupancy period, rental or business use, absence periods or absence-rule signals, spouse or partner main-residence conflict, and property records such as contract, settlement, rates, lease, occupancy, and absence evidence. For small-business CGT concession review, collect concession claim status, supplied concession type, business asset and active asset signals, entity/affiliate/connected entity facts, retirement exemption, rollover, 15-year exemption, 50% active asset reduction, business/private use, concession evidence, and source provenance. Explicit no-CGT answers without facts should skip the workflow; no-CGT plus facts, missing loss records, unknown carried-forward losses, discount uncertainty, foreign-resident discount signals, missing records, unknown or malformed amounts/dates, ownership uncertainty, missing or unknown main-residence periods, rental/business use, absence periods, spouse conflicts, property-record gaps, active asset uncertainty, concession type uncertainty, entity/affiliate/connected entity facts, item/top-level conflicts, partial item totals, and review flags stay Evidence or `Accountant review`. Preserve `0` proceeds, cost base, incidental costs, event losses, current-year losses, carried-forward losses, false discount claims, false foreign-resident discount signals, false review flags, false main-residence claim/use/conflict values, false concession values, and valid `0` or `0 days` main-residence values. Never work out capital gain/loss amounts, main residence treatment, small-business concession treatment, discount treatment, concession amounts, fill official ATO PDFs, lodge, or call the row copy-ready.
15. For crypto CGT prep, collect event type such as sale, swap, exchange, conversion, transfer, spend, gift, staking, or reward, asset, quantity, acquisition/disposal dates, cost base, proceeds, staking/rewards income, wallet or exchange records, ownership/entity, own-wallet transfer support, and both business and private use context flags. Explicit no-crypto answers without facts should skip the workflow; no-crypto plus facts, missing records, unknown or malformed amounts/dates, missing asset or exchange identity, missing ownership/entity, transfer ambiguity, exchange/convert/conversion disposal-like gaps, and missing either business or private use context stay Evidence or `Accountant review`; never decide CGT treatment or call it copy-ready.
16. For rental property worksheet prep, collect property identity, ownership, income, loan interest, repairs, capital works, depreciation, other expenses, records, private-use or holiday-home days, available-for-rent days, and net rental loss facts. Explicit no-rental-property answers without facts should skip the workflow; no-rental plus facts, missing records, unknown or malformed amounts, repairs-versus-capital ambiguity, missing private-use apportionment, capital works, depreciation, and net rental loss stay Evidence or `Accountant review`; never decide final rental treatment or call it copy-ready.
17. For sole-trader ABN prep, collect ABN, business name, activity, start/end dates, GST registration status/date, accounting basis, record system, business income streams, and expense categories. Keep private apportionment, home-business, motor vehicle, depreciation, capital expense, losses, PSI, business-versus-hobby, and non-commercial-loss facts visible in Evidence or `Accountant review`.
18. For BAS, prepare a worksheet only. Collect period coverage, 1A, 1B, GST-free/input-taxed sales, adjustments, PAYG labels, tax invoice evidence, accounting basis, and GST registration facts. Calculate totals where facts are complete, but do not lodge, finalise, fill official BAS forms, or support BAS lodgment.
19. For phone costs, keep phone plan/data, handset/device, insurance, and incidental-use rows separate. WFH fixed-rate blocks separate phone/data candidates. Employer-paid, reimbursed, or provided costs are blocked. Missing or unknown ABN phone GST status stays Evidence. Preserve free-form and unknown nested phone facts instead of blank rows. ABN/GST/BAS, mixed use, over-$300 decline-in-value, effective-life/method, and set/substantially-identical facts stay Evidence or `Accountant review`.
20. For assets, never claim full cost by default. Ask work-use and method facts, then present immediate, depreciation, low-value-pool, or review outcomes only when source-backed.
21. When full runtime execution is available, use the runtime intake command and output one print-first HTML pack only. Do not expose internal Python script names to users.

## Output Contract

When full runtime execution is available, the final handoff is HTML only. It must include prep-only boundary, manual-copy warning, intake summary, AI extraction confirmation table, individual return field guide, PAYG income statement rows, phone plan/device/incidental rows where supplied, itemized investment income rows, CGT schedule and item rows, ABN prep, BAS worksheet, missing facts, evidence queue, accountant-review queue, and source/provenance appendix.
