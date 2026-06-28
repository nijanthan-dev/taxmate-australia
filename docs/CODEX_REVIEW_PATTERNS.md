# Codex review guardrails

This repo has had repeated Codex review comments fixed across PRs. Keep the repeatable classes as local guardrails so future review cycles do not spend tokens on known issues.

## Patterns

- PR #7: preserve public JSON wire formats, reject non-finite numbers, keep half-up cent rounding, preserve generated source provenance, compare tracked generated artifacts, and remove stale Go/runtime docs.
- PR #8: keep Codex setup/cleanup safe in linked Git worktrees, do not dirty a clean checkout, and avoid unsafe `find -delete` patterns.
- PR #10: public metadata must describe the real bash+Python runtime.
- PR #22: public claim scanners must include wrappers, discovery docs, workflows, and endorsement phrasing in both directions around `ATO`.
- PR #25: ATO fetches must call `curl --disable -L` so user curl config cannot alter source refreshes.
- PR #27: output layers must preserve `Accountant review`, source provenance, falsey display values, dynamic generated dates, unique anchors, safe tab target lookup, and neutral mixed-area headings.
- Release guardrails: release workflow edits must preserve green-CI checks, unchanged-main checks, version manifest alignment, and the Release Please bootstrap SHA.

## Local gate

Run:

```bash
./scripts/taxmate review-guardrails
```

The guard is static by design. Full validation still runs:

```bash
PYTHONPYCACHEPREFIX=/tmp/taxmate-pycache python3 -m py_compile scripts/*.py
./scripts/taxmate validate
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
scripts/check-publication-ready.sh
gitleaks dir . --redact --no-banner
```

## Pre-commit

Either use the checked-in hook:

```bash
git config core.hooksPath .githooks
```

Or use `pre-commit`:

```bash
pre-commit install
```
