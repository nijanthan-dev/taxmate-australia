# Development

Contributor prerequisites:

- Node.js 18 or newer.
- Git.
- Bash 5+.
- Python 3.9+.

Core plugin checks:

```bash
bash scripts/test-skills-install.sh
scripts/check-publication-ready.sh
./scripts/taxmate validate
```

## Cloud (Codex) and local build environments (Mac-independent)

Use one setup for Codex Cloud and laptop-local workflows.

### Codex Cloud workspace

1. Open this repo in your Codex cloud workspace.
2. Ensure the workspace checks out the repository at runtime.
3. Run bootstrap checks (or your preferred command set):

```bash
bash scripts/bootstrap-dev-env.sh
```

This gives a deterministic contributor environment matching CI expectations.

### Runtime execution

Run runtime commands with the bash+python stack:

```bash
./scripts/taxmate refresh --help
./scripts/taxmate finance --help
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
bash scripts/test-skills-install.sh
scripts/check-publication-ready.sh
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

CI runs bash+python runtime checks, publication validation, and Gitleaks.

## Release (semver on merge to main)

- Every successful merge to `main` triggers `[.github/workflows/release.yml](/.github/workflows/release.yml)` after CI completes for that commit.
- Versions are calculated from Conventional Commits:
  - `feat:` -> minor
  - `fix:` / `perf:` -> patch
  - `feat!:` / `BREAKING CHANGE:` -> major
- Release notes/changelog and GitHub release artifacts are generated automatically when release-worthy commits are present.
