# Plugin scanner and marketplace hygiene notes

This file tracks the checks to run before publishing a marketplace build.

Use when you are preparing a public release (not required for local-only installs).
Public listing preflight also requires `.github/workflows/hol-plugin-scanner.yml` to run the reviewed HOL scanner action with minimum score 80 and failure on high-or-higher severity findings.

- Validate manifest pathing and JSON:
  - `jq . .codex-plugin/plugin.json > /dev/null`
  - `jq . plugin.lock.json > /dev/null` (if lock is used)
- Keep lock metadata honest:
  - every packaged public skill in `skills/` and every runtime skill in `runtime/skills/` appears once in `plugin.lock.json`
  - no `REPLACE_WITH_REAL_VALUE` entries remain
  - no placeholders remain in public docs (`TODO`, `fill-in`, `TBD`)
- Release scan checklist:
  - HOL Plugin Scanner CI is present and passing on the default branch before opening an awesome-codex-plugins listing PR
  - no secrets in changed files (run your scanner/`gitleaks` workflow if available)
  - no unresolved local debug artifacts or private paths in README/public docs
  - disclaimer/disclosure links are accurate and current
- Keep a note in PRs: scanner checks run date and tool used.
