# Portable Skills Install

This is the fastest path for most users who want TaxMate inside an agent.
Use portable skills when you need quick ad-hoc guidance without the full plugin checkout.
Portable install needs Node.js 18 or newer and does not need a repository checkout, runtime binaries, marketplace JSON, plugin manifests, or environment variables.

Use the full runtime checkout only when you need guide generation, workbook/taxpack output, ATO source refresh, finance review scripts, calculators, or repository validation.

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
  --skill capital-gains-tax \
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
  --skill capital-gains-tax \
  --agent codex
```

## Locations

- Project install: `.agents/skills/`
- Global install with `skills@1.5.13`: `~/.agents/skills/`

## Claude Code and Cowork

TaxMate portable skills use the standard skill folder shape from the Claude guide:

```text
skill-name/
  SKILL.md
  references/
```

For Claude Code or Cowork, use the same public portable skill folders listed below. Each folder is self-contained, has `SKILL.md` with YAML frontmatter, and avoids checkout-only runtime commands.

Install by downloading or copying the selected `skills/skill-name` folder into the skill location supported by your Claude Code or Cowork setup, or upload the zipped skill folder when the product UI asks for a skill package. Do not zip the whole repository when you only want portable skill access.

Use the full plugin runtime only when you need guide generation, workbook/taxpack output, ATO refresh, finance review scripts, calculators, or repository validation.

## Public portable skills

The source of truth is `config/public-skills.json`.

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

## Update and removal

Update all global skills:

```bash
npx skills@1.5.13 update --global --yes
```

Update one skill:

```bash
npx skills@1.5.13 update capital-gains-tax --global --yes
```

Remove one skill:

```bash
npx skills@1.5.13 remove --skill capital-gains-tax --agent codex --global --yes
```

Remove all TaxMate skills:

```bash
npx skills@1.5.13 remove --skill '*' --agent codex --global --yes
```

For boundaries and professional-review expectations, see [DISCLAIMER.md](../DISCLAIMER.md).
