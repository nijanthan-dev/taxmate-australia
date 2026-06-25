# Full Plugin Runtime

Use this advanced path only when you need live ATO source refresh, Go-backed CSV finance review, calculator commands, skill regeneration, source coverage, and Codex plugin orchestration.

Prerequisites:

- Go 1.22 or newer.
- Node.js 18 or newer if also testing portable install.
- Git.

## Clean checkout setup

```bash
git clone https://github.com/nijanthan-dev/taxmate-australia.git
cd taxmate-australia
go test ./...
go build ./...
```

Build runtime binaries:

```bash
mkdir -p bin
go build -o bin/taxmate-australia-refresh ./cmd/taxmate-australia-refresh
go build -o bin/taxmate-australia-skills ./cmd/taxmate-australia-skills
go build -o bin/taxmate-australia-validate ./cmd/taxmate-australia-validate
go build -o bin/taxmate-australia-finance ./cmd/taxmate-australia-finance
go build -o bin/taxmate-australia-calc ./cmd/taxmate-australia-calc
```

Validate:

```bash
bin/taxmate-australia-validate
bin/taxmate-australia-skills validate
bin/taxmate-australia-skills audit --check
bin/taxmate-australia-skills audit --format markdown --output /tmp/source-coverage.md
scripts/check-publication-ready.sh
```

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
