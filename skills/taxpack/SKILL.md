---
name: taxpack
description: Prepare accountant handoff packs and ATO-aligned manual guide PDFs from reviewed TaxMate Australia data. Use for summary PDFs, checklists, source bundles, and custom guide PDFs that help users copy reviewed answers into myTax, paper ATO forms, or an accountant handoff.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
metadata:
  priority: 3
  promptSignals:
    phrases:
      - "tax pack"
      - "ATO guide PDF"
      - "accountant pack"
      - "handoff pack"
      - "tax summary PDF"
---

# TaxMate Australia Taxpack

Use this skill for final handoff packaging only. It creates draft preparation artifacts and custom ATO-aligned manual guide PDFs, not official ATO PDFs, official lodgment forms, professional advice, tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, or investment advice. It consumes reviewed data from the user, installed topic skills, and workbook outputs.

Read `references/rules.md` before creating handoff packs.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit prepared material to the ATO. Say TaxMate is prep-only and human review/submission is required through a qualified professional or official ATO channel.
- Keep `Accountant review` flags visible. Do not remove review flags to make a pack appear submission-ready.
- If input fields conflict, `Accountant review` wins. Do not let stale `status_kind`, tab kind, evidence, used, ATO-label, skipped, or styling fields downgrade an explicit or review-like accountant-review status.
- Do not fill, modify, or present official ATO PDFs as completed returns.

## Rules

- Do not fill final tax forms from raw records.
- Do not make independent tax treatment decisions.
- Keep source URLs, evidence status, and accountant-review flags visible.
- Keep source URLs and checked-at dates visible in guide rows when supplied.
- For guide rows, preserve accountant-review status in the row badge, side tab, filters, and review queue even if other fields are stale or conflict.
- For guide PDFs, reference ATO labels and income-year wording, but keep the output clearly custom, manual, and non-lodgment.
- Tell users to copy reviewed answers into myTax, paper ATO forms, or give the pack to an accountant.
- Refuse any request to lodge, submit, file, transmit, or finalise the pack with the ATO.
