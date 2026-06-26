---
name: finance-review
description: Review Australian tax records and transaction CSVs for accountant handoff using TaxMate Australia.
metadata:
  internal: true
  priority: 5
---

# TaxMate Australia Finance Review

Runtime requirements:

- Bash
- Python 3.9+
- Git

Use this full-runtime skill to review structured financial records before workbook or accountant output. It is a preparation aid, not professional advice or official lodgment support. It does not replace TaxMate Australia research; refresh ATO pages before final tax treatment.

Run:

```bash
export TAXMATE_AUSTRALIA_ROOT="${TAXMATE_AUSTRALIA_ROOT:-$(pwd)}"
"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" finance --input "<records.csv>" --format markdown --output "<review.md>"
```

For machine-readable output:

```bash
"$TAXMATE_AUSTRALIA_ROOT/scripts/taxmate" finance --input "<records.csv>" --format json --output "<review.json>"
```

Accepted headers include `date`, `description`, `amount`, `gst`, `owner`, `purpose`, `evidence`, `abn`, `category`, `account`, `asset`, `units`, and `type`.

## Rules

- Keep employee and ABN/business items separate.
- Keep spouse, joint, and entity ownership explicit.
- Do not mark BAS as nil if GST credits or GST collected are present.
- Treat private, mixed-use, pre-revenue, capital, home-business, FBT, CGT, PSI, business-vs-hobby, and non-commercial-loss cases as `Accountant review` unless the facts are clear.
- Refresh ATO pages listed in `ato_refresh_queries` before finalising treatment.
- Pass reviewed JSON/Markdown to output skills; do not let output skills make new tax calls.
