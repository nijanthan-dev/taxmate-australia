# Development

Contributor prerequisites:

- Go 1.22 or newer.
- Node.js 18 or newer.
- Git.

Core checks:

```bash
go test ./...
go vet ./...
go build ./...
bash scripts/test-skills-install.sh
scripts/check-publication-ready.sh
```

Coverage checks:

```bash
go test ./...
go vet ./...
go build ./...
bin/taxmate-australia-skills generate --check
bin/taxmate-australia-skills audit --check
bin/taxmate-australia-skills audit --format markdown --output /tmp/source-coverage.md
scripts/check-publication-ready.sh
```

Build all binaries:

```bash
mkdir -p bin
go build -o bin/taxmate-australia-refresh ./cmd/taxmate-australia-refresh
go build -o bin/taxmate-australia-skills ./cmd/taxmate-australia-skills
go build -o bin/taxmate-australia-validate ./cmd/taxmate-australia-validate
go build -o bin/taxmate-australia-finance ./cmd/taxmate-australia-finance
go build -o bin/taxmate-australia-calc ./cmd/taxmate-australia-calc
```

Do not commit `bin/` outputs or private user tax records.

## Skill packaging

- Public portable skill source of truth: `config/public-skills.json`.
- Classification source of truth: `config/skill-packaging.json`.
- Runtime-only skills must include `metadata.internal: true`.
- Public skills must not reference repository binaries, `TAXMATE_AUSTRALIA_ROOT`, plugin-qualified skill names, or repository data paths.

## CI

CI runs Go tests, `go vet`, builds all packages, runs portable install smoke tests, runs publication validation, and runs Gitleaks.
