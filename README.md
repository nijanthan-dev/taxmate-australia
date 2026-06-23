# TaxMate Australia

TaxMate Australia is an Australian tax-prep plugin for Codex. It combines official ATO source refresh, conservative tax treatment rules, transaction review, calculation scaffolds, and accountant-facing output workflows.
TaxMate Australia is a preparation aid, not professional tax, legal, accounting, financial, BAS-agent, or registered-tax-agent advice. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency. Read [DISCLAIMER.md](DISCLAIMER.md) before using it.

TaxMate Australia is a preparation aid, not professional tax, legal, accounting, financial, BAS-agent, or registered-tax-agent advice. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency. Read [DISCLAIMER.md](DISCLAIMER.md) before using it.

Ambiguous, material, mixed-use, pre-revenue, home-business, FBT, CGT, GST/BAS, non-commercial-loss, and business-versus-hobby items should stay marked `Accountant review` unless the facts and official guidance clearly resolve them.

## Why it exists

- Reduce over-claim risk with conservative defaults.
- Make ATO interpretation and records traceable.
- Surface accountant handoff items early, before deadlines.
- Keep calculation output and reporting artifacts separate from tax treatment logic.

## What this plugin delivers

- ATO source refresh + search from bundled official pages.
- Structured review of transactions/receipts/bank exports.
- Bounded calculator paths for PAYG, BAS, CGT, FBT, super, and stamp duty routing.
- Workbook and taxpack outputs designed for handoff, not lodgment.

## Who it is for

- Individuals with Australian tax records needing a fast first-pass review.
- ABN holders who need GST/BAS and expense signal separation.
- Teams using Codex or Claude wanting consistent prompts and repeatable output layers.

## Plugin layout

- `.codex-plugin/plugin.json`: plugin metadata and marketplace card text.
- `skills/research`: official ATO research + conservative treatment logic.
- `skills/finance-review`: transaction and evidence review.
- `skills/calculators`: bounded calculation scaffolds.
- `skills/workbook`: structured accountant-facing spreadsheet output.
- `skills/taxpack`: handoff package and future PDF/form draft path.
- `bin/`, `cmd/`, `internal/`: shared Go binaries and backend.
- `data/ato_knowledge_base/`: official ATO source pack.
- `wrappers/`: compatibility wrappers for runtimes with different skill loading behavior.

## Runtime support

Codex is the primary runtime. Skill files are plain Markdown with frontmatter, and the backend is a portable Go CLI. Claude or other runtimes can add wrappers without changing tax logic.

## Install this plugin

### Codex (recommended local install)

1. Clone this repository.
2. Set the plugin root.
3. Build and validate before first use.

```bash
git clone https://github.com/nijanthan-dev/taxmate-au.git
cd taxmate-au
export TAXMATE_AU_ROOT="$PWD"
cd "$TAXMATE_AU_ROOT"
go test ./...
go build -o bin/taxmate-au-refresh ./cmd/taxmate-au-refresh
go build -o bin/taxmate-au-validate ./cmd/taxmate-au-validate
go build -o bin/taxmate-au-finance ./cmd/taxmate-au-finance
go build -o bin/taxmate-au-calc ./cmd/taxmate-au-calc
"$TAXMATE_AU_ROOT/bin/taxmate-au-validate"
```

Then point your Codex plugin path to this checkout (or keep the repo in your normal Codex/plugin workspace). Once loaded, skills resolve via `.codex-plugin/plugin.json`.

### Claude / other runtimes

Use the compatibility wrapper files if your runtime loads `~/.agents/skills`:

- `wrappers/taxmate-au/SKILL.md`
- `wrappers/taxmate-au-finance-review/SKILL.md`
- `wrappers/taxmate-au-calculators/SKILL.md`
- `wrappers/taxmate-au-workbook/SKILL.md`
- `wrappers/taxmate-au-taxpack/SKILL.md`

Copy these wrappers into your agent skill path, keep this repo checked out locally, and set `TAXMATE_AU_ROOT` to the local plugin root.

## Scope boundaries

- Tax treatment must stay in `research`, `finance-review`, and `calculators`.
- Output layers (`workbook`, `taxpack`) must consume reviewed data and must not invent tax treatment.
- Stamp duty uses state/territory source routing only, not embedded rate tables.
- Non-ATO commercial sources are out of scope unless explicitly requested.

## Trust and citations

The bundled source pack is ATO-first. Stamp duty is source-routed to official state or territory revenue offices. Non-ATO commercial sources are out of scope unless a user explicitly asks for them.
ATO and Commonwealth material remains subject to the notices and terms published by the relevant official source. TaxMate Australia must not imply official endorsement.
No official tax filing is performed by this plugin.
