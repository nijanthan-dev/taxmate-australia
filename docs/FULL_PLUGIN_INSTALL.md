# Full Plugin Runtime (Primary)

Use this runtime path for the full TaxMate product experience: live ATO source refresh, source coverage governance, calculator workflows, finance review, and plugin orchestration.

Prerequisites:

- Node.js 20+ for full-runtime bootstrap and packaging checks.
- Bash 5+.
- Python 3.9+.
- Git.
- curl.
- jq.

## Clean plugin checkout setup

```bash
git clone https://github.com/nijanthan-dev/taxmate-australia.git
cd taxmate-australia
```

Run runtime commands through the bash launcher (python runtime under the hood):

```bash
./scripts/taxmate refresh --help
```

The same commands also work by calling the Python module directly:

```bash
./scripts/taxmate.py refresh --help
```

Validate:

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

## Local plugin setup

This repo includes `.codex-plugin/plugin.json` for advanced local plugin testing. Local marketplace configuration is development-only.

If you create a user-global marketplace file, its path is:

```text
~/.agents/plugins/marketplace.json
```

For a cloned repo at `/absolute/path/taxmate-australia`, the local plugin entry path should be that absolute repo path. The path is interpreted relative to the marketplace file only when it is relative.

Example:

```json
{
  "name": "taxmate-local",
  "interface": { "displayName": "Local plugins" },
  "plugins": [
    {
      "name": "taxmate-australia",
      "source": {
        "source": "local",
        "path": "/absolute/path/taxmate-australia"
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

Do not claim official plugin discovery unless a published listing has been verified.
