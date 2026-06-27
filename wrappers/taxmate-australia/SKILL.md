---
name: taxmate-australia
description: Entry-point wrapper for TaxMate Australia's full ATO-backed tax prep workflow across research, review, calculators, and handoff outputs.
metadata:
  internal: true
---

# TaxMate Australia

## Hard Safety Boundary

- Never lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit, lodge, file, transmit, finalise, or send prepared material to the ATO.
- Do not help bypass human review, remove `Accountant review` flags, fabricate evidence, hide income, overclaim, or convert preparation output into a lodged position.

Use the plugin skill `$taxmate-australia:research` when available.

Resolve the local plugin root from `TAXMATE_AUSTRALIA_ROOT`, or from a colocated checkout when this wrapper is copied into a larger plugin bundle:

```bash
export TAXMATE_AUSTRALIA_ROOT="${TAXMATE_AUSTRALIA_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
```

Read:

```bash
"$TAXMATE_AUSTRALIA_ROOT/runtime/skills/research/SKILL.md"
```

Follow that skill exactly. This wrapper exists for Codex installations that load `~/.agents/skills` before local plugin-cache skills.
