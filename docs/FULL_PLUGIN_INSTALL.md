# Full Runtime Setup

Use this runtime path for guide generation, workbook/taxpack outputs, live ATO source refresh, source coverage governance, calculator workflows, finance review, validation, and local plugin testing.

If you only need quick agent prompts without a checkout, use [INSTALLATION.md](INSTALLATION.md) instead.

Prerequisites:

- Node.js 20+ for full-runtime bootstrap and packaging checks.
- Bash.
- Python 3.9+.
- Git.
- curl.
- jq.

## Clean Runtime Setup

```bash
git clone https://github.com/nijanthan-dev/taxmate-australia.git
cd taxmate-australia
bash scripts/bootstrap-dev-env.sh
```

Validate the checkout:

```bash
./scripts/taxmate validate
./scripts/taxmate skills generate --check
```

Run runtime commands through the bash launcher (python runtime under the hood):

```bash
./scripts/taxmate refresh --help
```

Render the self-prepared guide HTML users can save as PDF:

```bash
./scripts/taxmate taxpack sample-json --output /tmp/taxmate-guide-input.json
./scripts/taxmate taxpack guide-html \
  --input /tmp/taxmate-guide-input.json \
  --output /tmp/taxmate-guide.html
```

The guide is a custom preparation aid. Users manually copy reviewed values into myTax, a paper ATO form, or provide it to an accountant.

The same commands also work by calling the Python module directly:

```bash
./scripts/taxmate.py refresh --help
```

Full validation:

```bash
PYTHONPYCACHEPREFIX=/tmp/taxmate-pycache python3 -m py_compile scripts/*.py
./scripts/taxmate validate
./scripts/taxmate skills validate
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
./scripts/taxmate skills audit --format markdown --output /tmp/source-coverage.md
scripts/check-publication-ready.sh
gitleaks detect --source . --redact --no-banner
```

If you need local-speed, keep Python runtime wrappers and dependencies local and use the launcher directly.
Bash + python execution is the supported default path.

## Local Plugin Setup

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
