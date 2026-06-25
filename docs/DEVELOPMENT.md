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

## Cloud and local build environments (Mac-independent)

Use one setup for both GitHub-hosted and laptop-local workflows.

### GitHub Codespaces

1. Open the repository and click **Code → Codespaces → Create codespace on main**.
2. The container auto-creates from `.devcontainer/devcontainer.json`.
3. Run bootstrap checks (or your preferred command set) from the container:

```bash
bash scripts/bootstrap-dev-env.sh
```

Codespaces will keep `.devcontainer` dependencies pinned to the repository and avoids local host drift.

### Local Docker environment

```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec taxmate-australia bash
```

The local container includes:
- Go 1.22
- Node.js 20
- Git/cURL/JQ

Then run the normal checks from the repo:

```bash
bash scripts/bootstrap-dev-env.sh
go test ./...
go vet ./...
go build ./...
bash scripts/test-skills-install.sh
scripts/check-publication-ready.sh
```

### Codex usage in container

Codex is not globally installed by default in the container image.
If you need Codex commands inside the container, install it with your standard method and ensure it is on `PATH`.

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
