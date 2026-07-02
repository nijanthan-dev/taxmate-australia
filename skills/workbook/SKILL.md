---
name: taxmate-australia-workbook
description: Create accountant-facing Excel workbook outputs from reviewed TaxMate Australia data. Use for taxpayer/spouse-separated and combined tax expense workbooks, BAS/GST summaries, ETF/super/private-health tabs, evidence checklists, and accountant-review queues.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
metadata:
  priority: 4
  promptSignals:
    phrases:
      - "Excel workbook"
      - "spreadsheet"
      - "tax expense workbook"
      - "accountant spreadsheet"
      - "spouse and me"
      - "combined summary"
---

# TaxMate Australia Workbook

Use this skill for output rendering only. It creates draft accountant-facing artifacts, not lodgment-ready advice, tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, or investment advice. It must consume reviewed data and reviewed tax treatment from the user or installed topic skills; it must not create new tax logic.

Read `references/rules.md` before creating a workbook structure.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit workbook content to the ATO. Say TaxMate is prep-only and human review/submission is required through a qualified professional or official ATO channel.
- Keep `Accountant review` flags visible. Do not remove review flags to make a workbook appear submission-ready.
- If input fields conflict, explicit or review-like `Accountant review` wins over stale evidence, used, ATO-label, skipped, status-kind, tab-kind, or styling fields.
- Review queues must not show blank review items; use row number/status fallback when explanation fields are missing.
- Workbook display fields must preserve valid falsey values such as numeric `0` and boolean `false`; do not drop them through truthy fallbacks or raw string conversion.

## Workbook Shape

Default tabs:

- `Read Me`
- `Primary Taxpayer - Employee`
- `Primary Taxpayer - ABN`
- `Spouse or Partner - Employee`
- `Spouse or Partner - ABN`
- `Joint / Combined`
- `GST BAS`
- `ETF / Investments`
- `Super`
- `Private Health`
- `Evidence Checklist`
- `Accountant Review`
- `Source URLs`

## Rules

- Separate employee and ABN/business expenses.
- Separate primary taxpayer, spouse or partner, joint, and entity records.
- Preserve gross, GST, GST-exclusive, claim %, claim amount, evidence, source URL, and review status.
- Put ambiguous rows in `Accountant Review`.
- Before treating workbook output fixes as review-ready, cover parsed rows, file-backed data, and direct workbook-row paths in tests and validation.
- Do not silently drop rows.
- Do not mark BAS nil when GST credits or GST collected exist.
- Use formulas only for transparent totals; keep source rows visible.
- Refuse any request to lodge, submit, file, transmit, or finalise workbook content with the ATO.
