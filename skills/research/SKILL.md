---
name: research
description: ATO-first tax research that turns tax questions into conservative treatment recommendations and clear Accountant Review flags.
metadata:
  priority: 5
  promptSignals:
    phrases:
      - "ATO"
      - "Australian tax"
      - "claimable"
      - "GST"
      - "BAS"
      - "PAYG"
      - "FBT"
      - "CGT"
      - "ABN"
      - "sole trader"
      - "work from home"
      - "private health"
      - "super"
---

# TaxMate Australia Research

Use this skill for Australian tax-prep research and treatment decisions. It is not tax, legal, accounting, financial, BAS-agent, or registered-tax-agent advice, and it is not affiliated with or endorsed by the ATO. Be conservative, do not help overclaim, and mark ambiguous items as `Accountant review`.

## Shared Backend

Resolve the plugin root first:

```bash
export TAXMATE_AU_ROOT="${TAXMATE_AU_ROOT:-$(pwd)}"
```

Core commands:

```bash
"$TAXMATE_AU_ROOT/bin/taxmate-au-refresh" --query "<topic>"
"$TAXMATE_AU_ROOT/bin/taxmate-au-refresh" --all
"$TAXMATE_AU_ROOT/bin/taxmate-au-refresh" --recrawl
"$TAXMATE_AU_ROOT/bin/taxmate-au-validate"
```

ATO source pack:

```bash
"$TAXMATE_AU_ROOT/data/ato_knowledge_base"
```

Read `SCOPE_SUMMARY.md`, search `source_index.json` and `text/`, then refresh relevant pages before answering current tax questions. If refresh fails, say so and use cached sources only when useful.

## Answer Rules

- Use official ATO pages first unless the user asks for non-ATO sources.
- Include source URLs used.
- Use exact income-year labels, especially `2025-26`.
- Separate employee income/deductions, ABN business income/expenses, GST/BAS, PAYG, FBT, investment income/CGT, super, and private health.
- Never mix employee job expenses with ABN side-hustle expenses.
- For GST-registered users, do not call BAS `nil` if GST credits are being claimed.
- If GST credits are claimed, income-tax deductions generally use GST-exclusive amounts.
- For WFH 2025-26 employee fixed-rate method, use 70 cents per work hour only with valid records.
- For fixed-rate WFH, do not separately claim covered costs: energy, phone, internet, stationery, computer consumables.
- Separate depreciating assets/software/equipment from fixed-rate WFH running costs.
- Treat home occupancy and home-business claims as `Accountant review` unless facts clearly satisfy ATO criteria, because CGT main-residence consequences may apply.
- For ABN/no-income or pre-revenue expenses, record facts and mark deductibility/timing as `Accountant review` unless ATO guidance directly resolves it.
- For ETF/share questions, track annual tax statements, distributions, AMIT/member annual statements, cost base, DRP, disposals, trust non-assessable payments, CGT events, and capital losses.
- For crypto, track buys, sells, swaps, staking/rewards, transfers, wallet/exchange records, cost base, proceeds, and CGT events.
- For rental-property records, separate repairs, capital works/improvements, interest, agent fees, insurance, occupancy/private-use, and disposal-related CGT records.
- For CGT calculations, treat main-residence exemption, small business concessions, rollovers, foreign-resident rules, and carried-forward losses as `Accountant review`.
- For PAYG, use calculators only as estimates. For payroll, use official ATO withholding tables after refreshing PAYG/tax-table pages.
- For PAYG instalments, STP/income statements, and TPAR, refresh relevant ATO pages and mark uncertain obligations as `Accountant review`.
- For FBT, use calculator output only after taxable value is known. Car benefits, entertainment, exemptions, employee contributions, and reportable fringe benefit amounts are `Accountant review`.
- For super guarantee, use ordinary time earnings and the SG rate for the payment date; for 2025-26, refresh ATO sources before relying on 12%.
- For stamp duty, route to official state/territory revenue-office sources. Do not embed duty rate tables.
- For business-versus-hobby and non-commercial-loss questions, default to `Accountant review` unless ATO guidance directly resolves the facts.
- For private health, use the insurer tax statement and ATO private health rebate/Medicare levy surcharge pages.

## Workflow

1. Read `data/ato_knowledge_base/SCOPE_SUMMARY.md`.
2. Search `source_index.json` and `text/`.
3. Run `"$TAXMATE_AU_ROOT/bin/taxmate-au-refresh" --query "<topic>"`.
4. Re-read changed or relevant text.
5. Answer with conclusion, conservative treatment, evidence needed, source URLs, and accountant-review flags.

## Invocation

Use `$taxmate-australia:research` when plugin skills are available.
