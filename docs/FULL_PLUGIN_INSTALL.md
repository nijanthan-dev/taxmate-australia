# Plugin Runtime Setup

Normal users should install TaxMate Australia as a Codex or Claude Code plugin.

Plugin prerequisites:

- Codex CLI or Claude Code CLI.
- Node.js 20+ for the MCP launcher.
- Bash.
- Python 3.9+.

Codex:

```bash
codex plugin marketplace add nijanthan-dev/taxmate-australia
codex plugin add taxmate-australia@taxmate-local-marketplace
```

Claude Code:

```bash
claude plugin marketplace add nijanthan-dev/taxmate-australia
claude plugin install taxmate-australia@taxmate-australia
```

The plugin install is the runtime install. It places TaxMate in the agent plugin cache with the Node.js MCP launcher, bash and Python runtime, `scripts/`, `runtime/`, `wrappers/`, skills, `.mcp.json`, and the MCP server.

Use [INSTALLATION.md](INSTALLATION.md) for the beginner install path.

## Plugin Tools

After plugin install, ask your agent to use TaxMate Australia. The plugin exposes tools for:

- `calc`
- `finance`
- `intake`
- `refresh`
- `review-guardrails`
- `skills`
- `taxpack`
- `validate`

Common prompts:

```text
Use TaxMate Australia to validate the runtime.
```

```text
Use TaxMate Australia to write sample individual answers and render the individual-return HTML guide.
```

The print-first HTML handoff is a custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable. Users manually copy reviewed values into myTax, a paper ATO form, or provide it to an accountant after resolving missing facts, evidence gaps, and `Accountant review` queues.

The individual-return handoff includes the prep-only boundary, manual-copy warning, intake summary, AI extraction confirmation table, individual return field guide, CGT schedule and item rows with loss/discount review facts, ABN prep section, BAS worksheet, missing facts queue, evidence queue, accountant-review queue, and source/provenance appendix.

## Developer Fallback

Use a cloned repository only for development, debugging, source refresh work, screenshot refresh, or direct launcher testing.

Prerequisites:

- Node.js 20+ for development checks.
- Bash.
- Python 3.9+.
- Git.
- curl.
- jq.

Clone and bootstrap:

```bash
git clone https://github.com/nijanthan-dev/taxmate-australia.git
cd taxmate-australia
bash scripts/bootstrap-dev-env.sh
```

Validate the developer checkout:

```bash
./scripts/taxmate validate
```

Run runtime commands through the bash launcher (python runtime under the hood):

```bash
./scripts/taxmate refresh --help
./scripts/taxmate intake individual --help
```

Render the same self-prepared guide HTML directly from the launcher:

```bash
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
```

Bash + python execution is the supported default path. Contributor validation, CI, release checks, screenshot maintenance, and local plugin testing live in [DEVELOPMENT.md](DEVELOPMENT.md).
