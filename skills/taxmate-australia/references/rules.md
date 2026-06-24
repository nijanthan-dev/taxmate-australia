# TaxMate Australia Routing Rules

## Official-source metadata

- ATO home: https://www.ato.gov.au/

## TaxMate conservative summary

- This entry-point skill routes to the most specific installed topic skill.
- It does not make tax-treatment decisions by itself.
- It preserves source URLs, effective periods, evidence status, and `Accountant review` flags.
- It requires current verification for volatile values when web access is available.
- If a needed topic skill or reliable source is unavailable, state the limitation and mark the item `Accountant review`.
- It must not use repository binaries, local repository data, plugin manifests, marketplace JSON, or environment variables.

## Accountant review required

- Any ambiguous, mixed-use, pre-revenue, home-business, FBT, CGT, GST/BAS, non-commercial-loss, business-versus-hobby, missing-source, conflicting-source, or incomplete-fact issue.
