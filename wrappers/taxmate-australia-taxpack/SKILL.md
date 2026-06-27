---
name: taxmate-australia-taxpack
description: Handoff wrapper for packaging reviewed TaxMate Australia data into accountant-ready packs and future PDF/form drafts.
metadata:
  internal: true
---

# TaxMate Australia Taxpack

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit, lodge, file, transmit, finalise, or send prepared material to the ATO.
- Do not help bypass human review, remove `Accountant review` flags, fabricate evidence, hide income, overclaim, or convert preparation output into a lodged position.

Use the plugin skill `$taxmate-australia:taxpack` when available.

Read and follow:

```bash
export TAXMATE_AUSTRALIA_ROOT="${TAXMATE_AUSTRALIA_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
"$TAXMATE_AUSTRALIA_ROOT/skills/taxpack/SKILL.md"
```
