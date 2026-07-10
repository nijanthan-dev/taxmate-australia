---
name: taxmate-australia-private-health-medicare
description: Use when the user needs TaxMate Australia guidance for private health and Medicare levy questions.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
---

# TaxMate Australia Private Health Medicare

Generated from TaxMate Australia source metadata. Verify volatile values before relying on them.

Use for private health and Medicare levy questions. Do not use for deductibility of business or employment expenses.

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
- Private health statement routes depend on the supplied tax claim code: A, B, and C can map the code and J/K/L fields in myTax and paper after review; D is read-only in myTax and maps the code and J/K/L fields on paper; E maps the code but not J/K/L in myTax and maps the code and J/K/L fields on paper; F maps the code but J/K/L are not entered in either channel.
- Medicare levy M1 maps the guided myTax exemption-category question and supported full/half exemption day fields; paper mapping is limited to verified labels V and W, while the generic paper category question requires review. An explicit no-exemption answer with no category or day values makes those detail fields not entered directly; supplied category or positive-day conflicts require review.
- Medicare levy surcharge M2 maps question E only from an explicit local answer to whether the user and all dependants had an appropriate level of private patient hospital cover for the full income year. A true answer also requires 365 supplied cover days, an explicit appropriate-cover signal, and no period conflict. Days not liable can map to paper label A only after an explicit No at E; myTax may skip its days field after the income check, so that channel keeps conditional review wording. E Yes makes the days field non-entry, and missing or conflicting E context requires review.
- The had-spouse question has a verified myTax destination. The generic paper had-spouse destination and spouse income aggregates require review unless an exact mapping is added.
- These mappings prepare questions and reviewed values only. They do not calculate a levy, surcharge, rebate, entitlement, or final tax.

## Output states

- Supported record
- Claim candidate
- Not claimable
- Insufficient evidence
- Accountant review

## Required facts

- income year or effective period
- taxpayer/entity and ownership
- business/private/employment purpose
- amounts excluding and including GST where relevant
- dates acquired, used, paid, received, and disposed
- records held and missing evidence
- prior claims, reimbursements, and duplicate-risk factors
- one row for each private health statement line, including health insurer or fund, membership or policy identifier, benefit code, premiums eligible for rebate, rebate received, tax claim code, cover days or period, and statement evidence
- private hospital cover status and full-year, partial-year, or no-cover periods
- Medicare levy exemption or reduction signals and supporting evidence
- Medicare levy surcharge income, tier, hospital-cover, spouse, and family review signals without calculating a surcharge
- spouse period and spouse income-test facts plus dependant child or student facts
- row-specific source URLs, checked-at provenance, evidence gaps, and Accountant review routing
