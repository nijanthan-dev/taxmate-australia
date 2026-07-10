# Generated Topic Inputs

Workbook and taxpack are output layers only. They must consume reviewed classifications from topic skills and must not invent tax treatment.

- Preserve `Accountant review` flags.
- If input fields conflict, explicit or review-like `Accountant review` wins over stale evidence, used, ATO-label, skipped, status-kind, tab-kind, or styling fields.
- If explanation fields are blank, review queues must fall back to row number/status instead of rendering blank review items.
- Preserve the runtime-owned handoff action, destination or explicit non-entry/review wording, labelled facts, explanation, and provenance for every row and queue item.
- Preserve the seven runtime actions: enter reviewed value, answer guided question, retain evidence, resolve before entry, accountant handoff only, not entered directly, and destination requires review.
- Do not infer destinations from row names, broad topic URLs, source coverage alone, or unverified target labels; missing, malformed, conflicting, unsupported, or stale mappings fail closed.
- Mixed rows need field-level actions or safe row separation so one destination is not implied for unrelated facts.
- Preserve valid falsey output values such as numeric `0` and boolean `false`; do not drop them through truthy fallbacks or raw string conversion.
- Fixes from independent review must cover parsed input, file-backed data, direct renderer/workbook-row paths, generated artifacts, tests, validator, and documentation and instruction validation rules before another review is requested.
- Falsey output fixes must cover metadata, row fields, list fields, provenance, fallback labels, anchors, and direct constructors.
- Preserve source URLs and checked-at dates.
- Do not turn raw transactions into lodging-ready claims from source extracts alone.
