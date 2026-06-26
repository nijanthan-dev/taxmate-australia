---
name: taxmate-australia
description: Entry-point wrapper for TaxMate Australia's full ATO-backed tax prep workflow across research, review, calculators, and handoff outputs.
metadata:
  internal: true
---

# TaxMate Australia

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
