# TaxMate Australia

TaxMate Australia is an Australian tax prep skill pack and plugin linked to official ATO sources for conservative record review, GST/BAS and CGT triage, evidence gaps, accountant-ready workbook/taxpack handoff, ATO-aligned manual guide PDFs, and treatment flags across Codex, Claude Code, Cowork, and OpenAgentSkill CLI.

> [!WARNING]
> **Not tax advice.** TaxMate Australia is a preparation aid, not professional advice or lodgment software. For complex situations, binding decisions, or lodgment, consult a registered tax agent or use the official ATO channel directly. See [DISCLAIMER.md](DISCLAIMER.md).

![Example TaxMate Australia self-prepared guide output for synthetic John Doe data](assets/readme/taxmate-guide-john-doe.png)

Example guide from synthetic John Doe data. Shows interview answers, source-backed evidence prompts, and `Accountant review` flags. Not an ATO form. Not fileable.

## What it helps with

- Australian tax prep workflows for employees, ABN/sole-trader records, investments, rental property, crypto, superannuation, and private health.
- ATO source refresh, source coverage checks, and generated topic skills with source URLs and checked-at dates.
- GST/BAS, PAYG, FBT, CGT, super guarantee, and stamp-duty source-routing scaffolds.
- Conservative finance review for CSV tax records, missing evidence, mixed-use items, and `Accountant review` queues.
- Accountant-facing Excel workbook and taxpack outputs from reviewed data.
- ATO-aligned manual guide PDFs that help users copy reviewed answers into myTax, paper ATO forms, or an accountant handoff. TaxMate does not fill official ATO PDFs or create returns users can submit directly to the ATO.

## Install in 60 seconds

Primary install is the full plugin runtime (full feature set, CI-safe source pipeline, and audit tooling).

Prerequisites:

- Node.js 20 or newer.
- Bash, Python 3.9+, Git, curl, and jq.
- Codex for full plugin workflows; Claude Code, Cowork, or OpenAgentSkill CLI for portable skill workflows.

- Clone and wire locally:

```bash
git clone https://github.com/nijanthan-dev/taxmate-australia.git
cd taxmate-australia
```

Run plugin bootstrap and validation:

```bash
bash scripts/bootstrap-dev-env.sh
```

Validate plugin and generated artifacts:

```bash
./scripts/taxmate validate
./scripts/taxmate skills generate --check
```

Run a full runtime command:

```bash
./scripts/taxmate skills generate
```

Create a self-prepared HTML guide users can save as PDF from their browser:

```bash
./scripts/taxmate taxpack sample-json --output /tmp/taxmate-guide-input.json
./scripts/taxmate taxpack guide-html \
  --input /tmp/taxmate-guide-input.json \
  --output /tmp/taxmate-guide.html
```

Open the HTML in a browser and use print/save as PDF. The printed PDF keeps the same guide layout and hides the preview toolbar.
Rows can include `source_url`, `source_urls`, and `checked_at`; the guide keeps those provenance fields visible in the worksheet.

Optional: install one or more portable skills for ad-hoc use without checkout:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --agent codex --global --skill '*' --yes
```

## First use

```text
Use the capital-gains-tax skill to review this disposal conservatively.
```

```text
Use the gst-bas skill to identify missing evidence and accountant-review items.
```

```text
Use the work-from-home skill for the 2025-26 income year and verify current rates before calculating anything.
```

## Public portable skills (optional)

If you need ad-hoc access without checkout, the public portable entry points remain available:

- `taxmate-australia`
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

## Installation modes

Full plugin path is recommended for production and plugin users:

```bash
cd /path/to/taxmate-australia
./scripts/taxmate skills validate
./scripts/taxmate refresh --query "payg"
./scripts/taxmate finance --help
```

## Update and remove (portable only)

Portable skills are optional. Update/remove portable skills with the `skills@1.5.13` package as needed, then keep plugin checkout refreshed for plugin/runtime parity.

## Troubleshooting

- `npx: command not found`: install Node.js 20 or newer for full-runtime workflows.
- Plugin command not working: re-run `bash scripts/bootstrap-dev-env.sh` and verify `python3` + `bash` are available.

## More docs

- Full plugin setup: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md)
- Optional portable install: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- Development: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Discovery metadata: [docs/DISCOVERY.md](docs/DISCOVERY.md)
- Skill generation: [docs/SKILL_GENERATION.md](docs/SKILL_GENERATION.md)
- Disclaimer: [DISCLAIMER.md](DISCLAIMER.md)
