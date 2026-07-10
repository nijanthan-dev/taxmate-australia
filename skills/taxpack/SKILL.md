---
name: taxmate-australia-taxpack
description: Use when the user needs TaxMate Australia accountant handoff packs, source bundles, manual-copy guidance, or print-first HTML handoff setup.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
metadata:
  priority: 3
  promptSignals:
    phrases:
      - "tax pack"
      - "ATO guide"
      - "accountant pack"
      - "handoff pack"
      - "tax summary"
      - "manual copy guide"
---

# TaxMate Australia Taxpack

Use this skill for final handoff packaging only. It creates draft preparation guidance, checklist/source-bundle content, and manual-copy instructions, not rendered files, official ATO PDFs, official lodgment forms, professional advice, tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, or investment advice. It consumes reviewed data from the user, installed topic skills, and workbook outputs.

Read `references/rules.md` before creating handoff packs.

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit prepared material to the ATO. Say TaxMate is prep-only and human review/submission is required through a qualified professional or official ATO channel.
- Keep `Accountant review` flags visible. Do not remove review flags to make a pack appear submission-ready.
- If input fields conflict, `Accountant review` wins. Do not let stale `status_kind`, tab kind, evidence, used, ATO-label, skipped, or styling fields downgrade an explicit or review-like accountant-review status.
- Review queues and guide side tabs must not show blank review items; use row number/status fallback when explanation fields are missing.
- Guide display fields must preserve valid falsey values such as numeric `0` and boolean `false`; do not drop them through truthy fallbacks or raw string conversion.
- Do not fill, modify, or present official ATO PDFs as completed returns.

## Quick Reference

| Situation | Action |
| --- | --- |
| Reviewed facts are available | Build handoff guidance with sources, evidence status, and review flags. |
| HTML output is requested | Use the full runtime after reviewed input is supplied. |
| Explanation fields are blank | Fall back to row number or status instead of blank review items. |
| User asks to lodge or finalise | Refuse and keep the pack manual-copy only. |

## Common Mistakes

- Making independent tax treatment decisions in the output layer.
- Dropping `Accountant review` when stale lower-risk fields conflict.
- Hiding blank review items instead of rendering a fallback label.
- Presenting custom handoff content as an official ATO form.

## Rules

- Do not fill final tax forms from raw records.
- Do not make independent tax treatment decisions.
- Keep source URLs, evidence status, and accountant-review flags visible.
- Keep source URLs and checked-at dates visible in guide rows when supplied.
- For guide rows, preserve accountant-review status in the row badge, side tab, filters, and review queue even if other fields are stale or conflict.
- For guide rows, keep review side tabs and review queue entries visible even when `tab_text` and rationale fields are blank.
- Before treating guide output fixes as ready for independent review, cover parsed JSON rows, file-backed guide data, and direct renderer rows in tests and validation.
- Falsey-value regressions must cover top-level guide metadata, row fields, source URL lists, checked-at provenance, fallback tab text, anchors, and direct `GuideItem` construction.
- For manual-copy guidance, reference ATO labels and income-year wording, but keep the output clearly custom, manual, and non-lodgment. Use the full runtime for print-first HTML handoff generation.
- Tell users to copy reviewed answers into myTax, paper ATO forms, or give the pack to an accountant.
- Refuse any request to lodge, submit, file, transmit, or finalise the pack with the ATO.
