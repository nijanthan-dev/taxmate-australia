# Portable Skills Install

This is the fastest path for most users who want TaxMate inside an agent.
Use portable skills when you need quick ad-hoc guidance without the full plugin checkout.
Portable install needs Node.js 18 or newer and does not need a repository checkout, runtime binaries, marketplace JSON, plugin manifests, or environment variables.

Use the full runtime checkout only when you need the print-first HTML handoff, workbook/taxpack output, ATO source refresh, finance review scripts, calculators, or repository validation.

Portable skills produce source-backed guidance, evidence prompts, and `Accountant review` routing. They do not render the full runtime handoff.

The full runtime handoff is a custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable. Users manually copy reviewed values into myTax, paper ATO forms, or an accountant handoff after resolving missing facts, evidence gaps, and review queues.

Pinned CLI version: `skills@1.5.13`.

## Commands

Preview available install methods:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list
```

Global Codex install:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --skill '*' \
  --agent codex \
  --global \
  --yes
```

Project Codex install:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --skill '*' \
  --agent codex \
  --yes
```

One-skill install:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --skill taxmate-australia-capital-gains-tax \
  --agent codex \
  --global \
  --yes
```

Verify:

```bash
npx skills@1.5.13 list --agent codex --global
```

Use without install:

```bash
npx skills@1.5.13 use nijanthan-dev/taxmate-australia \
  --skill taxmate-australia-capital-gains-tax \
  --agent codex
```

## Repo-local workflow skill setup (full checkout only)

This repo also supports internal workflow SKILL folders under `local-skills/` that are installed from the checked-out repository, not from the public registry.

```bash
bash scripts/install-local-skills.sh --agent codex
```

Use `--agent claude` for Claude Code or Cowork-style local installs.

## Locations

- Project install: `.agents/skills/`
- Global install with `skills@1.5.13`: `~/.agents/skills/`

## Claude Code and Cowork

TaxMate portable skills use TaxMate Australia public names and the standard skill folder shape from the Claude guide:

```text
taxmate-australia-skill-name/
  SKILL.md
  references/
```

For Claude Code or Cowork, use the same public portable skill folders listed below. Each folder is self-contained, has `SKILL.md` with YAML frontmatter, and avoids checkout-only runtime commands.

Install through `skills@1.5.13` when possible so the installed folder matches the public `taxmate-australia-*` name. If you manually package a skill from this repository, use `config/public-skills.json` to map the public name to its source folder, and zip that folder with the public name. Do not zip the whole repository when you only want portable skill access.

Use the full plugin runtime only when you need the print-first HTML handoff, workbook/taxpack output, ATO refresh, finance review scripts, calculators, or repository validation.

## Public portable skills

The source of truth is `config/public-skills.json`.

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

## Update and removal

Update all global skills:

```bash
npx skills@1.5.13 update --global --yes
```

Update one skill:

```bash
npx skills@1.5.13 update taxmate-australia-capital-gains-tax --global --yes
```

Remove one skill:

```bash
npx skills@1.5.13 remove --skill taxmate-australia-capital-gains-tax --agent codex --global --yes
```

Remove all TaxMate skills:

```bash
npx skills@1.5.13 remove --skill '*' --agent codex --global --yes
```

For boundaries and professional-review expectations, see [DISCLAIMER.md](../DISCLAIMER.md).
