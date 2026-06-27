# Portable Skills Access (Optional)

Use portable skills only when you need quick ad-hoc use without the full plugin checkout.
Portable install needs Node.js 18 or newer and does not need a repository checkout, runtime binaries, marketplace JSON, plugin manifests, or environment variables.

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
