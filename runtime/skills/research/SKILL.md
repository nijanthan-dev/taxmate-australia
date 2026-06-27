---
name: research
description: ATO-first tax research that turns tax questions into conservative treatment recommendations and clear Accountant Review flags. Use when full-runtime ATO refresh or source-backed treatment review is needed.
compatibility: Full-runtime skill for Claude Code, Cowork, and Codex. Requires repo checkout, bash, Python 3.9+, Git, and network for refresh.
metadata:
  internal: true
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

Use this full-runtime skill for Australian tax-prep research and treatment decisions. It is not tax, legal, accounting, financial, BAS-agent, or registered-tax-agent advice, and it is not affiliated with or endorsed by the ATO. Be conservative, do not help overclaim, and mark ambiguous items as `Accountant review`.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit, lodge, file, transmit, finalise, or send prepared material to the ATO.
- Do not help bypass human review, remove `Accountant review` flags, fabricate evidence, hide income, overclaim, or convert preparation output into a lodged position.

## Shared Backend

Runtime requirements:

- Bash
- Python 3.9+
- Git

Do not use Go commands or Go module files. This runtime is bash plus Python.

Resolve the plugin root first:

```bash
export TAXMATE_AUSTRALIA_ROOT="${TAXMATE_AUSTRALIA_ROOT:-$(pwd)}"
```

Core commands:

```bash
"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" refresh --query "<topic>"
"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" refresh --all
"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" refresh --recrawl
"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" validate
```

ATO source pack:

```bash
"$TAXMATE_AUSTRALIA_ROOT/data/ato_knowledge_base"
```

Read `SCOPE_SUMMARY.md`, search `source_registry.json` and `.cache/ato/text/`, then refresh relevant pages before answering current tax questions. Do not use old `data/ato_knowledge_base/text`, `source_index`, or `source_manifest` paths. If refresh fails, say so and use cached sources only when useful.

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
2. Search `source_registry.json` and `.cache/ato/text/`.
3. Run `"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" refresh --query "<topic>"`.
4. Re-read changed or relevant text.
5. Answer with conclusion, conservative treatment, evidence needed, source URLs, and accountant-review flags.
