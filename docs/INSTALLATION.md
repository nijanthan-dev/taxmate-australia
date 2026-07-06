# Install TaxMate Australia

Use the Codex plugin install when you want TaxMate to generate files such as the print-first HTML guide, taxpack output, source refresh results, finance review output, or calculator output.

Use `npx skills` only when you want guidance in chat. That install does not include the renderer, root runtime scripts, `runtime/`, or `wrappers/`.

TaxMate outputs are preparation aids only. The HTML guide is a custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable. Users manually copy reviewed values into myTax, paper ATO forms, or an accountant handoff after resolving missing facts, evidence gaps, and `Accountant review` queues.

## Codex Plugin Install

Prerequisites:

- Codex CLI.
- Bash.
- Python 3.9+.

Install the plugin:

```bash
codex plugin marketplace add nijanthan-dev/taxmate-australia
codex plugin add taxmate-australia@taxmate-local-marketplace
```

Then ask Codex to use TaxMate Australia:

```text
Use TaxMate Australia to validate the runtime.
```

```text
Use TaxMate Australia to write sample individual answers and render the individual-return HTML guide.
```

The installed plugin exposes TaxMate runtime tools for:

- `calc`
- `finance`
- `intake`
- `refresh`
- `review-guardrails`
- `skills`
- `taxpack`
- `validate`

The individual-return HTML guide includes the prep-only boundary, manual-copy warning, intake summary, AI extraction confirmation table, individual return field guide, PAYG rows, investment rows, CGT schedule and item rows, ABN prep section, BAS worksheet, missing facts queue, evidence queue, accountant-review queue, source URLs, checked-at dates, and source/provenance appendix.

## Optional Guidance-Only Skills

Pinned CLI version: `skills@1.5.13`.

Preview available skills:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia --list
```

Install all public skills for Codex:

```bash
npx skills@1.5.13 add nijanthan-dev/taxmate-australia \
  --skill '*' \
  --agent codex \
  --global \
  --yes
```

Install one skill:

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

Guidance-only install locations:

- Project install: `.agents/skills/`
- Global install with `skills@1.5.13`: `~/.agents/skills/`

## Claude Code and Cowork

For Claude Code or Cowork, use the public TaxMate skill folders. Each folder is self-contained, has `SKILL.md` with YAML frontmatter, and avoids plugin-runtime commands.

Install through `skills@1.5.13` when possible so the installed folder matches the public `taxmate-australia-*` name. If you manually package a skill from this repository, use `config/public-skills.json` to map the public name to its source folder, and zip that folder with the public name. Do not zip the whole repository when you only want guidance-only skill access.

Use the Codex plugin install when you need the print-first HTML handoff, taxpack output, ATO refresh, finance review scripts, calculators, or repository validation.

## Public Guidance Skills

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

## Update and Removal

Update all global guidance skills:

```bash
npx skills@1.5.13 update --global --yes
```

Update one guidance skill:

```bash
npx skills@1.5.13 update taxmate-australia-capital-gains-tax --global --yes
```

Remove one guidance skill:

```bash
npx skills@1.5.13 remove --skill taxmate-australia-capital-gains-tax --agent codex --global --yes
```

Remove all TaxMate guidance skills:

```bash
npx skills@1.5.13 remove --skill '*' --agent codex --global --yes
```

For boundaries and professional-review expectations, see [DISCLAIMER.md](../DISCLAIMER.md).
