# TaxMate Australia

TaxMate Australia helps Codex, Claude Code, Cowork, and OpenAgentSkill CLI prepare Australian individual tax return materials with conservative checklists, review flags, accountant handoffs, and print-first HTML guides. It is linked to official ATO sources and keeps GST/BAS, CGT, missing evidence, and manual-copy boundaries visible.

> [!WARNING]
> **Not tax advice.** TaxMate Australia is a preparation aid, not professional advice or lodgment software. For complex situations, binding decisions, or lodgment, consult a registered tax agent or use the official ATO channel directly. See [DISCLAIMER.md](DISCLAIMER.md).

## Choose Your Install

Pick the smallest path that matches what you need:

| Need | Install | What you get |
| --- | --- | --- |
| HTML guide, taxpack output, source refresh, finance review, or calculators in Codex or Claude Code | Plugin install | Bash + Python runtime, Node.js MCP launcher, source pipeline, guide generation, and audit tooling. |
| Quick use in Codex, Claude Code, Cowork, or OpenAgentSkill CLI | `npx skills` guidance only | Topic guidance, source-backed review prompts, and `Accountant review` flags. No renderer or runtime scripts. |

Codex plugin install:

```bash
codex plugin marketplace add nijanthan-dev/taxmate-australia
codex plugin add taxmate-australia@taxmate-local-marketplace
```

Claude Code plugin install:

```bash
claude plugin marketplace add nijanthan-dev/taxmate-australia
claude plugin install taxmate-australia@taxmate-australia
```

After install, ask your agent to use TaxMate Australia to validate the runtime, create sample individual answers, or render the individual-return HTML guide.

Optional `npx skills` guidance-only install:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --agent codex --global --skill '*' --yes
```

Use `--agent claude-code` instead of `--agent codex` for Claude Code guidance-only skill installs. Generated files in Claude Code need the Claude Code plugin install above.

Install details: [docs/INSTALLATION.md](docs/INSTALLATION.md).
Developer runtime details: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md).

## Output Handoff

The optional `npx skills` install produces source-backed guidance, missing-evidence prompts, and conservative `Accountant review` routing. It does not install the renderer and does not render files.

The plugin runtime produces a print-first HTML handoff from reviewed or user-supplied facts. The handoff is a custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable. Users manually copy reviewed values into myTax, paper ATO forms, or an accountant handoff after evidence and review queues are resolved.

The current individual-return handoff includes:

- prep-only boundary and manual-copy warning;
- intake summary and AI extraction confirmation table;
- individual return field guide;
- primary and secondary PAYG income statement rows with payer, ABN, occupation, gross, withholding, allowances, RFBA, RESC, lump sum labels, statement evidence, and aggregate reconciliation;
- itemized investment income rows for bank interest, dividends/franking, managed fund/ETF/AMIT distributions, and trust distribution routing;
- general CGT event schedule and itemized non-crypto/non-rental CGT event rows with records, current-year and carried-forward loss facts, discount, foreign-resident discount, main residence, and small-business CGT concession review signals, source provenance, reconciliation prompts, and amount-not-worked-out wording;
- itemized deduction rows for gifts/donations, tax affairs costs, income protection, self-education, union/professional fees, work travel/car/public transport, tools/equipment/assets, personal super contribution deduction prep, and offset routing, all with evidence and review queues;
- phone plan/data/device/incidental-use rows with WFH fixed-rate double-dip blocking, employer paid/reimbursed/provided exclusions, evidence prompts, and ABN/GST/BAS review routing;
- ABN prep section and BAS worksheet, including ABN profile, income streams, expense categories, 1A/1B, GST-free/input-taxed sales, adjustments, PAYG labels, tax invoice evidence, and accounting-basis review;
- missing facts queue, evidence queue, and accountant-review queue;
- source/provenance appendix with source URLs and checked-at dates.

## Preview

![Example TaxMate Australia self-prepared guide output for synthetic John Doe data](assets/readme/taxmate-guide-john-doe.png)

Example guide from synthetic sample data. Shows the overview, prep boundary, manual-copy warning, AI extraction confirmation table, field guide rows, PAYG income statement rows, investment income prep rows, evidence prompts, and `Accountant review` flags. Not an ATO form. Not fileable.

![Example TaxMate Australia manual-copy worksheet for synthetic John Doe data](assets/readme/taxmate-guide-john-doe-worksheet.png)

The lower handoff preview shows itemized deduction and personal-super rows with accountant-review tabs and row-level provenance. The generated HTML also includes offset routing, ABN prep, BAS worksheet, missing facts, evidence queue, accountant-review queue, and source/provenance appendix.

The sample data is synthetic. Screenshot maintenance is a contributor task documented in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## What It Does

- Helps users prepare PAYG income statements, ABN/sole-trader facts, GST/BAS facts, investment statements, general CGT event and main residence exemption claim facts, rental property facts, crypto events, deductions, superannuation, private health, offsets, and other individual-return material.
- Keeps missing-evidence prompts, review queues, source-backed notes, and conservative `Accountant review` flags visible.
- Keeps source URLs, checked-at dates, source coverage checks, and generated topic skills visible.
- Audits verified source coverage against runtime/docs/tests status with `./scripts/taxmate coverage audit`.
- Builds taxpack and print-first HTML guide handoffs from reviewed data.
- Helps users manually copy reviewed answers into myTax, paper ATO forms, or an accountant handoff. TaxMate does not fill official ATO PDFs or create returns users can submit directly to the ATO.

## Use It

Start with the outcome, not an internal command. For a broad individual return, [Individual Return Prep](docs/INDIVIDUAL_RETURN_PREP.md) shows the guidance-only skill path, the plugin HTML guide path, and the prep-only boundaries for myTax, paper ATO form, or accountant handoff.

Talk to the agent in natural language. TaxMate works best when the user describes the income year, the return sections involved, the facts they have, and what they want prepared. The agent can use a specific guidance skill when the topic is clear, or use the installed plugin when you want a rendered HTML handoff.

Broad prep examples:

```text
Help me prepare my 2025-26 Australian individual tax return. Ask for the facts you need, keep missing evidence visible, and flag anything that needs accountant review.
```

```text
I have PAYG income statements, some bank interest and dividends, and a small ABN side business. Help me prepare a prep-only individual tax return review checklist for myTax or my accountant.
```

```text
I am GST registered and have ABN income, expenses, tax invoices, and BAS period facts. Use the taxmate-australia-individual-return, taxmate-australia-abn-business, and taxmate-australia-gst-bas skills to prepare the income-tax and BAS review items without treating anything as lodged or final.
```

Topic examples:

```text
Use the taxmate-australia-individual-return skill to prepare PAYG income statement rows from these employer statements, keep payer ABNs, gross, withholding, allowances, RFBA, RESC, lump sum labels, statement evidence, and reconciliation gaps visible.
```

```text
Use the taxmate-australia-individual-return skill to prepare investment income rows from my bank interest, dividend/franking, managed fund/ETF/AMIT, and trust distribution statements.
```

```text
Use the taxmate-australia-individual-return skill to prepare itemized deduction rows from my gifts, tax agent fees, income protection, self-education, union fees, work travel, tools/assets, personal super contribution deduction facts, and offset signals. Keep receipts, reimbursements, employer-paid/provided flags, work/private splits, GST/BAS overlap, duplicate-risk, notice of intent, fund acknowledgement, cap/Division 293 review, and source provenance visible.
```

```text
Use the taxmate-australia-individual-return skill to prepare itemized CGT event review rows from my asset list, owners, acquisition and disposal dates, proceeds, cost base, incidental costs, current-year and carried-forward capital loss facts, discount timing or review signals, foreign-resident discount signals, small-business concession claim facts, concession type, active asset and entity/affiliate/connected entity facts, records, and review flags. Reconcile supplied totals only as prep evidence. Do not work out capital gain/loss amounts or concession amounts.
```

```text
Use the taxmate-australia-capital-gains-tax skill to review this asset disposal conservatively. Include any main residence claim facts, ownership and occupancy periods, rental/business use, absence periods, spouse/partner main-residence conflicts, small-business concession signals, property records, and rental-property overlap signals. Show the facts still needed before anyone relies on the CGT treatment; do not work out exemption or concession amounts.
```

```text
Use the taxmate-australia-individual-return skill to prepare a rental property worksheet from my rent, loan interest, repairs, private use, depreciation, records, and net rental loss facts.
```

```text
Use the taxmate-australia-gst-bas skill to review my 1A GST collected, 1B GST credits, GST-free/input-taxed sales, adjustments, PAYG labels, tax invoices, accounting basis, and BAS period. Identify missing evidence and accountant-review items only; do not lodge anything.
```

```text
Use the taxmate-australia-work-from-home skill for the 2025-26 income year and verify current rates before calculating anything.
```

HTML handoff examples:

```text
Use the installed TaxMate Australia plugin to prepare the print-first individual return HTML guide from my reviewed answers, then tell me where the file is so I can open it and save it as PDF from my browser.
```

```text
I have a reviewed answers file. Use TaxMate to create the prep-only HTML handoff with the AI confirmation table, PAYG rows, investment rows, deduction/super/offset rows, CGT schedule and item rows, detailed ABN prep, BAS worksheet, review queues, and source/provenance appendix.
```

If you are using `npx skills` guidance only, the agent can build the checklist, review prompts, manual-copy guidance, and source-backed review flags in chat. Rendering the HTML file needs the plugin runtime.

## Plugin Runtime Quickstart

Plugin install is the real TaxMate install. Use it when you need generated guides, taxpack output, source refresh, finance review, or calculators.

Prerequisites:

- Codex or Claude Code.
- Node.js 20+ for the MCP launcher.
- Bash and Python 3.9+ for the plugin runtime.

Install for Codex:

```bash
codex plugin marketplace add nijanthan-dev/taxmate-australia
codex plugin add taxmate-australia@taxmate-local-marketplace
```

Install for Claude Code:

```bash
claude plugin marketplace add nijanthan-dev/taxmate-australia
claude plugin install taxmate-australia@taxmate-australia
```

Setup details: [docs/INSTALLATION.md](docs/INSTALLATION.md).

Ask your agent to use the TaxMate Australia tools:

```text
Use TaxMate Australia to validate the runtime.
```

```text
Use TaxMate Australia to write sample individual answers and render the individual-return HTML guide.
```

Open the HTML in a browser and use print/save as PDF. The printed PDF keeps the same guide layout and hides the preview toolbar. Rows can include `source_url`, `source_urls`, and `checked_at`; the guide keeps those provenance fields visible in the worksheet.

Developer fallback from a cloned repository is documented in [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md).

## Skills Included

Public guidance skill entry points:

- `taxmate-australia`
- `taxmate-australia-individual-return`
- `taxmate-australia-employment-deductions`
- `taxmate-australia-work-from-home`
- `taxmate-australia-abn-business`
- `taxmate-australia-gst-bas`
- `taxmate-australia-payg-employer`
- `taxmate-australia-capital-gains-tax`
- `taxmate-australia-shares-etfs-managed-funds`
- `taxmate-australia-crypto-assets`
- `taxmate-australia-property-rental-cgt`
- `taxmate-australia-superannuation`
- `taxmate-australia-private-health-medicare`
- `taxmate-australia-records-evidence`
- `taxmate-australia-workbook`
- `taxmate-australia-taxpack`

Source artifacts are tracked in `data/ato_knowledge_base/source_coverage.json`, derived from `data/ato_knowledge_base/source_registry.json`.

## Development

Contributor flow, release checks, screenshot maintenance, and repository guardrails: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Troubleshooting

- Plugin install fails: verify Codex or Claude Code is installed with Node.js 20+, then re-run the matching plugin install commands in [docs/INSTALLATION.md](docs/INSTALLATION.md).
- `node: command not found`: install Node.js 20+ so the plugin MCP launcher can start.
- HTML guide command fails: ask Codex to run TaxMate runtime validation and verify `python3` + `bash` are available.
- `npx: command not found`: install Node.js 20+. The plugin needs Node.js for MCP startup; `npx` is only for optional guidance-only skill installs.
- Need guidance only: use the optional `npx skills` commands in [docs/INSTALLATION.md](docs/INSTALLATION.md).

## More Docs

- Install: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- Developer runtime fallback: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md)
- Development: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Discovery metadata: [docs/DISCOVERY.md](docs/DISCOVERY.md)
- Skill generation: [docs/SKILL_GENERATION.md](docs/SKILL_GENERATION.md)
- Disclaimer: [DISCLAIMER.md](DISCLAIMER.md)
