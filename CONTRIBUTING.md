# Contributing

TaxMate Australia is conservative by design. Contributions must preserve source-backed behaviour and clear accountant-review boundaries.

Do not present TaxMate Australia output as tax, legal, accounting, financial, BAS-agent, or registered-tax-agent advice. TaxMate Australia is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency.

## Contributor Flow

1. Open an issue first for user-visible tax behaviour, source changes, generated skills, CI, packaging, release, or security-sensitive work.
2. Use synthetic records only. Do not attach real tax records, TFNs, Medicare numbers, bank details, identity documents, or private client files.
3. Keep the change narrow. Do not combine source refresh, generated skills, finance logic, calculator logic, docs, and repo plumbing unless a single issue requires it.
4. Add or update tests for changed behaviour and every failure pattern found while working.
5. Run the full local PR checklist before requesting independent review.

## Tax Safety Rules

- Prefer official ATO or government sources.
- Keep ambiguous, mixed-use, pre-revenue, home-business, FBT, CGT, GST/BAS, non-commercial-loss, and business-versus-hobby items as `Accountant review` unless sources clearly resolve them.
- Do not loosen accountant-review defaults for high-risk topics without source-backed tests.
- Keep source state in `data/ato_knowledge_base/source_registry.json` and `data/ato_knowledge_base/source_coverage.json`.
- Treat refreshed source text as ignored cache under `.cache/ato/text/`.
- Keep tax logic in `runtime/skills/research`, `runtime/skills/finance-review`, `runtime/skills/calculators`, and shared Python runtime.
- Keep `skills/workbook` and `skills/taxpack` as output layers only.
- Do not commit user tax records, private documents, or built binaries.
- Keep plugin docs portable. Avoid private machine paths in public docs and plugin skills.

## Generated Skills

Update generated topic skills through `scripts/skillgen.py`, then regenerate:

```bash
./scripts/taxmate skills generate
```

Do not hand-edit generated `skills/<topic>/SKILL.md` or `skills/<topic>/references/*`.

## Before Opening A PR

Run:

```bash
PYTHONPYCACHEPREFIX=/tmp/taxmate-pycache python3 -m py_compile scripts/*.py
./scripts/taxmate validate
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
scripts/check-publication-ready.sh
gitleaks detect --source . --redact
gitleaks dir . --redact
```

If `gitleaks` is unavailable locally, install it before merge.

## Pull Request Rules

- Use the PR template.
- Link the issue when one exists.
- Mark skipped checks with the reason.
- Reply to every review thread with the fix and resolve the thread after verification.
- Merge only after the full local workflow and secret scans pass, `mergeStateStatus` is `CLEAN`, and all review threads are resolved.
- Use squash merge only.
