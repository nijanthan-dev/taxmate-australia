# TaxMate Australia

TaxMate Australia is an Australian tax prep skill pack and plugin linked to official ATO sources for conservative record review, GST/BAS and CGT triage, evidence gaps, accountant-ready workbook/taxpack handoff, print-first HTML guide handoffs, and treatment flags across Codex, Claude Code, Cowork, and OpenAgentSkill CLI.

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

## Output Handoff

Portable skills produce source-backed guidance, missing-evidence prompts, and conservative `Accountant review` routing. They do not need a checkout and do not render files.

The full runtime produces a print-first HTML handoff from reviewed or user-supplied facts. The handoff is a custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable. Users manually copy reviewed values into myTax, paper ATO forms, or an accountant handoff after evidence and review queues are resolved.

The current individual-return handoff includes:

- prep-only boundary and manual-copy warning;
- intake summary and AI extraction confirmation table;
- individual return field guide;
- itemized investment income rows for bank interest, dividends/franking, managed fund/ETF/AMIT distributions, and trust distribution routing;
- ABN prep section and BAS worksheet;
- missing facts queue, evidence queue, and accountant-review queue;
- source/provenance appendix with source URLs and checked-at dates.

## Preview

![Example TaxMate Australia self-prepared guide output for synthetic John Doe data](assets/readme/taxmate-guide-john-doe.png)

Example guide from synthetic sample data. Shows the overview, prep boundary, manual-copy warning, AI extraction confirmation table, field guide rows, investment income prep rows, evidence prompts, and `Accountant review` flags. Not an ATO form. Not fileable.

![Example TaxMate Australia manual-copy worksheet for synthetic John Doe data](assets/readme/taxmate-guide-john-doe-worksheet.png)

The lower handoff preview shows the evidence queue, accountant-review queue, row-level provenance, and the source/provenance appendix. The generated HTML also includes ABN prep, BAS worksheet, and missing-facts sections above this section.

Screenshot refresh commands:

```bash
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless --disable-gpu --hide-scrollbars --disable-background-networking \
  --disable-component-update --no-first-run --no-default-browser-check \
  --user-data-dir=/tmp/taxmate-chrome-profile --window-size=1040,720 \
  --screenshot=assets/readme/taxmate-guide-john-doe.png \
  file:///tmp/taxmate-guide.html
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --headless --disable-gpu --hide-scrollbars --disable-background-networking \
  --disable-component-update --no-first-run --no-default-browser-check \
  --user-data-dir=/tmp/taxmate-chrome-profile-long --window-size=1120,10000 \
  --screenshot=/tmp/taxmate-guide-full.png \
  file:///tmp/taxmate-guide.html
python3 scripts/png_crop.py /tmp/taxmate-guide-full.png \
  assets/readme/taxmate-guide-john-doe-worksheet.png 0 6900 1120 760
```

The sample data is synthetic. Any PR that changes user-facing output, output sections, screenshots/images, install/use docs, or individual-return handoff expectations must update README/docs in the same PR, or state why no docs update is needed.

## What It Does

- Reviews Australian tax prep records for employees, ESS, ETP/lump sum, foreign income, ABN/sole-trader work, itemized investment income and distributions, rental property, crypto, superannuation, and private health.
- Keeps ATO source URLs, checked-at dates, source coverage checks, and generated topic skills visible.
- Flags GST/BAS, PAYG, FBT, CGT, super guarantee, and stamp-duty source-routing items for conservative review.
- Builds accountant-facing workbook and taxpack outputs from reviewed data.
- Creates print-first HTML guides that help users manually copy reviewed answers into myTax, paper ATO forms, or an accountant handoff. TaxMate does not fill official ATO PDFs or create returns users can submit directly to the ATO.

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
Use the individual-return skill to prepare bank interest, dividend/franking, managed fund/ETF/AMIT, and trust distribution statement rows for review.
```

```text
Use the individual-return skill to prepare a rental property worksheet with income, interest, repairs, private use, depreciation, and net rental loss review.
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
