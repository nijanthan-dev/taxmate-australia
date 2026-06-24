# Official Source Manifests

This directory keeps compact provenance for generated TaxMate Australia skills. It no longer commits raw ATO HTML or one-line cleaned webpage copies.

## Files

- `source_index.json`: legacy refresh target index from the official-source crawl.
- `source_manifest.json`: generated source map grouped by topic skill.
- `migration_report.json`: source-by-source migration report with duplicate and unassigned status.
- `SCOPE_SUMMARY.md`: coverage, limits, and dynamic-value handling.

## Refresh

Use the Go generator:

```bash
taxmate-australia-skills refresh --topic gst-bas
taxmate-australia-skills refresh --all
taxmate-australia-skills generate
taxmate-australia-skills validate
```

Live refresh stores temporary fetched HTML and extracted text under ignored `.cache/ato/`. Do not commit full webpage snapshots.

## Current-Value Rule

Generated `current-values.json` files may contain volatile values only with official source URL, source title, last-updated date when available, checked-at date, content hash, context, and reuse warning. If a value cannot be verified for the requested income year or effective period, use `Accountant review`.
