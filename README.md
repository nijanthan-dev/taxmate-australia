# TaxMate Australia

TaxMate Australia is a complete Codex plugin for Australian tax-prep review. It provides full runtime features, source-based generation, and conservative, source-linked workflows through the plugin architecture.

TaxMate Australia is only a preparation aid. It is not tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, investment advice, or a substitute for a qualified professional. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency.

TaxMate Australia must not lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency. If a user asks a skill to submit or lodge anything with the ATO, the skill must refuse and tell the user to use a qualified human tax professional or the official ATO channel themselves.

## Safety boundary

- Prep only: organise records, flag evidence gaps, draft handoff material, and preserve source URLs.
- No advice: do not present outputs as tax, financial, legal, accounting, BAS-agent, registered-tax-agent, or investment advice.
- No lodgment: do not submit to the ATO, even if the user requests it or says they accept the risk.
- Human review required: keep `Accountant review` visible for ambiguous, mixed-use, GST/BAS, CGT, FBT, home-business, pre-revenue, business-versus-hobby, non-commercial-loss, and uncertain items.
- Refuse unsafe requests: reject requests to bypass evidence, hide income, overclaim, fabricate records, remove review flags, or lodge/submit without human intervention.

## Install in 60 seconds

Primary install is the full plugin runtime (full feature set, CI-safe source pipeline, and audit tooling).

Prerequisites:

- Node.js 20 or newer.
- Bash, Python 3.9+, Git, curl, and jq.
- Codex for plugin-oriented workflows.

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
- Tax answer uncertain: keep `Accountant review`; do not guess.

## More docs

- Full plugin setup: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md)
- Optional portable install: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- Development: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Skill generation: [docs/SKILL_GENERATION.md](docs/SKILL_GENERATION.md)
- Disclaimer: [DISCLAIMER.md](DISCLAIMER.md)
