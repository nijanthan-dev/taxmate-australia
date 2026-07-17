"""Shared prep-only company, trust, and partnership worksheet routing."""

from __future__ import annotations

import copy
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

import taxmate_entity_routing


COMPANY_INCOME_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/company-tax-return-2026-instructions/"
    "instructions-to-complete-the-company-tax-return-2026/items-6-to-14/6-income"
)
COMPANY_DEDUCTION_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/company-tax-return-2026-instructions/"
    "instructions-to-complete-the-company-tax-return-2026/items-6-to-14/6-expenses"
)
COMPANY_LOSSES_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/"
    "income-and-deductions-for-business/business-losses"
)
COMPANY_CAPITAL_ALLOWANCES_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/"
    "income-and-deductions-for-business/deductions/"
    "deductions-for-depreciating-assets-and-capital-expenses"
)
COMPANY_DIVIDEND_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/dividend-and-interest-schedule-2026"
)
COMPANY_FRANKING_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/"
    "imputation/in-detail/franking-deficit-tax-offset-calculation-reduction-rule-and-exclusions"
)
COMPANY_DIVISION_7A_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/"
    "private-company-benefits-division-7a-dividends/"
    "managing-division-7a-risks-and-corrective-action"
)
COMPANY_REVIEW_SOURCES = (
    COMPANY_LOSSES_SOURCE,
    COMPANY_CAPITAL_ALLOWANCES_SOURCE,
    COMPANY_DIVIDEND_SOURCE,
    COMPANY_FRANKING_SOURCE,
    COMPANY_DIVISION_7A_SOURCE,
)
PARTNERSHIP_ITEM_5_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions/"
    "instructions-to-complete-the-partnership-tax-return-2026/"
    "income-excluding-foreign-income-item-5/business-income-and-expenses-item-5"
)
PARTNERSHIP_ITEMS_6_TO_9_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions/"
    "instructions-to-complete-the-partnership-tax-return-2026/"
    "income-excluding-foreign-income-items-6-to-9"
)
PARTNERSHIP_ITEMS_10_TO_15_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions/"
    "instructions-to-complete-the-partnership-tax-return-2026/"
    "income-excluding-foreign-income-items-10-to-15"
)
PARTNERSHIP_FOREIGN_INCOME_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions/"
    "instructions-to-complete-the-partnership-tax-return-2026/foreign-income-items-22-to-24"
)
PARTNERSHIP_INCOME_SOURCES = (
    PARTNERSHIP_ITEM_5_SOURCE,
    PARTNERSHIP_ITEMS_6_TO_9_SOURCE,
    PARTNERSHIP_ITEMS_10_TO_15_SOURCE,
    PARTNERSHIP_FOREIGN_INCOME_SOURCE,
)
PARTNERSHIP_ITEMS_16_TO_20_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions/"
    "instructions-to-complete-the-partnership-tax-return-2026/deductions-items-16-to-20"
)
PARTNERSHIP_DEDUCTION_SOURCES = (
    PARTNERSHIP_ITEM_5_SOURCE,
    PARTNERSHIP_ITEMS_16_TO_20_SOURCE,
)
PARTNERSHIP_BUSINESS_SOURCE = (
    "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions/"
    "instructions-to-complete-the-partnership-tax-return-2026/"
    "business-and-professional-items-items-37-to-53"
)
PARTNERSHIP_LOSSES_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/"
    "income-and-deductions-for-business/business-losses"
)
PARTNERSHIP_GST_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/"
    "gst/registering-for-gst"
)
PARTNERSHIP_BAS_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/"
    "business-activity-statements-bas"
)
PARTNERSHIP_PSI_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/"
    "personal-services-income"
)
PARTNERSHIP_REVIEW_SOURCES = (
    PARTNERSHIP_LOSSES_SOURCE, PARTNERSHIP_GST_SOURCE,
    PARTNERSHIP_BAS_SOURCE, PARTNERSHIP_PSI_SOURCE,
)
TRUST_STREAMING_SOURCE = (
    "https://www.ato.gov.au/businesses-and-organisations/trusts/"
    "trust-income-losses-and-capital-gains/"
    "streaming-trust-capital-gains-and-franked-distributions"
)
TRUST_REVIEW_SOURCES = (TRUST_STREAMING_SOURCE,)
DETAILED_SOURCES = tuple(dict.fromkeys((
    COMPANY_INCOME_SOURCE,
    COMPANY_DEDUCTION_SOURCE,
    *COMPANY_REVIEW_SOURCES,
    *PARTNERSHIP_INCOME_SOURCES,
    *PARTNERSHIP_DEDUCTION_SOURCES,
    PARTNERSHIP_BUSINESS_SOURCE,
    *PARTNERSHIP_REVIEW_SOURCES,
    *TRUST_REVIEW_SOURCES,
)))

COLLECTION_ALIASES = {
    "income": ("income_items", "income_categories", "income"),
    "deduction": ("deduction_items", "expense_items", "expense_categories", "expenses"),
}
TOTAL_ALIASES = {
    "income": ("income_total",),
    "deduction": ("deduction_total", "expense_total"),
}
LINE_FIELD_ALIASES = {
    "category": ("category", "kind", "type"),
    "description": ("description", "label", "name"),
    "amount": ("amount", "value", "total"),
    "evidence": ("evidence", "records", "documents", "evidence_files"),
    "gst_bas_interaction": ("gst_bas_interaction", "gst_bas", "bas_overlap"),
    "private_use": ("private_use", "private"),
    "non_deductible": ("non_deductible", "nondeductible"),
    "related_party": ("related_party", "associated_person"),
    "capital_or_depreciation": ("capital_or_depreciation", "capital", "depreciation"),
    "psi": ("psi", "personal_services_income"),
    "business_structure": ("business_structure", "structure"),
    "notes": ("notes", "note"),
    "checked_at": ("checked_at",),
    "status": ("status",),
    "review_status": ("review_status",),
}
PROVENANCE_FIELDS = {"source_url", "source_urls"}
REVIEW_FIELDS = (
    "gst_bas_interaction", "private_use", "non_deductible", "related_party",
    "capital_or_depreciation", "psi", "business_structure", "status", "review_status",
)

COMPANY_INCOME_CATEGORIES = {
    "foreign-resident-withholding", "no-abn-withholding", "sales-goods-services",
    "partnership-distribution", "trust-distribution", "fmis", "interest",
    "rent-leasing-hiring", "fbt-employee-contributions", "government-industry-payments",
    "unrealised-revaluation-gain", "other",
}
COMPANY_DEDUCTION_CATEGORIES = {
    "foreign-resident-withholding-expense", "cost-of-sales", "contractor-commission",
    "superannuation", "bad-debts", "lease-au", "lease-overseas", "rent",
    "interest-au", "interest-overseas", "royalty-au", "royalty-overseas",
    "motor-vehicle", "repairs-maintenance", "unrealised-revaluation-loss", "other",
}
PARTNERSHIP_INCOME_CATEGORIES = {
    "business-income", "no-abn-withholding", "foreign-resident-withholding",
    "government-industry-payments", "partnership-trust-income", "rent", "fmis",
    "interest", "dividends", "other-australian-income", "attributed-foreign-income",
    "other-foreign-source-income", "other",
}
PARTNERSHIP_DEDUCTION_CATEGORIES = {
    "foreign-resident-withholding-expense", "contractor-commission", "superannuation",
    "cost-of-sales", "bad-debts", "lease", "rent", "interest", "royalties",
    "depreciation", "motor-vehicle", "repairs-maintenance",
    "investment-income-deduction", "fmis-deduction", "other",
}
CATEGORIES = {
    ("company", "income"): COMPANY_INCOME_CATEGORIES,
    ("company", "deduction"): COMPANY_DEDUCTION_CATEGORIES,
    ("partnership", "income"): PARTNERSHIP_INCOME_CATEGORIES,
    ("partnership", "deduction"): PARTNERSHIP_DEDUCTION_CATEGORIES,
}
COMPANY_REVIEW_COLLECTIONS = {
    "loss": ("loss_items", "losses", "tax_losses"),
    "loss-continuity": ("loss_continuity", "continuity_tests", "ownership_continuity"),
    "asset": ("asset_items", "depreciating_assets"),
    "asset-pool": ("asset_pools",),
    "depreciation": ("depreciation_items",),
    "capital-allowance": ("capital_allowance_items",),
    "dividend": ("dividend_items", "dividends", "dividends_paid", "dividends_received"),
    "franking-account": (
        "franking_account_items", "franking_account", "franking_items", "franking",
    ),
    "division-7a": (
        "division_7a_items", "division_7a", "division7a", "shareholder_loans",
        "director_loans", "related_party_benefits",
    ),
}
COMPANY_REVIEW_ALIAS_DEFAULTS = {
    "dividend": {
        "dividends_paid": {"dividend_direction": "paid"},
        "dividends_received": {"dividend_direction": "received"},
    },
    "division-7a": {
        "shareholder_loans": {"transaction_type": "loan", "shareholder": True},
        "director_loans": {"transaction_type": "loan", "director": True},
        "related_party_benefits": {
            "transaction_type": "benefit",
            "related_party": True,
        },
    },
}
COMPANY_REVIEW_ALIAS_SCALAR_FIELDS = {
    "division-7a": {
        "shareholder_loans": "loan_amount",
        "director_loans": "loan_amount",
        "related_party_benefits": "payment",
    },
}
COMPANY_REVIEW_SCALAR_FIELDS = {
    "loss": "amount",
    "loss-continuity": "continuity_of_ownership",
    "asset": "asset",
    "asset-pool": "pool_type",
    "depreciation": "amount",
    "capital-allowance": "amount",
    "dividend": "amount",
    "franking-account": "closing_balance",
    "division-7a": "loan_amount",
}
COMPANY_REVIEW_SOURCE_MAP = {
    "loss": (COMPANY_LOSSES_SOURCE,),
    "loss-continuity": (COMPANY_LOSSES_SOURCE,),
    "asset": (COMPANY_CAPITAL_ALLOWANCES_SOURCE,),
    "asset-pool": (COMPANY_CAPITAL_ALLOWANCES_SOURCE,),
    "depreciation": (COMPANY_CAPITAL_ALLOWANCES_SOURCE,),
    "capital-allowance": (COMPANY_CAPITAL_ALLOWANCES_SOURCE,),
    "dividend": (COMPANY_DIVIDEND_SOURCE, COMPANY_FRANKING_SOURCE),
    "franking-account": (COMPANY_FRANKING_SOURCE,),
    "division-7a": (COMPANY_DIVISION_7A_SOURCE,),
}
COMPANY_REVIEW_MONEY_FIELDS = {
    "loss": (
        "amount", "current_year_loss", "prior_year_loss", "carried_forward_loss",
        "loss_deducted", "loss_applied",
    ),
    "asset": ("cost", "opening_value", "closing_value", "adjustable_value"),
    "asset-pool": ("opening_value", "additions", "deductions", "closing_value"),
    "depreciation": ("amount", "deduction_amount", "opening_value", "closing_value"),
    "capital-allowance": ("amount", "deduction_amount", "adjustable_value"),
    "dividend": (
        "amount", "dividend_amount", "franked_amount", "unfranked_amount",
        "franking_credit", "dividend_franking_credit", "tfn_withholding",
        "dividend_tfn_withholding", "dividend_franked_amount",
        "dividend_unfranked_amount", "dividend_franking_credits",
    ),
    "franking-account": (
        "opening_balance", "credits", "debits", "closing_balance",
        "franking_opening_balance", "franking_credits", "franking_debits",
        "franking_closing_balance", "franking_deficit_tax", "fdt", "fdt_payable",
        "franking_fdt", "franking_fdt_payable",
    ),
    "division-7a": (
        "amount", "payment", "loan", "loan_amount", "asset_use",
        "debt_forgiven", "repayment", "minimum_yearly_repayment",
        "distributable_surplus", "retained_earnings", "private_expense",
        "shareholder_payment", "director_payment", "associate_payment",
        "repayments", "minimum_repayment", "retained_profit", "retained_profits",
        "division_7a_payment", "division_7a_loan_amount",
        "division_7a_shareholder_payment", "division_7a_director_payment",
        "division_7a_associate_payment",
        "division_7a_asset_use", "division_7a_debt_forgiven",
        "division_7a_repayment", "division_7a_repayments",
        "division_7a_minimum_yearly_repayment", "division_7a_minimum_repayment",
        "division_7a_distributable_surplus", "division_7a_retained_earnings",
        "division_7a_retained_profit", "division_7a_retained_profits",
        "division_7a_private_expense",
    ),
}
COMPANY_REVIEW_NUMERIC_FIELDS = {
    "franking-account": (
        "benchmark_percentage", "corporate_tax_rate",
        "franking_benchmark_percentage", "franking_corporate_tax_rate",
    ),
    "division-7a": (
        "loan_term_years", "interest_rate", "benchmark_interest_rate",
        "benchmark_rate",
        "division_7a_loan_term_years", "division_7a_interest_rate",
        "division_7a_benchmark_interest_rate", "division_7a_benchmark_rate",
    ),
}
COMPANY_ALWAYS_REVIEW_SECTIONS = {
    "loss-continuity", "dividend", "franking-account", "division-7a",
}
COMPANY_REVIEW_CATEGORY_TARGETS = {
    "dividend": ("dividend_items", "received", None),
    "dividends": ("dividend_items", "received", None),
    "franking": ("franking_account_items", None, "credits"),
    "division-7a": ("division_7a_items", None, None),
}
TRUST_REVIEW_COLLECTIONS = {
    "capital-gain": (
        "capital_gain_items", "capital_gains", "cgt_items", "trust_capital_gains",
    ),
    "franked-distribution": (
        "franked_distribution_items", "franked_distributions",
        "trust_franked_distributions",
    ),
    "streaming": (
        "streaming_review", "streaming_details", "specific_entitlement",
    ),
    "beneficiary-allocation": (
        "beneficiary_allocations", "beneficiary_component_allocations",
        "component_allocations", "distribution_allocations",
    ),
}
TRUST_REVIEW_SCALAR_FIELDS = {
    "capital-gain": "amount",
    "franked-distribution": "amount",
    "streaming": "streaming",
    "beneficiary-allocation": "allocation",
}
TRUST_REVIEW_MONEY_FIELDS = {
    "capital-gain": (
        "amount", "gross_capital_gain", "net_capital_gain", "proceeds", "cost_base",
        "capital_losses_applied", "discount_amount",
    ),
    "franked-distribution": (
        "amount", "franked_amount", "unfranked_amount", "franking_credit",
        "franking_credits", "tfn_withholding",
    ),
    "beneficiary-allocation": (
        "allocation", "component_amount", "beneficiary_capital_gain",
        "beneficiary_discounted_capital_gain", "beneficiary_franked_distribution",
        "beneficiary_franking_credits",
    ),
}
PARTNERSHIP_REVIEW_COLLECTIONS = {
    "loss": ("loss_items", "losses", "tax_losses", "partnership_losses"),
    "loss-allocation": ("loss_allocations", "loss_allocation", "partner_loss_allocations"),
    "gst-bas": ("gst_bas_review", "gst_bas_details"),
    "psi": ("psi_review", "psi_details", "personal_services_income"),
    "business-structure": (
        "business_structure_review", "business_structure", "structure_indicators",
    ),
}
PARTNERSHIP_REVIEW_SCALAR_FIELDS = {
    "loss": "amount",
    "loss-allocation": "allocation",
    "gst-bas": "bas_overlap",
    "psi": "psi",
    "business-structure": "business_structure",
}
PARTNERSHIP_REVIEW_SOURCE_MAP = {
    "loss": (PARTNERSHIP_LOSSES_SOURCE,),
    "loss-allocation": (PARTNERSHIP_LOSSES_SOURCE, PARTNERSHIP_BUSINESS_SOURCE),
    "gst-bas": (PARTNERSHIP_GST_SOURCE, PARTNERSHIP_BAS_SOURCE),
    "psi": (PARTNERSHIP_PSI_SOURCE,),
    "business-structure": (PARTNERSHIP_PSI_SOURCE, PARTNERSHIP_BUSINESS_SOURCE),
}
CATEGORY_ALIASES = {
    "gross-payments-where-abn-not-quoted": "no-abn-withholding",
    "gross-payments-subject-to-foreign-resident-withholding": "foreign-resident-withholding",
    "sales": "sales-goods-services",
    "sales-of-goods-and-services": "sales-goods-services",
    "forestry-managed-investment-scheme": "fmis",
    "gross-interest": "interest",
    "gross-rent": "rent",
    "rent-and-leasing": "rent-leasing-hiring",
    "assessable-government-industry-payments": "government-industry-payments",
    "other-gross-income": "other",
    "contractor-subcontractor-and-commission": "contractor-commission",
    "super-expenses": "superannuation",
    "repairs-and-maintenance": "repairs-maintenance",
    "other-expenses": "other",
    "partnerships-and-trusts": "partnership-trust-income",
    "partnership-and-trust-income": "partnership-trust-income",
    "investment-income-deductions": "investment-income-deduction",
    "fmis-deductions": "fmis-deduction",
    "other-deduction": "other",
    "other-deductions": "other",
    "other-australian-income": "other-australian-income",
}


def _missing(value: Any) -> bool:
    return taxmate_entity_routing.value_missing(value)


def _declined(value: Any) -> bool:
    return taxmate_entity_routing.value_declined(value)


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return str(value)


def _unique(values: Iterable[Any]) -> List[Any]:
    result: List[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
        if marker not in seen:
            seen.add(marker)
            result.append(value)
    return result


def _slug(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return CATEGORY_ALIASES.get(normalized, normalized)


def _amount(value: Any) -> Optional[Decimal]:
    if isinstance(value, bool) or _missing(value):
        return None
    try:
        candidate = str(value).strip().replace(",", "").replace("$", "")
        parsed = Decimal(candidate)
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _percentage(value: Any) -> Optional[Decimal]:
    if isinstance(value, str) and value.strip().endswith("%"):
        value = value.strip()[:-1]
    return _amount(value)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def _false_signal(value: Any) -> bool:
    if value is False or value == 0:
        return True
    return isinstance(value, str) and value.strip().lower() in {
        "false", "no", "none", "0", "off", "unchecked",
    }


def _review_signal(value: Any) -> bool:
    if _missing(value) or _false_signal(value):
        return False
    if isinstance(value, dict):
        return any(_review_signal(item) for item in value.values())
    if isinstance(value, list):
        return any(_review_signal(item) for item in value)
    return True


def _status_review_signal(value: Any) -> bool:
    if not isinstance(value, str):
        return value is True
    lowered = value.strip().lower()
    return any(token in lowered for token in (
        "accountant review", "needs review", "requires review", "review required",
        "unknown", "unclear", "ambiguous", "disputed", "mixed", "partial",
    ))


def _evidence_available(value: Any) -> bool:
    values = value if isinstance(value, list) else [value]
    return any(not _missing(item) and not _declined(item) for item in values)


def _field_values_equal(field: str, left: Any, right: Any) -> bool:
    if left == right:
        return True
    if field == "category":
        return _slug(left) == _slug(right)
    if field == "amount":
        left_amount = _amount(left)
        right_amount = _amount(right)
        return left_amount is not None and right_amount is not None and left_amount == right_amount
    return False


def _field(raw: Dict[str, Any], field: str) -> Tuple[Any, List[Any], bool]:
    present = [(alias, raw[alias]) for alias in LINE_FIELD_ALIASES[field] if alias in raw]
    meaningful = [value for _, value in present if not _missing(value)]
    value = meaningful[0] if meaningful else (present[0][1] if present else None)
    conflicts = [candidate for candidate in meaningful[1:] if not _field_values_equal(field, value, candidate)]
    return value, _unique(conflicts), bool(present)


def _normalize_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    conflicts: Dict[str, Any] = {}
    consumed = set(PROVENANCE_FIELDS)
    for field, aliases in LINE_FIELD_ALIASES.items():
        consumed.update(aliases)
        value, field_conflicts, present = _field(raw, field)
        if present:
            normalized[field] = value
        if field_conflicts:
            conflicts[field] = [value, *field_conflicts]
    valid_sources, invalid_sources = taxmate_entity_routing.source_provenance(raw)
    if valid_sources:
        normalized["source_urls"] = _unique(valid_sources)
    if invalid_sources:
        normalized["invalid_sources"] = invalid_sources
    alias_conflicts = raw.get("_alias_conflicts")
    if isinstance(alias_conflicts, dict):
        conflicts.update(alias_conflicts)
    consumed.add("_alias_conflicts")
    unsupported = {key: value for key, value in raw.items() if key not in consumed}
    if unsupported:
        normalized["unsupported"] = unsupported
    if conflicts:
        normalized["conflicts"] = conflicts
    return normalized


def _item_identity(raw: Any) -> Tuple[str, str]:
    if not isinstance(raw, dict):
        return "", ""
    normalized = _normalize_item(raw)
    category = _slug(normalized.get("category", ""))
    description = str(normalized.get("description", "")).strip().casefold()
    return (category, description) if category and description else ("", "")


def _merge_alias_item(existing: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(existing)
    canonical_by_alias = {
        alias: field for field, aliases in LINE_FIELD_ALIASES.items() for alias in aliases
    }
    for key, value in candidate.items():
        if key == "_alias_conflicts" and isinstance(value, dict):
            taxmate_entity_routing.merge_alias_conflicts(merged, value)
            continue
        if key not in merged or _missing(merged[key]):
            merged[key] = copy.deepcopy(value)
            continue
        if _missing(value):
            continue
        canonical = canonical_by_alias.get(key)
        if _field_values_equal(canonical or "", merged[key], value):
            continue
        if key in PROVENANCE_FIELDS or canonical_by_alias.get(key) == "evidence":
            left = merged[key] if isinstance(merged[key], list) else [merged[key]]
            right = value if isinstance(value, list) else [value]
            merged[key] = _unique([*left, *right])
            continue
        spare = next(
            (alias for alias in LINE_FIELD_ALIASES.get(canonical, ()) if alias not in merged),
            None,
        )
        if spare:
            merged[spare] = copy.deepcopy(value)
            continue
        taxmate_entity_routing.merge_alias_conflicts(
            merged, {key: [merged[key], value]},
        )
    return merged


def _collection(
    record: Dict[str, Any],
    aliases: Tuple[str, ...],
    *,
    preserve_falsey_scalars: bool = False,
    alias_defaults: Optional[Dict[str, Dict[str, Any]]] = None,
    alias_scalar_fields: Optional[Dict[str, str]] = None,
    scalar_field: Optional[str] = None,
) -> Tuple[List[Any], bool]:
    values: List[Any] = []
    origins: List[set[str]] = []
    blank_supplied = False
    for alias in aliases:
        if alias not in record:
            continue
        value = record[alias]
        scalar_preserved = preserve_falsey_scalars and not isinstance(value, (dict, list))
        if _declined(value) and not scalar_preserved:
            continue
        if _missing(value):
            blank_supplied = True
            continue
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict) and _missing(item):
                blank_supplied = True
                continue
            defaults = (alias_defaults or {}).get(alias, {})
            if defaults:
                item = copy.deepcopy(item)
                if not isinstance(item, dict):
                    item = {(alias_scalar_fields or {}).get(alias, scalar_field): item}
                for key, default in defaults.items():
                    item.setdefault(key, default)
            if any(item == existing for existing in values):
                continue
            identity = _item_identity(item)
            matches = [
                index for index, existing in enumerate(values)
                if alias not in origins[index] and identity != ("", "") and _item_identity(existing) == identity
            ]
            if len(matches) == 1 and isinstance(item, dict) and isinstance(values[matches[0]], dict):
                index = matches[0]
                values[index] = _merge_alias_item(values[index], item)
                origins[index].add(alias)
            else:
                values.append(item)
                origins.append({alias})
    return values, blank_supplied and not values


def _record_has_worksheet(kind: str, record: Dict[str, Any]) -> bool:
    return any(field in record for field in taxmate_entity_routing.WORKSHEET_CONTENT_FIELDS_BY_KIND[kind])


def _identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def _parent_for(
    kind: str,
    record: Dict[str, Any],
    records: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Optional[str]]:
    if any(field in record and not _missing(record[field]) for field in ("name", "abn")):
        return record, None
    parents = [
        candidate for candidate in records
        if any(field in candidate and not _missing(candidate[field]) for field in taxmate_entity_routing.FIELDS[kind])
    ]
    supplied_name = record.get("entity_name")
    supplied_abn = record.get("entity_abn")
    if not _missing(supplied_name) or not _missing(supplied_abn):
        matches = [
            candidate for candidate in parents
            if (_missing(supplied_name) or _identifier(candidate.get("name")) == _identifier(supplied_name))
            and (_missing(supplied_abn) or _identifier(candidate.get("abn")) == _identifier(supplied_abn))
        ]
        if len(matches) == 1:
            return matches[0], None
        return record, "unmatched parent entity association" if not matches else "ambiguous parent entity association"
    if len(parents) == 1:
        return parents[0], None
    if len(parents) > 1:
        return record, "parent entity identity"
    return record, f"{kind} identity"


def _identity_facts(kind: str, parent: Dict[str, Any], record: Dict[str, Any]) -> List[Tuple[str, Any]]:
    facts: List[Tuple[str, Any]] = []
    for field in ("name", "abn"):
        value = parent.get(field)
        if _missing(value):
            value = record.get(f"entity_{field}")
        if not _missing(value):
            facts.append((f"{kind}_{field}", value))
    return facts


def _sources(kind: str, worksheet: str, item: Dict[str, Any]) -> List[str]:
    if kind == "company":
        detailed = [COMPANY_INCOME_SOURCE if worksheet == "income" else COMPANY_DEDUCTION_SOURCE]
    elif worksheet == "income":
        category = _slug(item.get("category", ""))
        if category in {"business-income", "no-abn-withholding", "foreign-resident-withholding", "government-industry-payments"}:
            detailed = [PARTNERSHIP_ITEM_5_SOURCE]
        elif category in {"partnership-trust-income", "rent"}:
            detailed = [PARTNERSHIP_ITEMS_6_TO_9_SOURCE]
        elif category in {"fmis", "interest", "dividends", "other-australian-income"}:
            detailed = [PARTNERSHIP_ITEMS_10_TO_15_SOURCE]
        elif category in {"attributed-foreign-income", "other-foreign-source-income"}:
            detailed = [PARTNERSHIP_FOREIGN_INCOME_SOURCE]
        else:
            detailed = list(PARTNERSHIP_INCOME_SOURCES)
    elif worksheet == "deduction":
        category = _slug(item.get("category", ""))
        detailed = (
            [PARTNERSHIP_ITEMS_16_TO_20_SOURCE]
            if category in {"investment-income-deduction", "fmis-deduction"}
            else [PARTNERSHIP_ITEM_5_SOURCE]
            if category
            else list(PARTNERSHIP_DEDUCTION_SOURCES)
        )
    else:
        detailed = [PARTNERSHIP_BUSINESS_SOURCE]
    return list(dict.fromkeys([
        taxmate_entity_routing.SOURCES[kind], *detailed, *item.get("source_urls", []),
    ]))


def _facts(pairs: Iterable[Tuple[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"key": key.replace("_", "-"), "label": key.replace("_", " ").title(), "value": value}
        for key, value in pairs
    ]


def _followup_sources(kind: str, worksheet: str, item: Dict[str, Any]) -> List[str]:
    if kind == "company" and worksheet in COMPANY_REVIEW_COLLECTIONS:
        return _company_sources(worksheet, item)
    if kind == "trust" and worksheet in TRUST_REVIEW_COLLECTIONS:
        return _trust_sources(item)
    if kind == "partnership" and worksheet in PARTNERSHIP_REVIEW_COLLECTIONS:
        return _partnership_review_sources(worksheet, item)
    return _sources(kind, worksheet, item)


def _line_followup(
    kind: str,
    worksheet: str,
    item: Dict[str, Any],
    gaps: List[str],
    review_required: bool,
    evidence_index: int,
) -> Dict[str, Any]:
    details: List[Tuple[str, Any]] = [("missing_or_ambiguous", gaps)]
    for key in ("conflicts", "unsupported", "invalid_sources"):
        if item.get(key):
            details.append((key, item[key]))
    return {
        "number": f"ENTITY-WORKSHEET-EVID-{evidence_index}",
        "ato_area": f"{kind.title()} {worksheet} worksheet evidence",
        "question": f"{kind.title()} {worksheet} item requires follow-up",
        "answer": f"Confirm {', '.join(gaps)}",
        "why_included": "Incomplete, conflicting, unsupported, or review-like worksheet facts fail closed.",
        "status": "Accountant review" if review_required else "Evidence",
        "source_urls": _followup_sources(kind, worksheet, item),
        "checked_at": item.get("checked_at") if taxmate_entity_routing.valid_checked_at(item.get("checked_at")) else taxmate_entity_routing.CHECKED_AT,
        "row_kind": f"entity-return-{kind}-{worksheet}-evidence",
        "facts": _facts(details),
    }


def _line_rows(
    kind: str,
    worksheet: str,
    raw_items: List[Any],
    parent: Dict[str, Any],
    record: Dict[str, Any],
    association_gap: Optional[str],
    counter: int,
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Decimal], bool, int, int]:
    rows: List[Dict[str, Any]] = []
    evidence: List[Dict[str, Any]] = []
    amounts: List[Decimal] = []
    all_valid = bool(raw_items)
    for raw in raw_items:
        counter += 1
        if not isinstance(raw, dict) or _missing(raw):
            all_valid = False
            evidence.append({
                "number": f"ENTITY-WORKSHEET-EVID-{evidence_index}",
                "ato_area": f"{kind.title()} {worksheet} worksheet evidence",
                "question": f"Malformed {worksheet} item",
                "answer": f"Preserved unresolved worksheet input: {_display(raw)}",
                "why_included": "Malformed worksheet input fails closed instead of being dropped.",
                "status": "Evidence", "source_urls": _sources(kind, worksheet, {}),
                "checked_at": taxmate_entity_routing.CHECKED_AT,
                "row_kind": f"entity-return-{kind}-{worksheet}-evidence",
                "facts": _facts([("raw", raw)]),
            })
            evidence_index += 1
            continue

        item = _normalize_item(raw)
        category = _slug(item.get("category", ""))
        amount = _amount(item.get("amount"))
        supported = category in CATEGORIES[(kind, worksheet)]
        gaps: List[str] = []
        if association_gap:
            gaps.append(association_gap)
        if not category:
            gaps.append("category")
        elif not supported:
            gaps.append("supported category")
        if category == "other" and _missing(item.get("description")):
            gaps.append("other category description")
        if amount is None:
            gaps.append("finite amount")
            all_valid = False
        else:
            amounts.append(amount)
        if not _evidence_available(item.get("evidence")):
            gaps.append("evidence")
        if item.get("invalid_sources"):
            gaps.append("source provenance")
        if "checked_at" in item and not _missing(item["checked_at"]) and not taxmate_entity_routing.valid_checked_at(item["checked_at"]):
            gaps.append("checked-at provenance")
        if item.get("conflicts"):
            gaps.append("conflicting item facts")
        if item.get("unsupported"):
            gaps.append("unsupported item facts")
        component_valid = bool(category) and supported and amount is not None
        if category == "other" and _missing(item.get("description")):
            component_valid = False
        if item.get("conflicts") or item.get("unsupported"):
            component_valid = False
        all_valid = all_valid and component_valid

        pairs = _identity_facts(kind, parent, record)
        for field in LINE_FIELD_ALIASES:
            if field in item and field not in {"status", "review_status"}:
                value = category if field == "category" else item[field]
                pairs.append((field, value))
        if item.get("conflicts"):
            pairs.append(("conflicts", item["conflicts"]))
        if item.get("unsupported"):
            pairs.append(("unsupported", item["unsupported"]))
        checked_at = item.get("checked_at")
        row = {
            "number": f"{kind.upper()}-{worksheet.upper()}-{counter}",
            "ato_area": f"{kind.title()} {worksheet} worksheet",
            "question": f"{kind.title()} {worksheet} item",
            "answer": "; ".join(f"{key.replace('_', ' ')} {_display(value)}" for key, value in pairs),
            "why_included": "Prep-only entity worksheet fact; no final deductibility, treatment, allocation, or lodgment decision.",
            "status": "Accountant review",
            "source_urls": _sources(kind, worksheet, item),
            "checked_at": checked_at if taxmate_entity_routing.valid_checked_at(checked_at) else taxmate_entity_routing.CHECKED_AT,
            "row_kind": f"entity-return-{kind}-{worksheet}",
            "facts": _facts(pairs),
            "tab_text": f"{kind.title()} {worksheet} facts stay in the isolated prep-only workflow.",
        }
        rows.append(row)
        review_required = (
            not supported
            or (amount is not None and amount < 0)
            or bool(item.get("conflicts") or item.get("unsupported"))
            or any(_review_signal(item.get(field)) for field in REVIEW_FIELDS if field not in {"status", "review_status"})
            or any(_status_review_signal(item.get(field)) for field in ("status", "review_status"))
        )
        if gaps:
            evidence.append(_line_followup(
                kind, worksheet, item, list(dict.fromkeys(gaps)), review_required, evidence_index,
            ))
            evidence_index += 1
    return rows, evidence, amounts, all_valid, counter, evidence_index


def _total_value(record: Dict[str, Any], worksheet: str) -> Tuple[Any, Dict[str, Any]]:
    supplied = [(alias, record[alias]) for alias in TOTAL_ALIASES[worksheet] if alias in record]
    meaningful = [(alias, value) for alias, value in supplied if not _missing(value)]
    if not meaningful:
        return None, {}
    value = meaningful[0][1]
    conflicts = {
        alias: candidate
        for alias, candidate in meaningful[1:]
        if not _field_values_equal("amount", value, candidate)
    }
    return value, conflicts


def _total_rows(
    kind: str,
    worksheet: str,
    record_number: int,
    record: Dict[str, Any],
    parent: Dict[str, Any],
    amounts: List[Decimal],
    all_valid: bool,
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    supplied, conflicts = _total_value(record, worksheet)
    if supplied is None:
        return [], [], evidence_index
    parsed = _amount(supplied)
    item_total = sum(amounts, Decimal("0")) if all_valid else None
    reconciliation = (
        "matches supplied item total"
        if parsed is not None and item_total is not None and parsed == item_total
        else "does not match supplied item total"
        if parsed is not None and item_total is not None
        else "item reconciliation unavailable"
    )
    pairs = _identity_facts(kind, parent, record)
    pairs.extend([("supplied_total", supplied), ("reconciliation", reconciliation)])
    if item_total is not None:
        pairs.append(("item_total", _decimal_text(item_total)))
    if conflicts:
        pairs.append(("conflicts", conflicts))
    source_item: Dict[str, Any] = {}
    row = {
        "number": f"{kind.upper()}-{worksheet.upper()}-TOTAL-{record_number}",
        "ato_area": f"{kind.title()} {worksheet} worksheet",
        "question": f"Supplied {worksheet} total reconciliation",
        "answer": "; ".join(f"{key.replace('_', ' ')} {_display(value)}" for key, value in pairs),
        "why_included": "Prep-only comparison of supplied totals; not a taxable-income or deduction calculation.",
        "status": "Accountant review", "source_urls": _sources(kind, worksheet, source_item),
        "checked_at": taxmate_entity_routing.CHECKED_AT,
        "row_kind": f"entity-return-{kind}-{worksheet}", "facts": _facts(pairs),
        "tab_text": "Supplied totals require accountant review before use.",
    }
    gaps: List[str] = []
    if parsed is None:
        gaps.append("finite supplied total")
    if not all_valid:
        gaps.append("complete item breakdown")
    elif parsed is not None and parsed != item_total:
        gaps.append("total reconciliation")
    if conflicts:
        gaps.append("conflicting total aliases")
    followups: List[Dict[str, Any]] = []
    if gaps:
        followups.append(_line_followup(
            kind, worksheet, {"conflicts": conflicts}, gaps, bool(conflicts), evidence_index,
        ))
        evidence_index += 1
    return [row], followups, evidence_index


def _context_rows(
    kind: str,
    record_number: int,
    record: Dict[str, Any],
    parent: Dict[str, Any],
    association_gap: Optional[str],
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    fields = [field for field in ("accounting_records", "gst_bas_interaction") if field in record]
    if not fields:
        return [], [], evidence_index
    pairs = _identity_facts(kind, parent, record)
    gaps = [association_gap] if association_gap else []
    for field in fields:
        value = record[field]
        pairs.append((field, value))
        if _missing(value) or (field == "accounting_records" and not _evidence_available(value)):
            gaps.append(field.replace("_", " "))
    valid_sources, invalid_sources = taxmate_entity_routing.source_provenance(record)
    if invalid_sources:
        gaps.append("source provenance")
    checked_at = record.get("checked_at")
    if "checked_at" in record and not _missing(checked_at) and not taxmate_entity_routing.valid_checked_at(checked_at):
        gaps.append("checked-at provenance")
    source_item = {"source_urls": valid_sources, "checked_at": checked_at}
    row = {
        "number": f"{kind.upper()}-DEDUCTION-CONTEXT-{record_number}",
        "ato_area": f"{kind.title()} income and deduction worksheet",
        "question": f"{kind.title()} accounting and GST/BAS context",
        "answer": "; ".join(f"{key.replace('_', ' ')} {_display(value)}" for key, value in pairs),
        "why_included": "Prep-only accounting-record and GST/BAS signals; no final treatment or calculation.",
        "status": "Accountant review",
        "source_urls": list(dict.fromkeys([
            *_sources(kind, "income", source_item), *_sources(kind, "deduction", source_item),
        ])),
        "checked_at": checked_at if taxmate_entity_routing.valid_checked_at(checked_at) else taxmate_entity_routing.CHECKED_AT,
        "row_kind": f"entity-return-{kind}-deduction",
        "facts": _facts(pairs),
        "tab_text": f"{kind.title()} accounting and GST/BAS context requires accountant review.",
    }
    followups: List[Dict[str, Any]] = []
    if gaps:
        followups.append(_line_followup(
            kind,
            "deduction",
            {**source_item, "invalid_sources": invalid_sources},
            list(dict.fromkeys(gaps)),
            _review_signal(record.get("gst_bas_interaction")),
            evidence_index,
        ))
        evidence_index += 1
    return [row], followups, evidence_index


def _special_rows(
    record: Dict[str, Any],
    parent: Dict[str, Any],
    association_gap: Optional[str],
    field: str,
    counter: int,
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    if field not in record or _declined(record[field]):
        return [], [], counter, evidence_index
    raw_value = record[field]
    raw_items = raw_value if isinstance(raw_value, list) else [raw_value]
    worksheet = "trading-stock" if field == "trading_stock" else "capital-allowance"
    rows: List[Dict[str, Any]] = []
    followups: List[Dict[str, Any]] = []
    for raw in raw_items:
        counter += 1
        if not isinstance(raw, dict) or _missing(raw):
            gaps = [f"{worksheet} facts"]
            followups.append(_line_followup(
                "partnership", worksheet, {}, gaps, False, evidence_index,
            ))
            evidence_index += 1
            continue
        valid_sources, invalid_sources = taxmate_entity_routing.source_provenance(raw)
        checked_at = raw.get("checked_at")
        metadata = {"source_url", "source_urls", "checked_at", "status", "review_status"}
        facts_raw = {key: value for key, value in raw.items() if key not in metadata}
        pairs = _identity_facts("partnership", parent, record) + list(facts_raw.items())
        gaps: List[str] = [association_gap] if association_gap else []
        if field == "trading_stock":
            stock_amounts = {
                "opening stock": raw.get("opening_stock", raw.get("opening")),
                "purchases or costs": raw.get("purchases", raw.get("costs", raw.get("purchases_costs"))),
                "closing stock": raw.get("closing_stock", raw.get("closing")),
            }
            for label, value in stock_amounts.items():
                if _amount(value) is None:
                    gaps.append(f"finite {label}")
            if all(_missing(raw.get(key)) for key in ("valuation_method", "valuation", "election")):
                gaps.append("valuation method or election")
        else:
            if _missing(raw.get("asset")) and _missing(raw.get("category")):
                gaps.append("asset or category")
            money_fields = ("amount", "deduction_amount", "adjustable_value", "balancing_adjustment")
            supplied_money = [
                key for key in money_fields
                if key in raw and not _missing(raw[key]) and not isinstance(raw[key], bool)
            ]
            if not supplied_money or any(_amount(raw[key]) is None for key in supplied_money):
                gaps.append("finite monetary fact")
            if _missing(raw.get("method")):
                gaps.append("method")
        evidence_value = raw.get("evidence", raw.get("records", raw.get("documents")))
        if not _evidence_available(evidence_value):
            gaps.append("evidence")
        if invalid_sources:
            gaps.append("source provenance")
        if "checked_at" in raw and not _missing(checked_at) and not taxmate_entity_routing.valid_checked_at(checked_at):
            gaps.append("checked-at provenance")
        item = {"source_urls": valid_sources, "invalid_sources": invalid_sources, "checked_at": checked_at}
        row = {
            "number": f"PARTNERSHIP-{worksheet.upper()}-{counter}",
            "ato_area": f"Partnership {worksheet.replace('-', ' ')} worksheet",
            "question": f"Partnership {worksheet.replace('-', ' ')} facts",
            "answer": "; ".join(f"{key.replace('_', ' ')} {_display(value)}" for key, value in pairs),
            "why_included": "Prep-only partnership fact; method, treatment, and final deduction remain accountant decisions.",
            "status": "Accountant review", "source_urls": _sources("partnership", worksheet, item),
            "checked_at": checked_at if taxmate_entity_routing.valid_checked_at(checked_at) else taxmate_entity_routing.CHECKED_AT,
            "row_kind": f"entity-return-partnership-{worksheet}", "facts": _facts(pairs),
            "tab_text": f"Partnership {worksheet.replace('-', ' ')} facts require accountant review.",
        }
        rows.append(row)
        review_required = (
            any(_review_signal(raw.get(key)) for key in ("election", "balancing_adjustment"))
            or any(_status_review_signal(raw.get(key)) for key in ("status", "review_status"))
        )
        if gaps:
            followups.append(_line_followup(
                "partnership", worksheet, item, list(dict.fromkeys(gaps)), review_required, evidence_index,
            ))
            evidence_index += 1
    return rows, followups, counter, evidence_index


def _company_sources(section: str, raw: Dict[str, Any]) -> List[str]:
    valid_sources, _ = taxmate_entity_routing.source_provenance(raw)
    return list(dict.fromkeys([
        taxmate_entity_routing.SOURCES["company"],
        *COMPANY_REVIEW_SOURCE_MAP[section],
        *valid_sources,
    ]))


def _review_alias_groups(
    fields: Iterable[str],
    canonical_by_field: Dict[str, str],
) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for field in fields:
        canonical = canonical_by_field.get(field, field)
        groups.setdefault(canonical, [canonical])
        if field not in groups[canonical]:
            groups[canonical].append(field)
    return groups


def _review_aliases_conflict(raw: Dict[str, Any], groups: Dict[str, List[str]]) -> bool:
    for canonical, aliases in groups.items():
        values = [
            raw[field]
            for field in aliases
            if field in raw and not _missing(raw[field])
        ]
        if len(values) < 2:
            continue
        if any(
            not taxmate_entity_routing.review_values_equivalent(
                canonical, values[0], candidate,
            )
            for candidate in values[1:]
        ):
            return True
    return False


def _company_review_has_alias_conflict(section: str, raw: Dict[str, Any]) -> bool:
    collection = {
        "dividend": "dividend_items",
        "franking-account": "franking_account_items",
        "division-7a": "division_7a_items",
    }.get(section)
    if not collection:
        return False
    groups = _review_alias_groups(
        taxmate_entity_routing.COMPANY_REVIEW_FLAT_GROUPS[collection],
        taxmate_entity_routing.COMPANY_REVIEW_FLAT_CANONICAL,
    )
    extras = {
        "dividend": {
            "franking_credit": ("franking_credits",),
        },
        "franking-account": {
            "franking_deficit_tax": ("fdt", "fdt_payable"),
        },
        "division-7a": {
            "complying_loan_agreement": ("complying_agreement",),
            "loan_terms": ("loan_term",),
            "benchmark_interest_rate": ("benchmark_rate",),
            "minimum_yearly_repayment": ("minimum_repayment",),
            "minimum_repayment_made": ("repayment_made",),
            "retained_profit": ("retained_profits",),
        },
    }.get(section, {})
    for canonical, aliases in extras.items():
        groups.setdefault(canonical, [canonical])
        groups[canonical].extend(alias for alias in aliases if alias not in groups[canonical])
    return _review_aliases_conflict(raw, groups)


def _company_review_gaps(section: str, raw: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    supplied_money = [
        field
        for field in COMPANY_REVIEW_MONEY_FIELDS.get(section, ())
        if field in raw
        and not (section == "division-7a" and isinstance(raw[field], bool))
    ]
    if section not in {"loss-continuity", "division-7a"}:
        if not supplied_money or any(_amount(raw[field]) is None for field in supplied_money):
            gaps.append("finite monetary fact")
    elif section == "division-7a" and supplied_money and any(
        _amount(raw[field]) is None for field in supplied_money
    ):
        gaps.append("finite monetary fact")
    supplied_numeric = [
        field
        for field in COMPANY_REVIEW_NUMERIC_FIELDS.get(section, ())
        if field in raw and not isinstance(raw[field], bool)
    ]
    if supplied_numeric and any(_amount(raw[field]) is None for field in supplied_numeric):
        gaps.append("finite numeric fact")
    if section in {"asset", "depreciation", "capital-allowance"}:
        if _missing(raw.get("asset")) and _missing(raw.get("category")):
            gaps.append("asset or category")
    if section == "asset-pool" and _missing(raw.get("pool")) and _missing(raw.get("pool_type")):
        gaps.append("asset pool type")
    if section in {"depreciation", "capital-allowance"} and _missing(raw.get("method")):
        gaps.append("method")
    if section == "loss-continuity" and all(
        _missing(raw.get(field))
        for field in (
            "continuity_of_ownership", "continuity_test", "ownership_change",
            "control_change", "business_continuity", "same_business", "similar_business",
        )
    ):
        gaps.append("ownership or business continuity signal")
    if section == "dividend":
        direction = str(
            raw.get("direction", raw.get("dividend_direction", ""))
        ).strip().lower()
        paid = direction == "paid" or any(
            _review_signal(raw.get(field))
            and not _status_review_signal(raw.get(field))
            for field in ("paid", "dividend_paid")
        )
        received = direction == "received" or any(
            _review_signal(raw.get(field))
            and not _status_review_signal(raw.get(field))
            for field in ("received", "dividend_received")
        )
        if not paid and not received:
            gaps.append("dividend paid or received")
        elif paid and received:
            gaps.append("conflicting dividend direction")
        if paid and not any(
            _evidence_available(raw.get(field))
            for field in ("resolution", "dividend_resolution")
        ):
            gaps.append("dividend resolution")
        if received and not any(
            _evidence_available(raw.get(field))
            for field in ("statement", "dividend_statement")
        ):
            gaps.append("dividend statement")
    if section == "franking-account" and all(
        _missing(raw.get(field))
        for field in (
            "opening_balance", "credits", "debits", "closing_balance",
            "franking_opening_balance", "franking_credits", "franking_debits",
            "franking_closing_balance",
        )
    ):
        gaps.append("franking account fact")
    if section == "division-7a":
        if all(
            _missing(raw.get(field))
            for field in (
                "transaction_type", "payment", "loan", "loan_amount", "asset_use",
                "shareholder_payment", "director_payment", "associate_payment",
                "debt_forgiven", "private_expense", "division_7a_transaction_type",
                "division_7a_payment", "division_7a_loan_amount",
                "division_7a_shareholder_payment", "division_7a_director_payment",
                "division_7a_associate_payment",
                "division_7a_asset_use", "division_7a_debt_forgiven",
                "division_7a_private_expense",
            )
        ):
            gaps.append("payment, loan, asset use, debt forgiveness, or private benefit")
        loan_supplied = any(
            not _missing(raw.get(field))
            and not (field == "loan" and _false_signal(raw.get(field)))
            for field in ("loan", "loan_amount", "division_7a_loan_amount")
        )
        if loan_supplied and all(
            _missing(raw.get(field))
            for field in (
                "agreement", "complying_loan_agreement",
                "complying_agreement", "division_7a_agreement",
                "division_7a_complying_agreement",
                "division_7a_complying_loan_agreement",
            )
        ):
            gaps.append("loan agreement")
        elif loan_supplied and any(
            _false_signal(raw.get(field))
            for field in (
                "agreement", "complying_loan_agreement",
                "complying_agreement", "division_7a_agreement",
                "division_7a_complying_agreement",
                "division_7a_complying_loan_agreement",
            )
        ):
            gaps.append("complying loan agreement review")
        if loan_supplied and all(
            _missing(raw.get(field))
            for field in (
                "loan_terms", "loan_term", "loan_term_years", "interest_rate",
                "benchmark_interest_rate", "benchmark_rate", "maturity_date",
                "division_7a_loan_terms", "division_7a_loan_term_years",
                "division_7a_interest_rate",
                "division_7a_benchmark_interest_rate",
                "division_7a_benchmark_rate",
                "division_7a_maturity_date",
            )
        ):
            gaps.append("loan terms")
        if loan_supplied and all(
            _missing(raw.get(field))
            for field in (
                "repayment", "repayments", "minimum_yearly_repayment",
                "minimum_repayment", "minimum_repayment_made", "repayment_made",
                "division_7a_repayment",
                "division_7a_minimum_yearly_repayment",
                "division_7a_minimum_repayment",
                "division_7a_minimum_repayment_made",
                "division_7a_repayment_made",
            )
        ):
            gaps.append("repayment or minimum yearly repayment signal")
        elif loan_supplied and any(
            _false_signal(raw.get(field))
            for field in (
                "repayment", "repayments", "minimum_repayment_made",
                "repayment_made", "division_7a_repayment",
                "division_7a_minimum_repayment_made",
                "division_7a_repayment_made",
            )
        ):
            gaps.append("repayment review")
    if raw.get("_alias_conflicts") or _company_review_has_alias_conflict(section, raw):
        gaps.append("conflicting review aliases")
    evidence_values = [
        raw.get("evidence"), raw.get("records"), raw.get("documents"),
        raw.get("resolution_evidence"), raw.get("statement"),
        raw.get("allocation_resolution"),
    ]
    if not any(_evidence_available(value) for value in evidence_values):
        gaps.append("evidence")
    _, invalid_sources = taxmate_entity_routing.source_provenance(raw)
    if invalid_sources:
        gaps.append("source provenance")
    checked_at = raw.get("checked_at")
    if "checked_at" in raw and not _missing(checked_at) and not taxmate_entity_routing.valid_checked_at(checked_at):
        gaps.append("checked-at provenance")
    return gaps


def _company_review_rows(
    record: Dict[str, Any],
    parent: Dict[str, Any],
    association_gap: Optional[str],
    section: str,
    aliases: Tuple[str, ...],
    counter: int,
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    raw_items, blank_requested = _collection(
        record,
        aliases,
        preserve_falsey_scalars=True,
        alias_defaults=COMPANY_REVIEW_ALIAS_DEFAULTS.get(section),
        alias_scalar_fields=COMPANY_REVIEW_ALIAS_SCALAR_FIELDS.get(section),
        scalar_field=COMPANY_REVIEW_SCALAR_FIELDS[section],
    )
    rows: List[Dict[str, Any]] = []
    followups: List[Dict[str, Any]] = []
    if blank_requested:
        followups.append(_line_followup(
            "company", section, {}, [f"{section.replace('-', ' ')} facts"], False, evidence_index,
        ))
        evidence_index += 1
    for raw in raw_items:
        counter += 1
        if not isinstance(raw, dict):
            raw = {COMPANY_REVIEW_SCALAR_FIELDS[section]: raw}
        if _missing(raw):
            followups.append(_line_followup(
                "company", section, {}, [f"{section.replace('-', ' ')} facts"], False, evidence_index,
            ))
            evidence_index += 1
            continue
        metadata = {"source_url", "source_urls", "checked_at", "status", "review_status"}
        fact_values = {key: value for key, value in raw.items() if key not in metadata}
        pairs = _identity_facts("company", parent, record) + list(fact_values.items())
        gaps = [association_gap] if association_gap else []
        gaps.extend(_company_review_gaps(section, raw))
        checked_at = raw.get("checked_at")
        rows.append({
            "number": f"COMPANY-{section.upper()}-{counter}",
            "ato_area": f"Company {section.replace('-', ' ')} review",
            "question": f"Company {section.replace('-', ' ')} facts",
            "answer": "; ".join(f"{key.replace('_', ' ')} {_display(value)}" for key, value in pairs),
            "why_included": (
                "Prep-only company fact; loss use, asset treatment, dividend/franking treatment, "
                "Division 7A, and final tax outcomes remain accountant decisions."
            ),
            "status": "Accountant review",
            "source_urls": _company_sources(section, raw),
            "checked_at": (
                checked_at
                if taxmate_entity_routing.valid_checked_at(checked_at)
                else taxmate_entity_routing.CHECKED_AT
            ),
            "row_kind": f"entity-return-company-{section}",
            "facts": _facts(pairs),
            "tab_text": f"Company {section.replace('-', ' ')} facts require accountant review.",
        })
        review_required = section in COMPANY_ALWAYS_REVIEW_SECTIONS or any(
            _status_review_signal(raw.get(key))
            for key in (
                "method", "instant_asset_write_off", "mixed_use", "private_use",
                "status", "review_status",
            )
        )
        if gaps:
            valid_sources, invalid_sources = taxmate_entity_routing.source_provenance(raw)
            source_item = {
                "source_urls": valid_sources,
                "invalid_sources": invalid_sources,
                "checked_at": checked_at,
                "conflicts": raw.get("_alias_conflicts"),
            }
            followups.append(_line_followup(
                "company", section, source_item,
                list(dict.fromkeys(gaps)), review_required, evidence_index,
            ))
            evidence_index += 1
    return rows, followups, counter, evidence_index


def _company_deferred_review_items(
    raw_items: List[Any],
) -> Tuple[List[Any], Dict[str, List[Dict[str, Any]]], List[Decimal], bool]:
    worksheet_items: List[Any] = []
    review_items = {
        "dividend_items": [],
        "franking_account_items": [],
        "division_7a_items": [],
    }
    amounts: List[Decimal] = []
    all_valid = True
    for raw in raw_items:
        if not isinstance(raw, dict):
            worksheet_items.append(raw)
            continue
        normalized = _normalize_item(raw)
        target = COMPANY_REVIEW_CATEGORY_TARGETS.get(
            _slug(normalized.get("category", ""))
        )
        if not target:
            worksheet_items.append(raw)
            continue
        collection, direction, amount_field = target
        review = copy.deepcopy(raw)
        if direction:
            review.setdefault("dividend_direction", direction)
        if amount_field and "amount" in normalized:
            review.setdefault(amount_field, normalized["amount"])
        review_items[collection].append(review)
        amount = _amount(normalized.get("amount"))
        if amount is None:
            all_valid = False
        else:
            amounts.append(amount)
    return worksheet_items, review_items, amounts, all_valid


def _merge_company_review_items(
    record: Dict[str, Any],
    review_items: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    merged = copy.deepcopy(record)
    for collection, additions in review_items.items():
        if not additions:
            continue
        existing = merged.get(collection)
        values = (
            copy.deepcopy(existing)
            if isinstance(existing, list)
            else [copy.deepcopy(existing)]
            if existing is not None
            else []
        )
        for addition in additions:
            identity = _item_identity(addition)
            matches = [
                index for index, value in enumerate(values)
                if identity != ("", "") and _item_identity(value) == identity
            ]
            if len(matches) == 1 and isinstance(values[matches[0]], dict):
                values[matches[0]] = _merge_alias_item(values[matches[0]], addition)
            elif addition not in values:
                values.append(copy.deepcopy(addition))
        merged[collection] = values
    return merged


def _trust_sources(raw: Dict[str, Any]) -> List[str]:
    valid_sources, _ = taxmate_entity_routing.source_provenance(raw)
    return list(dict.fromkeys([
        taxmate_entity_routing.SOURCES["trust"],
        *TRUST_REVIEW_SOURCES,
        *valid_sources,
    ]))


def _trust_review_has_alias_conflict(section: str, raw: Dict[str, Any]) -> bool:
    collection = {
        "capital-gain": "capital_gain_items",
        "franked-distribution": "franked_distribution_items",
        "streaming": "streaming_review",
        "beneficiary-allocation": "beneficiary_allocations",
    }[section]
    groups = _review_alias_groups(
        taxmate_entity_routing.TRUST_REVIEW_FLAT_GROUPS[collection],
        taxmate_entity_routing.TRUST_REVIEW_FLAT_CANONICAL,
    )
    return _review_aliases_conflict(raw, groups)


def _trust_resolution_present(record: Dict[str, Any], raw: Dict[str, Any]) -> bool:
    resolution_fields = (
        "resolution", "streaming_resolution", "allocation_resolution",
        "resolution_reference", "resolution_evidence", "resolution_records",
    )
    candidates: List[Any] = [raw, record]
    for alias in TRUST_REVIEW_COLLECTIONS["streaming"]:
        if alias in record:
            value = record[alias]
            candidates.extend(value if isinstance(value, list) else [value])
    return any(
        isinstance(candidate, dict)
        and any(_evidence_available(candidate.get(field)) for field in resolution_fields)
        for candidate in candidates
    )


def _trust_review_gaps(
    section: str,
    raw: Dict[str, Any],
    record: Dict[str, Any],
) -> List[str]:
    gaps: List[str] = []
    money_fields = TRUST_REVIEW_MONEY_FIELDS.get(section, ())
    supplied_money = [
        field for field in money_fields
        if field in raw and not isinstance(raw[field], bool)
    ]
    if section != "streaming" and (
        not supplied_money or any(_amount(raw[field]) is None for field in supplied_money)
    ):
        gaps.append("finite component amount")
    if section == "capital-gain":
        if all(_missing(raw.get(field)) for field in ("asset", "description", "gain_type")):
            gaps.append("capital gain component")
        if all(
            _missing(raw.get(field))
            for field in (
                "discount_eligible", "discount_applied", "discount_percentage",
                "discount_method", "discount_status",
            )
        ):
            gaps.append("CGT discount signal")
    elif section == "franked-distribution":
        if all(
            _missing(raw.get(field))
            for field in ("franking_credit", "franking_credits")
        ):
            gaps.append("franking credit amount")
        if not any(
            _evidence_available(raw.get(field))
            for field in ("statement", "distribution_statement")
        ):
            gaps.append("franked distribution statement")
    elif section == "streaming":
        if all(
            _missing(raw.get(field))
            for field in ("streaming", "specific_entitlement", "recorded_in_character")
        ):
            gaps.append("streaming or specific-entitlement signal")
        if _missing(raw.get("deed_allows_streaming")):
            gaps.append("trust deed streaming signal")
    elif section == "beneficiary-allocation":
        if _missing(raw.get("beneficiary_name")):
            gaps.append("beneficiary identity")
        if all(
            _missing(raw.get(field))
            for field in (
                "component_type", "beneficiary_capital_gain",
                "beneficiary_discounted_capital_gain",
                "beneficiary_franked_distribution", "beneficiary_franking_credits",
            )
        ):
            gaps.append("beneficiary component allocation")
        percentage = raw.get("allocation_percentage")
        if not _missing(percentage):
            amount = _percentage(percentage)
            if amount is None or amount < 0 or amount > 100:
                gaps.append("supported allocation percentage")
        if _missing(raw.get("allocation_basis")):
            gaps.append("allocation basis")
    if not _trust_resolution_present(record, raw):
        gaps.append("streaming resolution evidence")
    if raw.get("_alias_conflicts") or _trust_review_has_alias_conflict(section, raw):
        gaps.append("conflicting review aliases")
    evidence_value = raw.get("evidence", raw.get("records", raw.get("documents")))
    if not _evidence_available(evidence_value):
        gaps.append("evidence")
    _, invalid_sources = taxmate_entity_routing.source_provenance(raw)
    if invalid_sources:
        gaps.append("source provenance")
    checked_at = raw.get("checked_at")
    if (
        "checked_at" in raw
        and not _missing(checked_at)
        and not taxmate_entity_routing.valid_checked_at(checked_at)
    ):
        gaps.append("checked-at provenance")
    return gaps


def _trust_review_rows(
    record: Dict[str, Any],
    parent: Dict[str, Any],
    association_gap: Optional[str],
    section: str,
    aliases: Tuple[str, ...],
    counter: int,
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    raw_items, blank_requested = _collection(
        record,
        aliases,
        preserve_falsey_scalars=True,
        scalar_field=TRUST_REVIEW_SCALAR_FIELDS[section],
    )
    rows: List[Dict[str, Any]] = []
    followups: List[Dict[str, Any]] = []
    if blank_requested:
        followups.append(_line_followup(
            "trust", section, {}, [f"{section.replace('-', ' ')} facts"], True,
            evidence_index,
        ))
        evidence_index += 1
    for raw in raw_items:
        counter += 1
        if not isinstance(raw, dict):
            raw = {TRUST_REVIEW_SCALAR_FIELDS[section]: raw}
        if _missing(raw):
            followups.append(_line_followup(
                "trust", section, {}, [f"{section.replace('-', ' ')} facts"], True,
                evidence_index,
            ))
            evidence_index += 1
            continue
        metadata = {"source_url", "source_urls", "checked_at", "status", "review_status"}
        fact_values = {key: value for key, value in raw.items() if key not in metadata}
        pairs = _identity_facts("trust", parent, record) + list(fact_values.items())
        gaps = [association_gap] if association_gap else []
        gaps.extend(_trust_review_gaps(section, raw, record))
        checked_at = raw.get("checked_at")
        rows.append({
            "number": f"TRUST-{section.upper()}-{counter}",
            "ato_area": f"Trust {section.replace('-', ' ')} review",
            "question": f"Trust {section.replace('-', ' ')} facts",
            "answer": "; ".join(
                f"{key.replace('_', ' ')} {_display(value)}" for key, value in pairs
            ),
            "why_included": (
                "Prep-only trust fact; CGT, franking, streaming, beneficiary allocation, "
                "and final treatment remain accountant decisions."
            ),
            "status": "Accountant review",
            "source_urls": _trust_sources(raw),
            "checked_at": (
                checked_at
                if taxmate_entity_routing.valid_checked_at(checked_at)
                else taxmate_entity_routing.CHECKED_AT
            ),
            "row_kind": f"entity-return-trust-{section}",
            "facts": _facts(pairs),
            "tab_text": f"Trust {section.replace('-', ' ')} facts require accountant review.",
        })
        if gaps:
            valid_sources, invalid_sources = taxmate_entity_routing.source_provenance(raw)
            source_item = {
                "source_urls": valid_sources,
                "invalid_sources": invalid_sources,
                "checked_at": checked_at,
                "conflicts": raw.get("_alias_conflicts"),
            }
            followups.append(_line_followup(
                "trust", section, source_item, list(dict.fromkeys(gaps)), True,
                evidence_index,
            ))
            evidence_index += 1
    return rows, followups, counter, evidence_index


def _partnership_review_sources(section: str, raw: Dict[str, Any]) -> List[str]:
    valid_sources, _ = taxmate_entity_routing.source_provenance(raw)
    return list(dict.fromkeys([
        taxmate_entity_routing.SOURCES["partnership"],
        *PARTNERSHIP_REVIEW_SOURCE_MAP[section],
        *valid_sources,
    ]))


def _numeric_total(value: Any, *, percentages: bool = False) -> Optional[Decimal]:
    values = value.values() if isinstance(value, dict) else value if isinstance(value, list) else []
    parse = _percentage if percentages else _amount
    parsed = [parse(item) for item in values]
    return sum(parsed, Decimal("0")) if parsed and all(item is not None for item in parsed) else None


def _allocation_collection_gaps(raw_items: List[Any]) -> List[str]:
    percentages: List[Any] = []
    generic: List[Any] = []
    allocated_amounts: List[Any] = []
    bases: set[str] = set()
    loss_amounts: List[Decimal] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        for field in ("allocation_basis", "allocation_type"):
            if not _missing(raw.get(field)):
                bases.add(_slug(raw[field]))
        for field in ("loss_amount", "total_loss", "current_year_loss"):
            parsed_loss = _amount(raw.get(field))
            if parsed_loss is not None:
                loss_amounts.append(parsed_loss)
        if "allocated_loss" in raw:
            allocated_amounts.append(raw["allocated_loss"])
        for field in ("allocation_percentage", "share_percentage", "percentage"):
            if field in raw:
                percentages.append(raw[field])
                break
        for field in ("allocation", "allocations"):
            if field not in raw:
                continue
            value = raw[field]
            generic.extend(value.values() if isinstance(value, dict) else value if isinstance(value, list) else [value])
            break
    gaps: List[str] = []
    if percentages and _numeric_total(percentages, percentages=True) != Decimal("100"):
        gaps.append("conflicting loss allocation")
    if generic:
        total = _numeric_total(generic, percentages=not bases or next(iter(bases), "") in {
            "percentage", "percent", "share-percentage",
        })
        if not bases:
            if total != Decimal("100"):
                gaps.append("conflicting loss allocation")
            gaps.append("loss allocation basis")
        elif len(bases) != 1:
            gaps.extend(("conflicting loss allocation", "loss allocation basis"))
        elif next(iter(bases)) in {"percentage", "percent", "share-percentage"}:
            if total != Decimal("100"):
                gaps.append("conflicting loss allocation")
        elif next(iter(bases)) in {"amount", "dollar", "dollars"}:
            if not loss_amounts:
                gaps.append("loss amount for allocation reconciliation")
            elif len(set(loss_amounts)) != 1 or total != loss_amounts[0]:
                gaps.append("conflicting loss allocation")
        else:
            gaps.append("loss allocation basis")
    if allocated_amounts:
        allocated_total = _numeric_total(allocated_amounts)
        if not loss_amounts:
            gaps.append("loss amount for allocation reconciliation")
        elif (
            allocated_total is None
            or len(set(loss_amounts)) != 1
            or allocated_total != loss_amounts[0]
        ):
            gaps.append("conflicting loss allocation")
    return gaps


def _partnership_review_gaps(section: str, raw: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    if section == "loss":
        money = [
            raw[field] for field in (
                "amount", "current_year_loss", "prior_year_loss", "carried_forward_loss",
            ) if field in raw
        ]
        if not money or any(_amount(value) is None for value in money):
            gaps.append("finite partnership loss amount")
    elif section == "loss-allocation":
        if all(_missing(raw.get(field)) for field in (
            "allocation", "allocations", "allocation_percentages", "partner_percentages",
            "share_percentages", "allocated_loss", "allocation_percentage",
            "share_percentage", "percentage",
        )):
            gaps.append("loss allocation")
        per_partner_value = any(
            not _missing(raw.get(field))
            for field in (
                "allocated_loss", "allocation_percentage", "share_percentage", "percentage",
            )
        ) or any(
            field in raw and not isinstance(raw[field], (dict, list))
            for field in ("allocation", "allocations")
        )
        if per_partner_value and all(
            _missing(raw.get(field)) for field in ("partner", "partner_name")
        ):
            gaps.append("allocation partner")
        for field in ("allocation_percentages", "partner_percentages", "share_percentages"):
            if field in raw:
                total = _numeric_total(raw[field], percentages=True)
                if total is None or total != Decimal("100"):
                    gaps.append("conflicting loss allocation")
        if raw.get("conflicts") or raw.get("_alias_conflicts"):
            gaps.append("conflicting loss allocation")
    elif section == "gst-bas":
        if all(_missing(raw.get(field)) for field in (
            "gst_registered", "gst_registration_status", "registration_date",
        )):
            gaps.append("GST registration signal")
        if all(_missing(raw.get(field)) for field in ("bas_period", "reporting_period", "period")):
            gaps.append("BAS reporting period")
        if all(_missing(raw.get(field)) for field in ("bas_overlap", "gst_bas_interaction", "overlap")):
            gaps.append("BAS overlap signal")
        elif any(_review_signal(raw.get(field)) for field in ("bas_overlap", "gst_bas_interaction", "overlap")):
            gaps.append("BAS overlap review")
    elif section == "psi":
        psi_signal_fields = ("psi", "psi_indicator", "personal_services_income")
        supplied_signals = [raw[field] for field in psi_signal_fields if field in raw]
        if not supplied_signals:
            gaps.append("PSI indicator")
        elif all(_missing(value) for value in supplied_signals) or any(
            _review_signal(raw.get(field))
            for field in psi_signal_fields
        ):
            gaps.append("PSI uncertainty")
    elif all(_missing(raw.get(field)) for field in (
        "business_structure", "structure", "entity_structure", "structure_indicator",
    )):
        gaps.append("business structure indicator")
    elif any(_status_review_signal(raw.get(field)) for field in (
        "business_structure", "structure", "entity_structure", "structure_indicator",
    )):
        gaps.append("business structure uncertainty")
    if raw.get("_alias_conflicts") and section != "loss-allocation":
        gaps.append("conflicting review aliases")
    evidence_value = raw.get("evidence", raw.get("records", raw.get("documents")))
    if not _evidence_available(evidence_value):
        gaps.append("evidence")
    _, invalid_sources = taxmate_entity_routing.source_provenance(raw)
    if invalid_sources:
        gaps.append("source provenance")
    checked_at = raw.get("checked_at")
    if "checked_at" in raw and not _missing(checked_at) and not taxmate_entity_routing.valid_checked_at(checked_at):
        gaps.append("checked-at provenance")
    return list(dict.fromkeys(gaps))


def _partnership_review_rows(
    record: Dict[str, Any],
    parent: Dict[str, Any],
    association_gap: Optional[str],
    section: str,
    aliases: Tuple[str, ...],
    counter: int,
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    raw_items, blank_requested = _collection(record, aliases, preserve_falsey_scalars=True)
    allocation_gaps = (
        _allocation_collection_gaps(raw_items) if section == "loss-allocation" else []
    )
    rows: List[Dict[str, Any]] = []
    followups: List[Dict[str, Any]] = []
    if blank_requested:
        followups.append(_line_followup(
            "partnership", section, {}, [f"{section.replace('-', ' ')} facts"], True,
            evidence_index,
        ))
        evidence_index += 1
    for raw in raw_items:
        counter += 1
        if not isinstance(raw, dict):
            raw = {PARTNERSHIP_REVIEW_SCALAR_FIELDS[section]: raw}
        metadata = {"source_url", "source_urls", "checked_at", "status", "review_status"}
        pairs = _identity_facts("partnership", parent, record) + [
            (key, value) for key, value in raw.items() if key not in metadata
        ]
        checked_at = raw.get("checked_at")
        rows.append({
            "number": f"PARTNERSHIP-{section.upper()}-{counter}",
            "ato_area": f"Partnership {section.replace('-', ' ')} review",
            "question": f"Partnership {section.replace('-', ' ')} facts",
            "answer": "; ".join(
                f"{key.replace('_', ' ')} {_display(value)}" for key, value in pairs
            ),
            "why_included": (
                "Prep-only partnership fact; loss allocation, GST/BAS, PSI, structure, "
                "and final treatment remain accountant decisions."
            ),
            "status": "Accountant review",
            "source_urls": _partnership_review_sources(section, raw),
            "checked_at": (
                checked_at if taxmate_entity_routing.valid_checked_at(checked_at)
                else taxmate_entity_routing.CHECKED_AT
            ),
            "row_kind": f"entity-return-partnership-{section}",
            "facts": _facts(pairs),
            "tab_text": f"Partnership {section.replace('-', ' ')} facts require accountant review.",
        })
        gaps = ([association_gap] if association_gap else []) + _partnership_review_gaps(section, raw)
        gaps.extend(allocation_gaps)
        if gaps:
            valid_sources, invalid_sources = taxmate_entity_routing.source_provenance(raw)
            source_item = {
                "source_urls": valid_sources,
                "invalid_sources": invalid_sources,
                "checked_at": checked_at,
            }
            followups.append(_line_followup(
                "partnership", section, source_item, list(dict.fromkeys(gaps)), True,
                evidence_index,
            ))
            evidence_index += 1
    return rows, followups, counter, evidence_index


def route_entity_worksheets(
    answers: Dict[str, Any],
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    grouped, _ = taxmate_entity_routing.entity_records(copy.deepcopy(answers))
    sections = {"company_items": [], "trust_items": [], "partnership_items": []}
    evidence: List[Dict[str, Any]] = []
    counters = {
        "company-income": 0, "company-deduction": 0,
        "partnership-income": 0, "partnership-deduction": 0,
        "partnership-trading_stock": 0, "partnership-capital_allowance_items": 0,
        **{f"company-{section}": 0 for section in COMPANY_REVIEW_COLLECTIONS},
        **{f"trust-{section}": 0 for section in TRUST_REVIEW_COLLECTIONS},
        **{f"partnership-{section}": 0 for section in PARTNERSHIP_REVIEW_COLLECTIONS},
    }
    evidence_index = 1
    for kind in ("company", "trust", "partnership"):
        records = [record for record in grouped[kind] if isinstance(record, dict)]
        for record_number, record in enumerate(records, start=1):
            if not _record_has_worksheet(kind, record):
                continue
            parent, association_gap = _parent_for(kind, record, records)
            context_rows, context_followups, evidence_index = _context_rows(
                kind, record_number, record, parent, association_gap, evidence_index,
            )
            sections[f"{kind}_items"].extend(context_rows)
            evidence.extend(context_followups)
            company_review_record = record
            for worksheet in (() if kind == "trust" else ("income", "deduction")):
                raw_items, blank_requested = _collection(record, COLLECTION_ALIASES[worksheet])
                migrated_amounts: List[Decimal] = []
                migrated_valid = True
                migrated_present = False
                if kind == "company" and worksheet == "income":
                    (
                        raw_items,
                        migrated_reviews,
                        migrated_amounts,
                        migrated_valid,
                    ) = _company_deferred_review_items(raw_items)
                    company_review_record = _merge_company_review_items(
                        company_review_record, migrated_reviews,
                    )
                    migrated_present = any(migrated_reviews.values())
                key = f"{kind}-{worksheet}"
                if blank_requested:
                    evidence.append(_line_followup(
                        kind, worksheet, {}, [f"{worksheet} items"], False, evidence_index,
                    ))
                    evidence_index += 1
                rows, followups, amounts, all_valid, counters[key], evidence_index = _line_rows(
                    kind, worksheet, raw_items, parent, record, association_gap,
                    counters[key], evidence_index,
                )
                amounts.extend(migrated_amounts)
                if migrated_present:
                    all_valid = migrated_valid and (all_valid if raw_items else True)
                sections[f"{kind}_items"].extend(rows)
                evidence.extend(followups)
                total_rows, total_followups, evidence_index = _total_rows(
                    kind, worksheet, record_number, record, parent, amounts,
                    all_valid, evidence_index,
                )
                sections[f"{kind}_items"].extend(total_rows)
                evidence.extend(total_followups)

            if kind == "trust":
                for section, aliases in TRUST_REVIEW_COLLECTIONS.items():
                    key = f"trust-{section}"
                    rows, followups, counters[key], evidence_index = _trust_review_rows(
                        record, parent, association_gap, section, aliases,
                        counters[key], evidence_index,
                    )
                    sections["trust_items"].extend(rows)
                    evidence.extend(followups)
            elif kind == "partnership":
                for field in ("trading_stock", "capital_allowance_items"):
                    rows, followups, counters[f"partnership-{field}"], evidence_index = _special_rows(
                        record, parent, association_gap, field,
                        counters[f"partnership-{field}"], evidence_index,
                    )
                    sections["partnership_items"].extend(rows)
                    evidence.extend(followups)
                for section, aliases in PARTNERSHIP_REVIEW_COLLECTIONS.items():
                    key = f"partnership-{section}"
                    rows, followups, counters[key], evidence_index = _partnership_review_rows(
                        record, parent, association_gap, section, aliases,
                        counters[key], evidence_index,
                    )
                    sections["partnership_items"].extend(rows)
                    evidence.extend(followups)
            else:
                for section, aliases in COMPANY_REVIEW_COLLECTIONS.items():
                    key = f"company-{section}"
                    rows, followups, counters[key], evidence_index = _company_review_rows(
                        company_review_record, parent, association_gap, section, aliases,
                        counters[key], evidence_index,
                    )
                    sections["company_items"].extend(rows)
                    evidence.extend(followups)
    return sections, evidence
