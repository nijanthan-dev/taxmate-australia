# Development

Contributor prerequisites:

- Node.js 20 or newer.
- Git.
- curl.
- jq.
- Bash.
- Python 3.9+.
- Gitleaks for full local release checks.

Core plugin checks:

```bash
PYTHONPYCACHEPREFIX=/tmp/taxmate-pycache python3 -m py_compile scripts/*.py
./scripts/taxmate review-guardrails
./scripts/taxmate validate
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
scripts/check-publication-ready.sh
gitleaks detect --source . --redact --no-banner
gitleaks dir . --redact --no-banner
```

## Review feedback loop

Before requesting another Codex review after review feedback:

- Scan the whole same bug class, not only the commented line.
- Use a focused explorer/subagent when the bug class may recur outside the commented line, then close it after findings are integrated.
- Cover parser, file-backed data, and direct renderer/workbook-row paths.
- For falsey output bugs, cover top-level metadata, row fields, list fields, provenance, fallback labels, anchors, and direct constructors.
- Update AGENTS, relevant skills, generated docs, tests, validator, and plugin lock when behavior changes.
- Regenerate skills, run publication checks, and run secret scans.

Run `./scripts/taxmate review-guardrails` before opening or updating a PR. The script is the canonical pattern inventory and executable guardrail surface. Do not duplicate PR pattern bullets in docs.

List the inventory from the script:

```bash
./scripts/taxmate review-guardrails --list-patterns
./scripts/taxmate review-guardrails --list-patterns --format markdown
./scripts/taxmate review-guardrails --list-patterns --format json
```

Use `./scripts/taxmate review-guardrails --list-patterns --format json` for compact review context.

To enable the repo-local hook:

```bash
git config core.hooksPath .githooks
```

Or install the local `pre-commit` config:

```bash
pre-commit install
```

## Cloud (Codex) and local build environments (Mac-independent)

Use one setup for Codex Cloud and laptop-local workflows.

### Codex Cloud workspace

1. Open this repo in your Codex cloud workspace.
2. Ensure the workspace checks out the repository at runtime.
3. Use this setup script:

```bash
set -euo pipefail
bash scripts/codex-env-setup.sh
bash scripts/codex-env-cleanup.sh
```

4. Use this maintenance script:

```bash
set -euo pipefail
bash scripts/codex-env-setup.sh
bash scripts/codex-env-cleanup.sh
```

Codex Cloud currently exposes setup and maintenance fields. This gives a deterministic contributor environment matching CI expectations and removes generated cache/build noise when new or cached containers are prepared.

### Local environment parity

Run the same command sets locally:

```bash
bash scripts/codex-env-setup.sh
bash scripts/codex-env-cleanup.sh
```

### Runtime execution

Run runtime commands with the bash+python stack:

```bash
./scripts/taxmate refresh --help
./scripts/taxmate finance --help
./scripts/taxmate taxpack guide-html --output /tmp/taxmate-guide.html
./scripts/taxmate validate
```

The launcher entrypoint is bash (`./scripts/taxmate`) and delegates to `scripts/taxmate.py`.
Python is the supported default runtime path.

### Local Docker environment

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec taxmate-australia bash
```

The local container includes:
- Node.js 20
- Git/cURL/JQ

Then run the normal checks from the repo:

```bash
bash scripts/bootstrap-dev-env.sh
PYTHONPYCACHEPREFIX=/tmp/taxmate-pycache python3 -m py_compile scripts/*.py
./scripts/taxmate validate
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
scripts/check-publication-ready.sh
gitleaks detect --source . --redact --no-banner
gitleaks dir . --redact --no-banner
```

### Codex usage in container

Codex is not globally installed by default in the container image.
If you need Codex commands inside the container, install it with your standard method and ensure it is on `PATH`.

Coverage checks:

```bash
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
./scripts/taxmate skills audit --format markdown --output /tmp/source-coverage.md
scripts/check-publication-ready.sh
```

Do not commit private user tax records.

## Skill packaging

- Public portable skill source of truth: `config/public-skills.json` (optional fallback).
- Classification source of truth: `config/skill-packaging.json`.
- Runtime-only skills must include `metadata.internal: true`.
- Public skills must not reference repository runtime paths, `TAXMATE_AUSTRALIA_ROOT`, plugin-qualified skill names, or repository data paths.

## CI

CI runs bash+python runtime checks, generated-source checks, environment guardrails, macOS smoke, publication validation, and Gitleaks.

## Release

- After a successful merge to `main`, the Release workflow runs after main CI passes. It can also be run manually from `main`.
- The workflow requires `RELEASE_PLEASE_TOKEN`, a repo secret whose token can create release pull requests and write contents/issues.
- Versions are calculated from Conventional Commits:
  - `feat:` -> minor
  - `fix:` / `perf:` -> patch
  - `feat!:` / `BREAKING CHANGE:` -> major
- The workflow creates or updates the Release PR. After that PR is merged and main CI passes, the workflow runs again to publish the GitHub release artifact.
