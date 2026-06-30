#!/usr/bin/env python3
"""TaxMate Australia individual intake command."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import taxmate_taxpack


DEFAULT_INCOME_YEAR = "2025-26"
SUPPORTED_WFH_START = date(2025, 7, 1)
SUPPORTED_WFH_END = date(2026, 6, 30)
WFH_FIXED_RATE_2025_26 = 0.70
REVIEWABLE_ABN_FIELDS = ("abn_income", "abn_expenses")
REVIEWABLE_BAS_FIELDS = ("bas_period", "gst_collected", "gst_credits")
REVIEWABLE_ESS_FIELDS = (
    "ess_statement",
    "ess_taxed_upfront_discount",
    "ess_deferred_discount",
    "ess_foreign_source_discount",
    "ess_tfn_amount_withheld",
)
REVIEWABLE_COMPLEX_PAYMENT_FIELDS = (
    "etp_statement",
    "etp_taxable_component",
    "etp_tax_free_component",
    "etp_tax_withheld",
    "lump_sum_arrears_statement",
    "lump_sum_arrears_amount",
    "lump_sum_arrears_years",
    "lump_sum_arrears_tax_withheld",
    "super_income_statement",
    "super_income_payment_kind",
    "super_lump_sum_taxable_component",
    "super_lump_sum_tax_free_component",
    "super_income_stream_taxable_amount",
    "super_income_tax_withheld",
)
REVIEWABLE_FOREIGN_INCOME_FIELDS = (
    "foreign_income_statement",
    "foreign_income_country",
    "foreign_income_type",
    "foreign_income_amount",
    "foreign_tax_paid",
    "foreign_income_exchange_rate",
    "foreign_income_residency_status",
    "foreign_income_tax_offset_claim",
    "foreign_employment_exempt_claim",
)
COMPLEX_PAYMENT_STATEMENT_FLAT_FIELDS = (
    "etp_statement",
    "lump_sum_arrears_statement",
    "super_income_statement",
)
COMPLEX_PAYMENT_FLAT_FIELD_GROUPS = {
    "etp_statement": "etp",
    "etp_taxable_component": "etp",
    "etp_tax_free_component": "etp",
    "etp_tax_withheld": "etp",
    "lump_sum_arrears_statement": "lump_sum_arrears",
    "lump_sum_arrears_amount": "lump_sum_arrears",
    "lump_sum_arrears_years": "lump_sum_arrears",
    "lump_sum_arrears_tax_withheld": "lump_sum_arrears",
    "super_income_statement": "super_income",
    "super_income_payment_kind": "super_income",
    "super_lump_sum_taxable_component": "super_income",
    "super_lump_sum_tax_free_component": "super_income",
    "super_income_stream_taxable_amount": "super_income",
    "super_income_tax_withheld": "super_income",
}
COMPLEX_PAYMENT_AMOUNT_FIELDS = (
    "taxable_component",
    "tax_free_component",
    "tax_withheld",
    "amount",
    "taxable_amount",
)
COMPLEX_PAYMENT_FLAT_AMOUNT_FIELDS = (
    "etp_taxable_component",
    "etp_tax_free_component",
    "etp_tax_withheld",
    "lump_sum_arrears_amount",
    "lump_sum_arrears_tax_withheld",
    "super_lump_sum_taxable_component",
    "super_lump_sum_tax_free_component",
    "super_income_stream_taxable_amount",
    "super_income_tax_withheld",
)
COMPLEX_PAYMENT_STATEMENT_MISSING_PHRASES = (
    "do not have",
    "don't have",
    "no statement",
    "no payment summary",
    "statement not held",
    "statement not available",
    "statement not provided",
    "statement not received",
    "not held",
    "not available",
    "not provided",
    "not received",
    "not supplied",
    "payment summary not held",
    "payment summary not available",
    "payment summary not provided",
    "payment summary not received",
    "income statement not held",
    "income statement not available",
    "income statement not provided",
    "income statement not received",
    "fund statement not held",
    "fund statement not available",
    "fund statement not provided",
    "fund statement not received",
)
ESS_AMOUNT_FIELDS = (
    "taxed_upfront_discount",
    "deferred_discount",
    "foreign_source_discount",
    "tfn_amount_withheld",
)
ESS_FLAT_AMOUNT_FIELDS = tuple(f"ess_{field}" for field in ESS_AMOUNT_FIELDS)
ESS_ITEM_SIGNAL_FIELDS = ("employer", "scheme", "provider", *ESS_AMOUNT_FIELDS)
ESS_STATEMENT_MISSING_PHRASES = (
    "do not have",
    "don't have",
    "no ess statement",
    "no employee share scheme statement",
    "statement not held",
    "statement not available",
    "statement not provided",
    "statement not received",
    "not provided",
    "not received",
    "not supplied",
    "ess statement not held",
    "ess statement not available",
    "ess statement not provided",
    "ess statement not received",
)
ESS_DECLINE_PHRASES = (
    "no ess",
    "no employee share scheme",
    "no employee share schemes",
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
COMPLEX_PAYMENT_DECLINE_PHRASES = (
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
COMPLEX_PAYMENT_DECLINE_PHRASES_BY_GROUP = {
    "etp": (
        "no etp",
        "no employment termination payment",
        "no employment termination payments",
    ),
    "lump_sum_arrears": (
        "no lump sum",
        "no lump sums",
        "no lump sum in arrears",
        "no lump sums in arrears",
    ),
    "super_income": (
        "no super lump sum",
        "no super lump sums",
        "no super income stream",
        "no super income streams",
        "no super pension",
        "no super pensions",
        "no super annuity",
        "no super annuities",
    ),
}
FOREIGN_INCOME_AMOUNT_FIELDS = ("amount", "foreign_tax_paid", "tax_paid", "exchange_rate")
FOREIGN_INCOME_FLAT_AMOUNT_FIELDS = (
    "foreign_income_amount",
    "foreign_tax_paid",
    "foreign_income_exchange_rate",
)
FOREIGN_INCOME_SIGNAL_FIELDS = (
    "statement",
    "country",
    "income_type",
    "payer",
    "amount",
    "foreign_tax_paid",
    "tax_paid",
    "exchange_rate",
    "residency_status",
    "foreign_tax_offset_claim",
    "foreign_employment_exempt_claim",
)
FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS = ("foreign_tax_offset_claim", "foreign_employment_exempt_claim")
FOREIGN_INCOME_FLAT_BOOLEAN_FIELDS = ("foreign_income_tax_offset_claim", "foreign_employment_exempt_claim")
FOREIGN_INCOME_STATEMENT_MISSING_PHRASES = (
    "do not have",
    "don't have",
    "no statement",
    "no foreign income statement",
    "no foreign pension statement",
    "statement not held",
    "statement not available",
    "statement not provided",
    "statement not received",
    "statement not supplied",
    "not held",
    "not available",
    "not provided",
    "not received",
    "not supplied",
    "payment summary not held",
    "payment summary not available",
    "payment summary not provided",
    "payment summary not received",
    "pension statement not held",
    "pension statement not available",
    "pension statement not provided",
    "pension statement not received",
)
FOREIGN_INCOME_DECLINE_PHRASES = (
    "no foreign income",
    "no foreign employment",
    "no foreign pension",
    "no foreign pensions",
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
REVIEWABLE_COMPLEX_FIELDS = (
    "employee_deductions",
    "wfh_work_pattern",
    "wfh_records",
    "asset_items",
    "ess_items",
    "foreign_income_items",
)
EXACT_UNKNOWN_PHRASES = frozenset({"unknown", "missing", "not sure", "unsure", "uncertain"})
EMBEDDED_UNKNOWN_PHRASES = (
    "not confirmed",
    "unconfirmed",
    "unknown",
    "missing",
    "not sure",
    "unsure",
    "uncertain",
    "no receipt",
)
STATE_ALIASES = {
    "VIC": "VIC",
    "VICTORIA": "VIC",
    "NSW": "NSW",
    "NEW SOUTH WALES": "NSW",
    "QLD": "QLD",
    "QUEENSLAND": "QLD",
    "SA": "SA",
    "SOUTH AUSTRALIA": "SA",
    "WA": "WA",
    "WESTERN AUSTRALIA": "WA",
    "TAS": "TAS",
    "TASMANIA": "TAS",
    "ACT": "ACT",
    "AUSTRALIAN CAPITAL TERRITORY": "ACT",
    "NT": "NT",
    "NORTHERN TERRITORY": "NT",
}
WEEKDAY_ALIASES = {
    "MON": 0,
    "MONDAY": 0,
    "TUE": 1,
    "TUES": 1,
    "TUESDAY": 1,
    "WED": 2,
    "WEDNESDAY": 2,
    "THU": 3,
    "THUR": 3,
    "THURS": 3,
    "THURSDAY": 3,
    "FRI": 4,
    "FRIDAY": 4,
    "SAT": 5,
    "SATURDAY": 5,
    "SUN": 6,
    "SUNDAY": 6,
}

PUBLIC_HOLIDAY_SOURCE = "https://www.fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays"
PUBLIC_HOLIDAY_SOURCES = [
    "https://www.fairwork.gov.au/employment-conditions/public-holidays/2025-public-holidays",
    PUBLIC_HOLIDAY_SOURCE,
]
LIMITED_PUBLIC_HOLIDAYS_BY_STATE = {
    "NSW": {"2025-08-04"},
    "QLD": {"2025-08-13", "2025-12-24"},
    "SA": {"2025-12-24", "2025-12-31"},
    "NT": {"2025-12-24", "2025-12-31"},
    "TAS": {"2025-10-23", "2025-11-03", "2026-02-09", "2026-04-07"},
    "VIC": {"2025-11-04"},
    "WA": {"2025-09-29"},
}
ATO_INDIVIDUAL_SOURCE = "https://www.ato.gov.au/forms-and-instructions/individual-tax-return-instructions-2026"
ATO_WFH_FIXED_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method"
ATO_WFH_ACTUAL_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/actual-cost-method"
ATO_ASSET_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work/depreciating-assets-you-use-for-work"
ATO_BAS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas"
ATO_GST_CREDITS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/claiming-gst-credits"
ATO_ESS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/employee-share-schemes"
ATO_ESS_STATEMENT_SOURCE = "https://www.ato.gov.au/forms-and-instructions/employee-share-scheme-statement"
ATO_ETP_SOURCE = "https://www.ato.gov.au/tax-rates-and-codes/payg-withholding-schedule-11-tax-table-for-employment-termination-payments"
ATO_LUMP_SUM_ARREARS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/lump-sum-payment-in-arrears"
ATO_SUPER_PENSIONS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/superannuation-pensions-and-annuities"
ATO_SUPER_LUMP_SUM_SOURCE = "https://www.ato.gov.au/tax-rates-and-codes/schedule-12-tax-table-for-superannuation-lump-sums"
ATO_SUPER_STREAM_SOURCE = "https://www.ato.gov.au/tax-rates-and-codes/schedule-13-tax-table-for-superannuation-income-streams"
ATO_FOREIGN_WORLDWIDE_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income"
ATO_FOREIGN_RESIDENT_INCOME_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/australian-resident-for-tax-purposes-foreign-and-worldwide-income"
ATO_FOREIGN_TEMP_RESIDENT_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/foreign-and-temporary-resident-income"
ATO_FOREIGN_EMPLOYMENT_EXEMPT_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/tax-exempt-income-from-foreign-employment"
ATO_FOREIGN_INCOME_TAX_OFFSET_SOURCE = "https://www.ato.gov.au/forms-and-instructions/foreign-income-tax-offset-rules-guide-2026"
ATO_FOREIGN_INCOME_SOURCES = [
    ATO_FOREIGN_WORLDWIDE_SOURCE,
    ATO_FOREIGN_RESIDENT_INCOME_SOURCE,
    ATO_FOREIGN_TEMP_RESIDENT_SOURCE,
    ATO_FOREIGN_EMPLOYMENT_EXEMPT_SOURCE,
    ATO_FOREIGN_INCOME_TAX_OFFSET_SOURCE,
]
OMITTED_SCOPE_ITEMS = [
    ("feat: add company return intake", "Company/entity return prep, company tax labels, directors, dividends, franking, retained earnings."),
    ("feat: add trust return intake", "Trust return prep, beneficiary distributions, trustee-assessed income, family trust items."),
    ("feat: add partnership return intake", "Partnership return prep, partner shares, partnership income/loss allocations."),
    ("feat: add full supplementary return coverage", "Full supplementary labels beyond common V1 gates."),
    ("feat: add rental property worksheet", "Rental income, interest, repairs versus capital, private use, depreciation, net rental loss."),
    ("feat: add full CGT schedule workflow", "CGT events, cost base, discounts, carried losses, main residence, small business concessions."),
    ("feat: add crypto CGT workflow", "Buys, sells, swaps, staking, rewards, transfers, wallet records, and cost-base tracking."),
    ("feat: add PSI deep workflow", "PSI tests, attribution, deductions, and business structure impacts."),
    ("feat: add advanced document extraction", "Robust OCR and templates for arbitrary PDFs/images beyond AI-assisted candidate extraction."),
]


@dataclass(frozen=True)
class QuestionSpec:
    key: str
    section: str
    prompt: str
    ato_area: str
    required: bool = True


def omitted_scope_issues() -> List[Dict[str, str]]:
    common = (
        "Omitted from V1 individual intake + ABN/BAS HTML pack. "
        "V1 only detects, routes, or flags this area for Accountant review where relevant. "
        "Later work must remain official-source-backed, conservative, and prep-only."
    )
    return [issue(title, scope, common) for title, scope in OMITTED_SCOPE_ITEMS]


def issue(title: str, scope: str, common: str) -> Dict[str, str]:
    return {"title": title, "body": f"{common}\n\nScope: {scope}"}


def question_specs() -> List[QuestionSpec]:
    return [
        QuestionSpec("income_year", "Taxpayer", "Income year", "Individual information"),
        QuestionSpec("resident", "Taxpayer", "Australian resident for tax purposes?", "Individual information"),
        QuestionSpec("state", "Taxpayer", "State or territory", "Individual information"),
        QuestionSpec("date_of_birth", "Taxpayer", "Date of birth", "Individual information"),
        QuestionSpec("under_18", "Taxpayer", "Under 18 on 30 June?", "A1 Under 18"),
        QuestionSpec("final_return", "Taxpayer", "Final tax return?", "Individual information"),
        QuestionSpec("tfn_present", "Taxpayer", "TFN available?", "Individual information"),
        QuestionSpec("spouse_had", "Spouse", "Had spouse during income year?", "Spouse details"),
        QuestionSpec("dependant_children", "Spouse", "Dependent children/students count", "IT8 / M1"),
        QuestionSpec("private_health_cover", "Private health", "Private hospital cover?", "M2 / Private health insurance policy details"),
        QuestionSpec("payg_gross", "PAYG", "Salary or wages gross income", "1 Salary or wages", False),
        QuestionSpec("payg_withheld", "PAYG", "Salary or wages tax withheld", "1 Salary or wages", False),
        QuestionSpec("main_occupation", "PAYG", "Main salary and wage occupation", "1 Salary or wages", False),
        QuestionSpec("interest_income", "Income", "Gross interest", "10 Gross interest", False),
        QuestionSpec("dividend_income", "Income", "Dividends or ETF distributions", "11 Dividends", False),
        QuestionSpec("government_payments", "Income", "Government payments or allowances", "5/6 Government payments", False),
        QuestionSpec("etp_statement", "Complex income", "ETP payment summary or income statement held?", "Employment termination payments", False),
        QuestionSpec("etp_taxable_component", "Complex income", "ETP taxable component", "Employment termination payments", False),
        QuestionSpec("etp_tax_free_component", "Complex income", "ETP tax-free component", "Employment termination payments", False),
        QuestionSpec("etp_tax_withheld", "Complex income", "ETP tax withheld", "Employment termination payments", False),
        QuestionSpec("lump_sum_arrears_statement", "Complex income", "Lump sum in arrears statement held?", "Lump sum payment in arrears", False),
        QuestionSpec("lump_sum_arrears_amount", "Complex income", "Lump sum in arrears amount", "Lump sum payment in arrears", False),
        QuestionSpec("lump_sum_arrears_years", "Complex income", "Lump sum in arrears prior years", "Lump sum payment in arrears", False),
        QuestionSpec("lump_sum_arrears_tax_withheld", "Complex income", "Lump sum in arrears tax withheld", "Lump sum payment in arrears", False),
        QuestionSpec("super_income_statement", "Complex income", "Super lump sum or income stream statement held?", "Superannuation lump sums and income streams", False),
        QuestionSpec("super_income_payment_kind", "Complex income", "Super payment kind", "Superannuation lump sums and income streams", False),
        QuestionSpec("super_lump_sum_taxable_component", "Complex income", "Super lump sum taxable component", "Superannuation lump sums", False),
        QuestionSpec("super_lump_sum_tax_free_component", "Complex income", "Super lump sum tax-free component", "Superannuation lump sums", False),
        QuestionSpec("super_income_stream_taxable_amount", "Complex income", "Super income stream taxable amount", "Superannuation income streams", False),
        QuestionSpec("super_income_tax_withheld", "Complex income", "Super tax withheld", "Superannuation lump sums and income streams", False),
        QuestionSpec("foreign_income_statement", "Foreign income", "Foreign income statement or payment summary held?", "Foreign and worldwide income", False),
        QuestionSpec("foreign_income_country", "Foreign income", "Foreign income country", "Foreign and worldwide income", False),
        QuestionSpec("foreign_income_type", "Foreign income", "Foreign income type", "Foreign and worldwide income", False),
        QuestionSpec("foreign_income_amount", "Foreign income", "Foreign income amount", "Foreign and worldwide income", False),
        QuestionSpec("foreign_tax_paid", "Foreign income", "Foreign tax paid", "Foreign income tax offset", False),
        QuestionSpec("foreign_income_exchange_rate", "Foreign income", "Foreign income exchange rate used", "Foreign and worldwide income", False),
        QuestionSpec("foreign_income_residency_status", "Foreign income", "Residency or temporary-resident status for foreign income", "Foreign and worldwide income", False),
        QuestionSpec("foreign_income_tax_offset_claim", "Foreign income", "Foreign income tax offset claimed?", "Foreign income tax offset", False),
        QuestionSpec("foreign_employment_exempt_claim", "Foreign income", "Foreign employment exemption claimed?", "Tax-exempt foreign employment income", False),
        QuestionSpec("ess_statement", "ESS", "ESS statement held?", "Employee share schemes", False),
        QuestionSpec("ess_taxed_upfront_discount", "ESS", "ESS taxed-upfront discount", "Employee share schemes", False),
        QuestionSpec("ess_deferred_discount", "ESS", "ESS deferred discount", "Employee share schemes", False),
        QuestionSpec("ess_foreign_source_discount", "ESS", "ESS foreign-source discount", "Employee share schemes", False),
        QuestionSpec("ess_tfn_amount_withheld", "ESS", "ESS TFN amount withheld", "Employee share schemes", False),
        QuestionSpec("abn_income", "ABN", "Sole-trader ABN income", "Business income / supplementary gate", False),
        QuestionSpec("abn_expenses", "ABN", "Sole-trader ABN expenses", "Business expenses / supplementary gate", False),
        QuestionSpec("gst_registered", "BAS", "GST registered?", "BAS worksheet", False),
        QuestionSpec("bas_period", "BAS", "BAS period", "BAS worksheet", False),
        QuestionSpec("gst_collected", "BAS", "GST collected", "BAS 1A", False),
        QuestionSpec("gst_credits", "BAS", "GST credits", "BAS 1B", False),
        QuestionSpec("employee_deductions", "Deductions", "Employee deductions", "D1-D10 deductions", False),
        QuestionSpec("wfh_work_pattern", "WFH", "WFH work pattern", "D5 Other work-related expenses", False),
        QuestionSpec("wfh_records", "WFH", "WFH records held", "D5 Other work-related expenses", False),
        QuestionSpec("asset_items", "Assets", "Work assets such as monitor/laptop", "D5 Other work-related expenses", False),
    ]


def sample_answers() -> Dict[str, Any]:
    return {
        "income_year": DEFAULT_INCOME_YEAR,
        "resident": True,
        "state": "VIC",
        "date_of_birth": "1990-01-01",
        "under_18": False,
        "final_return": False,
        "tfn_present": True,
        "spouse_had": True,
        "dependant_children": 0,
        "private_health_cover": "partial year; statement not confirmed",
        "payg_gross": 120000,
        "payg_withheld": 31000,
        "main_occupation": "Software engineer",
        "interest_income": 120,
        "dividend_income": 430,
        "government_payments": 0,
        "etp": {
            "statement": "ETP payment summary held",
            "payer": "Example Employer Pty Ltd",
            "payment_type": "life benefit termination payment",
            "payment_date": "2026-04-15",
            "taxable_component": 12000,
            "tax_free_component": 3000,
            "tax_withheld": 3600,
            "code": "R",
        },
        "lump_sum_arrears": {
            "statement": "income statement held",
            "payer": "Example Employer Pty Ltd",
            "amount": 2400,
            "payment_years": "2023-24 and 2024-25",
            "tax_withheld": 500,
        },
        "super_income": {
            "statement": "fund statement held",
            "fund": "Example Super Fund",
            "payment_kind": "income stream",
            "taxable_amount": 18000,
            "tax_free_component": 0,
            "tax_withheld": 2100,
        },
        "foreign_income": {
            "statement": "foreign income statement held",
            "country": "NZ",
            "income_type": "employment",
            "payer": "Example NZ Employer",
            "amount": 5000,
            "foreign_tax_paid": 0,
            "exchange_rate": 0.92,
            "residency_status": "Australian resident for tax purposes all year",
            "foreign_tax_offset_claim": False,
            "foreign_employment_exempt_claim": False,
        },
        "ess": {
            "employer": "Example Pty Ltd",
            "statement": "ESS statement held",
            "taxed_upfront_discount": 1500,
            "deferred_discount": 2400,
            "foreign_source_discount": 300,
            "tfn_amount_withheld": 0,
        },
        "abn_income": 9000,
        "abn_expenses": 2200,
        "gst_registered": True,
        "bas_period": "Quarter ending 30 Jun 2026",
        "gst_collected": 818.18,
        "gst_credits": 140,
        "employee_deductions": [{"label": "Union fees", "amount": 0, "evidence": "unknown"}],
        "wfh": {
            "state": "VIC",
            "start": "2025-07-01",
            "end": "2026-06-30",
            "weekdays": [0, 1, 2],
            "hours_per_day": 7.5,
            "leave_dates": ["2025-12-29"],
            "worked_public_holidays": ["2026-01-26"],
            "worked_weekends": ["2026-02-07"],
            "records": "timesheet",
            "actual_cost_records": "unknown",
        },
        "assets": [
            {
                "description": "$400 monitor",
                "cost": 400,
                "work_use_percent": 80,
                "method_preference": "depreciation",
                "evidence": "receipt",
                "purchase_date": "2026-02-10",
            }
        ],
        "extracted_values": [
            {
                "document": "Income statement PDF",
                "page": 1,
                "field": "PAYG gross",
                "value": 120000,
                "confidence": "high",
                "confirmed": False,
                "target_label": "1 Salary or wages",
            }
        ],
        "uncommon_income": ["foreign income mentioned in notes"],
    }


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("answers input must be a JSON object")
    return payload


def missing_required_answers(answers: Dict[str, Any]) -> List[QuestionSpec]:
    missing: List[QuestionSpec] = []
    for spec in question_specs():
        if spec.required and is_missing(answers.get(spec.key)):
            missing.append(spec)
    return missing


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def has_meaningful_value(value: Any) -> bool:
    if is_missing(value):
        return False
    if isinstance(value, bool):
        return True
    if isinstance(value, list):
        return any(has_meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return any(has_meaningful_value(item) for item in value.values())
    return True


def answers_to_pack_payload(answers: Dict[str, Any]) -> Dict[str, Any]:
    items = base_items(answers)
    extracted_values = extraction_rows(answers.get("extracted_values", []))
    abn_items = abn_rows(answers)
    bas_items = bas_rows(answers)
    missing_items = missing_fact_rows(answers)
    evidence_items = evidence_rows(answers)
    items.extend(wfh_rows(wfh_answers(answers)))
    items.extend(asset_rows(asset_answers(answers)))
    items.extend(complex_payment_rows(complex_payment_answers(answers)))
    items.extend(foreign_income_rows(foreign_income_answers(answers)))
    items.extend(ess_rows(ess_answers(answers)))
    items.extend(uncommon_income_rows(answers.get("uncommon_income", [])))
    return {
        "income_year": text(answers.get("income_year"), DEFAULT_INCOME_YEAR),
        "summary_note": "Individual return, sole-trader ABN, and BAS prep pack. Manual copy only after review.",
        "items": items,
        "extracted_values": extracted_values,
        "abn_items": abn_items,
        "bas_items": bas_items,
        "missing_facts": missing_items,
        "evidence_items": evidence_items,
    }


def base_items(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in question_specs():
        value = answers.get(spec.key)
        if should_render_base_item(spec, value):
            status = base_item_status(spec.key, value)
            rows.append(
                guide_row(
                    spec.key,
                    spec.ato_area,
                    spec.prompt,
                    display_value(value),
                    "Long-checklist intake answer for manual copy guidance.",
                    status,
                    ATO_INDIVIDUAL_SOURCE,
                    tab_text=f"{spec.prompt}: {display_value(value)}",
                )
            )
    return rows


def should_render_base_item(spec: QuestionSpec, value: Any) -> bool:
    if spec.key in ESS_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key == "ess_statement" and ess_statement_declines_workflow(value):
        return False
    if spec.key in COMPLEX_PAYMENT_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in COMPLEX_PAYMENT_STATEMENT_FLAT_FIELDS and complex_payment_declines_workflow(
        value,
        COMPLEX_PAYMENT_FLAT_FIELD_GROUPS[spec.key],
    ):
        return False
    if spec.key in FOREIGN_INCOME_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key == "foreign_income_statement" and foreign_income_declines_workflow(value):
        return False
    if spec.key in FOREIGN_INCOME_FLAT_BOOLEAN_FIELDS and foreign_income_negative_claim_signal(
        foreign_income_nested_claim_key(spec.key),
        value,
    ):
        return False
    return spec.required or has_meaningful_value(value)


def base_item_status(key: str, value: Any) -> str:
    if key in REVIEWABLE_ESS_FIELDS:
        if key == "ess_statement" and ess_statement_missing(value):
            return "Evidence"
        if key in ESS_FLAT_AMOUNT_FIELDS and ess_amount_malformed(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_COMPLEX_PAYMENT_FIELDS:
        group = COMPLEX_PAYMENT_FLAT_FIELD_GROUPS.get(key)
        if key in COMPLEX_PAYMENT_STATEMENT_FLAT_FIELDS and complex_payment_statement_missing(value, group):
            return "Evidence"
        if key in COMPLEX_PAYMENT_FLAT_AMOUNT_FIELDS and complex_payment_amount_malformed(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_FOREIGN_INCOME_FIELDS:
        if key == "foreign_income_statement" and foreign_income_statement_missing(value):
            return "Evidence"
        if key in FOREIGN_INCOME_FLAT_AMOUNT_FIELDS and foreign_income_amount_malformed(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_ABN_FIELDS or key in REVIEWABLE_BAS_FIELDS or key == "gst_registered":
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_COMPLEX_FIELDS or isinstance(value, (dict, list)):
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    return "Evidence" if is_missing(value) or contains_unknown(value) else "Used"


def abn_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    income = money_value(answers.get("abn_income"), unknown_as_missing=True)
    expenses = money_value(answers.get("abn_expenses"), unknown_as_missing=True)
    status = "Accountant review" if has_abn_inputs(answers) else "N/A skipped"
    return [
        guide_row(
            "ABN",
            "Sole-trader ABN",
            "ABN business income and expenses",
            f"Income {money_text(income)}; expenses {money_text(expenses)}",
            "Sole-trader ABN amounts feed individual return business schedules and need accountant review for PSI, losses, GST, and business-versus-hobby.",
            status,
            "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business",
            tab_text="ABN figures are prep-only and not a final business schedule.",
        )
    ]


def bas_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    collected = money_value(answers.get("gst_collected"), unknown_as_missing=True)
    credits = money_value(answers.get("gst_credits"), unknown_as_missing=True)
    net = None if collected is None or credits is None else round(collected - credits, 2)
    status = "Accountant review" if has_bas_inputs(answers) else "N/A skipped"
    return [
        guide_row(
            "BAS",
            "BAS worksheet",
            "GST collected less GST credits",
            f"1A {money_text(collected)}; 1B {money_text(credits)}; net GST {money_text(net)}",
            "BAS worksheet only. Confirm labels, tax invoices, adjustments, and accounting basis before manual use.",
            status,
            [ATO_BAS_SOURCE, ATO_GST_CREDITS_SOURCE],
            tab_text="BAS prep only. No BAS lodgment support.",
        )
    ]


def extraction_rows(raw_values: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_values, list):
        return []
    rows: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_values, start=1):
        if not isinstance(raw, dict):
            continue
        if not has_meaningful_value(raw):
            continue
        confirmed = raw.get("confirmed") is True
        row = {
            "document": display_value(raw.get("document")),
            "page": display_value(raw.get("page")),
            "field": display_value(raw.get("field")),
            "value": display_value(raw.get("value")),
            "confidence": display_value(raw.get("confidence")),
            "target_label": display_value(raw.get("target_label")),
            "status": extraction_status(raw, confirmed),
            "confirmed": confirmed,
            "number": f"AI{idx}",
        }
        preserve_review_kinds(row, raw)
        rows.append(row)
    return rows


def extraction_status(raw: Dict[str, Any], confirmed: bool) -> str:
    if contains_review_status(raw):
        return "Accountant review"
    return "Used" if confirmed else "Evidence"


def contains_review_status(raw: Dict[str, Any]) -> bool:
    return any(is_review_status(raw.get(key)) for key in ("status", "status_kind", "tab_kind"))


def is_review_status(value: Any) -> bool:
    return taxmate_taxpack.known_kind(value) == "review"


def preserve_review_kinds(row: Dict[str, Any], raw: Dict[str, Any]) -> None:
    for key in ("status_kind", "tab_kind"):
        if not is_missing(raw.get(key)):
            row[key] = raw.get(key)


def missing_fact_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        guide_row(
            f"MISS-{idx}",
            spec.ato_area,
            spec.prompt,
            "Missing",
            "Required before the HTML pack can be treated as complete.",
            "Evidence",
            ATO_INDIVIDUAL_SOURCE,
            tab_text=f"Missing answer: {spec.prompt}",
        )
        for idx, spec in enumerate(missing_required_answers(answers), start=1)
    ]


def wfh_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("wfh")
    if not has_meaningful_value(raw) and isinstance(answers.get("wfh_work_pattern"), dict):
        raw = answers.get("wfh_work_pattern")
    if not isinstance(raw, dict) or not has_meaningful_value(raw):
        return {}
    enriched = dict(raw)
    if not has_meaningful_value(enriched.get("records")) and has_meaningful_value(answers.get("wfh_records")):
        enriched["records"] = answers.get("wfh_records")
    if not has_meaningful_value(enriched.get("state")) and has_meaningful_value(answers.get("state")):
        enriched["state"] = answers.get("state")
    enriched["income_year"] = text(answers.get("income_year"), DEFAULT_INCOME_YEAR)
    state_key = normalize_state(enriched.get("state"))
    if state_key is not None:
        enriched["state"] = state_key
    return enriched


def has_bas_inputs(answers: Dict[str, Any]) -> bool:
    gst_registered = answers.get("gst_registered")
    gst_status = parse_gst_registration(gst_registered)
    if gst_status is True or (gst_status is None and not is_missing(gst_registered)):
        return True
    for key in REVIEWABLE_BAS_FIELDS:
        if key in answers and not is_missing(answers.get(key)):
            return True
    return False


def has_abn_inputs(answers: Dict[str, Any]) -> bool:
    for key in REVIEWABLE_ABN_FIELDS:
        if key in answers and not is_missing(answers.get(key)):
            return True
    return False


def parse_gst_registration(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if is_missing(value):
        return False
    if contains_unknown(value):
        return None
    canonical = text(value).strip().lower()
    if canonical in {"yes", "y", "true", "registered", "gst registered"}:
        return True
    if canonical in {"no", "n", "false", "not registered", "not gst registered"}:
        return False
    return None


def evidence_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if contains_unknown(answers.get("private_health_cover")):
        rows.append(evidence_row("Private health statement", "M2 / Private health", "Insurer statement or policy details"))
    asset_items = answers.get("assets", [])
    if not isinstance(asset_items, list):
        asset_items = []
    for item in asset_items:
        if isinstance(item, dict) and contains_unknown(item.get("evidence")):
            rows.append(evidence_row(display_value(item.get("description")), "D5 assets", "Receipt/tax invoice"))
    wfh = answers.get("wfh", {})
    if isinstance(wfh, dict) and contains_unknown(wfh.get("records")):
        rows.append(evidence_row("WFH records", "D5 WFH", "Diary, timesheet, roster, or similar records"))
    return rows


def evidence_row(number: Any, area: str, evidence: str) -> Dict[str, Any]:
    return guide_row(number, area, "Evidence required", evidence, "Draft value remains not copy-ready until evidence is confirmed.", "Evidence", ATO_INDIVIDUAL_SOURCE)


def wfh_rows(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        return []
    hours = calculate_wfh_hours(raw)
    fixed_candidate = wfh_fixed_rate_candidate(hours, raw)
    hours_text = "unknown" if hours is None else f"{hours:.2f}"
    fixed_rate_text = money_text(fixed_candidate)
    records = raw.get("records")
    actual_cost_record_value = raw.get("actual_cost_records")
    actual_cost_records = display_value(actual_cost_record_value) or "unknown"
    status = (
        "Evidence"
        if hours is None
        or is_missing(records)
        or contains_unknown(records)
        or is_missing(actual_cost_record_value)
        or contains_unknown(actual_cost_record_value)
        else "Accountant review"
    )
    return [
        guide_row(
            "WFH",
            "D5 Other work-related expenses",
            "WFH fixed-rate and actual-cost comparison",
            f"{hours_text} hours; fixed-rate candidate {fixed_rate_text}; actual-cost records {actual_cost_records}",
            "Calendar helper excludes non-work public holidays and leave, includes confirmed weekends/holidays worked, and still requires records/method review.",
            status,
            [ATO_WFH_FIXED_SOURCE, ATO_WFH_ACTUAL_SOURCE, *PUBLIC_HOLIDAY_SOURCES],
            tab_text="WFH amount is not copy-ready without records and method review.",
        )
    ]


def calculate_wfh_hours(raw: Dict[str, Any]) -> Optional[float]:
    if "start" not in raw or "end" not in raw:
        return None
    start = parse_iso_date(raw.get("start"))
    end = parse_iso_date(raw.get("end"))
    if start is None or end is None or end < start:
        return None
    if not supported_wfh_income_year(raw):
        return None
    if not dates_within_supported_income_year(start, end):
        return None
    weekdays = parse_weekdays(raw)
    if weekdays is None:
        return None
    hours_per_day = money_value(raw.get("hours_per_day"), unknown_as_missing=True)
    if hours_per_day is None or hours_per_day <= 0 or hours_per_day > 24:
        return None
    state_key = normalize_state(raw.get("state"))
    if state_key is None:
        return None
    adjustment_dates = wfh_adjustment_dates(raw)
    if adjustment_dates is None:
        return None
    leave, worked_public, worked_weekends = adjustment_dates
    holidays = public_holidays(state_key)
    limited_holidays = limited_public_holidays(state_key)
    if limited_public_holiday_may_affect_period(start, end, weekdays, limited_holidays, leave, worked_public, worked_weekends):
        return None
    if not valid_wfh_adjustment_dates(start, end, weekdays, holidays, leave, worked_public, worked_weekends):
        return None
    work_days = 0
    current = start
    while current <= end:
        normal_workday = current.weekday() in weekdays
        holiday_not_worked = current in holidays and current not in worked_public
        leave_day = current in leave
        weekend_worked = current in worked_weekends
        holiday_worked = current in worked_public
        if ((normal_workday and not holiday_not_worked and not leave_day) or weekend_worked or holiday_worked):
            work_days += 1
        current += timedelta(days=1)
    return round(work_days * hours_per_day, 2)


def supported_wfh_income_year(raw: Dict[str, Any]) -> bool:
    return text(raw.get("income_year"), DEFAULT_INCOME_YEAR) == DEFAULT_INCOME_YEAR


def dates_within_supported_income_year(start: date, end: date) -> bool:
    return SUPPORTED_WFH_START <= start <= end <= SUPPORTED_WFH_END


def limited_public_holidays(state: Any) -> Set[date]:
    state_key = normalize_state(state)
    if state_key is None:
        return set()
    return {date.fromisoformat(value) for value in LIMITED_PUBLIC_HOLIDAYS_BY_STATE.get(state_key, set())}


def limited_public_holiday_may_affect_period(
    start: date,
    end: date,
    weekdays: Set[int],
    limited_holidays: Set[date],
    leave: Set[date],
    worked_public: Set[date],
    worked_weekends: Set[date],
) -> bool:
    relevant_adjustments = leave | worked_public | worked_weekends
    for day in limited_holidays:
        if start <= day <= end and (day.weekday() in weekdays or day in relevant_adjustments):
            return True
    return False


def has_complete_wfh_records(raw: Dict[str, Any]) -> bool:
    records = raw.get("records")
    return not is_missing(records) and not contains_unknown(records)


def wfh_fixed_rate_candidate(hours: Optional[float], raw: Dict[str, Any]) -> Optional[float]:
    if hours is None or not has_complete_wfh_records(raw):
        return None
    return round(float(hours) * WFH_FIXED_RATE_2025_26, 2)


def wfh_adjustment_dates(raw: Dict[str, Any]) -> Optional[tuple[Set[date], Set[date], Set[date]]]:
    required_keys = ("leave_dates", "worked_public_holidays", "worked_weekends")
    if any(key not in raw for key in required_keys):
        return None
    leave = parse_dates(raw.get("leave_dates"))
    worked_public = parse_dates(raw.get("worked_public_holidays"))
    worked_weekends = parse_dates(raw.get("worked_weekends"))
    if leave is None or worked_public is None or worked_weekends is None:
        return None
    return leave, worked_public, worked_weekends


def valid_wfh_adjustment_dates(
    start: date,
    end: date,
    weekdays: Set[int],
    holidays: Set[date],
    leave: Set[date],
    worked_public: Set[date],
    worked_weekends: Set[date],
) -> bool:
    all_adjustments = leave | worked_public | worked_weekends
    if any(day < start or day > end for day in all_adjustments):
        return False
    if any(day.weekday() not in weekdays for day in leave):
        return False
    if any(day not in holidays for day in worked_public):
        return False
    if any(day.weekday() < 5 for day in worked_weekends):
        return False
    return True


def parse_weekdays(raw: Dict[str, Any]) -> Optional[Set[int]]:
    if "weekdays" not in raw or contains_unknown(raw.get("weekdays")):
        return None
    weekdays = raw.get("weekdays")
    if not isinstance(weekdays, list) or not weekdays:
        return None
    parsed_days: Set[int] = set()
    for day in weekdays:
        parsed_day = parse_weekday(day)
        if parsed_day is None:
            return None
        parsed_days.add(parsed_day)
    return parsed_days or None


def parse_weekday(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 6 else None
    canonical = text(value).strip().upper()
    if canonical.isdigit():
        day = int(canonical)
        return day if 0 <= day <= 6 else None
    return WEEKDAY_ALIASES.get(canonical)


def public_holidays(state: Any) -> Set[date]:
    state_key = normalize_state(state)
    if state_key is None:
        return set()
    national = {
        "2025-12-25",
        "2025-12-26",
        "2026-01-01",
        "2026-01-26",
        "2026-04-03",
        "2026-04-06",
        "2026-04-25",
    }
    state_days = {
        "VIC": {"2025-09-26", "2026-03-09", "2026-04-04", "2026-04-05", "2026-06-08"},
        "NSW": {"2025-10-06", "2026-04-04", "2026-04-05", "2026-04-27", "2026-06-08"},
        "QLD": {"2025-10-06", "2026-04-04", "2026-04-05", "2026-05-04"},
        "SA": {"2025-10-06", "2026-03-09", "2026-04-04", "2026-04-05", "2026-06-08"},
        "WA": {"2026-03-02", "2026-04-05", "2026-04-27", "2026-06-01"},
        "TAS": {"2026-03-09", "2026-06-08"},
        "ACT": {"2025-10-06", "2026-03-09", "2026-04-04", "2026-04-05", "2026-04-27", "2026-06-01", "2026-06-08"},
        "NT": {"2025-08-04", "2026-04-04", "2026-04-05", "2026-05-04", "2026-06-08"},
    }
    values = set(national)
    values.update(state_days.get(state_key, set()))
    return {date.fromisoformat(value) for value in values}


def normalize_state(value: Any) -> Optional[str]:
    canonical = text(value).strip().upper()
    return STATE_ALIASES.get(canonical)


def asset_rows(raw_assets: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_assets, list):
        return []
    rows: List[Dict[str, Any]] = []
    for idx, asset in enumerate(raw_assets, start=1):
        if not isinstance(asset, dict):
            continue
        if not has_meaningful_value(asset):
            continue
        cost = money_value(asset.get("cost"), unknown_as_missing=True)
        work_use = money_value(asset.get("work_use_percent"), unknown_as_missing=True)
        claim_basis = asset_claim_basis(cost, work_use, asset.get("method_preference"))
        rows.append(
            guide_row(
                f"ASSET-{idx}",
                "D5 Other work-related expenses",
                display_value(asset.get("description")),
                claim_basis,
                "ATO-guided asset treatment asks work-use, cost, evidence, and method. Items over $300 are not auto-claimed in full.",
                asset_status(cost, work_use),
                ATO_ASSET_SOURCE,
                tab_text="Asset treatment needs evidence and method review before manual copy.",
            )
        )
    return rows


def asset_answers(answers: Dict[str, Any]) -> Any:
    raw_assets = answers.get("assets")
    if isinstance(raw_assets, list) and has_meaningful_value(raw_assets):
        return raw_assets
    return answers.get("asset_items", [])


def asset_status(cost: Optional[float], work_use: Optional[float]) -> str:
    if cost is None or work_use is None:
        return "Evidence"
    return "Accountant review" if cost > 300 or work_use != 100 else "Evidence"


def asset_claim_basis(cost: Optional[float], work_use: Optional[float], preference: Any) -> str:
    work_amount = None if cost is None or work_use is None else round(cost * work_use / 100, 2)
    if cost is None or work_use is None:
        return (
            f"Cost {money_text(cost)}; work use {percent_text(work_use)}; "
            f"work-use amount {money_text(work_amount)}; evidence needed before method review"
        )
    if cost > 300:
        return f"Cost {money_text(cost)}; work use {percent_text(work_use)}; work-use amount {money_text(work_amount)}; {display_value(preference)} candidate, not full immediate claim"
    if work_use != 100:
        return f"Cost {money_text(cost)}; work use {percent_text(work_use)}; work-use amount {money_text(work_amount)}; mixed-use immediate/depreciation method needs review"
    return f"Cost {money_text(cost)}; work use {percent_text(work_use)}; work-use amount {money_text(work_amount)}; immediate deduction candidate if evidence supports"


def complex_payment_answers(answers: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        "etp": merge_payment_answers(
            answers.get("etp"),
            {
                "statement": answers.get("etp_statement"),
                "payer": answers.get("etp_payer"),
                "payment_type": answers.get("etp_payment_type"),
                "payment_date": answers.get("etp_payment_date"),
                "taxable_component": answers.get("etp_taxable_component"),
                "tax_free_component": answers.get("etp_tax_free_component"),
                "tax_withheld": answers.get("etp_tax_withheld"),
                "code": answers.get("etp_code"),
            },
            "etp",
        ),
        "lump_sum_arrears": merge_payment_answers(
            answers.get("lump_sum_arrears"),
            {
                "statement": answers.get("lump_sum_arrears_statement"),
                "payer": answers.get("lump_sum_arrears_payer"),
                "amount": answers.get("lump_sum_arrears_amount"),
                "payment_years": answers.get("lump_sum_arrears_years"),
                "tax_withheld": answers.get("lump_sum_arrears_tax_withheld"),
            },
            "lump_sum_arrears",
        ),
        "super_income": merge_payment_answers(
            answers.get("super_income"),
            {
                "statement": answers.get("super_income_statement"),
                "fund": answers.get("super_income_fund"),
                "payment_kind": answers.get("super_income_payment_kind"),
                "taxable_component": answers.get("super_lump_sum_taxable_component"),
                "tax_free_component": answers.get("super_lump_sum_tax_free_component"),
                "taxable_amount": answers.get("super_income_stream_taxable_amount"),
                "tax_withheld": answers.get("super_income_tax_withheld"),
            },
            "super_income",
        ),
    }


def merge_payment_answers(raw: Any, flat: Dict[str, Any], group: Optional[str] = None) -> Dict[str, Any]:
    merged = {key: value for key, value in flat.items() if has_meaningful_value(value)}
    if not isinstance(raw, dict) or not has_meaningful_value(raw):
        return merged
    for key, value in raw.items():
        if has_meaningful_payment_signal(key, value, group):
            merged[key] = value
        elif key not in merged and has_explicit_payment_evidence_gap(key, value):
            merged[key] = value
    return merged


def complex_payment_rows(groups: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    rows.extend(etp_rows(groups.get("etp", {})))
    rows.extend(lump_sum_arrears_rows(groups.get("lump_sum_arrears", {})))
    rows.extend(super_income_rows(groups.get("super_income", {})))
    return rows


def etp_rows(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    group = "etp"
    if not has_complex_payment_inputs(raw, group):
        return []
    amount_evidence = payment_amounts_need_evidence(raw, ("taxable_component", "tax_free_component", "tax_withheld"))
    statement_evidence = complex_payment_statement_missing(raw.get("statement"), group)
    status = "Evidence" if amount_evidence or statement_evidence else "Accountant review"
    answer = (
        f"Payer {display_value(raw.get('payer'))}; "
        f"type {display_value(raw.get('payment_type'))}; "
        f"date {display_value(raw.get('payment_date'))}; "
        f"code {display_value(raw.get('code'))}; "
        f"taxable component {money_text(complex_payment_money_value(raw.get('taxable_component')))}; "
        f"tax-free component {money_text(complex_payment_money_value(raw.get('tax_free_component')))}; "
        f"tax withheld {money_text(complex_payment_money_value(raw.get('tax_withheld')))}"
    )
    return [
        guide_row(
            "ETP",
            "Employment termination payments",
            "ETP payment summary workflow",
            answer,
            "ETP records need payment summary/income statement evidence, payment code, component split, cap context, and accountant review before manual copy.",
            status,
            ATO_ETP_SOURCE,
            tab_text=complex_payment_tab_text("ETP", statement_evidence, amount_evidence),
        )
    ]


def lump_sum_arrears_rows(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    group = "lump_sum_arrears"
    if not has_complex_payment_inputs(raw, group):
        return []
    amount_evidence = payment_amounts_need_evidence(raw, ("amount", "tax_withheld"))
    statement_evidence = complex_payment_statement_missing(raw.get("statement"), group)
    prior_year_evidence = is_missing(raw.get("payment_years")) or contains_unknown(raw.get("payment_years"))
    status = "Evidence" if amount_evidence or statement_evidence or prior_year_evidence else "Accountant review"
    answer = (
        f"Payer {display_value(raw.get('payer'))}; "
        f"prior years {display_value(raw.get('payment_years'))}; "
        f"amount {money_text(complex_payment_money_value(raw.get('amount')))}; "
        f"tax withheld {money_text(complex_payment_money_value(raw.get('tax_withheld')))}"
    )
    return [
        guide_row(
            "LUMP-ARREARS",
            "Lump sum payment in arrears",
            "Lump sum in arrears workflow",
            answer,
            "Lump sum in arrears records need statement evidence, prior-year allocation, amount, withholding, and accountant review before manual copy.",
            status,
            ATO_LUMP_SUM_ARREARS_SOURCE,
            tab_text=lump_sum_arrears_tab_text(statement_evidence, prior_year_evidence, amount_evidence),
        )
    ]


def super_income_rows(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    group = "super_income"
    if not has_complex_payment_inputs(raw, group):
        return []
    amount_evidence = payment_amounts_need_evidence(
        raw,
        ("taxable_component", "tax_free_component", "taxable_amount", "tax_withheld"),
    )
    statement_evidence = complex_payment_statement_missing(raw.get("statement"), group)
    status = "Evidence" if amount_evidence or statement_evidence else "Accountant review"
    answer = (
        f"Fund {display_value(raw.get('fund'))}; "
        f"kind {display_value(raw.get('payment_kind'))}; "
        f"taxable component {money_text(complex_payment_money_value(raw.get('taxable_component')))}; "
        f"tax-free component {money_text(complex_payment_money_value(raw.get('tax_free_component')))}; "
        f"income-stream taxable amount {money_text(complex_payment_money_value(raw.get('taxable_amount')))}; "
        f"tax withheld {money_text(complex_payment_money_value(raw.get('tax_withheld')))}"
    )
    return [
        guide_row(
            "SUPER-INCOME",
            "Superannuation lump sum or income stream",
            "Super lump sum or income stream workflow",
            answer,
            "Super lump sums and income streams need fund statement evidence, component split, withholding, age/condition context, and accountant review before manual copy.",
            status,
            [ATO_SUPER_PENSIONS_SOURCE, ATO_SUPER_LUMP_SUM_SOURCE, ATO_SUPER_STREAM_SOURCE],
            tab_text=complex_payment_tab_text("Super income", statement_evidence, amount_evidence),
        )
    ]


def has_complex_payment_inputs(raw: Dict[str, Any], group: Optional[str] = None) -> bool:
    if not isinstance(raw, dict):
        return False
    if payment_statement_declines_without_facts(raw, group):
        return False
    if any(has_explicit_payment_evidence_gap(key, raw.get(key)) for key in ("statement", *COMPLEX_PAYMENT_AMOUNT_FIELDS)):
        return True
    return any(has_meaningful_payment_signal(key, value, group) for key, value in raw.items())


def payment_statement_declines_without_facts(raw: Dict[str, Any], group: Optional[str] = None) -> bool:
    if not complex_payment_declines_workflow(raw.get("statement"), group):
        return False
    return not any(
        has_meaningful_payment_signal(key, value, group) or has_explicit_payment_evidence_gap(key, value)
        for key, value in raw.items()
        if key != "statement"
    )


def has_meaningful_payment_signal(key: str, value: Any, group: Optional[str] = None) -> bool:
    if key in COMPLEX_PAYMENT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if contains_unknown(value):
        return False
    if key == "statement" and complex_payment_declines_workflow(value, group):
        return False
    return has_meaningful_value(value)


def has_explicit_payment_evidence_gap(key: str, value: Any) -> bool:
    if key in COMPLEX_PAYMENT_AMOUNT_FIELDS:
        return complex_payment_amount_needs_evidence(value)
    if key == "statement":
        return has_meaningful_value(value) and contains_unknown(value)
    return False


def complex_payment_statement_missing(statement: Any, group: Optional[str] = None) -> bool:
    if isinstance(statement, bool):
        return not statement
    if is_missing(statement) or contains_unknown(statement):
        return True
    if complex_payment_declines_workflow(statement, group):
        return True
    lowered = text(statement).strip().lower()
    return lowered in {"no", "n", "false", "none"} or any(
        phrase in lowered for phrase in COMPLEX_PAYMENT_STATEMENT_MISSING_PHRASES
    )


def complex_payment_declines_workflow(statement: Any, group: Optional[str] = None) -> bool:
    if not isinstance(statement, str):
        return False
    lowered = statement.strip().lower()
    group_phrases = COMPLEX_PAYMENT_DECLINE_PHRASES_BY_GROUP.get(group or "", ())
    return lowered in COMPLEX_PAYMENT_DECLINE_PHRASES or lowered in group_phrases


def payment_amounts_need_evidence(raw: Dict[str, Any], amount_fields: tuple[str, ...]) -> bool:
    return any(complex_payment_amount_needs_evidence(raw.get(key)) for key in amount_fields)


def complex_payment_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    return contains_unknown(value) or complex_payment_amount_malformed(value)


def complex_payment_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return False


def complex_payment_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def complex_payment_tab_text(label: str, statement_evidence: bool, amount_evidence: bool) -> str:
    if statement_evidence and amount_evidence:
        return f"{label} needs statement evidence and numeric amount evidence before accountant review."
    if amount_evidence:
        return f"{label} amount fields need numeric amount evidence before accountant review."
    if statement_evidence:
        return f"{label} needs statement evidence before accountant review."
    return f"{label} needs source-backed accountant review."


def lump_sum_arrears_tab_text(statement_evidence: bool, prior_year_evidence: bool, amount_evidence: bool) -> str:
    evidence = []
    if statement_evidence:
        evidence.append("statement evidence")
    if prior_year_evidence:
        evidence.append("prior-year allocation evidence")
    if amount_evidence:
        evidence.append("numeric amount evidence")
    if evidence:
        return f"Lump sum in arrears needs {', '.join(evidence)} before accountant review."
    return "Lump sum in arrears needs source-backed accountant review."


def foreign_income_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("foreign_income")
    fields = {
        "statement": answers.get("foreign_income_statement"),
        "country": answers.get("foreign_income_country"),
        "income_type": answers.get("foreign_income_type"),
        "payer": answers.get("foreign_income_payer"),
        "amount": answers.get("foreign_income_amount"),
        "foreign_tax_paid": answers.get("foreign_tax_paid"),
        "exchange_rate": answers.get("foreign_income_exchange_rate"),
        "residency_status": answers.get("foreign_income_residency_status"),
        "foreign_tax_offset_claim": answers.get("foreign_income_tax_offset_claim"),
        "foreign_employment_exempt_claim": answers.get("foreign_employment_exempt_claim"),
        "items": answers.get("foreign_income_items"),
    }
    flat_values = {key: value for key, value in fields.items() if has_meaningful_foreign_income_flat_value(key, value)}
    if not isinstance(raw, dict):
        return flat_values
    if not has_meaningful_value(raw):
        return flat_values
    merged = dict(flat_values)
    for key, value in raw.items():
        if foreign_income_should_ignore_boolean_signal(merged, key, value):
            continue
        if foreign_income_should_merge_boolean_signal(merged, key, value):
            merged[key] = value
        elif has_meaningful_foreign_income_override(key, value):
            merged[key] = value
        elif key not in merged and has_explicit_foreign_income_evidence_gap(key, value):
            merged[key] = value
    return merged


def foreign_income_should_merge_boolean_signal(merged: Dict[str, Any], key: str, value: Any) -> bool:
    if key not in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS:
        return False
    if not (isinstance(value, bool) or has_meaningful_value(value)):
        return False
    return not foreign_income_should_ignore_boolean_signal(merged, key, value)


def foreign_income_should_ignore_boolean_signal(merged: Dict[str, Any], key: str, value: Any) -> bool:
    return (
        key in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS
        and merged.get(key) is True
        and foreign_income_negative_claim_signal(key, value)
    )


def foreign_income_negative_claim_signal(key: str, value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return foreign_income_claim_negative(key, value)
    return False


def foreign_income_nested_claim_key(key: str) -> str:
    if key == "foreign_income_tax_offset_claim":
        return "foreign_tax_offset_claim"
    return key


def has_meaningful_foreign_income_flat_value(key: str, value: Any) -> bool:
    if key in FOREIGN_INCOME_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    return has_meaningful_value(value)


def foreign_income_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_foreign_income_inputs(raw):
        return []
    if not isinstance(raw, dict):
        return []
    items = foreign_income_item_values(raw.get("items"))
    amount = foreign_income_amount_value(raw, items, "amount")
    foreign_tax_paid = foreign_income_amount_value(raw, items, "foreign_tax_paid", "tax_paid")
    exchange_rate = foreign_income_summary_exchange_rate_text(raw, items)
    statement_evidence = foreign_income_statement_evidence(raw, items)
    amount_evidence = foreign_income_amounts_need_evidence(raw, items)
    residency_evidence = foreign_income_residency_needs_evidence(raw, items)
    tax_paid_evidence = foreign_income_tax_paid_needs_evidence(raw, items)
    status = "Evidence" if statement_evidence or amount_evidence or residency_evidence or tax_paid_evidence else "Accountant review"
    answer = (
        f"Country {foreign_income_country_text(raw, items)}; "
        f"type {display_value(raw.get('income_type')) or 'unknown'}; "
        f"payer {display_value(raw.get('payer')) or 'unknown'}; "
        f"amount {money_text(amount)}; "
        f"foreign tax paid {money_text(foreign_tax_paid)}; "
        f"exchange rate {exchange_rate}; "
        f"residency {foreign_income_field_text(raw, items, 'residency_status')}; "
        f"foreign tax offset claim {foreign_income_claim_text(raw, items, 'foreign_tax_offset_claim')}; "
        f"foreign employment exemption claim {foreign_income_claim_text(raw, items, 'foreign_employment_exempt_claim')}"
    )
    item_text = foreign_income_items_text(items)
    if item_text:
        answer = f"{answer}; items {item_text}"
    return [
        guide_row(
            "FOREIGN-INCOME",
            "Foreign and worldwide income",
            "Foreign income, residency, and tax offset workflow",
            answer,
            "Foreign income needs source statement evidence, residency or temporary-resident context, foreign tax paid records, exchange-rate support, and accountant review before manual copy.",
            status,
            ATO_FOREIGN_INCOME_SOURCES,
            tab_text=foreign_income_tab_text(
                statement_evidence,
                amount_evidence,
                residency_evidence,
                tax_paid_evidence,
            ),
        )
    ]


def foreign_income_item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict) and has_meaningful_foreign_income_item(item)]


def has_meaningful_foreign_income_item(item: Dict[str, Any]) -> bool:
    if any(has_meaningful_foreign_income_signal(key, item.get(key)) for key in FOREIGN_INCOME_SIGNAL_FIELDS):
        return True
    return any(foreign_income_amount_needs_evidence(item.get(key)) for key in FOREIGN_INCOME_AMOUNT_FIELDS)


def has_meaningful_foreign_income_override(key: str, value: Any) -> bool:
    if key == "items":
        return bool(foreign_income_item_values(value))
    return has_meaningful_foreign_income_signal(key, value)


def has_meaningful_foreign_income_signal(key: str, value: Any) -> bool:
    if key in FOREIGN_INCOME_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS and isinstance(value, bool):
        return value
    if key in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS and foreign_income_claim_negative(key, value):
        return False
    if contains_unknown(value):
        return False
    if key == "statement" and foreign_income_declines_workflow(value):
        return False
    return has_meaningful_value(value)


def has_explicit_foreign_income_evidence_gap(key: str, value: Any) -> bool:
    if key in FOREIGN_INCOME_AMOUNT_FIELDS:
        return foreign_income_amount_needs_evidence(value)
    if key in ("statement", "residency_status"):
        return has_meaningful_value(value) and contains_unknown(value)
    return False


def has_foreign_income_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if foreign_income_declines_without_facts(raw):
        return False
    if foreign_income_item_values(raw.get("items")):
        return True
    if any(
        has_explicit_foreign_income_evidence_gap(key, raw.get(key))
        for key in ("statement", "residency_status", *FOREIGN_INCOME_AMOUNT_FIELDS)
    ):
        return True
    return any(has_meaningful_foreign_income_signal(key, raw.get(key)) for key in FOREIGN_INCOME_SIGNAL_FIELDS)


def foreign_income_declines_without_facts(raw: Dict[str, Any]) -> bool:
    if not foreign_income_declines_workflow(raw.get("statement")):
        return False
    if foreign_income_item_values(raw.get("items")):
        return False
    return not any(
        has_meaningful_foreign_income_signal(key, value) or has_explicit_foreign_income_evidence_gap(key, value)
        for key, value in raw.items()
        if key != "statement"
    )


def foreign_income_statement_missing(statement: Any) -> bool:
    if isinstance(statement, bool):
        return not statement
    if is_missing(statement) or contains_unknown(statement):
        return True
    if foreign_income_declines_workflow(statement):
        return True
    lowered = text(statement).strip().lower()
    return lowered in {"no", "n", "false", "none", "not held", "not available"} or any(
        phrase in lowered for phrase in FOREIGN_INCOME_STATEMENT_MISSING_PHRASES
    ) or foreign_income_document_denial_phrase(lowered)


def foreign_income_declines_workflow(statement: Any) -> bool:
    if not isinstance(statement, str):
        return False
    if contains_unknown(statement):
        return False
    lowered = statement.strip().lower()
    if foreign_income_decline_phrase_is_tax_paid_context(lowered):
        return False
    if foreign_income_absence_decline_phrase(lowered):
        return True
    if foreign_income_document_context(lowered):
        return False
    return any(foreign_income_decline_phrase_matches(lowered, phrase) for phrase in FOREIGN_INCOME_DECLINE_PHRASES)


def foreign_income_absence_decline_phrase(lowered: str) -> bool:
    if foreign_income_document_context(lowered) or foreign_income_decline_phrase_is_tax_paid_context(lowered):
        return False
    return any(
        phrase in lowered
        for phrase in (
            "do not have any foreign income",
            "do not have foreign income",
            "don't have any foreign income",
            "don't have foreign income",
        )
    )


def foreign_income_document_context(lowered: str) -> bool:
    return "statement" in lowered or "payment summary" in lowered


def foreign_income_document_denial_phrase(lowered: str) -> bool:
    if not foreign_income_document_context(lowered):
        return False
    if foreign_income_document_positive_phrase(lowered):
        return False
    return lowered.startswith(("no ", "without ", "missing ")) or any(
        phrase in lowered
        for phrase in (
            "do not have",
            "don't have",
            "not held",
            "not available",
            "not provided",
            "not received",
            "not supplied",
        )
    )


def foreign_income_document_positive_phrase(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "statement held",
            "statement available",
            "statement provided",
            "statement received",
            "statement supplied",
            "payment summary held",
            "payment summary available",
            "payment summary provided",
            "payment summary received",
            "payment summary supplied",
        )
    )


def foreign_income_decline_phrase_matches(lowered: str, phrase: str) -> bool:
    if foreign_income_decline_phrase_is_tax_paid_context(lowered):
        return False
    if phrase in {"na", "n/a"}:
        return lowered == phrase
    return lowered == phrase or phrase in lowered


def foreign_income_decline_phrase_is_tax_paid_context(lowered: str) -> bool:
    return "no foreign income tax" in lowered or "foreign income tax paid" in lowered


def foreign_income_statement_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    statement = raw.get("statement")
    if has_meaningful_value(statement):
        if foreign_income_statement_missing(statement):
            return True
        return foreign_income_items_have_explicit_statement_gap(items)
    if items:
        return foreign_income_items_need_statement_evidence(items)
    return True


def foreign_income_items_need_statement_evidence(items: List[Dict[str, Any]]) -> bool:
    return any(foreign_income_statement_missing(item.get("statement")) for item in items)


def foreign_income_items_have_explicit_statement_gap(items: List[Dict[str, Any]]) -> bool:
    return any(
        has_meaningful_value(item.get("statement")) and foreign_income_statement_missing(item.get("statement"))
        for item in items
    )


def foreign_income_residency_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    residency = raw.get("residency_status")
    if is_missing(residency):
        if items:
            return any(foreign_income_item_residency_missing(item) for item in items)
        return True
    if contains_unknown(residency):
        return True
    return any(
        has_meaningful_value(item.get("residency_status")) and contains_unknown(item.get("residency_status"))
        for item in items
    )


def foreign_income_item_residency_missing(item: Dict[str, Any]) -> bool:
    residency = item.get("residency_status")
    return is_missing(residency) or contains_unknown(residency)


def foreign_income_tax_paid_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    raw_has_tax_paid = foreign_income_raw_has_tax_paid(raw)
    if (
        foreign_income_offset_claim_needs_tax_paid(raw.get("foreign_tax_offset_claim"))
        and not raw_has_tax_paid
        and not foreign_income_items_have_tax_paid(items)
    ):
        return True
    return any(
        foreign_income_offset_claim_needs_tax_paid(item.get("foreign_tax_offset_claim"))
        and not raw_has_tax_paid
        and not foreign_income_has_tax_paid_value(item.get("foreign_tax_paid"))
        and not foreign_income_has_tax_paid_value(item.get("tax_paid"))
        for item in items
    )


def foreign_income_raw_has_tax_paid(raw: Dict[str, Any]) -> bool:
    return foreign_income_has_tax_paid_value(raw.get("foreign_tax_paid")) or foreign_income_has_tax_paid_value(
        raw.get("tax_paid")
    )


def foreign_income_items_have_tax_paid(items: List[Dict[str, Any]]) -> bool:
    return any(
        foreign_income_has_tax_paid_value(item.get("foreign_tax_paid"))
        or foreign_income_has_tax_paid_value(item.get("tax_paid"))
        for item in items
    )


def foreign_income_has_tax_paid_value(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    amount = foreign_income_money_value(value)
    if amount is not None:
        return amount > 0
    return not contains_unknown(value)


def foreign_income_offset_claimed(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        lowered = value.strip().lower()
        if foreign_income_offset_claim_negative(value):
            return False
        return lowered in {"yes", "y", "true", "claimed", "claim"} or any(
            phrase in lowered
            for phrase in (
                "yes,",
                "claiming",
                "will claim",
                "intend to claim",
                "claim the offset",
                "claim foreign income tax offset",
            )
        )
    return False


def foreign_income_offset_claim_needs_tax_paid(value: Any) -> bool:
    if foreign_income_offset_claimed(value) or contains_unknown(value):
        return True
    if isinstance(value, str):
        return has_meaningful_value(value) and not foreign_income_offset_claim_negative(value)
    return False


def foreign_income_claim_negative(key: str, value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if key == "foreign_tax_offset_claim":
        return foreign_income_offset_claim_negative(value)
    if key == "foreign_employment_exempt_claim":
        return foreign_income_exemption_claim_negative(value)
    return False


def foreign_income_offset_claim_negative(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in {"no", "n", "false", "not claimed"} or any(
        phrase in lowered
        for phrase in (
            "no offset",
            "no foreign income tax offset",
            "no claim",
            "not claim",
            "not claiming",
            "will not claim",
            "do not claim",
            "don't claim",
        )
    )


def foreign_income_exemption_claim_negative(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in {"no", "n", "false", "not exempt", "not claimed"} or any(
        phrase in lowered
        for phrase in (
            "no exemption",
            "no foreign employment exemption",
            "no exempt income",
            "not exempt",
            "not claim",
            "not claiming",
            "will not claim",
            "do not claim",
            "don't claim",
        )
    )


def foreign_income_amounts_need_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if foreign_income_amount_values_conflict(raw, items):
        return True
    if foreign_income_exchange_rate_missing(raw, items):
        return True
    if any(foreign_income_amount_needs_evidence(raw.get(key)) for key in FOREIGN_INCOME_AMOUNT_FIELDS):
        return True
    return any(foreign_income_amount_needs_evidence(item.get(key)) for item in items for key in FOREIGN_INCOME_AMOUNT_FIELDS)


def foreign_income_amount_values_conflict(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return foreign_income_amount_value_conflicts(raw, items, "amount") or foreign_income_amount_value_conflicts(
        raw, items, "foreign_tax_paid", "tax_paid"
    )


def foreign_income_amount_value_conflicts(
    raw: Dict[str, Any],
    items: List[Dict[str, Any]],
    key: str,
    alias: str = "",
) -> bool:
    direct = foreign_income_money_value(raw.get(key))
    if direct is None and alias:
        direct = foreign_income_money_value(raw.get(alias))
    item_total = foreign_income_item_amount_total(items, key, alias)
    return direct is not None and item_total is not None and abs(direct - item_total) > 0.005


def foreign_income_exchange_rate_missing(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    item_rate_gap = any(
        foreign_income_money_value(item.get("amount")) is not None
        and foreign_income_exchange_rate_needs_evidence(item.get("exchange_rate"))
        for item in items
    )
    if item_rate_gap:
        return True
    if foreign_income_money_value(raw.get("amount")) is not None:
        if foreign_income_items_have_exchange_rate_support(items):
            return foreign_income_exchange_rate_invalid_when_present(raw.get("exchange_rate"))
        return foreign_income_exchange_rate_needs_evidence(raw.get("exchange_rate"))
    return False


def foreign_income_items_have_exchange_rate_support(items: List[Dict[str, Any]]) -> bool:
    return bool(items) and all(
        foreign_income_money_value(item.get("amount")) is None
        or not foreign_income_exchange_rate_needs_evidence(item.get("exchange_rate"))
        for item in items
    )


def foreign_income_exchange_rate_invalid_when_present(value: Any) -> bool:
    if is_missing(value) or isinstance(value, bool) or contains_unknown(value):
        return False
    rate = foreign_income_money_value(value)
    return rate is None or rate <= 0


def foreign_income_exchange_rate_needs_evidence(value: Any) -> bool:
    if is_missing(value) or isinstance(value, bool) or contains_unknown(value):
        return True
    rate = foreign_income_money_value(value)
    return rate is None or rate <= 0


def foreign_income_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    return contains_unknown(value) or foreign_income_amount_malformed(value)


def foreign_income_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return False


def foreign_income_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def foreign_income_amount_value(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str, alias: str = "") -> Optional[float]:
    item_total = foreign_income_item_amount_total(items, key, alias)
    if item_total is not None:
        return item_total
    amount = foreign_income_money_value(raw.get(key))
    if amount is not None:
        return amount
    return foreign_income_money_value(raw.get(alias)) if alias else None


def foreign_income_item_amount_total(items: List[Dict[str, Any]], key: str, alias: str = "") -> Optional[float]:
    amounts = []
    for item in items:
        amount = foreign_income_money_value(item.get(key))
        if amount is None and alias:
            amount = foreign_income_money_value(item.get(alias))
        if amount is not None:
            amounts.append(amount)
    if not amounts:
        return None
    return round(sum(amounts), 6)


def foreign_income_summary_exchange_rate_text(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    direct = foreign_income_money_value(raw.get("exchange_rate"))
    if direct is not None:
        return foreign_income_rate_text(direct)
    rates = {
        foreign_income_rate_text(rate)
        for item in items
        if (rate := foreign_income_money_value(item.get("exchange_rate"))) is not None
    }
    if len(rates) == 1:
        return next(iter(rates))
    if len(rates) > 1:
        return "item-specific"
    return "unknown"


def foreign_income_country_text(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    direct = display_value(raw.get("country"))
    if direct:
        return direct
    countries = [display_value(item.get("country")) for item in items if display_value(item.get("country"))]
    return ", ".join(countries) if countries else "unknown"


def foreign_income_field_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
    direct = display_value(raw.get(key))
    if direct:
        return direct
    values = [display_value(item.get(key)) for item in items if display_value(item.get(key))]
    return ", ".join(values) if values else "unknown"


def foreign_income_claim_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
    if key in raw:
        return display_value(raw.get(key)) or "unknown"
    values = [display_value(item.get(key)) for item in items if key in item]
    return ", ".join(values) if values else "unknown"


def foreign_income_items_text(items: List[Dict[str, Any]]) -> str:
    details: List[str] = []
    for idx, item in enumerate(items, start=1):
        label = display_value(item.get("country")) or display_value(item.get("payer")) or f"item {idx}"
        tax_paid = item.get("foreign_tax_paid")
        if is_missing(tax_paid):
            tax_paid = item.get("tax_paid")
        details.append(
            f"{label}: type {display_value(item.get('income_type')) or 'unknown'}, "
            f"amount {money_text(foreign_income_money_value(item.get('amount')))}, "
            f"foreign tax paid {money_text(foreign_income_money_value(tax_paid))}, "
            f"exchange rate {foreign_income_rate_text(foreign_income_money_value(item.get('exchange_rate')))}"
        )
    return " | ".join(details)


def foreign_income_rate_text(value: Optional[float]) -> str:
    return "unknown" if value is None else f"{value:.6g}"


def foreign_income_tab_text(
    statement_evidence: bool,
    amount_evidence: bool,
    residency_evidence: bool,
    tax_paid_evidence: bool,
) -> str:
    evidence = []
    if statement_evidence:
        evidence.append("statement evidence")
    if amount_evidence:
        evidence.append("numeric amount or exchange-rate evidence")
    if residency_evidence:
        evidence.append("residency or temporary-resident evidence")
    if tax_paid_evidence:
        evidence.append("foreign tax paid evidence")
    if evidence:
        return f"Foreign income needs {', '.join(evidence)} before accountant review."
    return "Foreign income needs source-backed accountant review."


def ess_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("ess")
    fields = {
        "employer": answers.get("ess_employer"),
        "scheme": answers.get("ess_scheme"),
        "provider": answers.get("ess_provider"),
        "statement": answers.get("ess_statement"),
        "taxed_upfront_discount": answers.get("ess_taxed_upfront_discount"),
        "deferred_discount": answers.get("ess_deferred_discount"),
        "foreign_source_discount": answers.get("ess_foreign_source_discount"),
        "tfn_amount_withheld": answers.get("ess_tfn_amount_withheld"),
        "items": answers.get("ess_items"),
    }
    flat_values = {key: value for key, value in fields.items() if has_meaningful_value(value)}
    if not isinstance(raw, dict):
        return flat_values
    if not has_meaningful_value(raw):
        return flat_values
    merged = dict(flat_values)
    for key, value in raw.items():
        if has_meaningful_ess_override(key, value):
            merged[key] = value
        elif key not in merged and has_explicit_ess_evidence_gap(key, value):
            merged[key] = value
    return merged


def ess_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_ess_inputs(raw):
        return []
    if not isinstance(raw, dict):
        return []
    items = ess_item_values(raw.get("items"))
    taxed_upfront = ess_amount_value(raw, items, "taxed_upfront_discount")
    deferred = ess_amount_value(raw, items, "deferred_discount")
    foreign_source = ess_amount_value(raw, items, "foreign_source_discount")
    tfn_withheld = ess_amount_value(raw, items, "tfn_amount_withheld")
    statement = raw.get("statement")
    if not has_meaningful_value(statement):
        statement = next((item.get("statement") for item in items if has_meaningful_value(item.get("statement"))), None)
    statement_evidence = ess_statement_missing(statement) or ess_items_need_statement_evidence(items)
    amount_conflict = ess_amount_conflict(raw, items)
    amount_evidence = ess_amounts_need_evidence(raw, items)
    status = "Evidence" if statement_evidence or amount_conflict or amount_evidence else "Accountant review"
    item_text = ess_items_text(items)
    employer = ess_employer_text(raw, items)
    answer = (
        f"Employer {employer}; "
        f"taxed-upfront discount {money_text(taxed_upfront)}; "
        f"deferred discount {money_text(deferred)}; "
        f"foreign-source discount {money_text(foreign_source)}; "
        f"TFN amount withheld {money_text(tfn_withheld)}"
    )
    if item_text:
        answer = f"{answer}; items {item_text}"
    tab_text = ess_tab_text(statement_evidence, amount_conflict, amount_evidence)
    return [
        guide_row(
            "ESS",
            "Employee share schemes",
            "ESS statement and discount workflow",
            answer,
            "ESS discounts need the ESS statement, deferred taxing-point timing, foreign-source split, and label mapping reviewed before manual copy.",
            status,
            [ATO_ESS_SOURCE, ATO_ESS_STATEMENT_SOURCE],
            tab_text=tab_text,
        )
    ]


def ess_item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict) and has_meaningful_ess_item(item)]


def has_meaningful_ess_item(item: Dict[str, Any]) -> bool:
    if any(has_meaningful_ess_signal(key, item.get(key)) for key in ESS_ITEM_SIGNAL_FIELDS):
        return True
    return any(ess_amount_needs_evidence(item.get(key)) for key in ESS_AMOUNT_FIELDS)


def has_meaningful_ess_signal(key: str, value: Any) -> bool:
    if key in ESS_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_ess_value(value)


def has_meaningful_ess_override(key: str, value: Any) -> bool:
    if key == "items":
        return bool(ess_item_values(value))
    if not has_meaningful_value(value) or contains_unknown(value):
        return False
    if key in ESS_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    return True


def has_explicit_ess_evidence_gap(key: str, value: Any) -> bool:
    if key not in ("statement", *ESS_AMOUNT_FIELDS):
        return False
    if key in ESS_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    return has_meaningful_value(value) and contains_unknown(value)


def ess_amount_value(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> Optional[float]:
    item_total = ess_item_amount_total(items, key)
    if item_total is not None:
        return item_total
    return ess_money_value(raw.get(key))


def ess_item_amount_total(items: List[Dict[str, Any]], key: str) -> Optional[float]:
    item_amounts = [ess_money_value(item.get(key)) for item in items]
    real_amounts = [amount for amount in item_amounts if amount is not None]
    if not real_amounts:
        return None
    return round(sum(real_amounts), 2)


def ess_amount_conflict(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    for key in ESS_AMOUNT_FIELDS:
        top_level = ess_money_value(raw.get(key))
        item_total = ess_item_amount_total(items, key)
        if top_level is not None and item_total is not None and top_level != item_total:
            return True
    return False


def ess_amounts_need_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if any(ess_amount_needs_evidence(raw.get(key)) for key in ESS_AMOUNT_FIELDS):
        return True
    return any(ess_amount_needs_evidence(item.get(key)) for item in items for key in ESS_AMOUNT_FIELDS)


def ess_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    return contains_unknown(value) or ess_amount_malformed(value)


def ess_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return False


def ess_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def ess_tab_text(statement_evidence: bool, amount_conflict: bool, amount_evidence: bool) -> str:
    if amount_conflict and statement_evidence:
        return "ESS discounts need ESS statement evidence and corrected amount totals before accountant review."
    if amount_conflict:
        return "ESS top-level and item amounts conflict; correct ESS amount totals before accountant review."
    if amount_evidence and statement_evidence:
        return "ESS discounts need ESS statement evidence and numeric amount evidence before accountant review."
    if amount_evidence:
        return "ESS amount fields need numeric evidence before accountant review."
    if statement_evidence:
        return "ESS discounts need ESS statement evidence before accountant review."
    return "ESS discounts need statement-backed accountant review."


def ess_statement_missing(statement: Any) -> bool:
    if isinstance(statement, bool):
        return not statement
    if is_missing(statement) or contains_unknown(statement):
        return True
    if ess_statement_declines_workflow(statement):
        return True
    lowered = text(statement).strip().lower()
    if lowered in {"no", "n", "false", "not held", "not available", "none"}:
        return True
    return any(phrase in lowered for phrase in ESS_STATEMENT_MISSING_PHRASES)


def ess_items_need_statement_evidence(items: List[Dict[str, Any]]) -> bool:
    return any(ess_statement_missing(item.get("statement")) for item in items)


def ess_items_text(items: List[Dict[str, Any]]) -> str:
    details: List[str] = []
    for idx, item in enumerate(items, start=1):
        name = ess_label_text(item) or f"item {idx}"
        details.append(
            f"{name}: taxed-upfront {money_text(ess_money_value(item.get('taxed_upfront_discount')))}, "
            f"deferred {money_text(ess_money_value(item.get('deferred_discount')))}, "
            f"foreign-source {money_text(ess_money_value(item.get('foreign_source_discount')))}, "
            f"TFN withheld {money_text(ess_money_value(item.get('tfn_amount_withheld')))}"
        )
    return " | ".join(details)


def ess_employer_text(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    direct = ess_label_text(raw)
    if direct:
        return direct
    for item in items:
        name = ess_label_text(item)
        if name:
            return name
    return "unknown"


def ess_label_text(raw: Dict[str, Any]) -> str:
    return display_value(raw.get("employer")) or display_value(raw.get("scheme")) or display_value(raw.get("provider"))


def has_ess_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if ess_item_values(raw.get("items")):
        return True
    if has_meaningful_ess_statement(raw.get("statement")):
        return True
    if any(
        has_explicit_ess_evidence_gap(key, raw.get(key))
        for key in ("statement", *ESS_AMOUNT_FIELDS)
    ):
        return True
    return any(has_meaningful_ess_signal(key, raw.get(key)) for key in ESS_ITEM_SIGNAL_FIELDS)


def has_meaningful_ess_statement(value: Any) -> bool:
    if not has_meaningful_value(value) or contains_unknown(value):
        return False
    return not ess_statement_declines_workflow(value)


def ess_statement_declines_workflow(statement: Any) -> bool:
    if not isinstance(statement, str):
        return False
    lowered = statement.strip().lower()
    return lowered in ESS_DECLINE_PHRASES


def has_meaningful_ess_value(value: Any) -> bool:
    return has_meaningful_value(value)


def uncommon_income_rows(raw_values: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_values, list):
        return []
    rows: List[Dict[str, Any]] = []
    for idx, value in enumerate(raw_values, start=1):
        if not has_meaningful_value(value):
            continue
        rows.append(
            guide_row(
                f"UNC-{idx}",
                "Supplementary / uncommon income",
                "Uncommon income trigger",
                display_value(value),
                "V1 detects this area and routes it to source-backed accountant review instead of full handling.",
                "Accountant review",
                ATO_INDIVIDUAL_SOURCE,
                tab_text="Uncommon income needs later workflow or accountant review.",
            )
        )
    return rows


def guide_row(
    number: Any,
    area: Any,
    question: Any,
    answer: Any,
    why: Any,
    status: Any,
    source: Any,
    tab_text: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "number": number,
        "ato_area": area,
        "question": question,
        "answer": answer,
        "why_included": why,
        "status": status,
        "source_urls": source if isinstance(source, list) else [source],
        "checked_at": generation_checked_at(),
        "tab_text": tab_text or why,
    }


def generation_checked_at() -> str:
    return date.today().isoformat()


def parse_iso_date(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def parse_dates(raw_values: Any) -> Optional[Set[date]]:
    if contains_unknown(raw_values):
        return None
    if not isinstance(raw_values, list):
        return None
    dates: Set[date] = set()
    for value in raw_values:
        try:
            dates.add(date.fromisoformat(str(value)))
        except ValueError:
            return None
    return dates


def money_value(value: Any, *, unknown_as_missing: bool = False) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if contains_unknown(value):
        if unknown_as_missing:
            return None
        raise ValueError(f"unknown money value: {value}")
    try:
        amount = float(str(value).replace("$", "").replace(",", ""))
    except ValueError:
        raise ValueError(f"invalid money value: {value}") from None
    if not math.isfinite(amount):
        raise ValueError(f"non-finite money value: {value}")
    return amount


def money(value: Any) -> float:
    amount = money_value(value)
    return 0.0 if amount is None else amount


def money_text(value: Optional[float]) -> str:
    return "unknown" if value is None else f"{value:.2f}"


def percent_text(value: Optional[float]) -> str:
    return "unknown" if value is None else f"{value:.0f}%"


def is_unknown(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() in EXACT_UNKNOWN_PHRASES


def contains_unknown(value: Any) -> bool:
    if is_unknown(value):
        return True
    if isinstance(value, str):
        lowered = value.strip().lower()
        return any(phrase in lowered for phrase in EMBEDDED_UNKNOWN_PHRASES)
    if isinstance(value, list):
        return any(contains_unknown(item) for item in value)
    if isinstance(value, dict):
        return any(contains_unknown(item) for item in value.values())
    return False


def text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(display_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return text(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="./scripts/taxmate intake", description="TaxMate Australia intake commands.")
    sub = parser.add_subparsers(dest="command")
    individual = sub.add_parser("individual", help="Build individual return + ABN/BAS prep HTML.")
    individual.add_argument("--answers", default="", help="Answers JSON. Omit for sample data.")
    individual.add_argument("--output", required=True, help="HTML output path.")
    individual.add_argument("--allow-missing", action="store_true", help="Render with missing required answers as evidence rows.")
    sample = sub.add_parser("sample-json", help="Write sample individual answers JSON.")
    sample.add_argument("--output", required=True, help="JSON output path.")
    issues = sub.add_parser("omitted-issues-json", help="Print omitted-scope GitHub issue specs.")
    issues.set_defaults(issues=True)
    return parser


def write_text(path: str, text_value: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text_value, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "sample-json":
        write_text(args.output, json.dumps(sample_answers(), indent=2) + "\n")
        return 0
    if args.command == "omitted-issues-json":
        print(json.dumps(omitted_scope_issues(), indent=2))
        return 0
    if args.command == "individual":
        try:
            answers = sample_answers() if not args.answers else read_json(args.answers)
            missing = missing_required_answers(answers)
            if missing and not args.allow_missing:
                for spec in missing:
                    print(f"missing required answer: {spec.key} - {spec.prompt}", file=sys.stderr)
                return 1
            payload = answers_to_pack_payload(answers)
            data = taxmate_taxpack.load_guide_payload(payload)
            write_text(args.output, taxmate_taxpack.render_html(data))
            return 0
        except Exception as exc:
            print(exc, file=sys.stderr)
            return 1
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
