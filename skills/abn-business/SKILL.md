---
name: abn-business
description: Sole trader and small business income, deductions, PSI, business-versus-hobby, losses, and evidence.
---

# ABN Business

Generated from TaxMate Australia source metadata. Verify volatile values before relying on them.

Use for ABN and business income or expenses. Do not use for employee-only expenses, GST/BAS lodgment, or CGT disposal calculations.

## Source workflow

1. Read `references/rules.md` before classifying tax treatment.
2. Read `references/evidence.md` before deciding record status.
3. Check `references/sources.json` for source URLs, checked-at dates, and metadata-only sources.
4. Verify volatile rates, thresholds, caps, due dates, and income-year values against the official source before relying on them.

## Safety rules

- Do not fabricate records, source support, source checks, or evidence.
- Do not hide income, omit private use, suppress missing evidence, or remove `Accountant review` flags.
- Do not treat metadata-only sources as source-backed tax treatment without explicit verification.
- Keep ambiguous, mixed-use, stale, unsupported, or material uncertainty as `Accountant review`.
- Do not lodge, submit, or present outputs as lodging-ready advice.

## Output states

- Supported record
- Claim candidate
- must not be bypassed
- Not claimable
- Insufficient evidence
- Accountant review

## Required facts

- income year or effective period
- taxpayer/entity and ownership
- business/private/employment purpose
- amounts excluding and including GST where relevant
- dates acquired, used, paid, received, and disposed
- records held and missing evidence
- prior claims, reimbursements, and duplicate-risk factors
