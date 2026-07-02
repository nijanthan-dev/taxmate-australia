---
name: taxmate-australia-crypto-assets
description: Crypto disposals, swaps, exchanges, conversions, staking/rewards, transfers, wallet/exchange records, ownership, cost-base, proceeds, and CGT review boundaries. Use for crypto asset events, records, and conservative CGT prep workflow.
compatibility: Portable skill for Claude Code, Cowork, Codex, and OpenAgentSkill CLI. No checkout required.
---

# TaxMate Australia Crypto Assets

Generated from TaxMate Australia source metadata. Verify volatile values before relying on them.

Use for crypto asset events, records, and conservative CGT prep workflow. Do not use for shares, ETFs, or non-crypto CGT.

## Source workflow

1. Read `references/rules.md` before classifying tax treatment.
2. Read `references/evidence.md` before deciding record status.
3. Check `references/sources.json` for source URLs, checked-at dates, and metadata-only sources.
4. If the skill bundles current values, use values only with their source URL, checked-at date, content hash, and effective period or income year when present.
5. Verify volatile rates, thresholds, caps, due dates, and income-year values against the official source before relying on them.

## Hard Safety Boundary

- Do not fabricate records, source support, source checks, or evidence.
- Do not hide income, omit private use, suppress missing evidence, or remove `Accountant review` flags.
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
- crypto event type such as sale, swap, exchange, conversion, staking, reward, transfer, spend, or gift
- asset name or ticker, quantity, exchange/wallet, and wallet or exchange records
- acquisition date, disposal date, cost base, capital proceeds, and rewards income where relevant
- owner/entity plus both business and private use context flags
- own-wallet transfer support and records preserving source provenance
