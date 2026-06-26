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


def bas(sales_gst: float, purchase_gst: float, payg_withheld: float, fuel_tax_credit: float, adjustments: float) -> Dict[str, Any]:
    net_gst = round2(sales_gst - purchase_gst + adjustments)
    net_payable = round2(net_gst + payg_withheld - fuel_tax_credit)
    return {
        "tool": titlecase_tool("bas"),
        "income_year": "2025-26",
        "inputs": {
            "gst_collected": sales_gst,
            "gst_credits": purchase_gst,
            "payg_withheld": payg_withheld,
            "fuel_tax_credit": fuel_tax_credit,
            "gst_adjustments": adjustments,
            "amounts_are_gst": True,
            "cash_or_accruals": "user supplied",
        },
        "outputs": {
            "net_gst_payable": net_gst,
            "estimated_bas_total": net_payable,
            "nil_bas": net_payable == 0,
        },
        "assumptions": [
            "Inputs are already separated into GST collected, GST credits, PAYG withheld, fuel tax credits, and adjustments."
        ],
        "review_flags": [
            "Confirm BAS reporting cycle, accounting basis, labels, and whether GST credits have valid tax invoices."
        ],
        "sources": [
            "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas",
            "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/claiming-gst-credits",
        ],
    }


def super_guarantee(ote: float, rate: float) -> Dict[str, Any]:
    if rate == 0:
        rate = SG_RATE_2025_26
    return {
        "tool": titlecase_tool("super"),
        "income_year": "2025-26",
        "inputs": {
            "ordinary_time_earnings": ote,
            "sg_rate_percent": rate,
        },
        "outputs": {
            "minimum_sg": round2(ote * rate / 100),
        },
        "assumptions": [
            "Uses ordinary time earnings supplied by the user; rate defaults to 12% for payments made from 1 July 2025."
        ],
        "review_flags": [
            "Check award/agreement higher rates, OTE classification, quarterly due date, and late-payment SGC exposure."
        ],
        "sources": [
            "https://www.ato.gov.au/businesses-and-organisations/super-for-employers/paying-super-contributions/how-much-super-to-pay",
        ],
    }


def fbt(taxable_value: float, benefit_type: str) -> Dict[str, Any]:
    if benefit_type.lower() in {"type1", "type-1", "1"}:
        gross_up = FBT_TYPE_1_GROSS_UP
        benefit_type = "type1"
    else:
        gross_up = FBT_TYPE_2_GROSS_UP
        benefit_type = "type2"

    grossed_up = round2(taxable_value * gross_up)
    return {
        "tool": titlecase_tool("fbt"),
        "income_year": "2025-26",
        "inputs": {
            "taxable_value": taxable_value,
            "benefit_type": benefit_type,
            "gross_up_rate": gross_up,
            "fbt_rate": FBT_RATE_2025_26,
            "fbt_year_basis": "year ending 31 March 2026",
        },
        "outputs": {
            "grossed_up_taxable_value": grossed_up,
            "estimated_fbt": round2(grossed_up * FBT_RATE_2025_26 / 100),
        },
        "assumptions": ["Taxable value has already been worked out under the relevant FBT benefit rules."],
        "review_flags": [
            "Does not determine car statutory formula, operating cost method, exemptions, employee contributions, or reportable fringe benefit treatment."
        ],
        "sources": [
            "https://www.ato.gov.au/tax-rates-and-codes/fringe-benefits-tax-rates-and-thresholds",
            "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax",
        ],
    }


def cgt(proceeds: float, cost_base: float, capital_losses: float, acquired: str, disposed: str, discount: bool) -> Dict[str, Any]:
    raw_gain = round2(proceeds - cost_base)
    net_before = round2(raw_gain - capital_losses)
    held_months = months_held(acquired, disposed)
    discount_allowed = discount and held_months >= 12 and net_before > 0
    discount_amount = round2(net_before * 0.5) if discount_allowed else 0.0
    net = round2(net_before - discount_amount)
    return {
        "tool": titlecase_tool("cgt"),
        "income_year": "2025-26",
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


def payg_estimate(gross_pay: float, periods_per_year: int, tax_free_threshold: bool, medicare: bool) -> Dict[str, Any]:
    if periods_per_year <= 0:
        periods_per_year = 52
    annual = gross_pay * float(periods_per_year)
    tax = _payg_tax(annual)
    if medicare:
        tax += annual * MEDICARE_LEVY_DEFAULT / 100
    if not tax_free_threshold and annual <= 18200:
        tax = annual * 0.16
    withhold = round2(tax / float(periods_per_year))
    return {
        "tool": titlecase_tool("payg"),
        "income_year": "2025-26",
        "inputs": {
            "gross_pay": gross_pay,
            "periods_per_year": periods_per_year,
            "annualised_pay": round2(annual),
            "tax_free_threshold": tax_free_threshold,
            "medicare_levy_added": medicare,
        },
        "outputs": {
            "estimated_withholding_per_period": withhold,
            "estimated_annual_tax": round2(tax),
        },
        "assumptions": ["Annualises regular pay and applies 2025-26 resident tax rates; this is not a substitute for ATO PAYG withholding tax tables."],
        "review_flags": [
            "Use official ATO withholding tables for payroll, HELP/STSL, Medicare variations, no-TFN cases, bonuses, commissions, termination payments, allowances, foreign residents, and rounding."
        ],
        "sources": [
            "https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents",
            "https://www.ato.gov.au/tax-rates-and-codes/tax-tables-overview",
            "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding",
        ],
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


def stamp_duty_router(state: str, value: float) -> Dict[str, Any]:
    state = (state or "").strip().upper()
    sources = state_revenue_sources()
    source = sources.get(state, "unknown state; use the relevant state or territory revenue office")
    return {
        "tool": titlecase_tool("stamp-duty"),
        "income_year": "2025-26",
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
    except Exception:
        return 0
    if d < a:
        return 0
    return int((d - a).days / 30.4375)


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

    if tool == "bas":
        parser.add_argument("tool")
        parser.add_argument("--gst-collected", type=finite_float, default=0)
        parser.add_argument("--gst-credits", type=finite_float, default=0)
        parser.add_argument("--payg-withheld", type=finite_float, default=0)
        parser.add_argument("--fuel-tax-credit", type=finite_float, default=0)
        parser.add_argument("--adjustments", type=finite_float, default=0)
        args = parser.parse_args(argv)
        result = bas(args.gst_collected, args.gst_credits, args.payg_withheld, args.fuel_tax_credit, args.adjustments)
    elif tool == "super":
        parser.add_argument("tool")
        parser.add_argument("--ote", type=finite_float, default=0)
        parser.add_argument("--rate", type=finite_float, default=0)
        args = parser.parse_args(argv)
        result = super_guarantee(args.ote, args.rate)
    elif tool == "fbt":
        parser.add_argument("tool")
        parser.add_argument("--taxable-value", type=finite_float, default=0)
        parser.add_argument("--type", default="type2")
        args = parser.parse_args(argv)
        result = fbt(args.taxable_value, args.type)
    elif tool == "cgt":
        parser.add_argument("tool")
        parser.add_argument("--proceeds", type=finite_float, default=0)
        parser.add_argument("--cost-base", type=finite_float, default=0)
        parser.add_argument("--capital-losses", type=finite_float, default=0)
        parser.add_argument("--acquired", default="")
        parser.add_argument("--disposed", default="")
        parser.add_argument("--discount", action="store_true")
        args = parser.parse_args(argv)
        result = cgt(args.proceeds, args.cost_base, args.capital_losses, args.acquired, args.disposed, args.discount)
    elif tool == "payg":
        parser.add_argument("tool")
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
        args = parser.parse_args(argv)
        result = payg_estimate(args.gross_pay, args.periods, args.tax_free_threshold, args.medicare)
    else:  # stamp-duty
        parser.add_argument("tool")
        parser.add_argument("--state", default="")
        parser.add_argument("--value", type=finite_float, default=0)
        args = parser.parse_args(argv)
        result = stamp_duty_router(args.state, args.value)

    write_json(result, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
