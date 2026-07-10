---
name: taxmate-australia-capital-gains-tax
description: Use when the user needs TaxMate Australia guidance for general CGT concepts and records.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
---

# TaxMate Australia Capital Gains Tax

Generated from TaxMate Australia source metadata. Verify volatile values before relying on them.

Use for general CGT concepts and records. Do not use for routine employee deductions or GST credits.

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
- main residence exemption claim, including false, uncertain, or partial claim signals
- main residence ownership, occupancy, and absence periods, preserving valid 0-day text
- rental or business use during ownership and spouse or partner main-residence conflict signals
- property records such as contract, settlement, rates, lease, occupancy, and absence-rule evidence
- main-residence source URLs and checked-at provenance for rows and evidence queues
- small business CGT concession claim status, concession type, business asset and active asset signals
- entity, affiliate, connected entity, retirement exemption, rollover, 15-year exemption, and 50% active asset reduction signals
- small-business CGT concession evidence, source URLs, and checked-at provenance for rows and evidence queues
