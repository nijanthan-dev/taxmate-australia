# Plugin scanner and marketplace hygiene notes

This file tracks the checks to run before publishing a marketplace build.

Use when you are preparing a public release (not required for local-only installs).

- Validate manifest pathing and JSON:
  - `jq . .codex-plugin/plugin.json > /dev/null`
  - `jq . .codex-plugin/plugin.lock.json > /dev/null` (if lock is used)
- Keep lock metadata honest:
  - every skill in `skills/` appears once in `plugin.lock.json`
  - no `REPLACE_WITH_REAL_VALUE` entries remain
  - no placeholders remain in public docs (`TODO`, `<fill-in>`, `TBD`)
- Release scan checklist:
  - no secrets in changed files (run your scanner/`gitleaks` workflow if available)
  - no unresolved local debug artifacts or private paths in README/public docs
  - disclaimer/disclosure links are accurate and current
- Keep a note in PRs: scanner checks run date and tool used.
