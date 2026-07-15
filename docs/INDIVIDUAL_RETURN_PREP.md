# Individual Return Prep

Use this path when someone asks how to prepare an Australian individual tax return with TaxMate.

## Boundary

TaxMate is prep-only. It helps collect facts, preserve source links, show missing evidence, and build a manual-copy handoff for myTax, paper ATO form, or accountant handoff. It does not lodge, submit, finalise, fill official ATO PDFs, or give final tax advice.

## Guidance Skill Path

Use `taxmate-australia-individual-return` first for a broad checklist. Route specialist sections to installed TaxMate Australia topic skills when facts appear:

- `taxmate-australia-employment-deductions` for PAYG and work deductions.
- `taxmate-australia-work-from-home` for WFH hours, records, holidays, and fixed-rate or actual-cost support.
- `taxmate-australia-private-health-medicare` for itemized private health statement lines, Medicare levy and surcharge review signals, spouse periods and income-test facts, and dependant child or student facts.
- `taxmate-australia-abn-business` for sole-trader, PSI, business-versus-hobby, and losses.
- `taxmate-australia-gst-bas` for BAS worksheets only.
- `taxmate-australia-shares-etfs-managed-funds`, `taxmate-australia-capital-gains-tax`, `taxmate-australia-crypto-assets`, and `taxmate-australia-property-rental-cgt` for investment, crypto, rental property worksheet, and CGT review.
- `taxmate-australia-records-evidence` for missing records and substantiation gaps.
- `taxmate-australia-workbook` or `taxmate-australia-taxpack` only for output-layer guidance, not tax logic.

Ask a full intake, not a short interview. Keep unknown, ambiguous, mixed-use, GST/BAS, CGT, PSI, foreign, ESS, ETP/lump sum, rental, company, trust, partnership, and entity-return items in Evidence or `Accountant review` unless official sources clearly resolve the prep step.

For PAYG salary and wages prep, collect each income statement by payer, employer or payer ABN, occupation, gross salary/wages, tax withheld, allowances, reportable fringe benefits, reportable employer super contributions, lump sum A/B/D/E labels, statement evidence, and finalised/tax-ready status. Reconcile item totals to supplied aggregate PAYG gross and withholding. Keep missing or unfinalised statements, unknown payer details, malformed amounts, ambiguous allowances/RFBA/RESC/lump sum labels, no-PAYG answers plus facts, and mismatched totals in Evidence or `Accountant review`.

For private health and Medicare prep, keep every private health statement line separate and every supplied value as an atomic labelled fact. Collect health insurer or fund, membership or policy identifier, benefit code, premiums eligible for rebate, rebate received, tax claim code, cover days or period, and statement evidence. Also collect private hospital cover status, Medicare levy exemption or reduction signals, Medicare levy surcharge income or tier signals, spouse period and income-test facts, and dependant child or student facts. Missing or unknown statements, no-cover or partial-year uncertainty, malformed amounts or dates, unsupported codes, source gaps, and spouse, dependant, levy, or surcharge uncertainty stay Evidence or `Accountant review`. Recursively exclude blank or no-op note and metadata containers before alias merge or rendering, while preserving every real sibling in a mixed container. Normalize explicit dependant collection or count denials to integer 0 before collection filtering, and keep denial-plus-positive count or item conflicts visible. Treat temporal, partial, mixed, or qualified-negative cover wording as review input before categorical no-cover classification. Carry matching valid source URLs and checked-at dates onto the review row whenever supplemental facts survive. Preserve row-specific source URLs, checked-at dates, unknown sibling facts, explicit evidence denials, `false` spouse or cover, `0` dependants, and supplied `0` premium, rebate, or cover-day amounts. Supplied zero or unsupported benefit and tax claim codes stay visible but remain Evidence or `Accountant review`; preservation does not make a code valid. Exact destinations are field- and context-specific; insurer identifiers, membership identifiers, cover periods, evidence, levy/surcharge context, and spouse income aggregates do not inherit a destination from another fact in the row. TaxMate does not calculate levy, surcharge, rebate, tax claim code, or final entitlement.

For investment income prep, collect itemized bank interest by payer/account, dividends with franked/unfranked amounts, franking credits and withholding, managed fund/ETF/AMIT distribution statement components, and trust distribution statement facts for individual beneficiaries. Reconcile item totals to supplied aggregate interest/dividend totals. Keep missing statements, AMIT/cost-base adjustments, foreign components, trust distributions, franking uncertainty, and mismatched totals in Evidence or `Accountant review`.

Individual partnership-share and residual trust-beneficiary/share statements use a separate supplementary-income route. Collect entity name, ABN/TFN where supplied, statement status, income and loss components, withholding, credits, source URLs, checked-at dates, and evidence status. This route does not duplicate managed fund/ETF/AMIT or investment trust-distribution rows. Missing statements, malformed amounts, mixed components, losses, uncertain credits, entitlement or allocation questions, and entity-return context stay Evidence or `Accountant review`. Full partnership and trust returns remain future work under #42 and #43.

Company, trust, and partnership return skeletons use separate prep-only sections. Company intake collects identity, ABN/ACN/TFN, income year, residency, activity, directors/shareholders, and related-entity signals. Trust intake collects identity, TFN/ABN, trustee, type, income year, residency, deed/election evidence, and beneficiary signals. Partnership intake collects identity, ABN/TFN, income year, partners, share percentages, activity, accounting basis, and agreement evidence. Flat, nested, and itemized entity inputs share the same fail-closed routing contract. Missing, malformed, conflicting, structural, residency, related-party, deed, beneficiary, partner-share, or accounting-basis facts remain Evidence or `Accountant review`. Entity facts never enter individual rows.

Company and partnership entity sections also accept shared itemized `income_items` and `deduction_items`, supplied totals, accounting-record evidence, GST/BAS interaction, private/non-deductible, related-party, capital/depreciation, PSI, and business-structure signals. Company categories follow the 2026 company income and expense instructions. Partnership categories follow the 2026 partnership income, deduction, trading-stock, and capital-allowance instructions. Unknown categories, malformed/non-finite amounts, missing evidence, alias conflicts, unsupported facts, total mismatches, invalid provenance, and review signals remain Evidence or `Accountant review`; valid `0`, `false`, and negative supplied values stay visible. Company dividends/franking/Division 7A and company losses/depreciation/capital allowances remain later review slices. Partnership loss allocation and detailed GST/BAS or PSI determination remain later review slices. TaxMate never decides final treatment, calculates taxable income or deductions, fills official forms, or lodges.

Uncommon income uses narrow review labels only when verified official source coverage supports them: compensation/insurance payments and scholarships/prizes/awards. Common insurance wording such as payout, settlement, proceeds, or claim routes to the compensation/insurance review even when an earlier field says only `other income`. Unsupported, unknown, mixed, entity-related, malformed, or free-form residual income stays preserved as an uncommon-income review row with evidence gaps visible. TaxMate does not decide final treatment, destination, or copy-ready values.

For rental property prep, collect property identity, ownership, income, loan interest, repairs, capital works, depreciation, other expenses, private-use or holiday-home days, available-for-rent days, records, and net rental loss facts. Treat repairs-versus-capital ambiguity, private use, depreciation, capital works, and net rental loss as review-first; TaxMate prepares a worksheet only.

For sole-trader ABN prep, collect ABN, business name, activity, start/end dates, GST registration status/date, accounting basis, record system, business income streams, and expense categories. Keep private apportionment, home-business, motor vehicle, depreciation, capital expense, losses, PSI, business-versus-hobby, and non-commercial-loss facts visible in Evidence or `Accountant review`.

For BAS worksheet prep, collect BAS period and coverage, 1A GST collected, 1B GST credits, GST-free sales, input-taxed sales, adjustments, PAYG instalments or withholding where relevant, accounting basis, GST registration status/date, and tax invoice evidence. Missing invoices, unknown basis, mixed/private-use GST credits, and BAS uncertainty stay visible; TaxMate does not lodge, finalise, or fill official BAS forms.

For phone deductions, collect employee/ABN/both context, whether the user paid, employer paid/reimbursed/provided flags, WFH fixed-rate versus actual-cost method, phone plan amount/months/itemised status/4-week basis/work-use percent, handset cost/date/work-use/receipt, incidental-use facts, changed work-use facts, phone insurance, ABN/GST status, and tax invoice facts where relevant. WFH fixed-rate blocks separate phone/data candidates. Employer-paid, reimbursed, or provided costs are blocked. Missing or unknown ABN phone GST status stays visible as Evidence. Preserve free-form and unknown nested phone facts instead of blank rows. ABN/GST/BAS, mixed-use, over-$300 decline-in-value, effective-life/method, and set/substantially-identical facts stay `Accountant review`.

For itemized deduction prep, collect one row per deduction with label/type, amount, receipt or statement evidence, reimbursement, employer-paid/provided flags, work/private split, GST/BAS interaction, duplicate-risk facts, and source provenance. Structured rows cover gifts/donations, cost of managing tax affairs, income protection insurance, self-education, union/professional fees, work travel/car/public transport, and tools/equipment/assets at review-first depth. Missing receipts, malformed or unknown amounts, reimbursements, employer-paid/provided costs, mixed/private use, GST/BAS overlap, duplicate-risk, unsupported deduction types, and asset/depreciation method facts stay Evidence or `Accountant review`.

For personal super contribution deduction prep, collect fund, member, contribution date, contribution amount, notice of intent, fund acknowledgement, intended deduction amount, concessional-cap review signals, and Division 293 review signals. Missing notice, missing fund acknowledgement, contribution amount/date uncertainty, cap uncertainty, and Division 293 uncertainty stay Evidence or `Accountant review`.

For offset routing, collect spouse, super, zone/remote, and other offset signals only as source-backed review rows. Preserve false offset claims and `0` amounts. Unsupported or uncertain offsets, missing eligibility evidence, income-test uncertainty, zone/remote residency gaps, and unknown amounts stay Evidence or `Accountant review`.

For general non-crypto/non-rental CGT event prep, collect top-level facts or itemized event rows with event type, asset description, owner or ownership share, acquisition date, disposal date, proceeds, cost base, incidental costs, losses, current-year and carried-forward capital loss facts, records, discount claim, discount timing or review signals, foreign-resident discount signals, main residence claim facts, ownership and occupancy periods, rental/business use, absence-period signals, spouse/partner main-residence conflict signals, property record evidence, rental-property overlap signals, small-business CGT concession claim status, concession type, business asset and active asset signals, entity/affiliate/connected entity facts, retirement exemption, rollover, 15-year exemption, 50% active asset reduction, business/private use, and concession evidence. Explicit no-CGT answers skip only when no CGT facts exist. No-CGT plus facts, missing loss records, unknown carried-forward losses, discount uncertainty, foreign-resident discount signals, missing records, unknown or malformed dates or amounts, ownership uncertainty, active asset uncertainty, concession type uncertainty, entity/affiliate/connected entity facts, item/top-level conflicts, partial item totals, and review flags stay visible in Evidence or `Accountant review`. TaxMate may reconcile supplied event totals to item totals as prep evidence only; it does not work out capital gain/loss amounts, apply discount treatment, determine main residence treatment, or work out small-business concession amounts.

## Runtime Coverage Matrix

`./scripts/taxmate coverage audit` compares verified ATO source topics with runtime functions, tests, docs, and linked issues. Source metadata is not treated as structured runtime support unless the manifest says so.

| Topic | Runtime status | Notes |
| --- | --- | --- |
| Phone plan/data/device/incidental use | Structured | Dedicated rows, WFH fixed-rate block, evidence queue, ABN/GST/BAS review routing. |
| WFH fixed-rate | Structured | 2025-26 calendar helper with records/method review. |
| CGT, crypto, rental, investment workflows | Structured | Review-first rows with source provenance; no final treatment. |
| Partnership/trust share statements | Structured | Individual statement facts only; separate from investment distributions and full entity returns. |
| Entity trust/partnership statements | Structured | Prep-only beneficiary and partner statement rows in isolated entity-return sections; no allocation or entitlement decision. |
| Uncommon income | Review-first | Narrow compensation/insurance and scholarship/prize/award labels; unsupported facts stay free-form review rows. |
| Itemized deductions | Structured | Gifts/donations, tax affairs, income protection, self-education, union/professional fees, travel/car/public transport, tools/equipment/assets; all review-first with evidence and duplicate/GST/private-use queues. |
| Personal super contribution deductions | Structured | Notice of intent, fund acknowledgement, intended deduction, cap, and Division 293 review signals. |
| Offset routing | Structured | Spouse/super/zone/remote/other offset facts route to Evidence or `Accountant review`; no final offset calculation. |
| WFH actual-cost and occupancy | Review-only | Actual-cost comparison and occupancy/main-residence risk stay review-first. |
| ABN categories | Triage-only | Summary/category worksheet exists; complex categories stay review-first. |
| GST/BAS special topics | Triage-only | Core worksheet exists; WET/LCT/fuel tax/reverse charge/groups/time limits/cancellation stay review-only. |
| Private health, Medicare, spouse, dependants | Structured | Itemized statement lines, cover periods, levy/surcharge review signals, spouse/dependant facts, row-specific provenance, and evidence/review queues; no final calculation. |
| Government payments | Review-only | Generic field visible only; detailed payment-type workflow remains open. |
| FBT/RFBA | Triage-only | RFBA preserved from PAYG; no FBT calculation. |

## Plugin Runtime Path

Install the plugin first.

Plugin prerequisites are Codex or Claude Code, Node.js 20+ for the MCP launcher, Bash, and Python 3.9+.

Codex:

```bash
codex plugin marketplace add nijanthan-dev/taxmate-australia
codex plugin add taxmate-australia@taxmate-local-marketplace
```

Claude Code:

```bash
claude plugin marketplace add nijanthan-dev/taxmate-australia
claude plugin install taxmate-australia@taxmate-australia
```

Then ask your agent:

```text
Use TaxMate Australia to write sample individual answers and render the individual-return HTML guide.
```

The plugin runtime can also run the underlying `intake` command family through TaxMate tools. Developer fallback from a cloned repository:

```bash
./scripts/taxmate intake individual --help
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
./scripts/taxmate coverage audit
```

Open the HTML in a browser and print or save as PDF. Every worksheet row and queue item uses the same runtime-owned handoff contract: labelled supplied facts, a nonblank next action, a verified destination or explicit non-entry/review wording, why the action applies, and supporting provenance. Output layers render that contract and do not infer destinations from row names, broad topic links, or unverified AI target labels.

The seven handoff actions are: enter reviewed value, answer guided question, retain evidence, resolve before entry, accountant handoff only, not entered directly, and destination requires review. `Accountant review` always wins over entry-ready actions. Missing, conflicting, malformed, unsupported, or stale mapping state fails closed to evidence or review wording.

Private health and Medicare rows use atomic field actions. A verified location can remain visible as context on an `Accountant review` row, but it does not make the fact entry-ready.

- Tax claim codes A, B, and C: the tax claim code and statement fields J, K, and L can map to verified myTax and paper locations after review.
- Tax claim code D: the myTax statement line is read-only; the tax claim code and J/K/L fields can map to verified paper locations after review.
- Tax claim code E: the tax claim code can map in myTax, while J/K/L are not entered there; the tax claim code and J/K/L fields can map to verified paper locations after review.
- Tax claim code F: the tax claim code can map in myTax and paper, while J/K/L are not entered in either channel.
- M1: the exemption-category answer and supported full/half exemption day values can map to verified myTax questions. Paper mapping is limited to labels V and W; the generic paper category question requires review. An explicit no-exemption answer with no category or day values makes those detail fields not entered directly. False-plus-category or positive-day conflicts, true-plus-no-positive-day conflicts, malformed day values, and invalid totals fail closed.
- M2: question E maps only from an explicit local answer to whether the user and all dependants had an appropriate level of private patient hospital cover for the full income year. A `true` answer also requires `365` supplied cover days, an explicit appropriate-cover signal, and no period conflict. Days not liable can map to paper label A only after an explicit `No` at E. myTax may skip its days field after the income check, so that channel retains conditional review wording. E `Yes` makes the days field non-entry; missing or conflicting E context requires review.
- Spouse: the had-spouse answer can map to the verified myTax question. The generic paper had-spouse destination and spouse income aggregates require review.

Every direct route requires the exact verified source ID, canonical URL, content hash, field binding, and row context. TaxMate does not calculate levy, surcharge, rebate, entitlement, or final tax.

## Review Rules

- Explicit no-income, no-crypto, no-PSI, or no-payment answers skip only when no other facts exist.
- No-answer plus facts stays Evidence and must remain visible in answer text and review queues.
- Valid falsey values such as `0` and `false` stay visible.
- `0` withholding, `0` allowances, `0` RFBA, `0` RESC, and false finalised/tax-ready flags stay visible in PAYG rows.
- `false` spouse, `false` private health cover, `0` dependants, and supplied `0` premium, rebate, or cover-day amounts stay visible in private health and Medicare review rows; supplied zero or unsupported benefit and tax claim codes also stay visible but remain Evidence or `Accountant review`.
- `0` franking credits, `0` withholding, and `false` foreign components stay visible in investment rows.
- `0` beneficiary or partner components, `0` ownership/share percentages, negative loss shares, and `false` present-entitlement or distribution signals stay visible in isolated entity-return statement rows.
- `0` company/partnership income, expense, stock, and capital-allowance facts, negative supplied worksheet amounts, and `false` GST/BAS, private-use, non-deductible, election, PSI, structure, or balancing-adjustment signals stay visible in isolated entity worksheets.
- `0` ABN income, `0` ABN expenses, `0` itemized business income or expense categories, and false GST registration stay visible in ABN and BAS prep rows.
- `0` GST collected, `0` GST credits, `0` GST-free sales, `0` input-taxed sales, `0` adjustments, `0` PAYG instalments, and `0` PAYG withholding stay visible in BAS worksheet rows.
- `0` CGT proceeds, cost base, incidental costs, event losses, current-year losses, carried-forward losses, main residence ownership/occupancy/absence period text such as `0 days`, and `false` exemption, discount claim, foreign-resident discount, concession, business-asset, active-asset, entity/affiliate/connected-entity, retirement, rollover, 15-year, 50% reduction, business-use, private-use, main-residence-claim, rental/business-use, and spouse/partner conflict flags stay visible in CGT schedule and item rows.
- `0` deduction amounts, personal super intended deduction amounts, offset amounts, and `false` reimbursement, employer-paid/provided, GST/BAS overlap, duplicate-risk, Division 293, cap-review, private-use, and offset-claim flags stay visible in deduction, personal-super, and offset rows.
- AI-extracted values are not used unless the user confirms them.
- Output layers stay output-only; runtime intake and topic skills own tax-prep logic.
