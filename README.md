# TaxMate Australia

TaxMate Australia is an Australian tax-prep plugin for Codex. It combines official ATO source refresh, conservative tax treatment rules, transaction review, calculation scaffolds, and accountant-facing output workflows.
TaxMate Australia is a preparation aid, not professional tax, legal, accounting, financial, BAS-agent, or registered-tax-agent advice. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency. Read [DISCLAIMER.md](DISCLAIMER.md) before using it.
TaxMate Australia is an OpenAI Codex plugin: a packaged workflow bundle for Australian tax-prep review work.

It connects official ATO research, transaction/evidence review, and bounded calculator scaffolds to output layers that support handoff to a tax professional.

The plugin is a preparation aid, not professional tax, legal, accounting, financial, BAS-agent, or registered-tax-agent advice. It is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office or any government agency. Read [DISCLAIMER.md](DISCLAIMER.md).

## Plugin model and boundaries

OpenAI treats:

- **Plugin** as a package that can include skills, MCP servers, and app bindings.
- **Skill** as a playbook-like prompt+workflow for how Codex should do work.

TaxMate uses:

- `skills/` for operational behavior and output conventions.
- `cmd/` and `internal/` for shared tax-review runtime logic.
- `.codex-plugin/plugin.json` for marketplace and install metadata.

Scope boundaries are intentionally strict:

- ATO-first sources only.
- Any `Accountant review` item stays flagged when facts are incomplete or ambiguous.
- No official filing/ lodgment is performed by this plugin.

## What this plugin includes

- Official-source research and evidence review workflow.
- Conservative treatment and uncertainty flags for mixed-use, pre-revenue, FBT/CGT/GST, and home-business edge cases.
- Calculator scaffolds for PAYG, BAS, and supporting Australian tax workflows.
- Output layers: `skills/workbook` and `skills/taxpack` for handoff quality.

## OpenAI plugin definition used here

Most mature Codex plugins follow the same manifest shape:
- `.codex-plugin/plugin.json` is required.
- fields like `name`, `version`, `description`, `author.name`, and `interface` are required.
- common optional top-level fields: `homepage`, `repository`, `license`, and `keywords`.
- all manifest paths are relative and start with `./`.

A representative minimal shape:

```json
{
  "name": "taxmate-australia",
  "version": "0.1.0",
  "description": "ATO-backed Australian tax-prep workflow for Codex and Claude",
  "author": {
    "name": "TaxMate Australia Maintainers"
  },
  "interface": {
    "displayName": "TaxMate Australia",
    "shortDescription": "ATO-backed Australian tax-prep workflow",
    "longDescription": "Converts messy tax inputs into ATO-sourced review-ready recommendations.",
    "category": "Productivity",
    "capabilities": ["Read", "Write"],
    "developerName": "TaxMate AU Maintainers",
    "websiteURL": "https://www.ato.gov.au/",
    "defaultPrompt": [
      "Review these tax expenses conservatively for my accountant.",
      "Summarize ATO-linked tax risk flags."
    ],
    "brandColor": "#1B5E20",
    "composerIcon": "./assets/icon.png",
    "logo": "./assets/icon.png",
    "logoDark": "./assets/logo-dark.png"
  },
  "skills": "./skills/"
}
```

## What successful plugins document and include

I sampled the official ecosystem (including the `openai/plugins` directory with 150+ plugin entries) and mature community plugin repos. Common patterns are:

- a plugin-level README explaining scope and how to use the plugin;
- explicit plugin structure (`.codex-plugin`, `skills`, optional `.app.json`, optional `.mcp.json`, optional `agents`, `assets`);
- optional tool glue (`commands/`, `hooks.json`, `scripts/`, `ui/`);
- optional lock metadata (`plugin.lock.json`) when release hygiene matters;
- explicit install path expectations and marketplace entry snippets.

## Plugin layout

### Plugin layout
 
- `.codex-plugin/plugin.json`: required plugin manifest.
- `skills/`
  - `research` — source-first treatment and reference checks.
  - `finance-review` — transaction and evidence review.
  - `calculators` — calculation scaffolds.
  - `workbook` — structured handoff file generation.
  - `taxpack` — handoff pack packaging.
- `cmd/`, `internal/`, `data/`: shared runtime and source assets.
- `assets/`: icon and visual assets used by plugin install surface.
- optional:
  - `.app.json` (app connector definitions, when plugin includes app integrations)
  - `.mcp.json` (MCP integration wiring)
  - `agents/` (plugin surface metadata)
  - `commands/`, `hooks.json`, `scripts/`, `ui/`
  - `plugin.lock.json` (release/refresh guard)

## Installation

### A) Install path for official/plugin sources (recommended)

1. Open Codex plugin discovery and install **TaxMate Australia** from the plugin list.
2. If your workspace policy requires explicit installation controls, keep one marketplace entry with:

```json
{
  "name": "taxmate-local",
  "interface": { "displayName": "Local plugins" },
  "plugins": [
    {
      "name": "taxmate-australia",
      "source": {
        "source": "local",
        "path": "../.."
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

3. Make sure `path` is relative to the selected marketplace file:
- personal install: `~/.agents/plugins/marketplace.json`
- repo/team install: `<repo-root>/.agents/plugins/marketplace.json`

For both cases:
- if your marketplace points at a repo-root plugin, use `../..` from `.agents/plugins/marketplace.json`.
- if your marketplace points at `plugins/<plugin-name>`, use `./plugins/<plugin-name>`.

### B) Local install for this repo

1. Set plugin root:

```bash
export TAXMATE_AU_ROOT="/path/to/taxmate-au"
cd "$TAXMATE_AU_ROOT"
```

2. (Optional) Build once to warm the runtime:

```bash
go test ./...
go build -o bin/taxmate-au-validate ./cmd/taxmate-au-validate
go build -o bin/taxmate-au-finance ./cmd/taxmate-au-finance
```

3. Validate plugin manifest:

```bash
"$TAXMATE_AU_ROOT/bin/taxmate-au-validate"
```

4. Add a local marketplace entry (Codex reads JSON marketplaces from `~/.agents/plugins/marketplace.json`).

Use `source.path` relative to the marketplace file location:
- personal install: `../..` if you use a repo-root plugin entry file under `<repo-root>/.agents/plugins/marketplace.json`
- repo install: `./plugins/taxmate-australia` if your repo stores plugin folders under `<repo-root>/plugins/taxmate-australia`

```json
{
  "name": "taxmate-local",
  "interface": { "displayName": "Local plugins" },
  "plugins": [
    {
      "name": "taxmate-australia",
      "source": {
        "source": "local",
        "path": "../.."
      },
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

5. Run Codex, reload plugin list, and enable TaxMate Australia.

If your install lives as a repo plugin, place it under your repo marketplace root and keep `path` aligned to that root (`./plugins/<plugin-name>` for plugin folders).

If your plugin is installed as a standalone marketplace root (no `plugins/` wrapper), set `source.path` to your plugin path accordingly (for example `../..` when the marketplace file is inside `<plugin-root>/.agents/plugins/marketplace.json`).

## Validation and review

## Trust and citations

The bundled source pack is ATO-first. Stamp duty is source-routed to official state or territory revenue offices. Non-ATO commercial sources are out of scope unless a user explicitly asks for them.
ATO and Commonwealth material remains subject to the notices and terms published by the relevant official source. TaxMate Australia must not imply official endorsement.
No official tax filing is performed by this plugin.
- `go test ./...`
- build required binaries (`go build -o bin/taxmate-au-refresh ./cmd/taxmate-au-refresh`, etc.)
- `scripts/check-publication-ready.sh`
- run a local secret scan before publish
