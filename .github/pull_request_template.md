## Summary


## Issue

- Closes:

## Risk

- [ ] tax logic, generated skills, or source metadata changed
- [ ] finance/calculator/runtime behaviour changed
- [ ] docs/templates/CI changed
- [ ] no user-visible behaviour changed

## Validation

- [ ] `bash scripts/bootstrap-dev-env.sh`
- [ ] `python3 -m py_compile scripts/*.py`
- [ ] `./scripts/taxmate validate`
- [ ] `./scripts/taxmate skills generate --check`
- [ ] `./scripts/taxmate skills audit --check`
- [ ] `scripts/check-publication-ready.sh`
- [ ] history secret scan (`gitleaks detect --source . --redact`)
- [ ] tree secret scan (`gitleaks dir . --redact`)

## Generated Artifacts

- [ ] generated skills unchanged or regenerated with `./scripts/taxmate skills generate`
- [ ] no hand edits to generated `skills/<topic>/SKILL.md`
- [ ] no stale generated artifacts

## Tax Safety

- [ ] ATO-first/source-backed behaviour preserved
- [ ] high-risk ambiguity remains `Accountant review`
- [ ] output skills do not make independent tax calls
- [ ] no private tax records, identity documents, TFNs, Medicare numbers, bank details, or client files added

## Review

- [ ] same-pattern scan completed before requesting independent review
- [ ] documentation and instruction validation rules updated for newly learned failure modes
- [ ] review threads replied to and resolved after fixes
- [ ] full local workflow passed
- [ ] merge only when `mergeStateStatus` is `CLEAN` and no review threads remain
