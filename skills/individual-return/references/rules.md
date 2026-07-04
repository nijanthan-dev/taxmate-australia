# Individual Return Rules

## Verified official-source content

This orchestration skill does not bundle extracted tax-treatment summaries. It coordinates installed topic skills and full-runtime output generation. Treat calculation rates, thresholds, labels, and income-year-specific rules as unverified until a topic skill or current official source supplies provenance with source URL, checked-at date, content hash, and effective period.

## Metadata-only official-source links

- ATO individual tax return instructions: https://www.ato.gov.au/forms-and-instructions/individual-tax-return-instructions-2026
- ATO working from home fixed-rate method: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method
- ATO working from home actual-cost method: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/actual-cost-method
- ATO business activity statements: https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas
- ATO employee share schemes: https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/employee-share-schemes
- ATO employee share scheme statement: https://www.ato.gov.au/forms-and-instructions/employee-share-scheme-statement
- ATO employment termination payments withholding: https://www.ato.gov.au/tax-rates-and-codes/payg-withholding-schedule-11-tax-table-for-employment-termination-payments
- ATO lump sum payment in arrears: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/lump-sum-payment-in-arrears
- ATO superannuation pensions and annuities: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/superannuation-pensions-and-annuities
- ATO superannuation lump sums withholding: https://www.ato.gov.au/tax-rates-and-codes/schedule-12-tax-table-for-superannuation-lump-sums
- ATO superannuation income streams withholding: https://www.ato.gov.au/tax-rates-and-codes/schedule-13-tax-table-for-superannuation-income-streams
- ATO foreign and worldwide income: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income
- ATO Australian resident foreign and worldwide income: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/australian-resident-for-tax-purposes-foreign-and-worldwide-income
- ATO foreign and temporary resident income: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/foreign-and-temporary-resident-income
- ATO tax-exempt foreign employment income: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/tax-exempt-income-from-foreign-employment
- ATO foreign income tax offset rules guide: https://www.ato.gov.au/forms-and-instructions/foreign-income-tax-offset-rules-guide-2026
- ATO investment income: https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/investment-income
- ATO investing in bank accounts and income bonds: https://www.ato.gov.au/individuals-and-families/investments-and-assets/investing-in-bank-accounts-and-income-bonds
- ATO shares, funds and trusts: https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts
- ATO refund of franking credits for individuals: https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals
- ATO trust non-assessable payments CGT event E4: https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments/trust-non-assessable-payments-cgt-event-e4
- ATO personal services income: https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income
- ATO crypto asset investments: https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments
- ATO keeping crypto records: https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments/keeping-crypto-records
- ATO crypto assets and business: https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/crypto-assets-and-business
- ATO records for rental properties and holiday homes: https://www.ato.gov.au/individuals-and-families/investments-and-assets/property-and-land/residential-rental-properties/records-for-rental-properties-and-holiday-homes
- ATO property and capital gains tax: https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax
- ATO using your home for rental or business: https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax/your-main-residence-home/using-your-home-for-rental-or-business
- Fair Work 2025 public holidays: https://www.fairwork.gov.au/employment-conditions/public-holidays/2025-public-holidays
- Fair Work 2026 public holidays: https://www.fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays

Metadata-only links are routing and verification leads, not enough by themselves for a copy-ready tax treatment.

## TaxMate conservative summary

Individual-return intake is a coordinator. It should collect facts, preserve evidence gaps, route to the most specific installed skill, and assemble an HTML preparation handoff. It should not duplicate detailed tax logic from PAYG, WFH, ABN, GST/BAS, private-health, superannuation, investment, records, workbook, or taxpack skills. If full-runtime tooling is available, use it for deterministic calendars, candidate rows, queues, and HTML rendering; keep portable skill output as guidance when no checkout/runtime exists.

WFH calendar helpers may automatically exclude only supported income-year state-wide public holidays. Regional, capital-city-only, sector-only, and partial-day public holidays need user facts before they affect hours; otherwise keep the affected WFH period as Evidence or `Accountant review`.

PAYG salary and wages handling is prep-only. Collect primary and secondary income statement rows with payer name, employer or payer ABN, occupation, gross salary/wages, tax withheld, allowances, reportable fringe benefits, reportable employer super contributions, lump sum A/B/D/E labels, statement evidence, and finalised/tax-ready status. Reconcile item totals to any supplied aggregate PAYG gross and withholding.

Explicit no-PAYG answers without facts should skip the workflow. No-PAYG plus facts, missing or unfinalised income statements, unknown payer names or ABNs, unknown or malformed gross/withholding/allowance/RFBA/RESC/lump sum values, direct alias conflicts, ambiguous lump sum labels, and aggregate-vs-item mismatches stay Evidence or `Accountant review`. Preserve valid falsey values such as `0` withheld, `0` allowances, `0` RFBA, `0` RESC, and `false` finalised flags.

ESS handling is prep-only. Collect statement evidence, employer or scheme labels, taxed-upfront discount, deferred discount, foreign-source discount, TFN amount withheld, and itemized statement rows. Missing statements, malformed or conflicting amount fields, deferred taxing-point uncertainty, and foreign-source splits stay Evidence or `Accountant review`.

ETP, lump sum in arrears, super lump sum, and super income stream handling is prep-only. Collect official statements, payer or fund labels, payment type, payment dates, taxable and tax-free components, prior-year allocation where relevant, and withholding. Explicit no-payment answers without facts should skip the workflow; no-payment answers plus amounts, unknown statements, malformed amounts, and incomplete prior-year allocation stay Evidence or `Accountant review`.

Foreign income handling is prep-only. Collect source statements, country, income type, amount, foreign tax paid, exchange-rate support, residency-specific or temporary-resident evidence, foreign income tax offset claims, and exempt foreign employment claims. Explicit no-foreign-income answers without facts should skip the workflow; no-foreign-income plus amount facts, missing statements, unknown or malformed amounts, exchange-rate gaps, missing residency or temporary-resident evidence, and offset claims without foreign tax paid evidence stay Evidence or `Accountant review`.

Investment income distribution handling is prep-only. Collect itemized bank interest, dividends/franking, managed fund/ETF/AMIT components, and trust distribution statement facts for individual beneficiaries. Reconcile item totals to supplied aggregate interest or dividend/distribution totals. Missing statements, AMIT/cost-base adjustments, foreign components, trust distributions, franking uncertainty, and mismatched totals stay Evidence or `Accountant review`. Preserve valid falsey values such as `0` franking credits, `0` withholding, and `false` foreign components. Do not provide full trust return prep, final CGT disposal calculation, investment advice, or broker integrations.

General CGT event handling is prep-only. Collect one non-crypto/non-rental event type, asset description, owner or ownership share, acquisition date, disposal date, proceeds, cost base, records, and basic review signals such as mixed/private/business use, exemption, discount, and concession flags. Explicit no-CGT answers without facts should skip the workflow; no-CGT plus facts, missing records, unknown or malformed amounts/dates, ownership uncertainty, and review flags stay Evidence or `Accountant review`. Preserve valid falsey values such as `0` proceeds, `0` cost base, and `false` exemption, discount, concession, business-use, and private-use flags. Completed CGT rows stay `Accountant review`; do not calculate a final capital gain or loss, decide final CGT treatment, fill official ATO forms, or call it copy-ready.

PSI deep handling is prep-only. Collect personal services income amount and type, contract or invoice evidence, results test, 80% client concentration, unrelated clients test, employment test, business premises test, personal services business determination, attribution, deductions, and business structure. Explicit no-PSI answers without facts should skip the workflow; no-PSI plus facts, missing contracts, unknown or malformed income, unknown tests, missing attribution, missing deduction facts, and missing business structure stay Evidence or `Accountant review`. Completed PSI rows stay `Accountant review`; do not decide final PSI treatment.

Crypto CGT handling is prep-only. Collect event type such as sale, swap, exchange, conversion, transfer, spend, gift, staking, or reward, asset, quantity, acquisition and disposal dates, cost base, capital proceeds, staking or rewards income, wallet/exchange records, owner or entity, own-wallet transfer support, and both business and private use context flags. Explicit no-crypto answers without facts should skip the workflow; no-crypto plus facts, missing records, unknown or malformed amounts/dates, missing asset or exchange identity, missing ownership/entity, transfer ambiguity, exchange/convert/conversion disposal-like gaps, and missing either business or private use context stay Evidence or `Accountant review`. Completed crypto rows stay `Accountant review`; do not decide final CGT treatment.

Rental property worksheet handling is prep-only. Collect property identity, ownership, rental income, loan interest, repairs, capital works, depreciation, other expenses, records, private-use or holiday-home days, available-for-rent days, and net rental loss facts. Explicit no-rental-property answers without facts should skip the workflow; no-rental plus facts, missing records, unknown or malformed amounts, repairs-versus-capital ambiguity, missing private-use apportionment, capital works, depreciation, and net rental loss stay Evidence or `Accountant review`. Completed rental rows stay `Accountant review`; do not decide final rental treatment.

## Accountant review

Use `Accountant review` for ambiguity, missing evidence, mixed-use items, GST/BAS uncertainty, PSI, non-commercial losses, business-versus-hobby, home-business occupancy, CGT, FBT, uncommon income, unsupported AI extraction, unknown required facts, and any source conflict. Review status wins over evidence, used, skipped, ATO-label, tab-kind, status-kind, or styling fields in all rendered queues and guide rows.
