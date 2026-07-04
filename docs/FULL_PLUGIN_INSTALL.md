# Full Runtime Setup

Use this runtime path for the print-first HTML handoff, workbook/taxpack outputs, live ATO source refresh, calculator workflows, and finance review.

If you only need quick agent prompts without a checkout, use [INSTALLATION.md](INSTALLATION.md) instead.

Prerequisites:

- Node.js 20+ for full-runtime bootstrap.
- Bash.
- Python 3.9+.
- Git.
- curl.
- jq.

## Clean Runtime Setup

```bash
git clone https://github.com/nijanthan-dev/taxmate-australia.git
cd taxmate-australia
bash scripts/bootstrap-dev-env.sh
```

Validate the checkout:

```bash
./scripts/taxmate validate
```

Run runtime commands through the bash launcher (python runtime under the hood):

```bash
./scripts/taxmate refresh --help
```

Render the self-prepared guide HTML users can save as PDF:

```bash
./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json
./scripts/taxmate intake individual \
  --answers /tmp/taxmate-answers.json \
  --output /tmp/taxmate-guide.html
```

The guide is a custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable. Users manually copy reviewed values into myTax, a paper ATO form, or provide it to an accountant after resolving missing facts, evidence gaps, and `Accountant review` queues.

The individual-return handoff includes the prep-only boundary, manual-copy warning, intake summary, AI extraction confirmation table, individual return field guide, CGT schedule and item rows with loss/discount review facts, ABN prep section, BAS worksheet, missing facts queue, evidence queue, accountant-review queue, and source/provenance appendix.

If you need local-speed, keep Python runtime wrappers and dependencies local and use the launcher directly.
Bash + python execution is the supported default path.

Contributor validation, CI, release checks, screenshot maintenance, and local plugin testing live in [DEVELOPMENT.md](DEVELOPMENT.md).
