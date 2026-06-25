# Official Source Manifests

This directory keeps compact provenance for generated TaxMate Australia skills. It no longer commits raw ATO HTML or one-line cleaned webpage copies.

## Files

- `source_registry.json`: active source registry used for refresh targeting and generation.
- `source_coverage.json`: global source-to-skill coverage with verified/metadata-only statuses and proof pointers.
- `SCOPE_SUMMARY.md`: coverage, limits, and dynamic-value handling.
- `README.md`: scope and generation summary.
- `skills/*/references/`: per-topic source and provenance references.

## Refresh

Use the Go generator:

```bash
taxmate-australia-skills refresh --topic gst-bas
taxmate-australia-skills refresh --all
taxmate-australia-skills generate
taxmate-australia-skills generate --check
taxmate-australia-skills validate
```

Live refresh stores temporary fetched HTML and extracted text under ignored `.cache/ato/`. Do not commit full webpage snapshots.

## Current-Value Rule

Generated `current-values.json` files may contain volatile values only with official source URL, source title, last-updated date when available, checked-at date, content hash, context, and reuse warning. If a value cannot be verified for the requested income year or effective period, use `Accountant review`.
