## Summary


## Validation

- [ ] `bash scripts/bootstrap-dev-env.sh`
- [ ] `python3 -m py_compile scripts/*.py`
- [ ] `./scripts/taxmate validate`
- [ ] `./scripts/taxmate skills generate --check`
- [ ] `./scripts/taxmate skills audit --check`
- [ ] `scripts/check-publication-ready.sh`
- [ ] secret scan

## Tax Safety

- [ ] ATO-first/source-backed behaviour preserved
- [ ] high-risk ambiguity remains `Accountant review`
- [ ] output skills do not make independent tax calls
