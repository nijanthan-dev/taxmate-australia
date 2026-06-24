# TaxMate Australia

TaxMate Australia is a portable Codex skill set for Australian tax-prep review. It helps route records and questions into conservative, source-linked, accountant-ready workflows.

TaxMate Australia is only a preparation aid. It is not tax advice, financial advice, legal advice, accounting advice, BAS-agent advice, registered-tax-agent advice, investment advice, or a substitute for a qualified professional. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency.

TaxMate Australia must not lodge, file, submit, transmit, or finalise any tax return, BAS, form, statement, objection, election, payment instruction, or other material with the ATO or any government agency. If a user asks a skill to submit or lodge anything with the ATO, the skill must refuse and tell the user to use a qualified human tax professional or the official ATO channel themselves.

## Safety boundary

- Prep only: organise records, flag evidence gaps, draft handoff material, and preserve source URLs.
- No advice: do not present outputs as tax, financial, legal, accounting, BAS-agent, registered-tax-agent, or investment advice.
- No lodgment: do not submit to the ATO, even if the user requests it or says they accept the risk.
- Human review required: keep `Accountant review` visible for ambiguous, mixed-use, GST/BAS, CGT, FBT, home-business, pre-revenue, business-versus-hobby, non-commercial-loss, and uncertain items.
- Refuse unsafe requests: reject requests to bypass evidence, hide income, overclaim, fabricate records, remove review flags, or lodge/submit without human intervention.

## Install in 60 seconds

Prerequisites:

- Node.js 18 or newer.
- Codex for Codex-targeted install commands.

Preview available portable skills:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list
```

Install all portable skills globally for Codex:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --skill '*' \
  --agent codex \
  --global \
  --yes
```

Install all portable skills in the current project:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --skill '*' \
  --agent codex \
  --yes
```

Install one skill:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --skill capital-gains-tax \
  --agent codex \
  --global \
  --yes
```

Use one skill without installing it:

```bash
npx skills@1.5.13 use nijanthan-dev/taxmate-australia \
  --skill capital-gains-tax \
  --agent codex
```

## Verify install

```bash
npx skills@1.5.13 list --agent codex --global
```

Expected Codex locations:

- Project: `.agents/skills/`
- Global with `skills@1.5.13`: `~/.agents/skills/`

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

## Portable skills

The public portable skills are:

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

Portable skills depend only on their own `SKILL.md`, bundled `references/`, official source URLs, and the agent's web access when available. They do not require Go, TaxMate binaries, a repository checkout, plugin manifests, marketplace JSON, or `TAXMATE_AUSTRALIA_ROOT`.

## Installation modes

| Capability | Portable skills | Full runtime |
|---|---:|---:|
| Topic guidance | Yes | Yes |
| Bundled references | Yes | Yes |
| Official source links | Yes | Yes |
| Live Go source refresh | No | Yes |
| CSV finance review | No | Yes |
| Calculator CLI | No | Yes |
| Skill regeneration | No | Yes |
| Plugin orchestration | No | Yes |

Portable skills are recommended. Full runtime is advanced and needs Go 1.22 or newer plus a repository checkout.

## Update and remove

Update all installed TaxMate skills:

```bash
npx skills@1.5.13 update --global --yes
```

Update one TaxMate skill:

```bash
npx skills@1.5.13 update capital-gains-tax --global --yes
```

Remove one TaxMate skill:

```bash
npx skills@1.5.13 remove --skill capital-gains-tax --agent codex --global --yes
```

Remove all TaxMate skills:

```bash
npx skills@1.5.13 remove --skill '*' --agent codex --global --yes
```

## Troubleshooting

- `npx: command not found`: install Node.js 18 or newer.
- Skill missing after install: run `npx skills@1.5.13 list --agent codex --global`.
- Project install not visible: check `.agents/skills/` in the current project.
- Global install not visible: check `~/.agents/skills/`.
- Tax answer uncertain: keep `Accountant review`; do not guess.

## More docs

- Portable install: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- Full runtime install: [docs/FULL_PLUGIN_INSTALL.md](docs/FULL_PLUGIN_INSTALL.md)
- Development: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- Skill generation: [docs/SKILL_GENERATION.md](docs/SKILL_GENERATION.md)
- Disclaimer: [DISCLAIMER.md](DISCLAIMER.md)
