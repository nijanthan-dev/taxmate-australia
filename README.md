# TaxMate Australia

TaxMate Australia is an Australian tax prep skill pack and plugin linked to official ATO sources for conservative record review, GST/BAS and CGT triage, evidence gaps, accountant-ready workbook/taxpack handoff, ATO-aligned manual guide PDFs, and treatment flags across Codex, Claude Code, Cowork, and OpenAgentSkill CLI.

> [!WARNING]
> **Not tax advice.** TaxMate Australia is a preparation aid, not professional advice or lodgment software. For complex situations, binding decisions, or lodgment, consult a registered tax agent or use the official ATO channel directly. See [DISCLAIMER.md](DISCLAIMER.md).

## Choose Your Install

Pick the smallest path that matches what you need:

| Need | Install | What you get |
| --- | --- | --- |
| Quick use in Codex, Claude Code, Cowork, or OpenAgentSkill CLI | Portable skills | Topic guidance, source-backed review prompts, and `Accountant review` flags. No checkout required. |
| HTML guide, workbook/taxpack output, source refresh, finance review, calculators, or validation | Full runtime checkout | Bash + Python runtime, source pipeline, guide generation, and audit tooling. |
| Development, CI, or local plugin testing | Full runtime checkout + dev checks | Same runtime plus publication checks and local plugin metadata validation. |

Fast portable install:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --agent codex --global --skill '*' --yes
```

Portable details: [docs/INSTALLATION.md](docs/INSTALLATION.md).
Full runtime details: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md).

## Preview

![Example TaxMate Australia self-prepared guide output for synthetic John Doe data](assets/readme/taxmate-guide-john-doe.png)

Example guide from synthetic John Doe data. Shows interview answers, source-backed evidence prompts, and `Accountant review` flags. Not an ATO form. Not fileable.

![Example TaxMate Australia manual-copy worksheet for synthetic John Doe data](assets/readme/taxmate-guide-john-doe-worksheet.png)

The worksheet page shows manual-copy rows, source provenance, evidence prompts, and `Accountant review` flags.

## What It Does

- Reviews Australian tax prep records for employees, ESS, ETP/lump sum, foreign income, ABN/sole-trader work, investments, rental property, crypto, superannuation, and private health.
- Keeps ATO source URLs, checked-at dates, source coverage checks, and generated topic skills visible.
- Flags GST/BAS, PAYG, FBT, CGT, super guarantee, and stamp-duty source-routing items for conservative review.
- Builds accountant-facing workbook and taxpack outputs from reviewed data.
- Creates ATO-aligned manual guide PDFs that help users copy reviewed answers into myTax, paper ATO forms, or an accountant handoff. TaxMate does not fill official ATO PDFs or create returns users can submit directly to the ATO.

## Full Runtime Quickstart

Use this path when you need generated guides, workbook/taxpack outputs, source refresh, finance review, calculators, validation, or local plugin testing.

Prerequisites:

- Node.js 20 or newer.
- Bash, Python 3.9+, Git, curl, and jq.
- Codex for full plugin workflows; Claude Code, Cowork, or OpenAgentSkill CLI for portable skill workflows.

Clone and bootstrap:

```bash
git clone https://github.com/nijanthan-dev/taxmate-australia.git
cd taxmate-australia
bash scripts/bootstrap-dev-env.sh
```

Validate the checkout:

```bash
./scripts/taxmate validate
./scripts/taxmate skills generate --check
```

Full setup details: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md).

## Use It

For a broad individual return, start with [Individual Return Prep](docs/INDIVIDUAL_RETURN_PREP.md). It shows the portable skill path, the full-runtime HTML guide path, and the prep-only boundaries for myTax, paper ATO form, or accountant handoff.

Ask for a specific portable skill when the topic is clear:

```text
Use the individual-return skill to build a V1 individual return checklist with ABN and BAS review queues.
```

```text
Use the capital-gains-tax skill to review this disposal conservatively.
```

```text
Use the gst-bas skill to identify missing evidence and accountant-review items.
```

```text
Use the work-from-home skill for the 2025-26 income year and verify current rates before calculating anything.
```

Run full-runtime commands from a checkout:

```bash
./scripts/taxmate skills generate
./scripts/taxmate refresh --query "payg"
./scripts/taxmate intake individual --help
./scripts/taxmate finance --help
```

Create a self-prepared HTML guide users can save as PDF from their browser:

```bash
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
```

Open the HTML in a browser and use print/save as PDF. The printed PDF keeps the same guide layout and hides the preview toolbar. Rows can include `source_url`, `source_urls`, and `checked_at`; the guide keeps those provenance fields visible in the worksheet.

## Skills Included

Public portable entry points:

- `taxmate-australia`
- `individual-return`
- `employment-deductions`
- `work-from-home`
- `abn-business`
- `gst-bas`
- `payg-employer`
- `capital-gains-tax`
- `shares-etfs-managed-funds`
- `crypto-assets`
- `property-rental-cgt`
- `superannuation`
- `private-health-medicare`
- `records-evidence`
- `workbook`
- `taxpack`

Source artifacts are tracked in `data/ato_knowledge_base/source_coverage.json`, derived from `data/ato_knowledge_base/source_registry.json`.

## Development

Core checks:

```bash
PYTHONPYCACHEPREFIX=/tmp/taxmate-pycache python3 -m py_compile scripts/*.py
./scripts/taxmate validate
./scripts/taxmate skills generate --check
./scripts/taxmate skills audit --check
scripts/check-publication-ready.sh
```

Contributor flow and release checks: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Troubleshooting

- `npx: command not found`: install Node.js. Portable skills need Node.js 18 or newer; full-runtime workflows need Node.js 20 or newer.
- Plugin command not working: re-run `bash scripts/bootstrap-dev-env.sh` and verify `python3` + `bash` are available.
- Need portable-only access: use [docs/INSTALLATION.md](docs/INSTALLATION.md), not the full checkout path.

## More Docs

- Full plugin setup: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md)
- Optional portable install: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- Development: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Discovery metadata: [docs/DISCOVERY.md](docs/DISCOVERY.md)
- Skill generation: [docs/SKILL_GENERATION.md](docs/SKILL_GENERATION.md)
- Disclaimer: [DISCLAIMER.md](DISCLAIMER.md)
