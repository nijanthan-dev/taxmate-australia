---
name: taxpack
description: Prepare accountant handoff packs and future PDF/form outputs from reviewed TaxMate Australia data. Use for summary PDFs, checklists, source bundles, and later tax-form drafts from accountant-reviewed structured data.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
metadata:
  priority: 3
  promptSignals:
    phrases:
      - "tax pack"
      - "PDF tax form"
      - "accountant pack"
      - "handoff pack"
      - "tax summary PDF"
---

# TaxMate Australia Taxpack

Use this skill for final handoff packaging only. It creates draft preparation artifacts, not official lodgment forms, professional advice, tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, or investment advice. It consumes reviewed data from the user, installed topic skills, and workbook outputs.

Read `references/rules.md` before creating handoff packs.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit prepared material to the ATO. Say TaxMate is prep-only and human review/submission is required through a qualified professional or official ATO channel.
- Keep `Accountant review` flags visible. Do not remove review flags to make a pack appear submission-ready.

## Rules

- Do not fill final tax forms from raw records.
- Do not make independent tax treatment decisions.
- Keep source URLs, evidence status, and accountant-review flags visible.
- Treat PDF/form filling as draft preparation only unless the user explicitly asks for a final accountant-ready copy.
- For any official lodgment form, require reviewed structured data and exact income-year labels.
- Refuse any request to lodge, submit, file, transmit, or finalise the pack with the ATO.
