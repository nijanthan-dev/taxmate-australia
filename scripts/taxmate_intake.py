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
)
REVIEWABLE_COMPLEX_FIELDS = ("employee_deductions", "wfh_work_pattern", "wfh_records", "asset_items", "ess_items")
EXACT_UNKNOWN_PHRASES = frozenset({"unknown", "missing", "not sure", "unsure"})
EMBEDDED_UNKNOWN_PHRASES = (
    "not confirmed",
    "unconfirmed",
    "unknown",
    "missing",
    "not sure",
    "unsure",
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
OMITTED_SCOPE_ITEMS = [
    ("feat: add company return intake", "Company/entity return prep, company tax labels, directors, dividends, franking, retained earnings."),
    ("feat: add trust return intake", "Trust return prep, beneficiary distributions, trustee-assessed income, family trust items."),
    ("feat: add partnership return intake", "Partnership return prep, partner shares, partnership income/loss allocations."),
    ("feat: add full supplementary return coverage", "Full supplementary labels beyond common V1 gates."),
    ("feat: add rental property worksheet", "Rental income, interest, repairs versus capital, private use, depreciation, net rental loss."),
    ("feat: add full CGT schedule workflow", "CGT events, cost base, discounts, carried losses, main residence, small business concessions."),
    ("feat: add crypto CGT workflow", "Buys, sells, swaps, staking, rewards, transfers, wallet records, and cost-base tracking."),
    ("feat: add foreign income workflow", "Foreign employment, pensions, tax offsets, and residency-specific review."),
    ("feat: add ESS workflow", "Employee share scheme labels, taxed upfront and deferral, and foreign source discounts."),
    ("feat: add ETP and lump sum workflow", "ETP, lump sum in arrears, and super lump sum or stream detailed handling."),
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
        QuestionSpec("ess_statement", "ESS", "ESS statement held?", "Employee share schemes", False),
        QuestionSpec("ess_taxed_upfront_discount", "ESS", "ESS taxed-upfront discount", "Employee share schemes", False),
        QuestionSpec("ess_deferred_discount", "ESS", "ESS deferred discount", "Employee share schemes", False),
        QuestionSpec("ess_foreign_source_discount", "ESS", "ESS foreign-source discount", "Employee share schemes", False),
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
        return value
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
        if spec.required or has_meaningful_value(value):
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


def base_item_status(key: str, value: Any) -> str:
    if key in REVIEWABLE_ESS_FIELDS:
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
    if is_missing(enriched.get("records")) and not is_missing(answers.get("wfh_records")):
        enriched["records"] = answers.get("wfh_records")
    if is_missing(enriched.get("state")) and not is_missing(answers.get("state")):
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
    if isinstance(raw_assets, list):
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


def ess_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("ess")
    if isinstance(raw, dict):
        return raw
    fields = {
        "statement": answers.get("ess_statement"),
        "taxed_upfront_discount": answers.get("ess_taxed_upfront_discount"),
        "deferred_discount": answers.get("ess_deferred_discount"),
        "foreign_source_discount": answers.get("ess_foreign_source_discount"),
        "items": answers.get("ess_items"),
    }
    return {key: value for key, value in fields.items() if not is_missing(value)}


def ess_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_ess_inputs(raw):
        return []
    if not isinstance(raw, dict):
        return []
    taxed_upfront = money_value(raw.get("taxed_upfront_discount"), unknown_as_missing=True)
    deferred = money_value(raw.get("deferred_discount"), unknown_as_missing=True)
    foreign_source = money_value(raw.get("foreign_source_discount"), unknown_as_missing=True)
    tfn_withheld = money_value(raw.get("tfn_amount_withheld"), unknown_as_missing=True)
    statement = raw.get("statement")
    status = "Evidence" if is_missing(statement) or contains_unknown(statement) else "Accountant review"
    answer = (
        f"Employer {display_value(raw.get('employer')) or 'unknown'}; "
        f"taxed-upfront discount {money_text(taxed_upfront)}; "
        f"deferred discount {money_text(deferred)}; "
        f"foreign-source discount {money_text(foreign_source)}; "
        f"TFN amount withheld {money_text(tfn_withheld)}"
    )
    return [
        guide_row(
            "ESS",
            "Employee share schemes",
            "ESS statement and discount workflow",
            answer,
            "ESS discounts need the ESS statement, deferred taxing-point timing, foreign-source split, and label mapping reviewed before manual copy.",
            status,
            [ATO_ESS_SOURCE, ATO_ESS_STATEMENT_SOURCE],
            tab_text="ESS discounts need statement-backed accountant review.",
        )
    ]


def has_ess_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return any(has_meaningful_ess_value(value) for value in raw.values())


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
