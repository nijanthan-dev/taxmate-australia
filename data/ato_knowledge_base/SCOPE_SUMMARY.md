# Official Source Scope Summary

Generated topic references from official ATO pages are refreshed into `source_registry.json` and derived into permanent source coverage during generation.

## Coverage

- Individual tax return setup, records, deductions, income to declare, tax offsets.
- Employee deductions, including working from home, fixed-rate method, actual-cost method, occupancy expenses, tools, software, phone, internet, depreciating assets, travel, clothing, self-education, memberships, and tax affairs costs.
- ABN/sole-trader topics, including assessable business income, business deductions, business losses, non-commercial-loss indicators, business-versus-hobby boundaries, PSI, home-based business expenses, home-business CGT implications, and small-business depreciation.
- GST/BAS, including registration, GST credits, tax invoices, when to charge GST, effect of GST credits on income-tax deductions, BAS, due dates, PAYG instalments, PAYG withholding, adjustments, TPAR, and GST labels.
- Employer/reporting topics, including Single Touch Payroll, income statements, PAYG withholding annual reporting, and contractor-payment reporting through TPAR.
- Investments, including investment income, shares/units, ETF-like unit holdings, crypto records, rental-property records, CGT events, CGT discount, records, dividend reinvestment plans, trust non-assessable payments, share investing versus trading, and capital losses.
- Calculators/scaffolds, including PAYG estimate-only, BAS arithmetic, FBT gross-up arithmetic, CGT gain/discount arithmetic, SG minimum contributions, and stamp-duty source routing.
- Super, including personal super contributions, deductions/records around super, and employer super guarantee.
- Private health, including private health insurance statements, rebate, Medicare levy, Medicare levy surcharge, thresholds, family/dependants, and tax return treatment.

## Dynamic Values

- Rates, thresholds, caps, cents-per-kilometre amounts, WFH rates, GST thresholds, tax brackets, super rates, FBT values, Medicare thresholds, asset write-off thresholds, and due dates are volatile.
- Volatile values live only in topic `references/current-values.json` with source URL, title, source last-updated date when available, checked-at date, content hash, context, and reuse warning.
- Before using a volatile value, refresh or verify the official source for the requested income year or effective period.
- If current verification is unavailable, stale, conflicting, or wrong-year, mark `Accountant review`.

## Known Limits

- This pack is ATO-first. Stamp duty is source-routed to state revenue offices only; it does not include embedded state duty rate tables.
- This pack does not include ASIC, ABR, private insurers, brokers, super funds, app marketplaces, software vendors, or accountant-specific guidance.
- Ten seed URLs returned 404, but the crawl found current moved alternatives for the main affected topics: tools/equipment, investment income, GST credit effects, personal super contributions, and business deductions.
- ATO search returned a 502 for `business or hobby`; use business-losses, assessable-income, PSI, and home-business pages for now.
- This is a source pack, not advice. Any ambiguous or material classification should be marked `Accountant review`.

## Files

- `source_registry.json`: active source registry and source metadata used by refresh and generation.
- `source_coverage.json`: global required field for every indexed source with coverage status and provenance.
- `README.md`: concise source-pack overview.
- `skills/*/references/`: compact generated topic references and per-source provenance.
- `.cache/ato/`: ignored local refresh cache for fetched HTML and extracted text.
