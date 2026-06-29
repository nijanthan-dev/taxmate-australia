#!/usr/bin/env python3
"""TaxMate Australia calculator command implementation (Python replacement)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Any, Dict, List, Optional

SUPPORTED_INCOME_YEAR = "2025-26"
SUPPORTED_FBT_YEAR = "2026"
SG_RATE_2025_26 = 12.0
FBT_RATE_2025_26 = 47.0
FBT_TYPE_1_GROSS_UP = 2.0802
FBT_TYPE_2_GROSS_UP = 1.8868
MEDICARE_LEVY_DEFAULT = 2.0


def validate_tool(tool: str) -> None:
    if tool not in {"bas", "super", "fbt", "cgt", "payg", "stamp-duty"}:
        raise ValueError(f"unknown calculator {tool!r}")


def write_json(result: Dict[str, Any], out) -> None:
    json.dump(result, out, indent=2, allow_nan=False)
    out.write("\n")


def finite_float(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid number: {value!r}") from exc
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError(f"invalid finite number: {value!r}")
    return number


def parse_bool_arg(value: str) -> bool:
    v = (value or "").strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def titlecase_tool(tool: str) -> str:
    mapping = {
        "bas": "bas",
        "super": "super",
        "fbt": "fbt",
        "cgt": "cgt",
        "payg": "payg-estimate",
        "stamp-duty": "stamp-duty-source-router",
    }
    return mapping.get(tool, tool)


def round2(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def supported_income_year(value: Any) -> bool:
    return str(value or SUPPORTED_INCOME_YEAR).strip() == SUPPORTED_INCOME_YEAR


def supported_fbt_year(value: Any) -> bool:
    year = str(value or SUPPORTED_FBT_YEAR).strip().lower()
    return year in {SUPPORTED_FBT_YEAR, "2025-26", "year ending 31 march 2026", "2026-03-31"}


def not_calculated_result(
    tool: str,
    temporal_label: str,
    inputs: Dict[str, Any],
    reason: str,
    sources: List[str],
) -> Dict[str, Any]:
    return {
        "tool": titlecase_tool(tool),
        "income_year": temporal_label,
        "inputs": inputs,
        "outputs": {
            "calculation": "not_calculated",
            "reason": reason,
        },
        "assumptions": [],
        "review_flags": [reason],
        "sources": sources,
    }


def normalize_fbt_type(benefit_type: str) -> str:
    if benefit_type.lower() in {"type1", "type-1", "1"}:
        return "type1"
    return "type2"


def bas(
    sales_gst: float,
    purchase_gst: float,
    payg_withheld: float,
    fuel_tax_credit: float,
    adjustments: float,
    income_year: str = SUPPORTED_INCOME_YEAR,
) -> Dict[str, Any]:
    inputs = {
        "gst_collected": sales_gst,
        "gst_credits": purchase_gst,
        "payg_withheld": payg_withheld,
        "fuel_tax_credit": fuel_tax_credit,
        "gst_adjustments": adjustments,
        "amounts_are_gst": True,
        "cash_or_accruals": "user supplied",
    }
    sources = [
        "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas",
        "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/claiming-gst-credits",
    ]
    if not supported_income_year(income_year):
        return not_calculated_result(
            "bas",
            income_year,
            inputs,
            "BAS calculator supports 2025-26 only; use accountant review or current ATO BAS instructions for other periods.",
            sources,
        )
    net_gst = round2(sales_gst - purchase_gst + adjustments)
    net_payable = round2(net_gst + payg_withheld - fuel_tax_credit)
    nil_activity = (
        sales_gst == 0
        and purchase_gst == 0
        and payg_withheld == 0
        and fuel_tax_credit == 0
        and adjustments == 0
    )
    return {
        "tool": titlecase_tool("bas"),
        "income_year": income_year,
        "inputs": inputs,
        "outputs": {
            "net_gst_payable": net_gst,
            "estimated_bas_total": net_payable,
            "nil_bas": nil_activity,
        },
        "assumptions": [
            "Inputs are already separated into GST collected, GST credits, PAYG withheld, fuel tax credits, and adjustments."
        ],
        "review_flags": [
            "Confirm BAS reporting cycle, accounting basis, labels, and whether GST credits have valid tax invoices."
        ],
        "sources": sources,
    }


def super_guarantee(ote: float, rate: float, income_year: str = SUPPORTED_INCOME_YEAR) -> Dict[str, Any]:
    sources = [
        "https://www.ato.gov.au/businesses-and-organisations/super-for-employers/paying-super-contributions/how-much-super-to-pay",
    ]
    inputs = {
        "ordinary_time_earnings": ote,
        "sg_rate_percent": rate,
    }
    if not supported_income_year(income_year):
        return not_calculated_result(
            "super",
            income_year,
            inputs,
            "Super guarantee calculator supports 2025-26 only; confirm the payment date and rate before calculating.",
            sources,
        )
    if rate == 0:
        rate = SG_RATE_2025_26
        inputs["sg_rate_percent"] = rate
    return {
        "tool": titlecase_tool("super"),
        "income_year": income_year,
        "inputs": inputs,
        "outputs": {
            "minimum_sg": round2(ote * rate / 100),
        },
        "assumptions": [
            "Uses ordinary time earnings supplied by the user; rate defaults to 12% for payments made from 1 July 2025."
        ],
        "review_flags": [
            "Check award/agreement higher rates, OTE classification, quarterly due date, and late-payment SGC exposure."
        ],
        "sources": sources,
    }


def fbt(taxable_value: float, benefit_type: str, fbt_year: str = SUPPORTED_FBT_YEAR) -> Dict[str, Any]:
    benefit_type = normalize_fbt_type(benefit_type)
    sources = [
        "https://www.ato.gov.au/tax-rates-and-codes/fringe-benefits-tax-rates-and-thresholds",
        "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax",
    ]
    if not supported_fbt_year(fbt_year):
        return not_calculated_result(
            "fbt",
            f"FBT year {fbt_year}",
            {
                "taxable_value": taxable_value,
                "benefit_type": benefit_type,
            },
            "FBT calculator supports the year ending 31 March 2026 only; confirm current FBT rates before calculating.",
            sources,
        )
    if benefit_type == "type1":
        gross_up = FBT_TYPE_1_GROSS_UP
    else:
        gross_up = FBT_TYPE_2_GROSS_UP

    inputs = {
        "taxable_value": taxable_value,
        "benefit_type": benefit_type,
        "gross_up_rate": gross_up,
        "fbt_rate": FBT_RATE_2025_26,
        "fbt_year_basis": "year ending 31 March 2026",
    }
    grossed_up = round2(taxable_value * gross_up)
    return {
        "tool": titlecase_tool("fbt"),
        "income_year": "2025-26",
        "inputs": inputs,
        "outputs": {
            "grossed_up_taxable_value": grossed_up,
            "estimated_fbt": round2(grossed_up * FBT_RATE_2025_26 / 100),
        },
        "assumptions": ["Taxable value has already been worked out under the relevant FBT benefit rules."],
        "review_flags": [
            "Does not determine car statutory formula, operating cost method, exemptions, employee contributions, or reportable fringe benefit treatment."
        ],
        "sources": sources,
    }


def cgt(
    proceeds: float,
    cost_base: float,
    capital_losses: float,
    acquired: str,
    disposed: str,
    discount: bool,
    income_year: str = SUPPORTED_INCOME_YEAR,
) -> Dict[str, Any]:
    raw_gain = round2(proceeds - cost_base)
    net_before = round2(raw_gain - capital_losses)
    held_months = months_held(acquired, disposed)
    discount_allowed = discount and held_months >= 12 and net_before > 0
    discount_amount = round2(net_before * 0.5) if discount_allowed else 0.0
    net = round2(net_before - discount_amount)
    return {
        "tool": titlecase_tool("cgt"),
        "income_year": income_year,
        "inputs": {
            "capital_proceeds": proceeds,
            "cost_base": cost_base,
            "capital_losses": capital_losses,
            "acquired": acquired,
            "disposed": disposed,
            "discount_claimed": discount,
        },
        "outputs": {
            "gross_capital_gain": raw_gain,
            "net_before_discount": net_before,
            "held_months": held_months,
            "discount_allowed": discount_allowed,
            "discount_amount": discount_amount,
            "net_capital_gain_est": net,
        },
        "assumptions": ["Cost base, proceeds, and capital losses are user-supplied and already include relevant incidental amounts."],
        "review_flags": [
            "Check asset type, main residence exemption, small business concessions, rollovers, foreign-resident rules, AMIT/ETF cost-base adjustments, and carried-forward losses."
        ],
        "sources": [
            "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt",
            "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount",
        ],
    }


def _payg_tax(annual: float) -> float:
    if annual <= 18200:
        return 0.0
    if annual <= 45000:
        return (annual - 18200) * 0.16
    if annual <= 135000:
        return 4288 + (annual - 45000) * 0.30
    if annual <= 190000:
        return 31288 + (annual - 135000) * 0.37
    return 51638 + (annual - 190000) * 0.45


def payg_estimate(
    gross_pay: float,
    periods_per_year: int,
    tax_free_threshold: bool,
    medicare: bool,
    income_year: str = SUPPORTED_INCOME_YEAR,
) -> Dict[str, Any]:
    if periods_per_year <= 0:
        periods_per_year = 52
    annual = gross_pay * float(periods_per_year)
    inputs = {
        "gross_pay": gross_pay,
        "periods_per_year": periods_per_year,
        "annualised_pay": round2(annual),
        "tax_free_threshold": tax_free_threshold,
        "medicare_levy_added": medicare,
    }
    sources = [
        "https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents",
        "https://www.ato.gov.au/tax-rates-and-codes/tax-tables-overview",
        "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding",
    ]
    if not supported_income_year(income_year):
        return not_calculated_result(
            "payg",
            income_year,
            inputs,
            "PAYG estimate supports 2025-26 resident rates only; use official ATO withholding tables for other years.",
            sources,
        )
    tax = _payg_tax(annual)
    if medicare:
        tax += annual * MEDICARE_LEVY_DEFAULT / 100
    if not tax_free_threshold and annual <= 18200:
        tax = annual * 0.16
    withhold = round2(tax / float(periods_per_year))
    return {
        "tool": titlecase_tool("payg"),
        "income_year": income_year,
        "inputs": inputs,
        "outputs": {
            "estimated_withholding_per_period": withhold,
            "estimated_annual_tax": round2(tax),
        },
        "assumptions": ["Annualises regular pay and applies 2025-26 resident tax rates; this is not a substitute for ATO PAYG withholding tax tables."],
        "review_flags": [
            "Use official ATO withholding tables for payroll, HELP/STSL, Medicare variations, no-TFN cases, bonuses, commissions, termination payments, allowances, foreign residents, and rounding."
        ],
        "sources": sources,
    }


def state_revenue_sources() -> Dict[str, str]:
    return {
        "ACT": "https://www.revenue.act.gov.au/",
        "NSW": "https://www.revenue.nsw.gov.au/taxes-duties-levies-royalties/transfer-duty",
        "NT": "https://nt.gov.au/property/buying-and-selling-property/stamp-duty",
        "QLD": "https://qro.qld.gov.au/duties/transfer-duty/",
        "SA": "https://www.revenuesa.sa.gov.au/stampduty",
        "TAS": "https://www.sro.tas.gov.au/property-transfer-duties",
        "VIC": "https://www.sro.vic.gov.au/land-transfer-duty",
        "WA": "https://www.wa.gov.au/organisation/department-of-finance/transfer-duty",
    }


def stamp_duty_router(state: str, value: float, income_year: str = SUPPORTED_INCOME_YEAR) -> Dict[str, Any]:
    state = (state or "").strip().upper()
    sources = state_revenue_sources()
    source = sources.get(state, "unknown state; use the relevant state or territory revenue office")
    return {
        "tool": titlecase_tool("stamp-duty"),
        "income_year": income_year,
        "inputs": {
            "state": state,
            "dutiable_value": value,
        },
        "outputs": {
            "calculation": "not_calculated",
            "reason": "Stamp duty is state or territory based and must be checked live against the relevant revenue-office calculator/rates.",
            "source": source,
        },
        "assumptions": ["TaxMate does not embed state stamp-duty rate tables because concessions and surcharges change frequently."],
        "review_flags": [
            "Check property type, first-home concessions, principal-place-of-residence rules, foreign purchaser surcharge, off-the-plan rules, vacant residential land tax, and transfer date."
        ],
        "sources": [source],
        "official_state_sources": sources,
    }


def months_held(acquired: str, disposed: str) -> int:
    try:
        a = datetime.strptime(acquired, "%Y-%m-%d")
        d = datetime.strptime(disposed, "%Y-%m-%d")
    except ValueError:
        return 0
    if d < a:
        return 0
    months = (d.year - a.year) * 12 + (d.month - a.month)
    if d.day <= a.day:
        months -= 1
    return max(months, 0)


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    usage = "usage: ./scripts/taxmate calc <bas|super|fbt|cgt|payg|stamp-duty> [flags]"
    if not argv:
        print(usage, file=sys.stderr)
        return 2
    if argv[0] in {"-h", "--help"}:
        print(usage)
        return 0

    tool = argv[0]
    if tool not in {"bas", "super", "fbt", "cgt", "payg", "stamp-duty"}:
        print(usage, file=sys.stderr)
        return 2

    try:
        validate_tool(tool)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        print(usage, file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(prog=f"./scripts/taxmate calc {tool}", add_help=True)
    tool_args = argv[1:]

    if tool == "bas":
        parser.add_argument("--income-year", default=SUPPORTED_INCOME_YEAR)
        parser.add_argument("--gst-collected", type=finite_float, default=0)
        parser.add_argument("--gst-credits", type=finite_float, default=0)
        parser.add_argument("--payg-withheld", type=finite_float, default=0)
        parser.add_argument("--fuel-tax-credit", type=finite_float, default=0)
        parser.add_argument("--adjustments", type=finite_float, default=0)
        args = parser.parse_args(tool_args)
        result = bas(
            args.gst_collected,
            args.gst_credits,
            args.payg_withheld,
            args.fuel_tax_credit,
            args.adjustments,
            args.income_year,
        )
    elif tool == "super":
        parser.add_argument("--income-year", default=SUPPORTED_INCOME_YEAR)
        parser.add_argument("--ote", type=finite_float, default=0)
        parser.add_argument("--rate", type=finite_float, default=0)
        args = parser.parse_args(tool_args)
        result = super_guarantee(args.ote, args.rate, args.income_year)
    elif tool == "fbt":
        parser.add_argument("--taxable-value", type=finite_float, default=0)
        parser.add_argument("--type", default="type2")
        parser.add_argument("--fbt-year", default=SUPPORTED_FBT_YEAR)
        args = parser.parse_args(tool_args)
        result = fbt(args.taxable_value, args.type, args.fbt_year)
    elif tool == "cgt":
        parser.add_argument("--income-year", default=SUPPORTED_INCOME_YEAR)
        parser.add_argument("--proceeds", type=finite_float, default=0)
        parser.add_argument("--cost-base", type=finite_float, default=0)
        parser.add_argument("--capital-losses", type=finite_float, default=0)
        parser.add_argument("--acquired", default="")
        parser.add_argument("--disposed", default="")
        parser.add_argument("--discount", action="store_true")
        args = parser.parse_args(tool_args)
        result = cgt(
            args.proceeds,
            args.cost_base,
            args.capital_losses,
            args.acquired,
            args.disposed,
            args.discount,
            args.income_year,
        )
    elif tool == "payg":
        parser.add_argument("--income-year", default=SUPPORTED_INCOME_YEAR)
        parser.add_argument("--gross-pay", type=finite_float, default=0)
        parser.add_argument("--periods", type=int, default=52)
        parser.add_argument(
            "--tax-free-threshold",
            nargs="?",
            const=True,
            type=parse_bool_arg,
            default=True,
            metavar="(true|false)",
        )
        parser.add_argument("--medicare", action="store_true")
        args = parser.parse_args(tool_args)
        result = payg_estimate(args.gross_pay, args.periods, args.tax_free_threshold, args.medicare, args.income_year)
    else:  # stamp-duty
        parser.add_argument("--income-year", default=SUPPORTED_INCOME_YEAR)
        parser.add_argument("--state", default="")
        parser.add_argument("--value", type=finite_float, default=0)
        args = parser.parse_args(tool_args)
        result = stamp_duty_router(args.state, args.value, args.income_year)

    write_json(result, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
