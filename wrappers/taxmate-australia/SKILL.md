---
name: taxmate-australia
description: Entry-point wrapper for TaxMate Australia's full ATO-backed tax prep workflow across research, review, calculators, and handoff outputs.
---

# TaxMate Australia

Use the plugin skill `$taxmate-australia:research` when available.

Resolve the local plugin root from `TAXMATE_AU_ROOT`, or from a colocated checkout when this wrapper is copied into a larger plugin bundle:

```bash
export TAXMATE_AU_ROOT="${TAXMATE_AU_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
```

Read:

```bash
"$TAXMATE_AU_ROOT/skills/research/SKILL.md"
```

Follow that skill exactly. This wrapper exists for Codex installations that load `~/.agents/skills` before local plugin-cache skills.
