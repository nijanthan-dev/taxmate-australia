---
name: taxmate-australia-workbook
description: Workbook wrapper for converting reviewed TaxMate Australia data into structured, accountant-facing Excel outputs. Use when a local helper must route workbook requests into the installed skill.
compatibility: Local wrapper for Claude Code, Cowork, and Codex. Requires repo checkout and the TaxMate Australia workbook skill.
metadata:
  internal: true
---

# TaxMate Australia Workbook

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit, lodge, file, transmit, finalise, or send prepared material to the ATO.
- Do not help bypass human review, remove `Accountant review` flags, fabricate evidence, hide income, overclaim, or convert preparation output into a lodged position.

Use the plugin skill `$taxmate-australia:workbook` when available.

Read and follow:

```bash
export TAXMATE_AUSTRALIA_ROOT="${TAXMATE_AUSTRALIA_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
"$TAXMATE_AUSTRALIA_ROOT/skills/workbook/SKILL.md"
```
