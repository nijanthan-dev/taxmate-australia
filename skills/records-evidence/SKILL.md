---
name: taxmate-australia-records-evidence
description: Use when the user needs TaxMate Australia guidance for records and proof standards.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
---

# TaxMate Australia Records Evidence

Generated from TaxMate Australia source metadata. Verify volatile values before relying on them.

Use for records and proof standards. Do not use for topic-specific current rates without source refresh.

## Quick Reference

| Situation | Action |
| --- | --- |
| User supplies records or facts | Read `references/rules.md` and `references/evidence.md` before classifying. |
| Source support is missing or metadata-only | Keep the item in `Accountant review`. |
| Values are volatile or income-year specific | Verify against the official source before relying on them. |
| User asks to lodge or finalise | Refuse and keep the output prep-only. |

## Common Mistakes

- Treating metadata-only source links as verified tax treatment.
- Dropping missing evidence or `Accountant review` flags to make output look complete.
- Using stale rates, thresholds, dates, or caps without checking the source.
- Presenting prep guidance as advice, final treatment, or lodgment-ready output.

## Source workflow

1. Read `references/rules.md` before classifying tax treatment.
2. Read `references/evidence.md` before deciding record status.
3. Check `references/sources.json` for source URLs, checked-at dates, and metadata-only sources.
4. If the skill bundles current values, use values only with their source URL, checked-at date, content hash, and effective period or income year when present.
5. Verify volatile rates, thresholds, caps, due dates, and income-year values against the official source before relying on them.

## Hard Safety Boundary

- Do not fabricate records, source support, source checks, or evidence.
- Do not hide income, omit private use, leave missing evidence unreported, or remove `Accountant review` flags.
- Do not treat metadata-only sources as source-backed tax treatment without explicit verification.
- Keep ambiguous, mixed-use, stale, unsupported, or material uncertainty as `Accountant review`.
- Never lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency.
- Refuse requests to submit, lodge, file, transmit, finalise, or send prepared material to the ATO.
- Do not present outputs as lodging-ready advice.

## Runtime handoff contract

- When the full runtime creates an HTML handoff, the runtime owns each atomic fact's action, destination, explanation, and provenance. Output layers render that contract and do not create destination logic.
- The seven actions are: enter reviewed value, answer guided question, retain evidence, resolve before entry, accountant handoff only, not entered directly, and destination requires review.
- A direct destination requires an exact field-and-context mapping to a verified source ID, canonical URL, and content hash. A broad topic link, row name, source coverage entry, or unverified target label is not a destination mapping.
- Missing, malformed, conflicting, unsupported, or stale mappings use evidence, non-entry, or review wording. `Accountant review` overrides entry-ready wording.
- Mixed rows use atomic field actions or separate rows so one destination is not applied to unrelated facts.

## Output states

- Supported record
- Claim candidate
- Not claimable
- Insufficient evidence
- Accountant review

## Required facts

Trust CGT, franked-distribution, streaming, and beneficiary-allocation handling is review-first and prep-only. Collect capital-gain components and discount signals, franked distribution and franking-credit amounts, deed and trustee-resolution records, streaming and specific-entitlement signals, the financial-benefit and recorded-in-character conditions, the component character and recording date, franking-integrity review signals, and beneficiary component allocations with source URLs and checked-at dates.

Keep trust entity facts only in isolated trust review rows. Missing deed power or evidence, financial-benefit or recorded-in-character conditions, component character, recording dates, resolutions, statements, franking-integrity review signals, unknown or malformed component amounts, unsupported allocation percentages or bases, conflicts, and invalid provenance stay Evidence or `Accountant review`. Preserve valid `0` amounts and `false` discount, streaming, deed, specific-entitlement, recorded-in-character, or qualified-person signals. Do not calculate trust CGT, test recording deadlines, apply discounts, determine specific entitlement, decide allocations or franking treatment, fill official forms, or lodge.

- income year or effective period
- taxpayer/entity and ownership
- business/private/employment purpose
- amounts excluding and including GST where relevant
- dates acquired, used, paid, received, and disposed
- records held and missing evidence
- prior claims, reimbursements, and duplicate-risk factors
