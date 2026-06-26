# Official Source Manifests

This directory keeps compact provenance for generated TaxMate Australia skills. It no longer commits raw ATO HTML or one-line cleaned webpage copies.

## Files

- `source_registry.json`: active source registry used for refresh targeting and generation.
- `source_coverage.json`: global source-to-skill coverage with verified/metadata-only statuses and proof pointers.
- `SCOPE_SUMMARY.md`: coverage, limits, and dynamic-value handling.
- `README.md`: scope and generation summary.
- `skills/*/references/`: per-topic source and provenance references.

## Refresh

Use the bash+python generator:

```bash
./scripts/taxmate refresh --topic gst-bas
./scripts/taxmate refresh --all
./scripts/taxmate skills generate
./scripts/taxmate skills generate --check
./scripts/taxmate skills validate
```

Live refresh stores temporary fetched HTML and extracted text under ignored `.cache/ato/`. Do not commit full webpage snapshots.

## Current-Value Rule

Generated `current-values.json` files may contain volatile values only with official source URL, source title, last-updated date when available, checked-at date, content hash, context, and reuse warning. If a value cannot be verified for the requested income year or effective period, use `Accountant review`.
