#!/usr/bin/env python3
"""TaxMate Australia finance command implementation (Python replacement)."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional


ModeStrict = "strict"
ModeAssisted = "assisted"
ModeReview = "review"

normalise_re = re.compile(r"[^a-z0-9]+")
private_health_terms = [
    "private health",
    "health insurance",
    "medicare levy surcharge",
]
investment_terms = [
    "broker",
    "trading platform",
    "etf",
    "managed fund",
    "index fund",
    "shares",
    "dividend",
    "distribution",
    "amit",
    "drp",
    "cgt",
]
software_terms = [
    "developer program",
    "developer tools",
    "software",
    "hosting",
    "domain",
    "api",
    "subscription",
    "saas",
    "source control",
    "build tool",
]
employment_income_terms = [
    "salary",
    "wage",
    "payroll",
    "employer",
    "payg",
]
investment_income_terms = [
    "dividend",
    "distribution",
    "interest",
    "etf",
    "broker",
    "trading platform",
    "amit",
]


@dataclass
class Transaction:
    row: int
    date: str = ""
    description: str = ""
    amount: float = 0.0
    gst: float = 0.0
    direction: str = ""
    owner: str = ""
    account: str = ""
    category: str = ""
    purpose: str = ""
    evidence: str = ""
    abn: str = ""
    source: str = ""
    asset: str = ""
    units: float = 0.0
    raw: Dict[str, str] = field(default_factory=dict)


@dataclass
class Finding:
    row: int
    owner: str = ""
    description: str = ""
    amount: float = 0.0
    direction: str = ""
    bucket: str = "uncategorised"
    tax_treatment: str = "accountant_review"
    claim_percent: float = 0.0
    claim_amount: float = 0.0
    gst_credit_candidate: bool = False
    gst_credit_amount: float = 0.0
    confidence: str = "low"
    reasons: List[str] = field(default_factory=lambda: ["insufficient facts for automatic tax treatment"])
    records_needed: List[str] = field(default_factory=lambda: ["receipt or invoice", "business or work purpose note", "owner"])
    accountant_review: bool = True


@dataclass
class HealthCheck:
    name: str
    passed: bool
    severity: str
    detail: str
    rows: List[int] = field(default_factory=list)
    advice: List[str] = field(default_factory=list)


@dataclass
class SummaryLine:
    owner: str
    bucket: str
    treatment: str
    gross_amount: float = 0.0
    claim_amount: float = 0.0
    gst_candidate: float = 0.0
    rows: int = 0


@dataclass
class BASSummary:
    business_expense_gross: float = 0.0
    gst_credit_candidate: float = 0.0
    business_income_gross: float = 0.0
    gst_collected_candidate: float = 0.0
    nil_bas_likely: bool = False
    review_note: str = ""


@dataclass
class Scenario:
    name: str
    base_amount: float = 0.0
    what_if: str = ""
    result: float = 0.0
    review_note: str = ""


@dataclass
class Report:
    generated_at: str
    mode: str
    source: str
    transactions: List[Transaction] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    summary: List[SummaryLine] = field(default_factory=list)
    bas_summary: BASSummary = field(default_factory=BASSummary)
    scenario_checks: List[Scenario] = field(default_factory=list)
    health_checks: List[HealthCheck] = field(default_factory=list)
    caveats: List[str] = field(default_factory=list)
    ato_refresh_queries: List[str] = field(default_factory=list)


def analyze_csv(path: str, mode: str) -> Report:
    mode = mode or ModeStrict
    if mode not in (ModeStrict, ModeAssisted, ModeReview):
        raise ValueError(f'invalid mode "{mode}"')

    with open(path, "r", encoding="utf-8", newline="") as f:
        transactions = read_csv(f)

    report = Report(
        generated_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        mode=mode,
        source=path,
        caveats=[
            "This is a preparation aid, not tax advice.",
            "Use official ATO refresh before answering final tax questions.",
            "Ambiguous, mixed-use, pre-revenue, private, capital, and GST items stay flagged for accountant review.",
        ],
        ato_refresh_queries=[
            "working from home fixed rate method 2025-26",
            "claiming GST credits tax invoices",
            "effect of GST credits on income tax deductions",
            "deductions for digital product expenses",
            "business losses pre revenue expenses",
            "shares funds trusts ETF annual tax statement AMIT CGT",
            "private health insurance rebate Medicare levy surcharge",
            "personal super contributions notice of intent",
        ],
    )
    report.transactions = transactions
    for tx in transactions:
        report.findings.append(classify(tx, mode))
    report.summary = summarise(report.findings)
    report.bas_summary = bas_summary(report.findings)
    report.scenario_checks = scenarios(report.findings)
    report.health_checks = health(transactions, report.findings)
    return report


def write_json(report: Report, out) -> None:
    payload = {
        "generated_at": report.generated_at,
        "mode": report.mode,
        "source": report.source,
        "transactions": [asdict(tx) for tx in report.transactions],
        "findings": [asdict(f) for f in report.findings],
        "summary": [asdict(s) for s in report.summary],
        "bas_summary": asdict(report.bas_summary),
        "scenario_checks": [asdict(s) for s in report.scenario_checks],
        "health_checks": [asdict(h) for h in report.health_checks],
        "caveats": report.caveats,
        "ato_refresh_queries": report.ato_refresh_queries,
    }
    json.dump(payload, out, indent=2, allow_nan=False)
    out.write("\n")


def write_markdown(report: Report, out) -> None:
    lines: List[str] = []
    lines.append("# TaxMate Australia Finance Review")
    lines.append("")
    lines.append(f"- Mode: `{report.mode}`")
    lines.append(f"- Source: `{report.source}`")
    lines.append(f"- Generated UTC: `{report.generated_at}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Owner | Bucket | Treatment | Rows | Gross | Claim | GST candidate |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for line in report.summary:
        lines.append(
            "| "
            + " | ".join(
                [
                    escape_md(line.owner),
                    escape_md(line.bucket),
                    escape_md(line.treatment),
                    str(line.rows),
                    f"{line.gross_amount:.2f}",
                    f"{line.claim_amount:.2f}",
                    f"{line.gst_candidate:.2f}",
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## BAS/GST")
    lines.append("")
    lines.append(f"- Business expense gross: {report.bas_summary.business_expense_gross:.2f}")
    lines.append(f"- GST credit candidate: {report.bas_summary.gst_credit_candidate:.2f}")
    lines.append(f"- Business income gross: {report.bas_summary.business_income_gross:.2f}")
    lines.append(f"- GST collected candidate: {report.bas_summary.gst_collected_candidate:.2f}")
    lines.append(f"- Nil BAS likely: `{str(report.bas_summary.nil_bas_likely).lower()}`")
    lines.append(f"- Review: {report.bas_summary.review_note}")
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    lines.append("| Row | Owner | Description | Bucket | Treatment | Claim % | Claim | GST | Review | Reasons |")
    lines.append("|---:|---|---|---|---|---:|---:|---:|---|---|")
    for item in report.findings:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.row),
                    escape_md(item.owner),
                    escape_md(item.description),
                    escape_md(item.bucket),
                    escape_md(item.tax_treatment),
                    f"{item.claim_percent:.0f}",
                    f"{item.claim_amount:.2f}",
                    f"{item.gst_credit_amount:.2f}",
                    str(item.accountant_review).lower(),
                    escape_md("; ".join(item.reasons)),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Health Checks")
    lines.append("")
    for check in report.health_checks:
        state = "pass" if check.passed else "fail"
        lines.append(f"- `{check.name}` [{state}/{check.severity}]: {check.detail}")
    lines.append("")
    lines.append("## ATO Refresh Queries")
    lines.append("")
    for query in report.ato_refresh_queries:
        lines.append(f"- `{query}`")
    out.write("\n".join(lines))


def read_csv(handle) -> List[Transaction]:
    reader = csv.reader(handle, skipinitialspace=True)
    rows = list(reader)
    if not rows:
        raise ValueError("empty csv")

    header = {norm(name): idx for idx, name in enumerate(rows[0])}
    if not header:
        raise ValueError("empty csv")

    transactions: List[Transaction] = []
    for idx, row in enumerate(rows[1:], start=2):
        if all_blank(row):
            continue
        tx = Transaction(
            row=idx,
            date=get(row, header, "date", "transactiondate", "posteddate"),
            description=get(row, header, "description", "merchant", "payee", "memo", "details"),
            owner=get(row, header, "owner", "person", "taxpayer"),
            account=get(row, header, "account", "accountname"),
            category=get(row, header, "category", "class"),
            purpose=get(row, header, "purpose", "businesspurpose", "notes", "note"),
            evidence=get(row, header, "evidence", "receipt", "invoice", "document"),
            abn=get(row, header, "abn", "business", "entity"),
            source=get(row, header, "source", "statement"),
            asset=get(row, header, "asset", "symbol", "ticker", "security"),
            raw={},
        )
        for name, header_idx in header.items():
            if header_idx < len(row):
                tx.raw[name] = row[header_idx].strip()
        amount = get(row, header, "amount", "value", "netamount")
        tx.amount = parse_money(amount) if amount else parse_money(signed_amount(row, header))
        tx.gst = parse_optional_money(get(row, header, "gst", "gstamount", "tax", "taxamount"))
        tx.units = parse_optional_money(get(row, header, "units", "quantity"))
        tx.direction = direction(row, header, tx.amount)
        transactions.append(tx)
    if not transactions:
        raise ValueError("empty csv")
    return transactions


def classify(tx: Transaction, mode: str) -> Finding:
    text = " ".join(
        [
            tx.description,
            tx.category,
            tx.purpose,
            tx.account,
            tx.abn,
            tx.source,
            tx.asset,
        ]
    ).lower()
    finding = Finding(
        row=tx.row,
        owner=first_non_empty(tx.owner, "unassigned"),
        description=tx.description,
        amount=tx.amount,
        direction=tx.direction,
    )

    if contains_any(text, *private_health_terms):
        set_finding(
            finding,
            "private_health",
            "tax_return_info_only",
            0,
            "medium",
            True,
            "private health insurance is usually tax-statement information, not a deduction",
        )
        finding.records_needed = ["private health insurance tax statement"]
        return finding
    if contains_any(text, "super", "superannuation", "personal contribution", "notice of intent"):
        set_finding(
            finding,
            "super",
            "accountant_review",
            0,
            "medium",
            True,
            "personal super deduction needs eligibility and notice-of-intent evidence",
        )
        finding.records_needed = ["fund acknowledgement", "notice of intent", "contribution statement"]
        return finding
    if tx.direction == "income":
        classify_income(finding, tx, text)
        return finding
    if contains_any(text, *investment_terms) or tx.asset != "" or tx.units != 0:
        set_finding(
            finding,
            "investment",
            "record_for_income_cgt",
            0,
            "medium",
            True,
            "investment records affect distributions, AMIT cost base, DRP, disposals, and CGT",
        )
        finding.records_needed = [
            "annual tax statement",
            "buy/sell contract notes",
            "DRP statement",
            "AMIT cost-base adjustments",
        ]
        return finding
    if contains_any(text, *software_terms):
        if is_business(tx, text):
            set_finding(
                finding,
                "abn_business_software",
                "deduction_candidate",
                100,
                "medium",
                mode == ModeStrict,
                "software or developer cost appears connected to ABN activity",
            )
            finding.records_needed = [
                "tax invoice",
                "business purpose",
                "GST status",
                "private-use apportionment note",
            ]
            apply_gst(finding, tx, True)
            return finding
        set_finding(
            finding,
            "software_or_subscription",
            "accountant_review",
            0,
            "low",
            True,
            "could be employee, ABN, private, or mixed-use; entity and purpose required",
        )
        return finding
    if contains_any(text, "work from home", "wfh", "internet", "phone", "electricity", "stationery", "computer consumables"):
        if is_business(tx, text):
            set_finding(
                finding,
                "abn_business_home_office",
                "accountant_review",
                0,
                "medium",
                True,
                "ABN home-office running costs need business-use apportionment and home-business review",
            )
            finding.records_needed = ["tax invoice", "business-use apportionment", "home-business facts", "GST status"]
            apply_gst(finding, tx, True)
            return finding
        set_finding(
            finding,
            "employee_wfh",
            "fixed_rate_or_actual_method_review",
            0,
            "medium",
            True,
            "WFH claim needs method choice and work-hour records; fixed rate may already cover this cost",
        )
        finding.records_needed = ["WFH hours", "method choice", "invoice", "private-use apportionment"]
        return finding
    if contains_any(text, "laptop", "monitor", "keyboard", "mouse", "desk", "chair", "equipment", "tool"):
        set_finding(
            finding,
            "work_or_business_asset",
            "depreciation_or_immediate_deduction_review",
            0,
            "medium",
            True,
            "asset treatment depends on cost, date, effective life, entity, and private use",
        )
        finding.records_needed = ["tax invoice", "purchase date", "private-use percentage", "employee or ABN use"]
        apply_gst(finding, tx, is_business(tx, text))
        return finding
    if contains_any(text, "meal", "coffee", "restaurant", "entertainment", "grocery", "clothes", "fitness", "gym", "medical", "commute", "parking fine"):
        if is_business(tx, text) and contains_any(text, "meal", "coffee", "restaurant", "entertainment"):
            set_finding(
                finding,
                "business_entertainment_fbt",
                "accountant_review",
                0,
                "medium",
                True,
                "business meals or entertainment may be private, non-deductible, or FBT-sensitive",
            )
            finding.records_needed = ["tax invoice", "attendees", "business purpose", "FBT/accountant review"]
            return finding
        set_finding(
            finding,
            "private_or_excluded",
            "not_claimable",
            0,
            "medium",
            False,
            "private or commonly excluded category",
        )
        finding.records_needed = ["only keep if accountant asks"]
        return finding
    if is_business(tx, text):
        set_finding(
            finding,
            "abn_business_expense",
            "accountant_review",
            0,
            "low",
            True,
            "business tag present but expense type is not specific enough",
        )
        finding.records_needed = ["tax invoice", "business purpose", "GST status", "private-use apportionment"]
        apply_gst(finding, tx, True)
    return finding


def classify_income(finding: Finding, tx: Transaction, text: str) -> None:
    if contains_any(text, *investment_income_terms) or tx.asset != "" or tx.units != 0:
        set_finding(
            finding,
            "investment_income",
            "tax_statement_record",
            0,
            "medium",
            True,
            "investment income needs annual tax statement and franking/AMIT details",
        )
        return
    if is_business(tx, text):
        set_finding(
            finding,
            "abn_business_income",
            "assessable_income_review",
            0,
            "medium",
            True,
            "income appears connected to ABN or side activity",
        )
        if tx.gst > 0:
            finding.gst_credit_amount = round2(abs_float(tx.gst))
            finding.reasons.append("GST collected candidate present")
        return
    if contains_any(text, *employment_income_terms):
        set_finding(
            finding,
            "employment_income",
            "income_statement_record",
            0,
            "medium",
            False,
            "employment income belongs outside ABN expense tracking",
        )
        return
    set_finding(finding, "income", "accountant_review", 0, "low", True, "income source needs classification")


def set_finding(
    finding: Finding,
    bucket: str,
    treatment: str,
    percent: float,
    confidence: str,
    review: bool,
    reason: str,
) -> None:
    finding.bucket = bucket
    finding.tax_treatment = treatment
    finding.claim_percent = percent
    finding.claim_amount = round2(abs_float(finding.amount) * percent / 100)
    finding.confidence = confidence
    finding.accountant_review = review
    finding.reasons = [reason]


def apply_gst(finding: Finding, tx: Transaction, business: bool) -> None:
    if business and tx.gst != 0:
        finding.gst_credit_candidate = True
        finding.gst_credit_amount = round2(abs_float(tx.gst))
        finding.reasons.append("GST credit candidate only if valid tax invoice and creditable purpose")
        if not contains_any(tx.evidence.lower(), "tax invoice", "invoice", "receipt"):
            finding.records_needed = append_missing(finding.records_needed, "valid tax invoice")

def summarise(findings: List[Finding]) -> List[SummaryLine]:
    grouped: Dict[tuple, SummaryLine] = {}
    for f in findings:
        key = (f.owner, f.bucket, f.tax_treatment)
        if key not in grouped:
            grouped[key] = SummaryLine(owner=f.owner, bucket=f.bucket, treatment=f.tax_treatment)
        line = grouped[key]
        line.rows += 1
        line.gross_amount = round2(line.gross_amount + abs_float(f.amount))
        line.claim_amount = round2(line.claim_amount + f.claim_amount)
        line.gst_candidate = round2(line.gst_candidate + f.gst_credit_amount)
    output = list(grouped.values())
    output.sort(key=lambda item: (item.owner, item.bucket, item.treatment))
    return output


def bas_summary(findings: List[Finding]) -> BASSummary:
    summary = BASSummary()
    for finding in findings:
        if finding.bucket.startswith("abn_business") and finding.direction == "expense":
            summary.business_expense_gross = round2(
                summary.business_expense_gross + abs_float(finding.amount)
            )
            summary.gst_credit_candidate = round2(summary.gst_credit_candidate + finding.gst_credit_amount)
        if finding.bucket == "abn_business_income":
            summary.business_income_gross = round2(summary.business_income_gross + abs_float(finding.amount))
            summary.gst_collected_candidate = round2(summary.gst_collected_candidate + finding.gst_credit_amount)
    summary.nil_bas_likely = (
        summary.business_income_gross == 0
        and summary.gst_credit_candidate == 0
        and summary.gst_collected_candidate == 0
    )
    if summary.nil_bas_likely:
        summary.review_note = (
            "No business income or GST-credit candidates detected in supplied rows; "
            "confirm complete records before nil BAS."
        )
    else:
        summary.review_note = (
            "Not nil if GST collected or GST credits are being claimed; accountant should review GST labels."
        )
    return summary


def scenarios(findings: List[Finding]) -> List[Scenario]:
    review_total = 0.0
    claim_total = 0.0
    for finding in findings:
        if finding.accountant_review:
            review_total += abs_float(finding.amount)
        claim_total += finding.claim_amount
    return [
        Scenario(
            name="strict_claims_only",
            base_amount=round2(claim_total),
            what_if="Only rows with explicit claim percentage are counted.",
            result=round2(claim_total),
            review_note="Use this for conservative accountant handoff totals.",
        ),
        Scenario(
            name="review_queue_value",
            base_amount=round2(review_total),
            what_if="Total value still needing accountant judgement.",
            result=round2(review_total),
            review_note="Large review value means evidence or entity labels are missing.",
        ),
    ]


def health(transactions: List[Transaction], findings: List[Finding]) -> List[HealthCheck]:
    missing_owner: List[int] = []
    missing_evidence: List[int] = []
    review_rows: List[int] = []
    gst_invoice_rows: List[int] = []
    seen: Dict[str, int] = {}
    duplicate_rows: List[int] = []

    for tx in transactions:
        if not tx.owner.strip():
            missing_owner.append(tx.row)
        if not tx.evidence.strip():
            missing_evidence.append(tx.row)
        key = f"{tx.date}|{norm(tx.description)}|{tx.amount:.2f}"
        first = seen.get(key)
        if first is None:
            seen[key] = tx.row
        else:
            duplicate_rows.extend([first, tx.row])

    transactions_by_row = {tx.row: tx for tx in transactions}
    for finding in findings:
        if finding.accountant_review:
            review_rows.append(finding.row)
        tx = transactions_by_row.get(finding.row)
        evidence = tx.evidence.lower() if tx is not None else ""
        if finding.gst_credit_candidate and not contains_any(evidence, "tax invoice", "invoice", "receipt"):
            gst_invoice_rows.append(finding.row)

    return [
        check(
            "owner_present",
            len(missing_owner) == 0,
            "medium",
            "every row should identify taxpayer/spouse/joint/entity",
            missing_owner,
        ),
        check(
            "evidence_present",
            len(missing_evidence) == 0,
            "high",
            "receipt/invoice evidence should be linked before claiming",
            missing_evidence,
        ),
        check(
            "gst_tax_invoice_support",
            len(gst_invoice_rows) == 0,
            "high",
            "GST credit candidates need valid tax invoices",
            unique(gst_invoice_rows),
        ),
        check(
            "duplicate_scan",
            len(duplicate_rows) == 0,
            "medium",
            "same date/description/amount appears more than once",
            unique(duplicate_rows),
        ),
        check("accountant_review_queue", len(review_rows) == 0, "info", "rows flagged for accountant judgement", review_rows),
    ]


def check(name: str, passed: bool, severity: str, detail: str, rows: List[int]) -> HealthCheck:
    return HealthCheck(name=name, passed=passed, severity=severity, detail=detail, rows=first_rows(unique(rows), 25))


def direction(row: List[str], header: Dict[str, int], amount: float) -> str:
    raw = first_non_empty(get(row, header, "direction", "type", "transactiontype"), get(row, header, "debitcredit")).lower()
    if any(token in raw for token in ("debit", "expense", "withdrawal", "purchase")):
        return "expense"
    if any(token in raw for token in ("credit", "income", "deposit")):
        return "income"
    return "expense" if amount < 0 else "income"


def signed_amount(row: List[str], header: Dict[str, int]) -> str:
    errors: List[ValueError] = []
    debit_value = get(row, header, "debit", "withdrawal", "spent")
    if debit_value and not money_placeholder(debit_value):
        try:
            debit = parse_money(debit_value)
        except ValueError as exc:
            errors.append(exc)
        else:
            if debit != 0:
                return f"{-abs(debit):.2f}"
    credit_value = get(row, header, "credit", "deposit", "received")
    if credit_value and not money_placeholder(credit_value):
        try:
            credit = parse_money(credit_value)
        except ValueError as exc:
            errors.append(exc)
        else:
            if credit != 0:
                return f"{abs(credit):.2f}"
    if errors:
        raise errors[0]
    return ""


def money_placeholder(raw_value: str) -> bool:
    return raw_value.strip().lower() in {"-", "--", "n/a", "na", "nil", "none", "null"}

def get(row: List[str], header: Dict[str, int], *names: str) -> str:
    for name in names:
        idx = header.get(norm(name))
        if idx is not None and idx < len(row):
            return row[idx].strip()
    return ""


def get_raw(row: List[str], header: Dict[str, int], name: str) -> str:
    return get(row, header, name)


def norm(value: str) -> str:
    return normalise_re.sub("", value.strip().lower())


def parse_money(raw_value: str) -> float:
    value = raw_value.strip()
    if not value:
        return 0.0
    neg = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    value = value.replace("$", "").replace(",", "").replace("AUD", "").strip()
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"invalid money value: {raw_value!r}")
    if not math.isfinite(number):
        raise ValueError(f"invalid finite money value: {raw_value!r}")
    if neg:
        number = -number
    return round2(number)


def parse_optional_money(raw_value: str) -> float:
    if money_placeholder(raw_value):
        return 0.0
    return parse_money(raw_value)


def is_business(tx: Transaction, text: str) -> bool:
    return bool(tx.abn.strip()) or contains_any(text, "abn", "sole trader", "business", "side hustle", "app business")


def contains_any(value: str, *needles: str) -> bool:
    for needle in needles:
        if needle in value:
            return True
    return False


def all_blank(row: List[str]) -> bool:
    return all(not v.strip() for v in row)


def first_non_empty(*values: str) -> str:
    for value in values:
        if value.strip():
            return value.strip()
    return ""


def append_missing(values: List[str], value: str) -> List[str]:
    if value in values:
        return values
    values.append(value)
    return values


def unique(values: List[int]) -> List[int]:
    seen = set()
    output: List[int] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    output.sort()
    return output


def first_rows(values: List[int], n: int) -> List[int]:
    return values if len(values) <= n else values[:n]


def round2(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def abs_float(value: float) -> float:
    return abs(value)


def escape_md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="./scripts/taxmate finance", description="TaxMate Australia finance review.")
    parser.add_argument("--input", required=False, help="CSV file of expenses, income, investments, GST, super, or private-health records.")
    parser.add_argument("--format", default="json", help="Output format: json or markdown.")
    parser.add_argument("--mode", default=ModeStrict, help="Analysis mode: strict, assisted, or review.")
    parser.add_argument("--output", default="", help="Optional output file.")
    return parser


def main(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.input:
        print("use --input file.csv", file=sys.stderr)
        return 2

    if args.format not in {"json", "markdown", "md"}:
        print(f"invalid format {args.format!r}", file=sys.stderr)
        return 2

    try:
        report = analyze_csv(args.input, args.mode)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1

    out = sys.stdout
    close_out = False
    if args.output:
        try:
            out = open(args.output, "w", encoding="utf-8")
            close_out = True
        except OSError as exc:
            print(exc, file=sys.stderr)
            return 1

    try:
        if args.format == "json":
            write_json(report, out)
        else:
            write_markdown(report, out)
    except Exception as exc:
        if close_out:
            out.close()
        print(exc, file=sys.stderr)
        return 1

    if close_out:
        out.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
