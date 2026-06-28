# Generated Topic Inputs

Workbook and taxpack are output layers only. They must consume reviewed classifications from topic skills and must not invent tax treatment.

- Preserve `Accountant review` flags.
- If input fields conflict, explicit or review-like `Accountant review` wins over stale evidence, used, ATO-label, skipped, status-kind, tab-kind, or styling fields.
- Preserve source URLs and checked-at dates.
- Do not turn raw transactions into lodging-ready claims from source extracts alone.
