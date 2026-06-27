---
name: calculators
description: Run TaxMate Australia bounded calculator scaffolds for PAYG estimates, BAS arithmetic, CGT gains, FBT gross-up arithmetic, super guarantee minimums, and stamp-duty source routing.
metadata:
  internal: true
  priority: 4
---

# TaxMate Australia Calculators

Runtime requirements:

- Bash
- Python 3.9+

Use this full-runtime skill for bounded tax-prep calculations. It is not professional advice, payroll advice, lodgment support, or confirmation of entitlement. Keep outputs labelled as estimates or scaffolds where applicable.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit, lodge, file, transmit, finalise, or send prepared material to the ATO.
- Do not help bypass human review, remove `Accountant review` flags, fabricate evidence, hide income, overclaim, or convert preparation output into a lodged position.

Run:

```bash
export TAXMATE_AUSTRALIA_ROOT="${TAXMATE_AUSTRALIA_ROOT:-$(pwd)}"
"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" calc <bas|super|fbt|cgt|payg|stamp-duty> [flags]
```

## Rules

- PAYG is estimate-only; use official ATO withholding tables for payroll.
- BAS arithmetic is not lodgment advice; GST labels need accountant review.
- CGT output depends on user-supplied cost base, proceeds, dates, losses, and eligibility.
- FBT output assumes taxable value is already known.
- Super guarantee uses ordinary time earnings and the SG rate for the payment date.
- Stamp duty routes to official state/territory sources; no embedded rate tables.
- Keep all review flags in the final answer.
