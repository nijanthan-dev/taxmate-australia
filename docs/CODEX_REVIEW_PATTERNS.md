# Codex review guardrails

This repo has had repeated Codex review comments fixed across PRs. Keep the repeatable classes as local guardrails so future review cycles do not spend tokens on known issues.

## Canonical inventory

`scripts/taxmate_review_guardrails.py` is the canonical pattern inventory and executable guardrail surface.

Do not duplicate the pattern list in this doc. List it from the script instead:

```bash
./scripts/taxmate review-guardrails --list-patterns
./scripts/taxmate review-guardrails --list-patterns --format markdown
./scripts/taxmate review-guardrails --list-patterns --format json
```

Use JSON output when passing review history into another tool without wasting tokens:

```bash
./scripts/taxmate review-guardrails --list-patterns --format json
```

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
