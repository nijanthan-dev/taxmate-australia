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
- When review exposes an invariant, encode that invariant broadly in guardrails and tests before fixing the narrow line.
- Use a focused explorer/subagent when the bug class may recur outside the commented line, then close it after findings are integrated.
- Cover parser, file-backed data, and direct renderer/workbook-row paths.
- For falsey output bugs, cover top-level metadata, row fields, list fields, provenance, fallback labels, anchors, and direct constructors.
- Update AGENTS, relevant skills, generated docs, tests, validator, and plugin lock when behavior changes.
- Regenerate skills, run publication checks, and run secret scans.

Run `./scripts/taxmate review-guardrails` before opening or updating a PR. The script is the canonical pattern inventory and executable guardrail surface. Do not duplicate PR pattern bullets in docs.

The local pre-commit config, repo hook, and CI run this guardrail. Public-doc leakage checks are deterministic Python checks in `scripts/taxmate_review_guardrails.py`: update `PUBLIC_OUTPUT_DOCS`, `DEVELOPER_ONLY_PUBLIC_DOC_TERMS`, and `DEVELOPER_ONLY_PUBLIC_DOC_PATTERNS` when Codex review finds a new developer-only command that must not appear in README or public setup docs.

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
bash scripts/install-local-skills.sh --agent codex
bash scripts/codex-env-cleanup.sh
```

4. Install local workflow skills only when this lane uses them:

```bash
set -euo pipefail
bash scripts/install-local-skills.sh --agent codex
```

5. Use this maintenance script:

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
bash scripts/install-local-skills.sh --agent codex
bash scripts/codex-env-cleanup.sh
```

`local-skills/` contains repo-local workflow SKILL definitions that are not part of portable installs.

### Runtime execution

Run runtime commands with the bash+python stack:

```bash
./scripts/taxmate refresh --help
./scripts/taxmate finance --help
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual --answers /tmp/taxmate-answers.json --output /tmp/taxmate-guide.html
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

### README screenshot refresh

Screenshot refresh commands are developer-only. Keep the global README focused on install, usage, previews, boundaries, and user-facing examples.

Refresh the README preview assets from synthetic sample data:

```bash
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless --disable-gpu --hide-scrollbars --disable-background-networking \
  --disable-component-update --no-first-run --no-default-browser-check \
  --user-data-dir=/tmp/taxmate-chrome-profile --window-size=1040,720 \
  --screenshot=assets/readme/taxmate-guide-john-doe.png \
  file:///tmp/taxmate-guide.html
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless --disable-gpu --hide-scrollbars --disable-background-networking \
  --disable-component-update --no-first-run --no-default-browser-check \
  --user-data-dir=/tmp/taxmate-chrome-profile-long --window-size=1120,10000 \
  --screenshot=/tmp/taxmate-guide-full.png \
  file:///tmp/taxmate-guide.html
python3 scripts/png_crop.py /tmp/taxmate-guide-full.png \
  assets/readme/taxmate-guide-john-doe-worksheet.png 0 5350 1120 760
```

Any PR that changes user-facing output, output sections, screenshots/images, install/use docs, or individual-return handoff expectations must update README/docs in the same PR, or state why no docs update is needed.

Do not commit private user tax records.

## Skill packaging

- Public portable skill source of truth: `config/public-skills.json` (optional fallback).
- Classification source of truth: `config/skill-packaging.json`.
- Runtime-only skills must include `metadata.internal: true`.
- Public skills must not reference repository runtime paths, `TAXMATE_AUSTRALIA_ROOT`, plugin-qualified skill names, or repository data paths.

## Local Plugin Testing

This repo includes `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` for advanced local Codex plugin testing. Local marketplace configuration is development-only.

From the repo root:

```bash
codex plugin marketplace add .
codex plugin add taxmate-australia@taxmate-local-marketplace
```

Verify available plugins:

```bash
codex plugin marketplace list
codex plugin list
```

Do not claim official plugin discovery unless a published listing has been verified.

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
