#!/usr/bin/env python3
"""TaxMate Australia individual intake command."""

from __future__ import annotations

import argparse
import calendar
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import taxmate_taxpack
import taxmate_handoff
import taxmate_entity_routing


DEFAULT_INCOME_YEAR = "2025-26"
SUPPORTED_WFH_START = date(2025, 7, 1)
SUPPORTED_WFH_END = date(2026, 6, 30)
WFH_FIXED_RATE_2025_26 = 0.70
REVIEWABLE_ABN_FIELDS = (
    "abn_income",
    "abn_expenses",
    "abn",
    "business_abn",
    "business_name",
    "business_activity",
    "business_start_date",
    "business_end_date",
    "business_record_system",
    "business_income_streams",
    "business_expense_categories",
    "business_private_apportionment",
    "business_home_use",
    "business_motor_vehicle",
    "business_depreciation",
    "business_capital_expense",
    "business_loss",
    "business_vs_hobby",
    "business_non_commercial_loss",
)
REVIEWABLE_BAS_FIELDS = (
    "bas_period",
    "gst_collected",
    "gst_credits",
    "gst_registration_date",
    "gst_accounting_basis",
    "bas_period_coverage",
    "gst_free_sales",
    "input_taxed_sales",
    "bas_adjustments",
    "payg_instalments",
    "payg_withholding",
    "tax_invoice_evidence",
)
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
REVIEWABLE_PAYG_FIELDS = (
    "payg_gross",
    "payg_withheld",
    "main_occupation",
    "payg_income_statements",
    "payg_statements",
    "payg_employer_name",
    "payg_employer_abn",
    "payg_occupation",
    "payg_allowances",
    "payg_rfba",
    "payg_resc",
    "payg_lump_sum_a",
    "payg_lump_sum_b",
    "payg_lump_sum_d",
    "payg_lump_sum_e",
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
REVIEWABLE_PSI_FIELDS = (
    "psi_income",
    "psi_income_type",
    "psi_contract_evidence",
    "psi_results_test",
    "psi_80_percent_test",
    "psi_unrelated_clients_test",
    "psi_employment_test",
    "psi_business_premises_test",
    "psi_psb_determination",
    "psi_attribution_entity",
    "psi_deductions",
    "psi_business_structure",
)
REVIEWABLE_CRYPTO_FIELDS = (
    "crypto_event_type",
    "crypto_exchange_or_wallet",
    "crypto_asset",
    "crypto_quantity",
    "crypto_acquired_date",
    "crypto_disposed_date",
    "crypto_cost_base",
    "crypto_capital_proceeds",
    "crypto_rewards_income",
    "crypto_transfer_between_wallets",
    "crypto_wallet_records",
    "crypto_ownership_entity",
    "crypto_business_use",
    "crypto_private_use",
)
REVIEWABLE_RENTAL_PROPERTY_FIELDS = (
    "rental_property_address",
    "rental_property_ownership",
    "rental_property_income",
    "rental_property_interest",
    "rental_property_repairs",
    "rental_property_capital_works",
    "rental_property_depreciation",
    "rental_property_other_expenses",
    "rental_property_private_use",
    "rental_property_private_use_days",
    "rental_property_available_days",
    "rental_property_records",
    "rental_property_net_loss",
)
REVIEWABLE_CGT_FIELDS = (
    "cgt_summary",
    "cgt_event_type",
    "cgt_asset",
    "cgt_asset_description",
    "cgt_owner",
    "cgt_acquisition_date",
    "cgt_disposal_date",
    "cgt_proceeds",
    "cgt_cost_base",
    "cgt_incidental_costs",
    "cgt_losses",
    "cgt_current_year_losses",
    "cgt_carried_forward_losses",
    "cgt_discount_claim",
    "cgt_discount_timing",
    "cgt_discount_eligibility",
    "cgt_foreign_resident_discount",
    "cgt_records",
    "cgt_items",
    "cgt_no_cgt",
    "cgt_exemption_flag",
    "cgt_discount_flag",
    "cgt_concession_flag",
    "cgt_mixed_use",
    "cgt_business_use",
    "cgt_private_use",
    "cgt_main_residence_claim",
    "cgt_main_residence_ownership_period",
    "cgt_main_residence_occupancy_period",
    "cgt_main_residence_rental_business_use",
    "cgt_main_residence_absence_periods",
    "cgt_main_residence_spouse_conflict",
    "cgt_main_residence_property_records",
)
REVIEWABLE_INVESTMENT_FIELDS = (
    "investment_interest_items",
    "investment_dividend_items",
    "investment_distribution_items",
    "trust_distribution_items",
)
REVIEWABLE_PARTNERSHIP_TRUST_FIELDS = (
    "partnership_share_items",
    "partnership_statement_items",
    "trust_share_items",
    "trust_beneficiary_statement_items",
)
MEDICARE_PRIVATE_HEALTH_BASE_FIELDS = frozenset(
    {
        "spouse_had",
        "dependant_children",
        "private_health_cover",
        "private_health_medicare",
        "medicare_private_health",
        "private_health",
        "private_health_statements",
        "private_health_statement",
        "medicare_levy",
        "medicare_levy_surcharge",
        "mls",
        "spouse",
        "spouse_details",
        "dependants",
        "dependant_details",
    }
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
COMPLEX_PAYMENT_FLAT_FIELD_KEYS = {
    "etp_statement": "statement",
    "etp_taxable_component": "taxable_component",
    "etp_tax_free_component": "tax_free_component",
    "etp_tax_withheld": "tax_withheld",
    "lump_sum_arrears_statement": "statement",
    "lump_sum_arrears_amount": "amount",
    "lump_sum_arrears_years": "payment_years",
    "lump_sum_arrears_tax_withheld": "tax_withheld",
    "super_income_statement": "statement",
    "super_income_payment_kind": "payment_kind",
    "super_lump_sum_taxable_component": "taxable_component",
    "super_lump_sum_tax_free_component": "tax_free_component",
    "super_income_stream_taxable_amount": "taxable_amount",
    "super_income_tax_withheld": "tax_withheld",
}
COMPLEX_PAYMENT_AMOUNT_FIELDS = (
    "taxable_component",
    "tax_free_component",
    "tax_withheld",
    "amount",
    "taxable_amount",
)
COMPLEX_PAYMENT_SOURCE_KEY_FACTS = (
    "statement",
    "payer",
    "payment_type",
    "payment_date",
    "taxable_component",
    "tax_free_component",
    "tax_withheld",
    "code",
    "amount",
    "payment_years",
    "fund",
    "payment_kind",
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
    "dont have",
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
INVESTMENT_INTEREST_AMOUNT_FIELDS = ("amount", "tfn_withheld")
INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS = ("amount", "dividend_amount", "cash_amount")
INVESTMENT_DIVIDEND_AMOUNT_FIELDS = (
    *INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS,
    "franked_amount",
    "unfranked_amount",
    "franking_credit",
    "tfn_withheld",
)
INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS = ("amount", "distribution_amount")
INVESTMENT_DISTRIBUTION_AMOUNT_FIELDS = (
    *INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS,
    "taxable_amount",
    "capital_gain",
    "foreign_income",
    "foreign_tax_offset",
    "franking_credit",
    "tfn_withheld",
)
INVESTMENT_TRUST_AMOUNT_FIELDS = (
    "distribution_amount",
    "franked_distribution",
    "franking_credit",
    "capital_gain",
    "foreign_income",
    "foreign_tax_offset",
    "non_assessable_payment",
)
INVESTMENT_INTEREST_REQUIRED_AMOUNT_GROUPS = (("amount",),)
INVESTMENT_DIVIDEND_REQUIRED_AMOUNT_GROUPS = (
    INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS,
    ("franked_amount", "unfranked_amount"),
)
INVESTMENT_DISTRIBUTION_REQUIRED_AMOUNT_GROUPS = (
    (
        *INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS,
        "taxable_amount",
        "capital_gain",
        "foreign_income",
    ),
)
INVESTMENT_TRUST_REQUIRED_AMOUNT_GROUPS = (
    (
        "distribution_amount",
        "franked_distribution",
        "capital_gain",
        "foreign_income",
        "non_assessable_payment",
    ),
)
INVESTMENT_ZERO_COMPONENT_AMOUNT_FIELDS = (
    "franked_amount",
    "unfranked_amount",
    "franked_distribution",
    "capital_gain",
    "foreign_income",
    "franking_credit",
    "foreign_tax_offset",
    "non_assessable_payment",
)
INVESTMENT_ITEM_ALIASES = {
    "interest_items": ("interest_items", "investment_interest_items", "bank_interest_items"),
    "dividend_items": ("dividend_items", "investment_dividend_items"),
    "distribution_items": ("distribution_items", "investment_distribution_items", "managed_fund_distribution_items"),
    "trust_distribution_items": ("trust_distribution_items",),
}
INVESTMENT_AGGREGATE_ALIASES = {
    "interest_income": ("interest_income", "gross_interest"),
    "dividend_income": ("dividend_income", "investment_distribution_income"),
}
INVESTMENT_STATEMENT_MISSING_PHRASES = (
    "do not have",
    "don't have",
    "dont have",
    "missing statement",
    "statement missing",
    "statement not held",
    "statement not available",
    "statement not provided",
    "statement not received",
    "no statement",
    "not provided",
    "not received",
    "not supplied",
    "not confirmed",
)
INVESTMENT_FRANKING_UNCERTAIN_PHRASES = (
    "unknown",
    "uncertain",
    "not confirmed",
    "not sure",
    "maybe",
    "unclear",
)
INVESTMENT_SOURCES = [
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/investment-income",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/investing-in-bank-accounts-and-income-bonds",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments/trust-non-assessable-payments-cgt-event-e4",
]
ESS_FLAT_AMOUNT_FIELDS = tuple(f"ess_{field}" for field in ESS_AMOUNT_FIELDS)
ESS_ITEM_SIGNAL_FIELDS = ("employer", "scheme", "provider", *ESS_AMOUNT_FIELDS)
ESS_SOURCE_KEY_FACTS = ("statement", *ESS_ITEM_SIGNAL_FIELDS)
ESS_STATEMENT_MISSING_PHRASES = (
    "do not have",
    "don't have",
    "dont have",
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
GENERIC_FIELD_ABSENCE_PHRASES = (
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
PAYMENT_DECLINE_SIGNAL_KEY = "_decline_signals"
ESS_DECLINE_SIGNAL_KEY = "_decline_signals"
PAYG_AMOUNT_FIELDS = (
    "gross",
    "withheld",
    "allowances",
    "rfba",
    "resc",
    "lump_sum_a",
    "lump_sum_b",
    "lump_sum_d",
    "lump_sum_e",
)
PAYG_FLAT_AMOUNT_FIELDS = (
    "payg_gross",
    "payg_withheld",
    "payg_allowances",
    "payg_rfba",
    "payg_resc",
    "payg_lump_sum_a",
    "payg_lump_sum_b",
    "payg_lump_sum_d",
    "payg_lump_sum_e",
)
PAYG_REQUIRED_AMOUNT_FIELDS = ("gross", "withheld")
PAYG_SUPPLEMENTAL_FIELDS = (
    "payer",
    "abn",
    "occupation",
    "allowances",
    "rfba",
    "resc",
    "lump_sum_a",
    "lump_sum_b",
    "lump_sum_d",
    "lump_sum_e",
)
PAYG_SOURCE_KEY_FACTS = (
    "payg_income_statements",
    "payg_statements",
    "income_statements",
    "payg_items",
    "employers",
    "statement",
    "income_statement",
    "payment_summary",
    "statement_evidence",
    "finalised",
    "payer",
    "payer_name",
    "employer",
    "employer_name",
    "abn",
    "employer_abn",
    "payer_abn",
    "occupation",
    "main_occupation",
    "job_title",
    "gross",
    "salary_wages",
    "gross_salary_wages",
    "gross_wages",
    "withheld",
    "tax_withheld",
    "payg_withheld",
    "amount_withheld",
    "allowance",
    "allowances",
    "total_allowances",
    "rfba",
    "reportable_fringe_benefits",
    "reportable_fringe_benefits_amount",
    "resc",
    "reportable_employer_super",
    "reportable_employer_super_contributions",
    "lump_sum",
    "lump_sums",
    "lump_sum_a",
    "lump_sum_a_amount",
    "lump_sum_b",
    "lump_sum_b_amount",
    "lump_sum_d",
    "lump_sum_d_amount",
    "lump_sum_e",
    "lump_sum_e_amount",
    "finalized",
    "tax_ready",
    "income_statement_finalised",
)
PAYG_BOOLEAN_FIELDS = ("statement", "finalised")
PAYG_FIELD_ALIASES = {
    "payer": ("payer", "employer", "employer_name", "payer_name"),
    "abn": ("abn", "employer_abn", "payer_abn"),
    "occupation": ("occupation", "main_occupation", "job_title"),
    "gross": ("gross", "gross_salary_wages", "salary_wages", "gross_wages", "payg_gross"),
    "withheld": ("withheld", "tax_withheld", "payg_withheld", "amount_withheld"),
    "allowances": ("allowances", "allowance", "total_allowances"),
    "rfba": ("rfba", "reportable_fringe_benefits", "reportable_fringe_benefits_amount"),
    "resc": ("resc", "reportable_employer_super", "reportable_employer_super_contributions"),
    "lump_sum_a": ("lump_sum_a", "lump_sum_a_amount"),
    "lump_sum_b": ("lump_sum_b", "lump_sum_b_amount"),
    "lump_sum_d": ("lump_sum_d", "lump_sum_d_amount"),
    "lump_sum_e": ("lump_sum_e", "lump_sum_e_amount"),
    "statement": ("statement", "income_statement", "payment_summary", "statement_evidence"),
    "finalised": ("finalised", "finalized", "tax_ready", "income_statement_finalised"),
}
PAYG_ALIAS_TO_FIELD = {
    alias: canonical
    for canonical, aliases in PAYG_FIELD_ALIASES.items()
    for alias in aliases
}
PAYG_FLAT_FIELD_KEYS = {
    "payg_employer_name": "payer",
    "payg_employer_abn": "abn",
    "main_occupation": "occupation",
    "payg_occupation": "occupation",
    "payg_gross": "gross",
    "payg_withheld": "withheld",
    "payg_allowances": "allowances",
    "payg_rfba": "rfba",
    "payg_resc": "resc",
    "payg_lump_sum_a": "lump_sum_a",
    "payg_lump_sum_b": "lump_sum_b",
    "payg_lump_sum_d": "lump_sum_d",
    "payg_lump_sum_e": "lump_sum_e",
}
PAYG_NESTED_BASE_FIELD_KEYS = {
    "payer": "payg_employer_name",
    "abn": "payg_employer_abn",
    "occupation": "payg_occupation",
    "gross": "payg_gross",
    "withheld": "payg_withheld",
    "allowances": "payg_allowances",
    "rfba": "payg_rfba",
    "resc": "payg_resc",
    "lump_sum_a": "payg_lump_sum_a",
    "lump_sum_b": "payg_lump_sum_b",
    "lump_sum_d": "payg_lump_sum_d",
    "lump_sum_e": "payg_lump_sum_e",
}
PAYG_ITEM_ALIASES = (
    "payg_income_statements",
    "payg_statements",
    "income_statements",
    "payg_items",
    "employers",
)
PAYG_NESTED_KEYS = ("payg", "payg_income", "salary_wages")
PAYG_DECLINE_SIGNAL_KEY = "_decline_signals"
PAYG_DECLINE_PHRASES = (
    "no payg",
    "no salary",
    "no salary or wages",
    "no wages",
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
PAYG_STATEMENT_MISSING_PHRASES = (
    "do not have",
    "don't have",
    "dont have",
    "no payg statement",
    "no payg statements",
    "no payment summary",
    "missing statement",
    "statement missing",
    "income statement missing",
    "income statement not held",
    "income statement not available",
    "income statement not provided",
    "income statement not received",
    "payment summary not held",
    "payment summary not available",
    "payment summary not provided",
    "payment summary not received",
    "not held",
    "not available",
    "not provided",
    "not received",
    "not supplied",
    "not confirmed",
)
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
FOREIGN_INCOME_SOURCE_KEY_FACTS = FOREIGN_INCOME_SIGNAL_FIELDS
FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS = ("foreign_tax_offset_claim", "foreign_employment_exempt_claim")
FOREIGN_INCOME_FLAT_BOOLEAN_FIELDS = ("foreign_income_tax_offset_claim", "foreign_employment_exempt_claim")
FOREIGN_INCOME_FLAT_FIELD_KEYS = {
    "foreign_income_statement": "statement",
    "foreign_income_country": "country",
    "foreign_income_type": "income_type",
    "foreign_income_amount": "amount",
    "foreign_tax_paid": "foreign_tax_paid",
    "foreign_income_exchange_rate": "exchange_rate",
    "foreign_income_residency_status": "residency_status",
    "foreign_income_tax_offset_claim": "foreign_tax_offset_claim",
    "foreign_employment_exempt_claim": "foreign_employment_exempt_claim",
}
FOREIGN_INCOME_STATEMENT_MISSING_PHRASES = (
    "do not have",
    "don't have",
    "dont have",
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
FOREIGN_INCOME_DECLINE_SIGNAL_KEY = "_decline_signals"
PSI_AMOUNT_FIELDS = ("income",)
PSI_FLAT_AMOUNT_FIELDS = ("psi_income",)
PSI_BOOLEAN_FIELDS = (
    "results_test",
    "eighty_percent_test",
    "unrelated_clients_test",
    "employment_test",
    "business_premises_test",
    "psb_determination",
)
PSI_FLAT_BOOLEAN_FIELDS = (
    "psi_results_test",
    "psi_80_percent_test",
    "psi_unrelated_clients_test",
    "psi_employment_test",
    "psi_business_premises_test",
    "psi_psb_determination",
)
PSI_SIGNAL_FIELDS = (
    "income",
    "income_type",
    "occupation",
    "client",
    "contract_evidence",
    "results_test",
    "eighty_percent_test",
    "unrelated_clients_test",
    "employment_test",
    "business_premises_test",
    "psb_determination",
    "attribution_entity",
    "deductions",
    "business_structure",
)
PSI_DECLINE_PHRASES = (
    "no psi",
    "no personal services income",
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
PSI_DECLINE_SIGNAL_KEY = "_decline_signals"
PSI_SOURCE_KEY_FACTS = (
    "income",
    "income_type",
    "occupation",
    "client",
    "contract_evidence",
    "results_test",
    "eighty_percent_test",
    "unrelated_clients_test",
    "employment_test",
    "business_premises_test",
    "psb_determination",
    "attribution_entity",
    "deductions",
    "business_structure",
)
CRYPTO_AMOUNT_FIELDS = ("quantity", "cost_base", "capital_proceeds", "rewards_income")
CRYPTO_FLAT_AMOUNT_FIELDS = (
    "crypto_quantity",
    "crypto_cost_base",
    "crypto_capital_proceeds",
    "crypto_rewards_income",
)
CRYPTO_DATE_FIELDS = ("acquired_date", "disposed_date")
CRYPTO_FLAT_DATE_FIELDS = ("crypto_acquired_date", "crypto_disposed_date")
CRYPTO_USE_CONTEXT_FIELDS = ("business_use", "private_use")
CRYPTO_BOOLEAN_FIELDS = ("transfer_between_wallets", *CRYPTO_USE_CONTEXT_FIELDS)
CRYPTO_FLAT_BOOLEAN_FIELDS = tuple(f"crypto_{field}" for field in CRYPTO_BOOLEAN_FIELDS)
CRYPTO_IDENTITY_FIELDS = ("exchange_or_wallet", "asset", "ownership_entity")
CRYPTO_IDENTITY_ABSENCE_CONTEXTS = {
    "exchange_or_wallet": ("exchange", "exchanges", "wallet", "wallets", "platform", "platforms"),
    "asset": ("asset", "assets"),
    "ownership_entity": ("owner", "owners", "ownership", "entity", "entities"),
}
CRYPTO_IDENTITY_ABSENCE_EXACT_PHRASES = {
    "exchange_or_wallet": ("no exchange", "no wallet"),
    "asset": ("no asset", "no assets"),
    "ownership_entity": ("no ownership entity", "no owner", "no entity"),
}
CRYPTO_SIGNAL_FIELDS = (
    "event_type",
    "exchange_or_wallet",
    "asset",
    "quantity",
    "acquired_date",
    "disposed_date",
    "cost_base",
    "capital_proceeds",
    "rewards_income",
    "transfer_between_wallets",
    "wallet_records",
    "ownership_entity",
    "business_use",
    "private_use",
)
CRYPTO_SOURCE_KEY_FACTS = (
    "event_type",
    "exchange_or_wallet",
    "asset",
    "quantity",
    "acquired_date",
    "disposed_date",
    "cost_base",
    "capital_proceeds",
    "rewards_income",
    "transfer_between_wallets",
    "wallet_records",
    "ownership_entity",
    "business_use",
    "private_use",
)
CRYPTO_ITEM_PARENT_CONTEXT_FIELDS = ("event_type", "asset", "exchange_or_wallet", "ownership_entity")
CRYPTO_DECLINE_PHRASES = (
    "no crypto",
    "no crypto asset",
    "no crypto assets",
    "no cryptocurrency",
    "no cryptocurrencies",
    "no digital currency",
    "no digital currencies",
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
CRYPTO_FIELD_ABSENCE_PHRASES = (
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
    "no staking rewards",
    "no crypto rewards",
)
BOOLEAN_UNCERTAIN_PHRASES = frozenset({"maybe", "possibly", "unclear", "not clear"})
CRYPTO_DECLINE_SIGNAL_KEY = "_decline_signals"
RENTAL_PROPERTY_FLAT_FIELD_KEYS = {
    "rental_property_address": "address",
    "rental_property_ownership": "ownership",
    "rental_property_income": "income",
    "rental_property_interest": "interest",
    "rental_property_repairs": "repairs",
    "rental_property_capital_works": "capital_works",
    "rental_property_depreciation": "depreciation",
    "rental_property_other_expenses": "other_expenses",
    "rental_property_private_use": "private_use",
    "rental_property_private_use_days": "private_use_days",
    "rental_property_available_days": "available_days",
    "rental_property_records": "records",
    "rental_property_net_loss": "net_loss",
}
RENTAL_PROPERTY_AMOUNT_FIELDS = (
    "income",
    "interest",
    "repairs",
    "capital_works",
    "depreciation",
    "other_expenses",
    "private_use_days",
    "available_days",
    "net_loss",
)
RENTAL_PROPERTY_EXPENSE_FIELDS = ("interest", "repairs", "capital_works", "depreciation", "other_expenses")
RENTAL_PROPERTY_FLAT_AMOUNT_FIELDS = tuple(
    key for key, nested in RENTAL_PROPERTY_FLAT_FIELD_KEYS.items() if nested in RENTAL_PROPERTY_AMOUNT_FIELDS
)
RENTAL_PROPERTY_SOURCE_KEY_FACTS = (
    "address",
    "ownership",
    "income",
    "interest",
    "repairs",
    "capital_works",
    "depreciation",
    "other_expenses",
    "private_use",
    "private_use_days",
    "available_days",
    "records",
    "net_loss",
)
RENTAL_PROPERTY_DECLINE_PHRASES = (
    "no rental",
    "no rental property",
    "no rental properties",
    "no investment property",
    "no investment properties",
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
RENTAL_PROPERTY_FIELD_ABSENCE_PHRASES = (
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
    "none",
)
RENTAL_PROPERTY_NET_LOSS_FALSE_PHRASES = frozenset(
    {
        "false",
        "no",
        "n",
        "0",
        "off",
        "unchecked",
        "no loss",
        "no net loss",
        "no rental loss",
        "not a loss",
    }
)
RENTAL_PROPERTY_DECLINE_SIGNAL_KEY = "_decline_signals"
CGT_FLAT_FIELD_KEYS = {
    "cgt_summary": "summary",
    "cgt_event_type": "event_type",
    "cgt_asset": "asset",
    "cgt_asset_description": "asset",
    "cgt_owner": "owner",
    "cgt_acquisition_date": "acquisition_date",
    "cgt_disposal_date": "disposal_date",
    "cgt_proceeds": "proceeds",
    "cgt_cost_base": "cost_base",
    "cgt_incidental_costs": "incidental_costs",
    "cgt_losses": "losses",
    "cgt_current_year_losses": "current_year_losses",
    "cgt_carried_forward_losses": "carried_forward_losses",
    "cgt_discount_claim": "discount_claim",
    "cgt_discount_timing": "discount_timing",
    "cgt_discount_eligibility": "discount_eligibility",
    "cgt_foreign_resident_discount": "foreign_resident_discount",
    "cgt_records": "records",
    "cgt_no_cgt": "no_cgt",
    "cgt_exemption_flag": "exemption_flag",
    "cgt_discount_flag": "discount_flag",
    "cgt_concession_flag": "concession_flag",
    "cgt_concession_type": "concession_type",
    "cgt_business_asset": "business_asset",
    "cgt_active_asset": "active_asset",
    "cgt_entity_affiliate_connected_entity": "entity_affiliate_connected_entity",
    "cgt_retirement_exemption": "retirement_exemption",
    "cgt_rollover": "rollover",
    "cgt_15_year_exemption": "fifteen_year_exemption",
    "cgt_fifteen_year_exemption": "fifteen_year_exemption",
    "cgt_50_percent_active_asset_reduction": "active_asset_reduction_50",
    "cgt_active_asset_reduction_50": "active_asset_reduction_50",
    "cgt_concession_evidence": "concession_evidence",
    "cgt_mixed_use": "mixed_use",
    "cgt_business_use": "business_use",
    "cgt_private_use": "private_use",
    "cgt_main_residence_claim": "main_residence_claim",
    "cgt_main_residence_ownership_period": "main_residence_ownership_period",
    "cgt_main_residence_occupancy_period": "main_residence_occupancy_period",
    "cgt_main_residence_rental_business_use": "main_residence_rental_business_use",
    "cgt_main_residence_absence_periods": "main_residence_absence_periods",
    "cgt_main_residence_spouse_conflict": "main_residence_spouse_conflict",
    "cgt_main_residence_property_records": "main_residence_property_records",
}
CGT_NESTED_FIELD_KEYS = {
    "asset_description": "asset",
    "cgt_asset_description": "asset",
    "acquired_date": "acquisition_date",
    "disposed_date": "disposal_date",
    "capital_proceeds": "proceeds",
    "incidental_cost": "incidental_costs",
    "capital_losses": "losses",
    "loss": "losses",
    "current_year_losses": "current_year_losses",
    "carry_forward_losses": "carried_forward_losses",
    "carried_forward_losses": "carried_forward_losses",
    "discount_claim": "discount_claim",
    "discount_timing": "discount_timing",
    "discount_eligibility": "discount_eligibility",
    "foreign_resident_discount": "foreign_resident_discount",
    "concession_type": "concession_type",
    "small_business_concession_type": "concession_type",
    "business_asset": "business_asset",
    "active_asset": "active_asset",
    "entity_affiliate_connected_entity": "entity_affiliate_connected_entity",
    "affiliate_connected_entity": "entity_affiliate_connected_entity",
    "connected_entity": "entity_affiliate_connected_entity",
    "retirement_exemption": "retirement_exemption",
    "rollover": "rollover",
    "roll_over": "rollover",
    "fifteen_year_exemption": "fifteen_year_exemption",
    "15_year_exemption": "fifteen_year_exemption",
    "active_asset_reduction_50": "active_asset_reduction_50",
    "50_percent_active_asset_reduction": "active_asset_reduction_50",
    "concession_evidence": "concession_evidence",
    "ownership": "owner",
    "ownership_share": "owner",
    "main_residence": "main_residence_claim",
    "main_residence_claim": "main_residence_claim",
    "main_residence_ownership_period": "main_residence_ownership_period",
    "main_residence_occupancy_period": "main_residence_occupancy_period",
    "main_residence_rental_business_use": "main_residence_rental_business_use",
    "main_residence_absence_periods": "main_residence_absence_periods",
    "main_residence_spouse_conflict": "main_residence_spouse_conflict",
    "main_residence_property_records": "main_residence_property_records",
}
CGT_ITEM_ALIASES = ("items", "cgt_items")
CGT_ITEM_FIELD_ALIASES = {
    "event_type": ("event_type", "cgt_event_type", "event"),
    "asset": ("asset", "asset_description", "cgt_asset", "cgt_asset_description"),
    "owner": ("owner", "ownership", "ownership_share", "cgt_owner"),
    "acquisition_date": ("acquisition_date", "acquired_date", "cgt_acquisition_date"),
    "disposal_date": ("disposal_date", "disposed_date", "cgt_disposal_date"),
    "proceeds": ("proceeds", "capital_proceeds", "cgt_proceeds"),
    "cost_base": ("cost_base", "cgt_cost_base"),
    "incidental_costs": ("incidental_costs", "incidental_cost", "cgt_incidental_costs"),
    "losses": ("losses", "capital_losses", "loss", "cgt_losses"),
    "current_year_losses": ("current_year_losses", "cgt_current_year_losses"),
    "carried_forward_losses": ("carried_forward_losses", "cgt_carried_forward_losses"),
    "discount_claim": ("discount_claim", "cgt_discount_claim"),
    "discount_timing": ("discount_timing", "cgt_discount_timing"),
    "discount_eligibility": ("discount_eligibility", "cgt_discount_eligibility"),
    "foreign_resident_discount": (
        "foreign_resident_discount",
        "cgt_foreign_resident_discount",
    ),
    "records": ("records", "cgt_records"),
    "no_cgt": ("no_cgt", "cgt_no_cgt"),
    "exemption_flag": ("exemption_flag", "cgt_exemption_flag"),
    "discount_flag": ("discount_flag", "cgt_discount_flag"),
    "concession_flag": ("concession_flag", "cgt_concession_flag"),
    "concession_type": ("concession_type", "small_business_concession_type", "cgt_concession_type"),
    "business_asset": ("business_asset", "cgt_business_asset"),
    "active_asset": ("active_asset", "cgt_active_asset"),
    "entity_affiliate_connected_entity": (
        "entity_affiliate_connected_entity",
        "affiliate_connected_entity",
        "connected_entity",
        "cgt_entity_affiliate_connected_entity",
    ),
    "retirement_exemption": ("retirement_exemption", "cgt_retirement_exemption"),
    "rollover": ("rollover", "roll_over", "cgt_rollover"),
    "fifteen_year_exemption": ("fifteen_year_exemption", "15_year_exemption", "cgt_15_year_exemption", "cgt_fifteen_year_exemption"),
    "active_asset_reduction_50": (
        "active_asset_reduction_50",
        "50_percent_active_asset_reduction",
        "cgt_active_asset_reduction_50",
        "cgt_50_percent_active_asset_reduction",
    ),
    "concession_evidence": ("concession_evidence", "cgt_concession_evidence"),
    "mixed_use": ("mixed_use", "cgt_mixed_use"),
    "business_use": ("business_use", "cgt_business_use"),
    "private_use": ("private_use", "cgt_private_use"),
    "main_residence_claim": ("main_residence_claim", "main_residence", "cgt_main_residence_claim"),
    "main_residence_ownership_period": ("main_residence_ownership_period", "cgt_main_residence_ownership_period"),
    "main_residence_occupancy_period": ("main_residence_occupancy_period", "cgt_main_residence_occupancy_period"),
    "main_residence_rental_business_use": ("main_residence_rental_business_use", "cgt_main_residence_rental_business_use"),
    "main_residence_absence_periods": ("main_residence_absence_periods", "cgt_main_residence_absence_periods"),
    "main_residence_spouse_conflict": ("main_residence_spouse_conflict", "cgt_main_residence_spouse_conflict"),
    "main_residence_property_records": ("main_residence_property_records", "cgt_main_residence_property_records"),
}
CGT_SIGNAL_FIELDS = (
    "summary",
    "event_type",
    "asset",
    "owner",
    "acquisition_date",
    "disposal_date",
    "proceeds",
    "cost_base",
    "incidental_costs",
    "losses",
    "current_year_losses",
    "carried_forward_losses",
    "discount_claim",
    "discount_timing",
    "discount_eligibility",
    "foreign_resident_discount",
    "records",
    "exemption_flag",
    "discount_flag",
    "concession_flag",
    "concession_type",
    "business_asset",
    "active_asset",
    "entity_affiliate_connected_entity",
    "retirement_exemption",
    "rollover",
    "fifteen_year_exemption",
    "active_asset_reduction_50",
    "concession_evidence",
    "mixed_use",
    "business_use",
    "private_use",
    "main_residence_claim",
    "main_residence_ownership_period",
    "main_residence_occupancy_period",
    "main_residence_rental_business_use",
    "main_residence_absence_periods",
    "main_residence_spouse_conflict",
    "main_residence_property_records",
)
CGT_RECONCILIATION_FIELDS = ("proceeds", "cost_base", "incidental_costs", "losses")
CGT_LOSS_REVIEW_AMOUNT_FIELDS = ("current_year_losses", "carried_forward_losses")
CGT_AMOUNT_FIELDS = (*CGT_RECONCILIATION_FIELDS, *CGT_LOSS_REVIEW_AMOUNT_FIELDS)
CGT_DISCOUNT_REVIEW_TEXT_FIELDS = ("discount_timing", "discount_eligibility")
CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS = (
    "concession_type",
    "concession_evidence",
)
CGT_SMALL_BUSINESS_CONCESSION_FLAG_FIELDS = (
    "concession_flag",
    "business_asset",
    "active_asset",
    "entity_affiliate_connected_entity",
    "retirement_exemption",
    "rollover",
    "fifteen_year_exemption",
    "active_asset_reduction_50",
)
CGT_SMALL_BUSINESS_CONCESSION_FIELDS = (
    *CGT_SMALL_BUSINESS_CONCESSION_FLAG_FIELDS,
    *CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS,
)
CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS = (
    "main_residence_ownership_period",
    "main_residence_occupancy_period",
    "main_residence_absence_periods",
    "main_residence_property_records",
)
CGT_MAIN_RESIDENCE_REVIEW_FLAG_FIELDS = (
    "main_residence_claim",
    "main_residence_rental_business_use",
    "main_residence_spouse_conflict",
)
CGT_MAIN_RESIDENCE_REVIEW_FIELDS = (
    *CGT_MAIN_RESIDENCE_REVIEW_FLAG_FIELDS,
    *CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS,
)
CGT_FLAT_AMOUNT_FIELDS = tuple(
    key for key, nested_key in CGT_FLAT_FIELD_KEYS.items() if nested_key in CGT_AMOUNT_FIELDS
)
CGT_DATE_FIELDS = ("acquisition_date", "disposal_date")
CGT_BOOLEAN_REVIEW_FIELDS = (
    "exemption_flag",
    "discount_flag",
    "discount_claim",
    "foreign_resident_discount",
    "concession_flag",
    "business_asset",
    "active_asset",
    "entity_affiliate_connected_entity",
    "retirement_exemption",
    "rollover",
    "fifteen_year_exemption",
    "active_asset_reduction_50",
    "mixed_use",
    "business_use",
    "private_use",
    "main_residence_claim",
    "main_residence_rental_business_use",
    "main_residence_spouse_conflict",
)
CGT_SOURCE_KEY_FACTS = ("no_cgt", *CGT_SIGNAL_FIELDS)
CGT_DECLINE_SIGNAL_KEY = "_decline_signals"
CGT_CONFLICT_SIGNAL_KEY = "_conflict_signals"
CGT_DECLINE_PHRASES = (
    "no cgt",
    "no cgt event",
    "no cgt events",
    "no capital gain",
    "no capital gains",
    "no capital gains tax",
    "no capital gains tax event",
    "no capital gains tax events",
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
CGT_FIELD_ABSENCE_PHRASES = (
    "not applicable",
    "not applicable to me",
    "n/a",
    "na",
)
REVIEWABLE_COMPLEX_FIELDS = (
    "deductions",
    "employee_deductions",
    "individual_deductions",
    "personal_super_deductions",
    "personal_super_contributions",
    "super_contribution_deductions",
    "offsets",
    "individual_offsets",
    "tax_offsets",
    "wfh_work_pattern",
    "wfh_records",
    "asset_items",
    "ess_items",
    "foreign_income_items",
    "crypto_items",
    "rental_property_items",
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
ATO_INDIVIDUAL_SOURCE = "https://www.ato.gov.au/forms-and-instructions/individual-tax-return-2026-instructions"
ATO_PARTNERSHIP_TRUST_INCOME_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/business-partnership-and-trust-income"
ATO_COMPENSATION_INCOME_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/compensation-and-insurance-payments"
ATO_SCHOLARSHIP_PRIZE_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/scholarships-prizes-and-awards"
ATO_PRIVATE_HEALTH_STATEMENT_SOURCE = "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/private-health-insurance-rebate/your-private-health-insurance-statement"
ATO_PRIVATE_HEALTH_REBATE_CLAIM_SOURCE = "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/private-health-insurance-rebate/claiming-the-private-health-insurance-rebate"
ATO_MEDICARE_LEVY_SOURCE = "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/medicare-levy"
ATO_MLS_RETURN_SOURCE = "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/medicare-levy-surcharge/medicare-levy-surcharge-and-your-tax-return"
ATO_MLS_THRESHOLDS_SOURCE = "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/medicare-levy-surcharge/medicare-levy-surcharge-income-thresholds-and-rates"
ATO_MLS_FAMILY_DEPENDANTS_SOURCE = "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/medicare-levy-surcharge/family-and-dependants-for-medicare-levy-surcharge-purposes"
ATO_MLS_PAYING_SOURCE = "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/medicare-levy-surcharge/paying-the-medicare-levy-surcharge"
ATO_PRIVATE_HEALTH_STATEMENT_SOURCES = [
    ATO_PRIVATE_HEALTH_STATEMENT_SOURCE,
    ATO_PRIVATE_HEALTH_REBATE_CLAIM_SOURCE,
]
ATO_MEDICARE_LEVY_SOURCES = [ATO_MEDICARE_LEVY_SOURCE]
ATO_MLS_SOURCES = [ATO_MLS_RETURN_SOURCE, ATO_MLS_THRESHOLDS_SOURCE, ATO_MLS_PAYING_SOURCE]
ATO_SPOUSE_DEPENDANT_SOURCES = [
    ATO_MLS_FAMILY_DEPENDANTS_SOURCE,
    ATO_MLS_RETURN_SOURCE,
    ATO_MLS_THRESHOLDS_SOURCE,
]
ATO_PAYG_EMPLOYMENT_INCOME_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/employment-income"
PAYG_SOURCES = [
    ATO_PAYG_EMPLOYMENT_INCOME_SOURCE,
    "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding/payg-payment-summaries",
    "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding",
]
ATO_WFH_FIXED_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method"
ATO_WFH_ACTUAL_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/actual-cost-method"
ATO_ASSET_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work/depreciating-assets-you-use-for-work"
ATO_PHONE_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work/mobile-phone-mobile-internet-and-other-devices"
ATO_HOME_PHONE_INTERNET_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work/home-phone-and-internet-expenses"
ATO_ASSET_300_OR_LESS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work/depreciating-assets-you-use-for-work/assets-costing-300-dollars-or-less"
ATO_ASSET_OVER_300_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work/depreciating-assets-you-use-for-work/assets-costing-more-than-300-dollars"
ATO_WORK_RELATED_DEDUCTIONS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions"
ATO_GIFTS_DONATIONS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/gifts-and-donations"
ATO_TAX_AFFAIRS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/cost-of-managing-tax-affairs"
ATO_INVESTMENTS_INSURANCE_SUPER_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/investments-insurance-and-super"
ATO_SELF_EDUCATION_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/education-training-and-seminars/self-education-expenses"
ATO_MEMBERSHIPS_FEES_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/memberships-accreditations-fees-and-commissions"
ATO_CAR_TRANSPORT_TRAVEL_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/cars-transport-and-travel"
ATO_CAR_EXPENSES_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/cars-transport-and-travel/motor-vehicle-and-car-expenses/expenses-for-a-car-you-own-or-lease"
ATO_PUBLIC_TRANSPORT_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/cars-transport-and-travel/taxi-ride-share-and-public-transport-expenses"
ATO_TRAVEL_RECORDS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/cars-transport-and-travel/overnight-travel-expenses-and-allowances/keeping-travel-expense-records"
ATO_TOOLS_EQUIPMENT_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work"
ATO_PERSONAL_SUPER_CONTRIBUTIONS_SOURCE = "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/growing-and-keeping-track-of-your-super/how-to-save-more-in-your-super/personal-super-contributions"
ATO_CONCESSIONAL_CONTRIBUTIONS_CAP_SOURCE = "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/growing-and-keeping-track-of-your-super/caps-limits-and-tax-on-super-contributions/concessional-contributions-cap"
ATO_DIVISION_293_SOURCE = "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/growing-and-keeping-track-of-your-super/caps-limits-and-tax-on-super-contributions/division-293-tax-on-concessional-contributions-by-high-income-earners"
ATO_TAX_OFFSETS_SOURCE = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/tax-offsets"
ATO_SUPER_COCONTRIBUTION_SOURCE = "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/growing-and-keeping-track-of-your-super/how-to-save-more-in-your-super/government-super-contributions/super-co-contribution"
ATO_DEDUCTION_SOURCES = [
    ATO_WORK_RELATED_DEDUCTIONS_SOURCE,
    ATO_GIFTS_DONATIONS_SOURCE,
    ATO_TAX_AFFAIRS_SOURCE,
    ATO_INVESTMENTS_INSURANCE_SUPER_SOURCE,
    ATO_SELF_EDUCATION_SOURCE,
    ATO_MEMBERSHIPS_FEES_SOURCE,
    ATO_CAR_TRANSPORT_TRAVEL_SOURCE,
    ATO_CAR_EXPENSES_SOURCE,
    ATO_PUBLIC_TRANSPORT_SOURCE,
    ATO_TRAVEL_RECORDS_SOURCE,
    ATO_TOOLS_EQUIPMENT_SOURCE,
    ATO_ASSET_SOURCE,
]
ATO_PERSONAL_SUPER_DEDUCTION_SOURCES = [
    ATO_PERSONAL_SUPER_CONTRIBUTIONS_SOURCE,
    ATO_CONCESSIONAL_CONTRIBUTIONS_CAP_SOURCE,
    ATO_DIVISION_293_SOURCE,
]
ATO_OFFSET_SOURCES = [ATO_TAX_OFFSETS_SOURCE]
ATO_SUPER_OFFSET_SOURCES = [
    ATO_TAX_OFFSETS_SOURCE,
    ATO_SUPER_COCONTRIBUTION_SOURCE,
    ATO_INVESTMENTS_INSURANCE_SUPER_SOURCE,
]
ATO_PHONE_SOURCES = [
    ATO_PHONE_SOURCE,
    ATO_HOME_PHONE_INTERNET_SOURCE,
    ATO_WFH_FIXED_SOURCE,
    ATO_WFH_ACTUAL_SOURCE,
    ATO_ASSET_SOURCE,
    ATO_ASSET_300_OR_LESS_SOURCE,
    ATO_ASSET_OVER_300_SOURCE,
]
ATO_BAS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas"
ATO_GST_CREDITS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/claiming-gst-credits"
ATO_TAX_INVOICES_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/tax-invoices"
ATO_GST_ACCOUNTING_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/accounting-for-gst-in-your-business"
ATO_GST_FREE_SALES_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/when-to-charge-gst-and-when-not-to/gst-free-sales"
ATO_INPUT_TAXED_SALES_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/when-to-charge-gst-and-when-not-to/input-taxed-sales"
ATO_BAS_ADJUSTMENTS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/fixing-bas-mistakes-or-making-adjustments"
ATO_PAYG_INSTALMENTS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/payg-instalments"
ATO_PAYG_WITHHOLDING_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/pay-as-you-go-payg-withholding"
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
ATO_BUSINESS_INCOME_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business"
ATO_BUSINESS_DEDUCTIONS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions"
ATO_HOME_BUSINESS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions/deductions-for-home-based-business-expenses/home-based-business-expenses-sole-trader-or-partnership"
ATO_BUSINESS_LOSSES_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/business-losses"
ATO_MOTOR_VEHICLE_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions/deductions-for-motor-vehicle-expenses"
ATO_BUSINESS_DEPRECIATING_ASSETS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions/deductions-for-depreciating-assets-and-capital-expenses"
ATO_PSI_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income"
ATO_PSI_SOURCES = [
    ATO_PSI_SOURCE,
    ATO_BUSINESS_INCOME_SOURCE,
]
ATO_ABN_BUSINESS_SOURCES = [
    ATO_BUSINESS_INCOME_SOURCE,
    ATO_BUSINESS_DEDUCTIONS_SOURCE,
    ATO_HOME_BUSINESS_SOURCE,
    ATO_BUSINESS_LOSSES_SOURCE,
    ATO_MOTOR_VEHICLE_SOURCE,
    ATO_BUSINESS_DEPRECIATING_ASSETS_SOURCE,
    ATO_PSI_SOURCE,
]
ATO_BAS_SOURCES = [
    ATO_BAS_SOURCE,
    ATO_GST_CREDITS_SOURCE,
    ATO_TAX_INVOICES_SOURCE,
    ATO_GST_ACCOUNTING_SOURCE,
    ATO_GST_FREE_SALES_SOURCE,
    ATO_INPUT_TAXED_SALES_SOURCE,
    ATO_BAS_ADJUSTMENTS_SOURCE,
    ATO_PAYG_INSTALMENTS_SOURCE,
    ATO_PAYG_WITHHOLDING_SOURCE,
]
ATO_CRYPTO_ASSETS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments"
ATO_CRYPTO_RECORDS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments/keeping-crypto-records"
ATO_CRYPTO_BUSINESS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/crypto-assets-and-business"
ATO_CRYPTO_SOURCES = [
    ATO_CRYPTO_ASSETS_SOURCE,
    ATO_CRYPTO_RECORDS_SOURCE,
    ATO_CRYPTO_BUSINESS_SOURCE,
]
ATO_RENTAL_RECORDS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/property-and-land/residential-rental-properties/records-for-rental-properties-and-holiday-homes"
ATO_RENTAL_CGT_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax"
ATO_RENTAL_HOME_USE_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax/your-main-residence-home/using-your-home-for-rental-or-business"
ATO_PROPERTY_RECORDS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax/keeping-records-for-property"
ATO_CGT_MAIN_RESIDENCE_ELIGIBILITY_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax/your-main-residence-home/eligibility-for-main-residence-exemption"
ATO_RENTAL_PROPERTY_SOURCES = [
    ATO_RENTAL_RECORDS_SOURCE,
    ATO_RENTAL_CGT_SOURCE,
    ATO_RENTAL_HOME_USE_SOURCE,
]
ATO_CGT_EVENTS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-events"
ATO_CGT_LOSS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt"
ATO_CGT_CALCULATION_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/how-to-calculate-your-cgt"
ATO_CGT_COST_BASE_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/cost-base-of-asset"
ATO_CGT_PROCEEDS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/capital-proceeds-from-disposing-of-assets"
ATO_CGT_ASSETS_EXEMPTIONS_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/list-of-cgt-assets-and-exemptions"
ATO_CGT_DISCOUNT_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount"
ATO_CGT_FOREIGN_RESIDENT_DISCOUNT_SOURCE = "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/foreign-residents-and-capital-gains-tax/cgt-discount-for-foreign-residents"
ATO_CGT_SMALL_BUSINESS_CONCESSIONS_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions"
ATO_CGT_SMALL_BUSINESS_ELIGIBILITY_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-cgt-concessions-eligibility-conditions"
ATO_CGT_SMALL_BUSINESS_ACTIVE_ASSET_TEST_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-cgt-concessions-eligibility-conditions/active-asset-test"
ATO_CGT_SMALL_BUSINESS_ENTITY_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-cgt-concessions-eligibility-conditions/cgt-small-business-entity-eligibility"
ATO_CGT_SMALL_BUSINESS_AFFILIATES_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-cgt-concessions-eligibility-conditions/small-business-affiliates"
ATO_CGT_SMALL_BUSINESS_CONNECTED_ENTITIES_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-cgt-concessions-eligibility-conditions/entities-connected-with-you-and-control-relationships"
ATO_CGT_SMALL_BUSINESS_15_YEAR_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-15-year-exemption"
ATO_CGT_SMALL_BUSINESS_50_PERCENT_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-50-percent-active-asset-reduction"
ATO_CGT_SMALL_BUSINESS_RETIREMENT_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-retirement-exemption"
ATO_CGT_SMALL_BUSINESS_ROLLOVER_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions/small-business-roll-over"
ATO_CGT_SMALL_BUSINESS_CONCESSION_SOURCES = [
    ATO_CGT_SMALL_BUSINESS_CONCESSIONS_SOURCE,
    ATO_CGT_SMALL_BUSINESS_ELIGIBILITY_SOURCE,
    ATO_CGT_SMALL_BUSINESS_ACTIVE_ASSET_TEST_SOURCE,
    ATO_CGT_SMALL_BUSINESS_ENTITY_SOURCE,
    ATO_CGT_SMALL_BUSINESS_AFFILIATES_SOURCE,
    ATO_CGT_SMALL_BUSINESS_CONNECTED_ENTITIES_SOURCE,
    ATO_CGT_SMALL_BUSINESS_15_YEAR_SOURCE,
    ATO_CGT_SMALL_BUSINESS_50_PERCENT_SOURCE,
    ATO_CGT_SMALL_BUSINESS_RETIREMENT_SOURCE,
    ATO_CGT_SMALL_BUSINESS_ROLLOVER_SOURCE,
]
ATO_CGT_SOURCES = [
    ATO_CGT_EVENTS_SOURCE,
    ATO_CGT_LOSS_SOURCE,
    ATO_CGT_CALCULATION_SOURCE,
    ATO_CGT_COST_BASE_SOURCE,
    ATO_CGT_PROCEEDS_SOURCE,
    ATO_CGT_ASSETS_EXEMPTIONS_SOURCE,
    ATO_CGT_LOSS_SOURCE,
    ATO_CGT_DISCOUNT_SOURCE,
    ATO_CGT_FOREIGN_RESIDENT_DISCOUNT_SOURCE,
]
ATO_CGT_MAIN_RESIDENCE_SOURCES = [
    ATO_CGT_MAIN_RESIDENCE_ELIGIBILITY_SOURCE,
    ATO_RENTAL_HOME_USE_SOURCE,
    ATO_PROPERTY_RECORDS_SOURCE,
]
OMITTED_SCOPE_ITEMS = [
    ("feat: add company return intake", "Company/entity return prep, company tax labels, directors, dividends, franking, retained earnings."),
    ("feat: add trust return intake", "Trust return prep, beneficiary distributions, trustee-assessed income, family trust items."),
    ("feat: add partnership return intake", "Partnership return prep, partner shares, partnership income/loss allocations."),
    ("feat: add full supplementary return coverage", "Full supplementary labels beyond common V1 gates."),
    ("feat: add full CGT schedule workflow", "CGT events, cost base, discounts, carried losses, main residence, small business concessions."),
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
        QuestionSpec("private_health_medicare", "Private health", "Private health, Medicare, spouse, and dependant details", "M1 / M2 / Private health insurance policy details", False),
        QuestionSpec("private_health_statements", "Private health", "Private health insurance statement rows", "Private health insurance policy details", False),
        QuestionSpec("medicare_levy", "Medicare", "Medicare levy reduction or exemption facts", "M1 Medicare levy reduction or exemption", False),
        QuestionSpec("medicare_levy_surcharge", "Medicare", "Medicare levy surcharge review facts", "M2 Medicare levy surcharge", False),
        QuestionSpec("spouse_details", "Spouse", "Spouse period and income-test facts", "Spouse details", False),
        QuestionSpec("dependant_details", "Dependants", "Dependant child or student facts", "M1 / M2 dependants", False),
        QuestionSpec("payg_gross", "PAYG", "Salary or wages gross income", "1 Salary or wages", False),
        QuestionSpec("payg_withheld", "PAYG", "Salary or wages tax withheld", "1 Salary or wages", False),
        QuestionSpec("main_occupation", "PAYG", "Main salary and wage occupation", "1 Salary or wages", False),
        QuestionSpec("payg_income_statements", "PAYG", "PAYG income statement items", "1 Salary or wages", False),
        QuestionSpec("payg_employer_name", "PAYG", "PAYG employer or payer name", "1 Salary or wages", False),
        QuestionSpec("payg_employer_abn", "PAYG", "PAYG employer or payer ABN", "1 Salary or wages", False),
        QuestionSpec("payg_occupation", "PAYG", "PAYG occupation", "1 Salary or wages", False),
        QuestionSpec("payg_allowances", "PAYG", "PAYG allowances", "1 Salary or wages", False),
        QuestionSpec("payg_rfba", "PAYG", "Reportable fringe benefits amount", "IT1 Reportable fringe benefits", False),
        QuestionSpec("payg_resc", "PAYG", "Reportable employer super contributions", "IT2 Reportable employer super contributions", False),
        QuestionSpec("payg_lump_sum_a", "PAYG", "PAYG lump sum A", "1 Salary or wages", False),
        QuestionSpec("payg_lump_sum_b", "PAYG", "PAYG lump sum B", "1 Salary or wages", False),
        QuestionSpec("payg_lump_sum_d", "PAYG", "PAYG lump sum D", "1 Salary or wages", False),
        QuestionSpec("payg_lump_sum_e", "PAYG", "PAYG lump sum E", "1 Salary or wages", False),
        QuestionSpec("interest_income", "Income", "Gross interest", "10 Gross interest", False),
        QuestionSpec("dividend_income", "Income", "Dividends or ETF distributions", "11 Dividends", False),
        QuestionSpec("investment_interest_items", "Investment income", "Bank interest items", "10 Gross interest", False),
        QuestionSpec("investment_dividend_items", "Investment income", "Dividend and franking items", "11 Dividends", False),
        QuestionSpec("investment_distribution_items", "Investment income", "Managed fund/ETF/AMIT distributions", "13 Partnerships and trusts", False),
        QuestionSpec("trust_distribution_items", "Investment income", "Trust distribution statements", "13 Partnerships and trusts", False),
        QuestionSpec("partnership_share_items", "Supplementary income", "Individual partnership share statements", "13 Partnerships and trusts", False),
        QuestionSpec("trust_share_items", "Supplementary income", "Individual trust beneficiary/share statements", "13 Partnerships and trusts", False),
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
        QuestionSpec("psi_income", "PSI", "Personal services income amount", "Personal services income", False),
        QuestionSpec("psi_income_type", "PSI", "PSI occupation or income type", "Personal services income", False),
        QuestionSpec("psi_contract_evidence", "PSI", "PSI contract or invoice evidence held?", "Personal services income", False),
        QuestionSpec("psi_results_test", "PSI", "PSI results test passed?", "Personal services income", False),
        QuestionSpec("psi_80_percent_test", "PSI", "80% PSI client concentration test", "Personal services income", False),
        QuestionSpec("psi_unrelated_clients_test", "PSI", "Unrelated clients test passed?", "Personal services income", False),
        QuestionSpec("psi_employment_test", "PSI", "Employment test passed?", "Personal services income", False),
        QuestionSpec("psi_business_premises_test", "PSI", "Business premises test passed?", "Personal services income", False),
        QuestionSpec("psi_psb_determination", "PSI", "Personal services business determination held?", "Personal services income", False),
        QuestionSpec("psi_attribution_entity", "PSI", "PSI attribution entity or individual", "Personal services income", False),
        QuestionSpec("psi_deductions", "PSI", "PSI deductions needing review", "Personal services income", False),
        QuestionSpec("psi_business_structure", "PSI", "PSI business structure", "Personal services income", False),
        QuestionSpec("crypto_event_type", "Crypto", "Crypto event type", "Crypto asset investments", False),
        QuestionSpec("crypto_exchange_or_wallet", "Crypto", "Crypto exchange or wallet", "Keeping crypto records", False),
        QuestionSpec("crypto_asset", "Crypto", "Crypto asset name or ticker", "Crypto asset investments", False),
        QuestionSpec("crypto_quantity", "Crypto", "Crypto quantity", "Keeping crypto records", False),
        QuestionSpec("crypto_acquired_date", "Crypto", "Crypto acquired date", "Crypto asset investments", False),
        QuestionSpec("crypto_disposed_date", "Crypto", "Crypto disposed date", "Crypto asset investments", False),
        QuestionSpec("crypto_cost_base", "Crypto", "Crypto cost base", "Crypto asset investments", False),
        QuestionSpec("crypto_capital_proceeds", "Crypto", "Crypto capital proceeds", "Crypto asset investments", False),
        QuestionSpec("crypto_rewards_income", "Crypto", "Crypto staking/rewards income", "Crypto asset investments", False),
        QuestionSpec("crypto_transfer_between_wallets", "Crypto", "Transfer between own wallets?", "Keeping crypto records", False),
        QuestionSpec("crypto_wallet_records", "Crypto", "Wallet/exchange records held?", "Keeping crypto records", False),
        QuestionSpec("crypto_ownership_entity", "Crypto", "Crypto owner or entity", "Crypto asset investments", False),
        QuestionSpec("crypto_business_use", "Crypto", "Business/trading use?", "Crypto assets and business", False),
        QuestionSpec("crypto_private_use", "Crypto", "Private/investment use?", "Crypto asset investments", False),
        QuestionSpec("rental_property_address", "Rental property", "Rental property address or label", "Rental property records", False),
        QuestionSpec("rental_property_ownership", "Rental property", "Rental property owner or ownership share", "Rental property records", False),
        QuestionSpec("rental_property_income", "Rental property", "Gross rental income", "Rental property records", False),
        QuestionSpec("rental_property_interest", "Rental property", "Rental loan interest", "Rental property records", False),
        QuestionSpec("rental_property_repairs", "Rental property", "Repairs and maintenance", "Rental property records", False),
        QuestionSpec("rental_property_capital_works", "Rental property", "Capital works or improvements", "Property and CGT records", False),
        QuestionSpec("rental_property_depreciation", "Rental property", "Depreciating assets or decline in value", "Property and CGT records", False),
        QuestionSpec("rental_property_other_expenses", "Rental property", "Other rental expenses", "Rental property records", False),
        QuestionSpec("rental_property_private_use", "Rental property", "Private or holiday-home use?", "Using your home for rental or business", False),
        QuestionSpec("rental_property_private_use_days", "Rental property", "Private-use days", "Using your home for rental or business", False),
        QuestionSpec("rental_property_available_days", "Rental property", "Days available for rent", "Rental property records", False),
        QuestionSpec("rental_property_records", "Rental property", "Rental statements and records held?", "Rental property records", False),
        QuestionSpec("rental_property_net_loss", "Rental property", "Net rental loss or carried issue", "Rental property records", False),
        QuestionSpec("cgt_summary", "CGT", "General CGT event summary", "CGT schedule", False),
        QuestionSpec("cgt_event_type", "CGT", "General CGT event type", "CGT events", False),
        QuestionSpec("cgt_asset", "CGT", "CGT asset description", "CGT events", False),
        QuestionSpec("cgt_asset_description", "CGT", "CGT asset description", "CGT events", False),
        QuestionSpec("cgt_owner", "CGT", "CGT owner or ownership share", "CGT records", False),
        QuestionSpec("cgt_acquisition_date", "CGT", "CGT acquisition date", "CGT records", False),
        QuestionSpec("cgt_disposal_date", "CGT", "CGT disposal date", "CGT records", False),
        QuestionSpec("cgt_proceeds", "CGT", "CGT capital proceeds", "Capital proceeds", False),
        QuestionSpec("cgt_cost_base", "CGT", "CGT cost base", "Cost base", False),
        QuestionSpec("cgt_current_year_losses", "CGT", "CGT current-year capital losses", "Cost base", False),
        QuestionSpec("cgt_carried_forward_losses", "CGT", "CGT carried-forward capital losses", "Cost base", False),
        QuestionSpec("cgt_records", "CGT", "CGT acquisition, disposal, and cost-base records", "CGT records", False),
        QuestionSpec("cgt_no_cgt", "CGT", "No general CGT event answer", "CGT events", False),
        QuestionSpec("cgt_main_residence_claim", "CGT", "Main residence exemption claim?", "Eligibility for main residence exemption", False),
        QuestionSpec("cgt_main_residence_ownership_period", "CGT", "Main residence ownership period", "Eligibility for main residence exemption", False),
        QuestionSpec("cgt_main_residence_occupancy_period", "CGT", "Main residence occupancy period", "Eligibility for main residence exemption", False),
        QuestionSpec("cgt_main_residence_rental_business_use", "CGT", "Rental or business use during ownership?", "Using your home for rental or business", False),
        QuestionSpec("cgt_main_residence_absence_periods", "CGT", "Absence periods or absence-rule signals", "Eligibility for main residence exemption", False),
        QuestionSpec("cgt_main_residence_spouse_conflict", "CGT", "Spouse/partner claimed another main residence?", "Eligibility for main residence exemption", False),
        QuestionSpec("cgt_main_residence_property_records", "CGT", "Main residence property and occupancy records", "Keeping records for property", False),
        QuestionSpec("cgt_exemption_flag", "CGT", "CGT exemption flag", "CGT review", False),
        QuestionSpec("cgt_discount_flag", "CGT", "CGT discount flag", "CGT review", False),
        QuestionSpec("cgt_discount_claim", "CGT", "CGT discount claim", "CGT review", False),
        QuestionSpec("cgt_discount_timing", "CGT", "CGT discount timing", "CGT review", False),
        QuestionSpec("cgt_discount_eligibility", "CGT", "CGT discount eligibility evidence", "CGT review", False),
        QuestionSpec("cgt_foreign_resident_discount", "CGT", "CGT foreign-resident discount signal", "CGT review", False),
        QuestionSpec("cgt_concession_flag", "CGT", "CGT concession flag", "CGT review", False),
        QuestionSpec("cgt_mixed_use", "CGT", "CGT mixed-use flag", "CGT review", False),
        QuestionSpec("cgt_business_use", "CGT", "CGT business-use flag", "CGT review", False),
        QuestionSpec("cgt_private_use", "CGT", "CGT private-use flag", "CGT review", False),
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
        QuestionSpec("deductions", "Deductions", "Deduction notes", "D1-D10 deductions", False),
        QuestionSpec("employee_deductions", "Deductions", "Employee deductions", "D1-D10 deductions", False),
        QuestionSpec("individual_deductions", "Deductions", "Itemized deduction rows", "D1-D10 deductions", False),
        QuestionSpec("personal_super_contributions", "Deductions", "Personal super contribution deduction prep", "D12 Personal super contributions", False),
        QuestionSpec("personal_super_deductions", "Deductions", "Personal super contribution deduction notes", "D12 Personal super contributions", False),
        QuestionSpec("super_contribution_deductions", "Deductions", "Super contribution deduction notes", "D12 Personal super contributions", False),
        QuestionSpec("offsets", "Offsets", "Offset notes", "Tax offsets", False),
        QuestionSpec("individual_offsets", "Offsets", "Individual offset review rows", "Tax offsets", False),
        QuestionSpec("tax_offsets", "Offsets", "Tax offset notes", "Tax offsets", False),
        QuestionSpec("phone", "Deductions", "Phone plan, data, and device facts", "D5 Other work-related expenses", False),
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
        "private_health_medicare": {
            "private_health_cover": True,
            "cover_period_start": "2025-07-01",
            "cover_period_end": "2026-06-30",
            "days_covered": 365,
            "statements": [
                {
                    "insurer": "Example Health Fund",
                    "membership_id": "SYNTHETIC-001",
                    "benefit_code": "30",
                    "premiums_eligible_for_rebate": 1800,
                    "rebate_received": 450,
                    "tax_claim_code": "C",
                    "days_covered": 274,
                    "period_start": "2025-07-01",
                    "period_end": "2026-03-31",
                    "evidence": "private health statement held",
                },
                {
                    "insurer": "Example Health Fund",
                    "membership_id": "SYNTHETIC-001",
                    "benefit_code": "31",
                    "premiums_eligible_for_rebate": 600,
                    "rebate_received": 150,
                    "tax_claim_code": "C",
                    "days_covered": 91,
                    "period_start": "2026-04-01",
                    "period_end": "2026-06-30",
                    "evidence": "private health statement held",
                }
            ],
            "medicare_levy": {
                "reduction": False,
                "exemption": False,
                "evidence": "Medicare levy review facts supplied",
            },
            "mls": {
                "review": True,
                "income_for_surcharge": 120000,
                "income_tier": "user-supplied review signal",
                "full_year_appropriate_family_cover": True,
                "appropriate_hospital_cover": True,
                "hospital_cover_days": 365,
                "evidence": "hospital cover period confirmed from policy records",
            },
            "spouse": {
                "had_spouse": True,
                "period_start": "2025-07-01",
                "period_end": "2026-06-30",
                "income_for_tests": 65000,
                "income_evidence": "spouse return summary held",
            },
            "dependant_count": 1,
            "dependants": [
                {
                    "name": "Synthetic dependant",
                    "type": "full-time student",
                    "student": True,
                    "age": 20,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "maintained": True,
                    "income_for_tests": 0,
                    "shared_care": False,
                    "evidence": "student enrolment and maintenance records held",
                }
            ],
        },
        "payg_gross": 120000,
        "payg_withheld": 31000,
        "main_occupation": "Software engineer",
        "payg_income_statements": [
            {
                "payer": "Example Tech Pty Ltd",
                "abn": "12 345 678 901",
                "occupation": "Software engineer",
                "gross": 110000,
                "withheld": 29000,
                "allowances": 0,
                "rfba": 0,
                "resc": 9500,
                "lump_sum_a": 0,
                "statement": "income statement held",
                "finalised": True,
            },
            {
                "payer": "Example Secondary Pty Ltd",
                "abn": "98 765 432 109",
                "occupation": "Casual tutor",
                "gross": 10000,
                "withheld": 2000,
                "allowances": 0,
                "rfba": 0,
                "resc": 950,
                "statement": "income statement held",
                "finalised": True,
            },
        ],
        "interest_income": 120,
        "dividend_income": 835,
        "investment_income": {
            "interest_items": [
                {
                    "payer": "Example Bank",
                    "account": "Saver account",
                    "amount": 120,
                    "tfn_withheld": 0,
                    "statement": "bank interest statement held",
                }
            ],
            "dividend_items": [
                {
                    "security": "EXM",
                    "company": "Example Ltd",
                    "franked_amount": 300,
                    "unfranked_amount": 0,
                    "franking_credit": 128.57,
                    "tfn_withheld": 0,
                    "statement": "dividend statement held",
                    "franking_confirmed": True,
                }
            ],
            "distribution_items": [
                {
                    "fund": "Example ETF",
                    "taxable_amount": 535,
                    "capital_gain": 80,
                    "foreign_income": 0,
                    "foreign_tax_offset": 0,
                    "franking_credit": 0,
                    "tfn_withheld": 0,
                    "statement": "AMMA statement held",
                    "amit": True,
                    "cost_base_adjustment": "statement shows annual tax statement cost-base adjustment",
                    "foreign_components": False,
                }
            ],
            "trust_distribution_items": [
                {
                    "trust": "Example Family Trust",
                    "beneficiary_type": "individual beneficiary",
                    "distribution_amount": 0,
                    "statement": "trust distribution statement not confirmed",
                    "foreign_components": False,
                }
            ],
        },
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
        "psi": {
            "income": 18000,
            "income_type": "IT consulting",
            "occupation": "Software engineer",
            "client": "Example Client Pty Ltd",
            "contract_evidence": "contracts and invoices held",
            "results_test": True,
            "eighty_percent_test": False,
            "unrelated_clients_test": False,
            "employment_test": False,
            "business_premises_test": False,
            "psb_determination": False,
            "attribution_entity": "sole trader",
            "deductions": "home office and software subscriptions",
            "business_structure": "sole trader ABN",
        },
        "crypto": {
            "event_type": "sale",
            "exchange_or_wallet": "Example Exchange CSV and wallet export held",
            "asset": "ETH",
            "quantity": 1.5,
            "acquired_date": "2025-08-01",
            "disposed_date": "2026-05-01",
            "cost_base": 3000,
            "capital_proceeds": 4200,
            "rewards_income": 0,
            "transfer_between_wallets": False,
            "wallet_records": "exchange CSV and wallet transaction history held",
            "ownership_entity": "individual",
            "business_use": False,
            "private_use": True,
        },
        "rental_property": {
            "address": "Example rental unit",
            "ownership": "50% individual owner",
            "income": 18000,
            "interest": 12500,
            "repairs": 2400,
            "capital_works": 4500,
            "depreciation": 1800,
            "other_expenses": 1600,
            "private_use": True,
            "private_use_days": 14,
            "available_days": 351,
            "records": "agent statement, loan interest statement, invoices held",
            "net_loss": True,
        },
        "cgt": {
            "event_type": "sale",
            "asset": "Example collectable",
            "owner": "individual",
            "acquisition_date": "2025-08-15",
            "disposal_date": "2026-04-20",
            "proceeds": 1500,
            "cost_base": 900,
            "records": "purchase receipt and sale record held",
            "exemption_flag": False,
            "discount_flag": False,
            "concession_flag": False,
            "mixed_use": False,
            "business_use": False,
            "private_use": True,
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
        "employee_deductions": [
            {"label": "Union fees", "type": "union", "amount": 0, "evidence": "unknown", "reimbursed": False},
            {
                "label": "Tax agent fee",
                "type": "tax agent fees",
                "amount": 275,
                "evidence": "invoice held",
                "reimbursed": False,
                "employer_paid": False,
                "employer_provided": False,
                "work_use_percent": 100,
                "gst_bas_interaction": False,
                "duplicate_risk": False,
            },
            {
                "label": "Self-education course",
                "type": "self education",
                "amount": 850,
                "evidence": "receipt held",
                "work_use_percent": 80,
                "reimbursed": False,
                "employer_paid": False,
                "gst_bas_interaction": False,
                "duplicate_risk": "also in employer reimbursement records",
            },
        ],
        "personal_super_contributions": [
            {
                "fund": "Example Super Fund",
                "member": "John Doe",
                "contribution_date": "2026-05-20",
                "amount": 3000,
                "notice_of_intent": "sent",
                "fund_acknowledgement": "held",
                "intended_deduction_amount": 3000,
                "concessional_cap_review": True,
                "division_293_review": False,
            }
        ],
        "individual_offsets": [
            {"type": "super co-contribution", "claim": False, "amount": 0, "evidence": "not claimed"},
            {"type": "zone offset", "claim": True, "amount": "unknown", "evidence": "residency days not confirmed"},
        ],
        "phone": {
            "context": "employee",
            "paid_by_user": True,
            "employer_reimbursed": False,
            "employer_paid": False,
            "employer_provided": False,
            "wfh_method": "actual-cost",
            "device": {
                "description": "Example phone",
                "cost": 1100,
                "purchase_date": "2025-07-01",
                "work_use_percent": 40,
                "receipt": "held",
                "method_preference": "prime-cost",
                "effective_life_years": 3,
                "insurance_amount": 0,
            },
            "plan": {
                "monthly_cost": 65,
                "months_claimed": 11,
                "itemised_bill": True,
                "representative_period_start": "2025-08-01",
                "representative_period_end": "2025-08-28",
                "work_use_percent": 20,
                "basis": "call-count",
                "bills": "held",
                "log": "held",
            },
            "incidental": {
                "claim_amount": 0,
                "work_calls": 0,
                "work_texts": 0,
                "basic_records": "held",
            },
        },
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
    private_health_medicare = private_health_medicare_answers(answers)
    for spec in question_specs():
        value = answers.get(spec.key)
        if spec.key in {"spouse_had", "dependant_children", "private_health_cover"} and is_missing(value):
            value = private_health_medicare_required_answer(private_health_medicare, spec.key)
        if spec.required and is_missing(value):
            missing.append(spec)
    return missing


def private_health_medicare_required_answer(raw: Dict[str, Any], key: str) -> Any:
    if key == "spouse_had":
        return normalized_item_field(raw.get("spouse", {}), SPOUSE_FIELD_ALIASES["had_spouse"])
    if key == "private_health_cover":
        return normalized_item_field(raw.get("private_health", {}), PRIVATE_HEALTH_FIELD_ALIASES["covered"])
    dependant_summary = private_health_dependant_summary_from_values(
        raw.get("dependant_summary", {}),
        raw.get("dependants", []),
    )
    dependant_count = normalized_item_field(
        dependant_summary,
        DEPENDANT_SUMMARY_FIELD_ALIASES["count"],
    )
    if not is_missing(dependant_count):
        return dependant_count
    dependants = private_health_dependant_items(raw.get("dependants", []))
    return dependants if dependants else None


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
    income_year = text(answers.get("income_year"), DEFAULT_INCOME_YEAR)
    investment = investment_answers(answers)
    payg = payg_answers(answers)
    cgt = cgt_answers(answers)
    deductions = deduction_answers(answers)
    personal_super_contributions = personal_super_contribution_answers(answers)
    offsets = offset_answers(answers)
    private_health_medicare = private_health_medicare_answers(answers)
    items = base_items(answers, private_health_medicare)
    extracted_values = extraction_rows(answers.get("extracted_values", []), income_year)
    abn_items = abn_rows(answers) if has_abn_inputs(answers) else []
    bas_items = bas_rows(answers) if has_bas_inputs(answers) else []
    missing_items = missing_fact_rows(answers)
    evidence_items = evidence_rows(answers, private_health_medicare)
    entity_sections, entity_evidence = taxmate_entity_routing.route_entity_returns(answers)
    evidence_items.extend(entity_evidence)
    items.extend(private_health_medicare_rows(private_health_medicare))
    items.extend(deduction_rows(deductions, answers))
    items.extend(personal_super_contribution_rows(personal_super_contributions))
    items.extend(offset_rows(offsets))
    phone = phone_answers(answers)
    items.extend(phone_rows(phone, answers))
    items.extend(wfh_rows(wfh_answers(answers)))
    items.extend(asset_rows(asset_answers(answers)))
    items.extend(complex_payment_rows(complex_payment_answers(answers)))
    items.extend(foreign_income_rows(foreign_income_answers(answers)))
    items.extend(psi_rows(psi_answers(answers)))
    items.extend(crypto_rows(crypto_answers(answers)))
    items.extend(rental_property_rows(rental_property_answers(answers)))
    items.extend(cgt_rows(cgt))
    items.extend(payg_rows(payg, answers))
    items.extend(investment_rows(investment, answers))
    items.extend(partnership_trust_share_rows(taxmate_entity_routing.individual_share_answers(answers)))
    items.extend(ess_rows(ess_answers(answers)))
    items.extend(uncommon_income_rows(answers))
    payload = {
        "income_year": income_year,
        "summary_note": "Individual return, sole-trader ABN, and BAS preparation aid. Follow each reviewed action and verified destination.",
        "items": items,
        "extracted_values": extracted_values,
        "abn_items": abn_items,
        "bas_items": bas_items,
        **entity_sections,
        "missing_facts": missing_items,
        "evidence_items": evidence_items,
    }
    for key in ("items", "abn_items", "bas_items", "company_items", "trust_items", "partnership_items", "missing_facts", "evidence_items"):
        payload[key] = [finalize_guide_row(row, income_year) for row in payload[key]]
    payload["extracted_values"] = [
        finalize_guide_row(row, income_year) for row in payload["extracted_values"]
    ]
    return payload


def base_items(
    answers: Dict[str, Any],
    private_health_medicare: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    investment = investment_answers(answers)
    payg = payg_answers(answers)
    cgt = cgt_answers(answers)
    structured_deduction_fields = {
        key
        for key in DEDUCTION_NESTED_KEYS
        if field_has_structured_item_answers(
            answers,
            key,
            DEDUCTION_ITEM_KEYS,
            "label",
            item_alias_keys(DEDUCTION_FIELD_ALIASES),
            false_only_alias_keys(DEDUCTION_FIELD_ALIASES),
        )
    }
    structured_super_contribution_fields = {
        key
        for key in SUPER_CONTRIBUTION_NESTED_KEYS
        if field_has_structured_item_answers(
            answers,
            key,
            SUPER_CONTRIBUTION_ITEM_KEYS,
            "notes",
            item_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES),
            false_only_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES),
        )
    }
    structured_offset_fields = {
        key
        for key in OFFSET_NESTED_KEYS
        if field_has_structured_item_answers(
            answers,
            key,
            OFFSET_ITEM_KEYS,
            "type",
            item_alias_keys(OFFSET_FIELD_ALIASES),
            false_only_alias_keys(OFFSET_FIELD_ALIASES),
        )
    }
    has_payg_items = bool(payg_item_values(payg.get("items")))
    has_cgt = has_cgt_inputs(cgt)
    has_phone = has_phone_inputs(phone_answers(answers))
    private_health_medicare = private_health_medicare or private_health_medicare_answers(answers)
    has_private_health_medicare = has_private_health_medicare_inputs(private_health_medicare)
    has_private_health_structure = any(
        key in answers for key in MEDICARE_PRIVATE_HEALTH_BASE_FIELDS
    )
    abn = abn_summary(answers) if has_abn_inputs(answers) else {}
    bas = bas_summary(answers) if has_bas_inputs(answers) else {}
    for spec in question_specs():
        value = investment_base_item_value(spec.key, answers, investment)
        if spec.key in MEDICARE_PRIVATE_HEALTH_BASE_FIELDS and (
            has_private_health_medicare or has_private_health_structure
        ):
            continue
        if spec.key in structured_deduction_fields:
            continue
        if spec.key in structured_super_contribution_fields:
            continue
        if spec.key in structured_offset_fields:
            continue
        if spec.key == "phone" and (
            has_phone or isinstance(answers.get("phone"), dict) or ("phone" in answers and phone_freeform_absent(answers.get("phone")))
        ):
            continue
        if spec.key in ("payg_gross", "payg_withheld", "main_occupation") and has_payg_items:
            continue
        if spec.key in REVIEWABLE_PAYG_FIELDS and has_payg_items:
            continue
        if spec.key == "interest_income" and investment_has_kind(investment, "interest_items"):
            continue
        if spec.key == "dividend_income" and investment_has_dividend_distribution_items(investment):
            continue
        if spec.key in REVIEWABLE_INVESTMENT_FIELDS and investment_has_kind(
            investment,
            investment_flat_field_key(spec.key),
        ):
            continue
        if spec.key in REVIEWABLE_PARTNERSHIP_TRUST_FIELDS and partnership_trust_share_items(answers):
            continue
        if spec.key in REVIEWABLE_CGT_FIELDS and has_cgt:
            continue
        if should_render_base_item(spec, value):
            status = base_item_status(spec.key, value)
            if spec.key in INVESTMENT_AGGREGATE_ALIASES and (
                investment_aggregate_needs_evidence(value) or investment_aggregate_alias_conflict(investment, spec.key)
            ):
                status = "Evidence"
            if spec.key in REVIEWABLE_PAYG_FIELDS and payg_aggregate_evidence_gaps(payg):
                status = "Evidence"
            rows.append(
                guide_row(
                    spec.key,
                    spec.ato_area,
                    spec.prompt,
                    display_value(value),
                    "Shown because this is a user-supplied intake value; follow the row handoff contract before any return entry.",
                    status,
                    base_item_sources(spec.key),
                    tab_text=f"{spec.prompt}: {display_value(value)}",
                    row_kind="individual-return",
                    facts=handoff_facts(
                        ("supplied-answer", spec.prompt, value),
                    ),
                )
            )
    return rows


def investment_base_item_value(key: str, answers: Dict[str, Any], investment: Dict[str, Any]) -> Any:
    if key in INVESTMENT_AGGREGATE_ALIASES:
        value = investment_aggregate_value(investment, key)
        if not is_missing(value):
            return value
    return answers.get(key)


def item_alias_keys(field_aliases: Dict[str, tuple[str, ...]], fields: Optional[Iterable[str]] = None) -> tuple[str, ...]:
    selected = set(fields) if fields is not None else set(field_aliases)
    return tuple(dict.fromkeys(alias for field, aliases in field_aliases.items() if field in selected for alias in aliases))


FALSE_ONLY_ITEM_FIELDS = frozenset(
    {
        "reimbursed",
        "employer_paid",
        "employer_provided",
        "work_private_split",
        "gst_bas_interaction",
        "duplicate_risk",
        "claim",
        "review_signal",
        "concessional_cap_review",
        "division_293_review",
    }
)


def false_only_alias_keys(field_aliases: Dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    return item_alias_keys(field_aliases, FALSE_ONLY_ITEM_FIELDS)


def false_only_placeholder_value(key: str, value: Any, false_only_keys: tuple[str, ...]) -> bool:
    if value is False:
        return True
    if key in false_only_keys and isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
        return True
    return key in false_only_keys and isinstance(value, str) and phone_bool(value) is False


def scalar_noop_item_value(value: str) -> bool:
    if contains_unknown(value):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if normalized in {"no claim", "no claims", "not claiming", "not claimed", "declined"}:
        return True
    claim_context = (
        r"(deduction|deductions|deductible|claim|claims|offset|offsets|rebate|rebates|personal\s+super|"
        r"super\s+contribution|super\s+contributions|superannuation\s+contribution|"
        r"superannuation\s+contributions)"
    )
    return bool(
        re.search(rf"\b(no|none|nil|without)\b(?:\s+\w+){{0,4}}\s+\b{claim_context}\b", normalized)
        or re.search(
            rf"\b(not|do\s+not|dont|don\s+t|did\s+not|didnt|didn\s+t|will\s+not|wont|won\s+t)\s+"
            rf"(claim|claiming|claimed|apply|applying|applied)\b(?:\s+\w+){{0,5}}\s+\b{claim_context}\b",
            normalized,
        )
        or re.search(
            rf"\b{claim_context}\b(?:\s+\w+){{0,5}}\s+\b(none|nil|not\s+claimed|not\s+claiming|"
            r"not\s+applicable|declined)\b",
            normalized,
        )
    )


def false_only_scalar_placeholder(value: Any) -> bool:
    return value is False or (
        isinstance(value, str) and (phone_bool(value) is False or scalar_noop_item_value(value))
    )


def false_only_item_placeholder(
    raw: Dict[str, Any],
    recognized_keys: tuple[str, ...],
    false_only_keys: tuple[str, ...] = (),
) -> bool:
    if not recognized_keys:
        return False
    meaningful_items = {key: value for key, value in raw.items() if has_meaningful_value(value)}
    if not meaningful_items:
        return False
    return all(
        (key in false_only_keys and false_only_placeholder_value(key, value, false_only_keys))
        or (key in AMOUNT_ONLY_FALSE_ITEM_KEYS and value is False)
        for key, value in meaningful_items.items()
    )


def false_only_item_value(
    value: Any,
    item_keys: tuple[str, ...],
    recognized_keys: tuple[str, ...],
    false_only_keys: tuple[str, ...] = (),
) -> bool:
    if isinstance(value, list):
        meaningful_items = [item for item in value if has_meaningful_value(item)]
        return bool(meaningful_items) and all(
            false_only_scalar_placeholder(item)
            or (isinstance(item, dict) and false_only_item_placeholder(item, recognized_keys, false_only_keys))
            for item in meaningful_items
        )
    if isinstance(value, dict):
        direct_values = {key: item for key, item in value.items() if key not in item_keys and has_meaningful_value(item)}
        nested_values = [value.get(key) for key in item_keys if has_meaningful_value(value.get(key))]
        direct_false_only = not direct_values or false_only_item_placeholder(direct_values, recognized_keys, false_only_keys)
        nested_false_only = not nested_values or all(
            false_only_item_value(item, item_keys, recognized_keys, false_only_keys) for item in nested_values
        )
        return (bool(direct_values) or bool(nested_values)) and direct_false_only and nested_false_only
    return False


def issue70_false_only_item_value(key: str, value: Any) -> bool:
    if key in DEDUCTION_NESTED_KEYS + SUPER_CONTRIBUTION_NESTED_KEYS + OFFSET_NESTED_KEYS:
        if false_only_scalar_placeholder(value):
            return True
    if key in DEDUCTION_NESTED_KEYS:
        return false_only_item_value(
            value,
            DEDUCTION_ITEM_KEYS,
            item_alias_keys(DEDUCTION_FIELD_ALIASES),
            false_only_alias_keys(DEDUCTION_FIELD_ALIASES),
        )
    if key in SUPER_CONTRIBUTION_NESTED_KEYS:
        return false_only_item_value(
            value,
            SUPER_CONTRIBUTION_ITEM_KEYS,
            item_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES),
            false_only_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES),
        )
    if key in OFFSET_NESTED_KEYS:
        return false_only_item_value(
            value,
            OFFSET_ITEM_KEYS,
            item_alias_keys(OFFSET_FIELD_ALIASES),
            false_only_alias_keys(OFFSET_FIELD_ALIASES),
        )
    return False


def is_recognized_item_dict(
    raw: Dict[str, Any],
    recognized_keys: tuple[str, ...],
    false_only_keys: tuple[str, ...] = (),
) -> bool:
    if false_only_item_placeholder(raw, recognized_keys, false_only_keys):
        return False
    return any(key in raw and not is_missing(raw.get(key)) for key in recognized_keys)


def raw_text_item_entry(raw_text: str, scalar_key: str) -> Dict[str, Any]:
    return {scalar_key: raw_text}


def raw_fallback_item_entry(
    raw: Dict[str, Any],
    scalar_key: str,
    recognized_keys: tuple[str, ...],
    false_only_keys: tuple[str, ...] = (),
) -> Optional[Dict[str, Any]]:
    if (
        not has_meaningful_value(raw)
        or false_only_item_placeholder(raw, recognized_keys, false_only_keys)
        or is_recognized_item_dict(raw, recognized_keys, false_only_keys)
    ):
        return None
    return raw_text_item_entry(display_value(raw), scalar_key)


def unrecognized_sibling_item_entry(
    raw: Dict[str, Any],
    item_keys: tuple[str, ...],
    scalar_key: str,
    recognized_keys: tuple[str, ...],
) -> Optional[Dict[str, Any]]:
    sibling_values = {
        key: value
        for key, value in raw.items()
        if key not in item_keys
        and key not in SUPPLEMENTAL_ITEM_NOTE_KEYS
        and key not in recognized_keys
        and has_meaningful_value(value)
    }
    if not sibling_values:
        return None
    return raw_text_item_entry(display_value(sibling_values), scalar_key)


def recognized_parent_item_entry(
    raw: Dict[str, Any],
    item_keys: tuple[str, ...],
    recognized_keys: tuple[str, ...],
    false_only_keys: tuple[str, ...] = (),
) -> Optional[Dict[str, Any]]:
    parent_values = {
        key: value
        for key, value in raw.items()
        if key not in item_keys and key in recognized_keys and has_meaningful_value(value)
    }
    if not parent_values or false_only_item_placeholder(parent_values, recognized_keys, false_only_keys):
        return None
    return parent_values


def field_has_structured_item_answers(
    answers: Dict[str, Any],
    key: str,
    item_keys: tuple[str, ...],
    scalar_key: str,
    recognized_keys: tuple[str, ...],
    false_only_keys: tuple[str, ...] = (),
) -> bool:
    value = answers.get(key)
    if isinstance(value, list):
        return bool(item_values_with_scalar_entries(value, scalar_key, recognized_keys, false_only_keys))
    if isinstance(value, dict):
        if false_only_item_value(value, item_keys, recognized_keys, false_only_keys):
            return False
        nested_items: List[Dict[str, Any]] = []
        for item_key in item_keys:
            nested_items.extend(item_key_value_entries(value.get(item_key), scalar_key, recognized_keys, false_only_keys))
        supplemental_items = supplemental_scalar_item_entries(value, item_keys, scalar_key, recognized_keys)
        parent_item = recognized_parent_item_entry(value, item_keys, recognized_keys, false_only_keys)
        fallback_item = raw_fallback_item_entry(value, scalar_key, recognized_keys, false_only_keys)
        sibling_item = unrecognized_sibling_item_entry(value, item_keys, scalar_key, recognized_keys)
        return (
            bool(nested_items)
            or bool(supplemental_items)
            or parent_item is not None
            or is_recognized_item_dict(value, recognized_keys, false_only_keys)
            or fallback_item is not None
            or sibling_item is not None
        )
    return False


def base_item_sources(key: str) -> Any:
    if key in {"private_health", "private_health_cover", "private_health_medicare", "private_health_statements", "private_health_statement"}:
        return ATO_PRIVATE_HEALTH_STATEMENT_SOURCES
    if key == "medicare_levy":
        return ATO_MEDICARE_LEVY_SOURCES
    if key in {"medicare_levy_surcharge", "mls"}:
        return ATO_MLS_SOURCES
    if key in {"spouse_had", "spouse", "spouse_details", "dependant_children", "dependants", "dependant_details"}:
        return ATO_SPOUSE_DEPENDANT_SOURCES
    if key in DEDUCTION_NESTED_KEYS:
        return ATO_DEDUCTION_SOURCES
    if key in SUPER_CONTRIBUTION_NESTED_KEYS:
        return ATO_PERSONAL_SUPER_DEDUCTION_SOURCES
    if key in OFFSET_NESTED_KEYS:
        return ATO_OFFSET_SOURCES
    if key in REVIEWABLE_INVESTMENT_FIELDS:
        return INVESTMENT_SOURCES
    if key in REVIEWABLE_PARTNERSHIP_TRUST_FIELDS:
        return [ATO_PARTNERSHIP_TRUST_INCOME_SOURCE]
    if key in REVIEWABLE_PAYG_FIELDS:
        return PAYG_SOURCES
    if key in REVIEWABLE_CGT_FIELDS:
        return ATO_CGT_SOURCES
    return ATO_INDIVIDUAL_SOURCE


def should_render_base_item(spec: QuestionSpec, value: Any) -> bool:
    if issue70_false_only_item_value(spec.key, value):
        return False
    if spec.key in PAYG_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in REVIEWABLE_PAYG_FIELDS and payg_flat_value_is_absent(spec.key, value):
        return False
    if spec.key in ESS_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in REVIEWABLE_ESS_FIELDS and (
        ess_source_declines_workflow(spec.key.removeprefix("ess_"), value)
        or ess_field_absence_value(spec.key.removeprefix("ess_"), value)
    ):
        return False
    if spec.key in COMPLEX_PAYMENT_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in REVIEWABLE_COMPLEX_PAYMENT_FIELDS and complex_payment_flat_value_is_absent(
        spec.key,
        value,
    ):
        return False
    if spec.key in FOREIGN_INCOME_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in REVIEWABLE_FOREIGN_INCOME_FIELDS and foreign_income_flat_value_is_absent(spec.key, value):
        return False
    if spec.key in FOREIGN_INCOME_FLAT_BOOLEAN_FIELDS and foreign_income_negative_claim_signal(
        foreign_income_nested_claim_key(spec.key),
        value,
    ):
        return False
    if spec.key in PSI_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in REVIEWABLE_PSI_FIELDS and (
        psi_source_declines_workflow(spec.key.removeprefix("psi_"), value)
        or psi_field_absence_value(spec.key.removeprefix("psi_"), value)
    ):
        return False
    if spec.key in CRYPTO_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in CRYPTO_FLAT_BOOLEAN_FIELDS and crypto_boolean_false(value):
        return False
    if spec.key in REVIEWABLE_CRYPTO_FIELDS and (
        crypto_source_declines_workflow(spec.key.removeprefix("crypto_"), value)
        or crypto_field_absence_value(spec.key.removeprefix("crypto_"), value)
    ):
        return False
    if spec.key in RENTAL_PROPERTY_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key == "rental_property_private_use" and rental_property_private_use_false(value):
        return False
    if spec.key in REVIEWABLE_RENTAL_PROPERTY_FIELDS and rental_property_flat_value_is_absent(spec.key, value):
        return False
    if spec.key in CGT_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if spec.key in REVIEWABLE_CGT_FIELDS and cgt_flat_value_is_absent(spec.key, value):
        return False
    if spec.key in REVIEWABLE_ABN_FIELDS and abn_flat_value_is_absent(spec.key, value):
        return False
    if spec.key in REVIEWABLE_BAS_FIELDS and bas_flat_value_is_absent(spec.key, value):
        return False
    return spec.required or has_meaningful_value(value)


def payg_flat_value_is_absent(key: str, value: Any) -> bool:
    nested_key = payg_flat_field_key(key)
    if nested_key in PAYG_ITEM_ALIASES and isinstance(value, (dict, list)):
        return not payg_item_values(value)
    return payg_source_declines_workflow(nested_key, value) or payg_field_absence_value(nested_key, value)


def payg_flat_field_key(key: str) -> str:
    return PAYG_FLAT_FIELD_KEYS.get(key, key)


def complex_payment_flat_value_is_absent(key: str, value: Any) -> bool:
    group = COMPLEX_PAYMENT_FLAT_FIELD_GROUPS.get(key)
    nested_key = complex_payment_flat_field_key(key)
    return complex_payment_source_declines_workflow(nested_key, value, group) or complex_payment_field_absence_value(
        nested_key,
        value,
        group,
    )


def complex_payment_flat_field_key(key: str) -> str:
    return COMPLEX_PAYMENT_FLAT_FIELD_KEYS.get(key, key)


def foreign_income_flat_value_is_absent(key: str, value: Any) -> bool:
    nested_key = foreign_income_flat_field_key(key)
    return foreign_income_source_declines_workflow(nested_key, value) or foreign_income_field_absence_value(
        nested_key,
        value,
    )


def foreign_income_flat_field_key(key: str) -> str:
    return FOREIGN_INCOME_FLAT_FIELD_KEYS.get(key, key)


def rental_property_flat_value_is_absent(key: str, value: Any) -> bool:
    nested_key = rental_property_flat_field_key(key)
    if nested_key == "net_loss" and rental_property_net_loss_false(value):
        return True
    return rental_property_source_declines_workflow(nested_key, value) or rental_property_field_absence_value(
        nested_key,
        value,
    )


def rental_property_flat_field_key(key: str) -> str:
    return RENTAL_PROPERTY_FLAT_FIELD_KEYS.get(key, key)


def cgt_flat_value_is_absent(key: str, value: Any) -> bool:
    nested_key = cgt_flat_field_key(key)
    if nested_key in CGT_ITEM_ALIASES:
        return not cgt_item_values(value)
    if nested_key in CGT_AMOUNT_FIELDS and isinstance(value, bool):
        return True
    if nested_key == "no_cgt" and cgt_boolean_false(value):
        return True
    if nested_key in ("records", "main_residence_property_records") and cgt_records_missing(value):
        return True
    if nested_key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS:
        return True
    if nested_key in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(value):
        return True
    return cgt_source_declines_workflow(nested_key, value) or cgt_field_absence_value(nested_key, value)


def cgt_flat_field_key(key: str) -> str:
    if key == "cgt_items":
        return "cgt_items"
    return CGT_FLAT_FIELD_KEYS.get(key, key)


def cgt_canonical_field_key(key: str) -> str:
    return CGT_FLAT_FIELD_KEYS.get(key, CGT_NESTED_FIELD_KEYS.get(key, key))


def abn_flat_value_is_absent(key: str, value: Any) -> bool:
    if abn_amount_signal_key(key) and amount_alias_default_false(value):
        return True
    return False


def bas_flat_value_is_absent(key: str, value: Any) -> bool:
    if bas_amount_signal_key(key) and amount_alias_default_false(value):
        return True
    if key == "tax_invoice_evidence":
        return True
    if key in {"gst_accounting_basis", "bas_period_coverage"} and evidence_missing(value):
        return True
    return False


def base_item_status(key: str, value: Any) -> str:
    if key in REVIEWABLE_PAYG_FIELDS:
        nested_key = payg_flat_field_key(key)
        if nested_key == "statement" and payg_statement_missing(value):
            return "Evidence"
        if nested_key == "finalised" and payg_finalised_missing(value):
            return "Evidence"
        if nested_key in PAYG_AMOUNT_FIELDS and payg_amount_malformed(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
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
    if key in REVIEWABLE_PSI_FIELDS:
        if key == "psi_contract_evidence" and psi_contract_evidence_missing(value):
            return "Evidence"
        if key in PSI_FLAT_AMOUNT_FIELDS and psi_amount_malformed(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_CRYPTO_FIELDS:
        if key == "crypto_wallet_records" and crypto_records_missing(value):
            return "Evidence"
        if key in CRYPTO_FLAT_AMOUNT_FIELDS and crypto_amount_malformed(value):
            return "Evidence"
        if key in CRYPTO_FLAT_DATE_FIELDS and crypto_date_needs_evidence(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_RENTAL_PROPERTY_FIELDS:
        nested_key = rental_property_flat_field_key(key)
        if key == "rental_property_records" and rental_property_records_missing(value):
            return "Evidence"
        if nested_key in RENTAL_PROPERTY_AMOUNT_FIELDS and rental_property_amount_malformed(value, nested_key):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_CGT_FIELDS:
        nested_key = cgt_flat_field_key(key)
        if nested_key in ("records", "main_residence_property_records") and cgt_records_missing(value):
            return "Evidence"
        if nested_key in CGT_AMOUNT_FIELDS and cgt_amount_malformed(value):
            return "Evidence"
        if nested_key in CGT_DATE_FIELDS and cgt_date_needs_evidence(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_INVESTMENT_FIELDS:
        if investment_statement_missing(value):
            return "Evidence"
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_ABN_FIELDS or key in REVIEWABLE_BAS_FIELDS or key == "gst_registered":
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    if key in REVIEWABLE_COMPLEX_FIELDS or isinstance(value, (dict, list)):
        return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"
    return "Evidence" if is_missing(value) or contains_unknown(value) else "Used"


ABN_NESTED_KEYS = ("abn_profile", "abn_business", "business", "business_profile", "sole_trader")
BAS_NESTED_KEYS = ("bas", "gst", "gst_bas", "bas_worksheet")
ABN_FIELD_ALIASES = {
    "abn": ("abn", "business_abn", "abn_number"),
    "business_name": ("business_name", "trading_name"),
    "activity": ("business_activity",),
    "start_date": ("business_start_date",),
    "end_date": ("business_end_date",),
    "gst_registered": ("gst_registered", "gst_registration_status"),
    "gst_registration_date": ("gst_registration_date", "registered_from", "registration_date"),
    "accounting_basis": ("gst_accounting_basis", "accounting_basis", "bas_accounting_basis"),
    "record_system": ("business_record_system",),
    "income_total": ("abn_income", "business_income", "income_total", "gross_income"),
    "expense_total": ("abn_expenses", "business_expenses", "expense_total"),
    "income_streams": ("business_income_streams", "income_items"),
    "expense_categories": ("business_expense_categories", "expense_items", "expenses_by_category"),
    "private_apportionment": ("business_private_apportionment", "private_apportionment", "business_private_use"),
    "home_business": ("business_home_use", "home_business", "home_based_business"),
    "motor_vehicle": ("business_motor_vehicle", "motor_vehicle", "vehicle_expenses"),
    "depreciation": ("business_depreciation", "depreciation", "depreciating_assets"),
    "capital_expense": ("business_capital_expense", "capital_expense", "capital_expenses"),
    "loss": ("business_loss", "business_losses", "loss", "net_loss"),
    "psi": ("psi", "psi_income", "personal_services_income"),
    "business_vs_hobby": ("business_vs_hobby", "business_versus_hobby", "hobby"),
    "non_commercial_loss": ("business_non_commercial_loss", "non_commercial_loss", "non_commercial_losses"),
}
ABN_NESTED_FIELD_ALIASES = {
    **ABN_FIELD_ALIASES,
    "business_name": ("business_name", "name", "trading_name"),
    "activity": ("business_activity", "activity", "industry", "description"),
    "start_date": ("business_start_date", "start_date", "started", "commencement_date"),
    "end_date": ("business_end_date", "end_date", "ceased", "cessation_date"),
    "record_system": ("business_record_system", "record_system", "records", "bookkeeping_system"),
    "income_total": ("abn_income", "business_income", "income_total", "gross_income", "income"),
    "expense_total": ("abn_expenses", "business_expenses", "expense_total", "expenses"),
    "income_streams": ("business_income_streams", "income_streams", "income_items", "income", "sales"),
    "expense_categories": ("business_expense_categories", "expense_categories", "expense_items", "expenses_by_category", "expenses"),
}
BAS_FIELD_ALIASES = {
    "gst_registered": ("gst_registered", "gst_registration_status"),
    "gst_registration_date": ("gst_registration_date",),
    "accounting_basis": ("gst_accounting_basis", "bas_accounting_basis"),
    "period": ("bas_period",),
    "period_coverage": ("bas_period_coverage",),
    "gst_collected": ("gst_collected", "gst_on_sales", "1a", "label_1a", "bas_1a"),
    "gst_credits": ("gst_credits", "gst_on_purchases", "1b", "label_1b", "bas_1b"),
    "gst_free_sales": ("gst_free_sales", "gst_free", "gst_free_supplies"),
    "input_taxed_sales": ("input_taxed_sales", "input_taxed", "input_taxed_supplies"),
    "adjustments": ("bas_adjustments", "gst_adjustments"),
    "payg_instalments": ("payg_instalments", "payg_instalment", "t7", "bas_t7"),
    "payg_withholding": ("payg_withholding", "bas_payg_withholding", "bas_payg_withheld", "w2", "bas_w2"),
    "tax_invoice_evidence": ("tax_invoice_evidence", "tax_invoices"),
}
BAS_NESTED_FIELD_ALIASES = {
    **BAS_FIELD_ALIASES,
    "gst_registered": ("gst_registered", "gst_registration_status", "registered"),
    "gst_registration_date": ("gst_registration_date", "registered_from", "registration_date"),
    "accounting_basis": ("gst_accounting_basis", "accounting_basis", "bas_accounting_basis"),
    "period": ("bas_period", "period", "tax_period"),
    "period_coverage": ("bas_period_coverage", "period_coverage", "coverage"),
    "adjustments": ("bas_adjustments", "adjustments", "gst_adjustments"),
    "payg_withholding": ("payg_withholding", "payg_withheld", "bas_payg_withholding", "bas_payg_withheld", "w2"),
    "tax_invoice_evidence": ("tax_invoice_evidence", "tax_invoices", "invoice_evidence", "invoices"),
}
BAS_CONTEXTUAL_FIELD_ALIASES = {
    "gst_registered": ("registered",),
    "gst_registration_date": ("registered_from", "registration_date"),
    "accounting_basis": ("accounting_basis",),
    "period": ("period", "tax_period"),
    "period_coverage": ("period_coverage", "coverage"),
    "adjustments": ("adjustments",),
    "tax_invoice_evidence": ("invoice_evidence", "invoices"),
}
ABN_CONTEXTUAL_FIELD_ALIASES = {
    "activity": ("activity",),
    "income_total": ("income",),
    "expense_total": ("expenses",),
}
ITEM_AMOUNT_ALIASES = ("amount", "gross", "total", "value")
ITEM_LABEL_ALIASES = ("label", "name", "description", "category", "stream", "source")
ITEM_EVIDENCE_ALIASES = ("evidence", "records", "invoice", "invoices", "tax_invoice", "statement")
ABN_COMPLEX_REVIEW_FIELDS = (
    "private_apportionment",
    "home_business",
    "motor_vehicle",
    "depreciation",
    "capital_expense",
    "loss",
    "psi",
    "business_vs_hobby",
    "non_commercial_loss",
)
ABN_BUSINESS_SIGNAL_FIELDS = (
    "abn",
    "business_name",
    "activity",
    "start_date",
    "end_date",
    "record_system",
    "income_total",
    "expense_total",
    "income_streams",
    "expense_categories",
    *ABN_COMPLEX_REVIEW_FIELDS,
)
ABN_CONTEXT_SIGNAL_FIELDS = tuple(key for key in ABN_BUSINESS_SIGNAL_FIELDS if key != "psi")
BAS_AMOUNT_FIELDS = (
    "gst_collected",
    "gst_credits",
    "gst_free_sales",
    "input_taxed_sales",
    "adjustments",
    "payg_instalments",
    "payg_withholding",
)
ABN_AMOUNT_SIGNAL_KEYS = {
    "income_total",
    "expense_total",
    "income_streams",
    "expense_categories",
    "abn_income",
    "abn_expenses",
    "business_income",
    "business_expenses",
    "business_income_streams",
    "business_expense_categories",
    "income",
    "expenses",
    "income_items",
    "expense_items",
    "expenses_by_category",
}
BAS_AMOUNT_SIGNAL_KEYS = set(BAS_AMOUNT_FIELDS).union(
    alias for field, aliases in BAS_FIELD_ALIASES.items() if field in BAS_AMOUNT_FIELDS for alias in aliases
)


def abn_amount_signal_key(key: str) -> bool:
    return key in ABN_AMOUNT_SIGNAL_KEYS


def bas_amount_signal_key(key: str) -> bool:
    return key in BAS_AMOUNT_SIGNAL_KEYS


def answer_value(answers: Dict[str, Any], aliases: tuple[str, ...], nested_keys: tuple[str, ...]) -> Any:
    value = alias_answer_value(answers, aliases)
    if value is not None and not contains_unknown(value):
        return value
    fallback = value
    for nested_key in nested_keys:
        nested = answers.get(nested_key)
        if isinstance(nested, dict):
            value = alias_answer_value(nested, aliases)
            if value is not None and not contains_unknown(value):
                return value
            if fallback is None:
                fallback = value
    return fallback


def normalized_alias_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", key.casefold())


def alias_keys(values: Dict[str, Any], alias: str) -> List[str]:
    keys: List[str] = []
    if alias in values:
        keys.append(alias)
    alias_folded = alias.casefold()
    alias_normalized = normalized_alias_key(alias)
    for key in values:
        if not isinstance(key, str) or key == alias:
            continue
        if key.casefold() == alias_folded or normalized_alias_key(key) == alias_normalized:
            keys.append(key)
    return keys


def alias_answer_value(values: Dict[str, Any], aliases: tuple[str, ...], amount: bool = False) -> Any:
    fallback = None
    for key in aliases:
        for actual_key in alias_keys(values, key):
            value = values.get(actual_key)
            if is_missing(value):
                continue
            if amount and amount_alias_default_false(value):
                if fallback is None:
                    fallback = value
                continue
            if not contains_unknown(value):
                return value
            if fallback is None:
                fallback = value
    return fallback


def alias_candidates(values: Dict[str, Any], aliases: tuple[str, ...]) -> List[Any]:
    candidates: List[Any] = []
    for key in aliases:
        for actual_key in alias_keys(values, key):
            value = values.get(actual_key)
            if not is_missing(value):
                candidates.append(value)
    return candidates


def answer_candidates(
    answers: Dict[str, Any],
    aliases: tuple[str, ...],
    nested_keys: tuple[str, ...],
    nested_aliases: tuple[str, ...],
    contextual_aliases: tuple[str, ...] = (),
) -> List[Any]:
    candidates = alias_candidates(answers, aliases)
    if contextual_aliases:
        candidates.extend(alias_candidates(answers, contextual_aliases))
    for nested_key in nested_keys:
        nested = answers.get(nested_key)
        if isinstance(nested, dict):
            candidates.extend(alias_candidates(nested, nested_aliases))
    return candidates


def normalized_alias_values(values: List[Any], amount: bool = False, gst_registration: bool = False) -> List[str]:
    normalized: List[str] = []
    for value in values:
        if is_missing(value):
            continue
        if amount and amount_alias_default_false(value):
            continue
        if amount and isinstance(value, (dict, list)):
            item_total = supplied_item_total(item_values(value))
            if item_total is not None:
                normalized.append(f"{item_total:.2f}")
            continue
        if contains_unknown(value):
            continue
        if isinstance(value, (dict, list)):
            normalized.append(json.dumps(value, sort_keys=True, default=str))
            continue
        if gst_registration:
            parsed = parse_gst_registration(value)
            if parsed is not None:
                normalized.append("true" if parsed else "false")
                continue
        if amount:
            amount_value = safe_money_value(value)
            if amount_value is not None:
                normalized.append(f"{amount_value:.2f}")
                continue
        rendered = display_value(value).strip().lower()
        if rendered:
            normalized.append(rendered)
    return normalized


def amount_alias_default_false(value: Any) -> bool:
    if value is False:
        return True
    if not isinstance(value, str):
        return False
    return value.strip().lower() in {"false", "no", "n", "off", "unchecked", "none", "n/a", "not applicable"}


def alias_values_conflict(values: List[Any], amount: bool = False, gst_registration: bool = False) -> bool:
    normalized = normalized_alias_values(values, amount=amount, gst_registration=gst_registration)
    return len(set(normalized)) > 1


def abn_alias_conflicts(answers: Dict[str, Any]) -> List[str]:
    conflicts: List[str] = []
    contextual = abn_contextual_aliases_allowed(answers)
    for key in ABN_FIELD_ALIASES:
        values = answer_candidates(
            answers,
            ABN_FIELD_ALIASES[key],
            ABN_NESTED_KEYS,
            ABN_NESTED_FIELD_ALIASES[key],
            ABN_CONTEXTUAL_FIELD_ALIASES.get(key, ()) if contextual else (),
        )
        if alias_values_conflict(
            values,
            amount=key in {"income_total", "expense_total", "income_streams", "expense_categories"},
            gst_registration=key == "gst_registered",
        ):
            conflicts.append(key)
    return conflicts


def bas_alias_conflicts(answers: Dict[str, Any]) -> List[str]:
    conflicts: List[str] = []
    contextual = has_bas_contextual_signal(answers) or has_bas_contextual_input_signal(answers)
    for key in BAS_FIELD_ALIASES:
        values = answer_candidates(
            answers,
            BAS_FIELD_ALIASES[key],
            BAS_NESTED_KEYS,
            BAS_NESTED_FIELD_ALIASES[key],
            BAS_CONTEXTUAL_FIELD_ALIASES.get(key, ()) if contextual else (),
        )
        if alias_values_conflict(values, amount=key in BAS_AMOUNT_FIELDS, gst_registration=key == "gst_registered"):
            conflicts.append(key)
    return conflicts


def abn_answer(answers: Dict[str, Any], key: str) -> Any:
    amount = key in {"income_total", "expense_total", "income_streams", "expense_categories"}
    value = alias_answer_value(answers, ABN_FIELD_ALIASES[key], amount=amount)
    if value is not None and not contains_unknown(value):
        return value
    fallback = value
    for nested_key in ABN_NESTED_KEYS:
        nested = answers.get(nested_key)
        if isinstance(nested, dict):
            value = alias_answer_value(nested, ABN_NESTED_FIELD_ALIASES[key], amount=amount)
            if value is not None and not contains_unknown(value):
                return value
            if fallback is None:
                fallback = value
    if abn_contextual_aliases_allowed(answers):
        value = alias_answer_value(answers, ABN_CONTEXTUAL_FIELD_ALIASES.get(key, ()), amount=amount)
        if value is not None and not contains_unknown(value):
            return value
        if fallback is None:
            fallback = value
    return fallback


def abn_contextual_aliases_allowed(answers: Dict[str, Any]) -> bool:
    if has_meaningful_value(answers.get("abn")) or has_meaningful_value(answers.get("business_abn")):
        return True
    for key in REVIEWABLE_ABN_FIELDS:
        if key in {"abn", "business_abn"}:
            continue
        if key in answers and abn_input_signal(key, answers.get(key)):
            return True
    for nested_key in ABN_NESTED_KEYS:
        nested = answers.get(nested_key)
        if isinstance(nested, dict):
            for aliases in ABN_NESTED_FIELD_ALIASES.values():
                if any(has_meaningful_value(value) for value in alias_candidates(nested, aliases)):
                    return True
    return False


def has_abn_contextual_alias_signal(answers: Dict[str, Any]) -> bool:
    return any(
        abn_input_signal(key, alias_answer_value(answers, aliases, amount=key in {"income_total", "expense_total"}))
        for key, aliases in ABN_CONTEXTUAL_FIELD_ALIASES.items()
    )


def bas_answer(answers: Dict[str, Any], key: str) -> Any:
    amount = key in BAS_AMOUNT_FIELDS
    value = alias_answer_value(answers, BAS_FIELD_ALIASES[key], amount=amount)
    if value is not None and not contains_unknown(value):
        return value
    fallback = value
    for nested_key in BAS_NESTED_KEYS:
        nested = answers.get(nested_key)
        if isinstance(nested, dict):
            value = alias_answer_value(nested, BAS_NESTED_FIELD_ALIASES[key], amount=amount)
            if value is not None and not contains_unknown(value):
                return value
            if fallback is None:
                fallback = value
    return fallback


def has_bas_contextual_signal(answers: Dict[str, Any]) -> bool:
    if has_meaningful_value(answers.get("gst_registered")):
        return True
    for aliases in BAS_FIELD_ALIASES.values():
        if any(has_meaningful_value(value) for value in alias_candidates(answers, aliases)):
            return True
    for nested_key in BAS_NESTED_KEYS:
        nested = answers.get(nested_key)
        if isinstance(nested, dict):
            for aliases in BAS_NESTED_FIELD_ALIASES.values():
                if any(has_meaningful_value(value) for value in alias_candidates(nested, aliases)):
                    return True
    return any(key in answers and has_meaningful_value(answers.get(key)) for key in REVIEWABLE_BAS_FIELDS)


def has_bas_contextual_input_signal(answers: Dict[str, Any], exclude: set[str] | None = None) -> bool:
    excluded = exclude or set()
    return any(
        bas_contextual_input_signal(key, alias_answer_value(answers, aliases, amount=key in BAS_AMOUNT_FIELDS))
        for key, aliases in BAS_CONTEXTUAL_FIELD_ALIASES.items()
        if key not in excluded
    )


def bas_contextual_answer(answers: Dict[str, Any], key: str) -> Any:
    candidate = alias_answer_value(answers, BAS_CONTEXTUAL_FIELD_ALIASES.get(key, ()), amount=key in BAS_AMOUNT_FIELDS)
    return candidate if bas_contextual_input_signal(key, candidate) else None


def bas_gst_registration_answer(answers: Dict[str, Any]) -> Any:
    value = bas_answer(answers, "gst_registered")
    if not is_missing(value):
        return value
    return bas_contextual_answer(answers, "gst_registered")


def bas_contextual_input_signal(key: str, value: Any) -> bool:
    if not has_meaningful_value(value):
        return False
    if key in BAS_AMOUNT_FIELDS:
        return safe_money_value(value) is not None or contains_unknown(value) or amount_malformed(value)
    lowered = display_value(value).strip().lower()
    if key == "gst_registered":
        return parse_gst_registration(value) is not None or contains_unknown(value)
    if key == "gst_registration_date":
        return contains_unknown(value) or bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", lowered))
    if key == "accounting_basis":
        return contains_unknown(value) or any(term in lowered for term in ("cash", "accrual", "non-cash", "noncash"))
    if key == "period":
        return contains_unknown(value) or bool(re.search(r"\bq[1-4]\b|quarter|monthly|annual|bas period", lowered))
    if key == "period_coverage":
        return contains_unknown(value) or any(term in lowered for term in ("full period", "partial", "coverage"))
    if key == "tax_invoice_evidence":
        return evidence_missing(value) or "invoice" in lowered
    return False


def item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict) and has_meaningful_value(item)]


def item_values_with_scalar_entries(
    raw_items: Any,
    scalar_key: str,
    recognized_keys: tuple[str, ...] = (),
    false_only_keys: tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        return []
    rows: List[Dict[str, Any]] = []
    for item in raw_items:
        if isinstance(item, dict):
            if not has_meaningful_value(item) or false_only_item_placeholder(item, recognized_keys, false_only_keys):
                continue
            if recognized_keys and not is_recognized_item_dict(item, recognized_keys, false_only_keys):
                rows.append(raw_text_item_entry(display_value(item), scalar_key))
            else:
                rows.append(item)
                if recognized_keys:
                    rows.extend(supplemental_scalar_item_entries(item, (), scalar_key, recognized_keys))
                    sibling_item = unrecognized_sibling_item_entry(item, (), scalar_key, recognized_keys)
                    if sibling_item is not None:
                        rows.append(sibling_item)
        elif false_only_scalar_placeholder(item):
            continue
        elif has_meaningful_value(item):
            rows.append({scalar_key: item})
    return rows


def item_key_value_entries(
    raw_items: Any,
    scalar_key: str,
    recognized_keys: tuple[str, ...] = (),
    false_only_keys: tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    rows = item_values_with_scalar_entries(raw_items, scalar_key, recognized_keys, false_only_keys)
    if rows or isinstance(raw_items, (dict, list)) or false_only_scalar_placeholder(raw_items) or not has_meaningful_value(raw_items):
        return rows
    return [raw_text_item_entry(display_value(raw_items), scalar_key)]


SUPPLEMENTAL_ITEM_NOTE_KEYS = frozenset({"notes", "note", "freeform", "description", "details", "other", "comments", "additional_notes"})


def supplemental_note_entries(value: Any, scalar_key: str) -> List[Dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    rows: List[Dict[str, Any]] = []
    for item in values:
        if not has_meaningful_value(item):
            continue
        if isinstance(item, (dict, list)):
            rows.append(raw_text_item_entry(display_value(item), scalar_key))
        else:
            rows.append({scalar_key: item})
    return rows


def supplemental_scalar_item_entries(
    raw: Dict[str, Any],
    item_keys: tuple[str, ...],
    scalar_key: str,
    recognized_keys: tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, value in raw.items():
        if key in item_keys or key in recognized_keys or key not in SUPPLEMENTAL_ITEM_NOTE_KEYS:
            continue
        rows.extend(supplemental_note_entries(value, scalar_key))
    return rows


def safe_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def nonnegative_money_value(value: Any) -> Optional[float]:
    amount = safe_money_value(value)
    if amount is None or amount < 0:
        return None
    return amount


def amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    if contains_unknown(value):
        return True
    try:
        money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return False


def item_amount(item: Dict[str, Any]) -> Optional[float]:
    values = item_amount_values(item)
    return values[0] if values else None


def item_amount_values(item: Dict[str, Any]) -> List[float]:
    values: List[float] = []
    for key in ITEM_AMOUNT_ALIASES:
        if key in item:
            amount = safe_money_value(item.get(key))
            if amount is not None:
                values.append(amount)
    return values


def item_amount_alias_conflict(item: Dict[str, Any]) -> bool:
    return len(set(item_amount_values(item))) > 1


def item_amount_alias_malformed(item: Dict[str, Any]) -> bool:
    return any(key in item and amount_malformed(item.get(key)) for key in ITEM_AMOUNT_ALIASES)


def item_amount_evidence_needed(item: Dict[str, Any]) -> bool:
    return item_amount(item) is None or item_amount_alias_conflict(item) or item_amount_alias_malformed(item)


def item_label(item: Dict[str, Any]) -> str:
    for key in ITEM_LABEL_ALIASES:
        if has_meaningful_value(item.get(key)):
            return display_value(item.get(key))
    return "item"


def item_evidence_value(item: Dict[str, Any]) -> Any:
    for key in ITEM_EVIDENCE_ALIASES:
        if key in item:
            return item.get(key)
    return None


def supplied_item_total(items: List[Dict[str, Any]]) -> Optional[float]:
    amounts = [item_amount(item) for item in items]
    if not amounts or any(amount is None for amount in amounts):
        return None
    return round(sum(amounts), 2)


def supplied_item_total_conflict(explicit_total: Optional[float], items: List[Dict[str, Any]]) -> bool:
    item_total = supplied_item_total(items)
    return explicit_total is not None and item_total is not None and round(explicit_total, 2) != item_total


def evidence_missing(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)) and value == 0:
        return True
    if is_missing(value) or contains_unknown(value):
        return True
    if isinstance(value, list):
        return not value or any(evidence_missing(item) for item in value)
    if isinstance(value, dict):
        return not value or any(evidence_missing(item) for item in value.values())
    lowered = text(value).strip().lower()
    uncertain = re.search(r"\b(maybe|perhaps|probably|possibly|unclear|unsure|not sure|pending|awaiting)\b", lowered) is not None
    requested = re.search(r"\b(statement|document|record|records|evidence)\s+(?:has been\s+)?requested\b", lowered) is not None
    return uncertain or requested or explicit_evidence_denial_value(value) or lowered in {
        "no",
        "n",
        "false",
        "none",
        "n/a",
        "na",
        "not applicable",
        "0",
        "not held",
        "not available",
        "not sent",
        "not lodged",
        "not received",
        "not acknowledged",
        "not confirmed",
        "missing",
    } or any(
        phrase in lowered
        for phrase in (
            "no record",
            "no records",
            "no bookkeeping records",
            "no business records",
            "record not held",
            "records not held",
            "without records",
            "no receipt",
            "no receipts",
            "receipt not held",
            "receipts not held",
            "without receipt",
            "without receipts",
            "receipt missing",
            "receipts missing",
            "no invoice",
            "no invoices",
            "no tax invoice",
            "no tax invoices",
            "missing invoice",
            "missing tax invoice",
            "invoice not held",
            "tax invoice not held",
            "invoice not applicable",
            "tax invoice not applicable",
            "records missing",
            "no statement",
            "no statements",
            "statement not held",
            "statements not held",
            "without statement",
            "without statements",
            "statement missing",
            "statements missing",
            "notice not sent",
            "notice of intent not sent",
            "noi not sent",
            "not lodged",
            "notice not lodged",
            "notice of intent not lodged",
            "no notice",
            "no notice of intent",
            "no noi",
            "no acknowledgement",
            "no acknowledgment",
            "acknowledgement not held",
            "acknowledgment not held",
            "tax invoices not available",
            "not available",
            "unavailable",
        )
    )


def item_list_text(label: str, items: List[Dict[str, Any]]) -> str:
    if not items:
        return f"{label} none supplied"
    parts = [f"{item_label(item)} {money_text(item_amount(item))}" for item in items]
    return f"{label} {', '.join(parts)}"


def review_flag_terms(raw: Dict[str, Any], keys: tuple[str, ...]) -> List[str]:
    terms: List[str] = []
    for key in keys:
        value = raw.get(key)
        if is_missing(value):
            continue
        if abn_review_flag_false(value):
            terms.append(f"{key.replace('_', ' ')} false")
        elif contains_unknown(value):
            terms.append(f"{key.replace('_', ' ')} unknown")
        else:
            terms.append(f"{key.replace('_', ' ')} review")
    return terms


def abn_review_handoff_facts(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    for key in ABN_COMPLEX_REVIEW_FIELDS:
        facts.extend(
            atomic_handoff_facts(
                key.replace("_", "-"),
                handoff_label_part(key),
                raw.get(key),
            )
        )
    return facts


def abn_summary(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = {key: abn_answer(answers, key) for key in ABN_FIELD_ALIASES}
    alias_conflicts = abn_alias_conflicts(answers)
    raw_income_total = raw.get("income_total")
    raw_expense_total = raw.get("expense_total")
    income_streams = item_values(raw.get("income_streams"))
    expense_categories = item_values(raw.get("expense_categories"))
    if isinstance(raw_income_total, (dict, list)):
        if not income_streams:
            income_streams = item_values(raw_income_total)
        raw_income_total = None
    if isinstance(raw_expense_total, (dict, list)):
        if not expense_categories:
            expense_categories = item_values(raw_expense_total)
        raw_expense_total = None
    income_total = safe_money_value(raw_income_total)
    expense_total = safe_money_value(raw_expense_total)
    if supplied_item_total_conflict(income_total, income_streams):
        alias_conflicts.append("income_total")
    if supplied_item_total_conflict(expense_total, expense_categories):
        alias_conflicts.append("expense_total")
    if any(item_amount_alias_conflict(item) for item in income_streams):
        alias_conflicts.append("income_streams")
    if any(item_amount_alias_conflict(item) for item in expense_categories):
        alias_conflicts.append("expense_categories")
    alias_conflicts = sorted(set(alias_conflicts))
    if "income_total" in alias_conflicts:
        income_total = None
    elif income_total is None and "income_streams" not in alias_conflicts:
        income_total = supplied_item_total(income_streams)
    if "expense_total" in alias_conflicts:
        expense_total = None
    elif expense_total is None and "expense_categories" not in alias_conflicts:
        expense_total = supplied_item_total(expense_categories)
    raw["income_streams"] = income_streams
    raw["expense_categories"] = expense_categories
    raw["income_total"] = income_total
    raw["expense_total"] = expense_total
    raw["alias_conflicts"] = alias_conflicts
    raw["alias_conflict"] = bool(alias_conflicts)
    raw["amount_evidence"] = (
        amount_malformed(raw_income_total)
        or amount_malformed(raw_expense_total)
        or "income_total" in alias_conflicts
        or "expense_total" in alias_conflicts
        or "income_streams" in alias_conflicts
        or "expense_categories" in alias_conflicts
        or any(item_amount_evidence_needed(item) for item in income_streams + expense_categories)
    )
    raw["record_system_required"] = any(
        has_meaningful_value(raw.get(key))
        for key in (
            "abn",
            "business_name",
            "activity",
            "start_date",
            "end_date",
            "income_total",
            "expense_total",
        )
    ) or bool(income_streams or expense_categories or raw["amount_evidence"])
    raw["record_evidence"] = raw["record_system_required"] and evidence_missing(raw.get("record_system"))
    raw["item_evidence"] = any(evidence_missing(item_evidence_value(item)) for item in income_streams + expense_categories)
    return raw


def bas_summary(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = {key: bas_answer(answers, key) for key in BAS_FIELD_ALIASES}
    alias_conflicts = bas_alias_conflicts(answers)
    if has_bas_contextual_signal(answers) or has_bas_contextual_input_signal(answers):
        for key in BAS_CONTEXTUAL_FIELD_ALIASES:
            candidate = alias_answer_value(answers, BAS_CONTEXTUAL_FIELD_ALIASES.get(key, ()), amount=key in BAS_AMOUNT_FIELDS)
            if candidate is not None and (is_missing(raw.get(key)) or contains_unknown(raw.get(key))):
                raw[key] = candidate
    for key in BAS_AMOUNT_FIELDS:
        if key in alias_conflicts:
            raw[key] = None
    raw["alias_conflicts"] = alias_conflicts
    raw["alias_conflict"] = bool(alias_conflicts)
    for key in BAS_AMOUNT_FIELDS:
        raw[f"{key}_amount"] = safe_money_value(raw.get(key))
        raw[f"{key}_malformed"] = amount_malformed(raw.get(key))
    collected = raw["gst_collected_amount"]
    credits = raw["gst_credits_amount"]
    raw["net_gst"] = None if collected is None or credits is None else round(collected - credits, 2)
    raw["invoice_evidence"] = raw["gst_credits_amount"] is not None and raw["gst_credits_amount"] > 0 and evidence_missing(
        raw.get("tax_invoice_evidence")
    )
    raw["worksheet_facts"] = any(
        has_meaningful_value(raw.get(key))
        for key in ("period", "period_coverage", "tax_invoice_evidence", *BAS_AMOUNT_FIELDS)
    )
    raw["basis_evidence"] = contains_unknown(raw.get("accounting_basis")) or (
        raw["worksheet_facts"] and evidence_missing(raw.get("accounting_basis"))
    )
    raw["period_coverage_evidence"] = contains_unknown(raw.get("period_coverage")) or (
        raw["worksheet_facts"] and evidence_missing(raw.get("period_coverage"))
    )
    return raw


def abn_answer_text(raw: Dict[str, Any]) -> str:
    flags = review_flag_terms(raw, ABN_COMPLEX_REVIEW_FIELDS)
    flag_text = ", ".join(flags) if flags else "none supplied"
    conflict_text = ", ".join(str(key).replace("_", " ") for key in raw.get("alias_conflicts", [])) or "none"
    return (
        f"ABN {display_value(raw.get('abn'))}; business {display_value(raw.get('business_name'))}; "
        f"activity {display_value(raw.get('activity'))}; dates {display_value(raw.get('start_date'))} to {display_value(raw.get('end_date'))}; "
        f"GST registered {display_value(raw.get('gst_registered'))}; GST date {display_value(raw.get('gst_registration_date'))}; "
        f"basis {display_value(raw.get('accounting_basis'))}; records {display_value(raw.get('record_system'))}; "
        f"income {money_text(raw.get('income_total'))}; expenses {money_text(raw.get('expense_total'))}; "
        f"{item_list_text('income streams', raw.get('income_streams', []))}; "
        f"{item_list_text('expense categories', raw.get('expense_categories', []))}; alias conflicts {conflict_text}; review flags {flag_text}"
    )


def bas_answer_text(raw: Dict[str, Any]) -> str:
    conflict_text = ", ".join(str(key).replace("_", " ") for key in raw.get("alias_conflicts", [])) or "none"
    return (
        f"GST registered {display_value(raw.get('gst_registered'))}; GST date {display_value(raw.get('gst_registration_date'))}; "
        f"basis {display_value(raw.get('accounting_basis'))}; period {display_value(raw.get('period'))}; "
        f"coverage {display_value(raw.get('period_coverage'))}; 1A {money_text(raw.get('gst_collected_amount'))}; "
        f"1B {money_text(raw.get('gst_credits_amount'))}; net GST {money_text(raw.get('net_gst'))}; "
        f"GST-free sales {money_text(raw.get('gst_free_sales_amount'))}; input-taxed sales {money_text(raw.get('input_taxed_sales_amount'))}; "
        f"adjustments {money_text(raw.get('adjustments_amount'))}; PAYG instalments {money_text(raw.get('payg_instalments_amount'))}; "
        f"PAYG withholding {money_text(raw.get('payg_withholding_amount'))}; tax invoices {display_value(raw.get('tax_invoice_evidence'))}; "
        f"alias conflicts {conflict_text}"
    )


def abn_tab_text(raw: Dict[str, Any]) -> str:
    terms: List[str] = []
    if raw.get("amount_evidence"):
        terms.append("amount evidence")
    if raw.get("record_evidence"):
        terms.append("record-system evidence")
    if raw.get("item_evidence"):
        terms.append("income or expense evidence")
    if raw.get("alias_conflict"):
        terms.append("alias conflict evidence")
    terms.extend(review_flag_terms(raw, ABN_COMPLEX_REVIEW_FIELDS))
    if not terms:
        terms.append("sole-trader business schedule review")
    return "ABN prep only; " + ", ".join(terms) + "."


def bas_tab_text(raw: Dict[str, Any]) -> str:
    terms: List[str] = []
    if any(raw.get(f"{key}_malformed") for key in BAS_AMOUNT_FIELDS):
        terms.append("amount evidence")
    if raw.get("invoice_evidence"):
        terms.append("tax invoice evidence")
    if raw.get("basis_evidence"):
        terms.append("accounting basis review")
    if raw.get("period_coverage_evidence"):
        terms.append("period coverage review")
    if raw.get("alias_conflict"):
        terms.append("alias conflict evidence")
    if not terms:
        terms.append("BAS worksheet review")
    return "BAS prep only. No BAS lodgment support. " + ", ".join(terms) + "."


def abn_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary = abn_summary(answers)
    status = "Accountant review" if has_abn_inputs(answers) else "N/A skipped"
    return [
        guide_row(
            "ABN",
            "Sole-trader ABN",
            "Sole-trader ABN profile, income, expenses, and review routing",
            abn_answer_text(summary),
            "Sole-trader ABN facts feed individual return business schedules and need review for PSI, losses, GST/BAS, private-use apportionment, home-business, motor vehicle, depreciation, capital items, and business-versus-hobby.",
            status,
            ATO_ABN_BUSINESS_SOURCES,
            tab_text=abn_tab_text(summary),
            row_kind="abn-business",
            facts=[
                *handoff_facts(
                    ("abn", "ABN", summary.get("abn")),
                    ("business-name", "Business name", summary.get("business_name")),
                    ("activity", "Business activity", summary.get("activity")),
                    ("start-date", "Start date", summary.get("start_date")),
                    ("end-date", "End date", summary.get("end_date")),
                    ("gst-registered", "GST registered", summary.get("gst_registered")),
                    ("gst-registration-date", "GST registration date", summary.get("gst_registration_date")),
                    ("accounting-basis", "Accounting basis", summary.get("accounting_basis")),
                    ("income-total", "Business income supplied", money_text(summary.get("income_total"))),
                    ("expense-total", "Business expenses supplied", money_text(summary.get("expense_total"))),
                    ("record-system", "Record system", summary.get("record_system")),
                ),
                *abn_review_handoff_facts(summary),
                *indexed_item_handoff_facts(
                    "abn-income-item",
                    "Business income item",
                    summary.get("income_streams", []),
                ),
                *indexed_item_handoff_facts(
                    "abn-expense-item",
                    "Business expense item",
                    summary.get("expense_categories", []),
                ),
                *atomic_handoff_facts(
                    "alias-conflict",
                    "Alias conflict",
                    summary.get("alias_conflicts", []),
                ),
            ],
        )
    ]


def bas_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    summary = bas_summary(answers)
    status = "Accountant review" if has_bas_inputs(answers) else "N/A skipped"
    return [
        guide_row(
            "BAS",
            "BAS worksheet",
            "GST/BAS prep worksheet labels and evidence",
            bas_answer_text(summary),
            "BAS worksheet only. Confirm 1A, 1B, GST-free/input-taxed sales, adjustments, PAYG labels, tax invoices, period coverage, and accounting basis before entry.",
            status,
            ATO_BAS_SOURCES,
            tab_text=bas_tab_text(summary),
            row_kind="bas",
            facts=handoff_facts(
                ("gst-registered", "GST registered", summary.get("gst_registered")),
                ("gst-registration-date", "GST registration date", summary.get("gst_registration_date")),
                ("accounting-basis", "Accounting basis", summary.get("accounting_basis")),
                ("period", "BAS period", summary.get("period")),
                ("period-coverage", "Period coverage", summary.get("period_coverage")),
                ("label-1a", "GST on sales - label 1A", money_text(summary.get("gst_collected_amount"))),
                ("label-1b", "GST on purchases - label 1B", money_text(summary.get("gst_credits_amount"))),
                ("net-gst", "Net GST worksheet amount", money_text(summary.get("net_gst"))),
                ("gst-free-sales", "GST-free sales", money_text(summary.get("gst_free_sales_amount"))),
                ("input-taxed-sales", "Input-taxed sales", money_text(summary.get("input_taxed_sales_amount"))),
                ("adjustments", "Adjustments", money_text(summary.get("adjustments_amount"))),
                ("payg-instalments", "PAYG instalments", money_text(summary.get("payg_instalments_amount"))),
                ("payg-withholding", "PAYG withholding", money_text(summary.get("payg_withholding_amount"))),
                ("tax-invoices", "Tax invoice evidence", summary.get("tax_invoice_evidence")),
                ("alias-conflicts", "Alias conflicts", ", ".join(str(key).replace("_", " ") for key in summary.get("alias_conflicts", [])) or "none"),
            ),
        )
    ]


def extraction_rows(
    raw_values: Any,
    income_year: str = DEFAULT_INCOME_YEAR,
) -> List[Dict[str, Any]]:
    if not isinstance(raw_values, list):
        return []
    rows: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_values, start=1):
        normalized = taxmate_handoff.normalize_extraction_row(
            raw,
            income_year,
            index=idx,
        )
        if normalized is not None:
            rows.append(normalized)
    return rows


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
            row_kind="missing-fact",
            facts=handoff_facts(
                ("missing-answer", spec.prompt, "Not supplied"),
            ),
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
    gst_registered = bas_gst_registration_answer(answers)
    gst_status = parse_gst_registration(gst_registered)
    if not is_missing(gst_registered):
        if gst_status is not None:
            return not (gst_status is False and bas_negative_gst_only_payg_context(answers))
        return True
    for key in REVIEWABLE_BAS_FIELDS:
        if key in answers and bas_input_signal(key, answers.get(key)):
            return True
    if has_bas_contextual_input_signal(answers):
        return True
    return any(bas_input_signal(key, bas_answer(answers, key)) for key in BAS_FIELD_ALIASES)


def bas_negative_gst_only_payg_context(answers: Dict[str, Any]) -> bool:
    if not has_payg_context_for_bare_abn(answers):
        return False
    for key in BAS_FIELD_ALIASES:
        if key == "gst_registered":
            continue
        value = bas_answer(answers, key)
        if bas_input_signal(key, value):
            return False
    return not has_bas_contextual_input_signal(answers, exclude={"gst_registered"})


def has_abn_inputs(answers: Dict[str, Any]) -> bool:
    for key in REVIEWABLE_ABN_FIELDS:
        if key == "abn" and bare_abn_is_payg(answers):
            continue
        if key in answers and abn_input_signal(key, answers.get(key)):
            return True
    if has_nested_abn_inputs(answers):
        return True
    return any(
        key != "abn" or not bare_abn_is_payg(answers)
        for key in ABN_CONTEXT_SIGNAL_FIELDS
        if abn_input_signal(key, abn_answer(answers, key))
    )


def has_nested_abn_inputs(answers: Dict[str, Any]) -> bool:
    for nested_key in ABN_NESTED_KEYS:
        nested = answers.get(nested_key)
        if not isinstance(nested, dict):
            continue
        for key in ABN_FIELD_ALIASES:
            value = alias_answer_value(
                nested,
                ABN_NESTED_FIELD_ALIASES.get(key, ()),
                amount=key in {"income_total", "expense_total", "income_streams", "expense_categories"},
            )
            if abn_input_signal(key, value):
                return True
    return False


def abn_input_signal(key: str, value: Any) -> bool:
    if not has_meaningful_value(value):
        return False
    if abn_amount_signal_key(key) and amount_alias_default_false(value):
        return False
    for review_key in ABN_COMPLEX_REVIEW_FIELDS:
        if key == review_key or key in ABN_FIELD_ALIASES.get(review_key, ()) or key in ABN_NESTED_FIELD_ALIASES.get(review_key, ()):
            return not abn_review_flag_false(value)
    return True


def bas_input_signal(key: str, value: Any) -> bool:
    if not has_meaningful_value(value):
        return False
    if bas_amount_signal_key(key) and amount_alias_default_false(value):
        return False
    if key == "tax_invoice_evidence":
        return False
    if key in {"accounting_basis", "period_coverage", "gst_accounting_basis", "bas_period_coverage"} and evidence_missing(value):
        return contains_unknown(value)
    return True


def abn_review_flag_false(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
        return True
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {
            "false",
            "no",
            "n",
            "0",
            "off",
            "unchecked",
            "none",
            "not applicable",
            "n/a",
            "no loss",
            "no business loss",
            "no home business",
            "no motor vehicle",
            "no vehicle",
            "no depreciation",
            "no capital expense",
            "no psi",
            "not psi",
            "no private apportionment",
            "no business-versus-hobby issue",
            "no business versus hobby issue",
            "no non-commercial loss",
        }
    return False


def parse_gst_registration(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if is_missing(value):
        return False
    if contains_unknown(value):
        return None
    canonical = re.sub(r"[^a-z0-9]+", " ", text(value).strip().lower()).strip()
    negation = r"(not|no|without|isn\s+t|isnt|is\s+not)"
    negative_patterns = (
        rf"\b{negation}\b(?:\s+\w+){{0,3}}\s+gst\b(?:\s+\w+){{0,3}}\s+registered\b",
        rf"\b{negation}\b(?:\s+\w+){{0,3}}\s+registered\b(?:\s+\w+){{0,3}}\s+gst\b",
        rf"\bgst\b(?:\s+\w+){{0,3}}\s+{negation}\b(?:\s+\w+){{0,3}}\s+registered\b",
        rf"\bregistered\b(?:\s+\w+){{0,3}}\s+{negation}\b(?:\s+\w+){{0,3}}\s+gst\b",
        r"\b(no|false)\b(?:\s+\w+){0,3}\s+gst\b",
        r"\bgst\b(?:\s+\w+){0,3}\s+(no|false)\b",
    )
    negative_registration = canonical in {"no", "n", "false", "not registered", "not gst registered"} or any(
        re.search(pattern, canonical) for pattern in negative_patterns
    )
    if negative_registration:
        return False
    positive_patterns = (
        r"\bgst\b(?:\s+\w+){0,3}\s+registered\b",
        r"\bregistered\b(?:\s+\w+){0,3}\s+gst\b",
        r"\b(yes|true)\b(?:\s+\w+){0,3}\s+gst\b",
        r"\bgst\b(?:\s+\w+){0,3}\s+(yes|true)\b",
    )
    positive_registration = canonical in {"yes", "y", "true", "registered", "gst registered"} or any(
        re.search(pattern, canonical) for pattern in positive_patterns
    )
    if positive_registration:
        return True
    return None


def evidence_rows(
    answers: Dict[str, Any],
    private_health_medicare: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    private_health_medicare = private_health_medicare or private_health_medicare_answers(answers)
    rows.extend(private_health_medicare_evidence_rows(private_health_medicare))
    asset_items = answers.get("assets", [])
    if not isinstance(asset_items, list):
        asset_items = []
    for item in asset_items:
        if isinstance(item, dict) and contains_unknown(item.get("evidence")):
            rows.append(evidence_row(display_value(item.get("description")), "D5 assets", "Receipt/tax invoice"))
    wfh = answers.get("wfh", {})
    if isinstance(wfh, dict) and contains_unknown(wfh.get("records")):
        rows.append(evidence_row("WFH records", "D5 WFH", "Diary, timesheet, roster, or similar records"))
    rows.extend(deduction_evidence_rows(deduction_answers(answers), answers))
    rows.extend(personal_super_contribution_evidence_rows(personal_super_contribution_answers(answers)))
    rows.extend(offset_evidence_rows(offset_answers(answers)))
    rows.extend(phone_evidence_rows(phone_answers(answers), answers))
    rows.extend(investment_evidence_rows(investment_answers(answers), answers))
    rows.extend(
        partnership_trust_share_evidence_rows(
            taxmate_entity_routing.individual_share_answers(answers)
        )
    )
    rows.extend(uncommon_income_evidence_rows(answers))
    rows.extend(payg_evidence_rows(payg_answers(answers), answers))
    rows.extend(abn_business_evidence_rows(answers))
    rows.extend(bas_evidence_rows(answers))
    rows.extend(cgt_evidence_rows(cgt_answers(answers)))
    return rows


def evidence_row(number: Any, area: str, evidence: str) -> Dict[str, Any]:
    return guide_row(
        number,
        area,
        "Evidence required",
        evidence,
        "Draft value remains not ready for entry until evidence is confirmed.",
        "Evidence",
        ATO_INDIVIDUAL_SOURCE,
        row_kind="evidence-queue",
        facts=handoff_facts(
            ("evidence-needed", "Evidence needed", evidence),
        ),
    )


PRIVATE_HEALTH_MEDICARE_NESTED_KEYS = (
    "private_health_medicare",
    "medicare_private_health",
)
PRIVATE_HEALTH_SECTION_KEYS = ("private_health", "private_health_insurance")
MEDICARE_SECTION_KEYS = ("medicare",)
PRIVATE_HEALTH_STATEMENT_KEYS = (
    "statements",
    "statement_rows",
    "private_health_statements",
    "private_health_statement",
    "private_health_insurance_statements",
    "policy_lines",
    "policies",
)
PRIVATE_HEALTH_STATEMENT_ITEM_KEYS = ("items", "rows", "lines")
PRIVATE_HEALTH_GLOBAL_STATEMENT_KEYS = (
    "private_health_statements",
    "private_health_statement",
    "private_health_insurance_statements",
)
PRIVATE_HEALTH_NOOP_TEXT = frozenset(
    {"n a", "na", "not applicable", "not applicable to me", "none"}
)
PRIVATE_HEALTH_NO_VALUE = object()
MEDICARE_LEVY_SECTION_KEYS = ("medicare_levy", "levy")
MLS_SECTION_KEYS = ("medicare_levy_surcharge", "mls", "surcharge")
SPOUSE_SECTION_KEYS = ("spouse", "spouse_details")
DEPENDANT_SECTION_KEYS = (
    "dependants",
    "dependents",
    "dependant_summary",
    "dependent_summary",
    "dependant_details",
    "dependent_details",
    "dependent_children",
    "dependant_students",
    "dependent_students",
)
PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS = (
    "items",
    "children",
    "students",
    "dependants",
    "dependents",
)
PRIVATE_HEALTH_FIELD_ALIASES = {
    "covered": (
        "covered",
        "cover",
        "private_health_cover",
        "private_hospital_cover",
        "hospital_cover",
        "appropriate_hospital_cover",
    ),
    "period_start": (
        "cover_period_start",
        "period_start",
        "cover_start",
        "start_date",
        "private_health_cover_start",
    ),
    "period_end": (
        "cover_period_end",
        "period_end",
        "cover_end",
        "end_date",
        "private_health_cover_end",
    ),
    "period": ("cover_period", "period", "period_covered", "private_health_cover_period"),
    "days_covered": ("days_covered", "hospital_cover_days", "cover_days", "private_health_days_covered"),
    "evidence": (
        "cover_evidence",
        "evidence",
        "policy_evidence",
        "records",
        "private_health_cover_evidence",
    ),
    "notes": ("notes", "note", "details", "freeform", "comments", "private_health_notes"),
    "source_urls": ("source_urls", "source_url", "sources", "private_health_source_urls"),
    "checked_at": ("checked_at", "source_checked_at", "private_health_checked_at"),
}
PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES = {
    "insurer": (
        "insurer",
        "fund",
        "health_fund",
        "insurer_name",
        "fund_name",
        "private_health_insurer",
        "private_health_fund",
    ),
    "membership_id": (
        "membership_id",
        "membership",
        "membership_identifier",
        "membership_number",
        "policy_id",
        "policy_identifier",
        "policy_number",
        "policy",
        "identifier",
        "private_health_membership_id",
        "private_health_membership_number",
        "private_health_policy_id",
        "private_health_policy_number",
    ),
    "benefit_code": ("benefit_code", "benefit", "benefit_label", "label_l", "private_health_benefit_code"),
    "premiums_eligible_for_rebate": (
        "premiums_eligible_for_rebate",
        "premiums_eligible",
        "eligible_premiums",
        "premium",
        "premiums",
        "label_j",
        "private_health_premiums_eligible_for_rebate",
    ),
    "rebate_received": (
        "rebate_received",
        "government_rebate_received",
        "australian_government_rebate_received",
        "rebate",
        "label_k",
        "private_health_rebate_received",
    ),
    "tax_claim_code": ("tax_claim_code", "claim_code", "tax_code", "private_health_tax_claim_code"),
    "days_covered": (
        "days_covered",
        "hospital_cover_days",
        "cover_days",
        "private_health_days_covered",
        "private_health_statement_days_covered",
    ),
    "period_start": (
        "period_start",
        "cover_period_start",
        "start_date",
        "private_health_statement_period_start",
    ),
    "period_end": (
        "period_end",
        "cover_period_end",
        "end_date",
        "private_health_statement_period_end",
    ),
    "period": ("period", "period_covered", "cover_period", "private_health_statement_period"),
    "evidence": (
        "evidence",
        "statement_evidence",
        "statement",
        "record",
        "records",
        "document",
        "private_health_statement_evidence",
    ),
    "notes": ("notes", "note", "details", "freeform", "comments"),
    "source_urls": ("source_urls", "source_url", "sources"),
    "checked_at": ("checked_at", "source_checked_at"),
}
MEDICARE_LEVY_FIELD_ALIASES = {
    "reduction": ("reduction", "reduction_signal", "medicare_levy_reduction", "levy_reduction"),
    "exemption": ("exemption", "exemption_signal", "medicare_levy_exemption", "levy_exemption"),
    "exemption_category": ("exemption_category", "category", "medicare_levy_exemption_category"),
    "full_exemption_days": ("full_exemption_days", "full_levy_exemption_days"),
    "half_exemption_days": ("half_exemption_days", "half_levy_exemption_days"),
    "evidence": (
        "evidence",
        "levy_evidence",
        "medicare_levy_evidence",
        "exemption_evidence",
        "reduction_evidence",
        "records",
    ),
    "notes": ("notes", "note", "details", "freeform", "comments"),
    "source_urls": ("source_urls", "source_url", "sources"),
    "checked_at": ("checked_at", "source_checked_at"),
}
MLS_FIELD_ALIASES = {
    "review": ("review", "review_signal", "mls_review", "surcharge_review"),
    "full_year_appropriate_family_cover": (
        "full_year_appropriate_family_cover",
        "all_dependants_full_year_appropriate_hospital_cover",
        "you_and_all_dependants_covered_by_appropriate_hospital_cover_full_year",
        "mls_full_year_appropriate_family_cover",
    ),
    "income_for_surcharge": (
        "income_for_surcharge",
        "mls_income",
        "income_for_mls",
        "surcharge_income",
        "mls_income_for_surcharge",
    ),
    "income_tier": ("income_tier", "mls_income_tier", "tier", "surcharge_tier"),
    "appropriate_hospital_cover": (
        "appropriate_hospital_cover",
        "hospital_cover",
        "private_hospital_cover",
        "covered",
        "mls_appropriate_hospital_cover",
    ),
    "hospital_cover_days": ("hospital_cover_days", "days_covered", "cover_days", "mls_hospital_cover_days"),
    "days_not_liable": ("days_not_liable", "days_no_surcharge", "mls_exemption_days", "mls_days_not_liable"),
    "period_start": ("period_start", "cover_period_start", "start_date"),
    "period_end": ("period_end", "cover_period_end", "end_date"),
    "period": ("period", "cover_period", "period_covered"),
    "evidence": ("evidence", "mls_evidence", "cover_evidence", "records"),
    "notes": ("notes", "note", "details", "freeform", "comments"),
    "source_urls": ("source_urls", "source_url", "sources"),
    "checked_at": ("checked_at", "source_checked_at"),
}
SPOUSE_FIELD_ALIASES = {
    "had_spouse": ("had_spouse", "spouse_had", "has_spouse"),
    "period_start": ("period_start", "spouse_period_start", "start_date", "spouse_start"),
    "period_end": ("period_end", "spouse_period_end", "end_date", "spouse_end"),
    "period": ("period", "spouse_period", "relationship_period"),
    "income_for_tests": (
        "income_for_tests",
        "spouse_income_for_tests",
        "spouse_income_test",
        "spouse_taxable_income",
        "taxable_income",
    ),
    "reportable_fringe_benefits": ("reportable_fringe_benefits", "spouse_reportable_fringe_benefits"),
    "reportable_super": ("reportable_super", "spouse_reportable_super", "reportable_super_contributions"),
    "net_investment_loss": ("net_investment_loss", "spouse_net_investment_loss"),
    "income_evidence": ("income_evidence", "spouse_income_evidence", "evidence", "records"),
    "notes": ("notes", "note", "details", "freeform", "comments"),
    "source_urls": ("source_urls", "source_url", "sources"),
    "checked_at": ("checked_at", "source_checked_at"),
}
DEPENDANT_SUMMARY_FIELD_ALIASES = {
    "count": (
        "count",
        "dependant_count",
        "dependent_count",
        "dependant_children",
        "dependent_children_count",
    ),
    "notes": ("notes", "note", "details", "freeform", "comments"),
    "source_urls": ("source_urls", "source_url", "sources"),
    "checked_at": ("checked_at", "source_checked_at"),
}
DEPENDANT_FIELD_ALIASES = {
    "name": ("name", "label", "dependant", "dependent"),
    "type": ("type", "kind", "category", "dependant_type", "dependent_type"),
    "age": ("age", "age_at_year_end"),
    "student": ("student", "is_student", "full_time_student"),
    "period_start": ("period_start", "maintained_from", "start_date"),
    "period_end": ("period_end", "maintained_to", "end_date"),
    "period": ("period", "maintenance_period"),
    "maintained": ("maintained", "financially_maintained", "maintenance"),
    "income_for_tests": ("income_for_tests", "adjusted_taxable_income", "income", "dependant_income"),
    "shared_care": ("shared_care", "shared_care_percentage"),
    "evidence": ("evidence", "student_evidence", "maintenance_evidence", "records"),
    "notes": ("notes", "note", "details", "freeform", "comments"),
    "source_urls": ("source_urls", "source_url", "sources"),
    "checked_at": ("checked_at", "source_checked_at"),
}
PRIVATE_HEALTH_DEPENDANT_DENIAL_KEYS = (
    "status",
    *DEPENDANT_SUMMARY_FIELD_ALIASES["count"],
)
PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS = (
    "value",
    "answer",
    "response",
    "count",
    "status",
)
PRIVATE_HEALTH_MLS_INHERITED_FIELDS = (
    "covered",
    "period_start",
    "period_end",
    "period",
    "days_covered",
    "evidence",
    "source_urls",
    "checked_at",
)

PRIVATE_HEALTH_STATEMENT_FLAT_FIELD_ALIASES = {
    field: tuple(alias for alias in aliases if alias.startswith("private_health_"))
    for field, aliases in PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES.items()
}
MEDICARE_LEVY_FLAT_FIELD_ALIASES = {
    "reduction": ("medicare_levy_reduction", "levy_reduction"),
    "exemption": ("medicare_levy_exemption", "levy_exemption"),
    "exemption_category": ("medicare_levy_exemption_category",),
    "full_exemption_days": ("full_levy_exemption_days",),
    "half_exemption_days": ("half_levy_exemption_days",),
    "evidence": ("levy_evidence", "medicare_levy_evidence", "exemption_evidence", "reduction_evidence"),
}
MLS_FLAT_FIELD_ALIASES = {
    "review": ("mls_review", "surcharge_review"),
    "income_for_surcharge": ("mls_income", "income_for_mls", "surcharge_income", "mls_income_for_surcharge"),
    "income_tier": ("mls_income_tier", "surcharge_tier"),
    "appropriate_hospital_cover": ("appropriate_hospital_cover",),
    "hospital_cover_days": ("mls_hospital_cover_days",),
    "days_not_liable": ("days_no_surcharge", "mls_exemption_days"),
    "evidence": ("mls_evidence",),
}
SPOUSE_FLAT_FIELD_ALIASES = {
    "had_spouse": ("spouse_had", "has_spouse"),
    "period_start": ("spouse_period_start", "spouse_start"),
    "period_end": ("spouse_period_end", "spouse_end"),
    "period": ("spouse_period", "relationship_period"),
    "income_for_tests": ("spouse_income_for_tests", "spouse_income_test", "spouse_taxable_income"),
    "reportable_fringe_benefits": ("spouse_reportable_fringe_benefits",),
    "reportable_super": ("spouse_reportable_super",),
    "net_investment_loss": ("spouse_net_investment_loss",),
    "income_evidence": ("spouse_income_evidence",),
}
DEPENDANT_SUMMARY_FLAT_FIELD_ALIASES = {
    "count": (
        "dependant_count",
        "dependent_count",
        "dependant_children",
        "dependent_children_count",
    ),
}
PRIVATE_HEALTH_WORKFLOW_NOTE_KEYS = ("notes", "note", "details", "freeform", "comments")
PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS = ("source_urls", "source_url", "sources", "checked_at", "source_checked_at")
PRIVATE_HEALTH_MEDICARE_FLAT_FIELD_ALIASES = {
    "private_health": PRIVATE_HEALTH_FIELD_ALIASES,
    "statement": PRIVATE_HEALTH_STATEMENT_FLAT_FIELD_ALIASES,
    "medicare_levy": MEDICARE_LEVY_FLAT_FIELD_ALIASES,
    "mls": {
        **MLS_FLAT_FIELD_ALIASES,
        "appropriate_hospital_cover": ("mls_appropriate_hospital_cover",),
        "days_not_liable": ("mls_exemption_days", "mls_days_not_liable"),
    },
    "spouse": SPOUSE_FLAT_FIELD_ALIASES,
    "dependant_summary": DEPENDANT_SUMMARY_FLAT_FIELD_ALIASES,
}
PRIVATE_HEALTH_GLOBAL_FLAT_FIELD_ALIASES = {
    "private_health": {
        "covered": ("private_health_cover", "private_hospital_cover"),
        "period_start": ("private_health_cover_start",),
        "period_end": ("private_health_cover_end",),
        "period": ("private_health_cover_period",),
        "days_covered": ("private_health_days_covered",),
        "evidence": ("private_health_cover_evidence",),
        "notes": ("private_health_notes",),
        "source_urls": ("private_health_source_urls",),
        "checked_at": ("private_health_checked_at",),
    },
    "statement": PRIVATE_HEALTH_STATEMENT_FLAT_FIELD_ALIASES,
    "medicare_levy": MEDICARE_LEVY_FLAT_FIELD_ALIASES,
    "mls": MLS_FLAT_FIELD_ALIASES,
    "spouse": {
        **SPOUSE_FLAT_FIELD_ALIASES,
        "period": ("spouse_period",),
    },
    "dependant_summary": DEPENDANT_SUMMARY_FLAT_FIELD_ALIASES,
}
PRIVATE_HEALTH_SUPPORTED_BENEFIT_CODES = frozenset({"30", "31", "35", "36", "40", "41"})
PRIVATE_HEALTH_FULL_YEAR_VALUES = frozenset(
    {
        "full year",
        "whole year",
        "all year",
        "income year",
        "full income year",
        "whole income year",
        "entire income year",
    }
)


DEDUCTION_NESTED_KEYS = ("deductions", "individual_deductions", "employee_deductions")
DEDUCTION_ITEM_KEYS = ("items", "deduction_items", "employee_deductions", "individual_deductions")
DEDUCTION_FIELD_ALIASES = {
    "label": ("label", "name", "description", "category"),
    "kind": ("type", "kind", "deduction_type", "category"),
    "amount": ("amount", "cost", "expense", "claim_amount"),
    "evidence": ("evidence", "receipt", "receipts", "invoice", "record", "records", "statement"),
    "reimbursed": ("reimbursed", "employer_reimbursed", "reimbursement"),
    "employer_paid": ("employer_paid", "paid_by_employer", "work_paid"),
    "employer_provided": ("employer_provided", "provided_by_employer", "work_provided"),
    "work_use_percent": ("work_use_percent", "work_percent", "business_use_percent"),
    "private_use_percent": ("private_use_percent", "private_percent", "personal_use_percent"),
    "work_private_split": ("work_private_split", "apportionment", "private_use", "mixed_use"),
    "gst_bas_interaction": ("gst_bas_interaction", "gst_credit_claimed", "bas_claimed", "gst_registered", "tax_invoice"),
    "duplicate_risk": ("duplicate_risk", "also_claimed_in", "duplicate_with", "overlap"),
}
DEDUCTION_KIND_LABELS = {
    "gift": "Gifts/donations",
    "tax_affairs": "Cost of managing tax affairs",
    "income_protection": "Income protection insurance",
    "self_education": "Self-education",
    "union_professional": "Union/professional fees",
    "travel": "Work travel/car/public transport",
    "tools_assets": "Tools/equipment/assets",
}
SUPER_CONTRIBUTION_NESTED_KEYS = ("personal_super_contributions", "personal_super_deductions", "super_contribution_deductions")
SUPER_CONTRIBUTION_ITEM_KEYS = ("items", "contributions", "personal_super_contributions")
SUPER_CONTRIBUTION_FIELD_ALIASES = {
    "fund": ("fund", "super_fund", "fund_name"),
    "member": ("member", "member_name", "account_holder"),
    "contribution_date": ("contribution_date", "date", "paid_date", "payment_date"),
    "amount": ("amount", "contribution_amount", "paid_amount"),
    "notice_of_intent": ("notice_of_intent", "noi", "notice"),
    "fund_acknowledgement": ("fund_acknowledgement", "acknowledgement", "fund_acknowledgment"),
    "intended_deduction_amount": ("intended_deduction_amount", "deduction_amount", "claim_amount"),
    "concessional_cap_review": ("concessional_cap_review", "cap_review", "cap_uncertainty"),
    "division_293_review": ("division_293_review", "div293_review", "division_293"),
    "notes": ("notes", "note", "freeform", "description"),
}
OFFSET_NESTED_KEYS = ("individual_offsets", "offsets", "tax_offsets")
OFFSET_ITEM_KEYS = ("items", "offset_items", "individual_offsets")
OFFSET_FIELD_ALIASES = {
    "kind": ("type", "kind", "offset_type", "label", "name"),
    "claim": ("claim", "claimed", "claiming", "eligible", "applying"),
    "amount": ("amount", "claim_amount", "offset_amount"),
    "evidence": ("evidence", "record", "records", "statement"),
    "review_signal": ("review_signal", "review", "eligibility", "notes"),
}
FALSE_CONCRETE_ALIAS_GROUPS = (
    PRIVATE_HEALTH_FIELD_ALIASES["evidence"],
    PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["evidence"],
    MEDICARE_LEVY_FIELD_ALIASES["evidence"],
    MLS_FIELD_ALIASES["evidence"],
    SPOUSE_FIELD_ALIASES["income_evidence"],
    DEPENDANT_FIELD_ALIASES["evidence"],
    DEDUCTION_FIELD_ALIASES["evidence"],
    SUPER_CONTRIBUTION_FIELD_ALIASES["notice_of_intent"],
    SUPER_CONTRIBUTION_FIELD_ALIASES["fund_acknowledgement"],
    OFFSET_FIELD_ALIASES["evidence"],
)
BOOLEAN_FALSE_CONCRETE_ALIAS_GROUPS = (
    PRIVATE_HEALTH_FIELD_ALIASES["covered"],
    MEDICARE_LEVY_FIELD_ALIASES["reduction"],
    MEDICARE_LEVY_FIELD_ALIASES["exemption"],
    MLS_FIELD_ALIASES["review"],
    MLS_FIELD_ALIASES["full_year_appropriate_family_cover"],
    MLS_FIELD_ALIASES["appropriate_hospital_cover"],
    SPOUSE_FIELD_ALIASES["had_spouse"],
    DEPENDANT_FIELD_ALIASES["student"],
    DEPENDANT_FIELD_ALIASES["maintained"],
    DEDUCTION_FIELD_ALIASES["reimbursed"],
    DEDUCTION_FIELD_ALIASES["employer_paid"],
    DEDUCTION_FIELD_ALIASES["employer_provided"],
    DEDUCTION_FIELD_ALIASES["work_private_split"],
    DEDUCTION_FIELD_ALIASES["gst_bas_interaction"],
    DEDUCTION_FIELD_ALIASES["duplicate_risk"],
    SUPER_CONTRIBUTION_FIELD_ALIASES["concessional_cap_review"],
    SUPER_CONTRIBUTION_FIELD_ALIASES["division_293_review"],
    OFFSET_FIELD_ALIASES["claim"],
    OFFSET_FIELD_ALIASES["review_signal"],
)
AMOUNT_ONLY_FALSE_ITEM_KEYS = tuple(
    dict.fromkeys(
        (
            *DEDUCTION_FIELD_ALIASES["amount"],
            *PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["premiums_eligible_for_rebate"],
            *PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["rebate_received"],
            *MEDICARE_LEVY_FIELD_ALIASES["full_exemption_days"],
            *MEDICARE_LEVY_FIELD_ALIASES["half_exemption_days"],
            *MLS_FIELD_ALIASES["income_for_surcharge"],
            *MLS_FIELD_ALIASES["hospital_cover_days"],
            *MLS_FIELD_ALIASES["days_not_liable"],
            *SPOUSE_FIELD_ALIASES["income_for_tests"],
            *DEPENDANT_SUMMARY_FIELD_ALIASES["count"],
            *DEPENDANT_FIELD_ALIASES["age"],
            *DEPENDANT_FIELD_ALIASES["income_for_tests"],
            *SUPER_CONTRIBUTION_FIELD_ALIASES["amount"],
            *SUPER_CONTRIBUTION_FIELD_ALIASES["intended_deduction_amount"],
            *OFFSET_FIELD_ALIASES["amount"],
        )
    )
)


def deduction_answers(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    return normalized_item_answers(
        answers,
        DEDUCTION_NESTED_KEYS,
        DEDUCTION_ITEM_KEYS,
        "label",
        item_alias_keys(DEDUCTION_FIELD_ALIASES),
        false_only_alias_keys(DEDUCTION_FIELD_ALIASES),
    )


def personal_super_contribution_answers(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    return normalized_item_answers(
        answers,
        SUPER_CONTRIBUTION_NESTED_KEYS,
        SUPER_CONTRIBUTION_ITEM_KEYS,
        "notes",
        item_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES),
        false_only_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES),
    )


def offset_answers(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    return normalized_item_answers(
        answers,
        OFFSET_NESTED_KEYS,
        OFFSET_ITEM_KEYS,
        "type",
        item_alias_keys(OFFSET_FIELD_ALIASES),
        false_only_alias_keys(OFFSET_FIELD_ALIASES),
    )


def normalized_item_answers(
    answers: Dict[str, Any],
    nested_keys: tuple[str, ...],
    item_keys: tuple[str, ...],
    scalar_key: str,
    recognized_keys: tuple[str, ...],
    false_only_keys: tuple[str, ...] = (),
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key in nested_keys:
        value = answers.get(key)
        if isinstance(value, list):
            rows.extend(item_values_with_scalar_entries(value, scalar_key, recognized_keys, false_only_keys))
        elif isinstance(value, dict):
            if false_only_item_value(value, item_keys, recognized_keys, false_only_keys):
                continue
            nested_items: List[Dict[str, Any]] = []
            for item_key in item_keys:
                nested_items.extend(item_key_value_entries(value.get(item_key), scalar_key, recognized_keys, false_only_keys))
            supplemental_items = supplemental_scalar_item_entries(value, item_keys, scalar_key, recognized_keys)
            parent_item = recognized_parent_item_entry(value, item_keys, recognized_keys, false_only_keys)
            sibling_item = unrecognized_sibling_item_entry(value, item_keys, scalar_key, recognized_keys)
            if nested_items:
                rows.extend(nested_items)
                if parent_item is not None:
                    rows.append(parent_item)
                rows.extend(supplemental_items)
                if sibling_item is not None:
                    rows.append(sibling_item)
            elif is_recognized_item_dict(value, recognized_keys, false_only_keys):
                rows.append(value)
                rows.extend(supplemental_items)
                if sibling_item is not None:
                    rows.append(sibling_item)
            elif supplemental_items:
                rows.extend(supplemental_items)
                if sibling_item is not None:
                    rows.append(sibling_item)
            else:
                fallback_item = raw_fallback_item_entry(value, scalar_key, recognized_keys, false_only_keys)
                if fallback_item is not None:
                    rows.append(fallback_item)
    return rows


def false_concrete_alias_group(aliases: tuple[str, ...], *, include_boolean: bool = False) -> bool:
    return aliases in FALSE_CONCRETE_ALIAS_GROUPS or (include_boolean and aliases in BOOLEAN_FALSE_CONCRETE_ALIAS_GROUPS)


def concrete_item_alias_value(value: Any, false_is_concrete: bool = False) -> bool:
    if is_missing(value):
        return False
    if contains_unknown(value) and not explicit_evidence_denial_value(value):
        return False
    if value is False:
        return false_is_concrete
    if isinstance(value, str) and phone_bool(value) is False:
        return false_is_concrete
    return has_meaningful_value(value)


def explicit_evidence_denial_value(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    evidence_context = r"(receipt|receipts|statement|statements|invoice|invoices|record|records|evidence|notice|intent|acknowledgement|acknowledgment)"
    return bool(
        re.search(rf"\b(no|without|missing)\b(?:\s+\w+){{0,3}}\s+\b{evidence_context}\b", normalized)
        or re.search(
            rf"\b(?:do|does|did)\s+not\s+(?:currently\s+)?(?:have|hold|receive|retain|possess)\b(?:\s+\w+){{0,3}}\s+\b{evidence_context}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:(?:don|doesn|didn)\s+t|dont|doesnt|didnt)\s+(?:currently\s+)?(?:have|hold|receive|retain|possess)\b(?:\s+\w+){{0,3}}\s+\b{evidence_context}\b",
            normalized,
        )
        or re.search(
            rf"\b{evidence_context}\b(?:\s+\w+){{0,3}}\s+\b(missing|not held|not available|not sent|not supplied|not provided|not lodged|not received|not acknowledged|not confirmed)\b",
            normalized,
        )
    )


def normalized_item_field(item: Dict[str, Any], aliases: tuple[str, ...]) -> Any:
    values = [item.get(key) for key in aliases if key in item and not is_missing(item.get(key))]
    false_is_concrete = false_concrete_alias_group(aliases)
    for value in values:
        if concrete_item_alias_value(value, false_is_concrete):
            return value
    for value in values:
        if contains_unknown(value):
            return value
    for value in values:
        if has_meaningful_value(value) or value is False:
            return value
    return None


ITEM_ALIAS_AMOUNT_FIELDS = frozenset(
    {
        "amount",
        "intended_deduction_amount",
        "premiums_eligible_for_rebate",
        "rebate_received",
        "full_exemption_days",
        "half_exemption_days",
        "income_for_surcharge",
        "hospital_cover_days",
        "days_not_liable",
        "income_for_tests",
        "count",
        "age",
    }
)
ITEM_ALIAS_EVIDENCE_FIELDS = frozenset(
    {
        "evidence",
        "income_evidence",
        "notice_of_intent",
        "fund_acknowledgement",
    }
)
ITEM_ALIAS_BOOLEAN_FIELDS = frozenset(
    {
        "reimbursed",
        "employer_paid",
        "employer_provided",
        "work_private_split",
        "gst_bas_interaction",
        "duplicate_risk",
        "concessional_cap_review",
        "division_293_review",
        "claim",
        "review_signal",
        "covered",
        "reduction",
        "exemption",
        "review",
        "appropriate_hospital_cover",
        "had_spouse",
        "student",
        "maintained",
    }
)


def item_alias_conflict_key(field: str, value: Any) -> tuple[str, str]:
    if field in ITEM_ALIAS_EVIDENCE_FIELDS:
        return ("evidence", "missing" if evidence_missing(value) else "present")
    if field in ITEM_ALIAS_AMOUNT_FIELDS:
        amount = safe_money_value(value)
        if amount is not None:
            return ("money", f"{amount:.2f}")
    parsed_bool = phone_bool(value)
    if parsed_bool is not None:
        return ("bool", str(parsed_bool))
    if field in ITEM_ALIAS_BOOLEAN_FIELDS and item_alias_negative_boolean_value(field, value):
        return ("bool", "False")
    amount = safe_money_value(value)
    if amount is not None:
        return ("money", f"{amount:.2f}")
    return ("text", display_value(value).strip().casefold())


def item_alias_negative_boolean_value(field: str, value: Any) -> bool:
    if is_missing(value) or contains_unknown(value):
        return False
    if field == "claim":
        return offset_claim_false(value)
    if field == "work_private_split":
        return deduction_private_use_negative(value)
    if field in {"concessional_cap_review", "division_293_review", "review_signal"}:
        return review_flag_negative(value)
    return deduction_flag_negative(value)


def item_alias_conflict_details(item: Dict[str, Any], field_aliases: Dict[str, tuple[str, ...]]) -> List[str]:
    details: List[str] = []
    for field, aliases in field_aliases.items():
        false_is_concrete = false_concrete_alias_group(aliases, include_boolean=True)
        values = [
            (alias, item.get(alias))
            for alias in aliases
            if alias in item and concrete_item_alias_value(item.get(alias), false_is_concrete)
        ]
        if len(values) < 2:
            continue
        keys = {item_alias_conflict_key(field, value) for _, value in values}
        if len(keys) > 1:
            rendered = "; ".join(f"{alias} {display_value(value)}" for alias, value in values)
            details.append(f"{field.replace('_', ' ')} alias conflict ({rendered})")
    return details


def item_alias_conflict_text(item: Dict[str, Any], field_aliases: Dict[str, tuple[str, ...]]) -> str:
    return "; ".join(item_alias_conflict_details(item, field_aliases))


def private_health_medicare_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    roots: List[Dict[str, Any]] = []
    notes: List[Any] = []
    supplemental_metadata: Dict[str, Any] = {}
    for value in private_health_key_values(answers, PRIVATE_HEALTH_MEDICARE_NESTED_KEYS):
        roots.extend(private_health_collection_entries(value))
        notes.extend(private_health_collection_notes(value))

    record_groups: Dict[str, List[Dict[str, Any]]] = {
        "private_health": [],
        "medicare_levy": [],
        "mls": [],
        "spouse": [],
        "dependant_summary": [],
    }
    root_known_keys = private_health_root_known_keys()
    for root in roots:
        group_root = {
            key: value
            for key, value in root.items()
            if key not in PRIVATE_HEALTH_WORKFLOW_NOTE_KEYS
        }
        private_health_append_record_groups(
            group_root,
            record_groups,
            global_scope=False,
        )
        notes.extend(private_health_workflow_notes(root))
        private_health_add_metadata(
            supplemental_metadata,
            private_health_workflow_note_metadata(root),
            PRIVATE_HEALTH_FIELD_ALIASES,
        )
        medicare = root.get("medicare")
        if isinstance(medicare, dict):
            private_health_append_medicare_groups(medicare, record_groups)
            wrapper_unknown = private_health_medicare_wrapper_unknown(medicare)
            if wrapper_unknown:
                notes.append({"medicare": wrapper_unknown})
        unknown = private_health_unknown_values(root, root_known_keys)
        if unknown:
            notes.append(unknown)
            private_health_add_metadata(
                supplemental_metadata,
                private_health_unknown_metadata(root, root_known_keys),
                PRIVATE_HEALTH_FIELD_ALIASES,
            )

    private_health_append_record_groups(answers, record_groups, global_scope=True)

    medicare = answers.get("medicare")
    if isinstance(medicare, dict):
        private_health_append_medicare_groups(medicare, record_groups)
        unknown = private_health_medicare_wrapper_unknown(medicare)
        if unknown:
            notes.append({"medicare": unknown})
    elif private_health_freeform_value(medicare):
        notes.append({"medicare": medicare})

    result = {
        "private_health": private_health_merge_records(
            record_groups["private_health"],
            PRIVATE_HEALTH_FIELD_ALIASES,
        ),
        "statements": private_health_statement_answers(answers),
        "medicare_levy": private_health_merge_records(
            record_groups["medicare_levy"],
            MEDICARE_LEVY_FIELD_ALIASES,
        ),
        "mls": private_health_merge_records(record_groups["mls"], MLS_FIELD_ALIASES),
        "spouse": private_health_merge_records(record_groups["spouse"], SPOUSE_FIELD_ALIASES),
        "dependant_summary": private_health_normalize_dependant_summary(
            private_health_merge_records(
                record_groups["dependant_summary"],
                DEPENDANT_SUMMARY_FIELD_ALIASES,
            )
        ),
        "dependants": private_health_dependant_answers(answers),
        "notes": private_health_unique_values(notes),
    }
    result["private_health_cover"] = normalized_item_field(
        result["private_health"],
        PRIVATE_HEALTH_FIELD_ALIASES["covered"],
    )
    result["spouse_had"] = normalized_item_field(result["spouse"], SPOUSE_FIELD_ALIASES["had_spouse"])
    result["dependant_children"] = normalized_item_field(
        result["dependant_summary"],
        DEPENDANT_SUMMARY_FIELD_ALIASES["count"],
    )
    private_health_capture_cover_lineage(
        result["private_health"],
        record_groups["private_health"],
    )
    private_health_add_metadata(
        result["private_health"],
        supplemental_metadata,
        PRIVATE_HEALTH_FIELD_ALIASES,
    )
    dependant_notes = private_health_dependant_collection_notes(answers)
    if dependant_notes:
        result["dependant_summary"]["dependant_supplemental_facts"] = dependant_notes
    private_health_add_metadata(
        result["dependant_summary"],
        private_health_dependant_collection_metadata(answers),
        DEPENDANT_SUMMARY_FIELD_ALIASES,
    )
    for metadata in (
        private_health_statement_collection_metadata(answers),
        private_health_medicare_supplemental_metadata(answers),
    ):
        private_health_add_metadata(
            result["private_health"],
            metadata,
            PRIVATE_HEALTH_FIELD_ALIASES,
        )
    income_year = text(answers.get("income_year"), DEFAULT_INCOME_YEAR)
    result["income_year"] = income_year
    for key in ("private_health", "medicare_levy", "mls", "spouse", "dependant_summary"):
        record = result.get(key)
        if isinstance(record, dict):
            record["_income_year"] = income_year
    for key in ("statements", "dependants"):
        for record in result.get(key, []):
            if isinstance(record, dict):
                record["_income_year"] = income_year
    statement_notes = [
        *private_health_statement_collection_notes(answers),
        *private_health_explicit_statement_notes(answers),
    ]
    if private_health_cover_bool(result["private_health_cover"]) is False:
        statement_notes = [
            value
            for value in statement_notes
            if value != {"private_health_statement": False}
        ]
    result["notes"] = private_health_unique_values([*result["notes"], *statement_notes])
    return result


def private_health_key_values(record: Dict[str, Any], keys: tuple[str, ...]) -> List[Any]:
    return [record[key] for key in keys if key in record]


def private_health_collection_entries(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        return [value] if (
            private_health_substantive_value(value, false_is_value=True)
            or private_health_scoped_dependant_none(value)
        ) else []
    if not isinstance(value, list):
        return []
    rows: List[Dict[str, Any]] = []
    for item in value:
        rows.extend(private_health_collection_entries(item))
    return rows


def private_health_scoped_dependant_none(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    def is_none(item: Any) -> bool:
        return isinstance(item, str) and item.strip().lower() == "none"

    for key in DEPENDANT_SUMMARY_FIELD_ALIASES["count"]:
        if key in value and is_none(value[key]):
            return True
    for key in DEPENDANT_SECTION_KEYS:
        if key not in value:
            continue
        dependant_value = value[key]
        if is_none(dependant_value):
            return True
        if isinstance(dependant_value, dict) and any(
            count_key in dependant_value and is_none(dependant_value[count_key])
            for count_key in DEPENDANT_SUMMARY_FIELD_ALIASES["count"]
        ):
            return True
    return False


def private_health_collection_notes(value: Any) -> List[Any]:
    if isinstance(value, list):
        notes: List[Any] = []
        for item in value:
            notes.extend(private_health_collection_notes(item))
        return notes
    if not isinstance(value, dict):
        sanitized = private_health_sanitized_value(value, false_is_value=False)
        if sanitized is not PRIVATE_HEALTH_NO_VALUE:
            return [sanitized]
    return []


def private_health_nested_records(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for value in private_health_key_values(answers, PRIVATE_HEALTH_MEDICARE_NESTED_KEYS):
        rows.extend(private_health_collection_entries(value))
    return rows


def private_health_input_records(
    answers: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    parent_records = [answers, *private_health_nested_records(answers)]
    private_health_sections: List[Dict[str, Any]] = []
    for record in parent_records:
        for value in private_health_key_values(record, PRIVATE_HEALTH_SECTION_KEYS):
            private_health_sections.extend(private_health_collection_entries(value))
    return parent_records, private_health_sections


def private_health_append_record_groups(
    record: Dict[str, Any],
    groups: Dict[str, List[Dict[str, Any]]],
    *,
    global_scope: bool,
) -> None:
    sections = (
        ("private_health", PRIVATE_HEALTH_SECTION_KEYS, PRIVATE_HEALTH_FIELD_ALIASES),
        ("medicare_levy", MEDICARE_LEVY_SECTION_KEYS, MEDICARE_LEVY_FIELD_ALIASES),
        ("mls", MLS_SECTION_KEYS, MLS_FIELD_ALIASES),
        ("spouse", SPOUSE_SECTION_KEYS, SPOUSE_FIELD_ALIASES),
    )
    for name, section_keys, field_aliases in sections:
        groups[name].extend(private_health_section_records(record, section_keys, field_aliases))
    private_health_append_flat_record_groups(
        record,
        groups,
        ("private_health", "medicare_levy", "mls", "spouse", "dependant_summary"),
        global_scope=global_scope,
    )
    groups["dependant_summary"].extend(private_health_dependant_summary_records(record))
    for value in private_health_key_values(record, PRIVATE_HEALTH_SECTION_KEYS):
        for section in private_health_collection_entries(value):
            private_health_append_embedded_groups(section, groups)


def private_health_append_flat_record_groups(
    record: Dict[str, Any],
    groups: Dict[str, List[Dict[str, Any]]],
    names: tuple[str, ...],
    *,
    global_scope: bool = False,
) -> None:
    for name in names:
        subset = private_health_flat_alias_subset(record, name, global_scope=global_scope)
        if subset:
            groups[name].append(subset)


def private_health_append_embedded_groups(
    record: Dict[str, Any],
    groups: Dict[str, List[Dict[str, Any]]],
) -> None:
    private_health_append_flat_record_groups(
        record,
        groups,
        ("medicare_levy", "mls", "spouse", "dependant_summary"),
    )
    for name, section_keys, field_aliases in (
        ("medicare_levy", MEDICARE_LEVY_SECTION_KEYS, MEDICARE_LEVY_FIELD_ALIASES),
        ("mls", MLS_SECTION_KEYS, MLS_FIELD_ALIASES),
        ("spouse", SPOUSE_SECTION_KEYS, SPOUSE_FIELD_ALIASES),
    ):
        groups[name].extend(private_health_section_records(record, section_keys, field_aliases))
    groups["dependant_summary"].extend(private_health_dependant_summary_records(record))


def private_health_append_medicare_groups(
    record: Dict[str, Any],
    groups: Dict[str, List[Dict[str, Any]]],
) -> None:
    starts = {name: len(groups[name]) for name in ("medicare_levy", "mls")}
    groups["medicare_levy"].extend(
        private_health_section_records(record, MEDICARE_LEVY_SECTION_KEYS, MEDICARE_LEVY_FIELD_ALIASES)
    )
    groups["mls"].extend(private_health_section_records(record, MLS_SECTION_KEYS, MLS_FIELD_ALIASES))
    private_health_append_flat_record_groups(record, groups, ("medicare_levy", "mls"))
    metadata = private_health_record_metadata(
        record,
        set(PRIVATE_HEALTH_FIELD_ALIASES["source_urls"]),
        set(PRIVATE_HEALTH_FIELD_ALIASES["checked_at"]),
    )
    if not metadata:
        return
    for name, field_aliases in (
        ("medicare_levy", MEDICARE_LEVY_FIELD_ALIASES),
        ("mls", MLS_FIELD_ALIASES),
    ):
        for index in range(starts[name], len(groups[name])):
            private_health_add_metadata(groups[name][index], metadata, field_aliases)


def private_health_medicare_wrapper_known_keys() -> set[str]:
    return (
        set(MEDICARE_LEVY_SECTION_KEYS)
        | set(MLS_SECTION_KEYS)
        | private_health_alias_set(MEDICARE_LEVY_FLAT_FIELD_ALIASES)
        | private_health_alias_set(MLS_FLAT_FIELD_ALIASES)
        | set(PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS)
    )


def private_health_medicare_wrapper_unknown(record: Dict[str, Any]) -> Dict[str, Any]:
    return private_health_unknown_values(
        record,
        private_health_medicare_wrapper_known_keys(),
    )


def private_health_medicare_supplemental_metadata(answers: Dict[str, Any]) -> Dict[str, Any]:
    parent_records, _ = private_health_input_records(answers)
    metadata: Dict[str, Any] = {}
    for record in parent_records:
        medicare = record.get("medicare")
        if not isinstance(medicare, dict) or not private_health_medicare_wrapper_unknown(medicare):
            continue
        supplied = private_health_record_metadata(
            medicare,
            set(PRIVATE_HEALTH_FIELD_ALIASES["source_urls"]),
            set(PRIVATE_HEALTH_FIELD_ALIASES["checked_at"]),
        )
        nested_supplied = private_health_unknown_metadata(
            medicare,
            private_health_medicare_wrapper_known_keys(),
        )
        private_health_add_metadata(metadata, supplied, PRIVATE_HEALTH_FIELD_ALIASES)
        private_health_add_metadata(
            metadata,
            nested_supplied,
            PRIVATE_HEALTH_FIELD_ALIASES,
        )
    return metadata


def private_health_section_records(
    record: Dict[str, Any],
    section_keys: tuple[str, ...],
    field_aliases: Dict[str, tuple[str, ...]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    excluded_child_keys = (
        set(PRIVATE_HEALTH_STATEMENT_KEYS)
        | set(MEDICARE_LEVY_SECTION_KEYS)
        | set(MLS_SECTION_KEYS)
        | set(SPOUSE_SECTION_KEYS)
        | set(DEPENDANT_SECTION_KEYS)
    )
    current_aliases = private_health_alias_set(field_aliases)
    cross_flat_aliases = private_health_all_flat_aliases().difference(current_aliases)
    if field_aliases is PRIVATE_HEALTH_FIELD_ALIASES:
        cross_flat_aliases.update(
            private_health_alias_set(PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES).difference(current_aliases)
        )
    for key in section_keys:
        value = record.get(key)
        records = private_health_collection_entries(value)
        for child in records:
            section = private_health_filter_record_values(
                {
                    child_key: child_value
                    for child_key, child_value in child.items()
                    if child_key not in excluded_child_keys
                    and child_key not in cross_flat_aliases
                },
                field_aliases,
            )
            if has_meaningful_value(section):
                rows.append(section)
        if isinstance(value, list):
            scalar_key = "notes" if records else private_health_section_scalar_key(section_keys)
            rows.extend(
                {scalar_key: note}
                for note in private_health_collection_notes(value)
            )
            continue
        if records:
            continue
        if value is False and section_keys in (PRIVATE_HEALTH_SECTION_KEYS, SPOUSE_SECTION_KEYS):
            scalar_key = private_health_section_scalar_key(section_keys)
            rows.append({scalar_key: False})
        elif private_health_freeform_value(value):
            scalar_key = private_health_section_scalar_key(section_keys)
            rows.append({scalar_key: value})
    return rows


def private_health_section_scalar_key(section_keys: tuple[str, ...]) -> str:
    if section_keys == PRIVATE_HEALTH_SECTION_KEYS:
        return "private_health_cover"
    if section_keys == SPOUSE_SECTION_KEYS:
        return "spouse_had"
    return "notes"


def private_health_alias_set(field_aliases: Dict[str, tuple[str, ...]]) -> set[str]:
    return set(item_alias_keys(field_aliases))


def private_health_alias_subset(
    record: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Dict[str, Any]:
    aliases = private_health_alias_set(field_aliases)
    return private_health_filter_record_values(
        {key: value for key, value in record.items() if key in aliases},
        field_aliases,
    )


def private_health_flat_alias_subset(
    record: Dict[str, Any],
    section: str,
    *,
    global_scope: bool = False,
) -> Dict[str, Any]:
    aliases_by_section = (
        PRIVATE_HEALTH_GLOBAL_FLAT_FIELD_ALIASES
        if global_scope
        else PRIVATE_HEALTH_MEDICARE_FLAT_FIELD_ALIASES
    )
    field_aliases = aliases_by_section[section]
    return private_health_alias_subset(record, field_aliases)


def private_health_all_flat_aliases() -> set[str]:
    aliases: set[str] = set()
    for aliases_by_section in (
        PRIVATE_HEALTH_MEDICARE_FLAT_FIELD_ALIASES,
        PRIVATE_HEALTH_GLOBAL_FLAT_FIELD_ALIASES,
    ):
        for field_aliases in aliases_by_section.values():
            aliases.update(private_health_alias_set(field_aliases))
    return aliases


def private_health_workflow_notes(record: Dict[str, Any]) -> List[Any]:
    notes: List[Any] = []
    for key in PRIVATE_HEALTH_WORKFLOW_NOTE_KEYS:
        if key not in record:
            continue
        detail, _ = private_health_note_detail_with_metadata(record[key])
        if detail is not PRIVATE_HEALTH_NO_VALUE:
            if isinstance(detail, list):
                notes.extend(detail)
            else:
                notes.append(detail)
    return private_health_unique_values(notes)


def private_health_workflow_note_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for key in PRIVATE_HEALTH_WORKFLOW_NOTE_KEYS:
        if key not in record:
            continue
        detail, supplied = private_health_note_detail_with_metadata(record[key])
        if detail is PRIVATE_HEALTH_NO_VALUE:
            continue
        private_health_add_metadata(
            metadata,
            supplied,
            PRIVATE_HEALTH_FIELD_ALIASES,
        )
    return metadata


def private_health_root_known_keys() -> set[str]:
    return (
        set(PRIVATE_HEALTH_SECTION_KEYS)
        | set(PRIVATE_HEALTH_STATEMENT_KEYS)
        | set(MEDICARE_SECTION_KEYS)
        | set(MEDICARE_LEVY_SECTION_KEYS)
        | set(MLS_SECTION_KEYS)
        | set(SPOUSE_SECTION_KEYS)
        | set(DEPENDANT_SECTION_KEYS)
        | private_health_all_flat_aliases()
        | set(PRIVATE_HEALTH_WORKFLOW_NOTE_KEYS)
        | set(PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS)
        | {"income_year"}
    )


def private_health_unknown_values(record: Dict[str, Any], known_keys: set[str]) -> Dict[str, Any]:
    unknown: Dict[str, Any] = {}
    for key, value in record.items():
        if key in known_keys or key.startswith("_"):
            continue
        detail, _ = private_health_detail_with_metadata(
            value,
            false_is_value=True,
        )
        if detail is not PRIVATE_HEALTH_NO_VALUE:
            unknown[key] = detail
    return unknown


def private_health_unknown_metadata(
    record: Dict[str, Any],
    known_keys: set[str],
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}
    for key, value in record.items():
        if key in known_keys or key.startswith("_"):
            continue
        detail, supplied = private_health_detail_with_metadata(
            value,
            false_is_value=True,
        )
        if detail is PRIVATE_HEALTH_NO_VALUE:
            continue
        private_health_add_metadata(
            metadata,
            supplied,
            PRIVATE_HEALTH_FIELD_ALIASES,
        )
    return metadata


def private_health_merge_records(
    records: List[Dict[str, Any]],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    conflicts: List[str] = []
    inherited_conflicts: List[Any] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        record = private_health_filter_record_values(record, field_aliases)
        for key, value in record.items():
            if is_missing(value):
                continue
            if key == "_source_conflicts":
                inherited_conflicts.extend(
                    private_health_recursive_scalar_values(value)
                )
                continue
            if key not in merged:
                merged[key] = value
                continue
            existing = merged[key]
            field = private_health_field_for_alias(key, field_aliases)
            if field == "source_urls":
                merged[key] = private_health_merge_provenance_values(existing, value)
                continue
            if private_health_values_equivalent(key, existing, value, field_aliases):
                continue
            if private_health_placeholder_value(existing) and private_health_concrete_value(key, value, field_aliases):
                merged[key] = value
                continue
            if private_health_placeholder_value(value) and private_health_concrete_value(key, existing, field_aliases):
                continue
            conflicts.append(f"{key} {display_value(existing)} vs {display_value(value)}")
    all_conflicts = private_health_unique_values(
        [*inherited_conflicts, *conflicts]
    )
    if all_conflicts:
        merged["_source_conflicts"] = all_conflicts
    return merged


def private_health_merge_provenance_values(left: Any, right: Any) -> List[Any]:
    values: List[Any] = []
    for value in (left, right):
        values.extend(value if isinstance(value, list) else [value])
    return private_health_unique_values(values)


def private_health_values_equivalent(
    key: str,
    left: Any,
    right: Any,
    field_aliases: Dict[str, tuple[str, ...]],
) -> bool:
    field = private_health_field_for_alias(key, field_aliases)
    if field in {"source_urls", "notes"} or isinstance(left, (dict, list)) or isinstance(right, (dict, list)):
        return json.dumps(
            private_health_singleton_value(left),
            sort_keys=True,
            default=str,
        ) == json.dumps(
            private_health_singleton_value(right),
            sort_keys=True,
            default=str,
        )
    return item_alias_conflict_key(field, left) == item_alias_conflict_key(field, right)


def private_health_singleton_value(value: Any) -> Any:
    while isinstance(value, list) and len(value) == 1:
        value = value[0]
    return value


def private_health_field_for_alias(key: str, field_aliases: Dict[str, tuple[str, ...]]) -> str:
    for field, aliases in field_aliases.items():
        if key in aliases:
            return field
    return key


def private_health_placeholder_value(value: Any) -> bool:
    return is_missing(value) or (contains_unknown(value) and not explicit_evidence_denial_value(value))


def private_health_concrete_value(
    key: str,
    value: Any,
    field_aliases: Dict[str, tuple[str, ...]],
) -> bool:
    field = private_health_field_for_alias(key, field_aliases)
    false_is_concrete = field in ITEM_ALIAS_BOOLEAN_FIELDS or field in ITEM_ALIAS_EVIDENCE_FIELDS
    return concrete_item_alias_value(value, false_is_concrete=false_is_concrete)


def private_health_statement_answers(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    parent_records, private_health_sections = private_health_input_records(answers)

    raw_groups: List[Any] = []
    for record in parent_records:
        keys = PRIVATE_HEALTH_GLOBAL_STATEMENT_KEYS if record is answers else PRIVATE_HEALTH_STATEMENT_KEYS
        raw_groups.extend(private_health_key_values(record, keys))
    for record in private_health_sections:
        raw_groups.extend(private_health_key_values(record, PRIVATE_HEALTH_STATEMENT_KEYS))

    for record in parent_records:
        flat_statement = private_health_explicit_statement_subset(record)
        if flat_statement:
            raw_groups.append(flat_statement)
    for record in private_health_sections:
        flat_statement = private_health_alias_subset(record, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES)
        if private_health_statement_identity_signal(flat_statement):
            raw_groups.append(flat_statement)
            continue
        prefixed_statement = private_health_explicit_statement_subset(record)
        if prefixed_statement:
            raw_groups.append(prefixed_statement)

    normalized_groups = [private_health_statement_entries(value) for value in raw_groups]
    normalized_groups = [group for group in normalized_groups if group]
    return private_health_merge_item_groups(normalized_groups, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES)


def private_health_explicit_statement_subset(record: Dict[str, Any]) -> Dict[str, Any]:
    subset = private_health_flat_alias_subset(record, "statement")
    if private_health_statement_identity_signal(subset):
        return subset
    explicit = {
        key: value
        for key, value in subset.items()
        if key.startswith("private_health_statement_")
    }
    return explicit if private_health_statement_record_has_signal(explicit) else {}


def private_health_statement_entries(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        rows: List[Dict[str, Any]] = []
        for item in value:
            rows.extend(private_health_statement_entries(item))
        return rows
    if isinstance(value, dict):
        nested_rows: List[Dict[str, Any]] = []
        nested_keys = (*PRIVATE_HEALTH_STATEMENT_KEYS, *PRIVATE_HEALTH_STATEMENT_ITEM_KEYS)
        for key in nested_keys:
            if key in value:
                nested_rows.extend(private_health_statement_entries(value.get(key)))
        parent = private_health_filter_record_values(
            {key: item for key, item in value.items() if key not in nested_keys},
            PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES,
        )
        if any(key in value for key in nested_keys):
            inherited = private_health_statement_wrapper_details(parent)
            if inherited:
                nested_rows = [
                    private_health_merge_records([inherited, row], PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES)
                    for row in nested_rows
                ]
            return nested_rows
        statement_signal = private_health_statement_record_has_signal(parent)
        if not statement_signal and any(
            explicit_evidence_denial_value(item) and private_health_statement_context(item)
            for item in parent.values()
        ):
            return []
        if statement_signal:
            nested_rows.append(parent)
        return nested_rows
    return []


def private_health_statement_record_has_signal(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    record = private_health_filter_record_values(
        record,
        PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES,
    )
    if private_health_statement_identity_signal(record):
        return True
    for field in ("days_covered", "period_start", "period_end", "period"):
        value = normalized_item_field(record, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES[field])
        if private_health_substantive_value(value, false_is_value=True):
            return True
    return False


def private_health_statement_identity_signal(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    record = private_health_filter_record_values(
        record,
        PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES,
    )
    for field in (
        "insurer",
        "membership_id",
        "benefit_code",
        "premiums_eligible_for_rebate",
        "rebate_received",
        "tax_claim_code",
    ):
        value = normalized_item_field(record, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES[field])
        if private_health_substantive_value(value, false_is_value=True):
            return True
    return False


def private_health_statement_wrapper_details(record: Dict[str, Any]) -> Dict[str, Any]:
    inherited_aliases = {
        field: PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES[field]
        for field in ("insurer", "membership_id", "evidence", "notes", "source_urls", "checked_at")
    }
    inherited = private_health_alias_subset(record, inherited_aliases)
    for alias in PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["evidence"]:
        if alias in inherited and explicit_evidence_denial_value(inherited[alias]):
            inherited.pop(alias)
    return inherited


def private_health_statement_collection_notes(answers: Dict[str, Any]) -> List[Any]:
    parent_records, private_health_sections = private_health_input_records(answers)
    notes: List[Any] = []
    for record in [*parent_records, *private_health_sections]:
        keys = PRIVATE_HEALTH_GLOBAL_STATEMENT_KEYS if record is answers else PRIVATE_HEALTH_STATEMENT_KEYS
        for value in private_health_key_values(record, keys):
            notes.extend(
                {"private_health_statement": detail}
                for detail in private_health_statement_supplemental_values(value)
            )
    return private_health_unique_values(notes)


def private_health_statement_collection_metadata(answers: Dict[str, Any]) -> Dict[str, Any]:
    parent_records, private_health_sections = private_health_input_records(answers)
    metadata: Dict[str, Any] = {}
    for record in [*parent_records, *private_health_sections]:
        keys = PRIVATE_HEALTH_GLOBAL_STATEMENT_KEYS if record is answers else PRIVATE_HEALTH_STATEMENT_KEYS
        for value in private_health_key_values(record, keys):
            for _, supplied in private_health_statement_supplemental_records(value):
                private_health_add_metadata(metadata, supplied, PRIVATE_HEALTH_FIELD_ALIASES)
    return metadata


def private_health_explicit_statement_notes(answers: Dict[str, Any]) -> List[Any]:
    parent_records, private_health_sections = private_health_input_records(answers)
    notes: List[Any] = []
    for record in [*parent_records, *private_health_sections]:
        subset = {
            key: value
            for key, value in private_health_flat_alias_subset(record, "statement").items()
            if key.startswith("private_health_statement_")
        }
        if not subset or private_health_statement_record_has_signal(subset):
            continue
        details = {
            key: value
            for key, value in subset.items()
            if private_health_field_for_alias(key, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES)
            not in {"source_urls", "checked_at"}
        }
        if details:
            notes.append({"private_health_statement": details})
    return private_health_unique_values(notes)


def private_health_statement_supplemental_records(
    value: Any,
    inherited_metadata: Optional[Dict[str, Any]] = None,
) -> List[tuple[Any, Dict[str, Any]]]:
    inherited_metadata = dict(inherited_metadata or {})
    if isinstance(value, list):
        records: List[tuple[Any, Dict[str, Any]]] = []
        for item in value:
            records.extend(
                private_health_statement_supplemental_records(
                    item,
                    inherited_metadata,
                )
            )
        return records
    if isinstance(value, dict):
        local_metadata = private_health_record_metadata(
            value,
            set(PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["source_urls"]),
            set(PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["checked_at"]),
        )
        metadata = dict(inherited_metadata)
        private_health_add_metadata(metadata, local_metadata, PRIVATE_HEALTH_FIELD_ALIASES)
        records: List[tuple[Any, Dict[str, Any]]] = []
        nested_keys = (*PRIVATE_HEALTH_STATEMENT_KEYS, *PRIVATE_HEALTH_STATEMENT_ITEM_KEYS)
        nested_values = [value[key] for key in nested_keys if key in value]
        for nested_value in nested_values:
            records.extend(
                private_health_statement_supplemental_records(
                    nested_value,
                    metadata,
                )
            )
        parent = {key: item for key, item in value.items() if key not in nested_keys}
        metadata_keys = set(PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["source_urls"]) | set(
            PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["checked_at"]
        )
        if not nested_values:
            represented = set(parent) if private_health_statement_record_has_signal(parent) else set()
        elif any(private_health_statement_entries(item) for item in nested_values):
            represented = set(private_health_statement_wrapper_details(parent))
        else:
            represented = set()
        details: Dict[str, Any] = {}
        for key, item in parent.items():
            if key in metadata_keys or key in represented:
                continue
            sanitized, supplied = private_health_detail_with_metadata(
                item,
                false_is_value=True,
            )
            if sanitized is not PRIVATE_HEALTH_NO_VALUE:
                details[key] = sanitized
                private_health_add_metadata(
                    metadata,
                    supplied,
                    PRIVATE_HEALTH_FIELD_ALIASES,
                )
        if details:
            records.append((details, metadata))
        return records
    sanitized, metadata = private_health_detail_with_metadata(
        value,
        false_is_value=True,
    )
    if sanitized is PRIVATE_HEALTH_NO_VALUE or (
        sanitized is not False and not private_health_freeform_value(sanitized)
    ):
        return []
    combined_metadata = dict(inherited_metadata)
    private_health_add_metadata(
        combined_metadata,
        metadata,
        PRIVATE_HEALTH_FIELD_ALIASES,
    )
    return [(sanitized, combined_metadata)]


def private_health_statement_supplemental_values(value: Any) -> List[Any]:
    return [
        detail
        for detail, _ in private_health_statement_supplemental_records(value)
    ]


def private_health_merge_item_groups(
    groups: List[List[Dict[str, Any]]],
    field_aliases: Dict[str, tuple[str, ...]],
) -> List[Dict[str, Any]]:
    if not groups:
        return []
    merged = [dict(item) for item in groups[0]]
    for group in groups[1:]:
        for index, item in enumerate(group):
            matching_index = private_health_matching_item_index(merged, item, field_aliases)
            if matching_index == -1:
                merged.append(dict(item))
            elif matching_index is not None:
                merged[matching_index] = private_health_merge_records(
                    [merged[matching_index], item],
                    field_aliases,
                )
            elif index < len(merged) and private_health_items_compatible(merged[index], item, field_aliases):
                merged[index] = private_health_merge_records([merged[index], item], field_aliases)
            else:
                merged.append(dict(item))
    return merged


def private_health_matching_item_index(
    rows: List[Dict[str, Any]],
    item: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Optional[int]:
    identity_fields = (
        ("insurer", 1),
        ("membership_id", 3),
        ("benefit_code", 1),
        ("period_start", 1),
        ("period_end", 1),
    )
    if field_aliases is DEPENDANT_FIELD_ALIASES:
        identity_fields = (("name", 3), ("period_start", 1), ("period_end", 1))
    best: List[int] = []
    best_score = 0
    for index, row in enumerate(rows):
        if not private_health_items_compatible(row, item, field_aliases):
            continue
        score = 0
        for field, weight in identity_fields:
            if field not in field_aliases:
                continue
            left = normalized_item_field(row, field_aliases[field])
            right = normalized_item_field(item, field_aliases[field])
            if is_missing(left) or is_missing(right):
                continue
            if private_health_values_equivalent(field, left, right, {field: field_aliases[field]}):
                score += weight
        if score >= 2 and score > best_score:
            best = [index]
            best_score = score
        elif score >= 2 and score == best_score:
            best.append(index)
    if len(best) == 1:
        return best[0]
    return -1 if best else None


def private_health_items_compatible(
    left: Dict[str, Any],
    right: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> bool:
    metadata_aliases = set(field_aliases.get("source_urls", ())) | set(
        field_aliases.get("checked_at", ())
    )
    filtered_left = {key: value for key, value in left.items() if key not in metadata_aliases}
    filtered_right = {key: value for key, value in right.items() if key not in metadata_aliases}
    merged = private_health_merge_records([filtered_left, filtered_right], field_aliases)
    return not private_health_record_conflicts(merged, field_aliases)


def private_health_dependant_answers(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_groups: List[Any] = []
    parent_records, private_health_sections = private_health_input_records(answers)
    for record in [*parent_records, *private_health_sections]:
        for value in private_health_key_values(record, DEPENDANT_SECTION_KEYS):
            if private_health_dependant_item_container(value):
                raw_groups.append(value)
    normalized_groups = [
        [
            row
            for row in private_health_dependant_entries(value)
            if private_health_dependant_record_has_signal(row)
        ]
        for value in raw_groups
    ]
    normalized_groups = [group for group in normalized_groups if group]
    return private_health_merge_item_groups(normalized_groups, DEPENDANT_FIELD_ALIASES)


def private_health_dependant_item_container(value: Any) -> bool:
    if isinstance(value, list):
        return True
    if not isinstance(value, dict):
        return False
    if any(key in value for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS):
        return True
    if private_health_dependant_record_has_signal(value):
        return True
    return False


def private_health_dependant_entries(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        rows: List[Dict[str, Any]] = []
        for item in value:
            rows.extend(private_health_dependant_entries(item))
        return rows
    if isinstance(value, dict):
        rows: List[Dict[str, Any]] = []
        for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS:
            if key in value:
                rows.extend(private_health_dependant_entries(value.get(key)))
        container = any(key in value for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS)
        excluded = set(DEPENDANT_SUMMARY_FIELD_ALIASES["count"])
        parent_value = {
            key: item
            for key, item in value.items()
            if key not in set(PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS) and key not in excluded
        }
        parent = private_health_dependant_item_record(parent_value)
        if container:
            inherited = private_health_dependant_wrapper_details(parent)
            private_health_add_metadata(
                inherited,
                private_health_dependant_metadata(parent_value),
                DEPENDANT_FIELD_ALIASES,
            )
            if inherited:
                rows = [
                    private_health_merge_records([inherited, row], DEPENDANT_FIELD_ALIASES)
                    for row in rows
                ]
            if private_health_dependant_record_has_signal(parent):
                rows.insert(0, parent)
            return rows
        if private_health_dependant_record_has_signal(parent):
            rows.append(parent)
            return rows
        if private_health_dependant_denial_value(parent):
            return []
        return rows
    if private_health_dependant_denial_value(value):
        return []
    if not private_health_freeform_value(value):
        return []
    return [{"notes": value}]


def private_health_dependant_record_has_signal(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    record = private_health_filter_record_values(record, DEPENDANT_FIELD_ALIASES)
    for field, aliases in DEPENDANT_FIELD_ALIASES.items():
        if field in {"evidence", "notes", "source_urls", "checked_at"}:
            continue
        value = normalized_item_field(record, aliases)
        if private_health_substantive_value(value, false_is_value=True):
            return True
    return False


def private_health_dependant_wrapper_details(record: Dict[str, Any]) -> Dict[str, Any]:
    inherited_aliases = {
        field: DEPENDANT_FIELD_ALIASES[field]
        for field in ("evidence", "notes", "source_urls", "checked_at")
    }
    return private_health_alias_subset(record, inherited_aliases)


def private_health_dependant_collection_notes(answers: Dict[str, Any]) -> List[Any]:
    parent_records, private_health_sections = private_health_input_records(answers)
    notes: List[Any] = []
    for record in [*parent_records, *private_health_sections]:
        for value in private_health_key_values(record, DEPENDANT_SECTION_KEYS):
            notes.extend(private_health_dependant_supplemental_values(value, nested=False))
    return private_health_unique_values(notes)


def private_health_dependant_collection_metadata(answers: Dict[str, Any]) -> Dict[str, Any]:
    parent_records, private_health_sections = private_health_input_records(answers)
    metadata: Dict[str, Any] = {}
    for record in [*parent_records, *private_health_sections]:
        for value in private_health_key_values(record, DEPENDANT_SECTION_KEYS):
            for _, supplied in private_health_dependant_supplemental_records(
                value,
                nested=False,
            ):
                private_health_add_metadata(
                    metadata,
                    supplied,
                    DEPENDANT_SUMMARY_FIELD_ALIASES,
                )
    return metadata


def private_health_dependant_supplemental_records(
    value: Any,
    *,
    nested: bool,
    inherited_metadata: Optional[Dict[str, Any]] = None,
) -> List[tuple[Any, Dict[str, Any]]]:
    inherited_metadata = dict(inherited_metadata or {})
    if isinstance(value, list):
        records: List[tuple[Any, Dict[str, Any]]] = []
        for item in value:
            records.extend(
                private_health_dependant_supplemental_records(
                    item,
                    nested=True,
                    inherited_metadata=inherited_metadata,
                )
            )
        return records
    if isinstance(value, dict):
        source_aliases = set(DEPENDANT_FIELD_ALIASES["source_urls"]) | set(
            DEPENDANT_SUMMARY_FIELD_ALIASES["source_urls"]
        )
        checked_at_aliases = set(DEPENDANT_FIELD_ALIASES["checked_at"]) | set(
            DEPENDANT_SUMMARY_FIELD_ALIASES["checked_at"]
        )
        local_metadata = private_health_record_metadata(
            value,
            source_aliases,
            checked_at_aliases,
        )
        metadata = dict(inherited_metadata)
        private_health_add_metadata(
            metadata,
            local_metadata,
            DEPENDANT_SUMMARY_FIELD_ALIASES,
        )
        records: List[tuple[Any, Dict[str, Any]]] = []
        nested_values = [
            value[key]
            for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS
            if key in value
        ]
        for nested_value in nested_values:
            records.extend(
                private_health_dependant_supplemental_records(
                    nested_value,
                    nested=True,
                    inherited_metadata=metadata,
                )
            )
        parent = {
            key: item
            for key, item in value.items()
            if key not in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS
        }
        parent = private_health_filter_record_values(parent, DEPENDANT_FIELD_ALIASES)
        private_health_add_metadata(
            metadata,
            private_health_record_metadata(
                parent,
                source_aliases,
                checked_at_aliases,
            ),
            DEPENDANT_SUMMARY_FIELD_ALIASES,
        )
        if private_health_dependant_record_has_signal(parent):
            return records

        represented: set[str] = set()
        summary = private_health_alias_subset(parent, DEPENDANT_SUMMARY_FIELD_ALIASES)
        if private_health_summary_substantive(summary):
            represented.update(summary)
        wrapper_keys = {
            key for key in ("value", "answer", "response") if key in parent
        }
        if wrapper_keys:
            represented.update(parent)
        child_items: List[Dict[str, Any]] = []
        for nested_value in nested_values:
            child_items.extend(
                private_health_dependant_items(
                    private_health_dependant_entries(nested_value)
                )
            )
        if child_items:
            represented.update(private_health_dependant_wrapper_details(parent))

        metadata_aliases = (
            set(DEPENDANT_FIELD_ALIASES["source_urls"])
            | set(DEPENDANT_FIELD_ALIASES["checked_at"])
            | set(DEPENDANT_SUMMARY_FIELD_ALIASES["source_urls"])
            | set(DEPENDANT_SUMMARY_FIELD_ALIASES["checked_at"])
        )
        details: Dict[str, Any] = {}
        details_metadata: Dict[str, Any] = {}
        for key, item in parent.items():
            if key.startswith("_") or key in metadata_aliases or key in represented:
                continue
            if key in DEPENDANT_SUMMARY_FIELD_ALIASES["count"] or key in {
                "value",
                "answer",
                "response",
                "status",
                "dependant_supplemental_facts",
            }:
                continue
            if key in DEPENDANT_SUMMARY_FIELD_ALIASES["notes"]:
                sanitized, supplied = private_health_dependant_remaining_record(
                    item,
                    bare=False,
                    inherited_metadata=metadata,
                )
            else:
                sanitized, supplied = private_health_dependant_supplemental_detail(
                    item,
                    metadata,
                )
            if sanitized is not PRIVATE_HEALTH_NO_VALUE:
                details[key] = sanitized
                private_health_add_metadata(
                    details_metadata,
                    supplied,
                    DEPENDANT_SUMMARY_FIELD_ALIASES,
                )
        if details:
            records.append((details, details_metadata))
        return records
    if (
        not nested
        or private_health_dependant_denial_value(value)
        or private_health_dependant_summary_entries(value)
    ):
        return []
    sanitized = private_health_sanitized_value(value, false_is_value=False)
    return (
        []
        if sanitized is PRIVATE_HEALTH_NO_VALUE
        else [(sanitized, inherited_metadata)]
    )


def private_health_dependant_supplemental_values(
    value: Any,
    *,
    nested: bool,
) -> List[Any]:
    return [
        detail
        for detail, _ in private_health_dependant_supplemental_records(
            value,
            nested=nested,
        )
    ]


def private_health_epistemic_uncertainty_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return bool(
        re.search(
            r"\b(?:cannot|can\s+t|unable\s+to)\s+(?:confirm|verify|establish|substantiate|say)\b"
            r"|\b(?:couldn|wouldn)\s+t\s+(?:confirm|verify|say|know|remember|recall)\b"
            r"|\b(?:uncertain|unsure|unconfirmed|possibly|probably|maybe|perhaps|likely|unlikely)\b"
            r"|\b(?:may|might|could)\s+(?:not\s+)?(?:have|be)\b"
            r"|\b(?:cannot|can|couldn|can\s+not|could\s+not)\s+t?\s*(?:have|be)\b"
            r"|\b(?:(?:have|has|had|did|could)\s+not|(?:haven|hasn|hadn|didn|couldn)\s+t)\s+"
            r"(?:confirm|verify|verified|establish|substantiate)\b"
            r"|\b(?:do|does|did)\s+not\s+(?:think|believe)\b"
            r"|\b(?:don|doesn|didn)\s+t\s+(?:think|believe)\b"
            r"|\b(?:do|does|did)\s+not\s+(?:know|remember|recall)\b"
            r"|\b(?:don|doesn|didn)\s+t\s+(?:know|remember|recall)\b"
            r"|\b(?:cannot|can\s+t|unable\s+to)\s+(?:know|remember|recall)\b"
            r"|\b(?:not\s+certain|not\s+confident|not\s+able|doubtful|in\s+doubt|guess(?:ing)?|unverified)\b"
            r"|\b(?:confirmation|verification)\s+(?:is\s+)?pending\b"
            r"|\b(?:wasn|weren)\s+t\s+(?:sure|certain)\b"
            r"|\b(?:think|believe|suppose|assume|doubt)\b"
            r"|\b(?:apparently|reportedly|seem(?:s|ed)?)\b"
            r"|\b(?:will|expect|plan|intend)\s+(?:to\s+)?(?:have|be)\b"
            r"|\b(?:used\s+to|previously|formerly)\b"
            r"|\b(?:last|previous|next)\s+(?:income\s+)?year\b"
            r"|\bnot\s+true\s+that\b|\bwhether\b|\bif\b",
            normalized,
        )
    )


def private_health_full_income_year_range_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    separator = r"(?:(?:to|and|until|through(?:\s+to)?)\s+)?"
    patterns = (
        rf"\b(?:(?:from|between)\s+)?1\s+july\s+(\d{{4}})\s+{separator}30\s+june\s+(\d{{4}})\b",
        rf"\b(?:(?:from|between)\s+)?(\d{{4}})\s+0?7\s+0?1\s+{separator}(\d{{4}})\s+0?6\s+30\b",
        rf"\b(?:(?:from|between)\s+)?0?1\s+0?7\s+(\d{{4}})\s+{separator}30\s+0?6\s+(\d{{4}})\b",
    )
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match and int(match.group(2)) == int(match.group(1)) + 1:
            return True
    return False


def private_health_qualified_period_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if private_health_partial_text(normalized):
        return True
    if private_health_full_income_year_range_text(normalized):
        return False
    if re.search(
        r"\b(?:not|was\s+not|were\s+not|wasn\s+t|weren\s+t)\s+on\s+and\s+off\b",
        normalized,
    ):
        return False
    if re.search(r"\b(?:intermittent(?:ly)?|on\s+and\s+off)\b", normalized):
        return True
    if re.search(
        r"\b(?:except|excluding|apart\s+from|other\s+than|besides|save\s+for|unless)\b"
        r"|\b(?:all\s+but|but\s+(?:one|a|an|\d+))\b",
        normalized,
    ):
        return True
    if re.search(
        r"\b(?:not|did\s+not|didn\s+t|does\s+not|doesn\s+t|was\s+not|were\s+not|wasn\s+t|weren\s+t)\b"
        r"(?:\s+\w+){0,8}\s+\b(?:fully|always|continuously|"
        r"(?:for\s+)?(?:the\s+)?(?:(?:full|whole|entire)(?:\s+of)?|all(?:\s+of)?)\s+"
        r"(?:the\s+)?(?:income\s+)?year|throughout\s+(?:the\s+)?(?:income\s+)?year)\b"
        r"|\bnot\s+(?:zero|no|none|nil|without|true\s+that)\b"
        r"|\b(?:do|does|did)\s+not\s+(?:think|believe)\b",
        normalized,
    ):
        return True
    if private_health_epistemic_uncertainty_text(normalized):
        return True
    if re.search(
        r"\b(?:currently|at\s+present|right\s+now|at\s+the\s+moment|today|now|anymore|no\s+longer)\b"
        r"|\b(?:as\s+(?:at|of)|at|on)\s+(?:today|eofy|"
        r"\d{4}\s+\d{1,2}\s+\d{1,2}|\d{1,2}\s+\d{1,2}\s+\d{4}|"
        r"\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december|"
        r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)(?:\s+\d{4})?)\b"
        r"|\bat\s+(?:the\s+)?(?:start|end)\s+of\s+(?:the\s+)?(?:income\s+)?year\b"
        r"|\bat\s+(?:income\s+)?year\s+end\b",
        normalized,
    ):
        return True
    if re.search(
        r"\b(?:(?:first|second|only)\s+)?half\s+(?:of\s+)?(?:the\s+)?(?:income\s+)?year\b"
        r"|\bhalf\s+(?:a|an)\s+(?:income\s+)?year\b"
        r"|\bmost\s+of\s+(?:the\s+)?(?:income\s+)?year\b"
        r"|\b(?:first|last)\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|\d+)\s+months?\b"
        r"|\b(?:for|during|in)\s+(?:a\s+)?(?:few|several)\s+(?:days?|weeks?|months?)\b"
        r"|\b(?:first|second|third|fourth)\s+quarter\b|\bq[1-4]\b"
        r"|\b(?:a|one)\s+quarter\b|\b(?:first|second)\s+half\b"
        r"|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|\d{1,2})\s+"
        r"(?:of|out\s+of)\s+(?:twelve|12)\s+months?\b",
        normalized,
    ):
        return True
    duration = re.search(
        r"\b(?:for|during|in)\s+(?:only\s+)?"
        r"(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,4})\s+"
        r"(days?|weeks?|months?)\b",
        normalized,
    )
    if duration:
        words = {
            "zero": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }
        amount = words.get(duration.group(1), int(duration.group(1)) if duration.group(1).isdigit() else 0)
        unit = duration.group(2)
        limit = 12 if unit.startswith("month") else 52 if unit.startswith("week") else 365
        return amount != limit
    if re.search(
        r"\bfor\s+(?:(?:less\s+than|under|approx(?:imately)?|roughly)\s+)?"
        r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|\d{1,4})"
        r"(?:\s+to\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|\d{1,4}))?\s+"
        r"(?:days?|weeks?|months?)\b",
        normalized,
    ):
        return True
    month = (
        r"(?:january|february|march|april|may|june|july|august|september|"
        r"october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
    )
    if re.search(
        rf"\bbetween\b.+\band\b|\bfrom\b.+\bto\b|\b{month}\s+to\s+{month}\b",
        normalized,
    ):
        return True
    if re.search(rf"\b{month}\s+{month}\b", normalized):
        return True
    if re.search(r"\b(?:from|until|since|before|after)\b", normalized):
        return True
    if re.search(
        rf"\b(?:up\s+to|by)\s+(?:eofy|lodg(?:e)?ment|\d{{1,2}}(?:\s+{month})?|{month})\b"
        r"|\b(?:at|as\s+at)\s+(?:lodg(?:e)?ment|the\s+date\s+of\s+(?:this|the)\s+form)\b",
        normalized,
    ):
        return True
    if re.search(
        r"\b(?:when\s+(?:lodging|i\s+lodge)|upon\s+lodg(?:e)?ment|at\s+tax\s+time|"
        r"when\s+(?:this|the)\s+form\s+was\s+completed|at\s+(?:the\s+)?end\s+of\s+june)\b",
        normalized,
    ):
        return True
    if re.search(rf"\b(?:in|during)\s+{month}\b", normalized):
        return True
    if re.search(r"\bduring\b", normalized) and not re.search(
        r"\bduring\s+(?:the\s+)?(?:income\s+)?year\b",
        normalized,
    ):
        return True
    if re.search(
        r"\bat\s+any\s+time\b|\bthroughout\s+(?:the\s+)?(?:income\s+)?year\b"
        r"|\bthis\s+(?:income\s+)?year\b",
        normalized,
    ):
        return False
    return False


def private_health_dependant_qualified_denial_text(value: Any) -> bool:
    if private_health_qualified_period_text(value):
        return True
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    subject = r"(?:dependants?|dependents?|child(?:ren)?|students?)"
    evidence_subject = (
        r"(?:dependants?|dependents?(?:\s+child(?:ren)?)?|child(?:ren)?|students?)"
    )
    if re.search(
        rf"\b{evidence_subject}\s+(?:records?|evidence|documents?|details|information|facts|data)\b",
        normalized,
    ):
        return True
    if re.search(
        r"\b(?:not(?:\s+exactly)?|more\s+than|less\s+than|at\s+least|at\s+most)\s+0+(?:\.0+)?\b",
        value.lower(),
    ):
        return True
    positive = (
        r"(?:one|[1-9]\d*)(?:\s+(?:dependants?|dependents?|child(?:ren)?|students?))?"
    )
    zero = rf"(?:0|zero|no|none|nil)\s+(?:any\s+)?{subject}"
    return bool(
        re.search(
            rf"\b(?:not(?:\s+exactly)?|more\s+than|less\s+than|at\s+least|at\s+most)\s+"
            rf"(?:0|zero|no|none|nil)\s+{subject}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:do|does|did)\s+not\s+have\s+(?:0|zero|no|none|nil)\s+{subject}\b",
            normalized,
        )
        or re.search(
            rf"(?:\b{positive}\b.*\bor\b.*\b{zero}\b|"
            rf"\b{zero}\b.*\bor\b.*\b{positive}\b)",
            normalized,
        )
        or re.search(r"\bunlikely\b", normalized)
    )


def private_health_source_like_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    slash_subject = (
        r"(?:(?:dependants?|dependents?)(?:\s+child(?:ren)?)?|child(?:ren)?|students?)"
    )
    if re.fullmatch(
        rf"(?:no|none|nil|zero|0+(?:\.0+)?|without)\s+"
        rf"(?:(?:any|a|an|one)\s+)?{slash_subject}(?:\s*/\s*{slash_subject})+",
        stripped,
        re.IGNORECASE,
    ):
        return False
    return bool(
        re.search(r"\b(?:https?|file)://|\bwww\.", stripped, re.IGNORECASE)
        or re.search(
            r"\b[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,24}\b",
            stripped,
            re.IGNORECASE,
        )
        or "/" in stripped
        or "\\" in stripped
        or re.search(
            r"\.(?:csv|docx?|html?|json|md|pdf|txt|xlsx?|xml|ya?ml)\b",
            stripped,
            re.IGNORECASE,
        )
    )


def private_health_dependant_denial_candidate(value: Any, *, bare: bool) -> bool:
    if value is False or (isinstance(value, (int, float)) and value == 0):
        return bare
    if not isinstance(value, str) or contains_unknown(value):
        return False
    if private_health_source_like_text(value):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if private_health_dependant_qualified_denial_text(value):
        return False
    if bare and normalized in {"0", "false", "no", "nil", "zero"}:
        return True
    if normalized in PRIVATE_HEALTH_NOOP_TEXT:
        return False
    subject = r"(?:dependants?|dependents?|child(?:ren)?|students?)"
    if re.search(
        rf"\b0+(?:\.0+)?\s+{subject}\b",
        value,
        re.IGNORECASE,
    ):
        return True
    return bool(
        re.search(
            rf"\b(?:no|none|nil|zero|0|without)\s+(?:(?:any|a|an|one)\s+)?{subject}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:do|does|did)\s+not\s+have\s+(?:(?:any|a|an|one)\s+)?{subject}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:dont|don\s+t|doesnt|doesn\s+t|didnt|didn\s+t)\s+have\s+"
            rf"(?:(?:any|a|an|one)\s+)?{subject}\b",
            normalized,
        )
        or re.search(
            rf"\b{subject}\s+(?:(?:count|total)\s+)?(?:is\s+)?(?:0|zero|none|nil)\b",
            normalized,
        )
        or re.search(
            rf"\b(?:dependant|dependent)\s+count\s+(?:is\s+)?(?:0|zero|none|nil)\b",
            normalized,
        )
    )


def private_health_dependant_denial_scalars(value: Any, *, bare: bool) -> List[Any]:
    if isinstance(value, list):
        values: List[Any] = []
        for item in value:
            values.extend(private_health_dependant_denial_scalars(item, bare=bare))
        return values
    if isinstance(value, dict):
        values: List[Any] = []
        for key, item in value.items():
            values.extend(
                private_health_dependant_denial_scalars(
                    item,
                    bare=bare if key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS else False,
                )
            )
        return values
    return [value] if private_health_dependant_denial_candidate(value, bare=bare) else []


def private_health_dependant_denial_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(private_health_dependant_denial_value(item) for item in value)
    if isinstance(value, dict):
        item_shaped = private_health_dependant_record_has_signal(value)
        if any(
            key in value and private_health_dependant_denial_value(value[key])
            for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS
        ):
            return True
        if not item_shaped and any(
            key in value
            and bool(private_health_dependant_denial_scalars(value[key], bare=True))
            for key in PRIVATE_HEALTH_DEPENDANT_DENIAL_KEYS
        ):
            return True
        return any(
            key in value
            and bool(private_health_dependant_denial_scalars(value[key], bare=False))
            for key in DEPENDANT_SUMMARY_FIELD_ALIASES["notes"]
        )
    return private_health_dependant_denial_candidate(value, bare=True)


def private_health_dependant_remaining_record(
    value: Any,
    *,
    bare: bool,
    inherited_metadata: Optional[Dict[str, Any]] = None,
) -> tuple[Any, Dict[str, Any]]:
    if isinstance(value, list):
        remaining: List[Any] = []
        metadata: Dict[str, Any] = {}
        for item in value:
            kept, supplied = private_health_dependant_remaining_record(
                item,
                bare=bare,
                inherited_metadata=inherited_metadata,
            )
            if kept is PRIVATE_HEALTH_NO_VALUE:
                continue
            remaining.append(kept)
            private_health_add_metadata(
                metadata,
                supplied,
                DEPENDANT_SUMMARY_FIELD_ALIASES,
            )
        return (
            (remaining, metadata)
            if remaining
            else (PRIVATE_HEALTH_NO_VALUE, {})
        )
    if isinstance(value, dict):
        remaining: Dict[str, Any] = {}
        metadata: Dict[str, Any] = {}
        local_metadata = private_health_dependant_metadata(
            value,
            inherited_metadata,
        )
        for key, item in value.items():
            if key.startswith("_") or key in PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS:
                continue
            kept, supplied = private_health_dependant_remaining_record(
                item,
                bare=bare if key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS else False,
                inherited_metadata=local_metadata,
            )
            if kept is not PRIVATE_HEALTH_NO_VALUE:
                remaining[key] = kept
                private_health_add_metadata(
                    metadata,
                    supplied,
                    DEPENDANT_SUMMARY_FIELD_ALIASES,
                )
        return (
            (remaining, metadata)
            if remaining
            else (PRIVATE_HEALTH_NO_VALUE, {})
        )
    if private_health_dependant_denial_candidate(value, bare=bare):
        return PRIVATE_HEALTH_NO_VALUE, {}
    remaining = private_health_sanitized_value(value, false_is_value=True)
    return (
        (remaining, dict(inherited_metadata or {}))
        if remaining is not PRIVATE_HEALTH_NO_VALUE
        else (PRIVATE_HEALTH_NO_VALUE, {})
    )


def private_health_dependant_supplemental_detail(
    value: Any,
    inherited_metadata: Optional[Dict[str, Any]] = None,
) -> tuple[Any, Dict[str, Any]]:
    if isinstance(value, list):
        details: List[Any] = []
        metadata: Dict[str, Any] = {}
        for item in value:
            detail, supplied = private_health_dependant_supplemental_detail(
                item,
                inherited_metadata,
            )
            if detail is PRIVATE_HEALTH_NO_VALUE:
                continue
            details.append(detail)
            private_health_add_metadata(
                metadata,
                supplied,
                DEPENDANT_SUMMARY_FIELD_ALIASES,
            )
        return (
            (details, metadata)
            if details
            else (PRIVATE_HEALTH_NO_VALUE, {})
        )
    if isinstance(value, dict):
        local_metadata = private_health_dependant_metadata(
            value,
            inherited_metadata,
        )
        details: Dict[str, Any] = {}
        metadata: Dict[str, Any] = {}
        for key, item in value.items():
            if key.startswith("_") or key in PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS:
                continue
            detail, supplied = private_health_dependant_supplemental_detail(
                item,
                local_metadata,
            )
            if detail is PRIVATE_HEALTH_NO_VALUE:
                continue
            details[key] = detail
            private_health_add_metadata(
                metadata,
                supplied,
                DEPENDANT_SUMMARY_FIELD_ALIASES,
            )
        return (
            (details, metadata)
            if details
            else (PRIVATE_HEALTH_NO_VALUE, {})
        )
    detail = private_health_sanitized_value(value, false_is_value=True)
    return (
        (detail, dict(inherited_metadata or {}))
        if detail is not PRIVATE_HEALTH_NO_VALUE
        else (PRIVATE_HEALTH_NO_VALUE, {})
    )


def private_health_dependant_item_record(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    inherited_metadata = private_health_dependant_metadata(value)
    record: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    metadata_aliases = set(DEPENDANT_FIELD_ALIASES["source_urls"]) | set(
        DEPENDANT_FIELD_ALIASES["checked_at"]
    )
    for key, item in value.items():
        if key.startswith("_"):
            record[key] = item
            continue
        if key in metadata_aliases:
            continue
        detail, supplied = private_health_dependant_supplemental_detail(
            item,
            inherited_metadata,
        )
        if detail is PRIVATE_HEALTH_NO_VALUE:
            continue
        if key in private_health_alias_set(DEPENDANT_FIELD_ALIASES) and isinstance(
            detail,
            dict,
        ):
            wrapper_keys = [
                wrapper
                for wrapper in ("value", "answer", "response")
                if wrapper in detail
            ]
            if len(wrapper_keys) == 1 and len(detail) == 1:
                detail = detail[wrapper_keys[0]]
        record[key] = detail
        private_health_add_metadata(
            metadata,
            supplied,
            DEPENDANT_FIELD_ALIASES,
        )
    private_health_add_metadata(record, metadata, DEPENDANT_FIELD_ALIASES)
    return private_health_filter_record_values(record, DEPENDANT_FIELD_ALIASES)


def private_health_dependant_metadata(
    value: Dict[str, Any],
    inherited_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(inherited_metadata or {})
    local_metadata = private_health_record_metadata(
        value,
        set(DEPENDANT_FIELD_ALIASES["source_urls"])
        | set(DEPENDANT_SUMMARY_FIELD_ALIASES["source_urls"]),
        set(DEPENDANT_FIELD_ALIASES["checked_at"])
        | set(DEPENDANT_SUMMARY_FIELD_ALIASES["checked_at"]),
    )
    private_health_add_metadata(
        metadata,
        local_metadata,
        DEPENDANT_SUMMARY_FIELD_ALIASES,
    )
    return metadata


def private_health_dependant_count_records(
    value: Any,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    allow_bare_none: bool = True,
) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        records: List[Dict[str, Any]] = []
        for item in value:
            records.extend(
                private_health_dependant_count_records(
                    item,
                    metadata,
                    allow_bare_none=False,
                )
            )
        count_candidates = private_health_unique_values(
            [record["count"] for record in records if "count" in record]
        )
        if len(count_candidates) > 1 and records:
            records[0]["count_candidates"] = count_candidates
        return records
    if isinstance(value, dict):
        metadata = private_health_dependant_metadata(value, metadata)
        payload: Dict[str, Any] = {}
        for key, item in value.items():
            if key.startswith("_") or key in PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS:
                continue
            if key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS:
                payload[key] = item
                continue
            sanitized_item = private_health_sanitized_value(item, false_is_value=True)
            if sanitized_item is not PRIVATE_HEALTH_NO_VALUE:
                payload[key] = sanitized_item
        if not payload:
            return []
        value_keys = [key for key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS if key in payload]
        if not value_keys:
            context, context_metadata = private_health_dependant_supplemental_detail(
                payload,
                metadata,
            )
            if context is PRIVATE_HEALTH_NO_VALUE:
                return []
            record = {"count_context": context}
            private_health_add_metadata(
                record,
                context_metadata,
                DEPENDANT_SUMMARY_FIELD_ALIASES,
            )
            return [record]
        records: List[Dict[str, Any]] = []
        for key in value_keys:
            records.extend(
                private_health_dependant_count_records(
                    payload[key],
                    metadata,
                    allow_bare_none=allow_bare_none,
                )
            )
        context = {
            key: item
            for key, item in payload.items()
            if key not in value_keys
        }
        context, context_metadata = private_health_dependant_supplemental_detail(
            context,
            metadata,
        )
        if context is not PRIVATE_HEALTH_NO_VALUE:
            if not records:
                records.append({"count_context": context})
            else:
                for record in records:
                    record["count_context"] = context
            for record in records:
                private_health_add_metadata(
                    record,
                    context_metadata,
                    DEPENDANT_SUMMARY_FIELD_ALIASES,
                )
        return records
    denial = private_health_dependant_denial_candidate(value, bare=True) or (
        allow_bare_none
        and isinstance(value, str)
        and re.sub(r"[^a-z0-9]+", " ", value.lower()).strip() == "none"
    )
    sanitized = (
        value
        if denial
        else private_health_sanitized_value(value, false_is_value=True)
    )
    if sanitized is PRIVATE_HEALTH_NO_VALUE:
        return []
    count = private_health_nonnegative_integer(sanitized)
    record = {
        "count": (
            0
            if denial
            else count if count is not None else sanitized
        )
    }
    private_health_add_metadata(record, metadata or {}, DEPENDANT_SUMMARY_FIELD_ALIASES)
    return [record]


def private_health_dependant_denial_records(
    value: Any,
    *,
    bare: bool,
    metadata: Optional[Dict[str, Any]] = None,
    preserve_note: bool,
) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        records: List[Dict[str, Any]] = []
        for item in value:
            records.extend(
                private_health_dependant_denial_records(
                    item,
                    bare=bare,
                    metadata=metadata,
                    preserve_note=preserve_note,
                )
            )
        return records
    if isinstance(value, dict):
        local_metadata = private_health_dependant_metadata(value, metadata)
        records = []
        for key, item in value.items():
            if key.startswith("_") or key in PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS:
                continue
            records.extend(
                private_health_dependant_denial_records(
                    item,
                    bare=bare if key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS else False,
                    metadata=local_metadata,
                    preserve_note=preserve_note,
                )
            )
        return records
    if not private_health_dependant_denial_candidate(value, bare=bare):
        return []
    record: Dict[str, Any] = {"count": 0}
    if preserve_note and isinstance(value, str):
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        if normalized not in {"0", "false", "no"}:
            record["notes"] = value
    private_health_add_metadata(record, metadata or {}, DEPENDANT_SUMMARY_FIELD_ALIASES)
    return [record]


def private_health_dependant_summary_entries(
    value: Any,
    inherited_metadata: Optional[Dict[str, Any]] = None,
    *,
    allow_bare_none: bool = True,
) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        records: List[Dict[str, Any]] = []
        for item in value:
            records.extend(
                private_health_dependant_summary_entries(
                    item,
                    inherited_metadata,
                    allow_bare_none=False,
                )
            )
        return records
    if not isinstance(value, dict):
        return private_health_dependant_count_records(
            value,
            inherited_metadata,
            allow_bare_none=allow_bare_none,
        )

    metadata = private_health_dependant_metadata(value, inherited_metadata)
    records: List[Dict[str, Any]] = []
    for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS:
        if key in value:
            records.extend(
                private_health_dependant_summary_entries(
                    value[key],
                    metadata,
                    allow_bare_none=False,
                )
            )

    item_shaped = private_health_dependant_record_has_signal(value)
    for key in DEPENDANT_SUMMARY_FIELD_ALIASES["count"]:
        if key in value:
            records.extend(private_health_dependant_count_records(value[key], metadata))
    if not item_shaped:
        if "status" in value:
            records.extend(
                private_health_dependant_denial_records(
                    value["status"],
                    bare=True,
                    metadata=metadata,
                    preserve_note=True,
                )
            )
            remaining, status_metadata = private_health_dependant_remaining_record(
                value["status"],
                bare=True,
                inherited_metadata=metadata,
            )
            if remaining is not PRIVATE_HEALTH_NO_VALUE:
                status_record = {"status": remaining}
                private_health_add_metadata(
                    status_record,
                    status_metadata,
                    DEPENDANT_SUMMARY_FIELD_ALIASES,
                )
                records.append(status_record)
        wrapper_keys = [
            key
            for key in ("value", "answer", "response")
            if key in value
        ]
        if wrapper_keys and not any(
            key in value for key in DEPENDANT_SUMMARY_FIELD_ALIASES["count"]
        ):
            records.extend(private_health_dependant_count_records(value, metadata))

    for key in DEPENDANT_SUMMARY_FIELD_ALIASES["notes"]:
        if key not in value:
            continue
        records.extend(
            private_health_dependant_denial_records(
                value[key],
                bare=False,
                metadata=metadata,
                preserve_note=True,
            )
        )
        if item_shaped:
            continue
        remaining, note_metadata = private_health_dependant_remaining_record(
            value[key],
            bare=False,
            inherited_metadata=metadata,
        )
        if remaining is not PRIVATE_HEALTH_NO_VALUE:
            note_record = {key: remaining}
            private_health_add_metadata(
                note_record,
                note_metadata,
                DEPENDANT_SUMMARY_FIELD_ALIASES,
            )
            records.append(note_record)
    return records


def private_health_dependant_summary_base(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    record = private_health_filter_record_values(value, DEPENDANT_SUMMARY_FIELD_ALIASES)
    for key in (
        *DEPENDANT_SUMMARY_FIELD_ALIASES["count"],
        *DEPENDANT_SUMMARY_FIELD_ALIASES["notes"],
        "status",
        *PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS,
        "value",
        "answer",
        "response",
    ):
        record.pop(key, None)
    metadata_aliases = set(DEPENDANT_SUMMARY_FIELD_ALIASES["source_urls"]) | set(
        DEPENDANT_SUMMARY_FIELD_ALIASES["checked_at"]
    )
    metadata: Dict[str, Any] = {}
    for key, item in list(record.items()):
        if key.startswith("_") or key in metadata_aliases:
            continue
        detail, supplied = private_health_dependant_supplemental_detail(item)
        if detail is PRIVATE_HEALTH_NO_VALUE:
            record.pop(key)
            continue
        record[key] = detail
        private_health_add_metadata(
            metadata,
            supplied,
            DEPENDANT_SUMMARY_FIELD_ALIASES,
        )
    private_health_add_metadata(
        record,
        metadata,
        DEPENDANT_SUMMARY_FIELD_ALIASES,
    )
    return record


def private_health_normalize_dependant_summary(value: Any) -> Dict[str, Any]:
    records = [
        private_health_dependant_summary_base(value),
        *private_health_dependant_summary_entries(value),
    ]
    return private_health_merge_records(records, DEPENDANT_SUMMARY_FIELD_ALIASES)


def private_health_dependant_summary_from_values(
    summary: Any,
    dependants: Any,
) -> Dict[str, Any]:
    records = [
        private_health_normalize_dependant_summary(summary),
        *private_health_dependant_summary_entries(dependants),
    ]
    return private_health_normalize_dependant_summary(
        private_health_merge_records(records, DEPENDANT_SUMMARY_FIELD_ALIASES)
    )


def private_health_dependant_summary_records(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = private_health_dependant_summary_entries(
        private_health_flat_alias_subset(record, "dependant_summary")
    )
    for key in DEPENDANT_SECTION_KEYS:
        if key not in record:
            continue
        value = record[key]
        if key in {"dependant_summary", "dependent_summary"}:
            summary_base = private_health_dependant_summary_base(value)
            if summary_base:
                rows.append(summary_base)
        rows.extend(private_health_dependant_summary_entries(value))
    return rows


def private_health_summary_substantive(record: Any) -> bool:
    record = private_health_normalize_dependant_summary(record)
    if not record:
        return False
    count = normalized_item_field(record, DEPENDANT_SUMMARY_FIELD_ALIASES["count"])
    notes = normalized_item_field(record, DEPENDANT_SUMMARY_FIELD_ALIASES["notes"])
    return private_health_substantive_value(
        count,
        false_is_value=True,
    ) or private_health_freeform_value(notes)


def private_health_metadata_aliases() -> tuple[set[str], set[str]]:
    source_aliases: set[str] = set()
    checked_at_aliases: set[str] = set()
    for field_aliases in (
        PRIVATE_HEALTH_FIELD_ALIASES,
        PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES,
        MEDICARE_LEVY_FIELD_ALIASES,
        MLS_FIELD_ALIASES,
        SPOUSE_FIELD_ALIASES,
        DEPENDANT_SUMMARY_FIELD_ALIASES,
        DEPENDANT_FIELD_ALIASES,
    ):
        source_aliases.update(field_aliases.get("source_urls", ()))
        checked_at_aliases.update(field_aliases.get("checked_at", ()))
    return source_aliases, checked_at_aliases


def private_health_detail_with_metadata(
    value: Any,
    *,
    false_is_value: bool,
) -> tuple[Any, Dict[str, Any]]:
    if isinstance(value, list):
        details: List[Any] = []
        metadata: Dict[str, Any] = {}
        for item in value:
            detail, supplied = private_health_detail_with_metadata(
                item,
                false_is_value=false_is_value,
            )
            if detail is PRIVATE_HEALTH_NO_VALUE:
                continue
            details.append(detail)
            private_health_add_metadata(
                metadata,
                supplied,
                PRIVATE_HEALTH_FIELD_ALIASES,
            )
        return (details, metadata) if details else (PRIVATE_HEALTH_NO_VALUE, {})
    if isinstance(value, dict):
        source_aliases, checked_at_aliases = private_health_metadata_aliases()
        local_metadata = private_health_record_metadata(
            value,
            source_aliases,
            checked_at_aliases,
        )
        details: Dict[str, Any] = {}
        metadata: Dict[str, Any] = {}
        for key, item in value.items():
            if key.startswith("_"):
                continue
            if key in source_aliases:
                invalid = private_health_invalid_source_values(item)
                if invalid:
                    details["unresolved_source_provenance"] = (
                        invalid[0] if len(invalid) == 1 else invalid
                    )
                continue
            if key in checked_at_aliases:
                invalid = private_health_invalid_checked_at_values(item)
                if invalid:
                    details["unresolved_checked_at_provenance"] = (
                        invalid[0] if len(invalid) == 1 else invalid
                    )
                continue
            detail, supplied = private_health_detail_with_metadata(
                item,
                false_is_value=false_is_value,
            )
            if detail is PRIVATE_HEALTH_NO_VALUE:
                continue
            details[key] = detail
            private_health_add_metadata(
                metadata,
                supplied,
                PRIVATE_HEALTH_FIELD_ALIASES,
            )
        if not details:
            return PRIVATE_HEALTH_NO_VALUE, {}
        private_health_add_metadata(
            metadata,
            local_metadata,
            PRIVATE_HEALTH_FIELD_ALIASES,
        )
        return details, metadata
    detail = private_health_sanitized_value(
        value,
        false_is_value=false_is_value,
    )
    return (
        (detail, {})
        if detail is not PRIVATE_HEALTH_NO_VALUE
        else (PRIVATE_HEALTH_NO_VALUE, {})
    )


def private_health_note_detail_with_metadata(
    value: Any,
) -> tuple[Any, Dict[str, Any]]:
    if isinstance(value, list):
        details: List[Any] = []
        metadata: Dict[str, Any] = {}
        for item in value:
            detail, supplied = private_health_note_detail_with_metadata(item)
            if detail is PRIVATE_HEALTH_NO_VALUE:
                continue
            details.append(detail)
            private_health_add_metadata(
                metadata,
                supplied,
                PRIVATE_HEALTH_FIELD_ALIASES,
            )
        return (details, metadata) if details else (PRIVATE_HEALTH_NO_VALUE, {})
    return private_health_detail_with_metadata(
        value,
        false_is_value=isinstance(value, dict),
    )


def private_health_sanitized_value(value: Any, *, false_is_value: bool) -> Any:
    if is_missing(value):
        return PRIVATE_HEALTH_NO_VALUE
    if value is False:
        return False if false_is_value else PRIVATE_HEALTH_NO_VALUE
    if isinstance(value, str):
        normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
        if not contains_unknown(value) and normalized in PRIVATE_HEALTH_NOOP_TEXT:
            return PRIVATE_HEALTH_NO_VALUE
        return value
    if isinstance(value, list):
        sanitized_items = [
            private_health_sanitized_value(item, false_is_value=false_is_value)
            for item in value
        ]
        sanitized_items = [
            item for item in sanitized_items if item is not PRIVATE_HEALTH_NO_VALUE
        ]
        return sanitized_items if sanitized_items else PRIVATE_HEALTH_NO_VALUE
    if isinstance(value, dict):
        sanitized_record = {
            key: sanitized_item
            for key, item in value.items()
            if (
                sanitized_item := private_health_sanitized_value(
                    item,
                    false_is_value=false_is_value,
                )
            )
            is not PRIVATE_HEALTH_NO_VALUE
        }
        return sanitized_record if sanitized_record else PRIVATE_HEALTH_NO_VALUE
    return value if has_meaningful_value(value) else PRIVATE_HEALTH_NO_VALUE


def private_health_substantive_value(value: Any, *, false_is_value: bool) -> bool:
    return private_health_sanitized_value(
        value,
        false_is_value=false_is_value,
    ) is not PRIVATE_HEALTH_NO_VALUE


def private_health_sanitized_note_value(value: Any) -> Any:
    detail, _ = private_health_note_detail_with_metadata(value)
    return detail


def private_health_freeform_value(value: Any) -> bool:
    return private_health_substantive_value(value, false_is_value=False)


def private_health_filter_record_values(
    record: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Dict[str, Any]:
    filtered: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    has_detail = False
    for key, value in record.items():
        if key.startswith("_"):
            filtered[key] = value
            continue
        field = private_health_field_for_alias(key, field_aliases)
        if (
            field == "count"
            and isinstance(value, str)
            and value.strip().lower() == "none"
        ):
            filtered[key] = value
            has_detail = True
            continue
        if field == "source_urls":
            valid_sources = private_health_recursive_urls(value)
            invalid_sources = private_health_invalid_source_values(value)
            if valid_sources:
                filtered[key] = list(dict.fromkeys(valid_sources))
            if invalid_sources:
                filtered["unresolved_source_provenance"] = (
                    invalid_sources[0]
                    if len(invalid_sources) == 1
                    else invalid_sources
                )
                has_detail = True
            continue
        if field == "checked_at":
            valid_checked_at = private_health_valid_checked_at_values(value)
            invalid_checked_at = private_health_invalid_checked_at_values(value)
            if valid_checked_at:
                filtered[key] = (
                    valid_checked_at[0]
                    if len(valid_checked_at) == 1
                    else valid_checked_at
                )
            if invalid_checked_at:
                filtered["unresolved_checked_at_provenance"] = (
                    invalid_checked_at[0]
                    if len(invalid_checked_at) == 1
                    else invalid_checked_at
                )
                has_detail = True
            continue
        sanitized, supplied = private_health_detail_with_metadata(
            value,
            false_is_value=field != "notes",
        )
        if sanitized is not PRIVATE_HEALTH_NO_VALUE:
            filtered[key] = sanitized
            has_detail = True
            private_health_add_metadata(
                metadata,
                supplied,
                field_aliases,
            )
    if has_detail:
        private_health_add_metadata(filtered, metadata, field_aliases)
    return filtered


def private_health_statement_items(value: Any) -> List[Dict[str, Any]]:
    return [
        private_health_filter_record_values(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES)
        for item in private_health_statement_entries(value)
        if isinstance(item, dict) and private_health_statement_record_has_signal(item)
    ]


def private_health_dependant_items(value: Any) -> List[Dict[str, Any]]:
    return [
        private_health_filter_record_values(item, DEPENDANT_FIELD_ALIASES)
        for item in private_health_dependant_entries(value)
        if isinstance(item, dict) and private_health_dependant_record_has_signal(item)
    ]


def private_health_statement_context(value: Any) -> bool:
    lowered = display_value(value).lower()
    return any(term in lowered for term in ("statement", "document", "record", "evidence", "policy line"))


def private_health_unique_values(values: List[Any]) -> List[Any]:
    rows: List[Any] = []
    seen: set[str] = set()
    for value in values:
        value = private_health_sanitized_value(value, false_is_value=True)
        if value is PRIVATE_HEALTH_NO_VALUE:
            continue
        key = json.dumps(value, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        rows.append(value)
    return rows


def has_private_health_medicare_inputs(raw: Dict[str, Any]) -> bool:
    private_health = raw.get("private_health", {})
    spouse = raw.get("spouse", {})
    dependant_summary = private_health_dependant_summary_from_values(
        raw.get("dependant_summary", {}),
        raw.get("dependants", []),
    )
    levy = raw.get("medicare_levy", {})
    levy = (
        private_health_filter_record_values(levy, MEDICARE_LEVY_FIELD_ALIASES)
        if isinstance(levy, dict)
        else {}
    )
    mls = raw.get("mls", {})
    mls = private_health_filter_record_values(mls, MLS_FIELD_ALIASES) if isinstance(mls, dict) else {}
    if private_health_core_record_has_inputs(private_health):
        return True
    if private_health_spouse_record_has_inputs(spouse):
        return True
    if private_health_dependant_summary_has_inputs(dependant_summary):
        return True
    notes = private_health_sanitized_note_value(raw.get("notes"))
    if (
        private_health_statement_items(raw.get("statements"))
        or private_health_dependant_items(raw.get("dependants"))
        or notes is not PRIVATE_HEALTH_NO_VALUE
    ):
        return True
    if private_health_levy_record_has_inputs(levy):
        return True
    return private_health_mls_record_has_inputs(mls)


def private_health_core_record_has_inputs(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    record = private_health_filter_record_values(record, PRIVATE_HEALTH_FIELD_ALIASES)
    covered = normalized_item_field(record, PRIVATE_HEALTH_FIELD_ALIASES["covered"])
    if covered is False or private_health_cover_bool(covered) is not None or contains_unknown(covered):
        return True
    return private_health_record_nonfalse_inputs(record, PRIVATE_HEALTH_FIELD_ALIASES, {"covered"})


def private_health_spouse_record_has_inputs(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    record = private_health_filter_record_values(record, SPOUSE_FIELD_ALIASES)
    had_spouse = normalized_item_field(record, SPOUSE_FIELD_ALIASES["had_spouse"])
    if had_spouse is False or private_health_spouse_bool(had_spouse) is not None or contains_unknown(had_spouse):
        return True
    return private_health_record_nonfalse_inputs(record, SPOUSE_FIELD_ALIASES, {"had_spouse"})


def private_health_dependant_summary_has_inputs(record: Any) -> bool:
    record = private_health_normalize_dependant_summary(record)
    if not record:
        return False
    count = normalized_item_field(record, DEPENDANT_SUMMARY_FIELD_ALIASES["count"])
    return not is_missing(count) or private_health_record_nonfalse_inputs(
        record,
        DEPENDANT_SUMMARY_FIELD_ALIASES,
        set(),
    ) or bool(
        private_health_unknown_values(
            record,
            private_health_alias_set(DEPENDANT_SUMMARY_FIELD_ALIASES),
        )
    )


def private_health_levy_record_has_inputs(record: Any) -> bool:
    return private_health_record_nonfalse_inputs(record, MEDICARE_LEVY_FIELD_ALIASES, {"reduction", "exemption"})


def private_health_mls_record_has_inputs(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    record = private_health_filter_record_values(record, MLS_FIELD_ALIASES)
    full_year_family_cover = normalized_item_field(
        record,
        MLS_FIELD_ALIASES["full_year_appropriate_family_cover"],
    )
    if (
        full_year_family_cover is False
        or private_health_cover_bool(full_year_family_cover) is not None
        or contains_unknown(full_year_family_cover)
    ):
        return True
    cover = normalized_item_field(record, MLS_FIELD_ALIASES["appropriate_hospital_cover"])
    if cover is False or private_health_cover_bool(cover) is not None or contains_unknown(cover):
        return True
    return private_health_record_nonfalse_inputs(record, MLS_FIELD_ALIASES, {"review"})


def private_health_mls_has_context(
    raw: Any,
    private_health: Any,
    workflow: Dict[str, Any],
) -> bool:
    return (
        private_health_mls_record_has_inputs(raw)
        or private_health_core_record_has_inputs(private_health)
        or private_health_spouse_record_has_inputs(workflow.get("spouse", {}))
        or private_health_dependant_summary_has_inputs(
            private_health_dependant_summary_from_values(
                workflow.get("dependant_summary", {}),
                workflow.get("dependants", []),
            )
        )
        or bool(private_health_dependant_items(workflow.get("dependants")))
    )


def private_health_record_nonfalse_inputs(
    record: Any,
    field_aliases: Dict[str, tuple[str, ...]],
    ignored_false_fields: set[str],
) -> bool:
    if not isinstance(record, dict):
        return False
    record = private_health_filter_record_values(record, field_aliases)
    for field, aliases in field_aliases.items():
        if field in {"source_urls", "checked_at"}:
            continue
        value = normalized_item_field(record, aliases)
        if is_missing(value):
            continue
        if field == "notes":
            if private_health_freeform_value(value):
                return True
            continue
        if field in ignored_false_fields and phone_bool(value) is False:
            continue
        if private_health_false_only_placeholder(value):
            continue
        if private_health_substantive_value(value, false_is_value=True):
            return True
    return bool(
        private_health_unknown_values(record, private_health_alias_set(field_aliases))
    )


def private_health_overview_context(
    raw: Dict[str, Any],
) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], bool]:
    private_health = raw.get("private_health", {})
    private_health = (
        private_health_filter_record_values(private_health, PRIVATE_HEALTH_FIELD_ALIASES)
        if isinstance(private_health, dict)
        else {}
    )
    statements = private_health_statement_items(raw.get("statements"))
    notes, notes_metadata = private_health_note_detail_with_metadata(
        raw.get("notes")
    )
    notes = None if notes is PRIVATE_HEALTH_NO_VALUE else notes
    if notes is not None and not isinstance(notes, list):
        notes = [notes]
    overview = dict(private_health)
    if private_health_substantive_value(notes, false_is_value=True):
        overview["supplemental_notes"] = notes
        private_health_add_metadata(
            overview,
            notes_metadata,
            PRIVATE_HEALTH_FIELD_ALIASES,
        )
    active = bool(
        private_health_core_record_has_inputs(private_health)
        or statements
        or private_health_substantive_value(notes, false_is_value=True)
    )
    return private_health, statements, overview, active


def private_health_workflow_section_record(
    value: Any,
    section_keys: tuple[str, ...],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Dict[str, Any]:
    records = private_health_section_records(
        {section_keys[0]: value},
        section_keys,
        field_aliases,
    )
    merged = private_health_merge_records(records, field_aliases)
    if field_aliases is PRIVATE_HEALTH_FIELD_ALIASES:
        private_health_capture_cover_lineage(merged, records)
    return merged


def private_health_normalize_workflow_boundary(
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    workflow = dict(raw)
    for key, section_keys, field_aliases in (
        ("private_health", PRIVATE_HEALTH_SECTION_KEYS, PRIVATE_HEALTH_FIELD_ALIASES),
        ("medicare_levy", MEDICARE_LEVY_SECTION_KEYS, MEDICARE_LEVY_FIELD_ALIASES),
        ("mls", MLS_SECTION_KEYS, MLS_FIELD_ALIASES),
        ("spouse", SPOUSE_SECTION_KEYS, SPOUSE_FIELD_ALIASES),
    ):
        if key in workflow:
            workflow[key] = private_health_workflow_section_record(
                workflow[key],
                section_keys,
                field_aliases,
            )
    if "dependant_summary" in workflow or "dependants" in workflow:
        workflow["dependant_summary"] = private_health_dependant_summary_from_values(
            workflow.get("dependant_summary", {}),
            workflow.get("dependants", []),
        )
        dependant_supplemental = private_health_dependant_supplemental_records(
            workflow.get("dependants", []),
            nested=False,
        )
        if dependant_supplemental:
            workflow["dependant_summary"]["dependant_supplemental_facts"] = [
                detail for detail, _ in dependant_supplemental
            ]
            for _, metadata in dependant_supplemental:
                private_health_add_metadata(
                    workflow["dependant_summary"],
                    metadata,
                    DEPENDANT_SUMMARY_FIELD_ALIASES,
                )
    if "statements" in workflow:
        statement_value = workflow["statements"]
        workflow["statements"] = private_health_statement_items(statement_value)
        statement_notes: List[Any] = []
        for detail, metadata in private_health_statement_supplemental_records(
            statement_value
        ):
            note: Dict[str, Any] = {"private_health_statement": detail}
            private_health_add_metadata(
                note,
                metadata,
                PRIVATE_HEALTH_FIELD_ALIASES,
            )
            statement_notes.append(note)
        if statement_notes:
            existing_notes = private_health_sanitized_note_value(
                workflow.get("notes")
            )
            workflow["notes"] = private_health_unique_values(
                [
                    *(
                        existing_notes
                        if isinstance(existing_notes, list)
                        else []
                        if existing_notes is PRIVATE_HEALTH_NO_VALUE
                        else [existing_notes]
                    ),
                    *statement_notes,
                ]
            )
    return workflow


def private_health_value_with_income_year(value: Any, income_year: Any) -> Any:
    if isinstance(value, list):
        return [
            private_health_value_with_income_year(item, income_year)
            for item in value
        ]
    if not isinstance(value, dict):
        return value
    child_keys = set(PRIVATE_HEALTH_STATEMENT_ITEM_KEYS) | set(
        PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS
    )
    record = dict(value)
    for key in child_keys:
        if key in record:
            record[key] = private_health_value_with_income_year(
                record[key],
                income_year,
            )
    record["_income_year"] = income_year
    return record


def private_health_workflow_with_income_year(raw: Dict[str, Any]) -> Dict[str, Any]:
    raw = private_health_normalize_workflow_boundary(raw)
    income_year = text(raw.get("income_year"), DEFAULT_INCOME_YEAR)
    workflow = dict(raw)
    workflow["income_year"] = income_year
    for key in (
        "private_health",
        "statements",
        "medicare_levy",
        "mls",
        "spouse",
        "dependant_summary",
        "dependants",
    ):
        if key in workflow:
            workflow[key] = private_health_value_with_income_year(
                workflow[key],
                income_year,
            )
    return workflow


def private_health_medicare_rows(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = private_health_workflow_with_income_year(raw)
    if not has_private_health_medicare_inputs(raw):
        return []
    rows: List[Dict[str, Any]] = []
    private_health, statements, overview, overview_active = private_health_overview_context(raw)
    if overview_active:
        rows.append(private_health_overview_row(overview, statements))
        rows.extend(private_health_statement_rows(statements))
    levy_row = medicare_levy_row(raw.get("medicare_levy", {}))
    if levy_row is not None:
        rows.append(levy_row)
    mls_row = mls_review_row(raw.get("mls", {}), private_health, raw)
    if mls_row is not None:
        rows.append(mls_row)
    spouse_row = spouse_review_row(raw.get("spouse", {}))
    if spouse_row is not None:
        rows.append(spouse_row)
    rows.extend(dependant_rows(raw.get("dependant_summary", {}), raw.get("dependants", [])))
    return rows


def private_health_overview_row(
    raw: Dict[str, Any],
    statements: List[Dict[str, Any]],
) -> Dict[str, Any]:
    fields = PRIVATE_HEALTH_FIELD_ALIASES
    raw = private_health_filter_record_values(raw, fields)
    answer = (
        f"Private hospital cover {private_health_bool_field_text(raw, fields['covered'])}; "
        f"period {private_health_period_text(raw, fields)}; "
        f"days covered {private_health_field_text(raw, fields['days_covered'])}; "
        f"cover evidence {private_health_field_text(raw, fields['evidence'])}; "
        f"statement rows {len(statements)}"
    )
    answer = private_health_append_record_details(answer, raw, fields)
    gaps = private_health_overview_gaps(raw, statements)
    return guide_row(
        "PHI-OVERVIEW",
        "M2 / Private health insurance policy details",
        "Private hospital cover review",
        answer,
        "Private hospital cover and policy periods are prep facts only. Confirm statement and cover "
        "evidence before accountant review; no levy, surcharge, or rebate is worked out.",
        "Accountant review",
        private_health_row_sources(raw, [*ATO_PRIVATE_HEALTH_STATEMENT_SOURCES, *ATO_MLS_SOURCES]),
        tab_text=private_health_review_tab("Private hospital cover", gaps),
        row_kind="private-health-overview",
        checked_at=private_health_row_checked_at(raw, fields),
        facts=[
            taxmate_handoff.fact(
                "private-hospital-cover",
                "Private hospital cover supplied",
                normalized_item_field(raw, fields["covered"]),
                action_kind="destination-requires-review",
            ),
            taxmate_handoff.fact(
                "cover-period",
                "Cover period",
                private_health_period_text(raw, fields),
                action_kind="retain-evidence",
            ),
            taxmate_handoff.fact(
                "days-covered",
                "Days covered",
                normalized_item_field(raw, fields["days_covered"]),
                action_kind="retain-evidence",
            ),
            taxmate_handoff.fact(
                "cover-evidence",
                "Cover evidence",
                normalized_item_field(raw, fields["evidence"]),
                action_kind="retain-evidence",
            ),
            taxmate_handoff.fact(
                "statement-count",
                "Private health statement lines supplied",
                len(statements),
                action_kind="not-entered-directly",
            ),
            *private_health_supplemental_handoff_facts(raw, fields),
        ],
    )


def private_health_statement_rows(raw: Any) -> List[Dict[str, Any]]:
    items = raw.get("statements", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    fields = PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES
    items = private_health_statement_items(items)
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        claim_code = normalized_item_field(item, fields["tax_claim_code"])
        destination_context = {
            "tax_claim_code": claim_code,
            "conflicted": bool(private_health_record_conflicts(item, fields)),
        }
        answer = (
            f"Insurer/fund {private_health_field_text(item, fields['insurer'])}; "
            f"policy/membership {private_health_field_text(item, fields['membership_id'])}; "
            f"benefit code {private_health_field_text(item, fields['benefit_code'])}; "
            "premiums eligible for rebate "
            f"{private_health_amount_field_text(item, fields['premiums_eligible_for_rebate'])}; "
            f"rebate received {private_health_amount_field_text(item, fields['rebate_received'])}; "
            f"tax claim code {private_health_field_text(item, fields['tax_claim_code'])}; "
            f"days covered {private_health_field_text(item, fields['days_covered'])}; "
            f"period {private_health_period_text(item, fields)}; "
            f"statement evidence {private_health_field_text(item, fields['evidence'])}"
        )
        answer = private_health_append_record_details(answer, item, fields)
        gaps = private_health_statement_gaps(item)
        rows.append(
            guide_row(
                f"PHI-STMT-{index}",
                "Private health insurance policy details",
                "Private health insurance statement line",
                answer,
                "Keep each insurer statement line separate with its evidence and source provenance. "
                "This is prep-only and does not calculate or decide a rebate.",
                "Accountant review",
                private_health_row_sources(item, ATO_PRIVATE_HEALTH_STATEMENT_SOURCES),
                tab_text=private_health_review_tab(f"Private health statement {index}", gaps),
                row_kind="private-health-statement",
                checked_at=private_health_row_checked_at(item, fields),
                facts=[
                    taxmate_handoff.fact(
                        "insurer",
                        "Insurer or health fund",
                        normalized_item_field(item, fields["insurer"]),
                        action_kind="destination-requires-review",
                    ),
                    taxmate_handoff.fact(
                        "membership-id",
                        "Policy or membership identifier",
                        normalized_item_field(item, fields["membership_id"]),
                        action_kind="destination-requires-review",
                    ),
                    taxmate_handoff.fact(
                        "benefit-code",
                        "Benefit code",
                        normalized_item_field(item, fields["benefit_code"]),
                        action_kind="enter-reviewed-value",
                        destination_key="phi-benefit-code-l",
                        destination_context=destination_context,
                    ),
                    taxmate_handoff.fact(
                        "premiums-eligible-for-rebate",
                        "Premiums eligible for rebate",
                        normalized_item_field(item, fields["premiums_eligible_for_rebate"]),
                        action_kind="enter-reviewed-value",
                        destination_key="phi-premiums-j",
                        destination_context=destination_context,
                    ),
                    taxmate_handoff.fact(
                        "rebate-received",
                        "Australian Government rebate received",
                        normalized_item_field(item, fields["rebate_received"]),
                        action_kind="enter-reviewed-value",
                        destination_key="phi-rebate-k",
                        destination_context=destination_context,
                    ),
                    taxmate_handoff.fact(
                        "tax-claim-code",
                        "Tax claim code",
                        claim_code,
                        action_kind="enter-reviewed-value",
                        destination_key="phi-tax-claim-code",
                        destination_context=destination_context,
                    ),
                    taxmate_handoff.fact(
                        "days-covered",
                        "Days covered",
                        normalized_item_field(item, fields["days_covered"]),
                        action_kind="retain-evidence",
                    ),
                    taxmate_handoff.fact(
                        "cover-period",
                        "Statement cover period",
                        private_health_period_text(item, fields),
                        action_kind="retain-evidence",
                    ),
                    taxmate_handoff.fact(
                        "statement-evidence",
                        "Statement evidence",
                        normalized_item_field(item, fields["evidence"]),
                        action_kind="retain-evidence",
                    ),
                    *private_health_supplemental_handoff_facts(item, fields),
                ],
            )
        )
    return rows


def medicare_levy_row(raw: Any) -> Optional[Dict[str, Any]]:
    raw = (
        private_health_filter_record_values(raw, MEDICARE_LEVY_FIELD_ALIASES)
        if isinstance(raw, dict)
        else raw
    )
    if not private_health_levy_record_has_inputs(raw):
        return None
    fields = MEDICARE_LEVY_FIELD_ALIASES
    exemption_value = normalized_item_field(raw, fields["exemption"])
    gaps = medicare_levy_gaps(raw)
    m1_semantic_conflicts = (
        "no-exemption answer conflicts with an exemption category",
        "no-exemption answer conflicts with exemption days",
        "exemption answer requires positive full or half exemption days",
        "full and half exemption days exceed the income year",
    )
    destination_context = {
        "exemption": exemption_value,
        "conflicted": bool(private_health_record_conflicts(raw, fields))
        or any(marker in gaps for marker in m1_semantic_conflicts),
    }
    answer = (
        f"Reduction signal {private_health_bool_field_text(raw, fields['reduction'])}; "
        f"exemption signal {private_health_bool_field_text(raw, fields['exemption'])}; "
        f"exemption category {private_health_field_text(raw, fields['exemption_category'])}; "
        f"full exemption days {private_health_field_text(raw, fields['full_exemption_days'])}; "
        f"half exemption days {private_health_field_text(raw, fields['half_exemption_days'])}; "
        f"evidence {private_health_field_text(raw, fields['evidence'])}"
    )
    answer = private_health_append_record_details(answer, raw, fields)
    return guide_row(
        "MEDICARE-LEVY",
        "M1 Medicare levy reduction or exemption",
        "Medicare levy reduction and exemption review",
        answer,
        "Collect reduction and exemption signals and evidence for accountant review. TaxMate does "
        "not determine eligibility or calculate the Medicare levy.",
        "Accountant review",
        private_health_row_sources(raw, ATO_MEDICARE_LEVY_SOURCES),
        tab_text=private_health_review_tab("Medicare levy", gaps),
        row_kind="medicare-levy-review",
        checked_at=private_health_row_checked_at(raw, fields),
        facts=[
            taxmate_handoff.fact(
                "reduction-signal",
                "Medicare levy reduction signal",
                normalized_item_field(raw, fields["reduction"]),
                action_kind="not-entered-directly",
            ),
            taxmate_handoff.fact(
                "exemption-signal",
                "Medicare levy exemption category question",
                exemption_value,
                action_kind="answer-guided-question",
                destination_key="m1-exemption-question",
                destination_context=destination_context,
            ),
            taxmate_handoff.fact(
                "exemption-category",
                "Exemption category",
                normalized_item_field(raw, fields["exemption_category"]),
                action_kind=(
                    "not-entered-directly"
                    if private_health_flag_bool(exemption_value) is False
                    and private_health_field_missing(raw, fields["exemption_category"])
                    else "destination-requires-review"
                ),
            ),
            taxmate_handoff.fact(
                "full-exemption-days",
                "Full exemption days",
                normalized_item_field(raw, fields["full_exemption_days"]),
                action_kind="enter-reviewed-value",
                destination_key="m1-full-days-v",
                destination_context=destination_context,
            ),
            taxmate_handoff.fact(
                "half-exemption-days",
                "Half exemption days",
                normalized_item_field(raw, fields["half_exemption_days"]),
                action_kind="enter-reviewed-value",
                destination_key="m1-half-days-w",
                destination_context=destination_context,
            ),
            taxmate_handoff.fact(
                "levy-evidence",
                "Levy exemption evidence",
                normalized_item_field(raw, fields["evidence"]),
                action_kind="retain-evidence",
            ),
            *private_health_supplemental_handoff_facts(raw, fields),
        ],
    )


def mls_review_row(
    raw: Any,
    private_health: Dict[str, Any],
    workflow: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    raw = private_health_filter_record_values(raw, MLS_FIELD_ALIASES) if isinstance(raw, dict) else raw
    private_health = private_health_filter_record_values(
        private_health,
        PRIVATE_HEALTH_FIELD_ALIASES,
    )
    if not private_health_mls_has_context(raw, private_health, workflow):
        return None
    local = raw if isinstance(raw, dict) else {}
    effective = private_health_effective_mls_record(raw, private_health)
    fields = MLS_FIELD_ALIASES
    local_family_cover = normalized_item_field(
        local,
        fields["full_year_appropriate_family_cover"],
    )
    local_cover = normalized_item_field(local, fields["appropriate_hospital_cover"])
    local_days = normalized_item_field(local, fields["hospital_cover_days"])
    gaps = mls_review_gaps(effective)
    general_conflict_markers = (
        "hospital cover is true but cover days is 0",
        "hospital cover days and days not liable exceed",
        "no-cover answer conflicts",
    )
    family_period_conflict_markers = (
        "confirm partial-year hospital cover period",
        "confirm hospital cover period dates",
        "confirm hospital cover period date order",
        "hospital cover period dates are outside requested income year",
        "reconcile hospital cover period dates",
    )
    family_cover = private_health_cover_bool(local_family_cover)
    local_appropriate_cover = private_health_cover_bool(local_cover)
    mls_conflicted = (
        bool(private_health_record_conflicts(effective, fields))
        or any(marker in gap for gap in gaps for marker in general_conflict_markers)
        or (
            family_cover is True
            and (
                local_appropriate_cover is not True
                or private_health_partial_cover_text(local_cover)
                or any(
                    marker in gap
                    for gap in gaps
                    for marker in family_period_conflict_markers
                )
            )
        )
    )
    cover_destination_context = {
        "explicit_family_cover": local_family_cover,
        "explicit_local_days": local_days,
        "conflicted": mls_conflicted,
    }
    answer = (
        f"Review signal {private_health_bool_field_text(effective, fields['review'])}; "
        "income for surcharge "
        f"{private_health_amount_field_text(effective, fields['income_for_surcharge'])}; "
        f"income tier signal {private_health_field_text(effective, fields['income_tier'])}; "
        "appropriate hospital cover "
        f"{private_health_bool_field_text(effective, fields['appropriate_hospital_cover'])}; "
        f"hospital cover days {private_health_field_text(effective, fields['hospital_cover_days'])}; "
        f"days not liable {private_health_field_text(effective, fields['days_not_liable'])}; "
        f"period {private_health_period_text(effective, fields)}; "
        f"evidence {private_health_field_text(effective, fields['evidence'])}"
    )
    answer = private_health_append_record_details(answer, effective, fields)
    return guide_row(
        "MLS-REVIEW",
        "M2 Medicare levy surcharge",
        "Medicare levy surcharge review",
        answer,
        "Keep cover periods, income-tier signals, spouse/family context, and uncertainty visible for "
        "accountant review. TaxMate does not determine or calculate the surcharge.",
        "Accountant review",
        private_health_row_sources(effective, ATO_MLS_SOURCES),
        tab_text=private_health_review_tab("Medicare levy surcharge", gaps),
        row_kind="medicare-surcharge-review",
        checked_at=private_health_row_checked_at(effective, fields),
        facts=[
            taxmate_handoff.fact(
                "review-signal",
                "Medicare levy surcharge review signal",
                normalized_item_field(effective, fields["review"]),
                action_kind="not-entered-directly",
            ),
            taxmate_handoff.fact(
                "income-for-surcharge",
                "Income for surcharge purposes",
                normalized_item_field(effective, fields["income_for_surcharge"]),
                action_kind="not-entered-directly",
            ),
            taxmate_handoff.fact(
                "income-tier",
                "Income tier signal",
                normalized_item_field(effective, fields["income_tier"]),
                action_kind="not-entered-directly",
            ),
            taxmate_handoff.fact(
                "full-year-family-cover",
                "You and all dependants covered by an appropriate level of private patient hospital cover for the full income year",
                local_family_cover,
                action_kind="answer-guided-question",
                destination_key="m2-cover-question-e",
                destination_context=cover_destination_context,
            ),
            taxmate_handoff.fact(
                "appropriate-hospital-cover",
                "Appropriate hospital cover",
                normalized_item_field(effective, fields["appropriate_hospital_cover"]),
                action_kind="destination-requires-review",
            ),
            taxmate_handoff.fact(
                "hospital-cover-days",
                "Hospital cover days",
                normalized_item_field(effective, fields["hospital_cover_days"]),
                action_kind="retain-evidence",
            ),
            taxmate_handoff.fact(
                "days-not-liable",
                "Days not liable for the surcharge",
                normalized_item_field(effective, fields["days_not_liable"]),
                action_kind="enter-reviewed-value",
                destination_key="m2-days-not-liable-a",
                destination_context={
                    "explicit_family_cover": local_family_cover,
                    "conflicted": mls_conflicted,
                },
            ),
            taxmate_handoff.fact(
                "cover-period",
                "Hospital cover period",
                private_health_period_text(effective, fields),
                action_kind="retain-evidence",
            ),
            taxmate_handoff.fact(
                "cover-evidence",
                "Hospital cover evidence",
                normalized_item_field(effective, fields["evidence"]),
                action_kind="retain-evidence",
            ),
            *private_health_supplemental_handoff_facts(effective, fields),
        ],
    )


def spouse_review_row(raw: Any) -> Optional[Dict[str, Any]]:
    raw = private_health_filter_record_values(raw, SPOUSE_FIELD_ALIASES) if isinstance(raw, dict) else raw
    if not private_health_spouse_record_has_inputs(raw):
        return None
    fields = SPOUSE_FIELD_ALIASES
    answer = (
        f"Had spouse {private_health_bool_field_text(raw, fields['had_spouse'])}; "
        f"period {private_health_period_text(raw, fields)}; "
        f"income for tests {private_health_amount_field_text(raw, fields['income_for_tests'])}; "
        "reportable fringe benefits "
        f"{private_health_amount_field_text(raw, fields['reportable_fringe_benefits'])}; "
        f"reportable super {private_health_amount_field_text(raw, fields['reportable_super'])}; "
        f"net investment loss {private_health_amount_field_text(raw, fields['net_investment_loss'])}; "
        f"income evidence {private_health_field_text(raw, fields['income_evidence'])}"
    )
    answer = private_health_append_record_details(answer, raw, fields)
    gaps = spouse_review_gaps(raw)
    had_spouse = normalized_item_field(raw, fields["had_spouse"])
    spouse_destination_context = {
        "had_spouse": had_spouse,
        "contradicted": any("no-spouse answer conflicts" in gap for gap in gaps),
        "conflicted": bool(private_health_record_conflicts(raw, fields)),
    }
    return guide_row(
        "SPOUSE-REVIEW",
        "Spouse details / M1 / M2",
        "Spouse period and income-test review",
        answer,
        "Spouse period and income-test facts remain prep-only and need source-backed accountant review.",
        "Accountant review",
        private_health_row_sources(raw, ATO_SPOUSE_DEPENDANT_SOURCES),
        tab_text=private_health_review_tab("Spouse facts", gaps),
        row_kind="spouse-review",
        checked_at=private_health_row_checked_at(raw, fields),
        facts=[
            taxmate_handoff.fact(
                "had-spouse",
                "Had a spouse during the income year",
                had_spouse,
                action_kind="answer-guided-question",
                destination_key="spouse-had-question",
                destination_context=spouse_destination_context,
            ),
            taxmate_handoff.fact(
                "spouse-period",
                "Spouse period",
                private_health_period_text(raw, fields),
                action_kind="destination-requires-review",
            ),
            taxmate_handoff.fact(
                "income-for-tests",
                "Spouse income for tests",
                normalized_item_field(raw, fields["income_for_tests"]),
                action_kind="destination-requires-review",
            ),
            taxmate_handoff.fact(
                "reportable-fringe-benefits",
                "Spouse reportable fringe benefits",
                normalized_item_field(raw, fields["reportable_fringe_benefits"]),
                action_kind="destination-requires-review",
            ),
            taxmate_handoff.fact(
                "reportable-super",
                "Spouse reportable super contributions",
                normalized_item_field(raw, fields["reportable_super"]),
                action_kind="destination-requires-review",
            ),
            taxmate_handoff.fact(
                "net-investment-loss",
                "Spouse net investment loss",
                normalized_item_field(raw, fields["net_investment_loss"]),
                action_kind="destination-requires-review",
            ),
            taxmate_handoff.fact(
                "income-evidence",
                "Spouse income evidence",
                normalized_item_field(raw, fields["income_evidence"]),
                action_kind="retain-evidence",
            ),
            *private_health_supplemental_handoff_facts(raw, fields),
        ],
    )


def dependant_rows(summary: Any, items: Any) -> List[Dict[str, Any]]:
    summary = private_health_dependant_summary_from_values(summary, items)
    items = private_health_dependant_items(items)
    rows: List[Dict[str, Any]] = []
    if private_health_dependant_summary_has_inputs(summary) or items:
        summary_fields = DEPENDANT_SUMMARY_FIELD_ALIASES
        count = private_health_field_text(summary, summary_fields["count"])
        answer = f"Dependent children/students count {count}; item rows {len(items)}"
        answer = private_health_append_record_details(answer, summary, DEPENDANT_SUMMARY_FIELD_ALIASES)
        rows.append(
            guide_row(
                "DEPENDANT-SUMMARY",
                "IT8 / M1 / M2 dependants",
                "Dependant child and student summary",
                answer,
                "Keep the supplied count and child/student detail aligned for accountant review; "
                "TaxMate does not decide dependant status.",
                "Accountant review",
                private_health_row_sources(summary, ATO_SPOUSE_DEPENDANT_SOURCES),
                tab_text=private_health_review_tab("Dependant summary", dependant_summary_gaps(summary, items)),
                row_kind="dependant-review",
                checked_at=private_health_row_checked_at(summary, summary_fields),
                facts=[
                    taxmate_handoff.fact(
                        "dependant-count",
                        "Dependent children or students supplied",
                        normalized_item_field(summary, summary_fields["count"]),
                        action_kind="destination-requires-review",
                    ),
                    taxmate_handoff.fact(
                        "dependant-item-count",
                        "Detailed dependant rows supplied",
                        len(items),
                        action_kind="not-entered-directly",
                    ),
                    *private_health_supplemental_handoff_facts(summary, summary_fields),
                ],
            )
        )
    for index, item in enumerate(items, start=1):
        fields = DEPENDANT_FIELD_ALIASES
        answer = (
            f"Name {private_health_field_text(item, fields['name'])}; "
            f"type {private_health_field_text(item, fields['type'])}; "
            f"age {private_health_field_text(item, fields['age'])}; "
            f"student {private_health_bool_field_text(item, fields['student'])}; "
            f"period {private_health_period_text(item, fields)}; "
            f"maintained {private_health_bool_field_text(item, fields['maintained'])}; "
            f"income for tests {private_health_amount_field_text(item, fields['income_for_tests'])}; "
            f"shared care {private_health_field_text(item, fields['shared_care'])}; "
            f"evidence {private_health_field_text(item, fields['evidence'])}"
        )
        answer = private_health_append_record_details(answer, item, fields)
        rows.append(
            guide_row(
                f"DEPENDANT-{index}",
                "M1 / M2 dependant child or student",
                "Dependant child or student review",
                answer,
                "Dependant and student facts remain prep-only. Confirm maintenance, period, student, "
                "income-test, and evidence facts with an accountant.",
                "Accountant review",
                private_health_row_sources(item, ATO_SPOUSE_DEPENDANT_SOURCES),
                tab_text=private_health_review_tab(f"Dependant {index}", dependant_item_gaps(item)),
                row_kind="dependant-review",
                checked_at=private_health_row_checked_at(item, fields),
                facts=[
                    taxmate_handoff.fact("name", "Name", normalized_item_field(item, fields["name"])),
                    taxmate_handoff.fact("type", "Dependant type", normalized_item_field(item, fields["type"])),
                    taxmate_handoff.fact("age", "Age", normalized_item_field(item, fields["age"])),
                    taxmate_handoff.fact("student", "Student", normalized_item_field(item, fields["student"])),
                    taxmate_handoff.fact(
                        "dependant-period",
                        "Dependant period",
                        private_health_period_text(item, fields),
                    ),
                    taxmate_handoff.fact("maintained", "Maintained", normalized_item_field(item, fields["maintained"])),
                    taxmate_handoff.fact(
                        "income-for-tests",
                        "Income for tests",
                        normalized_item_field(item, fields["income_for_tests"]),
                    ),
                    taxmate_handoff.fact("shared-care", "Shared care", normalized_item_field(item, fields["shared_care"])),
                    taxmate_handoff.fact(
                        "evidence",
                        "Dependant evidence",
                        normalized_item_field(item, fields["evidence"]),
                        action_kind="retain-evidence",
                    ),
                    *private_health_supplemental_handoff_facts(item, fields),
                ],
            )
        )
    return rows


def private_health_medicare_evidence_rows(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = private_health_workflow_with_income_year(raw)
    if not has_private_health_medicare_inputs(raw):
        return []
    entries: List[tuple[str, str, str, List[str]]] = []
    private_health, statements, overview, overview_active = private_health_overview_context(raw)
    if overview_active:
        entries.extend(
            private_health_evidence_entries(
                "Private hospital cover",
                "M2 / Private health insurance policy details",
                private_health_overview_gaps(overview, statements),
                private_health_row_sources(overview, [*ATO_PRIVATE_HEALTH_STATEMENT_SOURCES, *ATO_MLS_SOURCES]),
            )
        )
    for index, item in enumerate(statements, start=1):
        entries.extend(
            private_health_evidence_entries(
                f"Private health statement {index}",
                "Private health insurance policy details",
                private_health_statement_gaps(item),
                private_health_row_sources(item, ATO_PRIVATE_HEALTH_STATEMENT_SOURCES),
            )
        )
    levy = raw.get("medicare_levy", {})
    levy = (
        private_health_filter_record_values(levy, MEDICARE_LEVY_FIELD_ALIASES)
        if isinstance(levy, dict)
        else {}
    )
    if private_health_levy_record_has_inputs(levy):
        entries.extend(
            private_health_evidence_entries(
                "Medicare levy",
                "M1 Medicare levy reduction or exemption",
                medicare_levy_gaps(levy),
                private_health_row_sources(levy, ATO_MEDICARE_LEVY_SOURCES),
            )
        )
    mls = raw.get("mls", {})
    mls = private_health_filter_record_values(mls, MLS_FIELD_ALIASES) if isinstance(mls, dict) else {}
    if private_health_mls_has_context(mls, private_health, raw):
        effective_mls = private_health_effective_mls_record(mls, private_health)
        entries.extend(
            private_health_evidence_entries(
                "Medicare levy surcharge",
                "M2 Medicare levy surcharge",
                mls_review_gaps(effective_mls),
                private_health_row_sources(effective_mls, ATO_MLS_SOURCES),
            )
        )
    spouse = raw.get("spouse", {})
    spouse = (
        private_health_filter_record_values(spouse, SPOUSE_FIELD_ALIASES)
        if isinstance(spouse, dict)
        else {}
    )
    if private_health_spouse_record_has_inputs(spouse):
        entries.extend(
            private_health_evidence_entries(
                "Spouse",
                "Spouse details / M1 / M2",
                spouse_review_gaps(spouse),
                private_health_row_sources(spouse, ATO_SPOUSE_DEPENDANT_SOURCES),
            )
        )
    summary = private_health_dependant_summary_from_values(
        raw.get("dependant_summary", {}),
        raw.get("dependants", []),
    )
    dependants = private_health_dependant_items(raw.get("dependants"))
    if private_health_dependant_summary_has_inputs(summary) or dependants:
        entries.extend(
            private_health_evidence_entries(
                "Dependant summary",
                "IT8 / M1 / M2 dependants",
                dependant_summary_gaps(summary, dependants),
                private_health_row_sources(summary, ATO_SPOUSE_DEPENDANT_SOURCES),
            )
        )
    for index, item in enumerate(dependants, start=1):
        entries.extend(
            private_health_evidence_entries(
                f"Dependant {index}",
                "M1 / M2 dependant child or student",
                dependant_item_gaps(item),
                private_health_row_sources(item, ATO_SPOUSE_DEPENDANT_SOURCES),
            )
        )

    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for subject, area, gap, sources in entries:
        key = f"{subject}|{area}|{gap}|{'|'.join(sources)}"
        if key in seen:
            continue
        seen.add(key)
        rows.append(private_health_evidence_row(len(rows) + 1, subject, area, gap, sources))
    return rows


def private_health_mls_inherited_aliases() -> Dict[str, tuple[str, ...]]:
    return {
        field: PRIVATE_HEALTH_FIELD_ALIASES[field]
        for field in PRIVATE_HEALTH_MLS_INHERITED_FIELDS
    }


def private_health_mls_inherited_cover_has_inputs(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    for field in (
        "covered",
        "period_start",
        "period_end",
        "period",
        "days_covered",
        "evidence",
    ):
        value = normalized_item_field(record, PRIVATE_HEALTH_FIELD_ALIASES[field])
        if value is False and field in {
            "period_start",
            "period_end",
            "period",
            "days_covered",
        }:
            continue
        if private_health_substantive_value(value, false_is_value=True):
            return True
    return False


def private_health_effective_mls_record(raw: Any, private_health: Dict[str, Any]) -> Dict[str, Any]:
    local = private_health_filter_record_values(raw, MLS_FIELD_ALIASES) if isinstance(raw, dict) else {}
    for field in (
        "period_start",
        "period_end",
        "period",
        "hospital_cover_days",
    ):
        for alias in MLS_FIELD_ALIASES[field]:
            if private_health_false_only_placeholder(local.get(alias)):
                local.pop(alias)
    if not private_health_mls_record_has_inputs(local):
        local = {}
    private_health = private_health_filter_record_values(
        private_health,
        PRIVATE_HEALTH_FIELD_ALIASES,
    )
    cover_has_inputs = private_health_mls_inherited_cover_has_inputs(private_health)
    source_urls = (
        (
            private_health_recursive_urls(private_health["_cover_source_urls"])
            if "_cover_source_urls" in private_health
            else private_health_provenance_urls(private_health)
        )
        if cover_has_inputs
        else []
    )
    checked_at = (
        (
            private_health_recursive_scalar_values(private_health["_cover_checked_at"])
            if "_cover_checked_at" in private_health
            else private_health_alias_values(
                private_health,
                PRIVATE_HEALTH_FIELD_ALIASES["checked_at"],
            )
        )
        if cover_has_inputs
        else []
    )
    inherited_conflicts = (
        (
            private_health_recursive_scalar_values(
                private_health["_cover_source_conflicts"]
            )
            if "_cover_source_conflicts" in private_health
            else [
                conflict
                for conflict in private_health_mls_inherited_conflicts(
                    private_health
                )
                if conflict
            ]
        )
        if cover_has_inputs
        else []
    )
    inherited: Dict[str, Any] = {
        "_income_year": private_health.get("_income_year"),
        "appropriate_hospital_cover": normalized_item_field(
            private_health,
            PRIVATE_HEALTH_FIELD_ALIASES["covered"],
        ),
        "cover_period_start": normalized_item_field(
            private_health,
            PRIVATE_HEALTH_FIELD_ALIASES["period_start"],
        ),
        "cover_period_end": normalized_item_field(
            private_health,
            PRIVATE_HEALTH_FIELD_ALIASES["period_end"],
        ),
        "cover_period": normalized_item_field(
            private_health,
            PRIVATE_HEALTH_FIELD_ALIASES["period"],
        ),
        "hospital_cover_days": normalized_item_field(
            private_health,
            PRIVATE_HEALTH_FIELD_ALIASES["days_covered"],
        ),
        "cover_evidence": normalized_item_field(
            private_health,
            PRIVATE_HEALTH_FIELD_ALIASES["evidence"],
        ),
    }
    if source_urls:
        inherited["source_urls"] = source_urls
    if checked_at:
        inherited["checked_at"] = checked_at
    local_overrides = {
        "appropriate_hospital_cover": "appropriate_hospital_cover",
        "period_start": "cover_period_start",
        "period_end": "cover_period_end",
        "period": "cover_period",
        "hospital_cover_days": "hospital_cover_days",
        "evidence": "cover_evidence",
    }
    local_conflicts: List[str] = []
    for field, inherited_key in local_overrides.items():
        aliases = MLS_FIELD_ALIASES[field]
        if not any(alias in local for alias in aliases):
            continue
        local_value = normalized_item_field(local, aliases)
        if not private_health_substantive_value(
            local_value,
            false_is_value=True,
        ):
            continue
        inherited_value = inherited.get(inherited_key)
        if (
            not is_missing(inherited_value)
            and item_alias_conflict_key(field, inherited_value)
            != item_alias_conflict_key(field, local_value)
        ):
            local_conflicts.append(
                f"{field} inherited {display_value(inherited_value)} vs local {display_value(local_value)}"
            )
        inherited.pop(inherited_key, None)
    effective = private_health_merge_records(
        [
            inherited,
            local,
        ],
        MLS_FIELD_ALIASES,
    )
    private_health_add_metadata(
        effective,
        {
            "source_urls": private_health_provenance_urls(local),
            "checked_at": private_health_alias_values(
                local,
                MLS_FIELD_ALIASES["checked_at"],
            ),
        },
        MLS_FIELD_ALIASES,
    )
    conflicts = private_health_unique_values(
        [
            *private_health_recursive_scalar_values(
                effective.pop("_source_conflicts", None)
            ),
            *inherited_conflicts,
            *local_conflicts,
        ]
    )
    if conflicts:
        effective["_source_conflicts"] = conflicts
    return effective


def private_health_evidence_entries(
    subject: str,
    area: str,
    gaps: List[str],
    sources: List[str],
) -> List[tuple[str, str, str, List[str]]]:
    return [(subject, area, gap, sources) for gap in gaps]


def private_health_evidence_row(
    index: int,
    subject: str,
    area: str,
    gap: str,
    sources: List[str],
) -> Dict[str, Any]:
    return guide_row(
        f"PHI-EVID-{index}",
        area,
        "Evidence required",
        f"{subject}: {gap}",
        "The supplied fact remains prep-only and unresolved until the missing or conflicting evidence is reviewed.",
        "Evidence",
        sources,
        tab_text=f"{subject} needs {gap} before accountant review.",
        row_kind="evidence-queue",
        facts=handoff_facts(
            ("subject", "Subject", subject),
            ("evidence-gap", "Evidence or conflict to resolve", gap),
        ),
    )


def private_health_false_only_placeholder(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, list):
        return bool(value) and all(
            private_health_false_only_placeholder(item) for item in value
        )
    if isinstance(value, dict):
        supplied = [item for key, item in value.items() if not key.startswith("_")]
        return bool(supplied) and all(
            private_health_false_only_placeholder(item) for item in supplied
        )
    return False


def private_health_without_false_period_placeholders(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Dict[str, Any]:
    filtered = dict(raw)
    for field in ("period_start", "period_end", "period"):
        for alias in field_aliases[field]:
            if private_health_false_only_placeholder(filtered.get(alias)):
                filtered.pop(alias)
    return filtered


def private_health_period_fact_supplied(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> bool:
    if any(
        parse_iso_date(normalized_item_field(raw, field_aliases[field])) is not None
        for field in ("period_start", "period_end")
    ):
        return True
    period = normalized_item_field(raw, field_aliases["period"])
    return not is_missing(period) and private_health_period_value_supported(period)


def private_health_false_cover_period_gaps(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
    label: str,
    conflict: str,
) -> List[str]:
    filtered = private_health_without_false_period_placeholders(raw, field_aliases)
    gaps = private_health_period_gaps(
        filtered,
        field_aliases,
        label,
        required=False,
        partial_is_gap=False,
    )
    if private_health_period_fact_supplied(filtered, field_aliases):
        gaps.insert(0, conflict)
    return private_health_unique_text(gaps)


def private_health_overview_gaps(
    raw: Dict[str, Any],
    statements: List[Dict[str, Any]],
) -> List[str]:
    gaps: List[str] = []
    covered_raw = normalized_item_field(raw, PRIVATE_HEALTH_FIELD_ALIASES["covered"])
    covered = private_health_cover_bool(covered_raw)
    if covered is None:
        gaps.append("confirm private hospital cover status")
    if covered is True and not statements:
        gaps.append("missing private health statement")
    if covered is True and evidence_missing(normalized_item_field(raw, PRIVATE_HEALTH_FIELD_ALIASES["evidence"])):
        if not any(
            not evidence_missing(normalized_item_field(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["evidence"]))
            for item in statements
        ):
            gaps.append("confirm private hospital cover evidence")
    if covered is True:
        if private_health_partial_cover_text(covered_raw):
            gaps.append("confirm partial-year private hospital cover")
        gaps.extend(
            private_health_period_gaps(
                raw,
                PRIVATE_HEALTH_FIELD_ALIASES,
                "private hospital cover period",
                required=True,
                partial_is_gap=True,
            )
        )
        days = normalized_item_field(raw, PRIVATE_HEALTH_FIELD_ALIASES["days_covered"])
        if private_health_day_count(days) == 0:
            gaps.append("cover is true but days covered is 0")
        gaps.extend(private_health_statement_collection_gaps(raw, statements))
    if covered is False:
        if statements:
            gaps.append("no-cover answer conflicts with supplied private health statement lines")
        gaps.extend(
            private_health_false_cover_period_gaps(
                raw,
                PRIVATE_HEALTH_FIELD_ALIASES,
                "private hospital cover period",
                "no-cover answer conflicts with a supplied private hospital cover period",
            )
        )
        days = normalized_item_field(raw, PRIVATE_HEALTH_FIELD_ALIASES["days_covered"])
        parsed_days = private_health_day_count(days)
        if parsed_days is not None and parsed_days > 0:
            gaps.append("no-cover answer conflicts with positive days covered")
    gaps.extend(private_health_record_gaps(raw, PRIVATE_HEALTH_FIELD_ALIASES))
    return private_health_unique_text(gaps)


def private_health_statement_gaps(item: Any) -> List[str]:
    if not isinstance(item, dict):
        return ["confirm private health statement details"]
    gaps: List[str] = []
    if private_health_field_missing(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["insurer"]):
        gaps.append("confirm insurer or health fund")
    benefit_code = normalized_item_field(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["benefit_code"])
    if not private_health_benefit_code_valid(benefit_code):
        gaps.append(f"confirm benefit code ({private_health_raw_text(benefit_code)})")
    premiums = normalized_item_field(
        item,
        PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["premiums_eligible_for_rebate"],
    )
    if private_health_amount_needs_evidence(premiums):
        gaps.append(f"confirm premium amount ({private_health_raw_text(premiums)})")
    rebate = normalized_item_field(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["rebate_received"])
    if private_health_amount_needs_evidence(rebate):
        gaps.append(f"confirm rebate amount ({private_health_raw_text(rebate)})")
    tax_claim_code = normalized_item_field(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["tax_claim_code"])
    if not private_health_tax_claim_code_valid(tax_claim_code):
        gaps.append(f"confirm tax claim code ({private_health_raw_text(tax_claim_code)})")
    statement_evidence = normalized_item_field(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["evidence"])
    if evidence_missing(statement_evidence):
        gaps.append(f"confirm statement evidence ({private_health_raw_text(statement_evidence)})")
    gaps.extend(
        private_health_period_gaps(
            item,
            PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES,
            "statement cover period",
            required=True,
            partial_is_gap=False,
        )
    )
    gaps.extend(private_health_record_gaps(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES))
    return private_health_unique_text(gaps)


def medicare_levy_gaps(raw: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    reduction_raw = normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["reduction"])
    exemption_raw = normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["exemption"])
    reduction = private_health_flag_bool(reduction_raw)
    exemption = private_health_flag_bool(exemption_raw)
    if not is_missing(reduction_raw) and reduction is None:
        gaps.append("resolve Medicare levy reduction uncertainty")
    if not is_missing(exemption_raw) and exemption is None:
        gaps.append("resolve Medicare levy exemption uncertainty")
    evidence = normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["evidence"])
    if (reduction is True or exemption is True or contains_unknown(reduction_raw) or contains_unknown(exemption_raw)) and evidence_missing(evidence):
        gaps.append("confirm Medicare levy reduction or exemption evidence")
    if exemption is True:
        category = normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["exemption_category"])
        if is_missing(category) or contains_unknown(category):
            gaps.append("confirm Medicare levy exemption category")
        full_days = normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["full_exemption_days"])
        half_days = normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["half_exemption_days"])
        if is_missing(full_days) and is_missing(half_days):
            gaps.append("confirm full or half exemption days")
    if exemption is False:
        if not is_missing(normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["exemption_category"])):
            gaps.append("no-exemption answer conflicts with an exemption category")
        if any(
            (private_health_day_count(normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES[field])) or 0) > 0
            for field in ("full_exemption_days", "half_exemption_days")
        ):
            gaps.append("no-exemption answer conflicts with exemption days")
    for field, label in (
        ("full_exemption_days", "full exemption days"),
        ("half_exemption_days", "half exemption days"),
    ):
        value = normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES[field])
        if not is_missing(value) and private_health_day_count(value) is None:
            gaps.append(f"confirm {label} ({private_health_raw_text(value)})")
    full_days = private_health_day_count(
        normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["full_exemption_days"])
    )
    half_days = private_health_day_count(
        normalized_item_field(raw, MEDICARE_LEVY_FIELD_ALIASES["half_exemption_days"])
    )
    if exemption is True and (full_days is None or full_days == 0) and (
        half_days is None or half_days == 0
    ):
        gaps.append("exemption answer requires positive full or half exemption days")
    supplied_days = [value for value in (full_days, half_days) if value is not None]
    if supplied_days and sum(supplied_days) > private_health_income_year_day_limit(raw):
        gaps.append("full and half exemption days exceed the income year")
    gaps.extend(private_health_record_gaps(raw, MEDICARE_LEVY_FIELD_ALIASES))
    return private_health_unique_text(gaps)


def mls_review_gaps(raw: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    review_raw = normalized_item_field(raw, MLS_FIELD_ALIASES["review"])
    family_cover_raw = normalized_item_field(
        raw,
        MLS_FIELD_ALIASES["full_year_appropriate_family_cover"],
    )
    family_cover = private_health_cover_bool(family_cover_raw)
    cover_raw = normalized_item_field(raw, MLS_FIELD_ALIASES["appropriate_hospital_cover"])
    cover = private_health_cover_bool(cover_raw)
    income = normalized_item_field(raw, MLS_FIELD_ALIASES["income_for_surcharge"])
    tier = normalized_item_field(raw, MLS_FIELD_ALIASES["income_tier"])
    review = private_health_flag_bool(review_raw)
    if not is_missing(review_raw) and review is None:
        gaps.append("resolve Medicare levy surcharge review uncertainty")
    if not is_missing(family_cover_raw) and family_cover is None:
        gaps.append("resolve full-year family cover uncertainty")
    if cover is None:
        gaps.append("confirm appropriate private patient hospital cover")
    if not is_missing(income) and private_health_amount_needs_evidence(income):
        gaps.append(f"confirm surcharge income amount ({private_health_raw_text(income)})")
    if not is_missing(tier) and not private_health_mls_tier_valid(tier):
        gaps.append(f"confirm Medicare levy surcharge income tier ({private_health_raw_text(tier)})")
    if cover is False and (is_missing(income) or private_health_amount_needs_evidence(income)) and (
        is_missing(tier) or contains_unknown(tier)
    ):
        gaps.append("confirm Medicare levy surcharge income or tier facts")
    if cover is True:
        if private_health_partial_cover_text(cover_raw):
            gaps.append("confirm partial-year appropriate hospital cover")
        gaps.extend(
            private_health_period_gaps(
                raw,
                MLS_FIELD_ALIASES,
                "hospital cover period",
                required=True,
                partial_is_gap=True,
            )
        )
        days = normalized_item_field(raw, MLS_FIELD_ALIASES["hospital_cover_days"])
        if private_health_day_count(days) == 0:
            gaps.append("hospital cover is true but cover days is 0")
    if family_cover is True:
        if cover is False:
            gaps.append(
                "full-year family-cover answer conflicts with no appropriate hospital cover"
            )
        if private_health_day_count(
            normalized_item_field(raw, MLS_FIELD_ALIASES["hospital_cover_days"])
        ) != 365:
            gaps.append("confirm 365 cover days for the full-year family-cover answer")
    if cover is False:
        days = normalized_item_field(raw, MLS_FIELD_ALIASES["hospital_cover_days"])
        parsed_days = private_health_day_count(days)
        if parsed_days is not None and parsed_days > 0:
            gaps.append("no-cover answer conflicts with positive hospital cover days")
        gaps.extend(
            private_health_false_cover_period_gaps(
                raw,
                MLS_FIELD_ALIASES,
                "hospital cover period",
                "no-cover answer conflicts with a supplied hospital cover period",
            )
        )
    days_not_liable = normalized_item_field(raw, MLS_FIELD_ALIASES["days_not_liable"])
    if not is_missing(days_not_liable) and private_health_day_count(days_not_liable) is None:
        gaps.append(f"confirm days not liable ({private_health_raw_text(days_not_liable)})")
    cover_days = private_health_day_count(
        normalized_item_field(raw, MLS_FIELD_ALIASES["hospital_cover_days"])
    )
    not_liable_days = private_health_day_count(days_not_liable)
    supplied_days = [value for value in (cover_days, not_liable_days) if value is not None]
    if supplied_days and sum(supplied_days) > private_health_income_year_day_limit(raw):
        gaps.append("hospital cover days and days not liable exceed the income year")
    evidence = normalized_item_field(raw, MLS_FIELD_ALIASES["evidence"])
    if (
        (not is_missing(review_raw) and review is None)
        or cover is None
        or private_health_partial_cover_text(cover_raw)
        or private_health_partial_period(raw, MLS_FIELD_ALIASES)
    ) and evidence_missing(evidence):
        gaps.append("confirm Medicare levy surcharge cover evidence")
    gaps.extend(private_health_record_gaps(raw, MLS_FIELD_ALIASES))
    return private_health_unique_text(gaps)


def spouse_review_gaps(raw: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    had_raw = normalized_item_field(raw, SPOUSE_FIELD_ALIASES["had_spouse"])
    had_spouse = private_health_spouse_bool(had_raw)
    if had_spouse is False:
        filtered = private_health_without_false_period_placeholders(
            raw,
            SPOUSE_FIELD_ALIASES,
        )
        positive_amount = False
        amount_gaps: List[str] = []
        for field, label in (
            ("income_for_tests", "spouse income for tests"),
            ("reportable_fringe_benefits", "spouse reportable fringe benefits"),
            ("reportable_super", "spouse reportable super"),
            ("net_investment_loss", "spouse net investment loss"),
        ):
            value = normalized_item_field(filtered, SPOUSE_FIELD_ALIASES[field])
            if value is False or is_missing(value):
                continue
            amount = safe_money_value(value)
            if amount is None or amount < 0:
                amount_gaps.append(
                    f"confirm {label} ({private_health_raw_text(value)})"
                )
            elif amount > 0:
                positive_amount = True
        income_evidence = normalized_item_field(
            filtered,
            SPOUSE_FIELD_ALIASES["income_evidence"],
        )
        notes = normalized_item_field(filtered, SPOUSE_FIELD_ALIASES["notes"])
        supplemental = private_health_unknown_values(
            filtered,
            private_health_alias_set(SPOUSE_FIELD_ALIASES),
        )
        if (
            positive_amount
            or not evidence_missing(income_evidence)
            or private_health_freeform_value(notes)
            or supplemental
            or private_health_period_fact_supplied(
            filtered,
            SPOUSE_FIELD_ALIASES,
            )
        ):
            gaps.append("no-spouse answer conflicts with supplied spouse period or income facts")
        gaps.extend(amount_gaps)
        gaps.extend(
            private_health_period_gaps(
                filtered,
                SPOUSE_FIELD_ALIASES,
                "spouse period",
                required=False,
                partial_is_gap=False,
            )
        )
        gaps.extend(private_health_record_gaps(filtered, SPOUSE_FIELD_ALIASES))
        return private_health_unique_text(gaps)
    if had_spouse is None:
        gaps.append("confirm whether taxpayer had a spouse")
    gaps.extend(
        private_health_period_gaps(
            raw,
            SPOUSE_FIELD_ALIASES,
            "spouse period",
            required=True,
            partial_is_gap=False,
        )
    )
    income = normalized_item_field(raw, SPOUSE_FIELD_ALIASES["income_for_tests"])
    if private_health_amount_needs_evidence(income):
        gaps.append(f"confirm spouse income for tests ({private_health_raw_text(income)})")
    income_evidence = normalized_item_field(raw, SPOUSE_FIELD_ALIASES["income_evidence"])
    if evidence_missing(income_evidence):
        gaps.append(f"confirm spouse income evidence ({private_health_raw_text(income_evidence)})")
    for field, label in (
        ("reportable_fringe_benefits", "spouse reportable fringe benefits"),
        ("reportable_super", "spouse reportable super"),
        ("net_investment_loss", "spouse net investment loss"),
    ):
        value = normalized_item_field(raw, SPOUSE_FIELD_ALIASES[field])
        if not is_missing(value) and private_health_amount_needs_evidence(value):
            gaps.append(f"confirm {label} ({private_health_raw_text(value)})")
    gaps.extend(private_health_record_gaps(raw, SPOUSE_FIELD_ALIASES))
    return private_health_unique_text(gaps)


def dependant_summary_gaps(summary: Dict[str, Any], items: List[Dict[str, Any]]) -> List[str]:
    summary = private_health_normalize_dependant_summary(summary)
    gaps: List[str] = []
    count_raw = normalized_item_field(summary, DEPENDANT_SUMMARY_FIELD_ALIASES["count"])
    count = private_health_nonnegative_integer(count_raw)
    if count is None:
        gaps.append(f"confirm dependant count ({private_health_raw_text(count_raw)})")
    elif count > 0 and not items:
        gaps.append("confirm dependant or student details")
    elif items and count != len(items):
        gaps.append(f"reconcile dependant count {count} with {len(items)} item rows")
    notes = normalized_item_field(summary, DEPENDANT_SUMMARY_FIELD_ALIASES["notes"])
    review_notes, _ = private_health_dependant_remaining_record(
        notes,
        bare=False,
    )
    if review_notes is not PRIVATE_HEALTH_NO_VALUE and private_health_freeform_value(
        review_notes
    ):
        gaps.append(f"review dependant summary notes {display_value(review_notes)}")
    gaps.extend(private_health_record_gaps(summary, DEPENDANT_SUMMARY_FIELD_ALIASES))
    return private_health_unique_text(gaps)


def dependant_item_gaps(item: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    dependant_type = normalized_item_field(item, DEPENDANT_FIELD_ALIASES["type"])
    if private_health_field_missing(item, DEPENDANT_FIELD_ALIASES["type"]):
        gaps.append("confirm dependant child or student type")
    elif not private_health_dependant_type_valid(dependant_type):
        gaps.append(f"confirm dependant child or student type ({private_health_raw_text(dependant_type)})")
    student = normalized_item_field(item, DEPENDANT_FIELD_ALIASES["student"])
    student_flag = private_health_flag_bool(student)
    if student_flag is None:
        gaps.append("confirm dependant student status")
    dependant_type_text = re.sub(
        r"[^a-z]+",
        " ",
        str(dependant_type).lower(),
    ).strip()
    if (
        student_flag is False
        and "student" in dependant_type_text.split()
        and not re.search(r"\b(?:non|not)\s+student\b", dependant_type_text)
    ):
        gaps.append("student dependant type conflicts with student status false")
    age = normalized_item_field(item, DEPENDANT_FIELD_ALIASES["age"])
    if not is_missing(age) and private_health_nonnegative_integer(age) is None:
        gaps.append(f"confirm dependant age ({private_health_raw_text(age)})")
    gaps.extend(
        private_health_period_gaps(
            item,
            DEPENDANT_FIELD_ALIASES,
            "dependant maintenance period",
            required=True,
            partial_is_gap=False,
        )
    )
    evidence = normalized_item_field(item, DEPENDANT_FIELD_ALIASES["evidence"])
    if evidence_missing(evidence):
        gaps.append(f"confirm dependant or student evidence ({private_health_raw_text(evidence)})")
    income = normalized_item_field(item, DEPENDANT_FIELD_ALIASES["income_for_tests"])
    if is_missing(income) and (student_flag is True or "student" in str(dependant_type).lower()):
        gaps.append("confirm dependant student income for tests")
    elif not is_missing(income) and private_health_amount_needs_evidence(income):
        gaps.append(f"confirm dependant income for tests ({private_health_raw_text(income)})")
    maintained = normalized_item_field(item, DEPENDANT_FIELD_ALIASES["maintained"])
    if private_health_flag_bool(maintained) is None:
        gaps.append("confirm dependant maintenance status")
    shared_care = normalized_item_field(item, DEPENDANT_FIELD_ALIASES["shared_care"])
    if not is_missing(shared_care) and not private_health_shared_care_valid(shared_care):
        gaps.append(f"confirm shared care ({private_health_raw_text(shared_care)})")
    gaps.extend(private_health_record_gaps(item, DEPENDANT_FIELD_ALIASES))
    return private_health_unique_text(gaps)


def private_health_period_gaps(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
    label: str,
    *,
    required: bool,
    partial_is_gap: bool,
) -> List[str]:
    raw = private_health_without_false_period_placeholders(raw, field_aliases)
    gaps: List[str] = []
    income_year = raw.get("_income_year")
    income_year_bounds = private_health_income_year_bounds(income_year)
    income_year_days = private_health_income_year_day_limit(raw)
    start = normalized_item_field(raw, field_aliases["period_start"])
    end = normalized_item_field(raw, field_aliases["period_end"])
    period = normalized_item_field(raw, field_aliases["period"])
    days_alias = "days_covered" if "days_covered" in field_aliases else "hospital_cover_days"
    days = normalized_item_field(raw, field_aliases[days_alias]) if days_alias in field_aliases else None
    if private_health_false_only_placeholder(days):
        days = None
    span_days: Optional[int] = None
    explicit_interval: Optional[tuple[date, date]] = None
    period_interval = private_health_period_interval(period, income_year)
    if not is_missing(start) or not is_missing(end):
        start_date = parse_iso_date(start) if not is_missing(start) else None
        end_date = parse_iso_date(end) if not is_missing(end) else None
        if start_date is None or end_date is None:
            gaps.append(f"confirm {label} dates ({private_health_raw_text(start)} to {private_health_raw_text(end)})")
        elif start_date > end_date:
            gaps.append(f"confirm {label} date order ({start} to {end})")
        else:
            explicit_interval = (start_date, end_date)
            span_days = (end_date - start_date).days + 1
            if partial_is_gap and span_days < income_year_days:
                gaps.append(f"confirm partial-year {label}")
        if not is_missing(period):
            if contains_unknown(period) or not private_health_period_value_supported(period):
                gaps.append(f"confirm {label} ({private_health_raw_text(period)})")
            elif period_interval is not None and explicit_interval is not None and period_interval != explicit_interval:
                gaps.append(f"reconcile {label} dates with supplied period ({private_health_raw_text(period)})")
    elif is_missing(period):
        if required and is_missing(days):
            gaps.append(f"confirm {label}")
    elif contains_unknown(period):
        gaps.append(f"confirm {label} ({private_health_raw_text(period)})")
    elif not private_health_period_value_supported(period):
        gaps.append(f"confirm {label} ({private_health_raw_text(period)})")
    else:
        if period_interval is not None:
            span_days = (period_interval[1] - period_interval[0]).days + 1
        if partial_is_gap and private_health_partial_text(period):
            gaps.append(f"confirm partial-year {label}")
    for interval in (explicit_interval, period_interval):
        if interval is None or income_year_bounds is None:
            continue
        if interval[0] < income_year_bounds[0] or interval[1] > income_year_bounds[1]:
            gaps.append(f"{label} dates are outside requested income year {private_health_raw_text(income_year)}")
    if not is_missing(days):
        parsed_days = private_health_day_count(days)
        if parsed_days is None:
            gaps.append(f"confirm {label} days ({private_health_raw_text(days)})")
        elif parsed_days > income_year_days:
            gaps.append(f"{label} days exceed requested income year ({parsed_days} > {income_year_days})")
        elif span_days is not None and parsed_days != span_days:
            gaps.append(f"reconcile {label} dates ({span_days} days) with supplied days ({parsed_days})")
        elif partial_is_gap and 0 < parsed_days < income_year_days:
            gaps.append(f"confirm partial-year {label} ({parsed_days} days)")
    return private_health_unique_text(gaps)


def private_health_statement_collection_gaps(
    overview: Dict[str, Any],
    statements: List[Dict[str, Any]],
) -> List[str]:
    if not statements:
        return []
    intervals: List[tuple[date, date]] = []
    day_counts: List[int] = []
    for item in statements:
        interval = private_health_record_interval(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES)
        if interval is not None:
            intervals.append(interval)
        days = private_health_day_count(
            normalized_item_field(item, PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES["days_covered"])
        )
        if days is not None:
            day_counts.append(days)
    overview_interval = private_health_record_interval(overview, PRIVATE_HEALTH_FIELD_ALIASES)
    overview_days = private_health_day_count(
        normalized_item_field(overview, PRIVATE_HEALTH_FIELD_ALIASES["days_covered"])
    )
    expected_days = (
        (overview_interval[1] - overview_interval[0]).days + 1
        if overview_interval is not None
        else overview_days
    )
    income_year_days = private_health_income_year_day_limit(overview)
    if intervals:
        if len(intervals) != len(statements):
            return ["reconcile statement-line cover periods with the private hospital cover period"]
        relationship_gap = private_health_interval_relationship_gap(intervals)
        if relationship_gap:
            return [relationship_gap]
        union_days = private_health_interval_days(intervals)
        if overview_interval is not None:
            first = min(start for start, _ in intervals)
            last = max(end for _, end in intervals)
            if last < overview_interval[0] or first > overview_interval[1]:
                return ["statement-line dates are outside the supplied income year"]
            if first < overview_interval[0] or last > overview_interval[1]:
                return ["statement-line dates fall outside the overview private hospital cover period"]
            if first != overview_interval[0] or last != overview_interval[1]:
                return ["reconcile statement-line dates with the supplied private hospital cover period"]
        if expected_days is not None and union_days != expected_days:
            return ["reconcile statement-line cover periods with the private hospital cover period"]
        if expected_days is None and union_days != income_year_days:
            return ["reconcile statement-line cover periods with the private hospital cover period"]
        return []
    if day_counts:
        total_days = sum(day_counts)
        target_days = expected_days if expected_days is not None else income_year_days
        if total_days != target_days:
            return ["reconcile statement-line cover days with the private hospital cover period"]
    return []


def private_health_interval_relationship_gap(intervals: List[tuple[date, date]]) -> str:
    ordered = sorted(intervals)
    previous_end: Optional[date] = None
    for start, end in ordered:
        if previous_end is not None:
            if start <= previous_end:
                return "statement-line cover periods overlap"
            if start > previous_end + timedelta(days=1):
                return "statement-line cover periods have a gap"
        previous_end = max(previous_end, end) if previous_end is not None else end
    return ""


def private_health_record_interval(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Optional[tuple[date, date]]:
    start = normalized_item_field(raw, field_aliases["period_start"])
    end = normalized_item_field(raw, field_aliases["period_end"])
    if is_missing(start) or is_missing(end):
        return private_health_period_interval(
            normalized_item_field(raw, field_aliases["period"]),
            raw.get("_income_year"),
        )
    start_date = parse_iso_date(start)
    end_date = parse_iso_date(end)
    if start_date is None or end_date is None or start_date > end_date:
        return None
    return start_date, end_date


def private_health_income_year_bounds(value: Any) -> Optional[tuple[date, date]]:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace("–", "-").replace("—", "-")
    match = re.fullmatch(r"(20\d{2})\s*[-/]\s*(\d{2}|20\d{2})", normalized)
    if match is None:
        return None
    start_year = int(match.group(1))
    end_text = match.group(2)
    end_year = int(end_text) if len(end_text) == 4 else (start_year // 100) * 100 + int(end_text)
    if end_year != start_year + 1:
        return None
    return date(start_year, 7, 1), date(end_year, 6, 30)


def private_health_income_year_day_limit(raw: Any) -> int:
    income_year = raw.get("_income_year") if isinstance(raw, dict) else raw
    bounds = private_health_income_year_bounds(income_year)
    return (bounds[1] - bounds[0]).days + 1 if bounds is not None else 366


def private_health_period_interval(
    value: Any,
    income_year: Any,
) -> Optional[tuple[date, date]]:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    interval = private_health_parse_text_period(normalized)
    if interval is not None:
        return interval
    interval = private_health_income_year_bounds(normalized)
    if interval is not None:
        return interval
    if normalized in PRIVATE_HEALTH_FULL_YEAR_VALUES:
        return private_health_income_year_bounds(income_year)
    return None


def private_health_interval_days(intervals: List[tuple[date, date]]) -> int:
    total = 0
    current_start: Optional[date] = None
    current_end: Optional[date] = None
    for start, end in sorted(intervals):
        if current_start is None or current_end is None:
            current_start, current_end = start, end
        elif start <= current_end + timedelta(days=1):
            current_end = max(current_end, end)
        else:
            total += (current_end - current_start).days + 1
            current_start, current_end = start, end
    if current_start is not None and current_end is not None:
        total += (current_end - current_start).days + 1
    return total


def private_health_period_value_supported(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    if private_health_partial_text(normalized):
        return True
    if normalized in PRIVATE_HEALTH_FULL_YEAR_VALUES:
        return True
    if private_health_income_year_bounds(normalized) is not None:
        return True
    return private_health_parse_text_period(normalized) is not None


def private_health_parse_text_period(value: str) -> Optional[tuple[date, date]]:
    parts = re.split(r"\s+(?:to|through|until)\s+", value.strip(), maxsplit=1)
    if len(parts) != 2:
        return None
    start = private_health_parse_period_endpoint(parts[0], end=False)
    end = private_health_parse_period_endpoint(parts[1], end=True)
    if start is None or end is None or start > end:
        return None
    return start, end


def private_health_parse_period_endpoint(value: str, *, end: bool) -> Optional[date]:
    value = value.strip()
    parsed = parse_iso_date(value)
    if parsed is not None:
        return parsed
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    for fmt in ("%B %Y", "%b %Y"):
        try:
            parsed_month = datetime.strptime(value, fmt).date()
        except ValueError:
            continue
        day = calendar.monthrange(parsed_month.year, parsed_month.month)[1] if end else 1
        return date(parsed_month.year, parsed_month.month, day)
    return None


def private_health_record_has_field_inputs(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
    excluded: set[str],
) -> bool:
    raw = private_health_filter_record_values(raw, field_aliases)
    for field, aliases in field_aliases.items():
        if field in excluded or field in {"notes", "source_urls", "checked_at"}:
            continue
        value = normalized_item_field(raw, aliases)
        if private_health_substantive_value(value, false_is_value=True):
            return True
    return False


def private_health_mls_tier_valid(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    parsed = private_health_nonnegative_integer(value)
    if parsed is not None:
        return parsed <= 3
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    if normalized in {"base", "base tier"} or re.fullmatch(r"tier\s*[0-3]", normalized):
        return True
    return "review" in normalized and any(term in normalized for term in ("income", "supplied", "threshold"))


def private_health_dependant_type_valid(value: Any) -> bool:
    if not isinstance(value, str) or contains_unknown(value):
        return False
    normalized = re.sub(r"[^a-z]+", " ", value.lower()).strip()
    return any(term in normalized.split() for term in ("child", "student", "dependant", "dependent"))


def private_health_shared_care_valid(value: Any) -> bool:
    if private_health_flag_bool(value) is not None:
        return True
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        parsed = float(str(value).strip().rstrip("%"))
    except ValueError:
        parsed = math.nan
    if math.isfinite(parsed):
        return 0 <= parsed <= 100
    normalized = re.sub(r"[^a-z]+", " ", str(value).lower()).strip()
    return "shared care" in normalized


def private_health_partial_period(raw: Dict[str, Any], field_aliases: Dict[str, tuple[str, ...]]) -> bool:
    period = normalized_item_field(raw, field_aliases["period"])
    if private_health_partial_text(period):
        return True
    days_alias = "days_covered" if "days_covered" in field_aliases else "hospital_cover_days"
    days = normalized_item_field(raw, field_aliases[days_alias]) if days_alias in field_aliases else None
    parsed_days = private_health_day_count(days)
    return parsed_days is not None and 0 < parsed_days < private_health_income_year_day_limit(raw)


def private_health_partial_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    patterns = (
        r"\bpartial(?:ly)?\b",
        r"\bpart\s+(?:of\s+(?:the\s+)?)?(?:income\s+)?year\b",
        r"\bsome(?:\s+but\s+not\s+all)?\s+of\s+(?:the\s+)?(?:income\s+)?year\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def private_health_negated_partial_cover_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    partial_state = r"(?:mixed|partial(?:ly)?|part\s+year|intermittent(?:ly)?)"
    cover = r"(?:insurance|cover|coverage|covered|policy)"
    return bool(
        re.search(
            rf"\b(?:no|not|without|never|wasn\s+t|weren\s+t)\s+(?:any\s+|a\s+)?{partial_state}\b",
            normalized,
        )
        or re.search(
            rf"\b{cover}\b(?:\s+\w+){{0,3}}\s+\b(?:not|never|wasn\s+t|weren\s+t)\s+{partial_state}\b",
            normalized,
        )
    )


def private_health_continuous_cover_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if re.search(
        r"\b(?:not|was\s+not|were\s+not|wasn\s+t|weren\s+t)\s+"
        r"(?:continuous(?:ly)?|uninterrupted)\b",
        normalized,
    ):
        return False
    cover = r"(?:insurance|cover|coverage|covered|policy)"
    interruption = r"(?:gaps?|breaks?|interruptions?|interrupted|lapses?|lapsed)"
    negated_absence = (
        r"(?:not|never|(?:do|does|did|have|has|had|is|was|were)\s+not|"
        r"(?:don|doesn|didn|haven|hasn|hadn|isn|wasn|weren)\s+t)"
    )
    return bool(
        re.search(
            rf"\b{negated_absence}\s+(?:been\s+)?uninsured\b",
            normalized,
        )
        or re.search(
            rf"\b{negated_absence}\s+(?:been\s+|(?:go|went)\s+)?without"
            rf"(?:\s+\w+){{0,4}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:no|not\s+(?:a\s+single|one)|zero)\s+"
            rf"(?:day|week|month|period|time)\s+without"
            rf"(?:\s+\w+){{0,4}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b{negated_absence}\s+(?:ever\s+)?lack(?:ed|ing)?"
            rf"(?:\s+\w+){{0,4}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:no|without|not|wasn\s+t|weren\s+t)\s+(?:(?:any|a|a\s+single|single)\s+)?{interruption}\b"
            rf"(?:\s+\w+){{0,5}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b{cover}\b(?:\s+\w+){{0,5}}\s+"
            rf"\b(?:(?:with\s+)?(?:no|without)\s+(?:any\s+)?{interruption}|"
            rf"never\s+lapsed|did\s+not\s+lapse|didn\s+t\s+lapse|"
            rf"did\s+not\s+have\s+(?:any\s+)?{interruption}|did\s+not\s+break|"
            rf"never\s+had\s+(?:a\s+)?{interruption}|had\s+zero\s+{interruption}|"
            rf"without\s+(?:a\s+)?{interruption}|was\s+(?:not|never)\s+{interruption})\b",
            normalized,
        )
        or re.search(
            rf"\b{cover}\b(?:\s+\w+){{0,4}}\s+"
            rf"\b(?:(?:do|does|did|have|has|had|is|was|were)\s+not|"
            rf"(?:don|doesn|didn|haven|hasn|hadn|isn|wasn|weren)\s+t)\s+"
            rf"(?:(?:have|had|been)\s+)?(?:(?:any|a\s+single|one)\s+)?{interruption}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:never\s+lapsed|did\s+not\s+lapse|didn\s+t\s+lapse)\b"
            rf"(?:\s+\w+){{0,5}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:never\s+(?:had\s+)?(?:a\s+)?|had\s+zero\s+|not\s+a\s+single\s+)"
            rf"{interruption}\b(?:\s+\w+){{0,5}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:not|was\s+not|were\s+not|wasn\s+t|weren\s+t)\s+on\s+and\s+off\b"
            rf"(?:\s+\w+){{0,5}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b{cover}\b(?:\s+\w+){{0,4}}\s+"
            rf"\b(?:not|was\s+not|were\s+not|wasn\s+t|weren\s+t)\s+on\s+and\s+off\b",
            normalized,
        )
        or re.search(
            rf"\b(?:continuous(?:ly)?|uninterrupted)\b(?:\s+\w+){{0,4}}\s+\b{cover}\b",
            normalized,
        )
        or re.search(
            rf"\b{cover}\b(?:\s+\w+){{0,4}}\s+\b(?:continuous(?:ly)?|uninterrupted)\b",
            normalized,
        )
    )


def private_health_cover_duration_status(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if not re.search(
        r"\b(?:insurance|cover|coverage|covered|insured|uninsured)\b",
        normalized,
    ):
        return None
    words = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }
    amount = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d{1,4})"
    claim_context = bool(
        re.search(
            r"\b(?:covered|insured)\b"
            r"|\b(?:had|have|has|no|not|without|never)\b(?:\s+\w+){0,4}\s+"
            r"\b(?:insurance|cover|coverage)\b",
            normalized,
        )
    )
    ratio = re.search(
        rf"\b(?P<numerator>{amount})\s+(?:of|out\s+of)\s+"
        rf"(?P<denominator>{amount})\s+months?\b",
        normalized,
    )
    if ratio and claim_context:
        numerator_text = ratio.group("numerator")
        denominator_text = ratio.group("denominator")
        numerator = words.get(
            numerator_text,
            int(numerator_text) if numerator_text.isdigit() else 0,
        )
        denominator = words.get(
            denominator_text,
            int(denominator_text) if denominator_text.isdigit() else 0,
        )
        return "partial" if 0 < numerator < denominator else "invalid"
    if claim_context and re.search(
        r"\b(?:less\s+than|under|nearly|almost|at\s+most)\s+(?:12|twelve)\s+months?\b",
        normalized,
    ):
        return "partial"
    if claim_context and re.search(
        r"\b(?:more\s+than|over|at\s+least)\s+(?:12|twelve)\s+months?\b"
        r"|\bbetween\s+\d{1,2}\s+and\s+\d{1,2}\s+months?\b"
        r"|\b\d{1,2}\s+to\s+\d{1,2}\s+months?\b",
        normalized,
    ):
        return "invalid"
    duration_token = rf"(?P<amount>{amount})\s+(?P<unit>days?|weeks?|months?)"
    duration = None
    for pattern in (
        rf"\b(?:covered|insured)\b(?:\s+\w+){{0,2}}\s+(?:for\s+)?(?:only\s+)?{duration_token}\b",
        rf"\b(?:no|without)\s+(?:(?:private|hospital|health)\s+)?(?:insurance|cover|coverage)\b"
        rf"(?:\s+\w+){{0,2}}\s+(?:for|during)\s+{duration_token}\b",
        rf"\b(?:have|had|has|did\s+not\s+have|didn\s+t\s+have)\b"
        rf"(?:\s+\w+){{0,4}}\s+\b(?:insurance|cover|coverage)\b"
        rf"(?:\s+\w+){{0,2}}\s+(?:for|during)\s+{duration_token}\b",
        rf"\b(?:insurance|cover|coverage|policy)\b\s+(?:for|during)\s+{duration_token}\b",
    ):
        duration = re.search(pattern, normalized)
        if duration:
            break
    if duration is None:
        return None
    amount_text = duration.group("amount")
    amount = words.get(amount_text, int(amount_text) if amount_text.isdigit() else 0)
    unit = duration.group("unit")
    limit = 12 if unit.startswith("month") else 52 if unit.startswith("week") else 365
    if amount <= 0 or amount > limit:
        return "invalid"
    return "full" if amount == limit else "partial"


def private_health_partial_cover_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if private_health_negated_partial_cover_text(normalized):
        return False
    if private_health_epistemic_uncertainty_text(normalized):
        return False
    duration_status = private_health_cover_duration_status(normalized)
    if duration_status is not None:
        return duration_status == "partial"
    if private_health_continuous_cover_text(normalized):
        return False
    if private_health_qualified_period_text(normalized):
        return True
    patterns = (
        r"\bmixed\s+(?:hospital\s+|health\s+)?cover(?:age)?\b",
        r"\bon\s+and\s+off\b",
        r"\bintermittent(?:ly)?\b.*\b(?:cover|coverage|covered|policy)\b",
        r"\b(?:gaps?|breaks?|interruptions?|lapses?)\b.*\b(?:cover|coverage|covered|policy)\b",
        r"\b(?:cover|coverage|covered|policy)\b.*\b(?:gaps?|breaks?|interruptions?|lapses?|lapsed)\b",
        r"\b(?:cover|coverage|policy)\b.*\b(?:started|ended|lapsed|expired)\b.*\b(?:mid\s+year|during\s+(?:the\s+)?year)\b",
        r"\b(?:first|second|only)?\s*half\s+of\s+(?:the\s+)?(?:income\s+)?year\b",
        r"\bmost\s+of\s+(?:the\s+)?(?:income\s+)?year\b",
        r"\bnot\s+(?:covered\s+)?(?:for\s+)?(?:the\s+)?(?:(?:full|whole|entire)(?:\s+of)?\s+(?:the\s+)?(?:income\s+)?year|all(?:\s+of)?\s+(?:the\s+)?(?:income\s+)?year)\b",
        r"\b(?:(?:full|whole|entire)(?:\s+of)?\s+(?:the\s+)?(?:income\s+)?year|all(?:\s+of)?\s+(?:the\s+)?(?:income\s+)?year)\s+(?:except|excluding|apart\s+from|but)\b",
        r"\ball\s+but\b",
        r"\bcovered\s+(?:for\s+)?(?:only\s+)?(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven)\s+months?\b",
    )
    if any(re.search(pattern, normalized) for pattern in patterns):
        return True
    months = re.search(
        r"\bcovered\s+(?:for\s+)?(?:only\s+)?(\d{1,2})\s+months?\b",
        normalized,
    )
    return months is not None and 0 < int(months.group(1)) < 12


def private_health_record_gaps(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> List[str]:
    gaps: List[str] = []
    conflicts = private_health_record_conflicts(raw, field_aliases)
    if conflicts:
        gaps.append(f"resolve alias conflict: {conflicts}")
    unknown = private_health_unknown_values(raw, private_health_alias_set(field_aliases))
    if unknown:
        gaps.append(f"review supplemental facts {display_value(unknown)}")
    return gaps


def private_health_record_conflicts(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> str:
    return "; ".join(private_health_record_conflict_values(raw, field_aliases))


def private_health_record_conflict_values(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> List[str]:
    conflict_aliases = {
        field: aliases
        for field, aliases in field_aliases.items()
        if field != "source_urls"
    }
    details = item_alias_conflict_details(raw, conflict_aliases)
    source_conflicts = raw.get("_source_conflicts")
    if isinstance(source_conflicts, list):
        details.extend(display_value(value) for value in source_conflicts if display_value(value))
    return private_health_unique_text(details)


def private_health_supplemental_handoff_facts(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> List[Dict[str, Any]]:
    filtered = private_health_filter_record_values(raw, field_aliases)
    facts: List[Dict[str, Any]] = []
    notes = normalized_item_field(filtered, field_aliases.get("notes", ()))
    facts.extend(
        atomic_handoff_facts(
            "supplemental-note",
            "Supplemental note",
            notes,
            action_kind="destination-requires-review",
        )
    )
    unknown = private_health_unknown_values(
        filtered,
        private_health_alias_set(field_aliases),
    )
    facts.extend(
        atomic_handoff_facts(
            "supplemental-fact",
            "Supplemental fact",
            unknown,
            action_kind="destination-requires-review",
        )
    )
    facts.extend(
        atomic_handoff_facts(
            "supplied-source-url",
            "Supplied source URL",
            private_health_provenance_urls(filtered),
            action_kind="retain-evidence",
        )
    )
    facts.extend(
        atomic_handoff_facts(
            "supplied-checked-at",
            "Supplied checked at",
            private_health_alias_values(filtered, field_aliases.get("checked_at", ())),
            action_kind="retain-evidence",
        )
    )
    facts.extend(
        atomic_handoff_facts(
            "source-conflict",
            "Source or alias conflict",
            private_health_record_conflict_values(filtered, field_aliases),
            action_kind="destination-requires-review",
        )
    )
    return facts


def private_health_row_checked_at(
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> Optional[str]:
    filtered = private_health_filter_record_values(raw, field_aliases)
    values = private_health_alias_values(filtered, field_aliases.get("checked_at", ()))
    valid = private_health_valid_checked_at_values(values)
    return valid[0] if valid else None


def private_health_append_record_details(
    answer: str,
    raw: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> str:
    raw = private_health_filter_record_values(raw, field_aliases)
    parts: List[str] = []
    notes = normalized_item_field(raw, field_aliases.get("notes", ()))
    if private_health_freeform_value(notes):
        parts.append(f"notes {display_value(notes)}")
    source_urls = normalized_item_field(raw, field_aliases.get("source_urls", ()))
    if private_health_substantive_value(source_urls, false_is_value=False):
        parts.append(f"supplied source URLs {display_value(source_urls)}")
    checked_at = private_health_alias_values(raw, field_aliases.get("checked_at", ()))
    if checked_at:
        parts.append(f"supplied checked at {display_value(checked_at)}")
    unknown = private_health_unknown_values(raw, private_health_alias_set(field_aliases))
    if unknown:
        parts.append(f"supplemental facts {display_value(unknown)}")
    conflicts = private_health_record_conflicts(raw, field_aliases)
    if conflicts:
        parts.append(f"alias conflicts {conflicts}")
    return f"{answer}; {'; '.join(parts)}" if parts else answer


def private_health_alias_values(raw: Dict[str, Any], aliases: tuple[str, ...]) -> List[Any]:
    values: List[Any] = []
    for alias in aliases:
        if alias not in raw or is_missing(raw[alias]):
            continue
        values.extend(private_health_recursive_scalar_values(raw[alias]))
    return private_health_unique_values(values)


def private_health_recursive_scalar_values(value: Any) -> List[Any]:
    if isinstance(value, list):
        values: List[Any] = []
        for item in value:
            values.extend(private_health_recursive_scalar_values(item))
        return values
    if isinstance(value, dict):
        values: List[Any] = []
        for item in value.values():
            values.extend(private_health_recursive_scalar_values(item))
        return values
    sanitized = private_health_sanitized_value(value, false_is_value=False)
    return [] if sanitized is PRIVATE_HEALTH_NO_VALUE else [sanitized]


def private_health_recursive_urls(value: Any) -> List[str]:
    if isinstance(value, str):
        value = value.strip()
        return [value] if value.startswith(("https://", "http://")) else []
    if isinstance(value, list):
        urls: List[str] = []
        for item in value:
            urls.extend(private_health_recursive_urls(item))
        return urls
    if isinstance(value, dict):
        urls: List[str] = []
        for item in value.values():
            urls.extend(private_health_recursive_urls(item))
        return urls
    return []


def private_health_valid_checked_at_values(value: Any) -> List[str]:
    values = private_health_recursive_scalar_values(value)
    return private_health_unique_text(
        [
            item
            for item in values
            if isinstance(item, str)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", item.strip())
            and parse_iso_date(item.strip()) is not None
        ]
    )


def private_health_invalid_source_values(value: Any) -> List[Any]:
    valid = set(private_health_recursive_urls(value))
    return private_health_unique_values(
        [
            item
            for item in private_health_recursive_scalar_values(value)
            if not (isinstance(item, str) and item.strip() in valid)
        ]
    )


def private_health_invalid_checked_at_values(value: Any) -> List[Any]:
    valid = set(private_health_valid_checked_at_values(value))
    return private_health_unique_values(
        [
            item
            for item in private_health_recursive_scalar_values(value)
            if not (isinstance(item, str) and item.strip() in valid)
        ]
    )


def private_health_record_metadata(
    record: Dict[str, Any],
    source_aliases: set[str],
    checked_at_aliases: set[str],
) -> Dict[str, Any]:
    source_urls: List[str] = []
    checked_at: List[Any] = []
    for key, value in record.items():
        if key in source_aliases:
            source_urls.extend(private_health_recursive_urls(value))
        elif key in checked_at_aliases:
            checked_at.extend(private_health_valid_checked_at_values(value))
    metadata: Dict[str, Any] = {}
    if source_urls:
        metadata["source_urls"] = list(dict.fromkeys(source_urls))
    if checked_at:
        metadata["checked_at"] = private_health_unique_values(checked_at)
    return metadata


def private_health_mls_inherited_conflicts(record: Dict[str, Any]) -> List[str]:
    field_aliases = private_health_mls_inherited_aliases()
    conflicts = item_alias_conflict_details(record, field_aliases)
    inherited_aliases = private_health_alias_set(
        {
            field: aliases
            for field, aliases in field_aliases.items()
            if field not in {"source_urls", "checked_at"}
        }
    )
    for conflict in private_health_recursive_scalar_values(
        record.get("_source_conflicts")
    ):
        if str(conflict).split(maxsplit=1)[0] in inherited_aliases:
            conflicts.append(str(conflict))
    return private_health_unique_text(conflicts)


def private_health_capture_cover_lineage(
    record: Dict[str, Any],
    supplied_records: Optional[List[Dict[str, Any]]] = None,
) -> None:
    field_aliases = private_health_mls_inherited_aliases()
    eligible_supplied = [
        supplied
        for supplied in (supplied_records or [record])
        if private_health_mls_inherited_cover_has_inputs(supplied)
    ]
    eligible = [
        private_health_alias_subset(supplied, field_aliases)
        for supplied in eligible_supplied
    ]
    source_urls: List[str] = []
    checked_at: List[Any] = []
    inherited_conflicts: List[str] = []
    for supplied in eligible_supplied:
        source_urls.extend(
            private_health_recursive_urls(supplied["_cover_source_urls"])
            if "_cover_source_urls" in supplied
            else private_health_provenance_urls(supplied)
        )
        checked_at.extend(
            private_health_recursive_scalar_values(supplied["_cover_checked_at"])
            if "_cover_checked_at" in supplied
            else private_health_valid_checked_at_values(
                {
                    key: supplied[key]
                    for key in PRIVATE_HEALTH_FIELD_ALIASES["checked_at"]
                    if key in supplied
                }
            )
        )
        inherited_conflicts.extend(
            str(value)
            for value in private_health_recursive_scalar_values(
                supplied.get("_cover_source_conflicts")
            )
        )
        inherited_conflicts.extend(private_health_mls_inherited_conflicts(supplied))
    merged = private_health_merge_records(eligible, field_aliases)
    record["_cover_source_urls"] = list(dict.fromkeys(source_urls))
    record["_cover_checked_at"] = private_health_unique_values(checked_at)
    record["_cover_source_conflicts"] = private_health_unique_text(
        [
            *inherited_conflicts,
            *private_health_mls_inherited_conflicts(merged),
        ]
    )


def private_health_add_metadata(
    record: Dict[str, Any],
    metadata: Dict[str, Any],
    field_aliases: Dict[str, tuple[str, ...]],
) -> None:
    source_urls = [
        *private_health_provenance_urls(record),
        *private_health_recursive_urls(metadata.get("source_urls")),
    ]
    if source_urls:
        record["source_urls"] = list(dict.fromkeys(source_urls))
    checked_at = [
        *private_health_alias_values(record, field_aliases.get("checked_at", ())),
        *private_health_recursive_scalar_values(metadata.get("checked_at")),
    ]
    if checked_at:
        values = private_health_unique_values(checked_at)
        record["checked_at"] = values[0] if len(values) == 1 else values


def private_health_row_sources(raw: Any, official_sources: List[str]) -> List[str]:
    sources = list(official_sources)
    if isinstance(raw, dict):
        sources.extend(private_health_provenance_urls(raw))
    return list(dict.fromkeys(sources))


def private_health_provenance_urls(raw: Dict[str, Any]) -> List[str]:
    aliases: List[str] = []
    for field_aliases in (
        PRIVATE_HEALTH_FIELD_ALIASES,
        PRIVATE_HEALTH_STATEMENT_FIELD_ALIASES,
        MEDICARE_LEVY_FIELD_ALIASES,
        MLS_FIELD_ALIASES,
        SPOUSE_FIELD_ALIASES,
        DEPENDANT_SUMMARY_FIELD_ALIASES,
        DEPENDANT_FIELD_ALIASES,
    ):
        aliases.extend(field_aliases.get("source_urls", ()))
    sources: List[str] = []
    for key in dict.fromkeys(aliases):
        if key not in raw:
            continue
        sources.extend(private_health_recursive_urls(raw[key]))
    return list(dict.fromkeys(sources))


def private_health_field_text(raw: Dict[str, Any], aliases: tuple[str, ...]) -> str:
    return private_health_raw_text(normalized_item_field(raw, aliases))


def private_health_amount_field_text(raw: Dict[str, Any], aliases: tuple[str, ...]) -> str:
    return private_health_amount_text(normalized_item_field(raw, aliases))


def private_health_bool_field_text(raw: Dict[str, Any], aliases: tuple[str, ...]) -> str:
    return private_health_bool_text(normalized_item_field(raw, aliases))


def private_health_raw_text(value: Any) -> str:
    return display_value(value) if not is_missing(value) else "unknown"


def private_health_amount_text(value: Any) -> str:
    amount = safe_money_value(value)
    return f"{amount:.2f}" if amount is not None else private_health_raw_text(value)


def private_health_period_text(raw: Dict[str, Any], field_aliases: Dict[str, tuple[str, ...]]) -> str:
    period = normalized_item_field(raw, field_aliases["period"])
    start = normalized_item_field(raw, field_aliases["period_start"])
    end = normalized_item_field(raw, field_aliases["period_end"])
    if not is_missing(start) or not is_missing(end):
        return f"{private_health_raw_text(start)} to {private_health_raw_text(end)}"
    return private_health_raw_text(period)


def private_health_bool_text(value: Any) -> str:
    parsed = private_health_flag_bool(value)
    if parsed is True:
        return "true"
    if parsed is False:
        return "false"
    return private_health_raw_text(value)


def private_health_cover_bool(value: Any) -> Optional[bool]:
    if contains_unknown(value):
        return None
    parsed = phone_bool(value)
    if parsed is not None:
        return parsed
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    cover = (
        r"(?:private\s+)?(?:(?:hospital|health)\s+)?"
        r"(?:insurance|cover|coverage|covered|policy|insured|uninsured)"
    )
    if private_health_epistemic_uncertainty_text(normalized):
        return None
    if private_health_negated_partial_cover_text(normalized):
        return None
    duration_status = private_health_cover_duration_status(normalized)
    if duration_status == "invalid":
        return None
    if duration_status == "partial":
        return True
    if private_health_continuous_cover_text(normalized):
        return True
    if private_health_partial_cover_text(normalized):
        return True
    negative = r"(?:no|not|without|never|didn\s+t|don\s+t|doesn\s+t|haven\s+t|hasn\s+t|hadn\s+t)"
    if re.search(rf"\b{negative}\b(?:\s+\w+){{0,5}}\s+\b{cover}\b", normalized):
        return False
    if re.search(r"\buninsured\b", normalized):
        return False
    if private_health_full_income_year_range_text(normalized):
        return True
    if duration_status == "full":
        return True
    full_year = (
        r"(?:(?:full|whole|entire)(?:\s+of)?\s+(?:the\s+)?(?:income\s+)?year|"
        r"all(?:\s+of)?\s+(?:the\s+)?(?:income\s+)?year|"
        r"throughout\s+(?:the\s+)?(?:income\s+)?year)"
    )
    if re.search(
        rf"\b{cover}\b(?:\s+\w+){{0,3}}\s+\b{full_year}\b",
        normalized,
    ) or re.search(
        rf"\b{full_year}\b(?:\s+\w+){{0,3}}\s+\b{cover}\b",
        normalized,
    ):
        return True
    if re.search(rf"\b(have|had|has|with|yes|full|appropriate)\b(?:\s+\w+){{0,4}}\s+\b{cover}\b", normalized):
        return True
    return None


def private_health_spouse_bool(value: Any) -> Optional[bool]:
    if contains_unknown(value):
        return None
    parsed = phone_bool(value)
    if parsed is not None:
        return parsed
    if not isinstance(value, str):
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if private_health_negated_spouse_absence_text(normalized):
        return True
    if re.search(r"\b(spouse|partner)\b", normalized) and (
        private_health_epistemic_uncertainty_text(normalized)
        or private_health_qualified_period_text(normalized)
        or re.search(r"\b(no longer|separated)\b", normalized)
    ):
        return None
    negative = r"(?:no|not|without|never|didn\s+t|don\s+t|doesn\s+t|haven\s+t|hasn\s+t|hadn\s+t)"
    if re.search(rf"\b{negative}\b(?:\s+\w+){{0,5}}\s+\b(spouse|partner)\b", normalized):
        return False
    if private_health_full_income_year_range_text(normalized):
        return True
    if re.search(
        r"\b(spouse|partner)\b(?:\s+\w+){0,3}\s+"
        r"\b(?:(?:for\s+)?(?:the\s+)?(?:full|whole|entire)\s+(?:income\s+)?year|"
        r"all\s+(?:the\s+)?(?:income\s+)?year|"
        r"throughout\s+(?:the\s+)?(?:income\s+)?year)\b",
        normalized,
    ):
        return True
    if re.search(r"\b(have|had|has|with|yes)\b(?:\s+\w+){0,3}\s+\b(spouse|partner)\b", normalized):
        return True
    return None


def private_health_negated_spouse_absence_text(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    spouse = r"(?:a\s+)?(?:spouse|partner)"
    negated_absence = (
        r"(?:not|never|(?:do|does|did|have|has|had|is|was|were)\s+not|"
        r"(?:don|doesn|didn|haven|hasn|hadn|isn|wasn|weren)\s+t)"
    )
    return bool(
        re.search(
            rf"\b{negated_absence}\s+(?:been\s+|(?:go|went)\s+)?without"
            rf"(?:\s+\w+){{0,2}}\s+\b{spouse}\b",
            normalized,
        )
        or re.search(
            rf"\b(?:no|not\s+(?:a\s+single|one)|zero)\s+"
            rf"(?:day|week|month|period|time)\s+without"
            rf"(?:\s+\w+){{0,2}}\s+\b{spouse}\b",
            normalized,
        )
        or re.search(
            rf"\b{negated_absence}\s+(?:ever\s+)?lack(?:ed|ing)?"
            rf"(?:\s+\w+){{0,2}}\s+\b{spouse}\b",
            normalized,
        )
    )


def private_health_flag_bool(value: Any) -> Optional[bool]:
    if contains_unknown(value):
        return None
    return phone_bool(value)


def private_health_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return True
    amount = safe_money_value(value)
    return amount is None or amount < 0


def private_health_day_count(value: Any) -> Optional[int]:
    parsed = private_health_nonnegative_integer(value)
    if parsed is None or parsed > 366:
        return None
    return parsed


def private_health_nonnegative_integer(value: Any) -> Optional[int]:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return None
    try:
        parsed = float(str(value).strip())
    except ValueError:
        return None
    if not math.isfinite(parsed) or parsed < 0 or not parsed.is_integer():
        return None
    return int(parsed)


def private_health_benefit_code_valid(value: Any) -> bool:
    if is_missing(value) or contains_unknown(value) or isinstance(value, bool):
        return False
    return str(value).strip() in PRIVATE_HEALTH_SUPPORTED_BENEFIT_CODES


def private_health_tax_claim_code_valid(value: Any) -> bool:
    if is_missing(value) or contains_unknown(value) or isinstance(value, bool):
        return False
    return str(value).strip().upper() in {"A", "B", "C", "D", "E", "F"}


def private_health_field_missing(raw: Dict[str, Any], aliases: tuple[str, ...]) -> bool:
    value = normalized_item_field(raw, aliases)
    return is_missing(value) or contains_unknown(value)


def private_health_review_tab(subject: str, gaps: List[str]) -> str:
    if gaps:
        return f"{subject} stays accountant review and needs {', '.join(gaps)}."
    return f"{subject} stays source-backed accountant review; no levy, surcharge, or rebate is calculated."


def private_health_unique_text(values: List[str]) -> List[str]:
    return list(dict.fromkeys(value for value in values if value))


def deduction_rows(items: List[Dict[str, Any]], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not has_meaningful_value(item):
            continue
        kind = deduction_kind(item)
        amount = nonnegative_money_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["amount"]))
        gaps = deduction_review_terms(item, kind)
        rows.append(
            guide_row(
                f"DED-{index}",
                deduction_ato_area(kind),
                deduction_question(item, kind),
                deduction_answer_text(item, kind, amount),
                "Itemized deduction rows are prep-only. Evidence, reimbursement, employer-paid/provided, private-use, GST/BAS, duplicate-risk, and source-support checks must be resolved before entry.",
                "Accountant review",
                deduction_sources(kind, item, answers),
                tab_text=deduction_tab_text(kind, gaps),
                row_kind="deduction",
                facts=handoff_facts(
                    ("deduction-type", "Deduction type", DEDUCTION_KIND_LABELS.get(kind, "Unsupported or other deduction")),
                    ("description", "Description", deduction_question(item, kind)),
                    ("amount", "Amount supplied", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["amount"])),
                    ("evidence", "Evidence", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["evidence"])),
                    ("reimbursed", "Reimbursed", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["reimbursed"])),
                    ("employer-paid", "Employer paid", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["employer_paid"])),
                    ("employer-provided", "Employer provided", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["employer_provided"])),
                    ("work-use", "Work-use percentage", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["work_use_percent"])),
                    ("private-use", "Private-use percentage", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["private_use_percent"])),
                    ("work-private-split", "Work/private split", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["work_private_split"])),
                    ("gst-bas", "GST or BAS interaction", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["gst_bas_interaction"])),
                    ("duplicate-risk", "Duplicate-risk signal", normalized_item_field(item, DEDUCTION_FIELD_ALIASES["duplicate_risk"])),
                    ("alias-conflicts", "Alias conflicts", item_alias_conflict_text(item, DEDUCTION_FIELD_ALIASES) or "none"),
                ),
            )
        )
    return rows


def deduction_kind(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("kind", "label"):
        value = normalized_item_field(item, DEDUCTION_FIELD_ALIASES[key])
        if value is not None:
            parts.append(display_value(value))
    raw = " ".join(parts).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", raw).strip()
    tokens = set(normalized.split())
    if any(term in normalized for term in ("gift", "donation", "donations", "deductible gift recipient", "dgr")):
        return "gift"
    if any(term in normalized for term in ("tax agent", "managing tax", "tax affairs", "accountant fee", "accounting fee")):
        return "tax_affairs"
    if "income protection" in normalized or ("insurance" in normalized and "income" in normalized):
        return "income_protection"
    if any(term in normalized for term in ("self education", "self-education", "education", "training", "seminar", "course")):
        return "self_education"
    if any(term in normalized for term in ("tool", "equipment", "asset", "computer", "laptop", "software", "monitor")):
        return "tools_assets"
    if any(term in normalized for term in ("union", "professional", "membership", "accreditation", "licence", "license")):
        return "union_professional"
    if (
        any(term in normalized for term in ("public transport", "ride share"))
        or tokens.intersection({"travel", "car", "vehicle", "taxi", "rideshare", "uber"})
    ):
        return "travel"
    return "unsupported"


def deduction_question(item: Dict[str, Any], kind: str) -> str:
    label = display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["label"]))
    return label or DEDUCTION_KIND_LABELS.get(kind, "Deduction item")


def deduction_ato_area(kind: str) -> str:
    return {
        "gift": "D9 Gifts or donations",
        "tax_affairs": "D10 Cost of managing tax affairs",
        "income_protection": "D15 Other deductions / income protection review",
        "self_education": "D4 Work-related self-education expenses",
        "union_professional": "D5 Other work-related expenses",
        "travel": "D1/D2 Work-related travel and car expenses",
        "tools_assets": "D5 Other work-related expenses",
    }.get(kind, "Deductions review")


def deduction_answer_text(item: Dict[str, Any], kind: str, amount: Optional[float]) -> str:
    text = (
        f"type {DEDUCTION_KIND_LABELS.get(kind, 'Unsupported/other deduction')}; "
        f"label {deduction_question(item, kind)}; amount {money_text(amount)}; "
        f"evidence {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['evidence']))}; "
        f"reimbursed {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['reimbursed']))}; "
        f"employer paid {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['employer_paid']))}; "
        f"employer provided {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['employer_provided']))}; "
        f"work use {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['work_use_percent']))}; "
        f"private use {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['private_use_percent']))}; "
        f"split {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['work_private_split']))}; "
        f"GST/BAS {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['gst_bas_interaction']))}; "
        f"duplicate risk {display_value(normalized_item_field(item, DEDUCTION_FIELD_ALIASES['duplicate_risk']))}"
    )
    conflicts = item_alias_conflict_text(item, DEDUCTION_FIELD_ALIASES)
    return f"{text}; alias conflicts {conflicts}" if conflicts else text


def deduction_review_terms(item: Dict[str, Any], kind: str) -> List[str]:
    terms: List[str] = []
    amount_value = normalized_item_field(item, DEDUCTION_FIELD_ALIASES["amount"])
    if amount_malformed(amount_value) or nonnegative_money_value(amount_value) is None:
        terms.append("amount evidence")
    if evidence_missing(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["evidence"])):
        terms.append("receipt/statement evidence")
    if deduction_flag_review(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["reimbursed"])):
        terms.append("reimbursement review")
    if deduction_flag_review(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["employer_paid"])):
        terms.append("employer-paid review")
    if deduction_flag_review(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["employer_provided"])):
        terms.append("employer-provided review")
    if deduction_private_use_review(item, kind):
        terms.append("work/private split evidence")
    if deduction_flag_review(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["gst_bas_interaction"])):
        terms.append("GST/BAS overlap review")
    if deduction_flag_review(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["duplicate_risk"])):
        terms.append("duplicate-risk review")
    if kind == "unsupported":
        terms.append("official source support")
    terms.extend(item_alias_conflict_details(item, DEDUCTION_FIELD_ALIASES))
    return terms or ["accountant review"]


def deduction_flag_review(value: Any) -> bool:
    parsed = phone_bool(value)
    if parsed is False or is_missing(value):
        return False
    if parsed is True:
        return True
    if contains_unknown(value):
        return True
    if deduction_flag_negative(value):
        return False
    return has_meaningful_value(value)


def deduction_flag_negative(value: Any) -> bool:
    if deduction_flag_partial_value(value):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", display_value(value).lower()).strip()
    return bool(
        re.search(
            r"\b(not|no|never|without)\b.*\b(reimburs|employer|paid|provided|gst|bas|duplicate|risk|overlap)\w*\b",
            normalized,
        )
        or re.search(r"\b(no|not)\s+(gst|bas|duplicate|risk|overlap)\w*\b", normalized)
    )


def deduction_flag_partial_value(value: Any) -> bool:
    return partial_negative_context_value(value, r"(reimburs|employer|paid|provided)\w*")


def partial_negative_context_value(value: Any, review_context: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", display_value(value).lower()).strip()
    partial_context = r"(partial|partly|partially|some|not\s+fully|not\s+all)"
    return bool(
        re.search(rf"\b{partial_context}\b.*\b{review_context}\b", normalized)
        or re.search(rf"\b{review_context}\b.*\b{partial_context}\b", normalized)
    )


def review_flag_review(value: Any) -> bool:
    parsed = phone_bool(value)
    if parsed is False or is_missing(value):
        return False
    if parsed is True:
        return True
    if contains_unknown(value):
        return True
    if review_flag_negative(value):
        return False
    return has_meaningful_value(value)


def review_flag_negative(value: Any) -> bool:
    if review_flag_partial_value(value):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", display_value(value).lower()).strip()
    return bool(
        re.search(r"\b(no|not|never|without)\b.*\b(review|cap|division|293|eligibility|eligible)\b", normalized)
        or re.search(r"\b(no|not)\s+(review|cap|division|293|eligibility|eligible)\b", normalized)
    )


def review_flag_partial_value(value: Any) -> bool:
    return partial_negative_context_value(value, r"(review|cap|division|293|eligibility|eligible)\w*")


def deduction_private_use_review(item: Dict[str, Any], kind: str) -> bool:
    if kind in {"gift", "tax_affairs"}:
        return False
    work_use = normalized_item_field(item, DEDUCTION_FIELD_ALIASES["work_use_percent"])
    private_use = normalized_item_field(item, DEDUCTION_FIELD_ALIASES["private_use_percent"])
    split = normalized_item_field(item, DEDUCTION_FIELD_ALIASES["work_private_split"])
    if not is_missing(work_use) or not is_missing(private_use) or not is_missing(split):
        work_use_percent = phone_percent_value(work_use)
        work_use_review = not is_missing(work_use) and (work_use_percent is None or work_use_percent < 100)
        private_use_percent = phone_percent_value(private_use)
        private_use_review = not is_missing(private_use) and (
            contains_unknown(private_use)
            or (private_use_percent is not None and private_use_percent > 0)
            or (private_use_percent is None and not deduction_private_use_negative(private_use) and deduction_flag_review(private_use))
        )
        split_review = not is_missing(split) and contains_unknown(split) or (
            not is_missing(split) and not deduction_private_use_negative(split) and deduction_flag_review(split)
        )
        return (
            contains_unknown(work_use)
            or work_use_review
            or private_use_review
            or split_review
        )
    return kind in {"self_education", "travel", "tools_assets"}


def deduction_private_use_negative(value: Any) -> bool:
    if phone_bool(value) is False:
        return True
    if is_missing(value) or contains_unknown(value):
        return False
    percent = phone_percent_value(value)
    if percent is not None:
        return percent <= 0
    normalized = re.sub(r"[^a-z0-9]+", " ", display_value(value).lower()).strip()
    return bool(
        re.search(r"\b(no|not|without|zero)\b.*\b(private|personal|non work|nonwork|mixed)\b", normalized)
        or re.search(r"\b(work only|only work|wholly work|100 percent work|100 work)\b", normalized)
    )


def deduction_sources(kind: str, item: Dict[str, Any], answers: Dict[str, Any]) -> List[str]:
    sources = {
        "gift": [ATO_GIFTS_DONATIONS_SOURCE],
        "tax_affairs": [ATO_TAX_AFFAIRS_SOURCE],
        "income_protection": [ATO_INVESTMENTS_INSURANCE_SUPER_SOURCE],
        "self_education": [ATO_SELF_EDUCATION_SOURCE, ATO_WORK_RELATED_DEDUCTIONS_SOURCE],
        "union_professional": [ATO_MEMBERSHIPS_FEES_SOURCE, ATO_WORK_RELATED_DEDUCTIONS_SOURCE],
        "travel": [ATO_CAR_TRANSPORT_TRAVEL_SOURCE, ATO_CAR_EXPENSES_SOURCE, ATO_PUBLIC_TRANSPORT_SOURCE, ATO_TRAVEL_RECORDS_SOURCE],
        "tools_assets": [ATO_TOOLS_EQUIPMENT_SOURCE, ATO_ASSET_SOURCE, ATO_ASSET_300_OR_LESS_SOURCE, ATO_ASSET_OVER_300_SOURCE],
    }.get(kind, [ATO_WORK_RELATED_DEDUCTIONS_SOURCE])
    if deduction_flag_review(normalized_item_field(item, DEDUCTION_FIELD_ALIASES["gst_bas_interaction"])):
        sources = [*sources, ATO_GST_CREDITS_SOURCE, ATO_TAX_INVOICES_SOURCE]
    return sources


def deduction_tab_text(kind: str, terms: List[str]) -> str:
    label = DEDUCTION_KIND_LABELS.get(kind, "Unsupported/other deduction")
    return f"{label} stays prep-only; " + ", ".join(terms) + "."


def deduction_evidence_rows(items: List[Dict[str, Any]], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not has_meaningful_value(item):
            continue
        kind = deduction_kind(item)
        terms = deduction_review_terms(item, kind)
        if terms and terms != ["accountant review"]:
            rows.append(
                guide_row(
                    f"DED-EVID-{len(rows) + 1}",
                    deduction_ato_area(kind),
                    "Deduction evidence required",
                    f"{deduction_question(item, kind)}: {', '.join(terms)}",
                    "Deduction rows remain prep-only until receipts, payment source, private-use split, duplicate-risk, GST/BAS overlap, and source support are reviewed.",
                    "Evidence",
                    deduction_sources(kind, item, answers),
                    row_kind="evidence-queue",
                    facts=handoff_facts(
                        ("deduction", "Deduction", deduction_question(item, kind)),
                        ("evidence-needed", "Evidence or review needed", ", ".join(terms)),
                    ),
                )
            )
    return rows


def personal_super_contribution_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not has_meaningful_value(item):
            continue
        gaps = personal_super_contribution_review_terms(item)
        rows.append(
            guide_row(
                f"SUPER-DED-{index}",
                "D12 Personal super contributions",
                "Personal super contribution deduction prep",
                personal_super_contribution_answer_text(item),
                "Personal super contribution deductions need contribution records, valid notice of intent, fund acknowledgement, cap review, and Division 293 review before entry.",
                "Accountant review",
                ATO_PERSONAL_SUPER_DEDUCTION_SOURCES,
                tab_text="Personal super deduction prep-only; " + ", ".join(gaps) + ".",
                row_kind="deduction",
                facts=handoff_facts(
                    ("fund", "Fund", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["fund"])),
                    ("member", "Member", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["member"])),
                    ("contribution-date", "Contribution date", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["contribution_date"])),
                    ("contribution-amount", "Contribution amount", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["amount"])),
                    ("notice-of-intent", "Notice of intent", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["notice_of_intent"])),
                    ("fund-acknowledgement", "Fund acknowledgement", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["fund_acknowledgement"])),
                    ("intended-deduction", "Intended deduction amount", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["intended_deduction_amount"])),
                    ("cap-review", "Concessional cap review", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["concessional_cap_review"])),
                    ("division-293", "Division 293 review", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["division_293_review"])),
                    ("notes", "Notes", normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["notes"])),
                    ("alias-conflicts", "Alias conflicts", item_alias_conflict_text(item, SUPER_CONTRIBUTION_FIELD_ALIASES) or "none"),
                ),
            )
        )
    return rows


def personal_super_contribution_answer_text(item: Dict[str, Any]) -> str:
    amount = nonnegative_money_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["amount"]))
    intended = nonnegative_money_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["intended_deduction_amount"]))
    text = (
        f"fund {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['fund']))}; "
        f"member {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['member']))}; "
        f"date {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['contribution_date']))}; "
        f"contribution {money_text(amount)}; notice {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['notice_of_intent']))}; "
        f"fund acknowledgement {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['fund_acknowledgement']))}; "
        f"intended deduction {money_text(intended)}; cap review {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['concessional_cap_review']))}; "
        f"Division 293 review {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['division_293_review']))}; "
        f"notes {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES['notes']))}"
    )
    conflicts = item_alias_conflict_text(item, SUPER_CONTRIBUTION_FIELD_ALIASES)
    return f"{text}; alias conflicts {conflicts}" if conflicts else text


def personal_super_contribution_subject(item: Dict[str, Any]) -> str:
    for field in ("fund", "notes", "member"):
        value = display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES[field]))
        if value:
            return value
    return "Personal super contribution"


def personal_super_contribution_review_terms(item: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    amount_value = normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["amount"])
    intended_value = normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["intended_deduction_amount"])
    if amount_malformed(amount_value) or nonnegative_money_value(amount_value) is None:
        terms.append("contribution amount evidence")
    if amount_malformed(intended_value) or nonnegative_money_value(intended_value) is None:
        terms.append("intended deduction amount evidence")
    contribution_date = normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["contribution_date"])
    for field, label in (
        ("fund", "fund details"),
        ("member", "member details"),
        ("notice_of_intent", "notice of intent"),
        ("fund_acknowledgement", "fund acknowledgement"),
    ):
        if evidence_missing(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES[field])):
            terms.append(label)
    if evidence_missing(contribution_date) or parse_iso_date(contribution_date) is None:
        terms.append("contribution date")
    if review_flag_review(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["concessional_cap_review"])):
        terms.append("concessional cap review")
    if review_flag_review(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["division_293_review"])):
        terms.append("Division 293 review")
    if deduction_flag_review(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES["notes"])):
        terms.append("free-form note review")
    terms.extend(item_alias_conflict_details(item, SUPER_CONTRIBUTION_FIELD_ALIASES))
    return terms or ["cap and notice review"]


def personal_super_contribution_evidence_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in items:
        if not has_meaningful_value(item):
            continue
        terms = personal_super_contribution_review_terms(item)
        if terms and terms != ["cap and notice review"]:
            rows.append(
                guide_row(
                    f"SUPER-DED-EVID-{len(rows) + 1}",
                    "D12 Personal super contributions",
                    "Personal super contribution evidence required",
                    f"{personal_super_contribution_subject(item)}: {', '.join(terms)}",
                    "Personal super contribution deduction prep remains blocked until notice, acknowledgement, contribution amount/date, cap, and Division 293 facts are reviewed.",
                    "Evidence",
                    ATO_PERSONAL_SUPER_DEDUCTION_SOURCES,
                    row_kind="evidence-queue",
                    facts=handoff_facts(
                        ("contribution", "Contribution", personal_super_contribution_subject(item)),
                        ("evidence-needed", "Evidence or review needed", ", ".join(terms)),
                    ),
                )
            )
    return rows


def offset_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not has_meaningful_value(item):
            continue
        kind = offset_kind(item)
        gaps = offset_review_terms(item, kind)
        rows.append(
            guide_row(
                f"OFFSET-{index}",
                offset_ato_area(kind),
                "Individual offset routing",
                offset_answer_text(item, kind),
                "Offset rows are routing only. Eligibility, amount, income tests, remote-zone facts, spouse/dependant facts, and super offset details stay under accountant review.",
                "Accountant review",
                offset_sources(kind),
                tab_text=f"{offset_label(kind)} offset routing; " + ", ".join(gaps) + ".",
                row_kind="deduction",
                facts=handoff_facts(
                    ("offset-type", "Offset type", offset_label(kind)),
                    ("raw-type", "Type supplied", normalized_item_field(item, OFFSET_FIELD_ALIASES["kind"])),
                    ("claim", "Claim signal", normalized_item_field(item, OFFSET_FIELD_ALIASES["claim"])),
                    ("amount", "Amount supplied", normalized_item_field(item, OFFSET_FIELD_ALIASES["amount"])),
                    ("evidence", "Eligibility evidence", normalized_item_field(item, OFFSET_FIELD_ALIASES["evidence"])),
                    ("review-signal", "Review signal", normalized_item_field(item, OFFSET_FIELD_ALIASES["review_signal"])),
                    ("alias-conflicts", "Alias conflicts", item_alias_conflict_text(item, OFFSET_FIELD_ALIASES) or "none"),
                ),
            )
        )
    return rows


def offset_kind(item: Dict[str, Any]) -> str:
    value = display_value(normalized_item_field(item, OFFSET_FIELD_ALIASES["kind"])).lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", value).strip()
    if "spouse" in normalized:
        return "spouse"
    if "zone" in normalized or "remote" in normalized:
        return "zone_remote"
    if "super" in normalized:
        return "super"
    if normalized:
        return "other"
    return "unsupported"


def offset_label(kind: str) -> str:
    return {
        "spouse": "Spouse",
        "super": "Super",
        "zone_remote": "Zone/remote",
        "other": "Other",
    }.get(kind, "Unsupported")


def offset_ato_area(kind: str) -> str:
    return "Tax offsets" if kind != "super" else "Tax offsets / super"


def offset_answer_text(item: Dict[str, Any], kind: str) -> str:
    amount = nonnegative_money_value(normalized_item_field(item, OFFSET_FIELD_ALIASES["amount"]))
    text = (
        f"type {offset_label(kind)}; raw type {display_value(normalized_item_field(item, OFFSET_FIELD_ALIASES['kind']))}; "
        f"claim {display_value(normalized_item_field(item, OFFSET_FIELD_ALIASES['claim']))}; "
        f"amount {money_text(amount)}; evidence {display_value(normalized_item_field(item, OFFSET_FIELD_ALIASES['evidence']))}; "
        f"review signal {display_value(normalized_item_field(item, OFFSET_FIELD_ALIASES['review_signal']))}"
    )
    conflicts = item_alias_conflict_text(item, OFFSET_FIELD_ALIASES)
    return f"{text}; alias conflicts {conflicts}" if conflicts else text


def offset_subject(item: Dict[str, Any], kind: str) -> str:
    for field in ("kind", "review_signal", "evidence"):
        value = display_value(normalized_item_field(item, OFFSET_FIELD_ALIASES[field]))
        if value:
            return value
    return offset_label(kind)


def offset_review_terms(item: Dict[str, Any], kind: str) -> List[str]:
    terms: List[str] = []
    claim = normalized_item_field(item, OFFSET_FIELD_ALIASES["claim"])
    amount = normalized_item_field(item, OFFSET_FIELD_ALIASES["amount"])
    claim_false = offset_claim_false(claim)
    review_offset_facts = not claim_false and (
        kind != "unsupported"
        or deduction_flag_review(claim)
        or not is_missing(amount)
        or not is_missing(normalized_item_field(item, OFFSET_FIELD_ALIASES["evidence"]))
        or not is_missing(normalized_item_field(item, OFFSET_FIELD_ALIASES["review_signal"]))
    )
    if kind == "unsupported":
        terms.append("offset type required")
    if kind == "other":
        terms.append("official offset support")
    if review_offset_facts and (amount_malformed(amount) or nonnegative_money_value(amount) is None):
        terms.append("offset amount evidence")
    if review_offset_facts and evidence_missing(normalized_item_field(item, OFFSET_FIELD_ALIASES["evidence"])):
        terms.append("eligibility evidence")
    if review_offset_facts and review_flag_review(normalized_item_field(item, OFFSET_FIELD_ALIASES["review_signal"])):
        terms.append("eligibility review")
    terms.extend(item_alias_conflict_details(item, OFFSET_FIELD_ALIASES))
    return terms or ["accountant review"]


def offset_claim_false(value: Any) -> bool:
    if phone_bool(value) is False:
        return True
    if is_missing(value) or contains_unknown(value):
        return False
    if offset_claim_partial_value(value):
        return False
    normalized = re.sub(r"[^a-z0-9]+", " ", display_value(value).lower()).strip()
    return bool(
        re.search(r"\b(not|no|never)\b.*\b(claim|claiming|claimed|apply|applying|applied|eligible|entitled|entitlement)\b", normalized)
        or re.search(r"\b(ineligible|unentitled)\b", normalized)
    )


def offset_claim_partial_value(value: Any) -> bool:
    return partial_negative_context_value(
        value,
        r"(claim|claiming|claimed|apply|applying|applied|eligible|entitled|entitlement)\w*",
    )


def offset_sources(kind: str) -> List[str]:
    if kind == "super":
        return ATO_SUPER_OFFSET_SOURCES
    return ATO_OFFSET_SOURCES


def offset_evidence_rows(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in items:
        if not has_meaningful_value(item):
            continue
        kind = offset_kind(item)
        terms = offset_review_terms(item, kind)
        if terms and terms != ["accountant review"]:
            rows.append(
                guide_row(
                    f"OFFSET-EVID-{len(rows) + 1}",
                    offset_ato_area(kind),
                    "Offset evidence required",
                    f"{offset_subject(item, kind)}: {', '.join(terms)}",
                    "Offset routing remains prep-only until eligibility, evidence, income-test, and amount facts are reviewed.",
                    "Evidence",
                    offset_sources(kind),
                    row_kind="evidence-queue",
                    facts=handoff_facts(
                        ("offset", "Offset", offset_subject(item, kind)),
                        ("evidence-needed", "Evidence or review needed", ", ".join(terms)),
                    ),
                )
            )
    return rows


PHONE_NESTED_KEYS = ("phone", "phone_deduction", "mobile_phone", "mobile")
PHONE_FIELD_ALIASES = {
    "context": ("phone_context", "phone_work_context"),
    "paid_by_user": ("phone_paid_by_user", "phone_user_paid"),
    "employer_reimbursed": ("phone_employer_reimbursed", "phone_reimbursed"),
    "employer_paid": ("phone_employer_paid",),
    "employer_provided": ("phone_employer_provided", "employer_provided_phone"),
    "gst_registered": ("phone_gst_registered", "phone_gst_registration_status"),
    "gst_registration_date": ("phone_gst_registration_date",),
    "wfh_method": (
        "phone_wfh_method",
        "wfh_method",
        "work_from_home_method",
        "claim_method",
        "deduction_method",
        "calculation_method",
    ),
}
PHONE_LOCAL_WFH_NESTED_KEYS = ("wfh", "work_from_home", "work_from_home_pattern")
PHONE_WFH_NESTED_KEYS = ("wfh", "wfh_work_pattern")
PHONE_WFH_METHOD_ALIASES = (
    "method",
    "wfh_method",
    "work_from_home_method",
    "claim_method",
    "deduction_method",
    "calculation_method",
    "method_preference",
)
PHONE_WFH_METHOD_METADATA_KEYS = (
    "method",
    "wfh_method",
    "work_from_home_method",
    "claim_method",
    "deduction_method",
    "calculation_method",
)
PHONE_GST_STATUS_KEYS = (
    "gst_registered",
    "gst_registration_status",
    "registered",
    "phone_gst_registered",
    "phone_gst_registration_status",
)
PHONE_GST_DATE_KEYS = (
    "gst_registration_date",
    "registered_from",
    "registration_date",
    "phone_gst_registration_date",
)
PHONE_EMPLOYER_REIMBURSED_MARKERS = ("reimburs\\w*", "refund\\w*", "paid back")
PHONE_EMPLOYER_PAID_MARKERS = (
    "employer paid",
    "paid by employer",
    "company paid",
    "work paid",
    "paid by work",
    "employer covers",
    "company covers",
    "work covers",
)
PHONE_EMPLOYER_PROVIDED_MARKERS = (
    "employer provided",
    "provided by employer",
    "company provided",
    "provided by work",
    "issued by employer",
    "issued by work",
    "work phone",
    "company phone",
)
PHONE_EMPLOYER_MARKERS = (
    *PHONE_EMPLOYER_REIMBURSED_MARKERS,
    *PHONE_EMPLOYER_PAID_MARKERS,
    *PHONE_EMPLOYER_PROVIDED_MARKERS,
)
PHONE_EMPLOYER_MARKER_GROUPS = (
    ("reimbursed", PHONE_EMPLOYER_REIMBURSED_MARKERS),
    ("paid", PHONE_EMPLOYER_PAID_MARKERS),
    ("provided", PHONE_EMPLOYER_PROVIDED_MARKERS),
)
PHONE_TEXT_NEGATION_PATTERN = (
    r"(no|not|never|without|dont|don t|didnt|didn t|did not|n a|not applicable)"
)
PHONE_METADATA_KEYS = {
    "context",
    "paid_by_user",
    "employer_reimbursed",
    "employer_paid",
    "employer_provided",
    *PHONE_LOCAL_WFH_NESTED_KEYS,
    *PHONE_WFH_METHOD_METADATA_KEYS,
    *PHONE_GST_STATUS_KEYS,
    *PHONE_GST_DATE_KEYS,
    "wfh_method",
}
PHONE_OPT_OUT_KEYS = {
    "claim",
    "claimed",
    "claiming",
    "deduction",
    "expense",
    "expenses",
    "cost",
    "costs",
    "freeform",
}
PHONE_NEGATIVE_OPT_OUT_KEYS = {"no_claim", "no_deduction", "not_claiming"}
PHONE_DEVICE_ALIASES = {
    "description": ("description", "phone_device_description", "phone_description"),
    "cost": ("cost", "phone_device_cost", "phone_cost"),
    "purchase_date": ("purchase_date", "phone_purchase_date", "phone_device_purchase_date"),
    "work_use_percent": ("work_use_percent", "phone_device_work_use_percent", "phone_work_use_percent"),
    "method_preference": ("method_preference", "phone_depreciation_method", "phone_method_preference"),
    "effective_life_years": ("effective_life_years", "phone_effective_life_years"),
    "receipt": ("receipt", "phone_device_receipt", "phone_receipt"),
    "insurance_amount": ("insurance_amount", "phone_insurance_amount", "phone_device_insurance"),
    "set_or_substantially_identical": ("set_or_substantially_identical", "phone_set_or_substantially_identical", "phone_set_rule"),
    "more_than_50_percent_work_use": ("more_than_50_percent_work_use", "phone_more_than_50_percent_work_use"),
    "work_use_percent_changed": ("work_use_percent_changed", "phone_work_use_percent_changed", "phone_changed_use"),
}
PHONE_PLAN_ALIASES = {
    "monthly_cost": ("monthly_cost", "phone_plan_monthly_cost", "phone_monthly_cost", "mobile_plan_amount"),
    "months_claimed": ("months_claimed", "phone_plan_months_claimed", "phone_months_claimed", "mobile_plan_months"),
    "itemised_bill": ("itemised_bill", "phone_itemised_bill", "phone_plan_itemised_bill"),
    "prepaid": ("prepaid", "phone_prepaid", "phone_plan_prepaid"),
    "representative_period_start": ("representative_period_start", "phone_representative_period_start", "phone_4_week_start"),
    "representative_period_end": ("representative_period_end", "phone_representative_period_end", "phone_4_week_end"),
    "work_use_percent": ("work_use_percent", "phone_plan_work_use_percent", "phone_data_work_use_percent"),
    "basis": ("basis", "phone_plan_basis", "phone_work_use_basis"),
    "bills": ("bills", "phone_bills", "phone_plan_bills"),
    "log": ("log", "phone_log", "phone_4_week_record", "phone_calendar"),
}
PHONE_INCIDENTAL_ALIASES = {
    "claim_amount": ("claim_amount", "phone_incidental_claim_amount", "phone_incidental_amount"),
    "work_calls": ("work_calls", "phone_incidental_work_calls", "phone_work_calls"),
    "work_texts": ("work_texts", "phone_incidental_work_texts", "phone_work_texts"),
    "basic_records": ("basic_records", "phone_incidental_basic_records", "phone_basic_records"),
}
PHONE_DEVICE_SIGNAL_KEYS = set(PHONE_DEVICE_ALIASES).difference({"work_use_percent"})
PHONE_PLAN_SIGNAL_KEYS = set(PHONE_PLAN_ALIASES).difference({"work_use_percent"})
PHONE_INCIDENTAL_SIGNAL_KEYS = set(PHONE_INCIDENTAL_ALIASES)
PHONE_NESTED_ALIAS_GROUPS = (
    PHONE_FIELD_ALIASES,
    PHONE_DEVICE_ALIASES,
    PHONE_PLAN_ALIASES,
    PHONE_INCIDENTAL_ALIASES,
)


def phone_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw: Dict[str, Any] = {}
    for key in PHONE_NESTED_KEYS:
        value = answers.get(key)
        if isinstance(value, dict):
            raw.update(phone_normalized_nested_raw(value))
        elif key in answers and not is_missing(value) and not phone_freeform_absent(value):
            raw.setdefault("freeform", value)
    for target, aliases in PHONE_FIELD_ALIASES.items():
        value = first_alias_value(answers, aliases)
        if value is not None:
            raw[target] = value
    wfh_method = phone_preferred_wfh_method(
        raw.get("wfh_method"),
        phone_local_wfh_method(raw),
        phone_nested_wfh_method(answers),
    )
    if wfh_method is not None:
        raw["wfh_method"] = wfh_method
    raw["device"] = phone_child_answers(raw.get("device"), raw, answers, PHONE_DEVICE_ALIASES, PHONE_DEVICE_SIGNAL_KEYS)
    raw["plan"] = phone_child_answers(raw.get("plan"), raw, answers, PHONE_PLAN_ALIASES, PHONE_PLAN_SIGNAL_KEYS)
    raw["incidental"] = phone_child_answers(raw.get("incidental"), raw, answers, PHONE_INCIDENTAL_ALIASES, PHONE_INCIDENTAL_SIGNAL_KEYS)
    if not has_phone_inputs(raw):
        return {}
    if is_missing(raw.get("context")) and (has_abn_inputs(answers) or has_bas_inputs(answers)):
        raw["context"] = "employee" if phone_context_is_employee(display_value(raw.get("freeform"))) else "abn"
    return raw


def phone_preferred_wfh_method(*values: Any) -> Any:
    candidates = [value for value in values if value is not None and not is_missing(value)]
    for value in candidates:
        if phone_wfh_fixed_rate_value(value):
            return value
    return candidates[0] if candidates else None


def phone_local_wfh_method(raw: Dict[str, Any]) -> Any:
    values = [
        raw.get(alias)
        for alias in PHONE_WFH_METHOD_ALIASES
        if alias in raw and not is_missing(raw.get(alias))
    ]
    for key in PHONE_LOCAL_WFH_NESTED_KEYS:
        nested = raw.get(key)
        if not isinstance(nested, dict):
            continue
        values.extend(
            nested.get(alias)
            for alias in PHONE_WFH_METHOD_ALIASES
            if alias in nested and not is_missing(nested.get(alias))
        )
    return phone_preferred_wfh_method(*values)


def phone_nested_wfh_method(answers: Dict[str, Any]) -> Any:
    for key in PHONE_WFH_NESTED_KEYS:
        raw = answers.get(key)
        if not isinstance(raw, dict):
            continue
        value = first_alias_value(raw, PHONE_WFH_METHOD_ALIASES)
        if value is not None:
            return value
    return None


def phone_normalized_nested_raw(raw: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    freeform_parts: List[str] = []
    for key, value in raw.items():
        normalized_key = str(key).strip().lower()
        if normalized_key in PHONE_OPT_OUT_KEYS and phone_freeform_absent(value):
            continue
        if normalized_key in PHONE_NEGATIVE_OPT_OUT_KEYS:
            if phone_bool(value) is True:
                continue
            if phone_bool(value) is False or is_missing(value):
                continue
        if not phone_nested_known_field(normalized_key):
            if phone_freeform_present(value):
                freeform_parts.append(f"{normalized_key} {display_value(value)}")
            continue
        result[key] = value
    if freeform_parts:
        existing = ""
        if phone_freeform_present(result.get("freeform")):
            existing = display_value(result.get("freeform"))
        result["freeform"] = "; ".join(part for part in (existing, *freeform_parts) if part)
    return result


def phone_nested_known_field(key: str) -> bool:
    if key in {"device", "plan", "incidental", "freeform", *PHONE_METADATA_KEYS}:
        return True
    return any(
        key == target or key in aliases
        for aliases_by_target in PHONE_NESTED_ALIAS_GROUPS
        for target, aliases in aliases_by_target.items()
    )


def phone_child_answers(
    raw_child: Any,
    nested_phone: Dict[str, Any],
    answers: Dict[str, Any],
    aliases: Dict[str, tuple[str, ...]],
    signal_keys: set[str],
) -> Dict[str, Any]:
    child = phone_nested_answers(raw_child, nested_phone, aliases)
    child = phone_nested_answers(child, answers, aliases)
    if not any(has_meaningful_value(child.get(key)) for key in signal_keys):
        return {}
    return child


def phone_nested_answers(raw: Any, answers: Dict[str, Any], aliases: Dict[str, tuple[str, ...]]) -> Dict[str, Any]:
    result = dict(raw) if isinstance(raw, dict) else {}
    for target, keys in aliases.items():
        value = first_alias_value(answers, keys)
        if value is not None and (target not in result or is_missing(result.get(target))):
            result[target] = value
    return result


def first_alias_value(values: Dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in values and not is_missing(values.get(key)):
            return values.get(key)
    return None


def has_phone_inputs(raw: Dict[str, Any]) -> bool:
    if not isinstance(raw, dict):
        return False
    return any(
        phone_freeform_present(value) if key == "freeform" else has_meaningful_value(value)
        for key, value in raw.items()
        if key not in {*PHONE_METADATA_KEYS, "device", "plan", "incidental"}
    ) or any(has_meaningful_value(raw.get(key)) for key in ("device", "plan", "incidental"))


def phone_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not has_phone_inputs(raw):
        return []
    rows = [phone_overview_row(raw, answers)]
    rows.extend(phone_plan_rows(raw, answers))
    rows.extend(phone_device_rows(raw, answers))
    rows.extend(phone_incidental_rows(raw, answers))
    return rows


def phone_overview_row(raw: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    context = phone_context(raw, answers)
    flags = phone_blocking_terms(raw)
    if phone_abn_context(raw, answers):
        flags.append("ABN/GST/BAS review path")
    if phone_wfh_fixed_rate(raw):
        flags.append("WFH fixed-rate blocks separate phone/data")
    if not flags:
        flags.append("employee D5 prep-only review")
    freeform = display_value(raw.get("freeform"))
    freeform_text = f"; free-form facts {freeform}" if freeform else ""
    return guide_row(
        "PHONE",
        "Phone deduction overview",
        "Phone plan, data, and device prep path",
        f"context {context}; paid by user {display_value(raw.get('paid_by_user'))}; employer reimbursed {display_value(raw.get('employer_reimbursed'))}; employer paid {display_value(raw.get('employer_paid'))}; employer provided {display_value(raw.get('employer_provided'))}; WFH method {display_value(raw.get('wfh_method'))}{freeform_text}",
        "Phone facts are prep-only. Employer-paid/reimbursed/provided, mixed-use, WFH fixed-rate, ABN/GST/BAS, and depreciation facts stay blocked or under accountant review.",
        "Accountant review",
        phone_sources(raw, answers),
        tab_text="Phone overview: " + ", ".join(flags) + ".",
        row_kind="deduction",
        facts=handoff_facts(
            ("context", "Work context", context),
            ("paid-by-user", "Paid by user", raw.get("paid_by_user")),
            ("employer-reimbursed", "Employer reimbursed", raw.get("employer_reimbursed")),
            ("employer-paid", "Employer paid", raw.get("employer_paid")),
            ("employer-provided", "Employer provided", raw.get("employer_provided")),
            ("wfh-method", "Work-from-home method", raw.get("wfh_method")),
            ("freeform", "Additional phone facts", raw.get("freeform")),
            ("review-flags", "Review flags", ", ".join(flags)),
        ),
    )


def phone_plan_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    plan = raw.get("plan") if isinstance(raw.get("plan"), dict) else {}
    if not has_meaningful_value(plan):
        return []
    monthly = phone_nonnegative_money_value(plan.get("monthly_cost"))
    months = phone_months_claimed_value(plan.get("months_claimed"))
    work_use = phone_percent_value(plan.get("work_use_percent"))
    candidate = None if monthly is None or months is None or work_use is None else round(monthly * months * work_use / 100, 2)
    itemised = phone_bool(plan.get("itemised_bill"))
    blocked = phone_plan_blocked(raw)
    evidence_gap = phone_plan_evidence_gap(plan)
    status = "Evidence" if evidence_gap or candidate is None else "Accountant review"
    if blocked:
        status = "Accountant review"
        candidate_text = "blocked"
    else:
        candidate_text = money_text(candidate)
    answer = (
        f"monthly {money_text(monthly)}; months {money_text(months)}; itemised {display_value(plan.get('itemised_bill'))}; "
        f"prepaid {display_value(plan.get('prepaid'))}; representative period {display_value(plan.get('representative_period_start'))} to {display_value(plan.get('representative_period_end'))}; "
        f"work use {percent_text(work_use)}; basis {display_value(plan.get('basis'))}; candidate {candidate_text}; bills {display_value(plan.get('bills'))}; log {display_value(plan.get('log'))}"
    )
    if blocked:
        answer = f"{answer}; blocked: {', '.join(blocked)}"
    elif itemised is False:
        answer = f"{answer}; non-itemised/prepaid requires representative 4-week work/private record"
    return [
        guide_row(
            "PHONE-PLAN",
            "D5 Other work-related expenses" if not phone_abn_context(raw, answers) else "ABN/GST/BAS phone review",
            "Phone plan/data",
            answer,
            "Phone plan/data needs user-paid cost, work-use basis, bill/payment evidence, and 4-week support. WFH fixed-rate blocks a separate phone/data candidate.",
            status,
            phone_sources(raw, answers),
            tab_text=phone_plan_tab_text(blocked, evidence_gap),
            row_kind="deduction",
            facts=handoff_facts(
                ("monthly-cost", "Monthly cost", plan.get("monthly_cost")),
                ("months-claimed", "Months claimed", plan.get("months_claimed")),
                ("itemised-bill", "Itemised bill", plan.get("itemised_bill")),
                ("prepaid", "Prepaid", plan.get("prepaid")),
                ("representative-period-start", "Representative period start", plan.get("representative_period_start")),
                ("representative-period-end", "Representative period end", plan.get("representative_period_end")),
                ("work-use", "Work-use percentage", plan.get("work_use_percent")),
                ("basis", "Work-use basis", plan.get("basis")),
                ("candidate", "Prepared candidate amount", candidate_text),
                ("bills", "Bills or payment evidence", plan.get("bills")),
                ("usage-log", "Work/private usage log", plan.get("log")),
                ("blocking-facts", "Blocking facts", ", ".join(blocked) or "none"),
            ),
        )
    ]


def phone_device_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    device = raw.get("device") if isinstance(raw.get("device"), dict) else {}
    if not has_meaningful_value(device):
        return []
    cost = phone_nonnegative_money_value(device.get("cost"))
    work_use = phone_percent_value(device.get("work_use_percent"))
    work_amount = None if cost is None or work_use is None else round(cost * work_use / 100, 2)
    blocked = phone_device_blocked(raw)
    evidence_gap = phone_device_evidence_gap(device)
    immediate_candidate = phone_under_300_candidate(device, cost, work_use)
    if blocked:
        status = "Accountant review"
        treatment = "blocked: " + ", ".join(blocked)
        treatment_fact = "Method review blocked"
        treatment_boundary = ", ".join(blocked)
    elif cost is None or work_use is None or evidence_gap:
        status = "Evidence"
        treatment = "evidence needed before method review"
        treatment_fact = "Evidence needed before method review"
        treatment_boundary = ""
    elif cost > 300:
        status = "Accountant review"
        treatment = "decline-in-value review; not full immediate claim"
        treatment_fact = "Decline-in-value review"
        treatment_boundary = "Not a full immediate claim"
    elif immediate_candidate:
        status = "Accountant review"
        treatment = "immediate deduction candidate if source-backed conditions and evidence hold"
        treatment_fact = "Immediate deduction candidate"
        treatment_boundary = "Only if source-backed conditions and evidence hold"
    else:
        status = "Evidence"
        treatment = "under-300 conditions incomplete; no immediate candidate yet"
        treatment_fact = "Under-$300 conditions incomplete"
        treatment_boundary = "No immediate candidate prepared"
    prepared_facts = handoff_facts(
        ("description", "Device", device.get("description") or "Phone"),
        ("cost", "Cost", device.get("cost")),
        ("purchase-date", "Purchase date", device.get("purchase_date")),
        ("work-use", "Work-use percentage", device.get("work_use_percent")),
        ("work-use-amount", "Prepared work-use amount", work_amount),
        ("receipt", "Receipt or tax invoice", device.get("receipt")),
        ("method", "Method preference", device.get("method_preference")),
        ("effective-life", "Effective life", device.get("effective_life_years")),
        ("set-test", "Set or substantially identical", device.get("set_or_substantially_identical")),
        ("changed-use", "Changed-use facts", device.get("work_use_percent_changed")),
        ("treatment", "Prepared treatment", treatment_fact),
    )
    if treatment_boundary:
        prepared_facts.extend(
            handoff_facts(
                ("treatment-boundary", "Prepared treatment boundary", treatment_boundary),
            )
        )
    answer = (
        f"{display_value(device.get('description')) or 'phone'}; cost {money_text(cost)}; purchase date {display_value(device.get('purchase_date'))}; "
        f"work use {percent_text(work_use)}; work-use amount {money_text(work_amount)}; receipt {display_value(device.get('receipt'))}; "
        f"method {display_value(device.get('method_preference'))}; effective life {display_value(device.get('effective_life_years'))}; "
        f"set/substantially-identical {display_value(device.get('set_or_substantially_identical'))}; changed-use facts {display_value(device.get('work_use_percent_changed'))}; {treatment}"
    )
    rows = [
        guide_row(
            "PHONE-DEVICE",
            "D5 Other work-related expenses" if not phone_abn_context(raw, answers) else "ABN/GST/BAS phone review",
            "Phone handset/device",
            answer,
            "Phone device costs need purchase evidence, work/private apportionment, $300 threshold checks, set/substantially-identical checks, and depreciation method review.",
            status,
            phone_sources(raw, answers),
            tab_text=phone_device_tab_text(blocked, evidence_gap, cost),
            row_kind="deduction",
            facts=prepared_facts,
        )
    ]
    if "insurance_amount" in device:
        insurance = phone_nonnegative_money_value(device.get("insurance_amount"))
        insurance_work = None if insurance is None or work_use is None else round(insurance * work_use / 100, 2)
        insurance_status = "Evidence" if insurance is None or evidence_missing(device.get("receipt")) else "Accountant review"
        insurance_answer = f"insurance {money_text(insurance)}; work use {percent_text(work_use)}; work portion {money_text(insurance_work)}; evidence {display_value(device.get('receipt'))}"
        insurance_tab = "Phone insurance needs evidence and private-use apportionment."
        if blocked:
            insurance_status = "Accountant review"
            insurance_answer = f"{insurance_answer}; blocked: {', '.join(blocked)}"
            insurance_tab = "Phone insurance blocked: " + ", ".join(blocked) + "."
        rows.append(
            guide_row(
                "PHONE-INS",
                "D5 Other work-related expenses" if not phone_abn_context(raw, answers) else "ABN/GST/BAS phone review",
                "Phone insurance",
                insurance_answer,
                "Phone insurance is only a prep-only work-related portion where the user paid it, evidence exists, and private use is apportioned.",
                insurance_status,
                phone_sources(raw, answers),
                tab_text=insurance_tab,
                row_kind="deduction",
                facts=handoff_facts(
                    ("insurance-amount", "Insurance amount", device.get("insurance_amount")),
                    ("work-use", "Work-use percentage", device.get("work_use_percent")),
                    ("work-portion", "Prepared work-use portion", insurance_work),
                    ("evidence", "Evidence", device.get("receipt")),
                    ("blocking-facts", "Blocking facts", ", ".join(blocked) or "none"),
                ),
            )
        )
    return rows


def phone_incidental_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    incidental = raw.get("incidental") if isinstance(raw.get("incidental"), dict) else {}
    if not has_meaningful_value(incidental):
        return []
    supplied = phone_nonnegative_money_value(incidental.get("claim_amount"))
    raw_calls = phone_nonnegative_money_value(incidental.get("work_calls"))
    raw_texts = phone_nonnegative_money_value(incidental.get("work_texts"))
    missing_usage = supplied is None and (raw_calls is None or raw_texts is None)
    calculated = None if missing_usage else round((raw_calls or 0) * 0.75 + (raw_texts or 0) * 0.10, 2)
    amount = supplied if supplied is not None else calculated
    blocked = phone_plan_blocked(raw)
    evidence_gap = evidence_missing(incidental.get("basic_records")) or missing_usage
    over_limit = amount is not None and amount > 50
    status = "Accountant review"
    if evidence_gap or amount is None or over_limit:
        status = "Evidence"
    if blocked:
        status = "Accountant review"
    answer = (
        f"claim {money_text(amount)}; supplied {money_text(supplied)}; work calls {money_text(raw_calls)}; work texts {money_text(raw_texts)}; "
        f"basic records {display_value(incidental.get('basic_records'))}; rate basis 0.75 per work mobile call and 0.10 per work text"
    )
    if blocked:
        answer = f"{answer}; blocked: {', '.join(blocked)}"
    elif over_limit:
        answer = f"{answer}; over $50 incidental threshold needs detailed phone-plan evidence"
    tab_text = "Incidental phone use needs basic records and fixed-rate duplicate-claim review."
    if blocked:
        tab_text = "Incidental phone use blocked: " + ", ".join(blocked) + "."
    return [
        guide_row(
            "PHONE-INC",
            "D5 Other work-related expenses" if not phone_abn_context(raw, answers) else "ABN/GST/BAS phone review",
            "Incidental phone use",
            answer,
            "Incidental phone/data claims of $50 or less can use basic records, but WFH fixed-rate still blocks a separate phone/data claim.",
            status,
            phone_sources(raw, answers),
            tab_text=tab_text,
            row_kind="deduction",
            facts=handoff_facts(
                ("claim-amount", "Prepared claim amount", amount),
                ("supplied-amount", "Claim amount supplied", incidental.get("claim_amount")),
                ("work-calls", "Work calls", incidental.get("work_calls")),
                ("work-texts", "Work texts", incidental.get("work_texts")),
                ("basic-records", "Basic records", incidental.get("basic_records")),
                ("rate-basis", "Rate basis", "$0.75 per work mobile call and $0.10 per work text"),
                ("blocking-facts", "Blocking facts", ", ".join(blocked) or "none"),
            ),
        )
    ]


def phone_evidence_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not has_phone_inputs(raw):
        return []
    rows: List[Dict[str, Any]] = []
    plan = raw.get("plan") if isinstance(raw.get("plan"), dict) else {}
    device = raw.get("device") if isinstance(raw.get("device"), dict) else {}
    incidental = raw.get("incidental") if isinstance(raw.get("incidental"), dict) else {}
    if has_meaningful_value(plan):
        if evidence_missing(plan.get("bills")):
            rows.append(phone_evidence_row(len(rows) + 1, "Phone bills or prepaid receipts", raw, answers))
        if evidence_missing(plan.get("log")) or is_missing(plan.get("representative_period_start")) or is_missing(plan.get("representative_period_end")):
            rows.append(phone_evidence_row(len(rows) + 1, "4-week phone work/private usage log, diary, or calendar", raw, answers))
    if has_meaningful_value(device) and evidence_missing(device.get("receipt")):
        rows.append(phone_evidence_row(len(rows) + 1, "Phone handset receipt or tax invoice", raw, answers))
    if has_meaningful_value(incidental) and evidence_missing(incidental.get("basic_records")):
        rows.append(phone_evidence_row(len(rows) + 1, "Incidental phone basic records", raw, answers))
    if (
        has_meaningful_value(incidental)
        and phone_nonnegative_money_value(incidental.get("claim_amount")) is None
        and (
            phone_nonnegative_money_value(incidental.get("work_calls")) is None
            or phone_nonnegative_money_value(incidental.get("work_texts")) is None
        )
    ):
        rows.append(phone_evidence_row(len(rows) + 1, "Incidental phone call/text counts or supplied claim amount", raw, answers))
    if has_meaningful_value(raw.get("freeform")):
        rows.append(phone_evidence_row(len(rows) + 1, "Structured phone cost, work-use, and evidence details for free-form phone fact", raw, answers))
    if phone_abn_context(raw, answers) and phone_gst_registered(raw, answers):
        rows.append(phone_evidence_row(len(rows) + 1, "GST tax invoice and GST-credit basis for phone costs", raw, answers))
    elif phone_abn_context(raw, answers) and phone_gst_registration_unknown(raw, answers):
        rows.append(phone_evidence_row(len(rows) + 1, "GST registration status for phone GST-credit review", raw, answers))
    return rows


def phone_evidence_row(index: int, evidence: str, raw: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    return guide_row(
        f"PHONE-EVID-{index}",
        "Phone deduction evidence",
        "Phone evidence required",
        evidence,
        "Phone rows stay prep-only until bills, receipts, records, and review facts are confirmed.",
        "Evidence",
        phone_sources(raw, answers),
        row_kind="evidence-queue",
        facts=handoff_facts(
            ("evidence-needed", "Phone evidence needed", evidence),
        ),
    )


def phone_context(raw: Dict[str, Any], answers: Dict[str, Any]) -> str:
    context = display_value(raw.get("context")).strip().lower()
    if context:
        return context
    if phone_context_is_abn(display_value(raw.get("freeform")).strip().lower()):
        return "abn"
    return "abn" if has_abn_inputs(answers) or has_bas_inputs(answers) else "employee"


def phone_abn_context(raw: Dict[str, Any], answers: Dict[str, Any]) -> bool:
    context = phone_context(raw, answers)
    if context:
        return phone_context_is_abn(context)
    return has_abn_inputs(answers) or has_bas_inputs(answers)


def phone_context_is_abn(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    if phone_context_has_negated_abn(normalized):
        return False
    if phone_context_has_business_uncertainty(normalized):
        return False
    tokens = set(normalized.split())
    if value in {"abn", "business", "sole trader", "sole-trader", "both"}:
        return True
    return (
        "abn" in tokens
        or "business" in tokens
        or {"sole", "trader"}.issubset(tokens)
        or {"self", "employed"}.issubset(tokens)
    )


def phone_context_has_negated_abn(normalized: str) -> bool:
    business_context = r"(abn|business|sole\s+trader|self\s+employed)"
    return bool(
        re.search(rf"\b(not|no|without)\b(?:\s+\w+){{0,3}}\s+(a\s+|an\s+)?\b{business_context}\b", normalized)
        or re.search(rf"\bnon\s+{business_context}\b", normalized)
    )


def phone_context_has_business_uncertainty(normalized: str) -> bool:
    if re.search(r"\b(not sure|unsure|uncertain|maybe|possibly|whether|question)\b", normalized):
        return True
    tokens = set(normalized.split())
    business_terms = {"abn", "business", "sole", "trader", "self", "employed"}
    return "if" in tokens and bool(tokens.intersection(business_terms))


def phone_context_is_employee(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    tokens = set(normalized.split())
    if phone_context_is_abn(value):
        return False
    if phone_context_has_business_uncertainty(normalized) and "only" not in tokens:
        return False
    return bool(normalized) and (
        phone_context_has_negated_abn(normalized)
        or "employee" in tokens
    )


def phone_freeform_present(value: Any) -> bool:
    return not is_missing(value) and not phone_freeform_absent(value)


def phone_freeform_absent(value: Any) -> bool:
    if value is False:
        return True
    lowered = display_value(value).strip().lower()
    if lowered in {"no", "none", "false", "not applicable", "n/a", "no phone claim", "no phone deduction", "no mobile claim"}:
        return True
    normalized = re.sub(r"[^a-z0-9]+", " ", lowered).strip()
    if re.search(r"\b(not sure|unsure|uncertain|whether|can i|could i|no idea|unknown|question)\b", normalized):
        return False
    if phone_freeform_mixed_use(normalized):
        return False
    subject = r"(phone|mobile|internet|device|handset)"
    claim_word = r"(claim|claimed|claiming|deduction|expense|expenses|cost|costs)"
    no_word = r"no(?!\s+idea)"
    opt_out_patterns = (
        rf"\b({no_word}|without)\b.*\b{subject}\b.*\b{claim_word}\b",
        rf"\b({no_word}|without)\b.*\b{claim_word}\b.*\b{subject}\b",
        rf"\b(dont|don t|do not|didnt|didn t|did not|not going to|not gonna|not planning to)\b.*\b{claim_word}\b.*\b{subject}\b",
        rf"\bnot\s+(claim|claimed|claiming|deducting)\b.*\b{subject}\b",
        rf"\b{subject}\b.*\b{claim_word}\b.*\b(none|nil|zero)\b",
        rf"\b{subject}\b.*\b(not|never)\b.*\b(claimed|claiming|used)\b",
        rf"\b{subject}\b.*\b(not|never)\b.*\b(deductible|allowed|allowable)\b",
        rf"\bnot eligible\b.*\b{subject}\b.*\b{claim_word}\b",
        rf"\b{subject}\b.*\b{claim_word}\b.*\bnot eligible\b",
        rf"\b{subject}\b.*\b{claim_word}\b.*\b(not allowed|not allowable)\b",
    )
    if any(re.search(pattern, normalized) for pattern in opt_out_patterns):
        return True
    return False


def phone_freeform_mixed_use(normalized: str) -> bool:
    subject = r"(phone|mobile|internet|device|handset)"
    work_context = r"(work|business|employment|job)"
    exclusive = r"(only|exclusively|solely|wholly|100)"
    return bool(
        re.search(r"\bmixed\s+use\b|\bmixed\s+business\s+and\s+private\b", normalized)
        or re.search(r"\b(private|personal)\s+use\b", normalized)
        or re.search(r"\b(partly|partially)\s+(private|personal|work|business)\b", normalized)
        or re.search(rf"\b{subject}\b.*\bnot\b.*\bused\b.*\b{exclusive}\b.*\b{work_context}\b", normalized)
        or re.search(rf"\b{subject}\b.*\bnot\b.*\b{exclusive}\b.*\b{work_context}\b", normalized)
        or re.search(rf"\bnot\b.*\b{exclusive}\b.*\b{work_context}\b.*\b{subject}\b", normalized)
    )


def phone_gst_registered(raw: Dict[str, Any], answers: Dict[str, Any]) -> bool:
    return parse_gst_registration(phone_gst_registration_value(raw, answers)) is True


def phone_gst_registration_unknown(raw: Dict[str, Any], answers: Dict[str, Any]) -> bool:
    value = phone_gst_registration_value(raw, answers)
    return is_missing(value) or parse_gst_registration(value) is None


def phone_gst_registration_value(raw: Dict[str, Any], answers: Dict[str, Any]) -> Any:
    gst = first_alias_value(raw, PHONE_GST_STATUS_KEYS)
    if is_missing(gst):
        return bas_gst_registration_answer(answers)
    return gst


def phone_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if is_missing(value) or contains_unknown(value):
        return None
    lowered = text(value).strip().lower()
    if lowered in {"yes", "y", "true", "1", "on", "checked", "held", "itemised", "itemized"}:
        return True
    if lowered in {"no", "n", "false", "0", "off", "unchecked", "none", "not applicable", "n/a", "non-itemised", "non-itemized"}:
        return False
    return None


def phone_wfh_fixed_rate(raw: Dict[str, Any]) -> bool:
    return phone_wfh_fixed_rate_value(raw.get("wfh_method"))


def phone_wfh_fixed_rate_value(value: Any) -> bool:
    method = display_value(value).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", method.replace("_", " ").replace("-", " ")).strip()
    if "?" in method:
        return False
    if re.search(r"\b(not sure|unsure|uncertain|maybe|possibly|whether|if|no idea|unknown)\b", normalized):
        return False
    negative_patterns = (
        r"\b(not|no|without|dont|don t|didnt|didn t|did not)\b.*\bfixed\b.*\brate\b",
        r"\bfixed\b.*\brate\b.*\b(n a|not applicable)\b",
        r"\bfixed\b.*\brate\b.*\b(no|n|false|off|unchecked)\b",
        r"\bfixed\b.*\brate\b.*\b(not|never)\b.*\b(used|claimed|claiming|applicable|selected|chosen|elected|opted)\b",
        r"\binstead\b.*\bof\b.*\bfixed\b.*\brate\b",
        r"\brather\b.*\bthan\b.*\bfixed\b.*\brate\b",
        r"\b(not|no|without|dont|don t|didnt|didn t|did not)\b.*\b(70 cents?|70c per|70 c per)\b",
        r"\b(70 cents?|70c per|70 c per)\b.*\b(n a|not applicable)\b",
        r"\b(70 cents?|70c|70 c|70c per|70 c per)\b.*\b(no|n|false|off|unchecked)\b",
        r"\b(70 cents?|70c per|70 c per)\b.*\b(not|never)\b.*\b(used|claimed|claiming|applicable|selected|chosen|elected|opted)\b",
    )
    if any(re.search(pattern, normalized) for pattern in negative_patterns):
        return False
    if "70" in normalized and ("cent" in normalized or "c per" in normalized or re.search(r"\b70\s*c\b", normalized)):
        return True
    return normalized in {"fixed", "fixed rate", "fixed rate method"} or ("fixed" in normalized and "rate" in normalized)


def phone_flag_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", display_value(value).strip().lower()).strip()


def phone_text_has_affirmed_marker(normalized: str, markers: tuple[str, ...]) -> bool:
    return any(
        not phone_marker_match_negated(normalized, marker, match)
        for marker in markers
        for match in re.finditer(rf"\b{marker}\b", normalized)
    )


def phone_marker_match_negated(normalized: str, marker: str, match: re.Match[str]) -> bool:
    lead = normalized[: match.start()]
    leading = re.search(
        rf"\b{PHONE_TEXT_NEGATION_PATTERN}\b(?P<target>(?:\s+\w+){{0,4}})\s*$",
        lead,
    )
    if leading:
        if phone_negation_targets_other_employer_marker(leading.group("target"), marker):
            return False
        return True
    tail = normalized[match.end() :]
    trailing = re.match(rf"(?:\s+\w+){{0,4}}\s+\b{PHONE_TEXT_NEGATION_PATTERN}\b", tail)
    if not trailing:
        return False
    negated_target = tail[trailing.end() :]
    return not phone_negation_targets_other_employer_marker(negated_target, marker)


def phone_negation_targets_other_employer_marker(text_value: str, current_marker: str) -> bool:
    current_kind = phone_employer_marker_kind(current_marker)
    for marker in PHONE_EMPLOYER_MARKERS:
        if marker == current_marker:
            continue
        if re.search(rf"^\s*(?:\w+\s+){{0,3}}\b{marker}\b", text_value):
            return phone_employer_marker_kind(marker) != current_kind
    return False


def phone_employer_marker_kind(marker: str) -> str:
    for kind, markers in PHONE_EMPLOYER_MARKER_GROUPS:
        if marker in markers:
            return kind
    return marker


def phone_user_paid_false(value: Any) -> bool:
    parsed = phone_bool(value)
    if parsed is not None:
        return parsed is False
    normalized = phone_flag_text(value)
    if phone_user_paid_unanswered_text(normalized):
        return False
    if re.match(r"^(no|n|false|off|unchecked)\b", normalized):
        return True
    if not normalized:
        return False
    if re.search(r"\b(not|never|did not|dont|don t|didnt|didn t)\b(?:\s+\w+){0,3}\s+\b(pay|paid)\b", normalized):
        return True
    return phone_text_has_affirmed_marker(normalized, PHONE_EMPLOYER_MARKERS)


def phone_user_paid_unanswered_text(normalized: str) -> bool:
    if not re.match(r"^no\b", normalized):
        return False
    missing_markers = (
        "answer",
        "response",
        "reply",
        "information",
        "info",
        "detail",
        "details",
        "data",
        "value",
        "confirmation",
    )
    return any(re.search(rf"\b{marker}\b", normalized) for marker in missing_markers)


def phone_employer_flag_true(value: Any, markers: tuple[str, ...]) -> bool:
    parsed = phone_bool(value)
    if parsed is not None:
        return parsed is True
    normalized = phone_flag_text(value)
    return bool(normalized) and phone_text_has_affirmed_marker(normalized, markers)


def phone_employee_excluded(raw: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    if phone_user_paid_false(raw.get("paid_by_user")):
        terms.append("not paid by user")
    if phone_employer_flag_true(raw.get("employer_reimbursed"), PHONE_EMPLOYER_REIMBURSED_MARKERS):
        terms.append("employer reimbursed")
    if phone_employer_flag_true(raw.get("employer_paid"), PHONE_EMPLOYER_PAID_MARKERS):
        terms.append("employer paid")
    if phone_employer_flag_true(raw.get("employer_provided"), PHONE_EMPLOYER_PROVIDED_MARKERS):
        terms.append("employer provided")
    return terms


def phone_blocking_terms(raw: Dict[str, Any]) -> List[str]:
    terms = phone_employee_excluded(raw)
    if phone_wfh_fixed_rate(raw):
        terms.append("WFH fixed-rate duplicate-claim risk")
    return terms


def phone_plan_blocked(raw: Dict[str, Any]) -> List[str]:
    terms = phone_employee_excluded(raw)
    if phone_wfh_fixed_rate(raw):
        terms.append("WFH fixed-rate covers phone/data")
    return terms


def phone_device_blocked(raw: Dict[str, Any]) -> List[str]:
    return phone_employee_excluded(raw)


def phone_plan_evidence_gap(plan: Dict[str, Any]) -> bool:
    itemised = phone_bool(plan.get("itemised_bill"))
    if (
        phone_nonnegative_money_value(plan.get("monthly_cost")) is None
        or phone_months_claimed_value(plan.get("months_claimed")) is None
    ):
        return True
    if phone_percent_value(plan.get("work_use_percent")) is None:
        return True
    if evidence_missing(plan.get("bills")):
        return True
    if itemised is False or phone_bool(plan.get("prepaid")) is True:
        return evidence_missing(plan.get("log"))
    return is_missing(plan.get("representative_period_start")) or is_missing(plan.get("representative_period_end")) or evidence_missing(plan.get("log"))


def phone_device_evidence_gap(device: Dict[str, Any]) -> bool:
    return (
        phone_nonnegative_money_value(device.get("cost")) is None
        or phone_percent_value(device.get("work_use_percent")) is None
        or evidence_missing(device.get("receipt"))
    )


def phone_under_300_candidate(device: Dict[str, Any], cost: Optional[float], work_use: Optional[float]) -> bool:
    if cost is None or work_use is None or cost > 300 or work_use <= 50:
        return False
    set_rule = phone_bool(device.get("set_or_substantially_identical"))
    more_than_half = phone_bool(device.get("more_than_50_percent_work_use"))
    return set_rule is False and (more_than_half is True or work_use > 50)


def phone_percent_value(value: Any) -> Optional[float]:
    parsed = None
    had_percent_suffix = False
    if isinstance(value, str):
        lowered = value.strip().lower()
        for suffix in ("%", " percent", " per cent"):
            if lowered.endswith(suffix):
                had_percent_suffix = True
                parsed = safe_money_value(lowered[: -len(suffix)].strip())
                break
    if parsed is None:
        parsed = safe_money_value(value)
    if isinstance(value, str) and not had_percent_suffix and parsed is not None and 0 < parsed < 1:
        return None
    if parsed is None or parsed < 0 or parsed > 100:
        return None
    return parsed


def phone_nonnegative_money_value(value: Any) -> Optional[float]:
    parsed = safe_money_value(value)
    if parsed is None:
        parsed = phone_number_with_unit_value(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


def phone_number_with_unit_value(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    unit_pattern = r"(\$|\baud\b|\bdollars?\b|\bper month\b|\bmonthly\b|\bmonths?\b|\bcalls?\b|\btexts?\b)"
    if not re.search(unit_pattern, lowered):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", lowered.replace(",", ""))
    if not match:
        return None
    return float(match.group(0))


def phone_months_claimed_value(value: Any) -> Optional[float]:
    parsed = phone_nonnegative_money_value(value)
    if parsed is None or parsed > 12:
        return None
    return parsed


def phone_plan_tab_text(blocked: List[str], evidence_gap: bool) -> str:
    if blocked:
        return "Phone plan blocked: " + ", ".join(blocked) + "."
    if evidence_gap:
        return "Phone plan needs bills and 4-week work/private records."
    return "Phone plan candidate stays prep-only and requires accountant review before entry."


def phone_device_tab_text(blocked: List[str], evidence_gap: bool, cost: Optional[float]) -> str:
    if blocked:
        return "Phone device blocked: " + ", ".join(blocked) + "."
    if evidence_gap:
        return "Phone device needs receipt, cost, and work-use evidence."
    if cost is not None and cost > 300:
        return "Phone over $300 needs decline-in-value method/effective-life accountant review."
    return "Phone $300 or less needs set/substantially-identical and work-use review."


def phone_sources(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[str]:
    sources = list(ATO_PHONE_SOURCES)
    if phone_abn_context(raw, answers):
        sources.extend([ATO_BUSINESS_DEPRECIATING_ASSETS_SOURCE, ATO_GST_CREDITS_SOURCE, ATO_TAX_INVOICES_SOURCE])
    return sources


def abn_business_evidence_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not has_abn_inputs(answers):
        return []
    summary = abn_summary(answers)
    rows: List[Dict[str, Any]] = []
    if summary.get("amount_evidence"):
        rows.append(
            guide_row(
                "ABN-EVID-1",
                "Sole-trader ABN",
                "ABN amount evidence required",
                "Confirm malformed or unknown business income and expense amounts before entry.",
                "ABN income and expense rows are not ready for entry until amount records are reconciled.",
                "Evidence",
                ATO_ABN_BUSINESS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("evidence-needed", "Evidence needed", "Business income and expense amount records"),
                ),
            )
        )
    if summary.get("alias_conflict"):
        rows.append(
            guide_row(
                f"ABN-EVID-{len(rows) + 1}",
                "Sole-trader ABN",
                "ABN alias reconciliation required",
                "Reconcile conflicting ABN aliases: " + ", ".join(str(key).replace("_", " ") for key in summary.get("alias_conflicts", [])) + ".",
                "Conflicting ABN aliases stay Evidence until source records show which business fact should be used.",
                "Evidence",
                ATO_ABN_BUSINESS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("conflicting-aliases", "Conflicting ABN aliases", ", ".join(str(key).replace("_", " ") for key in summary.get("alias_conflicts", []))),
                ),
            )
        )
    item_gaps = [
        item_label(item)
        for item in summary.get("income_streams", []) + summary.get("expense_categories", [])
        if evidence_missing(item_evidence_value(item))
    ]
    if item_gaps:
        rows.append(
            guide_row(
                f"ABN-EVID-{len(rows) + 1}",
                "Sole-trader ABN",
                "ABN income or expense evidence required",
                f"Confirm invoices, receipts, statements, or records for {', '.join(item_gaps[:6])}.",
                "Itemized business income and expense rows need evidence before accountant review.",
                "Evidence",
                ATO_ABN_BUSINESS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("items-needing-evidence", "Income or expense items needing evidence", ", ".join(item_gaps[:6])),
                ),
            )
        )
    if summary.get("record_evidence"):
        rows.append(
            guide_row(
                f"ABN-EVID-{len(rows) + 1}",
                "Sole-trader ABN",
                "ABN record system evidence required",
                "Confirm the bookkeeping or record system used for the business period.",
                "Record-system gaps remain Evidence for the business schedule workflow.",
                "Evidence",
                ATO_ABN_BUSINESS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("record-system", "Record system needed", summary.get("record_system")),
                ),
            )
        )
    return rows


def bas_evidence_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not has_bas_inputs(answers):
        return []
    summary = bas_summary(answers)
    rows: List[Dict[str, Any]] = []
    if any(summary.get(f"{key}_malformed") for key in BAS_AMOUNT_FIELDS):
        rows.append(
            guide_row(
                "BAS-EVID-1",
                "BAS worksheet",
                "BAS amount evidence required",
                "Confirm malformed or unknown BAS label amounts before entry.",
                "BAS label rows are not ready for entry until 1A, 1B, GST-free/input-taxed, adjustment, and PAYG amounts are reconciled.",
                "Evidence",
                ATO_BAS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("amounts", "BAS amounts needing evidence", "1A, 1B, GST-free/input-taxed sales, adjustments, or PAYG amounts"),
                ),
            )
        )
    if summary.get("alias_conflict"):
        rows.append(
            guide_row(
                f"BAS-EVID-{len(rows) + 1}",
                "BAS worksheet",
                "BAS alias reconciliation required",
                "Reconcile conflicting BAS aliases: " + ", ".join(str(key).replace("_", " ") for key in summary.get("alias_conflicts", [])) + ".",
                "Conflicting BAS aliases keep worksheet labels unknown until source records show which amount or fact should be used.",
                "Evidence",
                ATO_BAS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("conflicting-aliases", "Conflicting BAS aliases", ", ".join(str(key).replace("_", " ") for key in summary.get("alias_conflicts", []))),
                ),
            )
        )
    if summary.get("invoice_evidence"):
        rows.append(
            guide_row(
                f"BAS-EVID-{len(rows) + 1}",
                "BAS worksheet",
                "GST credit tax invoice evidence required",
                "GST credits were supplied but tax invoice evidence is missing or unknown.",
                "GST credits need valid tax invoice and creditable-purpose evidence before manual BAS use.",
                "Evidence",
                ATO_BAS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("tax-invoice-evidence", "Tax invoice evidence", summary.get("tax_invoice_evidence")),
                    ("gst-credits", "GST credits supplied", summary.get("gst_credits_amount")),
                ),
            )
        )
    if summary.get("basis_evidence"):
        rows.append(
            guide_row(
                f"BAS-EVID-{len(rows) + 1}",
                "BAS worksheet",
                "GST accounting basis evidence required",
                "Confirm cash or non-cash accounting basis for the BAS period.",
                "Unknown GST accounting basis stays visible before any manual BAS worksheet use.",
                "Evidence",
                ATO_BAS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("accounting-basis", "Accounting basis", summary.get("accounting_basis")),
                ),
            )
        )
    if summary.get("period_coverage_evidence"):
        rows.append(
            guide_row(
                f"BAS-EVID-{len(rows) + 1}",
                "BAS worksheet",
                "BAS period coverage evidence required",
                "Confirm whether the supplied BAS facts cover the full period.",
                "Unknown BAS period coverage stays visible before any manual BAS worksheet use.",
                "Evidence",
                ATO_BAS_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("period", "BAS period", summary.get("period")),
                    ("period-coverage", "Period coverage", summary.get("period_coverage")),
                ),
            )
        )
    return rows


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
            tab_text="WFH amount is not ready for entry without records and method review.",
            row_kind="deduction",
            facts=handoff_facts(
                ("hours", "Work-from-home hours", hours if hours is not None else "unknown"),
                (
                    "fixed-rate-candidate",
                    "Prepared fixed-rate candidate",
                    fixed_candidate if fixed_candidate is not None else "unknown",
                ),
                ("work-records", "Work records", records),
                ("actual-cost-records", "Actual-cost records", actual_cost_record_value),
                ("method", "Method", raw.get("method") or raw.get("method_preference")),
            ),
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
        work_amount = None if cost is None or work_use is None else round(cost * work_use / 100, 2)
        treatment = asset_fact_treatment(cost, work_use)
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
                tab_text="Asset treatment needs evidence and method review before entry.",
                row_kind="deduction",
                facts=handoff_facts(
                    ("description", "Asset", asset.get("description")),
                    ("cost", "Cost", asset.get("cost")),
                    ("work-use", "Work-use percentage", asset.get("work_use_percent")),
                    ("work-use-amount", "Prepared work-use amount", work_amount),
                    ("method", "Method preference", asset.get("method_preference")),
                    ("evidence", "Evidence", asset.get("evidence")),
                    ("prepared-treatment", "Prepared treatment", treatment),
                ),
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


def investment_flat_field_key(key: str) -> str:
    mapping = {
        "investment_interest_items": "interest_items",
        "investment_dividend_items": "dividend_items",
        "investment_distribution_items": "distribution_items",
        "trust_distribution_items": "trust_distribution_items",
    }
    return mapping.get(key, key)


def investment_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("investment_income")
    merged: Dict[str, Any] = dict(raw) if isinstance(raw, dict) else {}
    aggregate_conflicts: List[str] = list(merged.get("_aggregate_conflicts") or [])
    item_conflicts: List[str] = list(merged.get("_item_conflicts") or [])
    for target, aliases in INVESTMENT_AGGREGATE_ALIASES.items():
        if investment_aggregate_record_conflict(merged, aliases) or investment_aggregate_record_conflict(answers, aliases):
            aggregate_conflicts.append(target)
        nested_value = first_present(merged, aliases)
        answer_value = first_present(answers, aliases)
        if not is_missing(nested_value) and not is_missing(answer_value) and investment_aggregate_values_conflict(nested_value, answer_value):
            aggregate_conflicts.append(target)
        value = nested_value
        if is_missing(value):
            value = answer_value
        if not is_missing(value) and is_missing(merged.get(target)):
            merged[target] = value
    if aggregate_conflicts:
        merged["_aggregate_conflicts"] = sorted(set(aggregate_conflicts))
    for key, source_keys in INVESTMENT_ITEM_ALIASES.items():
        nested_value = first_investment_items(merged, source_keys)
        answer_value = first_investment_items(answers, source_keys)
        if investment_item_alias_record_conflict(merged, source_keys) or investment_item_alias_record_conflict(answers, source_keys):
            item_conflicts.append(key)
        if investment_item_values(nested_value) and investment_item_values(answer_value) and investment_items_conflict(nested_value, answer_value):
            item_conflicts.append(key)
        value = nested_value if investment_item_values(nested_value) else answer_value
        if not investment_item_values(merged.get(key)) and investment_item_values(value):
            merged[key] = value
    if item_conflicts:
        merged["_item_conflicts"] = sorted(set(item_conflicts))
    return merged


def investment_aggregate_alias_values(record: Dict[str, Any], aliases: tuple[str, ...]) -> List[Any]:
    return [record.get(alias) for alias in aliases if not is_missing(record.get(alias))]


def investment_aggregate_record_conflict(record: Dict[str, Any], aliases: tuple[str, ...]) -> bool:
    values = investment_aggregate_alias_values(record, aliases)
    if len(values) < 2:
        return False
    first = values[0]
    return any(investment_aggregate_values_conflict(first, value) for value in values[1:])


def investment_aggregate_values_conflict(left: Any, right: Any) -> bool:
    if is_missing(left) or is_missing(right):
        return False
    left_amount = investment_money_value(left)
    right_amount = investment_money_value(right)
    if left_amount is None or right_amount is None:
        return True
    return round(abs(left_amount - right_amount), 2) >= 0.01


def investment_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    interest_items = investment_item_values(raw.get("interest_items"))
    dividend_items = investment_item_values(raw.get("dividend_items"))
    distribution_items = investment_item_values(raw.get("distribution_items"))
    trust_items = investment_item_values(raw.get("trust_distribution_items"))
    item_conflicts = investment_item_conflict_keys(raw)
    has_interest_items = bool(interest_items)
    has_dividend_distribution_items = bool(dividend_items or distribution_items)
    interest_total = interest_category_total(interest_items)
    dividend_total = dividend_distribution_category_total(dividend_items, distribution_items)
    interest_conflict = investment_aggregate_alias_conflict(raw, "interest_income") or investment_reconciliation_conflict(
        investment_aggregate_value(raw, "interest_income"),
        interest_total,
        has_interest_items,
    ) or "interest_items" in item_conflicts
    dividend_conflict = investment_aggregate_alias_conflict(raw, "dividend_income") or investment_reconciliation_conflict(
        investment_aggregate_value(raw, "dividend_income"),
        dividend_total,
        has_dividend_distribution_items,
    ) or bool(item_conflicts.intersection({"dividend_items", "distribution_items"}))
    for idx, item in enumerate(interest_items, start=1):
        rows.append(investment_interest_row(idx, item, interest_conflict))
    for idx, item in enumerate(dividend_items, start=1):
        rows.append(investment_dividend_row(idx, item, dividend_conflict))
    for idx, item in enumerate(distribution_items, start=1):
        rows.append(investment_distribution_row(idx, item, dividend_conflict))
    for idx, item in enumerate(trust_items, start=1):
        rows.append(investment_trust_row(idx, item))
    if investment_has_reconciliation_target(raw, interest_items, dividend_items, distribution_items):
        rows.append(
            investment_reconciliation_row(
                raw,
                interest_items,
                dividend_items,
                distribution_items,
                interest_conflict,
                dividend_conflict,
            )
        )
    return rows


def investment_item_conflict_keys(raw: Dict[str, Any]) -> set[str]:
    conflicts = raw.get("_item_conflicts")
    if not isinstance(conflicts, list):
        return set()
    return {conflict for conflict in conflicts if isinstance(conflict, str)}


def investment_interest_row(index: int, item: Dict[str, Any], conflict: bool) -> Dict[str, Any]:
    amount_evidence = investment_amounts_need_evidence(
        item,
        INVESTMENT_INTEREST_AMOUNT_FIELDS,
        INVESTMENT_INTEREST_REQUIRED_AMOUNT_GROUPS,
    )
    statement_evidence = investment_statement_missing(item.get("statement"))
    status = "Evidence" if statement_evidence or amount_evidence or conflict else "Accountant review"
    return guide_row(
        f"INT-{index}",
        "10 Gross interest",
        "Bank interest statement item",
        (
            f"Payer {investment_display_text(item, 'payer')}; account {investment_display_text(item, 'account')}; "
            f"interest {money_text(investment_money_value(item.get('amount')))}; "
            f"TFN withholding {money_text(investment_money_value(item.get('tfn_withheld')))}"
        ),
        "Itemized bank interest is prep-only and needs statement support before entry.",
        status,
        INVESTMENT_SOURCES[:2],
        tab_text=investment_tab_text("Bank interest", evidence_terms(statement_evidence, amount_evidence, conflict), []),
        row_kind="investment",
        facts=handoff_facts(
            ("payer", "Payer", item.get("payer")),
            ("account", "Account", item.get("account")),
            ("interest", "Gross interest", item.get("amount")),
            ("tfn-withholding", "TFN withholding", item.get("tfn_withheld")),
            ("statement", "Statement evidence", item.get("statement")),
            (
                "alias-conflicts",
                "Alias conflicts",
                (", ".join(item.get("_alias_conflicts", [])) or "none")
                if isinstance(item.get("_alias_conflicts"), list)
                else "none",
            ),
        ),
    )


def investment_dividend_row(index: int, item: Dict[str, Any], conflict: bool) -> Dict[str, Any]:
    amount_evidence = dividend_amounts_need_evidence(item) or investment_amounts_need_evidence(
        item,
        INVESTMENT_DIVIDEND_AMOUNT_FIELDS,
        INVESTMENT_DIVIDEND_REQUIRED_AMOUNT_GROUPS,
        franked_key="franked_amount",
    )
    statement_evidence = investment_statement_missing(item.get("statement"))
    franking_evidence = investment_franking_uncertain(item)
    reviews = investment_review_terms(item, include_trust=False)
    status = "Evidence" if statement_evidence or amount_evidence or franking_evidence or conflict else "Accountant review"
    return guide_row(
        f"DIV-{index}",
        "11 Dividends",
        "Dividend and franking statement item",
        (
            f"Security {investment_label_text(item)}; cash dividend {money_text(dividend_item_total(item))}; "
            f"franked {money_text(investment_money_value(item.get('franked_amount')))}; "
            f"unfranked {money_text(investment_money_value(item.get('unfranked_amount')))}; "
            f"franking credit {money_text(investment_money_value(item.get('franking_credit')))}; "
            f"TFN withholding {money_text(investment_money_value(item.get('tfn_withheld')))}"
        ),
        "Dividend rows preserve franking credits and withholding but stay prep-only until statement and franking treatment are reviewed.",
        status,
        [INVESTMENT_SOURCES[0], INVESTMENT_SOURCES[2], INVESTMENT_SOURCES[3]],
        tab_text=investment_tab_text("Dividend", evidence_terms(statement_evidence, amount_evidence or franking_evidence, conflict), reviews),
        row_kind="investment",
        facts=handoff_facts(
            ("security", "Security", investment_label_text(item)),
            ("cash-dividend", "Cash dividend", dividend_item_total(item)),
            ("franked", "Franked amount", item.get("franked_amount")),
            ("unfranked", "Unfranked amount", item.get("unfranked_amount")),
            ("franking-credit", "Franking credit", item.get("franking_credit")),
            ("tfn-withholding", "TFN withholding", item.get("tfn_withheld")),
            ("statement", "Statement evidence", item.get("statement")),
        ),
    )


def investment_distribution_row(index: int, item: Dict[str, Any], conflict: bool) -> Dict[str, Any]:
    amount_evidence = distribution_amounts_need_evidence(item) or investment_amounts_need_evidence(
        item,
        INVESTMENT_DISTRIBUTION_AMOUNT_FIELDS,
        INVESTMENT_DISTRIBUTION_REQUIRED_AMOUNT_GROUPS,
    )
    statement_evidence = investment_statement_missing(item.get("statement"))
    reviews = investment_review_terms(item, include_trust=False)
    status = "Evidence" if statement_evidence or amount_evidence or conflict else "Accountant review"
    return guide_row(
        f"DIST-{index}",
        "13 Partnerships and trusts",
        "Managed fund/ETF/AMIT distribution statement item",
        (
            f"Fund {investment_display_text(item, 'fund')}; distribution {money_text(distribution_item_total(item))}; "
            f"taxable amount {money_text(investment_money_value(item.get('taxable_amount')))}; "
            f"capital gain {money_text(investment_money_value(item.get('capital_gain')))}; "
            f"foreign income {money_text(investment_money_value(item.get('foreign_income')))}; "
            f"foreign tax offset {money_text(investment_money_value(item.get('foreign_tax_offset')))}; "
            f"franking credit {money_text(investment_money_value(item.get('franking_credit')))}; "
            f"TFN withholding {money_text(investment_money_value(item.get('tfn_withheld')))}; "
            f"foreign components {investment_foreign_components_text(item)}"
            f"{investment_review_flag_sentence(item)}"
        ),
        "Managed fund, ETF, and AMIT distributions need annual statement labels, component review, and cost-base follow-up where flagged.",
        status,
        [INVESTMENT_SOURCES[0], INVESTMENT_SOURCES[2], INVESTMENT_SOURCES[4]],
        tab_text=investment_tab_text("Managed fund/ETF distribution", evidence_terms(statement_evidence, amount_evidence, conflict), reviews),
        row_kind="investment",
        facts=handoff_facts(
            ("fund", "Fund", item.get("fund")),
            ("distribution", "Distribution total", distribution_item_total(item)),
            ("taxable-amount", "Taxable amount", item.get("taxable_amount")),
            ("capital-gain", "Capital gain component", item.get("capital_gain")),
            ("foreign-income", "Foreign income component", item.get("foreign_income")),
            ("foreign-tax-offset", "Foreign tax offset component", item.get("foreign_tax_offset")),
            ("franking-credit", "Franking credit", item.get("franking_credit")),
            ("tfn-withholding", "TFN withholding", item.get("tfn_withheld")),
            ("foreign-components", "Foreign components", investment_foreign_components_text(item)),
            ("statement", "Statement evidence", item.get("statement")),
        ),
    )


def investment_trust_row(index: int, item: Dict[str, Any]) -> Dict[str, Any]:
    amount_evidence = investment_amounts_need_evidence(
        item,
        INVESTMENT_TRUST_AMOUNT_FIELDS,
        INVESTMENT_TRUST_REQUIRED_AMOUNT_GROUPS,
        franked_key="franked_distribution",
    )
    statement_evidence = investment_statement_missing(item.get("statement"))
    status = "Evidence" if statement_evidence or amount_evidence else "Accountant review"
    return guide_row(
        f"TRUST-DIST-{index}",
        "13 Partnerships and trusts",
        "Trust distribution routing for individual beneficiary",
        (
            f"Trust {investment_display_text(item, 'trust')}; beneficiary {investment_display_text(item, 'beneficiary_type')}; "
            f"distribution {money_text(investment_money_value(item.get('distribution_amount')))}; "
            f"franked distribution {money_text(investment_money_value(item.get('franked_distribution')))}; "
            f"franking credit {money_text(investment_money_value(item.get('franking_credit')))}; "
            f"capital gain {money_text(investment_money_value(item.get('capital_gain')))}; "
            f"foreign income {money_text(investment_money_value(item.get('foreign_income')))}; "
            f"foreign tax offset {money_text(investment_money_value(item.get('foreign_tax_offset')))}; "
            f"non-assessable payment {money_text(investment_money_value(item.get('non_assessable_payment')))}; "
            f"foreign components {investment_foreign_components_text(item)}"
        ),
        "Individual beneficiary trust distributions are routed for accountant review only; TaxMate does not prepare a trust return.",
        status,
        [INVESTMENT_SOURCES[0], INVESTMENT_SOURCES[2], INVESTMENT_SOURCES[4]],
        tab_text=investment_tab_text("Trust distribution", evidence_terms(statement_evidence, amount_evidence, False), investment_review_terms(item, include_trust=True)),
        row_kind="investment",
        facts=handoff_facts(
            ("trust", "Trust", item.get("trust")),
            ("beneficiary-type", "Beneficiary type", item.get("beneficiary_type")),
            ("distribution", "Distribution amount", item.get("distribution_amount")),
            ("franked-distribution", "Franked distribution", item.get("franked_distribution")),
            ("franking-credit", "Franking credit", item.get("franking_credit")),
            ("capital-gain", "Capital gain component", item.get("capital_gain")),
            ("foreign-income", "Foreign income component", item.get("foreign_income")),
            ("foreign-tax-offset", "Foreign tax offset component", item.get("foreign_tax_offset")),
            ("non-assessable-payment", "Non-assessable payment", item.get("non_assessable_payment")),
            ("foreign-components", "Foreign components", investment_foreign_components_text(item)),
            ("statement", "Statement evidence", item.get("statement")),
        ),
    )


def investment_reconciliation_row(
    raw: Dict[str, Any],
    interest_items: List[Dict[str, Any]],
    dividend_items: List[Dict[str, Any]],
    distribution_items: List[Dict[str, Any]],
    interest_conflict: bool,
    dividend_conflict: bool,
) -> Dict[str, Any]:
    interest_total = interest_category_total(interest_items)
    dividend_total = dividend_distribution_category_total(dividend_items, distribution_items)
    status = "Evidence" if interest_conflict or dividend_conflict else "Accountant review"
    answers_text: List[str] = []
    if interest_items:
        answers_text.append(
            f"Interest items {money_text(interest_total)} vs aggregate {money_text(investment_money_value(investment_aggregate_value(raw, 'interest_income')))}"
        )
    if dividend_items or distribution_items:
        answers_text.append(
            f"dividend/distribution items {money_text(dividend_total)} vs aggregate {money_text(investment_money_value(investment_aggregate_value(raw, 'dividend_income')))}"
        )
    aggregate_conflicts = raw.get("_aggregate_conflicts")
    if isinstance(aggregate_conflicts, list) and aggregate_conflicts:
        answers_text.append(f"aggregate conflicts {', '.join(sorted(aggregate_conflicts))}")
    item_conflicts = sorted(investment_item_conflict_keys(raw))
    if item_conflicts:
        answers_text.append(f"item alias conflicts {', '.join(item_conflicts)}")
    return guide_row(
        "INVEST-RECON",
        "10/11/13 Investment income",
        "Investment income item total reconciliation",
        "; ".join(answers_text),
        "Itemized investment rows must be reconciled to supplied aggregate totals before entry.",
        status,
        INVESTMENT_SOURCES,
        tab_text=investment_reconciliation_tab_text(interest_conflict, dividend_conflict),
        row_kind="investment",
        facts=handoff_facts(
            ("interest-item-total", "Interest item total", interest_total),
            ("interest-aggregate", "Interest aggregate supplied", investment_aggregate_value(raw, "interest_income")),
            ("dividend-item-total", "Dividend/distribution item total", dividend_total),
            ("dividend-aggregate", "Dividend aggregate supplied", investment_aggregate_value(raw, "dividend_income")),
            ("aggregate-conflicts", "Aggregate conflicts", ", ".join(sorted(raw.get("_aggregate_conflicts", []))) or "none"),
            ("item-conflicts", "Item alias conflicts", ", ".join(sorted(investment_item_conflict_keys(raw))) or "none"),
        ),
    )


def investment_evidence_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    groups = (
        ("Bank interest statement", "10 Gross interest", raw.get("interest_items"), INVESTMENT_INTEREST_AMOUNT_FIELDS, ""),
        ("Dividend statement", "11 Dividends", raw.get("dividend_items"), INVESTMENT_DIVIDEND_AMOUNT_FIELDS, "franked_amount"),
        ("Managed fund/ETF annual tax statement", "13 Partnerships and trusts", raw.get("distribution_items"), INVESTMENT_DISTRIBUTION_AMOUNT_FIELDS, ""),
        ("Trust distribution statement", "13 Partnerships and trusts", raw.get("trust_distribution_items"), INVESTMENT_TRUST_AMOUNT_FIELDS, "franked_distribution"),
    )
    for group_label, area, raw_items, amount_fields, franked_key in groups:
        for idx, item in enumerate(investment_item_values(raw_items), start=1):
            missing = investment_statement_missing(item.get("statement"))
            amounts = investment_amounts_need_evidence(
                item,
                amount_fields,
                investment_required_amount_groups(group_label),
                franked_key=franked_key,
            )
            if group_label == "Dividend statement" and dividend_amounts_need_evidence(item):
                amounts = True
            if group_label == "Managed fund/ETF annual tax statement" and distribution_amounts_need_evidence(item):
                amounts = True
            franking = group_label == "Dividend statement" and investment_franking_uncertain(item)
            if missing or amounts or franking:
                rows.append(
                    guide_row(
                        f"INV-EVID-{len(rows) + 1}",
                        area,
                        "Investment evidence required",
                        investment_evidence_text(group_label, idx, missing, amounts, franking),
                        "Investment prep row is not ready for entry until statement and amount evidence are confirmed.",
                        "Evidence",
                        INVESTMENT_SOURCES,
                        row_kind="evidence-queue",
                        facts=handoff_facts(
                            ("investment-item", "Investment item", f"{group_label} {idx}"),
                            ("evidence-needed", "Evidence needed", investment_evidence_text(group_label, idx, missing, amounts, franking)),
                        ),
                    )
                )
    interest_items = investment_item_values(raw.get("interest_items"))
    dividend_items = investment_item_values(raw.get("dividend_items"))
    distribution_items = investment_item_values(raw.get("distribution_items"))
    item_conflicts = investment_item_conflict_keys(raw)
    interest_conflict = investment_aggregate_alias_conflict(raw, "interest_income") or investment_reconciliation_conflict(
        investment_aggregate_value(raw, "interest_income"),
        interest_category_total(interest_items),
        bool(interest_items),
    ) or "interest_items" in item_conflicts
    dividend_conflict = investment_aggregate_alias_conflict(raw, "dividend_income") or investment_reconciliation_conflict(
        investment_aggregate_value(raw, "dividend_income"),
        dividend_distribution_category_total(dividend_items, distribution_items),
        bool(dividend_items or distribution_items),
    ) or bool(item_conflicts.intersection({"dividend_items", "distribution_items"}))
    if interest_conflict or dividend_conflict:
        rows.append(
            guide_row(
                f"INV-EVID-{len(rows) + 1}",
                "10/11/13 Investment income",
                "Investment reconciliation evidence required",
                investment_reconciliation_evidence_text(interest_conflict, dividend_conflict, item_conflicts),
                "Supplied aggregate totals and itemized investment rows conflict.",
                "Evidence",
                INVESTMENT_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("reconciliation", "Reconciliation evidence needed", investment_reconciliation_evidence_text(interest_conflict, dividend_conflict, item_conflicts)),
                ),
            )
        )
    return rows


def investment_reconciliation_evidence_text(
    interest_conflict: bool,
    dividend_conflict: bool,
    item_conflicts: set[str],
) -> str:
    text = investment_reconciliation_tab_text(interest_conflict, dividend_conflict)
    if item_conflicts:
        text = f"{text}; item alias conflicts {', '.join(sorted(item_conflicts))}"
    return text


def investment_item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict) and investment_item_has_facts(item)]


def first_investment_items(answers: Dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = answers.get(key)
        if investment_item_values(value):
            return value
    return None


def investment_item_alias_record_conflict(record: Dict[str, Any], keys: tuple[str, ...]) -> bool:
    values = [record.get(key) for key in keys if investment_item_values(record.get(key))]
    if len(values) < 2:
        return False
    first = values[0]
    return any(investment_items_conflict(first, value) for value in values[1:])


def investment_items_conflict(left: Any, right: Any) -> bool:
    left_items = investment_item_values(left)
    right_items = investment_item_values(right)
    return bool(left_items and right_items and left_items != right_items)


def investment_item_has_facts(item: Dict[str, Any]) -> bool:
    ignored_false_only = {"foreign_components", "amit"}
    return any(has_meaningful_value(value) for key, value in item.items() if key not in ignored_false_only or value is not False)


def investment_has_kind(raw: Dict[str, Any], key: str) -> bool:
    return bool(investment_item_values(raw.get(key)))


def investment_has_dividend_distribution_items(raw: Dict[str, Any]) -> bool:
    return any(investment_has_kind(raw, key) for key in ("dividend_items", "distribution_items"))


def investment_has_reconciliation_target(
    raw: Dict[str, Any],
    interest_items: List[Dict[str, Any]],
    dividend_items: List[Dict[str, Any]],
    distribution_items: List[Dict[str, Any]],
) -> bool:
    return (
        bool(interest_items) and investment_amount_present(investment_aggregate_value(raw, "interest_income"))
    ) or (
        bool(dividend_items or distribution_items) and investment_amount_present(investment_aggregate_value(raw, "dividend_income"))
    ) or bool(investment_item_conflict_keys(raw))


def investment_required_amount_groups(label: str) -> tuple[tuple[str, ...], ...]:
    if label == "Bank interest statement":
        return INVESTMENT_INTEREST_REQUIRED_AMOUNT_GROUPS
    if label == "Dividend statement":
        return INVESTMENT_DIVIDEND_REQUIRED_AMOUNT_GROUPS
    if label == "Managed fund/ETF annual tax statement":
        return INVESTMENT_DISTRIBUTION_REQUIRED_AMOUNT_GROUPS
    return INVESTMENT_TRUST_REQUIRED_AMOUNT_GROUPS


def investment_amounts_need_evidence(
    item: Dict[str, Any],
    fields: tuple[str, ...],
    required_groups: tuple[tuple[str, ...], ...],
    *,
    franked_key: str = "",
) -> bool:
    return investment_required_amount_missing(item, required_groups) or any(
        investment_amount_needs_evidence(item.get(key)) for key in fields
    ) or investment_franking_credit_missing(item, franked_key)


def investment_required_amount_missing(item: Dict[str, Any], required_groups: tuple[tuple[str, ...], ...]) -> bool:
    return not any(any(investment_amount_is_supplied(item.get(key), key) for key in group) for group in required_groups)


def investment_amount_is_supplied(value: Any, key: str = "") -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    amount = investment_money_value(value)
    if amount is None:
        return False
    if key in INVESTMENT_ZERO_COMPONENT_AMOUNT_FIELDS and amount == 0:
        return False
    return True


def investment_franking_credit_missing(item: Dict[str, Any], franked_key: str = "") -> bool:
    if not franked_key:
        return False
    franked_amount = investment_money_value(item.get(franked_key))
    if franked_amount is None or franked_amount <= 0:
        return False
    return not investment_amount_is_supplied(item.get("franking_credit"))


def investment_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    return contains_unknown(value) or investment_amount_malformed(value)


def investment_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return False


def investment_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def investment_statement_missing(statement: Any) -> bool:
    if isinstance(statement, bool):
        return not statement
    if is_missing(statement) or contains_unknown(statement):
        return True
    lowered = text(statement).strip().lower()
    if lowered in {"no", "n", "false", "not held", "not available", "none"}:
        return True
    return any(phrase in lowered for phrase in INVESTMENT_STATEMENT_MISSING_PHRASES)


def investment_franking_uncertain(item: Dict[str, Any]) -> bool:
    if "franking_confirmed" not in item:
        return False
    value = item.get("franking_confirmed")
    if value is True:
        return False
    if value is False:
        return True
    if is_missing(value) or contains_unknown(value):
        return True
    lowered = text(value).strip().lower()
    if lowered in {"no", "n", "false", "0", "not confirmed", "not held", "not available", "none"}:
        return True
    return any(phrase in lowered for phrase in INVESTMENT_FRANKING_UNCERTAIN_PHRASES)


def dividend_amounts_need_evidence(item: Dict[str, Any]) -> bool:
    return investment_direct_amount_unresolved(item, INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS) or dividend_direct_component_conflict(item)


def interest_item_total(items: List[Dict[str, Any]]) -> Optional[float]:
    return investment_itemized_total(investment_money_value(item.get("amount")) for item in items)


def dividend_item_total(item: Dict[str, Any]) -> Optional[float]:
    direct = investment_direct_amount_value(item, INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS)
    component_total = dividend_component_total(item)
    if direct is not None:
        if component_total is not None and investment_total_conflict(direct, component_total):
            return None
        return direct
    if investment_has_direct_amount(item, INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS):
        return None
    return component_total


def dividend_component_total(item: Dict[str, Any]) -> Optional[float]:
    values = [
        investment_money_value(item.get(key))
        for key in ("franked_amount", "unfranked_amount")
        if key in item and not is_missing(item.get(key))
    ]
    if not values:
        return None
    return investment_itemized_total(values)


def dividend_direct_component_conflict(item: Dict[str, Any]) -> bool:
    direct = investment_direct_amount_value(item, INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS)
    component_total = dividend_component_total(item)
    return direct is not None and component_total is not None and investment_total_conflict(direct, component_total)


def distribution_amounts_need_evidence(item: Dict[str, Any]) -> bool:
    return investment_direct_amount_unresolved(item, INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS) or distribution_direct_taxable_conflict(item)


def distribution_item_total(item: Dict[str, Any]) -> Optional[float]:
    direct = investment_direct_amount_value(item, INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS)
    taxable = investment_money_value(item.get("taxable_amount"))
    if direct is not None:
        if investment_amount_present(item.get("taxable_amount")):
            if taxable is None or investment_total_conflict(direct, taxable):
                return None
        return direct
    if investment_has_direct_amount(item, INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS):
        return None
    return taxable


def distribution_direct_taxable_conflict(item: Dict[str, Any]) -> bool:
    direct = investment_direct_amount_value(item, INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS)
    taxable = investment_money_value(item.get("taxable_amount"))
    return direct is not None and taxable is not None and investment_total_conflict(direct, taxable)


def dividend_distribution_total(dividend_items: List[Dict[str, Any]], distribution_items: List[Dict[str, Any]]) -> Optional[float]:
    return investment_itemized_total(
        [dividend_item_total(item) for item in dividend_items]
        + [distribution_item_total(item) for item in distribution_items]
    )


def interest_category_total(items: List[Dict[str, Any]]) -> Optional[float]:
    return investment_category_total(interest_item_total(items), bool(items))


def dividend_distribution_category_total(
    dividend_items: List[Dict[str, Any]],
    distribution_items: List[Dict[str, Any]],
) -> Optional[float]:
    return investment_category_total(
        dividend_distribution_total(dividend_items, distribution_items),
        bool(dividend_items or distribution_items),
    )


def first_present(item: Dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in item and not is_missing(item.get(key)):
            return item.get(key)
    return None


def investment_has_direct_amount(item: Dict[str, Any], keys: tuple[str, ...]) -> bool:
    return any(key in item and not is_missing(item.get(key)) for key in keys)


def investment_direct_amount_value(item: Dict[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    if investment_direct_amount_unresolved(item, keys):
        return None
    return investment_money_value(first_present(item, keys))


def investment_amount_present(value: Any) -> bool:
    return not isinstance(value, bool) and not is_missing(value)


def investment_aggregate_value(raw: Dict[str, Any], key: str) -> Any:
    return raw.get(key)


def investment_aggregate_alias_conflict(raw: Dict[str, Any], key: str) -> bool:
    conflicts = raw.get("_aggregate_conflicts")
    return isinstance(conflicts, list) and key in conflicts


def investment_direct_amount_unresolved(item: Dict[str, Any], keys: tuple[str, ...]) -> bool:
    values = [
        investment_money_value(item.get(key))
        for key in keys
        if investment_amount_present(item.get(key))
    ]
    if any(value is None for value in values):
        return True
    return investment_direct_amount_conflict(values)


def investment_direct_amount_conflict(values: List[float]) -> bool:
    if len(values) < 2:
        return False
    first = values[0]
    return any(round(abs(first - value), 2) >= 0.01 for value in values[1:])


def investment_total(values: Any) -> Optional[float]:
    amounts = [value for value in values if value is not None]
    if not amounts:
        return None
    return round(sum(amounts), 2)


def investment_itemized_total(values: Any) -> Optional[float]:
    amounts = list(values)
    if not amounts or any(value is None for value in amounts):
        return None
    return round(sum(amounts), 2)


def investment_category_total(item_total: Optional[float], has_items: bool) -> Optional[float]:
    return item_total if has_items else 0


def investment_total_conflict(aggregate_value: Any, item_total: Optional[float]) -> bool:
    aggregate = investment_money_value(aggregate_value)
    if aggregate is None or item_total is None:
        return False
    return round(abs(aggregate - item_total), 2) >= 0.01


def investment_reconciliation_conflict(aggregate_value: Any, item_total: Optional[float], has_items: bool) -> bool:
    return has_items and investment_reconciliation_needs_evidence(aggregate_value, item_total)


def investment_reconciliation_needs_evidence(aggregate_value: Any, item_total: Optional[float]) -> bool:
    if investment_aggregate_needs_evidence(aggregate_value):
        return True
    aggregate = investment_money_value(aggregate_value)
    if aggregate is None:
        return False
    return item_total is None or investment_total_conflict(aggregate_value, item_total)


def investment_aggregate_needs_evidence(value: Any) -> bool:
    if is_missing(value) or isinstance(value, bool):
        return False
    return investment_amount_needs_evidence(value)


def investment_review_terms(item: Dict[str, Any], *, include_trust: bool) -> List[str]:
    terms: List[str] = []
    if investment_boolean_flag_value(item.get("amit")) is True or has_meaningful_value(item.get("amit_status")):
        terms.append("AMIT label mapping")
    if investment_review_amount_or_text(item.get("cost_base_adjustment")):
        terms.append("cost-base adjustment")
    if investment_has_foreign_components(item):
        terms.append("foreign components")
    if include_trust:
        terms.append("trust distribution routing")
    return terms


def investment_review_flag_sentence(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    amit = investment_review_flag_value(item.get("amit"))
    if amit:
        parts.append(f"AMIT {amit}")
    amit_status = investment_review_flag_value(item.get("amit_status"))
    if amit_status:
        parts.append(f"AMIT status {amit_status}")
    cost_base = investment_review_flag_value(item.get("cost_base_adjustment"))
    if cost_base:
        parts.append(f"cost-base adjustment {cost_base}")
    return f"; {'; '.join(parts)}" if parts else ""


def investment_review_flag_value(value: Any) -> str:
    if is_missing(value) or contains_unknown(value):
        return ""
    flag = investment_boolean_flag_value(value)
    if flag is False:
        return ""
    if flag is True:
        return display_value(value)
    amount = investment_money_value(value)
    if amount == 0:
        return ""
    return display_value(value)


def investment_boolean_flag_value(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str) or contains_unknown(value):
        return None
    lowered = value.strip().lower()
    if lowered in {"yes", "y", "true", "1", "on", "checked"}:
        return True
    if lowered in {"no", "n", "false", "0", "off", "unchecked", "none", "not applicable", "n/a"}:
        return False
    return None


def investment_has_foreign_components(item: Dict[str, Any]) -> bool:
    foreign_flag = investment_boolean_flag_value(item.get("foreign_components"))
    if foreign_flag is True:
        return True
    for key in ("foreign_income", "foreign_tax_offset"):
        value = investment_money_value(item.get(key))
        if value is not None and value != 0:
            return True
    return False


def investment_foreign_components_text(item: Dict[str, Any]) -> str:
    value = item.get("foreign_components")
    flag = investment_boolean_flag_value(value)
    if flag is False:
        return "false"
    if is_missing(value):
        return "unknown"
    return display_value(value) or "unknown"


def investment_review_amount_or_text(value: Any) -> bool:
    if value is True:
        return True
    if value is False or is_missing(value) or contains_unknown(value):
        return False
    amount = investment_money_value(value)
    return amount is None or amount != 0


def evidence_terms(statement_evidence: bool, amount_evidence: bool, conflict: bool) -> List[str]:
    terms: List[str] = []
    if statement_evidence:
        terms.append("statement evidence")
    if amount_evidence:
        terms.append("numeric amount/franking evidence")
    if conflict:
        terms.append("corrected aggregate reconciliation")
    return terms


def investment_tab_text(label: str, evidence: List[str], reviews: List[str]) -> str:
    if evidence and reviews:
        return f"{label} needs {', '.join(evidence)} and stays accountant review for {', '.join(reviews)}."
    if evidence:
        return f"{label} needs {', '.join(evidence)} before accountant review."
    if reviews:
        return f"{label} requires accountant review before entry because of {', '.join(reviews)}."
    return f"{label} requires accountant review before entry."


def investment_reconciliation_tab_text(interest_conflict: bool, dividend_conflict: bool) -> str:
    gaps: List[str] = []
    if interest_conflict:
        gaps.append("interest item total vs aggregate interest")
    if dividend_conflict:
        gaps.append("dividend/distribution item total vs aggregate dividend income")
    if gaps:
        return f"Investment totals need corrected reconciliation for {', '.join(gaps)} before accountant review."
    return "Investment item totals reconcile to supplied aggregates; still prep-only and review-first."


def investment_evidence_text(label: str, index: int, missing: bool, amounts: bool, franking: bool) -> str:
    gaps: List[str] = []
    if missing:
        gaps.append("statement")
    if amounts:
        gaps.append("amount/component values")
    if franking:
        gaps.append("franking confirmation")
    return f"{label} item {index}: confirm {', '.join(gaps)}"


def investment_display_text(item: Dict[str, Any], key: str) -> str:
    return display_value(item.get(key)) or "unknown"


def investment_label_text(item: Dict[str, Any]) -> str:
    return investment_display_text(item, "security") if has_meaningful_value(item.get("security")) else investment_display_text(item, "company")


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


def asset_fact_treatment(cost: Optional[float], work_use: Optional[float]) -> str:
    if cost is None or work_use is None:
        return "Evidence needed before method review"
    if cost > 300:
        return "Selected method candidate, not a full immediate claim"
    if work_use != 100:
        return "Mixed-use method needs review"
    return "Immediate deduction candidate if evidence supports it"


def payg_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    nested = first_payg_nested(answers)
    merged: Dict[str, Any] = dict(nested) if isinstance(nested, dict) else {}
    merged = payg_drop_absence_fields(merged)
    normalized_answer_fields = normalize_payg_fields(payg_top_level_alias_answers(answers))
    flat = {
        "payer": answers.get("payg_employer_name"),
        "abn": answers.get("payg_employer_abn"),
        "occupation": first_present(answers, ("payg_occupation", "main_occupation")),
        "gross": answers.get("payg_gross"),
        "withheld": answers.get("payg_withheld"),
        "allowances": answers.get("payg_allowances"),
        "rfba": answers.get("payg_rfba"),
        "resc": answers.get("payg_resc"),
        "lump_sum_a": answers.get("payg_lump_sum_a"),
        "lump_sum_b": answers.get("payg_lump_sum_b"),
        "lump_sum_d": answers.get("payg_lump_sum_d"),
        "lump_sum_e": answers.get("payg_lump_sum_e"),
    }
    flat = payg_merge_flat_values(normalized_answer_fields, flat)
    item_values = first_payg_items(answers)
    raw_items = merged.get("items")
    nested_scalar_statement_gap = payg_scalar_statement_gap_value(merged)
    nested_items = payg_item_values(raw_items)
    top_level_items = payg_item_values(item_values)
    nested_alias_raw_items = first_payg_items(merged)
    nested_alias_items = payg_item_values(nested_alias_raw_items)
    has_item_context = bool(nested_items or top_level_items or nested_alias_items)
    flat_values = {
        key: value
        for key, value in flat.items()
        if key == "_alias_conflicts"
        or has_meaningful_payg_flat_value(key, value)
        or (has_item_context and has_unknown_payg_flat_value(key, value))
    }
    flat_declines = payg_decline_values(flat)
    scalar_statement_gap = payg_scalar_statement_gap_value(answers)
    if nested_items:
        if nested_alias_items and payg_items_conflict(raw_items, nested_alias_raw_items):
            merged["_alias_conflicts"] = sorted(set(list(merged.get("_alias_conflicts") or []) + ["items"]))
        if top_level_items and payg_items_conflict(raw_items, item_values):
            merged["_alias_conflicts"] = sorted(set(list(merged.get("_alias_conflicts") or []) + ["items"]))
    elif nested_alias_items:
        raw_items = first_payg_items(merged)
        if top_level_items and payg_items_conflict(raw_items, item_values):
            merged["_alias_conflicts"] = sorted(set(list(merged.get("_alias_conflicts") or []) + ["items"]))
    elif top_level_items:
        raw_items = item_values
    else:
        raw_items = first_payg_items(merged)
    normalized_items = payg_item_values(raw_items)
    normalized_fields = normalize_payg_fields(merged)
    raw_declines = payg_decline_values(merged)
    answer_declines = payg_decline_values(answers)
    for key, value in normalized_fields.items():
        if key == "_alias_conflicts":
            merged[key] = value
        elif key not in merged:
            merged[key] = value
    if is_missing(scalar_statement_gap):
        scalar_statement_gap = nested_scalar_statement_gap
    if not is_missing(scalar_statement_gap) and "statement" not in merged:
        merged["statement"] = scalar_statement_gap
    if normalized_items:
        merged = {key: value for key, value in merged.items() if key not in PAYG_ITEM_ALIASES}
        merged["items"] = normalized_items
    merged = payg_merge_flat_values(merged, flat_values)
    merged = payg_backfill_single_item_context(merged)
    merged = payg_values_with_declines(merged, {**answer_declines, **flat_declines, **raw_declines})
    return merged


def payg_top_level_alias_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    if "abn" not in answers or bare_abn_is_payg(answers):
        return answers
    narrowed = dict(answers)
    narrowed.pop("abn", None)
    return narrowed


def bare_abn_is_payg(answers: Dict[str, Any]) -> bool:
    return "abn" in answers and has_payg_context_for_bare_abn(answers) and not has_business_context_for_bare_abn(answers)


def has_payg_context_for_bare_abn(answers: Dict[str, Any]) -> bool:
    if payg_item_context_for_bare_abn(answers):
        return True
    for key, value in answers.items():
        canonical = PAYG_FLAT_FIELD_KEYS.get(key, PAYG_ALIAS_TO_FIELD.get(key))
        if canonical and canonical != "abn" and has_meaningful_payg_flat_value(canonical, value):
            return True
    for nested_key in PAYG_NESTED_KEYS:
        nested = answers.get(nested_key)
        if isinstance(nested, dict):
            if payg_item_context_for_bare_abn(nested):
                return True
            for key, value in nested.items():
                canonical = PAYG_ALIAS_TO_FIELD.get(key)
                if canonical and canonical != "abn" and has_meaningful_payg_flat_value(canonical, value):
                    return True
    return False


def payg_item_context_for_bare_abn(record: Dict[str, Any]) -> bool:
    return first_payg_items(record) is not None or bool(payg_item_values(record.get("items")))


def has_business_context_for_bare_abn(answers: Dict[str, Any]) -> bool:
    if has_bas_inputs(answers):
        return True
    for key in REVIEWABLE_ABN_FIELDS:
        if key in {"abn", "business_abn"}:
            continue
        if key in answers and abn_input_signal(key, answers.get(key)):
            return True
    if has_abn_contextual_alias_signal(answers):
        return True
    return any(
        abn_input_signal(key, abn_answer(answers, key))
        for key in ABN_CONTEXT_SIGNAL_FIELDS
        if key not in {"abn"}
    )


def first_payg_nested(answers: Dict[str, Any]) -> Any:
    merged: Dict[str, Any] = {}
    for key in PAYG_NESTED_KEYS:
        raw = answers.get(key)
        if isinstance(raw, dict) and has_meaningful_value(raw):
            merged = payg_merge_nested_values(merged, payg_drop_absence_fields(dict(raw)))
    return merged


def payg_merge_nested_values(merged: Dict[str, Any], values: Dict[str, Any]) -> Dict[str, Any]:
    if not values:
        return merged
    result = dict(merged)
    conflicts = list(result.get("_alias_conflicts") or [])
    for key, value in values.items():
        if key == "_alias_conflicts":
            conflicts.extend(value if isinstance(value, list) else [value])
            continue
        if key in PAYG_ITEM_ALIASES and isinstance(value, (dict, list)):
            if payg_item_values(result.get(key)) and payg_items_conflict(result.get(key), value):
                conflicts.append("items")
            elif not payg_item_values(result.get(key)):
                result[key] = value
            continue
        existing = result.get(key)
        canonical = payg_canonical_field_key(key)
        if is_missing(existing):
            result[key] = value
        elif payg_values_conflict(canonical, existing, value):
            conflicts.append(canonical)
            if payg_prefer_merged_value(canonical, value, existing):
                result[key] = value
    if conflicts:
        result["_alias_conflicts"] = sorted(set(conflicts))
    return result


def first_payg_items(record: Dict[str, Any]) -> Any:
    for key in PAYG_ITEM_ALIASES:
        value = record.get(key)
        if payg_item_values(value):
            return value
    return None


def payg_backfill_single_item_context(record: Dict[str, Any]) -> Dict[str, Any]:
    items = payg_item_values(record.get("items"))
    if len(items) != 1:
        return record
    item = dict(items[0])
    moved_keys: List[str] = []
    for key in ("abn",):
        if not has_meaningful_payg_item_value(key, item.get(key)) and has_meaningful_payg_flat_value(key, record.get(key)):
            item[key] = record.get(key)
            moved_keys.append(key)
    if not moved_keys:
        return record
    merged = dict(record)
    for key in moved_keys:
        merged.pop(key, None)
    merged["items"] = [item]
    return merged


def payg_items_conflict(left: Any, right: Any) -> bool:
    left_items = payg_item_values(left)
    right_items = payg_item_values(right)
    if not left_items or not right_items:
        return False
    return json.dumps(left_items, sort_keys=True, default=str) != json.dumps(right_items, sort_keys=True, default=str)


def payg_merge_flat_values(merged: Dict[str, Any], flat_values: Dict[str, Any]) -> Dict[str, Any]:
    if not flat_values:
        return merged
    result = dict(merged)
    conflicts = list(result.get("_alias_conflicts") or [])
    for key, value in flat_values.items():
        if key == "_alias_conflicts":
            conflicts.extend(value if isinstance(value, list) else [value])
            continue
        existing = result.get(key)
        if is_missing(existing):
            result[key] = value
        elif payg_values_conflict(key, existing, value):
            conflicts.append(key)
            if payg_prefer_merged_value(key, value, existing):
                result[key] = value
    if conflicts:
        result["_alias_conflicts"] = sorted(set(conflicts))
    return result


def payg_prefer_merged_value(key: str, candidate: Any, existing: Any) -> bool:
    return payg_concrete_alias_value(candidate, key) and contains_unknown(existing)


def payg_values_conflict(key: str, left: Any, right: Any) -> bool:
    if key in PAYG_AMOUNT_FIELDS:
        return payg_alias_amount_conflict([left, right])
    if key == "statement":
        return payg_statement_values_conflict(left, right)
    if key == "finalised":
        return payg_alias_bool_conflict([left, right])
    return payg_alias_text_conflict([left, right])


def payg_statement_values_conflict(left: Any, right: Any) -> bool:
    if is_missing(left) or is_missing(right):
        return False
    left_missing = payg_statement_missing(left)
    right_missing = payg_statement_missing(right)
    if left_missing != right_missing:
        return True
    if left_missing and right_missing:
        return False
    left_bool = parse_payg_bool(left)
    right_bool = parse_payg_bool(right)
    return left_bool is not None and right_bool is not None and left_bool != right_bool


def payg_scalar_statement_gap_value(answers: Dict[str, Any]) -> Any:
    for key in PAYG_ITEM_ALIASES:
        value = answers.get(key)
        if isinstance(value, str) and payg_statement_missing(value):
            return value
    return None


def payg_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payg_item_values(raw.get("items"))
    rows: List[Dict[str, Any]] = []
    if not items:
        return payg_nested_base_rows(raw, answers)
    gross_conflict = payg_reconciliation_conflict(payg_aggregate_value(raw, "gross"), payg_item_amount_total(items, "gross"), bool(items))
    withheld_conflict = payg_reconciliation_conflict(
        payg_aggregate_value(raw, "withheld"),
        payg_item_amount_total(items, "withheld"),
        bool(items),
    )
    aggregate_alias_conflict = bool(raw.get("_alias_conflicts"))
    for idx, item in enumerate(items, start=1):
        rows.append(payg_statement_row(idx, item, gross_conflict or withheld_conflict or aggregate_alias_conflict))
    supplemental_row = payg_supplemental_row(raw)
    if supplemental_row:
        rows.append(supplemental_row)
    if items and payg_has_reconciliation_target(raw):
        rows.append(payg_reconciliation_row(raw, items, gross_conflict, withheld_conflict))
    return rows


def payg_statement_row(index: int, item: Dict[str, Any], conflict: bool) -> Dict[str, Any]:
    statement_evidence = payg_statement_missing(item.get("statement"))
    finalised_evidence = payg_finalised_missing(item.get("finalised"))
    payer_evidence = payg_payer_detail_missing(item)
    amount_evidence = payg_item_amounts_need_evidence(item)
    lump_sum_evidence = payg_lump_sum_label_evidence(item)
    decline_evidence = payg_decline_contradiction(item)
    alias_evidence = bool(item.get("_alias_conflicts"))
    status = (
        "Evidence"
        if statement_evidence
        or finalised_evidence
        or payer_evidence
        or amount_evidence
        or lump_sum_evidence
        or decline_evidence
        or alias_evidence
        or conflict
        else "Accountant review"
    )
    answer = (
        f"Payer {payg_display_text(item, 'payer')}; ABN {payg_display_text(item, 'abn')}; "
        f"occupation {payg_display_text(item, 'occupation')}; gross {money_text(payg_amount_value(item.get('gross')))}; "
        f"tax withheld {money_text(payg_amount_value(item.get('withheld')))}; "
        f"allowances {money_text(payg_amount_value(item.get('allowances')))}; "
        f"RFBA {money_text(payg_amount_value(item.get('rfba')))}; "
        f"RESC {money_text(payg_amount_value(item.get('resc')))}; "
        f"lump sum A {money_text(payg_amount_value(item.get('lump_sum_a')))}; "
        f"lump sum B {money_text(payg_amount_value(item.get('lump_sum_b')))}; "
        f"lump sum D {money_text(payg_amount_value(item.get('lump_sum_d')))}; "
        f"lump sum E {money_text(payg_amount_value(item.get('lump_sum_e')))}; "
        f"statement {payg_display_text(item, 'statement')}; finalised {payg_boolean_text(item.get('finalised'))}"
    )
    decline_text = payg_decline_signal_text(item)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    conflict_text = payg_alias_conflict_text(item)
    if conflict_text:
        answer = f"{answer}; alias conflicts {conflict_text}"
    return guide_row(
        f"PAYG-{index}",
        "1 Salary or wages",
        "PAYG income statement item",
        answer,
        "PAYG statement rows are prep-only. Confirm income statement evidence, payer identity, amounts, allowances, RFBA, RESC, and any lump sum labels before entry.",
        status,
        PAYG_SOURCES,
        tab_text=payg_tab_text(statement_evidence, finalised_evidence, payer_evidence, amount_evidence, lump_sum_evidence, decline_evidence, conflict),
        row_kind="individual-return",
        facts=handoff_facts(
            ("payer", "Payer", item.get("payer")),
            ("abn", "Payer ABN", item.get("abn")),
            ("occupation", "Occupation", item.get("occupation")),
            ("gross", "Gross income", item.get("gross")),
            ("withheld", "Tax withheld", item.get("withheld")),
            ("allowances", "Allowances", item.get("allowances")),
            ("rfba", "Reportable fringe benefits amount", item.get("rfba")),
            ("resc", "Reportable employer super contributions", item.get("resc")),
            ("lump-sum-a", "Lump sum A", item.get("lump_sum_a")),
            ("lump-sum-b", "Lump sum B", item.get("lump_sum_b")),
            ("lump-sum-d", "Lump sum D", item.get("lump_sum_d")),
            ("lump-sum-e", "Lump sum E", item.get("lump_sum_e")),
            ("statement", "Income statement evidence", item.get("statement")),
            ("finalised", "Income statement finalised", item.get("finalised")),
            ("decline-signals", "Decline signals", decline_text or "none"),
            ("alias-conflicts", "Alias conflicts", conflict_text or "none"),
        ),
    )


def payg_nested_base_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for nested_key, row_key in PAYG_NESTED_BASE_FIELD_KEYS.items():
        value = raw.get(nested_key)
        flat_value = answers.get(row_key)
        if nested_key == "occupation" and is_missing(flat_value):
            flat_value = answers.get("main_occupation")
        if payg_flat_row_covers_nested_fact(nested_key, flat_value, value):
            continue
        if not has_meaningful_payg_flat_value(nested_key, value) and not payg_amount_field_needs_evidence(nested_key, value):
            continue
        rows.append(
            guide_row(
                row_key,
                "1 Salary or wages",
                payg_nested_base_question(nested_key),
                display_value(value),
                "PAYG aggregate-only fact is prep-only and needs source evidence before entry.",
                payg_nested_base_status(nested_key, value, raw),
                PAYG_SOURCES,
                tab_text=f"{payg_nested_base_question(nested_key)}: {display_value(value)}",
                row_kind="individual-return",
                facts=handoff_facts(
                    (nested_key.replace("_", "-"), payg_nested_base_question(nested_key), value),
                ),
            )
        )
    return rows


def payg_flat_row_renders_fact(key: str, value: Any) -> bool:
    return has_meaningful_payg_flat_value(key, value) or payg_amount_field_needs_evidence(key, value)


def payg_flat_row_covers_nested_fact(key: str, flat_value: Any, nested_value: Any) -> bool:
    if payg_source_declines_workflow(key, flat_value) or payg_field_absence_value(key, flat_value):
        return False
    if not payg_flat_row_renders_fact(key, flat_value):
        return False
    if flat_value == nested_value:
        return True
    if has_unknown_payg_flat_value(key, flat_value) or payg_amount_field_needs_evidence(key, flat_value):
        return False
    if has_meaningful_payg_flat_value(key, nested_value) or payg_amount_field_needs_evidence(key, nested_value):
        return True
    return not payg_values_conflict(key, flat_value, nested_value)


def payg_nested_base_question(key: str) -> str:
    labels = {
        "payer": "PAYG employer or payer name",
        "abn": "PAYG employer or payer ABN",
        "occupation": "PAYG occupation",
        "gross": "Salary or wages gross income",
        "withheld": "Salary or wages tax withheld",
        "allowances": "PAYG allowances",
        "rfba": "Reportable fringe benefits amount",
        "resc": "Reportable employer super contributions",
        "lump_sum_a": "PAYG lump sum A",
        "lump_sum_b": "PAYG lump sum B",
        "lump_sum_d": "PAYG lump sum D",
        "lump_sum_e": "PAYG lump sum E",
    }
    return labels.get(key, f"PAYG {key}")


def payg_nested_base_status(key: str, value: Any, raw: Dict[str, Any]) -> str:
    if payg_aggregate_evidence_gaps(raw):
        return "Evidence"
    if key in PAYG_AMOUNT_FIELDS and payg_amount_malformed(value):
        return "Evidence"
    return "Evidence" if is_missing(value) or contains_unknown(value) else "Accountant review"


def payg_supplemental_row(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not payg_has_supplemental_facts(raw):
        return None
    status = "Evidence" if payg_supplemental_needs_evidence(raw) else "Accountant review"
    answer = (
        f"Payer {payg_display_text(raw, 'payer')}; ABN {payg_display_text(raw, 'abn')}; "
        f"occupation {payg_display_text(raw, 'occupation')}; allowances {money_text(payg_amount_value(raw.get('allowances')))}; "
        f"RFBA {money_text(payg_amount_value(raw.get('rfba')))}; RESC {money_text(payg_amount_value(raw.get('resc')))}; "
        f"lump sum A {money_text(payg_amount_value(raw.get('lump_sum_a')))}; "
        f"lump sum B {money_text(payg_amount_value(raw.get('lump_sum_b')))}; "
        f"lump sum D {money_text(payg_amount_value(raw.get('lump_sum_d')))}; "
        f"lump sum E {money_text(payg_amount_value(raw.get('lump_sum_e')))}"
    )
    if "statement" in raw:
        answer = f"{answer}; statement {payg_display_text(raw, 'statement')}"
    if "finalised" in raw:
        answer = f"{answer}; finalised {payg_boolean_text(raw.get('finalised'))}"
    decline_text = payg_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    conflict_text = payg_alias_conflict_text(raw)
    if conflict_text:
        answer = f"{answer}; aggregate alias conflicts {conflict_text}"
    return guide_row(
        "PAYG-SUPP",
        "1 Salary or wages",
        "PAYG aggregate supplied details",
        answer,
        "Flat PAYG details supplied beside itemized statements are preserved for accountant review instead of being assigned to a payer row.",
        status,
        PAYG_SOURCES,
        tab_text=payg_supplemental_tab_text(raw),
        row_kind="individual-return",
        facts=handoff_facts(
            ("payer", "Payer", raw.get("payer")),
            ("abn", "Payer ABN", raw.get("abn")),
            ("occupation", "Occupation", raw.get("occupation")),
            ("allowances", "Allowances", raw.get("allowances")),
            ("rfba", "Reportable fringe benefits amount", raw.get("rfba")),
            ("resc", "Reportable employer super contributions", raw.get("resc")),
            ("lump-sum-a", "Lump sum A", raw.get("lump_sum_a")),
            ("lump-sum-b", "Lump sum B", raw.get("lump_sum_b")),
            ("lump-sum-d", "Lump sum D", raw.get("lump_sum_d")),
            ("lump-sum-e", "Lump sum E", raw.get("lump_sum_e")),
            ("statement", "Income statement evidence", raw.get("statement")),
            ("finalised", "Income statement finalised", raw.get("finalised")),
            ("decline-signals", "Decline signals", decline_text or "none"),
            ("alias-conflicts", "Aggregate alias conflicts", conflict_text or "none"),
        ),
    )


def payg_has_supplemental_facts(raw: Dict[str, Any]) -> bool:
    if payg_aggregate_evidence_gaps(raw):
        return True
    return any(
        has_meaningful_payg_flat_value(key, raw.get(key)) or payg_amount_field_needs_evidence(key, raw.get(key))
        for key in PAYG_SUPPLEMENTAL_FIELDS
    )


def payg_supplemental_needs_evidence(raw: Dict[str, Any]) -> bool:
    if payg_aggregate_evidence_gaps(raw):
        return True
    if raw.get("_alias_conflicts"):
        return True
    if any(payg_amount_needs_evidence(raw.get(key)) for key in PAYG_SUPPLEMENTAL_FIELDS if key in PAYG_AMOUNT_FIELDS):
        return True
    if any(key in raw and payg_required_text_missing(raw.get(key)) for key in ("payer", "abn", "occupation")):
        return True
    return payg_lump_sum_label_evidence(raw)


def payg_supplemental_tab_text(raw: Dict[str, Any]) -> str:
    gaps: List[str] = payg_aggregate_evidence_gaps(raw)
    if raw.get("_alias_conflicts"):
        payg_append_unique_gap(gaps, "aggregate alias conflict")
    if any(payg_amount_needs_evidence(raw.get(key)) for key in PAYG_SUPPLEMENTAL_FIELDS if key in PAYG_AMOUNT_FIELDS):
        payg_append_unique_gap(gaps, "numeric amount evidence")
    if any(key in raw and payg_required_text_missing(raw.get(key)) for key in ("payer", "abn", "occupation")):
        payg_append_unique_gap(gaps, "payer, ABN, or occupation evidence")
    if payg_lump_sum_label_evidence(raw):
        payg_append_unique_gap(gaps, "lump sum label evidence")
    if gaps:
        return f"PAYG aggregate supplied details need {', '.join(gaps)} before accountant review."
    return "PAYG aggregate supplied details preserved for accountant review beside itemized statements."


def payg_append_unique_gap(values: List[str], value: str) -> None:
    if value not in values:
        values.append(value)


def payg_reconciliation_row(
    raw: Dict[str, Any],
    items: List[Dict[str, Any]],
    gross_conflict: bool,
    withheld_conflict: bool,
) -> Dict[str, Any]:
    aggregate_alias_conflict = bool(raw.get("_alias_conflicts"))
    status = "Evidence" if gross_conflict or withheld_conflict or aggregate_alias_conflict else "Accountant review"
    answer = (
        f"Gross statement total {money_text(payg_item_amount_total(items, 'gross'))} vs aggregate {money_text(payg_amount_value(payg_aggregate_value(raw, 'gross')))}; "
        f"withheld statement total {money_text(payg_item_amount_total(items, 'withheld'))} vs aggregate {money_text(payg_amount_value(payg_aggregate_value(raw, 'withheld')))}"
    )
    conflict_text = payg_alias_conflict_text(raw)
    if conflict_text:
        answer = f"{answer}; aggregate alias conflicts {conflict_text}"
    return guide_row(
        "PAYG-RECON",
        "1 Salary or wages",
        "PAYG income statement reconciliation",
        answer,
        "Itemized PAYG statement totals must be reconciled to supplied aggregate salary/wages and withholding before entry.",
        status,
        PAYG_SOURCES,
        tab_text=payg_reconciliation_tab_text(gross_conflict, withheld_conflict, aggregate_alias_conflict),
        row_kind="individual-return",
        facts=handoff_facts(
            ("gross-item-total", "Gross statement total", payg_item_amount_total(items, "gross")),
            ("gross-aggregate", "Gross aggregate supplied", payg_aggregate_value(raw, "gross")),
            ("withheld-item-total", "Withheld statement total", payg_item_amount_total(items, "withheld")),
            ("withheld-aggregate", "Withheld aggregate supplied", payg_aggregate_value(raw, "withheld")),
            ("alias-conflicts", "Aggregate alias conflicts", conflict_text or "none"),
        ),
    )


def payg_evidence_rows(raw: Dict[str, Any], answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    items = payg_item_values(raw.get("items"))
    aggregate_gaps = payg_aggregate_evidence_gaps(raw)
    if aggregate_gaps:
        rows.append(
            guide_row(
                f"PAYG-EVID-{len(rows) + 1}",
                "1 Salary or wages",
                "PAYG evidence required",
                f"PAYG aggregate facts: confirm {', '.join(aggregate_gaps)}",
                "PAYG aggregate rows are not ready for entry until supplied salary/wages facts and statement evidence are reconciled.",
                "Evidence",
                PAYG_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("aggregate-evidence", "PAYG aggregate evidence needed", ", ".join(aggregate_gaps)),
                ),
            )
        )
    for idx, item in enumerate(items, start=1):
        statement = payg_statement_missing(item.get("statement"))
        finalised = payg_finalised_missing(item.get("finalised"))
        payer = payg_payer_detail_missing(item)
        amounts = payg_item_amounts_need_evidence(item)
        lump = payg_lump_sum_label_evidence(item)
        decline = payg_decline_contradiction(item)
        alias = bool(item.get("_alias_conflicts"))
        if statement or finalised or payer or amounts or lump or decline or alias:
            rows.append(
                guide_row(
                    f"PAYG-EVID-{len(rows) + 1}",
                    "1 Salary or wages",
                    "PAYG evidence required",
                    payg_evidence_text(idx, statement, finalised, payer, amounts, lump, decline, alias),
                    "PAYG prep row is not ready for entry until statement, payer, amount, finalisation, and label evidence are resolved.",
                    "Evidence",
                    PAYG_SOURCES,
                    row_kind="evidence-queue",
                    facts=handoff_facts(
                        ("payg-item", "PAYG item", idx),
                        ("evidence-needed", "Evidence needed", payg_evidence_text(idx, statement, finalised, payer, amounts, lump, decline, alias)),
                    ),
                )
            )
    if items and payg_supplemental_needs_evidence(raw):
        rows.append(
            guide_row(
                f"PAYG-EVID-{len(rows) + 1}",
                "1 Salary or wages",
                "PAYG aggregate detail evidence required",
                payg_supplemental_tab_text(raw),
                "Flat PAYG details supplied with itemized statements are not ready for entry until amount, payer, and alias evidence is resolved.",
                "Evidence",
                PAYG_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("aggregate-details", "Aggregate details needing evidence", payg_supplemental_tab_text(raw)),
                ),
            )
        )
    gross_conflict = payg_reconciliation_conflict(payg_aggregate_value(raw, "gross"), payg_item_amount_total(items, "gross"), bool(items))
    withheld_conflict = payg_reconciliation_conflict(
        payg_aggregate_value(raw, "withheld"),
        payg_item_amount_total(items, "withheld"),
        bool(items),
    )
    aggregate_alias_conflict = bool(raw.get("_alias_conflicts"))
    if items and (gross_conflict or withheld_conflict or aggregate_alias_conflict):
        rows.append(
            guide_row(
                f"PAYG-EVID-{len(rows) + 1}",
                "1 Salary or wages",
                "PAYG reconciliation evidence required",
                payg_reconciliation_tab_text(gross_conflict, withheld_conflict, aggregate_alias_conflict),
                "Supplied aggregate PAYG totals and itemized income statement rows conflict or include unresolved item amounts.",
                "Evidence",
                PAYG_SOURCES,
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("reconciliation", "PAYG reconciliation evidence needed", payg_reconciliation_tab_text(gross_conflict, withheld_conflict, aggregate_alias_conflict)),
                ),
            )
        )
    return rows


def payg_item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        return []
    rows: List[Dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = normalize_payg_item(raw)
        if payg_item_has_facts(item):
            rows.append(item)
    return rows


def normalize_payg_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    item = normalize_payg_fields(payg_item_flat_aliases(raw))
    declines = payg_decline_values(raw)
    if declines:
        item = payg_values_with_declines(item, declines)
    return item


def payg_item_flat_aliases(raw: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(raw)
    conflicts = list(result.get("_alias_conflicts") or [])
    for flat_key, canonical in PAYG_FLAT_FIELD_KEYS.items():
        if flat_key not in raw or is_missing(raw.get(flat_key)):
            continue
        value = raw.get(flat_key)
        existing = result.get(canonical)
        if is_missing(existing):
            result[canonical] = value
        elif payg_values_conflict(canonical, existing, value):
            conflicts.append(canonical)
            if payg_prefer_merged_value(canonical, value, existing):
                result[canonical] = value
    if conflicts:
        result["_alias_conflicts"] = sorted(set(conflicts))
    return result


def payg_drop_absence_fields(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in raw.items()
        if not payg_field_absence_value(payg_canonical_field_key(key), value)
    }


def payg_canonical_field_key(key: str) -> str:
    return PAYG_FLAT_FIELD_KEYS.get(key, PAYG_ALIAS_TO_FIELD.get(key, key))


def normalize_payg_fields(raw: Dict[str, Any]) -> Dict[str, Any]:
    item: Dict[str, Any] = {}
    conflicts: List[str] = []
    for canonical, aliases in PAYG_FIELD_ALIASES.items():
        values = payg_alias_values(raw, aliases, canonical)
        if not values:
            continue
        chosen = values[0][1]
        if canonical in PAYG_AMOUNT_FIELDS:
            if payg_alias_amount_conflict([value for _, value in values]):
                conflicts.append(canonical)
            chosen = first_payg_alias_value(values, canonical)
        elif canonical in PAYG_BOOLEAN_FIELDS:
            if canonical == "finalised" and payg_alias_bool_conflict([value for _, value in values]):
                conflicts.append(canonical)
            elif canonical == "statement" and payg_alias_text_conflict([value for _, value in values]):
                conflicts.append(canonical)
            chosen = first_payg_alias_value(values, canonical)
            normalized = parse_payg_bool(chosen)
            if normalized is not None:
                chosen = normalized
        else:
            if payg_alias_text_conflict([value for _, value in values]):
                conflicts.append(canonical)
            chosen = first_payg_alias_value(values, canonical)
        item[canonical] = chosen
    if "lump_sum" in raw or "lump_sums" in raw:
        item["lump_sum"] = first_present(raw, ("lump_sum", "lump_sums"))
    if conflicts:
        item["_alias_conflicts"] = conflicts
    elif isinstance(raw.get("_alias_conflicts"), list):
        item["_alias_conflicts"] = raw.get("_alias_conflicts")
    return item


def payg_alias_values(raw: Dict[str, Any], aliases: tuple[str, ...], canonical: str) -> List[tuple[str, Any]]:
    return [
        (alias, raw.get(alias))
        for alias in aliases
        if payg_alias_value_usable(raw, alias, canonical)
    ]


def payg_alias_value_usable(raw: Dict[str, Any], alias: str, canonical: str) -> bool:
    if alias not in raw or is_missing(raw.get(alias)):
        return False
    if canonical in PAYG_AMOUNT_FIELDS and isinstance(raw.get(alias), (dict, list)):
        return False
    if canonical in PAYG_AMOUNT_FIELDS and payg_source_declines_workflow(canonical, raw.get(alias)):
        return False
    return not payg_field_absence_value(canonical, raw.get(alias))


def first_payg_alias_value(values: List[tuple[str, Any]], canonical: str) -> Any:
    for _, value in values:
        if payg_concrete_alias_value(value, canonical):
            return value
    for _, value in values:
        if contains_unknown(value):
            return value
    for _, value in values:
        if has_meaningful_value(value) or value is False:
            return value
    return values[0][1] if values else None


def payg_concrete_alias_value(value: Any, canonical: str) -> bool:
    if is_missing(value) or contains_unknown(value):
        return False
    if canonical in PAYG_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    return has_meaningful_value(value) or value is False


def payg_alias_bool_conflict(values: List[Any]) -> bool:
    parsed = [parse_payg_bool(value) for value in values if not is_missing(value)]
    if len(parsed) < 2:
        return False
    known = [value for value in parsed if value is not None]
    return any(value is None for value in parsed) or len(set(known)) > 1


def payg_item_has_facts(item: Dict[str, Any]) -> bool:
    if any(payg_amount_needs_evidence(item.get(key)) for key in PAYG_AMOUNT_FIELDS):
        return True
    if item.get("_alias_conflicts"):
        return True
    return any(
        has_meaningful_payg_item_value(key, value)
        for key, value in item.items()
    )


def has_meaningful_payg_item_value(key: str, value: Any) -> bool:
    if key == "_alias_conflicts":
        return bool(value)
    if key == "finalised" and value is False:
        return True
    if key in PAYG_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if payg_source_declines_workflow(key, value) or payg_field_absence_value(key, value):
        return False
    return has_meaningful_value(value) or contains_unknown(value)


def has_meaningful_payg_flat_value(key: str, value: Any) -> bool:
    if key in PAYG_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in PAYG_SOURCE_KEY_FACTS and (
        payg_source_declines_workflow(key, value) or payg_field_absence_value(key, value)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def has_unknown_payg_flat_value(key: str, value: Any) -> bool:
    if key in PAYG_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in PAYG_SOURCE_KEY_FACTS and (
        payg_source_declines_workflow(key, value) or payg_field_absence_value(key, value)
    ):
        return False
    return contains_unknown(value)


def payg_decline_values(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key in PAYG_SOURCE_KEY_FACTS and payg_source_declines_workflow(key, value)
    }


def payg_values_with_declines(values: Dict[str, Any], declines: Dict[str, Any]) -> Dict[str, Any]:
    if not declines or not payg_has_facts(values):
        return values
    merged = dict(values)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        canonical = PAYG_FLAT_FIELD_KEYS.get(key, PAYG_ALIAS_TO_FIELD.get(key, key))
        if canonical in PAYG_AMOUNT_FIELDS:
            continue
        if canonical not in merged:
            merged[canonical] = value
    merged[PAYG_DECLINE_SIGNAL_KEY] = signals
    return merged


def payg_has_facts(record: Dict[str, Any]) -> bool:
    if payg_item_values(record.get("items")):
        return True
    return any(
        has_meaningful_payg_flat_value(key, value) or payg_amount_field_needs_evidence(key, value)
        for key, value in record.items()
        if key not in ("items", PAYG_DECLINE_SIGNAL_KEY)
    )


def payg_decline_contradiction(raw: Dict[str, Any]) -> bool:
    return bool(raw.get(PAYG_DECLINE_SIGNAL_KEY))


def payg_source_declines_workflow(key: str, value: Any) -> bool:
    if payg_field_absence_value(key, value) or not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if key not in PAYG_ITEM_ALIASES and lowered in GENERIC_FIELD_ABSENCE_PHRASES:
        return False
    if payg_document_context(lowered):
        return False
    return lowered in PAYG_DECLINE_PHRASES or any(
        phrase in lowered
        for phrase in (
            "do not have any payg",
            "do not have payg",
            "don't have any payg",
            "don't have payg",
            "dont have any payg",
            "dont have payg",
            "do not have salary or wages",
            "don't have salary or wages",
            "dont have salary or wages",
        )
    )


def payg_field_absence_value(key: str, value: Any) -> bool:
    if key in ("statement", "finalised") or not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if lowered in PAYG_DECLINE_PHRASES and lowered not in GENERIC_FIELD_ABSENCE_PHRASES:
        return False
    return lowered in GENERIC_FIELD_ABSENCE_PHRASES


def payg_document_context(lowered: str) -> bool:
    return "statement" in lowered or "payment summary" in lowered


def payg_statement_missing(statement: Any) -> bool:
    if isinstance(statement, bool):
        return not statement
    if is_missing(statement) or contains_unknown(statement):
        return True
    lowered = text(statement).strip().lower()
    return (
        lowered in {"no", "n", "false", "none", "not held", "not available"}
        or lowered in GENERIC_FIELD_ABSENCE_PHRASES
        or any(phrase in lowered for phrase in PAYG_STATEMENT_MISSING_PHRASES)
    )


def payg_finalised_missing(value: Any) -> bool:
    parsed = parse_payg_bool(value)
    if parsed is True:
        return False
    if parsed is False:
        return True
    if is_missing(value) or contains_unknown(value):
        return True
    lowered = text(value).strip().lower()
    if any(term in lowered for term in ("unfinalised", "not final", "not tax ready", "not ready")):
        return True
    return bool(lowered)


def parse_payg_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
    if not isinstance(value, str) or contains_unknown(value):
        return None
    lowered = value.strip().lower()
    if lowered in {"yes", "y", "true", "1", "on", "checked", "final", "finalised", "finalized", "tax ready"}:
        return True
    if lowered in {"no", "n", "false", "0", "off", "unchecked", "unfinalised", "unfinalized", "not final", "not tax ready"}:
        return False
    return None


def payg_payer_detail_missing(item: Dict[str, Any]) -> bool:
    return payg_required_text_missing(item.get("payer")) or payg_required_text_missing(item.get("abn"))


def payg_required_text_missing(value: Any) -> bool:
    return is_missing(value) or contains_unknown(value) or payg_field_absence_value("", value)


def payg_item_amounts_need_evidence(item: Dict[str, Any]) -> bool:
    if item.get("_alias_conflicts"):
        return True
    if any(not payg_amount_is_supplied(item.get(key)) for key in PAYG_REQUIRED_AMOUNT_FIELDS):
        return True
    return any(payg_amount_needs_evidence(item.get(key)) for key in PAYG_AMOUNT_FIELDS)


def payg_amount_is_supplied(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    return payg_amount_value(value) is not None


def payg_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    return contains_unknown(value) or payg_amount_malformed(value)


def payg_amount_field_needs_evidence(key: str, value: Any) -> bool:
    return key in PAYG_AMOUNT_FIELDS and payg_amount_needs_evidence(value)


def payg_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return False


def payg_amount_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def payg_item_amount_total(items: List[Dict[str, Any]], key: str) -> Optional[float]:
    amounts = [payg_amount_value(item.get(key)) for item in items]
    if not amounts or any(amount is None for amount in amounts):
        return None
    return round(sum(amounts), 2)


def payg_aggregate_value(raw: Dict[str, Any], key: str) -> Any:
    return raw.get(key)


def payg_aggregate_evidence_gaps(raw: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    if payg_decline_contradiction(raw):
        gaps.append("no-PAYG answer with PAYG facts")
    if "statement" in raw and payg_statement_missing(raw.get("statement")):
        gaps.append("income statement evidence")
    if "finalised" in raw and payg_finalised_missing(raw.get("finalised")):
        gaps.append("finalised/tax-ready status")
    if payg_aggregate_payer_detail_gap(raw):
        gaps.append("payer name or ABN")
    if any(payg_amount_needs_evidence(raw.get(key)) for key in PAYG_AMOUNT_FIELDS):
        gaps.append("numeric amount evidence")
    if payg_lump_sum_label_evidence(raw):
        gaps.append("lump sum label evidence")
    if raw.get("_alias_conflicts"):
        gaps.append("aggregate alias conflict")
    return gaps


def payg_aggregate_payer_detail_gap(raw: Dict[str, Any]) -> bool:
    return any(key in raw for key in ("payer", "abn")) and payg_payer_detail_missing(raw)


def payg_reconciliation_conflict(aggregate_value: Any, item_total: Optional[float], has_items: bool) -> bool:
    if not has_items:
        return False
    if payg_amount_needs_evidence(aggregate_value):
        return True
    aggregate = payg_amount_value(aggregate_value)
    if aggregate is None:
        return False
    return item_total is None or round(abs(aggregate - item_total), 2) >= 0.01


def payg_has_reconciliation_target(raw: Dict[str, Any]) -> bool:
    return not is_missing(payg_aggregate_value(raw, "gross")) or not is_missing(payg_aggregate_value(raw, "withheld"))


def payg_alias_amount_conflict(values: List[Any]) -> bool:
    amounts = [payg_amount_value(value) for value in values if not is_missing(value)]
    if any(amount is None for amount in amounts):
        return True
    if len(amounts) < 2:
        return False
    first = amounts[0]
    return any(round(abs(first - amount), 2) >= 0.01 for amount in amounts[1:])


def payg_alias_text_conflict(values: List[Any]) -> bool:
    texts = [display_value(value).strip().lower() for value in values if display_value(value)]
    return len(set(texts)) > 1


def payg_lump_sum_label_evidence(item: Dict[str, Any]) -> bool:
    if payg_field_absence_value("lump_sum", item.get("lump_sum")):
        return False
    if has_meaningful_value(item.get("lump_sum")) or contains_unknown(item.get("lump_sum")):
        return True
    return any(payg_amount_needs_evidence(item.get(key)) for key in ("lump_sum_a", "lump_sum_b", "lump_sum_d", "lump_sum_e"))


def payg_display_text(item: Dict[str, Any], key: str) -> str:
    value = item.get(key)
    if key in PAYG_BOOLEAN_FIELDS:
        return payg_boolean_text(value)
    if payg_field_absence_value(key, value):
        return "unknown"
    return display_value(value) or "unknown"


def payg_boolean_text(value: Any) -> str:
    parsed = parse_payg_bool(value)
    if parsed is True:
        return "true"
    if parsed is False:
        return "false"
    return display_value(value) or "unknown"


def payg_tab_text(
    statement: bool,
    finalised: bool,
    payer: bool,
    amounts: bool,
    lump: bool,
    decline: bool,
    conflict: bool,
) -> str:
    gaps: List[str] = []
    if decline:
        gaps.append("no-PAYG answer with PAYG facts")
    if statement:
        gaps.append("income statement evidence")
    if finalised:
        gaps.append("finalised/tax-ready status")
    if payer:
        gaps.append("payer name or ABN")
    if amounts:
        gaps.append("numeric amount evidence")
    if lump:
        gaps.append("lump sum label evidence")
    if conflict:
        gaps.append("aggregate reconciliation")
    if gaps:
        return f"PAYG statement needs {', '.join(gaps)} before accountant review."
    return "PAYG statement requires accountant review before entry."


def payg_reconciliation_tab_text(gross_conflict: bool, withheld_conflict: bool, alias_conflict: bool = False) -> str:
    gaps: List[str] = []
    if gross_conflict:
        gaps.append("gross salary/wages total")
    if withheld_conflict:
        gaps.append("tax withheld total")
    if alias_conflict:
        gaps.append("aggregate alias conflict")
    if gaps:
        return f"PAYG totals need corrected reconciliation for {', '.join(gaps)} before accountant review."
    return "PAYG statement totals reconcile to supplied aggregates; still prep-only and review-first."


def payg_evidence_text(
    index: int,
    statement: bool,
    finalised: bool,
    payer: bool,
    amounts: bool,
    lump: bool,
    decline: bool,
    alias: bool = False,
) -> str:
    gaps: List[str] = []
    if decline:
        gaps.append("no-PAYG answer with PAYG facts")
    if alias:
        gaps.append("alias conflicts")
    if statement:
        gaps.append("income statement")
    if finalised:
        gaps.append("finalised/tax-ready status")
    if payer:
        gaps.append("payer name or ABN")
    if amounts:
        gaps.append("amount values")
    if lump:
        gaps.append("lump sum labels")
    return f"PAYG statement item {index}: confirm {', '.join(gaps)}"


def payg_decline_signal_text(raw: Dict[str, Any]) -> str:
    signals = raw.get(PAYG_DECLINE_SIGNAL_KEY)
    if not isinstance(signals, list):
        return ""
    return ", ".join(display_value(signal) for signal in signals if display_value(signal))


def payg_alias_conflict_text(raw: Dict[str, Any]) -> str:
    conflicts = raw.get("_alias_conflicts")
    if not isinstance(conflicts, list):
        return ""
    return ", ".join(display_value(conflict) for conflict in conflicts if display_value(conflict))


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
    merged = {key: value for key, value in flat.items() if has_meaningful_payment_signal(key, value, group)}
    flat_declines = payment_decline_values(flat, group)
    if not isinstance(raw, dict) or not has_meaningful_value(raw):
        return payment_values_with_declines(merged, flat_declines, group)
    raw_declines = payment_decline_values(raw, group)
    for key, value in raw.items():
        if has_meaningful_payment_signal(key, value, group):
            merged[key] = value
        elif key not in merged and has_explicit_payment_evidence_gap(key, value, group):
            merged[key] = value
    return payment_values_with_declines(merged, {**flat_declines, **raw_declines}, group)


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
    decline_evidence = payment_decline_contradiction(raw)
    status = "Evidence" if amount_evidence or statement_evidence or decline_evidence else "Accountant review"
    answer = (
        f"Payer {complex_payment_display_text(raw, 'payer', group)}; "
        f"type {complex_payment_display_text(raw, 'payment_type', group)}; "
        f"date {complex_payment_display_text(raw, 'payment_date', group)}; "
        f"code {complex_payment_display_text(raw, 'code', group)}; "
        f"taxable component {money_text(complex_payment_money_value(raw.get('taxable_component')))}; "
        f"tax-free component {money_text(complex_payment_money_value(raw.get('tax_free_component')))}; "
        f"tax withheld {money_text(complex_payment_money_value(raw.get('tax_withheld')))}"
    )
    decline_text = payment_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    return [
        guide_row(
            "ETP",
            "Employment termination payments",
            "ETP payment summary workflow",
            answer,
            "ETP records need payment summary/income statement evidence, payment code, component split, cap context, and accountant review before entry.",
            status,
            ATO_ETP_SOURCE,
            tab_text=complex_payment_tab_text("ETP", statement_evidence, amount_evidence, decline_evidence),
            row_kind="extended-section",
            facts=handoff_facts(
                ("payer", "Payer", raw.get("payer")),
                ("payment-type", "Payment type", raw.get("payment_type")),
                ("payment-date", "Payment date", raw.get("payment_date")),
                ("code", "ETP code", raw.get("code")),
                ("taxable-component", "Taxable component", raw.get("taxable_component")),
                ("tax-free-component", "Tax-free component", raw.get("tax_free_component")),
                ("tax-withheld", "Tax withheld", raw.get("tax_withheld")),
                ("statement", "Statement evidence", raw.get("statement")),
                ("decline-signals", "Decline signals", decline_text or "none"),
            ),
        )
    ]


def lump_sum_arrears_rows(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    group = "lump_sum_arrears"
    if not has_complex_payment_inputs(raw, group):
        return []
    amount_evidence = payment_amounts_need_evidence(raw, ("amount", "tax_withheld"))
    statement_evidence = complex_payment_statement_missing(raw.get("statement"), group)
    decline_evidence = payment_decline_contradiction(raw)
    prior_year_evidence = is_missing(raw.get("payment_years")) or contains_unknown(raw.get("payment_years"))
    status = "Evidence" if amount_evidence or statement_evidence or decline_evidence or prior_year_evidence else "Accountant review"
    answer = (
        f"Payer {complex_payment_display_text(raw, 'payer', group)}; "
        f"prior years {complex_payment_display_text(raw, 'payment_years', group)}; "
        f"amount {money_text(complex_payment_money_value(raw.get('amount')))}; "
        f"tax withheld {money_text(complex_payment_money_value(raw.get('tax_withheld')))}"
    )
    decline_text = payment_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    return [
        guide_row(
            "LUMP-ARREARS",
            "Lump sum payment in arrears",
            "Lump sum in arrears workflow",
            answer,
            "Lump sum in arrears records need statement evidence, prior-year allocation, amount, withholding, and accountant review before entry.",
            status,
            ATO_LUMP_SUM_ARREARS_SOURCE,
            tab_text=lump_sum_arrears_tab_text(statement_evidence, prior_year_evidence, amount_evidence, decline_evidence),
            row_kind="extended-section",
            facts=handoff_facts(
                ("payer", "Payer", raw.get("payer")),
                ("prior-years", "Prior payment years", raw.get("payment_years")),
                ("amount", "Amount", raw.get("amount")),
                ("tax-withheld", "Tax withheld", raw.get("tax_withheld")),
                ("statement", "Statement evidence", raw.get("statement")),
                ("decline-signals", "Decline signals", decline_text or "none"),
            ),
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
    decline_evidence = payment_decline_contradiction(raw)
    status = "Evidence" if amount_evidence or statement_evidence or decline_evidence else "Accountant review"
    answer = (
        f"Fund {complex_payment_display_text(raw, 'fund', group)}; "
        f"kind {complex_payment_display_text(raw, 'payment_kind', group)}; "
        f"taxable component {money_text(complex_payment_money_value(raw.get('taxable_component')))}; "
        f"tax-free component {money_text(complex_payment_money_value(raw.get('tax_free_component')))}; "
        f"income-stream taxable amount {money_text(complex_payment_money_value(raw.get('taxable_amount')))}; "
        f"tax withheld {money_text(complex_payment_money_value(raw.get('tax_withheld')))}"
    )
    decline_text = payment_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    return [
        guide_row(
            "SUPER-INCOME",
            "Superannuation lump sum or income stream",
            "Super lump sum or income stream workflow",
            answer,
            "Super lump sums and income streams need fund statement evidence, component split, withholding, age/condition context, and accountant review before entry.",
            status,
            [ATO_SUPER_PENSIONS_SOURCE, ATO_SUPER_LUMP_SUM_SOURCE, ATO_SUPER_STREAM_SOURCE],
            tab_text=complex_payment_tab_text("Super income", statement_evidence, amount_evidence, decline_evidence),
            row_kind="extended-section",
            facts=handoff_facts(
                ("fund", "Fund", raw.get("fund")),
                ("payment-kind", "Payment kind", raw.get("payment_kind")),
                ("taxable-component", "Taxable component", raw.get("taxable_component")),
                ("tax-free-component", "Tax-free component", raw.get("tax_free_component")),
                ("taxable-amount", "Income-stream taxable amount", raw.get("taxable_amount")),
                ("tax-withheld", "Tax withheld", raw.get("tax_withheld")),
                ("statement", "Statement evidence", raw.get("statement")),
                ("decline-signals", "Decline signals", decline_text or "none"),
            ),
        )
    ]


def has_complex_payment_inputs(raw: Dict[str, Any], group: Optional[str] = None) -> bool:
    if not isinstance(raw, dict):
        return False
    if payment_declines_without_facts(raw, group):
        return False
    if any(has_explicit_payment_evidence_gap(key, raw.get(key), group) for key in ("statement", *COMPLEX_PAYMENT_AMOUNT_FIELDS)):
        return True
    return any(has_meaningful_payment_signal(key, value, group) for key, value in raw.items())


def payment_declines_without_facts(raw: Dict[str, Any], group: Optional[str] = None) -> bool:
    if not payment_decline_values(raw, group):
        return False
    return not any(
        has_meaningful_payment_signal(key, value, group) or has_explicit_payment_evidence_gap(key, value, group)
        for key, value in raw.items()
        if key != PAYMENT_DECLINE_SIGNAL_KEY
        and not complex_payment_source_declines_workflow(key, value, group)
        and not complex_payment_field_absence_value(key, value, group)
    )


def payment_decline_values(raw: Dict[str, Any], group: Optional[str] = None) -> Dict[str, Any]:
    return {
        key: value
        for key, value in raw.items()
        if key in COMPLEX_PAYMENT_SOURCE_KEY_FACTS and complex_payment_source_declines_workflow(key, value, group)
    }


def payment_values_with_declines(
    merged: Dict[str, Any],
    declines: Dict[str, Any],
    group: Optional[str] = None,
) -> Dict[str, Any]:
    if not declines:
        return merged
    if not any(
        has_meaningful_payment_signal(key, value, group) or has_explicit_payment_evidence_gap(key, value, group)
        for key, value in merged.items()
        if key != PAYMENT_DECLINE_SIGNAL_KEY
        and not complex_payment_source_declines_workflow(key, value, group)
        and not complex_payment_field_absence_value(key, value, group)
    ):
        return merged
    out = dict(merged)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        if not has_meaningful_payment_signal(key, out.get(key), group):
            out[key] = value
    out[PAYMENT_DECLINE_SIGNAL_KEY] = signals
    return out


def payment_decline_contradiction(raw: Dict[str, Any]) -> bool:
    return bool(raw.get(PAYMENT_DECLINE_SIGNAL_KEY))


def has_meaningful_payment_signal(key: str, value: Any, group: Optional[str] = None) -> bool:
    if key in COMPLEX_PAYMENT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in COMPLEX_PAYMENT_SOURCE_KEY_FACTS and (
        complex_payment_source_declines_workflow(key, value, group)
        or complex_payment_field_absence_value(key, value, group)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def has_explicit_payment_evidence_gap(key: str, value: Any, group: Optional[str] = None) -> bool:
    if key in COMPLEX_PAYMENT_AMOUNT_FIELDS:
        return complex_payment_amount_needs_evidence(value)
    if key in COMPLEX_PAYMENT_SOURCE_KEY_FACTS and (
        complex_payment_source_declines_workflow(key, value, group)
        or complex_payment_field_absence_value(key, value, group)
    ):
        return False
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
    return (
        lowered in COMPLEX_PAYMENT_DECLINE_PHRASES
        or lowered in group_phrases
        or complex_payment_absence_decline_phrase(lowered, group)
    )


def complex_payment_absence_decline_phrase(lowered: str, group: Optional[str] = None) -> bool:
    if complex_payment_document_context(lowered):
        return False
    if not any(phrase in lowered for phrase in ("do not have", "don't have", "dont have")):
        return False
    group_terms = {
        "etp": ("etp", "employment termination payment"),
        "lump_sum_arrears": ("lump sum", "lump sum in arrears", "lump sums in arrears"),
        "super_income": ("super lump sum", "super income stream", "super pension", "super annuity"),
    }.get(group or "", ())
    return any(term in lowered for term in group_terms)


def complex_payment_document_context(lowered: str) -> bool:
    return any(term in lowered for term in ("statement", "payment summary", "income statement", "fund statement"))


def complex_payment_source_declines_workflow(key: str, value: Any, group: Optional[str] = None) -> bool:
    if complex_payment_field_absence_value(key, value, group):
        return False
    return complex_payment_declines_workflow(value, group)


def complex_payment_field_absence_value(key: str, value: Any, group: Optional[str] = None) -> bool:
    if key == "statement" or not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    group_phrases = COMPLEX_PAYMENT_DECLINE_PHRASES_BY_GROUP.get(group or "", ())
    if lowered in group_phrases:
        return False
    return lowered in GENERIC_FIELD_ABSENCE_PHRASES


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


def complex_payment_display_text(raw: Dict[str, Any], key: str, group: Optional[str] = None) -> str:
    if complex_payment_field_absence_value(key, raw.get(key), group):
        return "unknown"
    return display_value(raw.get(key)) or "unknown"


def complex_payment_tab_text(label: str, statement_evidence: bool, amount_evidence: bool, decline_evidence: bool = False) -> str:
    if decline_evidence:
        return f"{label} has a no-payment answer with payment facts; resolve before accountant review."
    if statement_evidence and amount_evidence:
        return f"{label} needs statement evidence and numeric amount evidence before accountant review."
    if amount_evidence:
        return f"{label} amount fields need numeric amount evidence before accountant review."
    if statement_evidence:
        return f"{label} needs statement evidence before accountant review."
    return f"{label} needs source-backed accountant review."


def lump_sum_arrears_tab_text(
    statement_evidence: bool,
    prior_year_evidence: bool,
    amount_evidence: bool,
    decline_evidence: bool = False,
) -> str:
    evidence = []
    if decline_evidence:
        evidence.append("no-payment answer with payment facts")
    if statement_evidence:
        evidence.append("statement evidence")
    if prior_year_evidence:
        evidence.append("prior-year allocation evidence")
    if amount_evidence:
        evidence.append("numeric amount evidence")
    if evidence:
        return f"Lump sum in arrears needs {', '.join(evidence)} before accountant review."
    return "Lump sum in arrears needs source-backed accountant review."


def payment_decline_signal_text(raw: Dict[str, Any]) -> str:
    signals = raw.get(PAYMENT_DECLINE_SIGNAL_KEY)
    if not isinstance(signals, list):
        return ""
    return ", ".join(display_value(signal) for signal in signals if display_value(signal))


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
    flat_declines = foreign_income_decline_values(fields)
    if not isinstance(raw, dict):
        return foreign_income_values_with_declines(flat_values, flat_declines)
    if not has_meaningful_value(raw):
        return foreign_income_values_with_declines(flat_values, flat_declines)
    raw_declines = foreign_income_decline_values(raw)
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
    return foreign_income_values_with_declines(merged, {**flat_declines, **raw_declines})


def foreign_income_should_merge_boolean_signal(merged: Dict[str, Any], key: str, value: Any) -> bool:
    if key not in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS:
        return False
    if not (isinstance(value, bool) or has_meaningful_value(value)):
        return False
    return not foreign_income_should_ignore_boolean_signal(merged, key, value)


def foreign_income_should_ignore_boolean_signal(merged: Dict[str, Any], key: str, value: Any) -> bool:
    return (
        key in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS
        and foreign_income_positive_claim_signal(key, merged.get(key))
        and foreign_income_negative_claim_signal(key, value)
    )


def foreign_income_positive_claim_signal(key: str, value: Any) -> bool:
    if key == "foreign_tax_offset_claim":
        return foreign_income_offset_claimed(value)
    if key == "foreign_employment_exempt_claim":
        return foreign_income_exemption_claimed(value)
    return value is True


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
    if key in FOREIGN_INCOME_SOURCE_KEY_FACTS and (
        foreign_income_source_declines_workflow(key, value) or foreign_income_field_absence_value(key, value)
    ):
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
    decline_evidence = foreign_income_decline_contradiction(raw, items)
    status = "Evidence" if statement_evidence or amount_evidence or residency_evidence or tax_paid_evidence or decline_evidence else "Accountant review"
    answer = (
        f"Country {foreign_income_country_text(raw, items)}; "
        f"type {foreign_income_field_text(raw, items, 'income_type')}; "
        f"payer {foreign_income_field_text(raw, items, 'payer')}; "
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
    decline_text = foreign_income_decline_signal_text(raw, items)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    return [
        guide_row(
            "FOREIGN-INCOME",
            "Foreign and worldwide income",
            "Foreign income, residency, and tax offset workflow",
            answer,
            "Foreign income needs source statement evidence, residency or temporary-resident context, foreign tax paid records, exchange-rate support, and accountant review before entry.",
            status,
            ATO_FOREIGN_INCOME_SOURCES,
            tab_text=foreign_income_tab_text(
                statement_evidence,
                amount_evidence,
                residency_evidence,
                tax_paid_evidence,
                decline_evidence,
            ),
            row_kind="extended-section",
            facts=[
                *handoff_facts(
                    ("country", "Country", raw.get("country")),
                    ("income-type", "Income type", raw.get("income_type")),
                    ("payer", "Payer", raw.get("payer")),
                    ("amount", "Prepared foreign income total", amount),
                    ("foreign-tax-paid", "Prepared foreign tax paid total", foreign_tax_paid),
                    ("exchange-rate", "Supplied exchange rate", raw.get("exchange_rate")),
                    ("residency", "Residency context", raw.get("residency_status")),
                    ("foreign-tax-offset-claim", "Foreign tax offset claim", raw.get("foreign_tax_offset_claim")),
                    ("employment-exemption-claim", "Foreign employment exemption claim", raw.get("foreign_employment_exempt_claim")),
                    ("decline-signals", "Decline signals", decline_text or "none"),
                ),
                *indexed_item_handoff_facts("foreign-item", "Foreign income item", items),
            ],
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
    if key in FOREIGN_INCOME_SOURCE_KEY_FACTS and (
        foreign_income_source_declines_workflow(key, value) or foreign_income_field_absence_value(key, value)
    ):
        return False
    return has_meaningful_value(value)


def has_explicit_foreign_income_evidence_gap(key: str, value: Any) -> bool:
    if key in FOREIGN_INCOME_AMOUNT_FIELDS:
        return foreign_income_amount_needs_evidence(value)
    if key in FOREIGN_INCOME_SOURCE_KEY_FACTS and (
        foreign_income_source_declines_workflow(key, value) or foreign_income_field_absence_value(key, value)
    ):
        return False
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
    if not foreign_income_decline_values(raw):
        return False
    if foreign_income_item_values(raw.get("items")):
        return False
    return not any(
        has_meaningful_foreign_income_signal(key, value) or has_explicit_foreign_income_evidence_gap(key, value)
        for key, value in raw.items()
        if key != FOREIGN_INCOME_DECLINE_SIGNAL_KEY
        and not foreign_income_source_declines_workflow(key, value)
        and not foreign_income_field_absence_value(key, value)
    )


def foreign_income_decline_values(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key in FOREIGN_INCOME_SOURCE_KEY_FACTS and foreign_income_source_declines_workflow(key, value)
    }


def foreign_income_values_with_declines(values: Dict[str, Any], declines: Dict[str, Any]) -> Dict[str, Any]:
    if not declines:
        return values
    if not foreign_income_has_facts(values):
        return values
    merged = dict(values)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        if not has_meaningful_foreign_income_signal(key, merged.get(key)):
            merged[key] = value
    merged[FOREIGN_INCOME_DECLINE_SIGNAL_KEY] = signals
    return merged


def foreign_income_has_facts(record: Dict[str, Any]) -> bool:
    if foreign_income_item_values(record.get("items")):
        return True
    return any(
        has_meaningful_foreign_income_signal(key, value) or has_explicit_foreign_income_evidence_gap(key, value)
        for key, value in record.items()
        if key not in ("items", FOREIGN_INCOME_DECLINE_SIGNAL_KEY)
        and not foreign_income_source_declines_workflow(key, value)
        and not foreign_income_field_absence_value(key, value)
    )


def foreign_income_decline_contradiction(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return bool(raw.get(FOREIGN_INCOME_DECLINE_SIGNAL_KEY)) or any(
        foreign_income_decline_values(item) and foreign_income_has_facts(item)
        for item in items
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


def foreign_income_source_declines_workflow(key: str, value: Any) -> bool:
    if foreign_income_field_absence_value(key, value):
        return False
    if key in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS and foreign_income_claim_negative(key, value):
        return False
    return foreign_income_declines_workflow(value)


def foreign_income_field_absence_value(key: str, value: Any) -> bool:
    if key == "statement" or not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if foreign_income_decline_phrase_is_tax_paid_context(lowered):
        return False
    if foreign_income_claim_negative(key, value):
        return False
    whole_workflow_phrases = {"no foreign income", "no foreign employment", "no foreign pension", "no foreign pensions"}
    if lowered in whole_workflow_phrases:
        return False
    return lowered in GENERIC_FIELD_ABSENCE_PHRASES


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
            "dont have any foreign income",
            "dont have foreign income",
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
            "dont have",
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


def foreign_income_exemption_claimed(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        lowered = value.strip().lower()
        if foreign_income_exemption_claim_negative(value):
            return False
        return lowered in {"yes", "y", "true", "claimed", "claim", "exempt"} or any(
            phrase in lowered
            for phrase in (
                "yes,",
                "claiming",
                "will claim",
                "intend to claim",
                "claim the exemption",
                "claim foreign employment exemption",
                "foreign employment exemption applies",
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
    if foreign_income_items_need_amount_evidence(items):
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


def foreign_income_items_need_amount_evidence(items: List[Dict[str, Any]]) -> bool:
    return any(not foreign_income_amount_is_supplied(item.get("amount")) for item in items)


def foreign_income_amount_is_supplied(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    return foreign_income_money_value(value) is not None


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
    amounts: List[Optional[float]] = []
    for item in items:
        amount = foreign_income_money_value(item.get(key))
        if amount is None and alias:
            amount = foreign_income_money_value(item.get(alias))
        amounts.append(amount)
    if not amounts or any(amount is None for amount in amounts):
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
    direct = foreign_income_record_field_text(raw, "country")
    if direct:
        return direct
    countries = [value for item in items if (value := foreign_income_record_field_text(item, "country"))]
    return ", ".join(countries) if countries else "unknown"


def foreign_income_field_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
    direct = foreign_income_record_field_text(raw, key)
    if direct:
        return direct
    values = [value for item in items if (value := foreign_income_record_field_text(item, key))]
    return ", ".join(values) if values else "unknown"


def foreign_income_claim_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
    if key in raw:
        if foreign_income_field_absence_value(key, raw.get(key)):
            return "unknown"
        return display_value(raw.get(key)) or "unknown"
    values = [
        display_value(item.get(key))
        for item in items
        if key in item and not foreign_income_field_absence_value(key, item.get(key))
    ]
    return ", ".join(values) if values else "unknown"


def foreign_income_items_text(items: List[Dict[str, Any]]) -> str:
    details: List[str] = []
    for idx, item in enumerate(items, start=1):
        label = foreign_income_record_field_text(item, "country") or foreign_income_record_field_text(item, "payer") or f"item {idx}"
        tax_paid = item.get("foreign_tax_paid")
        if is_missing(tax_paid):
            tax_paid = item.get("tax_paid")
        details.append(
            f"{label}: type {foreign_income_record_field_text(item, 'income_type') or 'unknown'}, "
            f"amount {money_text(foreign_income_money_value(item.get('amount')))}, "
            f"foreign tax paid {money_text(foreign_income_money_value(tax_paid))}, "
            f"exchange rate {foreign_income_rate_text(foreign_income_money_value(item.get('exchange_rate')))}"
        )
    return " | ".join(details)


def foreign_income_decline_signal_text(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    signals = raw.get(FOREIGN_INCOME_DECLINE_SIGNAL_KEY)
    values = [display_value(signal) for signal in signals if display_value(signal)] if isinstance(signals, list) else []
    for idx, item in enumerate(items, start=1):
        values.extend(
            f"item {idx} {key} {display_value(value)}"
            for key, value in foreign_income_decline_values(item).items()
            if display_value(value)
        )
    return ", ".join(values)


def foreign_income_record_field_text(record: Dict[str, Any], key: str) -> str:
    if foreign_income_field_absence_value(key, record.get(key)):
        return ""
    return display_value(record.get(key))


def foreign_income_rate_text(value: Optional[float]) -> str:
    return "unknown" if value is None else f"{value:.6g}"


def foreign_income_tab_text(
    statement_evidence: bool,
    amount_evidence: bool,
    residency_evidence: bool,
    tax_paid_evidence: bool,
    decline_evidence: bool = False,
) -> str:
    evidence = []
    if decline_evidence:
        evidence.append("no-foreign-income answer with foreign income facts")
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


def psi_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("psi")
    fields = {
        "income": answers.get("psi_income"),
        "income_type": answers.get("psi_income_type"),
        "occupation": answers.get("psi_occupation"),
        "client": answers.get("psi_client"),
        "contract_evidence": answers.get("psi_contract_evidence"),
        "results_test": answers.get("psi_results_test"),
        "eighty_percent_test": answers.get("psi_80_percent_test"),
        "unrelated_clients_test": answers.get("psi_unrelated_clients_test"),
        "employment_test": answers.get("psi_employment_test"),
        "business_premises_test": answers.get("psi_business_premises_test"),
        "psb_determination": answers.get("psi_psb_determination"),
        "attribution_entity": answers.get("psi_attribution_entity"),
        "deductions": answers.get("psi_deductions"),
        "business_structure": answers.get("psi_business_structure"),
    }
    flat_values = {key: value for key, value in fields.items() if has_meaningful_psi_flat_value(key, value)}
    flat_declines = psi_decline_values(fields)
    if not isinstance(raw, dict):
        return psi_values_with_declines(flat_values, flat_declines)
    if not has_meaningful_value(raw):
        return psi_values_with_declines(flat_values, flat_declines)
    raw_declines = psi_decline_values(raw)
    merged = dict(flat_values)
    for key, value in raw.items():
        if has_meaningful_psi_override(key, value):
            merged[key] = value
        elif key not in merged and has_explicit_psi_evidence_gap(key, value):
            merged[key] = value
    return psi_values_with_declines(merged, {**flat_declines, **raw_declines})


def psi_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_psi_inputs(raw):
        return []
    if not isinstance(raw, dict):
        return []
    income = psi_money_value(raw.get("income"))
    evidence = psi_evidence_gaps(raw)
    status = "Evidence" if evidence else "Accountant review"
    answer = (
        f"Income {money_text(income)}; "
        f"type {psi_display_text(raw, 'income_type')}; "
        f"occupation {psi_display_text(raw, 'occupation')}; "
        f"client {psi_display_text(raw, 'client')}; "
        f"contract evidence {psi_display_text(raw, 'contract_evidence')}; "
        f"results test {psi_bool_text(raw.get('results_test'))}; "
        f"80% test {psi_bool_text(raw.get('eighty_percent_test'))}; "
        f"unrelated clients test {psi_bool_text(raw.get('unrelated_clients_test'))}; "
        f"employment test {psi_bool_text(raw.get('employment_test'))}; "
        f"business premises test {psi_bool_text(raw.get('business_premises_test'))}; "
        f"PSB determination {psi_bool_text(raw.get('psb_determination'))}; "
        f"attribution {psi_display_text(raw, 'attribution_entity')}; "
        f"deductions {psi_display_text(raw, 'deductions')}; "
        f"structure {psi_display_text(raw, 'business_structure')}"
    )
    decline_text = psi_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    return [
        guide_row(
            "PSI",
            "Personal services income",
            "PSI tests, attribution, deductions, and structure workflow",
            answer,
            "PSI handling collects test facts, contracts, client concentration, attribution, deductions, and structure impacts for accountant review before entry.",
            status,
            ATO_PSI_SOURCES,
            tab_text=psi_tab_text(evidence),
            row_kind="extended-section",
            facts=handoff_facts(
                ("income", "PSI income", raw.get("income")),
                ("income-type", "Income type", raw.get("income_type")),
                ("occupation", "Occupation", raw.get("occupation")),
                ("client", "Client", raw.get("client")),
                ("contract-evidence", "Contract evidence", raw.get("contract_evidence")),
                ("results-test", "Results test", raw.get("results_test")),
                ("eighty-percent-test", "80% test", raw.get("eighty_percent_test")),
                ("unrelated-clients-test", "Unrelated clients test", raw.get("unrelated_clients_test")),
                ("employment-test", "Employment test", raw.get("employment_test")),
                ("business-premises-test", "Business premises test", raw.get("business_premises_test")),
                ("psb-determination", "PSB determination", raw.get("psb_determination")),
                ("attribution", "Attribution entity", raw.get("attribution_entity")),
                ("deductions", "Deductions supplied", raw.get("deductions")),
                ("structure", "Business structure", raw.get("business_structure")),
                ("decline-signals", "Decline signals", decline_text or "none"),
            ),
        )
    ]


def has_meaningful_psi_flat_value(key: str, value: Any) -> bool:
    if key in PSI_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in PSI_SOURCE_KEY_FACTS and (
        psi_source_declines_workflow(key, value) or psi_field_absence_value(key, value)
    ):
        return False
    return has_meaningful_value(value)


def has_meaningful_psi_override(key: str, value: Any) -> bool:
    if key in PSI_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in PSI_SOURCE_KEY_FACTS and (
        psi_source_declines_workflow(key, value) or psi_field_absence_value(key, value)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def has_explicit_psi_evidence_gap(key: str, value: Any) -> bool:
    if key in PSI_SOURCE_KEY_FACTS and (
        psi_source_declines_workflow(key, value) or psi_field_absence_value(key, value)
    ):
        return False
    if key in PSI_AMOUNT_FIELDS:
        return psi_amount_needs_evidence(value)
    if key in PSI_SOURCE_KEY_FACTS:
        return has_meaningful_value(value) and contains_unknown(value)
    return False


def has_psi_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if psi_declines_without_facts(raw):
        return False
    if any(has_explicit_psi_evidence_gap(key, raw.get(key)) for key in PSI_SOURCE_KEY_FACTS):
        return True
    return any(has_meaningful_psi_signal(key, raw.get(key)) for key in PSI_SIGNAL_FIELDS)


def psi_declines_without_facts(raw: Dict[str, Any]) -> bool:
    if not psi_declines_workflow(raw.get("contract_evidence")):
        return False
    return not any(
        has_meaningful_psi_signal(key, value) or has_explicit_psi_evidence_gap(key, value)
        for key, value in raw.items()
        if key != "contract_evidence"
        and not psi_field_absence_value(key, value)
    )


def psi_values_with_declines(values: Dict[str, Any], declines: Dict[str, Any]) -> Dict[str, Any]:
    if not declines or not psi_has_facts(values):
        return values
    merged = dict(values)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        if not has_meaningful_psi_signal(key, merged.get(key)):
            merged[key] = value
    merged[PSI_DECLINE_SIGNAL_KEY] = signals
    return merged


def psi_decline_values(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key in PSI_SOURCE_KEY_FACTS and psi_source_declines_workflow(key, value)
    }


def psi_has_facts(record: Dict[str, Any]) -> bool:
    return any(
        has_meaningful_psi_signal(key, value) or has_explicit_psi_evidence_gap(key, value)
        for key, value in record.items()
        if key != PSI_DECLINE_SIGNAL_KEY
        and not psi_source_declines_workflow(key, value)
        and not psi_field_absence_value(key, value)
    )


def has_meaningful_psi_signal(key: str, value: Any) -> bool:
    if key in PSI_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in PSI_SIGNAL_FIELDS and (psi_source_declines_workflow(key, value) or psi_field_absence_value(key, value)):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def psi_evidence_gaps(raw: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    if psi_decline_contradiction(raw):
        evidence.append("no-PSI answer with PSI facts")
    if is_missing(raw.get("income")) or psi_amount_needs_evidence(raw.get("income")):
        evidence.append("numeric income evidence")
    if psi_contract_evidence_missing(raw.get("contract_evidence")):
        evidence.append("contract or invoice evidence")
    missing_tests = [
        label
        for key, label in (
            ("results_test", "results test"),
            ("eighty_percent_test", "80% client concentration test"),
            ("unrelated_clients_test", "unrelated clients test"),
            ("employment_test", "employment test"),
            ("business_premises_test", "business premises test"),
            ("psb_determination", "PSB determination"),
        )
        if psi_test_needs_evidence(raw.get(key))
    ]
    if missing_tests:
        evidence.append(", ".join(missing_tests))
    for key, label in (
        ("income_type", "income type"),
        ("attribution_entity", "attribution evidence"),
        ("deductions", "deduction evidence"),
        ("business_structure", "business structure evidence"),
    ):
        if is_missing(raw.get(key)) or contains_unknown(raw.get(key)):
            evidence.append(label)
    return evidence


def psi_tab_text(evidence: List[str]) -> str:
    if evidence:
        return f"PSI needs {', '.join(evidence)} before accountant review."
    return "PSI tests, attribution, deductions, and structure require accountant review before entry."


def psi_decline_contradiction(raw: Dict[str, Any]) -> bool:
    return bool(raw.get(PSI_DECLINE_SIGNAL_KEY))


def psi_decline_signal_text(raw: Dict[str, Any]) -> str:
    signals = raw.get(PSI_DECLINE_SIGNAL_KEY)
    if not isinstance(signals, list):
        return ""
    return ", ".join(display_value(signal) for signal in signals if display_value(signal))


def psi_contract_evidence_missing(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if is_missing(value) or contains_unknown(value):
        return True
    if psi_declines_workflow(value):
        return True
    lowered = text(value).strip().lower()
    if psi_document_context(lowered) and lowered.startswith(("no ", "without ", "missing ")):
        return True
    return lowered in {"no", "n", "false", "none", "not held", "not available"} or any(
        phrase in lowered
        for phrase in (
            "no contract",
            "no contracts",
            "no invoice",
            "no invoices",
            "contract not held",
            "contract not available",
            "contract not provided",
            "invoice not held",
            "invoice not available",
            "invoice not provided",
            "do not have",
            "don't have",
            "dont have",
        )
    )


def psi_declines_workflow(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if psi_document_context(lowered):
        return False
    if lowered in PSI_DECLINE_PHRASES:
        return True
    return any(
        phrase in lowered
        for phrase in (
            "do not have personal services income",
            "do not have any personal services income",
            "don't have personal services income",
            "don't have any personal services income",
            "dont have personal services income",
            "dont have any personal services income",
            "do not have psi",
            "don't have psi",
            "dont have psi",
            "no psi income",
            "no personal services income this year",
        )
    )


def psi_source_declines_workflow(key: str, value: Any) -> bool:
    if psi_field_absence_value(key, value):
        return False
    return psi_declines_workflow(value)


def psi_field_absence_value(key: str, value: Any) -> bool:
    if not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if lowered in {"no psi", "no personal services income"}:
        return False
    return lowered in GENERIC_FIELD_ABSENCE_PHRASES


def psi_document_context(lowered: str) -> bool:
    return "contract" in lowered or "invoice" in lowered


def psi_test_needs_evidence(value: Any) -> bool:
    return is_missing(value) or boolean_answer_needs_evidence(value)


def psi_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    if psi_declines_workflow(value):
        return False
    return contains_unknown(value) or psi_amount_malformed(value)


def psi_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return False


def psi_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def psi_bool_text(value: Any) -> str:
    return display_value(value) if not is_missing(value) and not psi_field_absence_value("", value) else "unknown"


def psi_display_text(raw: Dict[str, Any], key: str) -> str:
    if psi_field_absence_value(key, raw.get(key)):
        return "unknown"
    return display_value(raw.get(key)) or "unknown"


def cgt_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("cgt")
    fields: Dict[str, Any] = {}
    field_conflicts: List[str] = []
    item_conflicts: List[str] = []
    for flat_key, nested_key in CGT_FLAT_FIELD_KEYS.items():
        value = answers.get(flat_key)
        existing = fields.get(nested_key)
        if cgt_values_conflict(nested_key, existing, value):
            field_conflicts.append(f"{nested_key} {display_value(existing)} vs {display_value(value)}")
        elif nested_key not in fields or cgt_flat_alias_should_replace(nested_key, existing, value):
            fields[nested_key] = value
    if not isinstance(raw, dict) and has_meaningful_value(raw):
        fields["summary"] = raw
    flat_items = cgt_item_values(answers.get("cgt_items"))
    raw_context = isinstance(raw, dict) and any(cgt_answer_context_value(key, value) for key, value in raw.items())
    flat_values = cgt_answer_values(fields, existing_context=bool(flat_items) or raw_context)
    if flat_items:
        review_conflicts = cgt_itemized_review_field_conflicts(flat_values, flat_items)
        if review_conflicts:
            flat_values.setdefault(CGT_CONFLICT_SIGNAL_KEY, []).extend(review_conflicts)
        flat_values["items"] = cgt_items_with_inherited_review_flags(flat_items, flat_values)
    if field_conflicts:
        flat_values.setdefault(CGT_CONFLICT_SIGNAL_KEY, []).extend(field_conflicts)
    flat_declines = cgt_decline_values(fields)
    if not isinstance(raw, dict):
        return cgt_values_with_declines(flat_values, flat_declines)
    if not has_meaningful_value(raw):
        return cgt_values_with_declines(flat_values, flat_declines)
    raw_declines = cgt_decline_values(raw)
    merged = dict(flat_values)
    conflicts = list(flat_values.get(CGT_CONFLICT_SIGNAL_KEY, []))
    existing_flat_context = cgt_has_facts(flat_values)
    raw_item_values = cgt_merge_item_values(raw.get("items"), raw.get("cgt_items"))
    if cgt_items_conflict(raw.get("items"), raw.get("cgt_items")):
        item_conflicts.append("items")
    if flat_items and raw_item_values and cgt_items_conflict(flat_items, raw_item_values):
        item_conflicts.append("items")
    if raw_item_values:
        merged["items"] = cgt_merge_item_values(merged.get("items"), raw_item_values)
    for key, value in cgt_answer_values(raw, existing_context=existing_flat_context).items():
        if key == "items":
            continue
        if key == CGT_CONFLICT_SIGNAL_KEY:
            conflicts.extend(value if isinstance(value, list) else [value])
            continue
        existing = merged.get(key)
        if cgt_values_conflict(key, existing, value):
            conflicts.append(f"{key} {display_value(existing)} vs {display_value(value)}")
            continue
        merged[key] = cgt_merge_value(key, existing, value)
    if conflicts:
        merged[CGT_CONFLICT_SIGNAL_KEY] = conflicts
    if item_conflicts:
        merged["_item_conflicts"] = sorted(set(item_conflicts))
    if cgt_item_values(merged.get("items")):
        items = cgt_item_values(merged.get("items"))
        review_conflicts = cgt_itemized_review_field_conflicts(merged, items)
        if review_conflicts:
            merged.setdefault(CGT_CONFLICT_SIGNAL_KEY, []).extend(review_conflicts)
        merged["items"] = cgt_items_with_inherited_review_flags(items, merged)
    return cgt_values_with_declines(merged, {**flat_declines, **raw_declines})


def cgt_flat_alias_should_replace(key: str, existing: Any, value: Any) -> bool:
    if is_missing(existing):
        return True
    if has_meaningful_cgt_signal(key, existing):
        return False
    if key in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(existing):
        return False
    return has_meaningful_cgt_signal(key, value) or has_explicit_cgt_evidence_gap(key, value)


def cgt_answer_values(record: Dict[str, Any], existing_context: bool = False) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    has_context = existing_context or any(cgt_answer_context_value(key, value) for key, value in record.items())
    for key, value in record.items():
        if key in CGT_ITEM_ALIASES:
            items = cgt_item_values(value)
            if items:
                values["items"] = items
            continue
        canonical_key = cgt_canonical_field_key(key)
        if canonical_key == "no_cgt" and cgt_summary_has_event_fact(value):
            existing = values.get("summary")
            if cgt_values_conflict("summary", existing, value):
                values.setdefault(CGT_CONFLICT_SIGNAL_KEY, []).append(
                    f"summary {display_value(existing)} vs {display_value(value)}"
                )
            else:
                values["summary"] = cgt_merge_value("summary", existing, value)
            continue
        evidence_gap = has_explicit_cgt_evidence_gap(canonical_key, value)
        signal = has_meaningful_cgt_signal(canonical_key, value)
        if (
            (signal and (has_context or not cgt_fact_requires_context(canonical_key)))
            or (evidence_gap and (has_context or not cgt_evidence_gap_requires_context(canonical_key)))
            or cgt_preserved_false_review_flag(canonical_key, value, has_context)
        ):
            existing = values.get(canonical_key)
            if cgt_values_conflict(canonical_key, existing, value):
                values.setdefault(CGT_CONFLICT_SIGNAL_KEY, []).append(
                    f"{canonical_key} {display_value(existing)} vs {display_value(value)}"
                )
                continue
            values[canonical_key] = cgt_merge_value(canonical_key, values.get(canonical_key), value)
    return values


def cgt_item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        return []
    items: List[Dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item = normalize_cgt_item(raw_item)
        if cgt_item_has_facts(item):
            items.append(dict(item))
    return items


def cgt_items_with_inherited_review_flags(items: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
    inherited = {
        key: context.get(key)
        for key in CGT_BOOLEAN_REVIEW_FIELDS
        if cgt_inherited_review_flag(context.get(key))
    }
    inherited.update(
        {
            key: context.get(key)
            for key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS
            if has_meaningful_cgt_signal(key, context.get(key)) or has_explicit_cgt_evidence_gap(key, context.get(key))
        }
    )
    inherited.update(
        {
            key: context.get(key)
            for key in CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS
            if has_meaningful_cgt_signal(key, context.get(key)) or has_explicit_cgt_evidence_gap(key, context.get(key))
        }
    )
    if not inherited:
        return items
    merged_items = []
    for item in items:
        merged_item = dict(item)
        for key, value in inherited.items():
            if is_missing(merged_item.get(key)):
                merged_item[key] = value
        merged_items.append(merged_item)
    return merged_items


def cgt_itemized_review_field_conflicts(context: Dict[str, Any], items: List[Dict[str, Any]]) -> List[str]:
    conflicts: List[str] = []
    for index, item in enumerate(items, start=1):
        for key in CGT_MAIN_RESIDENCE_REVIEW_FIELDS + CGT_SMALL_BUSINESS_CONCESSION_FIELDS:
            top_value = context.get(key)
            item_value = item.get(key)
            if cgt_values_conflict(key, top_value, item_value):
                conflicts.append(f"item {index} {key} {display_value(top_value)} vs {display_value(item_value)}")
    return conflicts


def cgt_inherited_review_flag(value: Any) -> bool:
    return cgt_boolean_false(value) or cgt_review_flag_has_signal(value) or cgt_boolean_needs_evidence(value)


def cgt_merge_item_values(left: Any, right: Any) -> List[Dict[str, Any]]:
    left_items = cgt_item_values(left)
    right_items = cgt_item_values(right)
    if not left_items:
        return right_items
    if not right_items:
        return left_items
    merged_items: List[Dict[str, Any]] = []
    for index in range(max(len(left_items), len(right_items))):
        if index >= len(left_items):
            merged_items.append(right_items[index])
            continue
        if index >= len(right_items):
            merged_items.append(left_items[index])
            continue
        left_item = left_items[index]
        right_item = right_items[index]
        if cgt_item_values_conflict(left_item, right_item):
            merged_items.append(left_item)
            merged_items.append(right_item)
        else:
            merged_items.append(cgt_merge_item_value(left_item, right_item))
    return merged_items


def cgt_merge_item_value(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged_item = dict(left)
    for key, value in right.items():
        if key in (CGT_DECLINE_SIGNAL_KEY, CGT_CONFLICT_SIGNAL_KEY, "_alias_conflicts", "_alias_conflict_details"):
            merged_values = list(merged_item.get(key) or [])
            new_values = value if isinstance(value, list) else [value]
            merged_item[key] = sorted({str(item) for item in [*merged_values, *new_values] if has_meaningful_value(item)})
            continue
        canonical = cgt_canonical_field_key(key)
        if cgt_values_conflict(canonical, merged_item.get(key), value):
            continue
        merged_item[key] = cgt_merge_value(canonical, merged_item.get(key), value)
    return merged_item


def normalize_cgt_item(raw: Dict[str, Any]) -> Dict[str, Any]:
    item: Dict[str, Any] = {}
    conflicts: List[str] = []
    conflict_details: List[str] = []
    for canonical, aliases in CGT_ITEM_FIELD_ALIASES.items():
        values = cgt_item_alias_values(raw, aliases, canonical)
        if not values:
            continue
        chosen = first_cgt_item_alias_value(values, canonical)
        if cgt_item_alias_values_conflict(canonical, [value for _, value in values]):
            conflicts.append(canonical)
            conflict_details.append(cgt_item_alias_conflict_detail(canonical, values))
        item[canonical] = chosen
    for key, value in raw.items():
        canonical = cgt_canonical_field_key(key)
        if canonical in item or canonical in CGT_ITEM_ALIASES:
            continue
        if has_meaningful_cgt_signal(canonical, value) or (
            has_explicit_cgt_evidence_gap(canonical, value)
            and not cgt_evidence_gap_requires_context(canonical)
        ):
            item[canonical] = value
    declines = cgt_decline_values(raw)
    if declines:
        item = cgt_values_with_declines(item, declines)
    if conflicts:
        item["_alias_conflicts"] = sorted(set(conflicts))
    if isinstance(raw.get("_alias_conflict_details"), list):
        conflict_details.extend(raw.get("_alias_conflict_details") or [])
    if conflict_details:
        item["_alias_conflict_details"] = sorted({detail for detail in conflict_details if has_meaningful_value(detail)})
    return item


def cgt_item_alias_conflict_detail(canonical: str, values: List[tuple[str, Any]]) -> str:
    parts: List[str] = []
    for alias, value in values:
        text = display_value(value)
        if not is_missing(value) and text:
            parts.append(f"{alias} {text}")
    if not parts:
        return canonical
    return f"{canonical}: {' vs '.join(parts)}"


def cgt_item_alias_values(raw: Dict[str, Any], aliases: tuple[str, ...], canonical: str) -> List[tuple[str, Any]]:
    return [
        (alias, raw.get(alias))
        for alias in aliases
        if cgt_item_alias_value_usable(raw, alias, canonical)
    ]


def cgt_item_alias_value_usable(raw: Dict[str, Any], alias: str, canonical: str) -> bool:
    if alias not in raw or is_missing(raw.get(alias)):
        return False
    value = raw.get(alias)
    if canonical in CGT_AMOUNT_FIELDS and isinstance(value, (dict, list, bool)):
        return False
    return not cgt_field_absence_value(canonical, value)


def first_cgt_item_alias_value(values: List[tuple[str, Any]], canonical: str) -> Any:
    for _, value in values:
        if cgt_concrete_alias_value(value, canonical):
            return value
    for _, value in values:
        if contains_unknown(value):
            return value
    for _, value in values:
        if has_meaningful_value(value) or value is False:
            return value
    return values[0][1] if values else None


def cgt_concrete_alias_value(value: Any, canonical: str) -> bool:
    if is_missing(value) or contains_unknown(value):
        return False
    if canonical in CGT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if canonical in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(value):
        return True
    return has_meaningful_value(value)


def cgt_item_alias_values_conflict(canonical: str, values: List[Any]) -> bool:
    concrete = [value for value in values if not is_missing(value)]
    if len(concrete) < 2:
        return False
    first = concrete[0]
    return any(cgt_values_conflict(canonical, first, value) for value in concrete[1:])


def cgt_items_conflict(left: Any, right: Any) -> bool:
    left_items = cgt_item_values(left)
    right_items = cgt_item_values(right)
    if not left_items or not right_items:
        return False
    if len(left_items) != len(right_items):
        return True
    return any(cgt_item_values_conflict(left_item, right_item) for left_item, right_item in zip(left_items, right_items))


def cgt_item_values_conflict(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    for key in sorted(set(left) | set(right)):
        if key in (CGT_DECLINE_SIGNAL_KEY, CGT_CONFLICT_SIGNAL_KEY, "_alias_conflicts", "_alias_conflict_details"):
            continue
        canonical = cgt_canonical_field_key(key)
        if cgt_values_conflict(canonical, left.get(key), right.get(key)):
            return True
    return False


def cgt_item_has_facts(item: Dict[str, Any]) -> bool:
    if item.get("_alias_conflicts"):
        return True
    has_context = any(cgt_answer_context_value(key, value) for key, value in item.items())
    return any(
        (has_meaningful_cgt_signal(key, value) and (has_context or not cgt_fact_requires_context(key)))
        or (
            has_explicit_cgt_evidence_gap(key, value)
            and not cgt_evidence_gap_requires_context(key)
        )
        for key, value in item.items()
        if key not in (CGT_DECLINE_SIGNAL_KEY, CGT_CONFLICT_SIGNAL_KEY, "_alias_conflict_details")
    )


def cgt_merge_value(key: str, existing: Any, value: Any) -> Any:
    if has_explicit_cgt_evidence_gap(key, value) and not has_meaningful_cgt_signal(key, value):
        if has_meaningful_cgt_signal(key, existing):
            return existing
        if key in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(existing):
            return existing
    return value


def cgt_values_conflict(key: str, existing: Any, value: Any) -> bool:
    if not cgt_conflict_value(key, existing) or not cgt_conflict_value(key, value):
        return False
    if key in CGT_AMOUNT_FIELDS:
        existing_money = cgt_money_value(existing)
        value_money = cgt_money_value(value)
        if existing_money is not None and value_money is not None:
            return existing_money != value_money
    if key in CGT_BOOLEAN_REVIEW_FIELDS:
        if (cgt_boolean_true(existing) or cgt_boolean_false(existing)) and (
            cgt_boolean_true(value) or cgt_boolean_false(value)
        ):
            return cgt_boolean_true(existing) != cgt_boolean_true(value)
    return display_value(existing).strip().lower() != display_value(value).strip().lower()


def cgt_conflict_value(key: str, value: Any) -> bool:
    if cgt_evidence_gap_requires_context(key) and has_explicit_cgt_evidence_gap(key, value):
        return True
    return (
        has_meaningful_cgt_signal(key, value)
        or (key in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(value))
    )


def cgt_answer_context_value(key: str, value: Any) -> bool:
    if key in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(value):
        return False
    if cgt_fact_requires_context(key) and (
        has_meaningful_cgt_signal(key, value) or has_explicit_cgt_evidence_gap(key, value)
    ):
        return False
    return has_meaningful_cgt_signal(key, value) or has_explicit_cgt_evidence_gap(key, value)


def cgt_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_cgt_inputs(raw):
        return []
    if not isinstance(raw, dict):
        return []
    items = cgt_item_values(raw.get("items"))
    if items:
        rows = [
            cgt_item_row(
                idx,
                item,
                cgt_item_evidence_gaps(raw, item),
                cgt_review_terms(item),
            )
            for idx, item in enumerate(items, start=1)
        ]
        if cgt_has_top_level_details(raw):
            rows.append(
                cgt_schedule_row(raw, cgt_itemized_top_level_evidence(raw), cgt_review_terms(raw), itemized=True)
            )
        if cgt_has_reconciliation_target(raw):
            rows.append(cgt_reconciliation_row(raw, items))
        return rows
    return [cgt_schedule_row(raw, cgt_evidence_gaps(raw), cgt_review_terms(raw), itemized=False)]


def cgt_small_business_concession_answer_text(raw: Dict[str, Any]) -> str:
    return (
        f"concession flag {cgt_boolean_flag_text(raw.get('concession_flag'))}; "
        f"concession type {cgt_field_text(raw, 'concession_type')}; "
        f"business asset {cgt_boolean_flag_text(raw.get('business_asset'))}; "
        f"active asset {cgt_boolean_flag_text(raw.get('active_asset'))}; "
        f"entity/affiliate/connected entity {cgt_boolean_flag_text(raw.get('entity_affiliate_connected_entity'))}; "
        f"retirement exemption {cgt_boolean_flag_text(raw.get('retirement_exemption'))}; "
        f"rollover {cgt_boolean_flag_text(raw.get('rollover'))}; "
        f"15-year exemption {cgt_boolean_flag_text(raw.get('fifteen_year_exemption'))}; "
        f"50% active asset reduction {cgt_boolean_flag_text(raw.get('active_asset_reduction_50'))}; "
        f"concession evidence {cgt_field_text(raw, 'concession_evidence')}"
    )


def cgt_handoff_facts(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return atomic CGT facts without working out a gain, loss, or concession."""
    return handoff_facts(
        ("event-type", "Event type", raw.get("event_type")),
        ("asset", "Asset", raw.get("asset")),
        ("owner", "Owner", raw.get("owner")),
        ("acquisition-date", "Acquisition date", raw.get("acquisition_date")),
        ("disposal-date", "Disposal date", raw.get("disposal_date")),
        ("proceeds", "Capital proceeds supplied", raw.get("proceeds")),
        ("cost-base", "Cost base supplied", raw.get("cost_base")),
        ("incidental-costs", "Incidental costs supplied", raw.get("incidental_costs")),
        ("losses", "Losses supplied", raw.get("losses")),
        ("current-year-losses", "Current-year losses supplied", raw.get("current_year_losses")),
        ("carried-forward-losses", "Carried-forward losses supplied", raw.get("carried_forward_losses")),
        ("records", "CGT records", raw.get("records")),
        ("exemption-flag", "Exemption flag", raw.get("exemption_flag")),
        ("discount-flag", "Discount flag", raw.get("discount_flag")),
        ("discount-claim", "Discount claim", raw.get("discount_claim")),
        ("discount-timing", "Discount timing", raw.get("discount_timing")),
        ("discount-eligibility", "Discount eligibility", raw.get("discount_eligibility")),
        ("concession-flag", "Small business concession flag", raw.get("concession_flag")),
        ("concession-type", "Small business concession type", raw.get("concession_type")),
        ("business-asset", "Business asset", raw.get("business_asset")),
        ("active-asset", "Active asset", raw.get("active_asset")),
        ("entity-context", "Entity, affiliate, or connected-entity context", raw.get("entity_affiliate_connected_entity")),
        ("retirement-exemption", "Retirement exemption", raw.get("retirement_exemption")),
        ("rollover", "Rollover", raw.get("rollover")),
        ("fifteen-year-exemption", "15-year exemption", raw.get("fifteen_year_exemption")),
        ("active-asset-reduction", "50% active asset reduction", raw.get("active_asset_reduction_50")),
        ("concession-evidence", "Concession evidence", raw.get("concession_evidence")),
        ("mixed-use", "Mixed use", raw.get("mixed_use")),
        ("business-use", "Business use", raw.get("business_use")),
        ("private-use", "Private use", raw.get("private_use")),
        ("main-residence-claim", "Main residence claim", raw.get("main_residence_claim")),
        ("ownership-period", "Main residence ownership period", raw.get("main_residence_ownership_period")),
        ("occupancy-period", "Main residence occupancy period", raw.get("main_residence_occupancy_period")),
        ("rental-business-use", "Main residence rental or business use", raw.get("main_residence_rental_business_use")),
        ("absence-periods", "Main residence absence periods", raw.get("main_residence_absence_periods")),
        ("spouse-conflict", "Spouse or partner main-residence conflict", raw.get("main_residence_spouse_conflict")),
        ("property-records", "Main residence property records", raw.get("main_residence_property_records")),
        ("foreign-resident-discount", "Foreign resident discount", raw.get("foreign_resident_discount")),
        ("summary", "Supplied summary", raw.get("summary")),
        ("decline-signals", "Decline signals", cgt_decline_signal_text(raw) or "none"),
        ("conflict-signals", "Conflict signals", cgt_conflict_signal_text(raw) or "none"),
        ("alias-conflicts", "Alias conflicts", cgt_alias_conflict_text(raw) or "none"),
        ("calculation-boundary", "Calculation boundary", "No capital gain or loss amount is worked out"),
    )


def cgt_schedule_row(
    raw: Dict[str, Any],
    evidence: List[str],
    review: List[str],
    itemized: bool,
) -> Dict[str, Any]:
    status = "Evidence" if evidence else "Accountant review"
    answer = (
        f"Event {cgt_field_text(raw, 'event_type')}; "
        f"asset {cgt_field_text(raw, 'asset')}; "
        f"owner {cgt_field_text(raw, 'owner')}; "
        f"acquired {cgt_field_text(raw, 'acquisition_date')}; "
        f"disposed {cgt_field_text(raw, 'disposal_date')}; "
        f"proceeds {cgt_amount_text(raw.get('proceeds'))}; "
        f"cost base {cgt_amount_text(raw.get('cost_base'))}; "
        f"incidental costs {cgt_amount_text(raw.get('incidental_costs'))}; "
        f"losses {cgt_amount_text(raw.get('losses'))}; "
        f"current-year losses {cgt_amount_text(raw.get('current_year_losses'))}; "
        f"carried-forward losses {cgt_amount_text(raw.get('carried_forward_losses'))}; "
        f"records {cgt_field_text(raw, 'records')}; "
        f"exemption flag {cgt_boolean_flag_text(raw.get('exemption_flag'))}; "
        f"discount flag {cgt_boolean_flag_text(raw.get('discount_flag'))}; "
        f"discount claim {cgt_boolean_flag_text(raw.get('discount_claim'))}; "
        f"discount timing {cgt_field_text(raw, 'discount_timing')}; "
        f"discount eligibility {cgt_field_text(raw, 'discount_eligibility')}; "
        f"{cgt_small_business_concession_answer_text(raw)}; "
        f"mixed use {cgt_boolean_flag_text(raw.get('mixed_use'))}; "
        f"business use {cgt_boolean_flag_text(raw.get('business_use'))}; "
        f"private use {cgt_boolean_flag_text(raw.get('private_use'))}; "
        f"main residence claim {cgt_boolean_flag_text(raw.get('main_residence_claim'))}; "
        f"main residence ownership period {cgt_field_text(raw, 'main_residence_ownership_period')}; "
        f"main residence occupancy period {cgt_field_text(raw, 'main_residence_occupancy_period')}; "
        f"main residence rental/business use {cgt_boolean_flag_text(raw.get('main_residence_rental_business_use'))}; "
        f"main residence absence periods {cgt_field_text(raw, 'main_residence_absence_periods')}; "
        f"spouse/partner main residence conflict {cgt_boolean_flag_text(raw.get('main_residence_spouse_conflict'))}; "
        f"main residence property records {cgt_field_text(raw, 'main_residence_property_records')}; "
        f"foreign resident discount {cgt_boolean_flag_text(raw.get('foreign_resident_discount'))}"
    )
    summary = cgt_field_text(raw, "summary")
    if summary != "unknown":
        answer = f"{answer}; summary {summary}"
    decline_text = cgt_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    conflict_text = cgt_conflict_signal_text(raw)
    if conflict_text:
        answer = f"{answer}; conflict signals {conflict_text}"
    answer = f"{answer}; No capital gain or loss amount is worked out."
    row = guide_row(
        "CGT-SCHEDULE",
        "CGT schedule",
        "General CGT event intake and accountant-review schedule" if not itemized else "CGT top-level supplied facts",
        answer,
        "General CGT event facts are collected for review only. No capital gain or loss amount is worked out.",
        status,
        cgt_row_sources(raw),
        tab_text=cgt_tab_text(evidence, review),
        row_kind="capital-gains",
        facts=cgt_handoff_facts(raw),
    )
    if review:
        row["tab_kind"] = "review"
    return row


def cgt_item_row(
    index: int,
    item: Dict[str, Any],
    evidence: List[str],
    review: List[str],
) -> Dict[str, Any]:
    status = "Evidence" if evidence else "Accountant review"
    answer = (
        f"Asset {cgt_field_text(item, 'asset')}; "
        f"event {cgt_field_text(item, 'event_type')}; "
        f"owner {cgt_field_text(item, 'owner')}; "
        f"acquired {cgt_field_text(item, 'acquisition_date')}; "
        f"disposed {cgt_field_text(item, 'disposal_date')}; "
        f"proceeds {cgt_amount_text(item.get('proceeds'))}; "
        f"cost base {cgt_amount_text(item.get('cost_base'))}; "
        f"incidental costs {cgt_amount_text(item.get('incidental_costs'))}; "
        f"losses {cgt_amount_text(item.get('losses'))}; "
        f"current-year losses {cgt_amount_text(item.get('current_year_losses'))}; "
        f"carried-forward losses {cgt_amount_text(item.get('carried_forward_losses'))}; "
        f"records {cgt_field_text(item, 'records')}; "
        f"exemption flag {cgt_boolean_flag_text(item.get('exemption_flag'))}; "
        f"discount flag {cgt_boolean_flag_text(item.get('discount_flag'))}; "
        f"discount claim {cgt_boolean_flag_text(item.get('discount_claim'))}; "
        f"discount timing {cgt_field_text(item, 'discount_timing')}; "
        f"discount eligibility {cgt_field_text(item, 'discount_eligibility')}; "
        f"{cgt_small_business_concession_answer_text(item)}; "
        f"mixed use {cgt_boolean_flag_text(item.get('mixed_use'))}; "
        f"business use {cgt_boolean_flag_text(item.get('business_use'))}; "
        f"private use {cgt_boolean_flag_text(item.get('private_use'))}; "
        f"main residence claim {cgt_boolean_flag_text(item.get('main_residence_claim'))}; "
        f"main residence ownership period {cgt_field_text(item, 'main_residence_ownership_period')}; "
        f"main residence occupancy period {cgt_field_text(item, 'main_residence_occupancy_period')}; "
        f"main residence rental/business use {cgt_boolean_flag_text(item.get('main_residence_rental_business_use'))}; "
        f"main residence absence periods {cgt_field_text(item, 'main_residence_absence_periods')}; "
        f"spouse/partner main residence conflict {cgt_boolean_flag_text(item.get('main_residence_spouse_conflict'))}; "
        f"main residence property records {cgt_field_text(item, 'main_residence_property_records')}; "
        f"foreign resident discount {cgt_boolean_flag_text(item.get('foreign_resident_discount'))}"
    )
    decline_text = cgt_decline_signal_text(item)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    conflict_text = cgt_conflict_signal_text(item)
    if conflict_text:
        answer = f"{answer}; conflict signals {conflict_text}"
    alias_text = cgt_alias_conflict_text(item)
    if alias_text:
        answer = f"{answer}; alias conflicts {alias_text}"
    answer = f"{answer}; No capital gain or loss amount is worked out."
    row = guide_row(
        f"CGT-EVENT-{index}",
        "CGT schedule",
        "Itemized CGT event prep row",
        answer,
        "Itemized CGT event facts are collected for review only. No capital gain or loss amount is worked out.",
        status,
        cgt_row_sources(item),
        tab_text=cgt_tab_text(evidence, review),
        row_kind="capital-gains",
        facts=cgt_handoff_facts(item),
    )
    if review:
        row["tab_kind"] = "review"
    return row


def cgt_reconciliation_row(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> Dict[str, Any]:
    conflicts = cgt_reconciliation_conflicts(raw, items)
    parts = []
    for key, label in (
        ("proceeds", "proceeds"),
        ("cost_base", "cost base"),
        ("incidental_costs", "incidental costs"),
        ("losses", "losses"),
    ):
        if is_missing(raw.get(key)):
            continue
        parts.append(
            f"{label} items {cgt_amount_text(cgt_item_amount_total(items, key))} vs aggregate {cgt_amount_text(raw.get(key))}"
        )
    if raw.get("_item_conflicts"):
        parts.append(f"CGT item alias conflicts {cgt_alias_conflict_text(raw)}")
    return guide_row(
        "CGT-RECON",
        "CGT schedule",
        "CGT item total reconciliation",
        "; ".join(parts) + "; No capital gain or loss amount is worked out.",
        "Itemized CGT totals are reconciled to supplied aggregate totals before accountant review.",
        "Evidence" if conflicts else "Accountant review",
        ATO_CGT_SOURCES,
        tab_text=cgt_reconciliation_tab_text(conflicts),
        row_kind="capital-gains",
        facts=handoff_facts(
            ("proceeds-item-total", "Proceeds item total", cgt_item_amount_total(items, "proceeds")),
            ("proceeds-aggregate", "Proceeds aggregate supplied", raw.get("proceeds")),
            ("cost-base-item-total", "Cost base item total", cgt_item_amount_total(items, "cost_base")),
            ("cost-base-aggregate", "Cost base aggregate supplied", raw.get("cost_base")),
            ("incidental-costs-item-total", "Incidental costs item total", cgt_item_amount_total(items, "incidental_costs")),
            ("incidental-costs-aggregate", "Incidental costs aggregate supplied", raw.get("incidental_costs")),
            ("losses-item-total", "Losses item total", cgt_item_amount_total(items, "losses")),
            ("losses-aggregate", "Losses aggregate supplied", raw.get("losses")),
            ("conflicts", "Reconciliation conflicts", ", ".join(conflicts) or "none"),
            ("calculation-boundary", "Calculation boundary", "No capital gain or loss amount is worked out"),
        ),
    )


def cgt_evidence_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_cgt_inputs(raw) or not isinstance(raw, dict):
        return []
    rows: List[Dict[str, Any]] = []
    items = cgt_item_values(raw.get("items"))
    if items:
        for idx, item in enumerate(items, start=1):
            evidence = cgt_item_evidence_gaps(raw, item)
            if evidence:
                rows.append(
                    guide_row(
                        f"CGT-EVID-{len(rows) + 1}",
                        "CGT schedule",
                        "CGT evidence required",
                        f"CGT item {idx} needs {', '.join(evidence)}; no capital gain or loss amount worked out.",
                        "CGT item row is not ready for entry until evidence gaps are resolved.",
                        "Evidence",
                        cgt_row_sources(item),
                        row_kind="evidence-queue",
                        facts=handoff_facts(
                            ("cgt-item", "CGT item", idx),
                            ("evidence-needed", "Evidence needed", ", ".join(evidence)),
                            ("calculation-boundary", "Calculation boundary", "No capital gain or loss amount is worked out"),
                        ),
                    )
                )
        top_level_evidence = cgt_itemized_top_level_evidence(raw)
        if top_level_evidence:
            subject = "CGT top-level facts" if cgt_has_top_level_details(raw) else "CGT itemized facts"
            evidence_prefix = (
                "CGT top-level facts need" if cgt_has_top_level_details(raw) else "CGT itemized facts need"
            )
            rows.append(
                guide_row(
                    f"CGT-EVID-{len(rows) + 1}",
                    "CGT schedule",
                    "CGT evidence required",
                    f"{evidence_prefix} {', '.join(top_level_evidence)}; no capital gain or loss amount worked out.",
                    f"{subject} are not ready for entry until evidence gaps are resolved.",
                    "Evidence",
                    cgt_row_sources(raw),
                    row_kind="evidence-queue",
                    facts=handoff_facts(
                        ("cgt-scope", "CGT scope", subject),
                        ("evidence-needed", "Evidence needed", ", ".join(top_level_evidence)),
                        ("calculation-boundary", "Calculation boundary", "No capital gain or loss amount is worked out"),
                    ),
                )
            )
        reconciliation = cgt_reconciliation_conflicts(raw, items)
        if reconciliation:
            rows.append(
                guide_row(
                    f"CGT-EVID-{len(rows) + 1}",
                    "CGT schedule",
                    "CGT reconciliation evidence required",
                    cgt_reconciliation_tab_text(reconciliation),
                    "Supplied aggregate CGT totals and itemized CGT event rows conflict or include unresolved item amounts.",
                    "Evidence",
                    ATO_CGT_SOURCES,
                    row_kind="evidence-queue",
                    facts=handoff_facts(
                        ("reconciliation", "CGT reconciliation evidence needed", cgt_reconciliation_tab_text(reconciliation)),
                        ("calculation-boundary", "Calculation boundary", "No capital gain or loss amount is worked out"),
                    ),
                )
            )
        return rows
    evidence = cgt_evidence_gaps(raw)
    if evidence:
        rows.append(
            guide_row(
                "CGT-EVID-1",
                "CGT schedule",
                "CGT evidence required",
                f"CGT event needs {', '.join(evidence)}; no capital gain or loss amount worked out.",
                "CGT schedule row is not ready for entry until evidence gaps are resolved.",
                "Evidence",
                cgt_row_sources(raw),
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("evidence-needed", "CGT evidence needed", ", ".join(evidence)),
                    ("calculation-boundary", "Calculation boundary", "No capital gain or loss amount is worked out"),
                ),
            )
        )
    return rows


def cgt_values_with_declines(values: Dict[str, Any], declines: Dict[str, Any]) -> Dict[str, Any]:
    if not declines or not cgt_has_facts(values):
        return values
    merged = dict(values)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        if not cgt_has_signal(key, merged.get(key)) and key not in merged:
            merged[key] = value
    merged[CGT_DECLINE_SIGNAL_KEY] = signals
    return merged


def cgt_decline_values(record: Dict[str, Any]) -> Dict[str, Any]:
    declines: Dict[str, Any] = {}
    for key, value in record.items():
        canonical_key = cgt_canonical_field_key(key)
        if canonical_key in CGT_SOURCE_KEY_FACTS and cgt_source_declines_workflow(canonical_key, value):
            declines[canonical_key] = value
    return declines


def has_cgt_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if cgt_declines_without_facts(raw):
        return False
    return cgt_has_facts(raw)


def cgt_declines_without_facts(raw: Dict[str, Any]) -> bool:
    if not cgt_decline_values(raw):
        return False
    return not cgt_has_facts(raw)


def cgt_has_facts(record: Dict[str, Any]) -> bool:
    if cgt_item_values(record.get("items")) or cgt_item_values(record.get("cgt_items")):
        return True
    has_context = any(cgt_answer_context_value(key, value) for key, value in record.items())
    return any(
        (cgt_has_signal(key, value) and (has_context or not cgt_fact_requires_context(key)))
        or (
            has_explicit_cgt_evidence_gap(key, value)
            and not cgt_evidence_gap_requires_context(key)
        )
        for key, value in record.items()
        if key != CGT_DECLINE_SIGNAL_KEY
        and key != CGT_CONFLICT_SIGNAL_KEY
        and key != "_item_conflicts"
        and key not in CGT_ITEM_ALIASES
        and not cgt_source_declines_workflow(key, value)
        and not cgt_field_absence_value(key, value)
    )


def cgt_has_signal(key: str, value: Any) -> bool:
    return has_meaningful_cgt_signal(key, value)


def has_meaningful_cgt_signal(key: str, value: Any) -> bool:
    if key == "no_cgt":
        return False
    if key in CGT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in CGT_BOOLEAN_REVIEW_FIELDS:
        return cgt_review_flag_has_signal(value)
    if key in CGT_SOURCE_KEY_FACTS and (
        cgt_source_declines_workflow(key, value) or cgt_field_absence_value(key, value)
    ):
        return False
    if key in ("records", "main_residence_property_records") and cgt_records_missing(value):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def cgt_preserved_false_review_flag(key: str, value: Any, has_context: bool) -> bool:
    return has_context and key in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(value)


def cgt_review_flag_has_signal(value: Any) -> bool:
    if cgt_boolean_true(value):
        return True
    if cgt_boolean_false(value) or cgt_boolean_needs_evidence(value) or cgt_field_absence_value("", value):
        return False
    return has_meaningful_value(value)


def has_explicit_cgt_evidence_gap(key: str, value: Any) -> bool:
    if key in CGT_SOURCE_KEY_FACTS and (
        cgt_source_declines_workflow(key, value) or cgt_field_absence_value(key, value)
    ):
        return False
    if key == "records":
        return not is_missing(value) and cgt_records_missing(value)
    if key in CGT_AMOUNT_FIELDS:
        return cgt_amount_needs_evidence(value)
    if key in CGT_DATE_FIELDS:
        return cgt_date_needs_evidence(value)
    if key in CGT_BOOLEAN_REVIEW_FIELDS:
        return cgt_boolean_needs_evidence(value)
    if key in CGT_DISCOUNT_REVIEW_TEXT_FIELDS:
        return has_meaningful_value(value) and contains_unknown(value)
    if key in CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS:
        if key == "concession_evidence":
            return not is_missing(value) and cgt_records_missing(value)
        return has_meaningful_value(value) and contains_unknown(value)
    if key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS:
        if key == "main_residence_property_records":
            return not is_missing(value) and cgt_records_missing(value)
        return has_meaningful_value(value) and contains_unknown(value)
    if key in ("summary", "event_type", "asset", "owner", "records"):
        return has_meaningful_value(value) and contains_unknown(value)
    return False


def cgt_evidence_gap_requires_context(key: str) -> bool:
    return key == "records" or key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS or key in CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS


def cgt_fact_requires_context(key: str) -> bool:
    return key == "records" or key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS or key in CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS


def cgt_evidence_gaps(raw: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    if cgt_decline_contradiction(raw):
        evidence.append("no-CGT answer with CGT facts")
    if raw.get(CGT_CONFLICT_SIGNAL_KEY):
        evidence.append("CGT field conflicts")
        evidence.extend(cgt_conflict_evidence_labels(raw))
    if raw.get("_item_conflicts"):
        evidence.append("CGT item alias conflicts")
    for key, label in (
        ("event_type", "event type evidence"),
        ("asset", "asset evidence"),
        ("owner", "ownership evidence"),
    ):
        if not cgt_has_signal(key, raw.get(key)) or contains_unknown(raw.get(key)):
            evidence.append(label)
    if cgt_records_missing(raw.get("records")):
        evidence.append("CGT records")
    if any(cgt_date_needs_evidence(raw.get(key)) or is_missing(raw.get(key)) for key in CGT_DATE_FIELDS):
        evidence.append("acquisition or disposal date evidence")
    if any(cgt_amount_needs_evidence(raw.get(key)) or is_missing(raw.get(key)) for key in ("proceeds", "cost_base")):
        evidence.append("numeric proceeds or cost-base evidence")
    if any(
        not is_missing(raw.get(key)) and cgt_amount_needs_evidence(raw.get(key))
        for key in ("incidental_costs", "losses")
    ):
        evidence.append("numeric incidental-cost or loss evidence")
    if cgt_loss_amounts_need_evidence(raw):
        evidence.append("numeric current-year or carried-forward loss evidence")
    if cgt_discount_text_needs_evidence(raw):
        evidence.append("discount timing/eligibility evidence")
    evidence.extend(cgt_small_business_concession_evidence_gaps(raw))
    evidence.extend(cgt_main_residence_evidence_gaps(raw))
    if cgt_boolean_needs_evidence(raw.get("foreign_resident_discount")):
        evidence.append("foreign resident discount review signal evidence")
    if any(cgt_boolean_needs_evidence(raw.get(key)) for key in CGT_BOOLEAN_REVIEW_FIELDS):
        evidence.append("review signal evidence")
    return evidence


def cgt_item_evidence_gaps(raw: Dict[str, Any], item: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    if cgt_decline_contradiction(item):
        evidence.append("no-CGT answer with CGT facts")
    if item.get("_alias_conflicts"):
        evidence.append("CGT item alias conflicts")
    for key, label in (
        ("event_type", "event type evidence"),
        ("asset", "asset evidence"),
        ("owner", "ownership evidence"),
    ):
        if not cgt_has_signal(key, item.get(key)) or contains_unknown(item.get(key)):
            evidence.append(label)
    if cgt_records_missing(item.get("records")):
        evidence.append("CGT records")
    if any(cgt_date_needs_evidence(item.get(key)) or is_missing(item.get(key)) for key in CGT_DATE_FIELDS):
        evidence.append("acquisition or disposal date evidence")
    if any(cgt_amount_needs_evidence(item.get(key)) or is_missing(item.get(key)) for key in ("proceeds", "cost_base")):
        evidence.append("numeric proceeds or cost-base evidence")
    if any(
        not is_missing(item.get(key)) and cgt_amount_needs_evidence(item.get(key))
        for key in ("incidental_costs", "losses")
    ):
        evidence.append("numeric proceeds, cost-base, incidental-cost, or loss evidence")
    if cgt_loss_amounts_need_evidence(item):
        evidence.append("numeric current-year or carried-forward loss evidence")
    if cgt_discount_text_needs_evidence(item):
        evidence.append("discount timing/eligibility evidence")
    evidence.extend(cgt_small_business_concession_evidence_gaps(item))
    evidence.extend(cgt_main_residence_evidence_gaps(item))
    if cgt_boolean_needs_evidence(item.get("foreign_resident_discount")):
        evidence.append("foreign resident discount review signal evidence")
    if any(cgt_boolean_needs_evidence(item.get(key)) for key in CGT_BOOLEAN_REVIEW_FIELDS):
        evidence.append("review signal evidence")
    return evidence


def cgt_itemized_top_level_evidence(raw: Dict[str, Any]) -> List[str]:
    if cgt_decline_contradiction(raw):
        return ["no-CGT answer with CGT facts"]
    if cgt_has_top_level_details(raw):
        return cgt_itemized_top_level_evidence_gaps(raw)
    return []


def cgt_itemized_top_level_evidence_gaps(raw: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    if raw.get(CGT_CONFLICT_SIGNAL_KEY):
        evidence.append("CGT field conflicts")
        evidence.extend(cgt_conflict_evidence_labels(raw))
    for key, label in (
        ("summary", "summary evidence"),
        ("event_type", "event type evidence"),
        ("asset", "asset evidence"),
        ("owner", "ownership evidence"),
    ):
        if key in raw and has_explicit_cgt_evidence_gap(key, raw.get(key)):
            evidence.append(label)
    if "records" in raw and cgt_records_missing(raw.get("records")):
        evidence.append("CGT records")
    if any(key in raw and cgt_date_needs_evidence(raw.get(key)) for key in CGT_DATE_FIELDS):
        evidence.append("acquisition or disposal date evidence")
    evidence.extend(cgt_itemized_summary_evidence(raw))
    if any(key in raw and cgt_boolean_needs_evidence(raw.get(key)) for key in CGT_BOOLEAN_REVIEW_FIELDS):
        evidence.append("review signal evidence")
    return list(dict.fromkeys(evidence))


def cgt_conflict_evidence_labels(raw: Dict[str, Any]) -> List[str]:
    labels: List[str] = []
    signals = [display_value(signal) for signal in raw.get(CGT_CONFLICT_SIGNAL_KEY, [])]
    if any(signal.startswith("records ") for signal in signals):
        labels.append("CGT records")
    if any(signal.startswith("item ") for signal in signals):
        labels.append("CGT item review field conflicts")
    return labels


def cgt_itemized_summary_evidence(raw: Dict[str, Any]) -> List[str]:
    evidence: List[str] = []
    if any(
        not is_missing(raw.get(key)) and cgt_amount_needs_evidence(raw.get(key))
        for key in ("proceeds", "cost_base")
    ):
        evidence.append("numeric proceeds or cost-base evidence")
    if any(
        not is_missing(raw.get(key)) and cgt_amount_needs_evidence(raw.get(key))
        for key in ("incidental_costs", "losses")
    ):
        evidence.append("numeric incidental-cost or loss evidence")
    if cgt_loss_amounts_need_evidence(raw):
        evidence.append("numeric current-year or carried-forward loss evidence")
    if cgt_discount_text_needs_evidence(raw):
        evidence.append("discount timing/eligibility evidence")
    evidence.extend(cgt_small_business_concession_evidence_gaps(raw))
    evidence.extend(cgt_main_residence_evidence_gaps(raw))
    return evidence


def cgt_loss_amounts_need_evidence(raw: Dict[str, Any]) -> bool:
    return any(
        not is_missing(raw.get(key)) and cgt_amount_needs_evidence(raw.get(key))
        for key in CGT_LOSS_REVIEW_AMOUNT_FIELDS
    )


def cgt_discount_text_needs_evidence(raw: Dict[str, Any]) -> bool:
    return any(contains_unknown(raw.get(key)) for key in CGT_DISCOUNT_REVIEW_TEXT_FIELDS)


def cgt_discount_or_residency_has_review_signal(raw: Dict[str, Any]) -> bool:
    return any(
        has_meaningful_cgt_signal(key, raw.get(key))
        for key in CGT_DISCOUNT_REVIEW_TEXT_FIELDS
    ) or cgt_review_flag_has_signal(raw.get("foreign_resident_discount"))


def cgt_small_business_concession_has_review_signal(raw: Dict[str, Any]) -> bool:
    return any(
        cgt_review_flag_has_signal(raw.get(key)) or cgt_boolean_needs_evidence(raw.get(key))
        for key in CGT_SMALL_BUSINESS_CONCESSION_FLAG_FIELDS
    ) or any(
        cgt_small_business_concession_text_has_signal(key, raw.get(key))
        for key in CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS
    )


def cgt_small_business_concession_text_has_signal(key: str, value: Any) -> bool:
    if key == "concession_evidence" and cgt_records_missing(value):
        return not is_missing(value)
    return has_meaningful_cgt_signal(key, value) or (has_meaningful_value(value) and contains_unknown(value))


def cgt_small_business_concession_evidence_gaps(raw: Dict[str, Any]) -> List[str]:
    if not cgt_small_business_concession_has_review_signal(raw):
        return []
    evidence: List[str] = []
    if cgt_boolean_needs_evidence(raw.get("concession_flag")):
        evidence.append("small business CGT concession claim evidence")
    if is_missing(raw.get("concession_type")) or contains_unknown(raw.get("concession_type")):
        evidence.append("small business CGT concession type evidence")
    for key, label in (
        ("business_asset", "business asset evidence"),
        ("active_asset", "active asset evidence"),
        ("entity_affiliate_connected_entity", "entity, affiliate, or connected entity evidence"),
        ("retirement_exemption", "retirement exemption signal evidence"),
        ("rollover", "rollover signal evidence"),
        ("fifteen_year_exemption", "15-year exemption signal evidence"),
        ("active_asset_reduction_50", "50% active asset reduction signal evidence"),
    ):
        if is_missing(raw.get(key)) or cgt_boolean_needs_evidence(raw.get(key)):
            evidence.append(label)
    if cgt_records_missing(raw.get("concession_evidence")):
        evidence.append("small business CGT concession evidence")
    return list(dict.fromkeys(evidence))


def cgt_has_top_level_details(raw: Dict[str, Any]) -> bool:
    has_item_context = bool(cgt_item_values(raw.get("items")) or cgt_item_values(raw.get("cgt_items")))
    has_context = has_item_context or any(
        cgt_answer_context_value(key, value) for key, value in raw.items()
    )
    return any(
        (
            (
                key not in CGT_BOOLEAN_REVIEW_FIELDS
                and has_meaningful_cgt_signal(key, value)
                and (has_context or not cgt_fact_requires_context(key))
            )
            or (
                has_explicit_cgt_evidence_gap(key, value)
                and (has_context or not cgt_evidence_gap_requires_context(key))
            )
        )
        for key, value in raw.items()
        if key not in ("items", "cgt_items", "_item_conflicts", CGT_DECLINE_SIGNAL_KEY, CGT_CONFLICT_SIGNAL_KEY)
        and key not in CGT_RECONCILIATION_FIELDS
        and not (has_item_context and cgt_itemized_inherited_main_residence_key(key))
    ) or bool(raw.get(CGT_CONFLICT_SIGNAL_KEY))


def cgt_itemized_inherited_main_residence_key(key: str) -> bool:
    return key in CGT_MAIN_RESIDENCE_REVIEW_FIELDS or key in CGT_SMALL_BUSINESS_CONCESSION_FIELDS


def cgt_has_reconciliation_target(raw: Dict[str, Any]) -> bool:
    return any(not is_missing(raw.get(key)) for key in CGT_RECONCILIATION_FIELDS) or bool(raw.get("_item_conflicts"))


def cgt_reconciliation_conflicts(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> List[str]:
    conflicts: List[str] = []
    if raw.get("_item_conflicts"):
        conflicts.append("CGT item alias conflicts")
    if not items:
        return conflicts
    for key, label in (
        ("proceeds", "proceeds"),
        ("cost_base", "cost base"),
        ("incidental_costs", "incidental costs"),
        ("losses", "losses"),
    ):
        aggregate_value = raw.get(key)
        if is_missing(aggregate_value):
            continue
        if cgt_amount_needs_evidence(aggregate_value):
            conflicts.append(label)
            continue
        aggregate = cgt_money_value(aggregate_value)
        if aggregate is None:
            continue
        item_total = cgt_item_amount_total(items, key)
        if item_total is None or round(abs(aggregate - item_total), 2) >= 0.01:
            conflicts.append(label)
    return conflicts


def cgt_item_amount_total(items: List[Dict[str, Any]], key: str) -> Optional[float]:
    amounts = [cgt_money_value(item.get(key)) for item in items]
    if not amounts or any(amount is None for amount in amounts):
        return None
    return round(sum(amounts), 2)


def cgt_reconciliation_tab_text(conflicts: List[str]) -> str:
    if conflicts:
        return f"CGT item totals need corrected reconciliation for {', '.join(conflicts)} before accountant review; no capital gain or loss amount worked out."
    return "CGT item totals reconcile to supplied aggregates; still prep-only and review-first; no capital gain or loss amount worked out."


def cgt_alias_conflict_text(raw: Dict[str, Any]) -> str:
    conflicts = raw.get("_alias_conflicts") or raw.get("_item_conflicts")
    details = raw.get("_alias_conflict_details")
    parts: List[str] = []
    if isinstance(conflicts, list):
        parts.extend(display_value(conflict) for conflict in conflicts if display_value(conflict))
    if isinstance(details, list):
        parts.extend(display_value(detail) for detail in details if display_value(detail))
    return ", ".join(dict.fromkeys(parts))


def cgt_review_terms(raw: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    if any(cgt_review_flag_has_signal(raw.get(key)) for key in ("mixed_use", "business_use", "private_use")):
        terms.append("mixed, private, or business use")
    if any(
        cgt_review_flag_has_signal(raw.get(key))
        for key in ("exemption_flag", "discount_flag", "discount_claim", "concession_flag")
    ):
        terms.append("exemption, discount claim, or concession flags")
    if cgt_discount_or_residency_has_review_signal(raw):
        terms.append("discount timing or residency signals")
    if cgt_small_business_concession_has_review_signal(raw):
        terms.append("small business CGT concession review")
    if cgt_main_residence_has_review_signal(raw):
        terms.append("main residence exemption review")
    if cgt_main_residence_conflict_or_overlap(raw):
        terms.append("rental/business use or spouse/partner main-residence conflict")
    return terms


def cgt_row_sources(raw: Dict[str, Any]) -> List[str]:
    sources = list(ATO_CGT_SOURCES)
    if cgt_main_residence_has_source_signal(raw):
        sources.extend(ATO_CGT_MAIN_RESIDENCE_SOURCES)
    if cgt_small_business_concession_has_source_signal(raw):
        sources.extend(ATO_CGT_SMALL_BUSINESS_CONCESSION_SOURCES)
    return list(dict.fromkeys(sources))


def cgt_small_business_concession_has_source_signal(raw: Dict[str, Any]) -> bool:
    return cgt_small_business_concession_has_review_signal(raw) or any(
        key in raw and cgt_boolean_false(raw.get(key))
        for key in CGT_SMALL_BUSINESS_CONCESSION_FLAG_FIELDS
    )


def cgt_main_residence_has_source_signal(raw: Dict[str, Any]) -> bool:
    return cgt_main_residence_has_review_signal(raw) or any(
        key in raw and cgt_boolean_false(raw.get(key))
        for key in (
            "main_residence_claim",
            "main_residence_rental_business_use",
            "main_residence_spouse_conflict",
        )
    )


def cgt_main_residence_conflict_or_overlap(raw: Dict[str, Any]) -> bool:
    return cgt_boolean_true(raw.get("main_residence_rental_business_use")) or cgt_boolean_true(
        raw.get("main_residence_spouse_conflict")
    )


def cgt_main_residence_has_review_signal(raw: Dict[str, Any]) -> bool:
    return any(
        cgt_review_flag_has_signal(raw.get(key)) or cgt_boolean_needs_evidence(raw.get(key))
        for key in (
            "main_residence_claim",
            "main_residence_rental_business_use",
            "main_residence_spouse_conflict",
        )
    ) or any(cgt_main_residence_text_has_signal(key, raw.get(key)) for key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS)


def cgt_main_residence_text_has_signal(key: str, value: Any) -> bool:
    if key == "main_residence_property_records" and cgt_records_missing(value):
        return not is_missing(value)
    return has_meaningful_cgt_signal(key, value) or (has_meaningful_value(value) and contains_unknown(value))


def cgt_main_residence_evidence_gaps(raw: Dict[str, Any]) -> List[str]:
    if not cgt_main_residence_has_review_signal(raw):
        return []
    evidence: List[str] = []
    if cgt_boolean_needs_evidence(raw.get("main_residence_claim")):
        evidence.append("main residence claim evidence")
    if cgt_boolean_needs_evidence(raw.get("main_residence_rental_business_use")):
        evidence.append("rental/business use evidence")
    if cgt_boolean_needs_evidence(raw.get("main_residence_spouse_conflict")):
        evidence.append("spouse/partner main residence evidence")
    for key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS:
        value = raw.get(key)
        if key == "main_residence_property_records" and cgt_records_missing(value):
            evidence.append("main residence property records")
        elif is_missing(value) or contains_unknown(value):
            evidence.append("main residence ownership/occupancy/absence evidence")
    return list(dict.fromkeys(evidence))


def cgt_decline_contradiction(raw: Dict[str, Any]) -> bool:
    return bool(raw.get(CGT_DECLINE_SIGNAL_KEY)) or bool(cgt_decline_values(raw) and cgt_has_facts(raw))


def cgt_declines_workflow(value: Any) -> bool:
    if not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if cgt_record_context(lowered):
        return False
    if lowered in CGT_DECLINE_PHRASES:
        return True
    return any(
        phrase in lowered
        for phrase in (
            "do not have cgt",
            "don't have cgt",
            "dont have cgt",
            "do not have capital gains",
            "don't have capital gains",
            "dont have capital gains",
            "no cgt this year",
            "no cgt event",
            "no cgt events",
            "no capital gains this year",
            "no capital gains tax event",
            "no capital gains tax events",
        )
    )


def cgt_source_declines_workflow(key: str, value: Any) -> bool:
    if key == "no_cgt":
        return cgt_boolean_true(value) or cgt_declines_workflow(value)
    if key == "summary" and cgt_summary_has_event_fact(value):
        return False
    if cgt_field_absence_value(key, value):
        return False
    return cgt_declines_workflow(value)


def cgt_summary_has_event_fact(value: Any) -> bool:
    if not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if lowered in CGT_DECLINE_PHRASES:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "cgt event",
            "capital gains tax event",
            "selling",
            "sold",
            "sell",
            "sale",
            "disposed",
            "disposal",
            "gifted",
            "gift",
            "transferred",
            "transfer",
            "capital loss",
            "at a loss",
            "loss on",
        )
    )


def cgt_field_absence_value(key: str, value: Any) -> bool:
    if not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if key == "no_cgt":
        return False
    if lowered in {"no cgt", "no cgt event", "no cgt events", "no capital gain", "no capital gains", "no capital gains tax"}:
        return False
    return key != "event_type" and lowered in CGT_FIELD_ABSENCE_PHRASES


def cgt_records_missing(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if is_missing(value) or contains_unknown(value):
        return True
    if cgt_declines_workflow(value):
        return True
    lowered = text(value).strip().lower()
    has_record_context = cgt_record_context(lowered)
    if has_record_context and lowered.startswith(("no ", "without ", "missing ")):
        return True
    if has_record_context and any(
        phrase in lowered
        for phrase in (
            "record not held",
            "receipt not held",
            "not held",
            "not available",
            "not provided",
            "do not have",
            "don't have",
            "dont have",
        )
    ):
        return True
    return lowered in {"no", "n", "false", "none", "not held", "not available"} or any(
        phrase in lowered
        for phrase in (
            "no records",
            "no receipt",
            "no contract",
            "records not held",
            "records not available",
            "records not provided",
            "do not have records",
            "don't have records",
            "dont have records",
        )
    )


def cgt_record_context(lowered: str) -> bool:
    return any(term in lowered for term in ("record", "records", "receipt", "statement", "contract", "invoice"))


def cgt_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    if cgt_declines_workflow(value):
        return False
    return contains_unknown(value) or cgt_amount_malformed(value)


def cgt_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        amount = money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return amount is not None and amount < 0


def cgt_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def cgt_date_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    if cgt_declines_workflow(value):
        return False
    return contains_unknown(value) or parse_iso_date(value) is None


def cgt_boolean_needs_evidence(value: Any) -> bool:
    return boolean_answer_needs_evidence(value)


def cgt_boolean_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if contains_unknown(value):
        return False
    return text(value).strip().lower() in {"true", "yes", "y", "1", "on", "checked"}


def cgt_boolean_false(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value == 0
    if contains_unknown(value):
        return False
    return text(value).strip().lower() in {"false", "no", "n", "0", "off", "unchecked", "none"}


def cgt_field_text(raw: Dict[str, Any], key: str) -> str:
    if cgt_field_absence_value(key, raw.get(key)):
        return "unknown"
    value = display_value(raw.get(key))
    return value if value else "unknown"


def cgt_amount_text(value: Any) -> str:
    if cgt_amount_needs_evidence(value):
        return display_value(value) or "unknown"
    return money_text(cgt_money_value(value))


def cgt_boolean_flag_text(value: Any) -> str:
    return cgt_bool_text(value) if not is_missing(value) else "unknown"


def cgt_bool_text(value: Any) -> str:
    return display_value(value) if not cgt_field_absence_value("", value) else "unknown"


def cgt_decline_signal_text(raw: Dict[str, Any]) -> str:
    signals = raw.get(CGT_DECLINE_SIGNAL_KEY)
    if not isinstance(signals, list):
        return ""
    return ", ".join(display_value(signal) for signal in signals if display_value(signal))


def cgt_conflict_signal_text(raw: Dict[str, Any]) -> str:
    signals = raw.get(CGT_CONFLICT_SIGNAL_KEY)
    if not isinstance(signals, list):
        return ""
    return ", ".join(display_value(signal) for signal in signals if display_value(signal))


def cgt_tab_text(evidence: List[str], review: List[str]) -> str:
    if evidence and review:
        return (
            f"CGT event needs {', '.join(evidence)} and stays accountant review for "
            f"{', '.join(review)}; no capital gain or loss amount worked out."
        )
    if evidence:
        return f"CGT event needs {', '.join(evidence)} before accountant review; no capital gain or loss amount worked out."
    if review:
        return f"CGT event stays accountant review for {', '.join(review)}; no capital gain or loss amount worked out."
    return "CGT event stays accountant review; no capital gain or loss amount worked out."


def crypto_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("crypto")
    fields = {
        "event_type": answers.get("crypto_event_type"),
        "exchange_or_wallet": answers.get("crypto_exchange_or_wallet"),
        "asset": answers.get("crypto_asset"),
        "quantity": answers.get("crypto_quantity"),
        "acquired_date": answers.get("crypto_acquired_date"),
        "disposed_date": answers.get("crypto_disposed_date"),
        "cost_base": answers.get("crypto_cost_base"),
        "capital_proceeds": answers.get("crypto_capital_proceeds"),
        "rewards_income": answers.get("crypto_rewards_income"),
        "transfer_between_wallets": answers.get("crypto_transfer_between_wallets"),
        "wallet_records": answers.get("crypto_wallet_records"),
        "ownership_entity": answers.get("crypto_ownership_entity"),
        "business_use": answers.get("crypto_business_use"),
        "private_use": answers.get("crypto_private_use"),
        "items": answers.get("crypto_items"),
    }
    flat_values = {key: value for key, value in fields.items() if has_meaningful_crypto_flat_value(key, value)}
    flat_declines = {
        key: value
        for key, value in fields.items()
        if key in CRYPTO_SOURCE_KEY_FACTS and crypto_source_declines_workflow(key, value)
    }
    if not isinstance(raw, dict):
        return crypto_values_with_declines(flat_values, flat_declines)
    if not has_meaningful_value(raw):
        return crypto_values_with_declines(flat_values, flat_declines)
    raw_declines = crypto_decline_values(raw)
    merged = dict(flat_values)
    for key, value in raw.items():
        if has_meaningful_crypto_override(key, value):
            merged[key] = value
        elif key not in merged and has_explicit_crypto_evidence_gap(key, value):
            merged[key] = value
    return crypto_values_with_declines(merged, {**flat_declines, **raw_declines})


def crypto_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_crypto_inputs(raw):
        return []
    if not isinstance(raw, dict):
        return []
    items = crypto_item_values(raw.get("items"))
    evidence = crypto_evidence_gaps(raw, items)
    status = "Evidence" if evidence else "Accountant review"
    answer = (
        f"Event {crypto_field_text(raw, items, 'event_type')}; "
        f"asset {crypto_field_text(raw, items, 'asset')}; "
        f"exchange/wallet {crypto_field_text(raw, items, 'exchange_or_wallet')}; "
        f"quantity {crypto_amount_field_text(raw, items, 'quantity')}; "
        f"acquired {crypto_field_text(raw, items, 'acquired_date')}; "
        f"disposed {crypto_field_text(raw, items, 'disposed_date')}; "
        f"cost base {crypto_amount_field_text(raw, items, 'cost_base', money=True)}; "
        f"capital proceeds {crypto_amount_field_text(raw, items, 'capital_proceeds', money=True)}; "
        f"rewards income {crypto_amount_field_text(raw, items, 'rewards_income', money=True)}; "
        f"own-wallet transfer {crypto_bool_field_text(raw, items, 'transfer_between_wallets')}; "
        f"records {crypto_field_text(raw, items, 'wallet_records')}; "
        f"owner/entity {crypto_field_text(raw, items, 'ownership_entity')}; "
        f"business use {crypto_bool_field_text(raw, items, 'business_use')}; "
        f"private use {crypto_bool_field_text(raw, items, 'private_use')}"
    )
    item_text = crypto_items_text(items)
    if item_text:
        answer = f"{answer}; items {item_text}"
    decline_text = crypto_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    return [
        guide_row(
            "CRYPTO-CGT",
            "Crypto asset investments",
            "Crypto disposals, swaps, exchanges, conversions, rewards, transfers, wallet records, and cost-base workflow",
            answer,
            "Crypto handling collects event type, asset, dates, proceeds, cost base, rewards, wallet records, ownership, and both business and private use context flags for accountant review before entry.",
            status,
            ATO_CRYPTO_SOURCES,
            tab_text=crypto_tab_text(evidence),
            row_kind="capital-gains",
            facts=[
                *handoff_facts(
                    ("event-type", "Event type", raw.get("event_type")),
                    ("asset", "Crypto asset", raw.get("asset")),
                    ("exchange-wallet", "Exchange or wallet", raw.get("exchange_or_wallet")),
                    ("quantity", "Quantity", raw.get("quantity")),
                    ("acquired-date", "Acquired date", raw.get("acquired_date")),
                    ("disposed-date", "Disposed date", raw.get("disposed_date")),
                    ("cost-base", "Cost base supplied", raw.get("cost_base")),
                    ("capital-proceeds", "Capital proceeds supplied", raw.get("capital_proceeds")),
                    ("rewards-income", "Rewards income supplied", raw.get("rewards_income")),
                    ("own-wallet-transfer", "Transfer between own wallets", raw.get("transfer_between_wallets")),
                    ("records", "Wallet records", raw.get("wallet_records")),
                    ("owner-entity", "Owner or entity", raw.get("ownership_entity")),
                    ("business-use", "Business-use context", raw.get("business_use")),
                    ("private-use", "Private-use context", raw.get("private_use")),
                    ("decline-signals", "Decline signals", decline_text or "none"),
                ),
                *indexed_item_handoff_facts("crypto-item", "Crypto item", items),
            ],
        )
    ]


def has_meaningful_crypto_flat_value(key: str, value: Any) -> bool:
    if key in CRYPTO_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in CRYPTO_SOURCE_KEY_FACTS and (
        crypto_source_declines_workflow(key, value) or crypto_field_absence_value(key, value)
    ):
        return False
    return has_meaningful_value(value)


def has_meaningful_crypto_override(key: str, value: Any) -> bool:
    if key == "items":
        return bool(crypto_item_values(value))
    if key in CRYPTO_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in CRYPTO_SOURCE_KEY_FACTS and (
        crypto_source_declines_workflow(key, value) or crypto_field_absence_value(key, value)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def has_explicit_crypto_evidence_gap(key: str, value: Any) -> bool:
    if key in CRYPTO_SOURCE_KEY_FACTS and (
        crypto_source_declines_workflow(key, value) or crypto_field_absence_value(key, value)
    ):
        return False
    if key in CRYPTO_AMOUNT_FIELDS:
        return crypto_amount_needs_evidence(value)
    if key in CRYPTO_DATE_FIELDS:
        return crypto_date_needs_evidence(value)
    if key in ("event_type", "exchange_or_wallet", "asset", "wallet_records", "ownership_entity", *CRYPTO_BOOLEAN_FIELDS):
        return has_meaningful_value(value) and contains_unknown(value)
    return False


def crypto_values_with_declines(values: Dict[str, Any], declines: Dict[str, Any]) -> Dict[str, Any]:
    if not declines or not crypto_has_facts(values):
        return values
    merged = dict(values)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        if not crypto_has_field_value(merged, key):
            merged[key] = value
    merged[CRYPTO_DECLINE_SIGNAL_KEY] = signals
    return merged


def crypto_decline_values(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key in CRYPTO_SOURCE_KEY_FACTS and crypto_source_declines_workflow(key, value)
    }


def crypto_item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict) and has_meaningful_crypto_item(item)]


def has_meaningful_crypto_item(item: Dict[str, Any]) -> bool:
    if any(has_meaningful_crypto_signal(key, item.get(key)) for key in CRYPTO_SIGNAL_FIELDS):
        return True
    if any(crypto_amount_field_needs_evidence(item, key) for key in CRYPTO_AMOUNT_FIELDS):
        return True
    return any(crypto_date_field_needs_evidence(item, key) for key in CRYPTO_DATE_FIELDS)


def crypto_amount_field_needs_evidence(record: Dict[str, Any], key: str) -> bool:
    value = record.get(key)
    return not crypto_field_absence_value(key, value) and crypto_amount_needs_evidence(value)


def crypto_date_field_needs_evidence(record: Dict[str, Any], key: str) -> bool:
    value = record.get(key)
    return not crypto_field_absence_value(key, value) and crypto_date_needs_evidence(value)


def has_crypto_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if crypto_declines_without_facts(raw):
        return False
    return crypto_has_facts(raw)


def crypto_has_facts(record: Dict[str, Any]) -> bool:
    if crypto_item_values(record.get("items")):
        return True
    return any(
        has_meaningful_crypto_signal(key, value) or has_explicit_crypto_evidence_gap(key, value)
        for key, value in record.items()
        if key != "items"
        and key != CRYPTO_DECLINE_SIGNAL_KEY
        and not crypto_source_declines_workflow(key, value)
        and not crypto_field_absence_value(key, value)
    )


def crypto_declines_without_facts(raw: Dict[str, Any]) -> bool:
    if not crypto_decline_values(raw):
        return False
    return not crypto_has_facts(raw)


def has_meaningful_crypto_signal(key: str, value: Any) -> bool:
    if key in CRYPTO_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    if key in CRYPTO_BOOLEAN_FIELDS:
        if crypto_boolean_true(value):
            return True
        if crypto_boolean_false(value):
            return False
    if key in CRYPTO_SOURCE_KEY_FACTS and (
        crypto_source_declines_workflow(key, value) or crypto_field_absence_value(key, value)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def crypto_evidence_gaps(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> List[str]:
    evidence: List[str] = []
    if crypto_decline_contradiction(raw, items):
        evidence.append("no-crypto answer with crypto facts")
    if crypto_event_type_needs_evidence(raw, items):
        evidence.append("event type evidence")
    if crypto_identity_needs_evidence(raw, items):
        evidence.append("asset and exchange/wallet identity evidence")
    if crypto_items_need_evidence(raw, items):
        evidence.append("per-item crypto evidence")
    if crypto_amount_conflicts(raw, items):
        evidence.append("top-level and item amount reconciliation")
    if crypto_records_evidence(raw, items):
        evidence.append("wallet or exchange records")
    if crypto_amounts_need_evidence(raw, items):
        evidence.append("numeric proceeds, cost-base, quantity, or rewards evidence")
    if crypto_dates_need_evidence(raw, items):
        evidence.append("acquisition or disposal date evidence")
    if crypto_ownership_needs_evidence(raw, items):
        evidence.append("ownership or entity evidence")
    if crypto_use_context_needs_evidence(raw, items):
        evidence.append("business/private use context")
    if crypto_transfer_needs_evidence(raw, items):
        evidence.append("own-wallet transfer support")
    return evidence


def crypto_event_type_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    event = raw.get("event_type")
    if not crypto_has_field_value(raw, "event_type"):
        return not any(crypto_has_field_value(item, "event_type") for item in items)
    return contains_unknown(event) or any(contains_unknown(item.get("event_type")) for item in items)


def crypto_identity_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    for key in ("asset", "exchange_or_wallet"):
        value = raw.get(key)
        if not crypto_has_field_value(raw, key):
            if not any(crypto_has_field_value(item, key) for item in items):
                return True
        elif contains_unknown(value):
            return True
    return any(
        contains_unknown(item.get(key))
        for item in items
        for key in ("asset", "exchange_or_wallet")
    )


def crypto_items_need_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return any(crypto_item_needs_evidence(raw, item) for item in items)


def crypto_item_needs_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    return (
        crypto_declines_with_facts(item)
        or any(crypto_item_context_field_needs_evidence(raw, item, key) for key in CRYPTO_ITEM_PARENT_CONTEXT_FIELDS)
        or crypto_item_records_need_evidence(raw, item)
        or crypto_item_amounts_need_evidence(raw, item)
        or crypto_item_dates_need_evidence(raw, item)
        or crypto_item_use_context_needs_evidence(raw, item)
        or crypto_item_transfer_needs_evidence(raw, item)
    )


def crypto_item_context_field_needs_evidence(raw: Dict[str, Any], item: Dict[str, Any], key: str) -> bool:
    value = item.get(key)
    if not is_missing(value):
        return contains_unknown(value) or crypto_field_absence_value(key, value)
    return not crypto_has_field_value(raw, key)


def crypto_item_records_need_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    value = item.get("wallet_records")
    if not is_missing(value):
        return crypto_records_missing(value) or crypto_field_absence_value("wallet_records", value)
    return not crypto_has_field_value(raw, "wallet_records")


def crypto_item_amounts_need_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    if any(crypto_amount_field_needs_evidence(item, key) for key in CRYPTO_AMOUNT_FIELDS):
        return True
    if crypto_item_disposal_like(raw, item):
        return any(crypto_money_value(item.get(key)) is None for key in ("cost_base", "capital_proceeds", "quantity"))
    if crypto_item_reward_like(raw, item):
        return crypto_money_value(item.get("rewards_income")) is None
    return False


def crypto_item_dates_need_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    if any(crypto_date_field_needs_evidence(item, key) for key in CRYPTO_DATE_FIELDS):
        return True
    if crypto_item_disposal_like(raw, item):
        return any(not crypto_has_field_value(item, key) for key in CRYPTO_DATE_FIELDS)
    return False


def crypto_item_disposal_like(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    event = crypto_item_effective_value(raw, item, "event_type")
    transfer_between_wallets = crypto_item_effective_value(raw, item, "transfer_between_wallets")
    if crypto_event_is_transfer(event) and crypto_boolean_true(transfer_between_wallets):
        return False
    return crypto_event_is_disposal(event) or (
        crypto_event_is_transfer(event) and crypto_boolean_false(transfer_between_wallets)
    )


def crypto_item_reward_like(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    return crypto_event_is_reward(crypto_item_effective_value(raw, item, "event_type"))


def crypto_item_effective_value(raw: Dict[str, Any], item: Dict[str, Any], key: str) -> Any:
    if crypto_has_field_value(item, key):
        return item.get(key)
    if crypto_has_field_value(raw, key):
        return raw.get(key)
    return None


def crypto_item_use_context_needs_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    if any(crypto_boolean_needs_evidence(item.get(key)) for key in CRYPTO_USE_CONTEXT_FIELDS):
        return True
    if crypto_use_context_complete(raw):
        return False
    return crypto_use_context_needs_evidence(item, [])


def crypto_item_transfer_needs_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    value = item.get("transfer_between_wallets")
    if crypto_boolean_needs_evidence(value):
        return True
    if crypto_event_is_transfer(crypto_item_effective_value(raw, item, "event_type")):
        if crypto_field_absence_value("transfer_between_wallets", value):
            return True
        if crypto_boolean_complete(value):
            return False
        return not crypto_has_field_value(raw, "transfer_between_wallets")
    return False


def crypto_records_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    records = raw.get("wallet_records")
    if has_meaningful_value(records):
        if crypto_records_missing(records):
            return True
    if items:
        return any(crypto_item_records_need_evidence(raw, item) for item in items)
    return not crypto_has_field_value(raw, "wallet_records")


def crypto_amounts_need_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if any(crypto_amount_field_needs_evidence(raw, key) for key in CRYPTO_AMOUNT_FIELDS):
        return True
    if any(crypto_amount_field_needs_evidence(item, key) for item in items for key in CRYPTO_AMOUNT_FIELDS):
        return True
    if crypto_disposal_like(raw, items) and (
        crypto_amount_value(raw, items, "cost_base") is None
        or crypto_amount_value(raw, items, "capital_proceeds") is None
        or crypto_disposal_quantity_missing(raw, items)
    ):
        return True
    if crypto_reward_like(raw, items) and crypto_amount_value(raw, items, "rewards_income") is None:
        return True
    return False


def crypto_amount_conflicts(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    for key in CRYPTO_AMOUNT_FIELDS:
        if key == "quantity" and crypto_quantities_are_item_specific(raw, items):
            continue
        direct = crypto_money_value(raw.get(key))
        item_total = crypto_item_amount_total(raw, items, key)
        if direct is None or item_total is None:
            continue
        tolerance = 0.00000001 if key == "quantity" else 0.005
        if abs(direct - item_total) > tolerance:
            return True
    return False


def crypto_decline_contradiction(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return crypto_declines_with_facts(raw) or any(crypto_declines_with_facts(item) for item in items)


def crypto_declines_with_facts(record: Dict[str, Any]) -> bool:
    if record.get(CRYPTO_DECLINE_SIGNAL_KEY):
        return True
    if not crypto_decline_values(record):
        return False
    return crypto_has_facts(record)


def crypto_dates_need_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if any(crypto_date_field_needs_evidence(raw, key) for key in CRYPTO_DATE_FIELDS):
        return True
    if any(crypto_date_field_needs_evidence(item, key) for item in items for key in CRYPTO_DATE_FIELDS):
        return True
    if crypto_disposal_like(raw, items):
        return crypto_missing_date(raw, items, "acquired_date") or crypto_missing_date(raw, items, "disposed_date")
    return False


def crypto_ownership_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    owner = raw.get("ownership_entity")
    if not crypto_has_field_value(raw, "ownership_entity"):
        return not any(crypto_has_field_value(item, "ownership_entity") for item in items)
    return contains_unknown(owner) or any(contains_unknown(item.get("ownership_entity")) for item in items)


def crypto_use_context_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if any(crypto_boolean_needs_evidence(raw.get(key)) for key in CRYPTO_USE_CONTEXT_FIELDS):
        return True
    if any(
        crypto_boolean_needs_evidence(item.get(key))
        for item in items
        for key in CRYPTO_USE_CONTEXT_FIELDS
    ):
        return True
    if crypto_use_context_conflicts(raw, items):
        return True
    if crypto_use_context_complete(raw):
        return False
    return not items or not all(crypto_use_context_complete(item) for item in items)


def crypto_use_context_conflicts(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if not crypto_use_context_complete(raw):
        return False
    return any(crypto_item_use_context_conflicts(raw, item) for item in items)


def crypto_item_use_context_conflicts(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    for key in CRYPTO_USE_CONTEXT_FIELDS:
        raw_value = crypto_boolean_value(raw.get(key))
        item_value = crypto_boolean_value(item.get(key))
        if raw_value is not None and item_value is not None and raw_value != item_value:
            return True
    return False


def crypto_use_context_complete(record: Dict[str, Any]) -> bool:
    return all(crypto_boolean_complete(record.get(key)) for key in CRYPTO_USE_CONTEXT_FIELDS)


def crypto_boolean_complete(value: Any) -> bool:
    return crypto_boolean_true(value) or crypto_boolean_false(value)


def crypto_boolean_value(value: Any) -> Optional[bool]:
    if crypto_boolean_true(value):
        return True
    if crypto_boolean_false(value):
        return False
    return None


def crypto_transfer_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if crypto_boolean_needs_evidence(raw.get("transfer_between_wallets")):
        return True
    if any(crypto_boolean_needs_evidence(item.get("transfer_between_wallets")) for item in items):
        return True
    if crypto_event_is_transfer(raw.get("event_type")) and is_missing(raw.get("transfer_between_wallets")) and not items:
        return True
    return any(crypto_item_transfer_needs_evidence(raw, item) for item in items)


def crypto_disposal_like(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return crypto_record_disposal_like(raw) or any(crypto_record_disposal_like(item) for item in items)


def crypto_reward_like(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return any(crypto_event_is_reward(value) for value in crypto_event_values(raw, items))


def crypto_event_values(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> List[Any]:
    values = [raw.get("event_type") if crypto_has_field_value(raw, "event_type") else None]
    values.extend(item.get("event_type") for item in items)
    return [
        value
        for value in values
        if has_meaningful_value(value) and not crypto_field_absence_value("event_type", value)
    ]


def crypto_record_disposal_like(record: Dict[str, Any]) -> bool:
    event = record.get("event_type")
    if crypto_event_is_transfer(event) and crypto_boolean_true(record.get("transfer_between_wallets")):
        return False
    return crypto_event_is_disposal(event) or (
        crypto_event_is_transfer(event) and crypto_boolean_false(record.get("transfer_between_wallets"))
    )


def crypto_event_is_disposal(value: Any) -> bool:
    lowered = text(value).strip().lower()
    return any(
        term in lowered
        for term in (
            "sell",
            "sold",
            "sale",
            "disposal",
            "dispose",
            "swap",
            "trade",
            "exchange",
            "convert",
            "conversion",
            "spend",
            "gift",
        )
    )


def crypto_event_is_reward(value: Any) -> bool:
    lowered = text(value).strip().lower()
    return any(term in lowered for term in ("staking", "reward", "airdrop", "mining"))


def crypto_event_is_transfer(value: Any) -> bool:
    lowered = text(value).strip().lower()
    return "transfer" in lowered


def crypto_boolean_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    lowered = text(value).strip().lower()
    return lowered in {"true", "yes", "y", "1", "on", "checked"}


def crypto_boolean_false(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value == 0
    if contains_unknown(value):
        return False
    lowered = text(value).strip().lower()
    if lowered in {"false", "no", "n", "0", "off", "unchecked"}:
        return True
    return any(
        phrase in lowered
        for phrase in (
            "not own wallet",
            "not own-wallet",
            "not my wallet",
            "not my own wallet",
            "not between own wallets",
            "not an own-wallet transfer",
            "not own-wallet transfer",
            "non-own wallet",
            "non own wallet",
        )
    )


def crypto_missing_date(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> bool:
    if crypto_has_field_value(raw, key):
        return False
    return not any(crypto_has_field_value(item, key) for item in items)


def crypto_records_missing(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if is_missing(value) or contains_unknown(value):
        return True
    if crypto_declines_workflow(value):
        return True
    lowered = text(value).strip().lower()
    if crypto_record_context(lowered) and lowered.startswith(("no ", "without ", "missing ")):
        return True
    if crypto_record_absence_phrase(lowered):
        return True
    if crypto_record_context(lowered) and any(
        phrase in lowered
        for phrase in ("do not have", "don't have", "dont have", "not held", "not available", "not provided")
    ):
        return True
    return lowered in {"no", "n", "false", "none", "not held", "not available"} or any(
        phrase in lowered
        for phrase in (
            "no wallet records",
            "no exchange records",
            "no transaction history",
            "records not held",
            "records not available",
            "records not provided",
            "csv not held",
            "csv not available",
            "csv not provided",
            "do not have records",
            "don't have records",
        )
    )


def crypto_declines_workflow(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if crypto_record_context(lowered):
        return False
    if lowered in CRYPTO_DECLINE_PHRASES:
        return True
    return any(
        phrase in lowered
        for phrase in (
            "do not have crypto",
            "do not have any crypto",
            "don't have crypto",
            "don't have any crypto",
            "dont have crypto",
            "dont have any crypto",
            "do not have crypto assets",
            "don't have crypto assets",
            "dont have crypto assets",
            "no crypto this year",
            "no cryptocurrency this year",
        )
    )


def crypto_source_declines_workflow(key: str, value: Any) -> bool:
    if crypto_field_absence_value(key, value):
        return False
    return crypto_declines_workflow(value)


def crypto_field_absence_value(key: str, value: Any) -> bool:
    if not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if crypto_identity_absence_value(key, lowered):
        return True
    if lowered in {"no crypto", "no crypto asset", "no crypto assets", "no cryptocurrency", "no cryptocurrencies", "no digital currency", "no digital currencies"}:
        return False
    if lowered in {"no staking rewards", "no crypto rewards"}:
        return key == "rewards_income"
    return key != "event_type" and lowered in CRYPTO_FIELD_ABSENCE_PHRASES


def crypto_identity_absence_value(key: str, lowered: str) -> bool:
    if key not in CRYPTO_IDENTITY_FIELDS:
        return False
    if lowered in CRYPTO_IDENTITY_ABSENCE_EXACT_PHRASES[key]:
        return True
    context_pattern = "|".join(re.escape(term) for term in CRYPTO_IDENTITY_ABSENCE_CONTEXTS[key])
    return bool(
        re.search(rf"\b(?:no|without|missing)\b(?:\s+\w+){{0,3}}\s+\b(?:{context_pattern})\b", lowered)
        or re.search(
            rf"\b(?:do not have|don't have|dont have)\b(?:\s+\w+){{0,3}}\s+\b(?:{context_pattern})\b",
            lowered,
        )
    )


def crypto_has_field_value(record: Dict[str, Any], key: str) -> bool:
    value = record.get(key)
    return (
        has_meaningful_value(value)
        and not crypto_source_declines_workflow(key, value)
        and not crypto_field_absence_value(key, value)
    )


def crypto_record_context(lowered: str) -> bool:
    return any(term in lowered for term in ("record", "records", "wallet", "exchange", "csv", "transaction history"))


def crypto_record_absence_phrase(lowered: str) -> bool:
    if not crypto_record_context(lowered):
        return False
    return re.search(
        r"\b(?:no|without|missing)\b(?:\s+\w+){0,3}\s+\b(?:record|records|wallet|exchange|csv|transaction\s+history)\b",
        lowered,
    ) is not None


def crypto_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    if crypto_declines_workflow(value):
        return False
    return contains_unknown(value) or crypto_amount_malformed(value)


def crypto_amount_malformed(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    try:
        amount = money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return amount is not None and amount < 0


def crypto_amount_value(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> Optional[float]:
    if key == "quantity" and crypto_quantities_are_item_specific(raw, items):
        return None
    item_total = crypto_item_amount_total(raw, items, key)
    if item_total is not None:
        return item_total
    return crypto_money_value(raw.get(key))


def crypto_disposal_quantity_missing(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if crypto_quantities_are_item_specific(raw, items):
        return False
    return crypto_amount_value(raw, items, "quantity") is None


def crypto_item_amount_total(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> Optional[float]:
    if key == "quantity" and crypto_quantities_are_item_specific(raw, items):
        return None
    amounts = [crypto_money_value(item.get(key)) for item in items]
    real_amounts = [amount for amount in amounts if amount is not None]
    if not real_amounts:
        return None
    return round(sum(real_amounts), 8 if key == "quantity" else 2)


def crypto_quantities_are_item_specific(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    assets: Set[str] = set()
    for item in items:
        if crypto_money_value(item.get("quantity")) is None:
            continue
        asset = crypto_quantity_asset_label(raw, item)
        if asset:
            assets.add(asset)
    return len(assets) > 1


def crypto_quantity_asset_label(raw: Dict[str, Any], item: Dict[str, Any]) -> str:
    if crypto_has_field_value(item, "asset"):
        return text(item.get("asset")).strip().lower()
    if crypto_has_field_value(raw, "asset"):
        return text(raw.get("asset")).strip().lower()
    return ""


def crypto_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def crypto_date_needs_evidence(value: Any) -> bool:
    if isinstance(value, bool) or is_missing(value):
        return False
    if crypto_declines_workflow(value):
        return False
    return contains_unknown(value) or parse_iso_date(value) is None


def crypto_boolean_needs_evidence(value: Any) -> bool:
    return boolean_answer_needs_evidence(value)


def boolean_answer_needs_evidence(value: Any) -> bool:
    if not has_meaningful_value(value) or isinstance(value, bool):
        return False
    lowered = text(value).strip().lower()
    return contains_unknown(value) or any(phrase in lowered for phrase in BOOLEAN_UNCERTAIN_PHRASES)


def crypto_field_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
    direct = crypto_record_field_text(raw, key)
    if direct:
        return direct
    values = [value for item in items if (value := crypto_record_field_text(item, key))]
    return ", ".join(values) if values else "unknown"


def crypto_items_text(items: List[Dict[str, Any]]) -> str:
    details: List[str] = []
    for idx, item in enumerate(items, start=1):
        label = crypto_record_field_text(item, "asset") or crypto_record_field_text(item, "exchange_or_wallet") or f"item {idx}"
        context = crypto_item_context_text(item)
        suffix = f", {context}" if context else ""
        details.append(
            f"{label}: event {crypto_record_field_text(item, 'event_type') or 'unknown'}, "
            f"acquired {crypto_record_field_text(item, 'acquired_date') or 'unknown'}, "
            f"disposed {crypto_record_field_text(item, 'disposed_date') or 'unknown'}, "
            f"quantity {crypto_item_amount_text(item, 'quantity')}, "
            f"cost base {crypto_item_amount_text(item, 'cost_base', money=True)}, "
            f"proceeds {crypto_item_amount_text(item, 'capital_proceeds', money=True)}, "
            f"rewards {crypto_item_amount_text(item, 'rewards_income', money=True)}"
            f"{suffix}"
        )
    return " | ".join(details)


def crypto_item_context_text(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key, label in (
        ("exchange_or_wallet", "exchange/wallet"),
        ("transfer_between_wallets", "own-wallet transfer"),
        ("wallet_records", "records"),
        ("ownership_entity", "owner/entity"),
        ("business_use", "business use"),
        ("private_use", "private use"),
    ):
        value = crypto_record_field_text(item, key)
        if value:
            parts.append(f"{label} {value}")
    return ", ".join(parts)


def crypto_amount_field_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str, money: bool = False) -> str:
    if crypto_declines_workflow(raw.get(key)):
        return display_value(raw.get(key))
    if key == "quantity" and crypto_quantities_are_item_specific(raw, items):
        return "item-specific"
    amount = crypto_amount_value(raw, items, key)
    return money_text(amount) if money else crypto_amount_text(amount)


def crypto_item_amount_text(item: Dict[str, Any], key: str, money: bool = False) -> str:
    if crypto_declines_workflow(item.get(key)):
        return display_value(item.get(key))
    amount = crypto_money_value(item.get(key))
    return money_text(amount) if money else crypto_amount_text(amount)


def crypto_record_field_text(record: Dict[str, Any], key: str) -> str:
    if crypto_field_absence_value(key, record.get(key)):
        return ""
    return display_value(record.get(key))


def crypto_decline_signal_text(raw: Dict[str, Any]) -> str:
    signals = raw.get(CRYPTO_DECLINE_SIGNAL_KEY)
    if not isinstance(signals, list):
        return ""
    return ", ".join(display_value(signal) for signal in signals if display_value(signal))


def crypto_amount_text(value: Optional[float]) -> str:
    return "unknown" if value is None else f"{value:.8g}"


def crypto_bool_text(value: Any) -> str:
    return display_value(value) if not is_missing(value) else "unknown"


def crypto_bool_field_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
    if not is_missing(raw.get(key)) and not crypto_field_absence_value(key, raw.get(key)):
        return crypto_bool_text(raw.get(key))
    values: List[str] = []
    seen: Set[str] = set()
    for item in items:
        if is_missing(item.get(key)) or crypto_field_absence_value(key, item.get(key)):
            continue
        value = crypto_bool_text(item.get(key))
        if value in seen:
            continue
        seen.add(value)
        values.append(value)
    return ", ".join(values) if values else "unknown"


def crypto_tab_text(evidence: List[str]) -> str:
    if evidence:
        return f"Crypto workflow needs {', '.join(evidence)} before accountant review."
    return "Crypto disposals, swaps, exchanges, conversions, rewards, transfers, wallet records, and cost base require accountant review before entry."


def rental_property_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    raw = answers.get("rental_property")
    fields = {
        nested_key: answers.get(flat_key)
        for flat_key, nested_key in RENTAL_PROPERTY_FLAT_FIELD_KEYS.items()
    }
    fields["items"] = answers.get("rental_property_items")
    flat_values = rental_property_answer_values(fields)
    flat_declines = rental_property_decline_values(fields)
    if not isinstance(raw, dict):
        return rental_property_values_with_declines(flat_values, flat_declines)
    if not has_meaningful_value(raw):
        return rental_property_values_with_declines(flat_values, flat_declines)
    raw_declines = rental_property_decline_values(raw)
    raw_has_context = any(rental_property_answer_context_value(key, value) for key, value in raw.items())
    merged = dict(flat_values)
    for key, value in raw.items():
        if has_meaningful_rental_property_override(key, value):
            merged[key] = value
        elif key not in merged and has_explicit_rental_property_evidence_gap(key, value):
            merged[key] = value
        elif key not in merged and rental_property_preserved_absence_value(key, value, raw_has_context):
            merged[key] = value
    return rental_property_values_with_declines(merged, {**flat_declines, **raw_declines})


def rental_property_rows(raw: Any) -> List[Dict[str, Any]]:
    if not has_rental_property_inputs(raw):
        return []
    if not isinstance(raw, dict):
        return []
    items = rental_property_item_values(raw.get("items"))
    evidence = rental_property_evidence_gaps(raw, items)
    review = rental_property_review_flags(raw, items)
    status = rental_property_status(evidence, review)
    answer = (
        f"Property {rental_property_field_text(raw, items, 'address')}; "
        f"owner {rental_property_field_text(raw, items, 'ownership')}; "
        f"income {rental_property_amount_field_text(raw, items, 'income')}; "
        f"interest {rental_property_amount_field_text(raw, items, 'interest')}; "
        f"repairs {rental_property_amount_field_text(raw, items, 'repairs')}; "
        f"capital works {rental_property_amount_field_text(raw, items, 'capital_works')}; "
        f"depreciation {rental_property_amount_field_text(raw, items, 'depreciation')}; "
        f"other expenses {rental_property_amount_field_text(raw, items, 'other_expenses')}; "
        f"private use {rental_property_field_text(raw, items, 'private_use')}; "
        f"private days {rental_property_amount_field_text(raw, items, 'private_use_days', money=False)}; "
        f"available days {rental_property_amount_field_text(raw, items, 'available_days', money=False)}; "
        f"records {rental_property_field_text(raw, items, 'records')}; "
        f"worksheet net {rental_property_net_text(raw, items)}"
    )
    item_text = rental_property_items_text(raw, items)
    if item_text:
        answer = f"{answer}; properties {item_text}"
    decline_text = rental_property_decline_signal_text(raw)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    return [
        guide_row(
            "RENTAL-PROPERTY",
            "Rental property worksheet",
            "Rental income, interest, repairs/capital, private use, depreciation, and net loss review",
            answer,
            "Rental property handling collects income, expenses, records, private-use apportionment, repairs versus capital indicators, depreciation, and net-loss flags for accountant review before entry.",
            status,
            ATO_RENTAL_PROPERTY_SOURCES,
            tab_text=rental_property_tab_text(evidence, review),
            row_kind="extended-section",
            facts=[
                *handoff_facts(
                    ("property", "Property", raw.get("address")),
                    ("ownership", "Ownership", raw.get("ownership")),
                    ("income", "Rental income", raw.get("income")),
                    ("interest", "Interest expense", raw.get("interest")),
                    ("repairs", "Repairs", raw.get("repairs")),
                    ("capital-works", "Capital works", raw.get("capital_works")),
                    ("depreciation", "Depreciation", raw.get("depreciation")),
                    ("other-expenses", "Other expenses", raw.get("other_expenses")),
                    ("private-use", "Private use", raw.get("private_use")),
                    ("private-days", "Private-use days", raw.get("private_use_days")),
                    ("available-days", "Available days", raw.get("available_days")),
                    ("records", "Records", raw.get("records")),
                    ("worksheet-net", "Prepared worksheet net", rental_property_net_text(raw, items)),
                    ("decline-signals", "Decline signals", decline_text or "none"),
                ),
                *indexed_item_handoff_facts("rental-item", "Rental property item", items),
            ],
        )
    ]


def rental_property_status(evidence: List[str], review: List[str]) -> str:
    if review:
        return "Accountant review"
    return "Evidence" if evidence else "Accountant review"


def has_meaningful_rental_property_flat_value(key: str, value: Any) -> bool:
    if key == "items":
        return bool(rental_property_item_values(value))
    if key == "net_loss" and rental_property_net_loss_false(value):
        return False
    if key in RENTAL_PROPERTY_AMOUNT_FIELDS and isinstance(value, bool):
        return key == "net_loss" and value is True
    if key in RENTAL_PROPERTY_SOURCE_KEY_FACTS and (
        rental_property_source_declines_workflow(key, value) or rental_property_field_absence_value(key, value)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def has_meaningful_rental_property_override(key: str, value: Any) -> bool:
    return has_meaningful_rental_property_flat_value(key, value)


def rental_property_answer_values(record: Dict[str, Any]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    has_context = any(rental_property_answer_context_value(key, value) for key, value in record.items())
    for key, value in record.items():
        if (
            has_meaningful_rental_property_flat_value(key, value)
            or has_explicit_rental_property_evidence_gap(key, value)
            or rental_property_preserved_absence_value(key, value, has_context)
        ):
            values[key] = value
    return values


def rental_property_answer_context_value(key: str, value: Any) -> bool:
    return has_meaningful_rental_property_flat_value(key, value) or has_explicit_rental_property_evidence_gap(key, value)


def rental_property_preserved_absence_value(key: str, value: Any, has_context: bool) -> bool:
    return has_context and key in RENTAL_PROPERTY_EXPENSE_FIELDS and rental_property_field_absence_value(key, value)


def has_explicit_rental_property_evidence_gap(key: str, value: Any) -> bool:
    if key == "net_loss" and rental_property_net_loss_false(value):
        return False
    if key in RENTAL_PROPERTY_SOURCE_KEY_FACTS and (
        rental_property_source_declines_workflow(key, value) or rental_property_field_absence_value(key, value)
    ):
        return False
    if key in RENTAL_PROPERTY_AMOUNT_FIELDS:
        return rental_property_amount_needs_evidence(value, key)
    if key in ("address", "ownership", "records", "private_use"):
        return has_meaningful_value(value) and contains_unknown(value)
    return False


def rental_property_values_with_declines(values: Dict[str, Any], declines: Dict[str, Any]) -> Dict[str, Any]:
    if not declines or not rental_property_has_facts(values):
        return values
    merged = dict(values)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        if not rental_property_has_field_value(merged, key):
            merged[key] = value
    merged[RENTAL_PROPERTY_DECLINE_SIGNAL_KEY] = signals
    return merged


def rental_property_decline_values(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key in RENTAL_PROPERTY_SOURCE_KEY_FACTS and rental_property_source_declines_workflow(key, value)
    }


def rental_property_item_values(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [item for item in raw_items if isinstance(item, dict) and rental_property_has_facts(item)]


def has_rental_property_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if rental_property_declines_without_facts(raw):
        return False
    return rental_property_has_facts(raw)


def rental_property_has_facts(record: Dict[str, Any]) -> bool:
    if rental_property_item_values(record.get("items")):
        return True
    return any(
        rental_property_has_signal(key, value) or has_explicit_rental_property_evidence_gap(key, value)
        for key, value in record.items()
        if key != "items"
        and key != RENTAL_PROPERTY_DECLINE_SIGNAL_KEY
        and not rental_property_source_declines_workflow(key, value)
        and not rental_property_field_absence_value(key, value)
    )


def rental_property_declines_without_facts(raw: Dict[str, Any]) -> bool:
    if not rental_property_decline_values(raw):
        return False
    return not rental_property_has_facts(raw)


def rental_property_has_signal(key: str, value: Any) -> bool:
    if key == "net_loss" and rental_property_net_loss_false(value):
        return False
    if key in RENTAL_PROPERTY_AMOUNT_FIELDS and isinstance(value, bool):
        return key == "net_loss" and value is True
    if key == "private_use" and rental_property_private_use_false(value):
        return False
    if key in RENTAL_PROPERTY_SOURCE_KEY_FACTS and (
        rental_property_source_declines_workflow(key, value) or rental_property_field_absence_value(key, value)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_value(value)


def rental_property_evidence_gaps(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> List[str]:
    evidence: List[str] = []
    if rental_property_decline_contradiction(raw, items):
        evidence.append("no-rental answer with rental facts")
    if rental_property_identity_needs_evidence(raw, items):
        evidence.append("property identity and ownership evidence")
    if rental_property_income_needs_evidence(raw, items):
        evidence.append("rental income evidence")
    if rental_property_records_evidence(raw, items):
        evidence.append("rental records")
    if rental_property_amounts_need_evidence(raw, items):
        evidence.append("numeric rental amount evidence")
    if rental_property_repair_classification_needs_evidence(raw, items):
        evidence.append("repairs versus capital classification")
    if rental_property_private_use_needs_evidence(raw, items):
        evidence.append("private-use apportionment evidence")
    if rental_property_amount_conflicts(raw, items):
        evidence.append("top-level and per-property amount reconciliation")
    if rental_property_net_loss_component_conflicts(raw, items):
        evidence.append("net-loss amount reconciliation")
    if any(rental_property_item_needs_evidence(raw, item) for item in items):
        evidence.append("per-property rental evidence")
    return evidence


def rental_property_review_flags(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> List[str]:
    flags: List[str] = []
    if rental_property_has_capital_or_depreciation(raw, items):
        flags.append("capital works or depreciation review")
    if rental_property_has_private_use(raw, items):
        flags.append("private-use review")
    if rental_property_has_net_loss(raw, items):
        flags.append("net rental loss review")
    if rental_property_has_repairs_and_capital(raw, items):
        flags.append("repairs versus capital review")
    return flags


def rental_property_identity_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    for key in ("address", "ownership"):
        if not rental_property_has_field_value(raw, key):
            if not any(rental_property_has_field_value(item, key) for item in items):
                return True
        elif contains_unknown(raw.get(key)):
            return True
    return any(contains_unknown(item.get(key)) for item in items for key in ("address", "ownership"))


def rental_property_income_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if items:
        return rental_property_items_income_need_evidence(items)
    if rental_property_has_field_value(raw, "income"):
        return rental_property_amount_needs_evidence(raw.get("income"), "income")
    return rental_property_has_facts(raw) or bool(items)


def rental_property_items_income_need_evidence(items: List[Dict[str, Any]]) -> bool:
    return any(rental_property_item_income_needs_evidence(item) for item in items)


def rental_property_item_income_needs_evidence(item: Dict[str, Any]) -> bool:
    if not rental_property_has_field_value(item, "income"):
        return True
    return rental_property_amount_needs_evidence(item.get("income"), "income")


def rental_property_items_income_partially_incomplete(items: List[Dict[str, Any]]) -> bool:
    if not items:
        return False
    complete = [not rental_property_item_income_needs_evidence(item) for item in items]
    return not all(complete)


def rental_property_records_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    records = raw.get("records")
    if has_meaningful_value(records) and rental_property_records_missing(records):
        return True
    if items:
        return any(rental_property_item_records_need_evidence(raw, item) for item in items)
    return not rental_property_has_field_value(raw, "records")


def rental_property_item_needs_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    return (
        rental_property_declines_with_facts(item)
        or any(rental_property_item_context_field_needs_evidence(raw, item, key) for key in ("address", "ownership"))
        or rental_property_item_records_need_evidence(raw, item)
        or any(rental_property_amount_needs_evidence(item.get(key), key) for key in RENTAL_PROPERTY_AMOUNT_FIELDS)
        or rental_property_private_use_needs_evidence(raw, [item])
        or rental_property_repair_classification_needs_evidence(item, [])
    )


def rental_property_item_context_field_needs_evidence(raw: Dict[str, Any], item: Dict[str, Any], key: str) -> bool:
    value = item.get(key)
    if not is_missing(value):
        return contains_unknown(value) or rental_property_field_absence_value(key, value)
    return not rental_property_has_field_value(raw, key)


def rental_property_item_records_need_evidence(raw: Dict[str, Any], item: Dict[str, Any]) -> bool:
    value = item.get("records")
    if not is_missing(value):
        return rental_property_records_missing(value) or rental_property_field_absence_value("records", value)
    return not rental_property_has_field_value(raw, "records")


def rental_property_amounts_need_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return (
        any(rental_property_amount_needs_evidence(raw.get(key), key) for key in RENTAL_PROPERTY_AMOUNT_FIELDS)
        or any(
            rental_property_amount_needs_evidence(item.get(key), key)
            for item in items
            for key in RENTAL_PROPERTY_AMOUNT_FIELDS
        )
        or rental_property_amount_conflicts(raw, items)
        or rental_property_net_loss_component_conflicts(raw, items)
        or rental_property_expense_amounts_incomplete(raw, items)
        or rental_property_any_explicit_net_component_amounts_need_evidence(raw, items)
    )


def rental_property_repair_classification_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return rental_property_repairs_are_ambiguous(raw.get("repairs")) or any(
        rental_property_repairs_are_ambiguous(item.get("repairs")) for item in items
    )


def rental_property_repairs_are_ambiguous(value: Any) -> bool:
    if not isinstance(value, str) or rental_property_field_absence_value("repairs", value):
        return False
    lowered = value.strip().lower()
    return any(term in lowered for term in ("renovation", "improvement", "capital", "replace", "replacement", "initial repair"))


def rental_property_private_use_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    records = [raw, *items]
    meaningful = [record for record in records if rental_property_has_facts(record)]
    if any(rental_property_private_use_conflict(record) for record in meaningful):
        return True
    if rental_property_private_use_summary_conflict(raw, items):
        return True
    if meaningful and not any(rental_property_has_field_value(record, "private_use") for record in meaningful):
        return True
    if any(rental_property_private_use_uncertain(record.get("private_use")) for record in meaningful):
        return True
    if any(rental_property_private_use_signal(record) for record in meaningful):
        return any(rental_property_apportionment_needs_evidence(record) for record in meaningful)
    return False


def rental_property_apportionment_needs_evidence(record: Dict[str, Any]) -> bool:
    if not rental_property_private_use_signal(record):
        return False
    private_days = rental_property_usable_amount_value(record.get("private_use_days"), "private_use_days")
    available_days = rental_property_usable_amount_value(record.get("available_days"), "available_days")
    if private_days is None or available_days is None:
        return True
    if rental_property_private_use_true(record.get("private_use")) and private_days <= 0:
        return True
    if available_days <= 0:
        return True
    return private_days > available_days


def rental_property_private_use_summary_conflict(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if rental_property_private_use_false(raw.get("private_use")):
        return any(rental_property_private_use_signal(item) for item in items)
    if rental_property_private_use_true(raw.get("private_use")) and items:
        item_private_use_values = [item for item in items if rental_property_has_field_value(item, "private_use")]
        return bool(item_private_use_values) and not any(rental_property_private_use_signal(item) for item in items)
    return False


def rental_property_has_capital_or_depreciation(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return any(
        (rental_property_amount_value(record.get("capital_works")) or 0) > 0
        or (rental_property_amount_value(record.get("depreciation")) or 0) > 0
        for record in [raw, *items]
    )


def rental_property_has_repairs_and_capital(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return any(
        (rental_property_amount_value(record.get("repairs")) or 0) > 0
        and (
            (rental_property_amount_value(record.get("capital_works")) or 0) > 0
            or (rental_property_amount_value(record.get("depreciation")) or 0) > 0
        )
        for record in [raw, *items]
    )


def rental_property_has_private_use(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return any(rental_property_private_use_signal(record) for record in [raw, *items])


def rental_property_has_net_loss(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    if any(rental_property_record_has_net_loss(record) for record in [raw, *items]):
        return True
    display_net = rental_property_display_net_amount(raw, items)
    if display_net is not None:
        return display_net < 0
    return False


def rental_property_record_has_net_loss(record: Dict[str, Any]) -> bool:
    explicit = rental_property_net_loss_amount_value(record.get("net_loss"))
    if explicit is not None and explicit < 0:
        return True
    net_amount = rental_property_net_amount(record)
    if net_amount is not None and net_amount < 0:
        return True
    return rental_property_net_loss_signal(record.get("net_loss"))


def rental_property_net_amount(record: Dict[str, Any]) -> Optional[float]:
    explicit = rental_property_net_loss_amount_value(record.get("net_loss"))
    if explicit is not None:
        if rental_property_component_amounts_need_evidence(record):
            return None
        return explicit
    income = rental_property_usable_amount_value(record.get("income"), "income")
    if income is None:
        return None
    if rental_property_record_expense_amounts_incomplete(record):
        return None
    expenses = [rental_property_usable_amount_value(record.get(key), key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS]
    known_expenses = [amount for amount in expenses if amount is not None]
    if not known_expenses:
        return income
    return round(income - sum(known_expenses), 2)


def rental_property_decline_contradiction(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return rental_property_declines_with_facts(raw) or any(rental_property_declines_with_facts(item) for item in items)


def rental_property_declines_with_facts(record: Dict[str, Any]) -> bool:
    if record.get(RENTAL_PROPERTY_DECLINE_SIGNAL_KEY):
        return True
    if not rental_property_decline_values(record):
        return False
    return rental_property_has_facts(record)


def rental_property_records_missing(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if is_missing(value) or contains_unknown(value):
        return True
    if rental_property_declines_workflow(value):
        return True
    lowered = text(value).strip().lower()
    if rental_property_no_loan_missing_record_answer(lowered):
        return True
    if rental_property_no_loan_records_answer(lowered):
        return False
    if rental_property_record_context(lowered) and lowered.startswith(("no ", "without ", "missing ")):
        return True
    if rental_property_record_context(lowered) and any(
        phrase in lowered for phrase in ("do not have", "don't have", "dont have", "not held", "not available", "not provided")
    ):
        return True
    return lowered in {"no", "n", "false", "none", "not held", "not available"}


def rental_property_record_context(lowered: str) -> bool:
    return any(term in lowered for term in ("record", "records", "statement", "invoice", "invoices", "agent", "loan", "interest"))


def rental_property_no_loan_records_answer(lowered: str) -> bool:
    no_loan = bool(re.search(r"\bno\W+(?:loan|mortgage|borrowing|borrowings)\b", lowered))
    records_held = any(term in lowered for term in ("agent statement", "records held", "invoice held"))
    return no_loan and records_held


def rental_property_no_loan_missing_record_answer(lowered: str) -> bool:
    return bool(
        re.search(
            r"\bno[\s-]+(?:loan|mortgage|borrowing|borrowings)[\s-]+"
            r"(?:statement|statements|record|records|invoice|invoices)\b",
            lowered,
        )
    )


def rental_property_declines_workflow(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if rental_property_record_context(lowered):
        return False
    if lowered in RENTAL_PROPERTY_DECLINE_PHRASES:
        return True
    if rental_property_decline_text_matches(lowered):
        return True
    return any(
        phrase in lowered
        for phrase in (
            "do not have rental property",
            "do not have a rental property",
            "don't have rental property",
            "don't have a rental property",
            "dont have rental property",
            "no rental income this year",
        )
    )


def rental_property_decline_text_matches(lowered: str) -> bool:
    return any(
        re.search(pattern, lowered)
        for pattern in (
            r"\b(?:do\W+not|don't|dont)\W+have\W+(?:a\W+|any\W+)?(?:rental|investment)\W+propert(?:y|ies)\b",
            r"\bhave\W+no\W+(?:a\W+|any\W+)?(?:rental|investment)\W+propert(?:y|ies)\b",
            r"\bhas\W+no\W+(?:a\W+|any\W+)?(?:rental|investment)\W+propert(?:y|ies)\b",
            r"\bno\W+(?:rental|investment)\W+propert(?:y|ies)(?:\W+this\W+year)?\b",
            r"\bnot\W+(?:a\W+)?landlord\b",
            r"\bno\W+rental\W+income(?:\W+this\W+year)?\b",
        )
    )


def rental_property_source_declines_workflow(key: str, value: Any) -> bool:
    if rental_property_field_absence_value(key, value):
        return False
    return rental_property_declines_workflow(value)


def rental_property_field_absence_value(key: str, value: Any) -> bool:
    if not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if key == "records" and rental_property_records_missing(value):
        return False
    if lowered in {"no rental", "no rental property", "no rental properties", "no investment property", "no investment properties"}:
        return False
    if key in {"interest", "repairs", "capital_works", "depreciation", "other_expenses", "private_use_days", "net_loss"} and lowered.startswith("no "):
        return not rental_property_amount_missing_document_text(lowered)
    return lowered in RENTAL_PROPERTY_FIELD_ABSENCE_PHRASES


def rental_property_amount_missing_document_text(lowered: str) -> bool:
    if not lowered.startswith(("no ", "without ", "missing ")):
        return False
    return any(
        term in lowered
        for term in (
            "document",
            "documents",
            "invoice",
            "invoices",
            "receipt",
            "receipts",
            "record",
            "records",
            "schedule",
            "schedules",
            "statement",
            "statements",
            "substantiation",
        )
    )


def rental_property_amount_missing_document_value(value: Any) -> bool:
    return isinstance(value, str) and rental_property_amount_missing_document_text(value.strip().lower())


def rental_property_has_field_value(record: Dict[str, Any], key: str) -> bool:
    value = record.get(key)
    if key == "net_loss" and rental_property_net_loss_false(value):
        return False
    if key in RENTAL_PROPERTY_AMOUNT_FIELDS and isinstance(value, bool):
        return key == "net_loss" and value is True
    return (
        has_meaningful_value(value)
        and not rental_property_source_declines_workflow(key, value)
        and not rental_property_field_absence_value(key, value)
    )


def rental_property_amount_needs_evidence(value: Any, key: str = "") -> bool:
    if is_missing(value):
        return False
    if key == "net_loss" and rental_property_net_loss_false(value):
        return False
    if rental_property_boolean_amount_evidence_gap(value, key):
        return True
    if isinstance(value, bool):
        return False
    if rental_property_declines_workflow(value) or rental_property_field_absence_value(key, value):
        return False
    return contains_unknown(value) or rental_property_amount_malformed(value, key)


def rental_property_boolean_amount_evidence_gap(value: Any, key: str = "") -> bool:
    return key in RENTAL_PROPERTY_AMOUNT_FIELDS and key != "net_loss" and value is True


def rental_property_amount_malformed(value: Any, key: str = "") -> bool:
    if isinstance(value, bool) or is_missing(value) or contains_unknown(value):
        return False
    if key == "net_loss" and rental_property_net_loss_false(value):
        return False
    if rental_property_field_absence_value(key, value):
        return False
    try:
        amount = money_value(value, unknown_as_missing=True)
    except ValueError:
        return True
    return amount is not None and amount < 0 and key != "net_loss"


def rental_property_amount_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


def rental_property_private_use_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value == 1
    if rental_property_private_use_uncertain(value):
        return False
    if rental_property_private_use_false(value):
        return False
    lowered = text(value).strip().lower()
    return lowered in {"true", "yes", "y", "1", "on", "checked", "private", "holiday home", "mixed use", "mixed-use"} or any(
        phrase in lowered for phrase in ("private use", "holiday home", "personal use")
    )


def rental_property_private_use_false(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value == 0
    if rental_property_private_use_uncertain(value):
        return False
    lowered = text(value).strip().lower()
    if lowered in {"false", "no", "n", "0", "off", "unchecked"}:
        return True
    return rental_property_private_use_negative_text(lowered)


def rental_property_private_use_uncertain(value: Any) -> bool:
    if contains_unknown(value):
        return True
    if not isinstance(value, str):
        return False
    lowered = value.strip().lower()
    return lowered in BOOLEAN_UNCERTAIN_PHRASES or any(phrase in lowered for phrase in BOOLEAN_UNCERTAIN_PHRASES)


def rental_property_private_use_negative_text(lowered: str) -> bool:
    if lowered in {"false", "no", "n", "0", "no private use", "no personal use", "not private"}:
        return True
    if any(
        phrase in lowered
        for phrase in (
            "not private use",
            "not for private use",
            "not personal use",
            "not for personal use",
            "no holiday home use",
            "no holiday-home use",
            "not a holiday home",
            "not holiday home",
        )
    ):
        return True
    return bool(
        re.search(
            r"\b(?:not|never|without)\b(?:\W+\w+){0,3}\W+(?:private use|personal use|holiday[- ]home(?: use)?)\b",
            lowered,
        )
        or re.search(r"\bno\W+(?:private use|personal use|holiday[- ]home(?: use)?)\b", lowered)
    )


def rental_property_private_use_signal(record: Dict[str, Any]) -> bool:
    return rental_property_private_use_true(record.get("private_use")) or rental_property_positive_private_use_days(record)


def rental_property_positive_private_use_days(record: Dict[str, Any]) -> bool:
    days = rental_property_usable_amount_value(record.get("private_use_days"), "private_use_days")
    return days is not None and days > 0


def rental_property_private_use_conflict(record: Dict[str, Any]) -> bool:
    return rental_property_private_use_false(record.get("private_use")) and rental_property_positive_private_use_days(record)


def rental_property_net_loss_signal(value: Any) -> bool:
    if rental_property_net_loss_false(value):
        return False
    if isinstance(value, bool):
        return value
    if contains_unknown(value):
        return False
    lowered = text(value).strip().lower()
    return "loss" in lowered and not rental_property_field_absence_value("net_loss", value)


def rental_property_net_loss_false(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value == 0
    if contains_unknown(value):
        return False
    lowered = text(value).strip().lower()
    return lowered in RENTAL_PROPERTY_NET_LOSS_FALSE_PHRASES or rental_property_net_loss_negative_text(lowered)


def rental_property_net_loss_negative_text(lowered: str) -> bool:
    return bool(
        re.search(r"\bno\W+(?:net\W+)?(?:rental\W+)?loss(?:es)?\b", lowered)
        or re.search(r"\bnot\W+(?:a\W+)?(?:net\W+)?(?:rental\W+)?loss\b", lowered)
        or re.search(r"\bwithout\W+(?:a\W+)?(?:net\W+)?(?:rental\W+)?loss\b", lowered)
        or re.search(r"\bprofit(?:able)?\b", lowered)
    )


def rental_property_field_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
    if key == "private_use" and rental_property_private_use_summary_conflict(raw, items):
        return "unknown"
    direct = rental_property_record_field_text(raw, key)
    if direct:
        return direct
    values = [value for item in items if (value := rental_property_record_field_text(item, key))]
    return ", ".join(values) if values else "unknown"


def rental_property_amount_field_text(
    raw: Dict[str, Any],
    items: List[Dict[str, Any]],
    key: str,
    money: bool = True,
) -> str:
    if rental_property_amount_missing_document_value(raw.get(key)):
        return display_value(raw.get(key))
    if key == "income" and rental_property_items_income_partially_incomplete(items):
        return "unknown"
    if rental_property_amount_conflict(raw, items, key):
        return "unknown"
    if rental_property_supplied_field_needs_evidence(raw, key):
        return rental_property_supplied_amount_text(raw.get(key))
    if rental_property_item_supplied_amount_needs_evidence(items, key):
        return "unknown"
    if rental_property_field_absence_value(key, raw.get(key)):
        return display_value(raw.get(key))
    direct = rental_property_usable_amount_value(raw.get(key), key)
    if direct is not None:
        return money_text(direct) if money else rental_property_number_text(direct)
    values = [rental_property_usable_amount_value(item.get(key), key) for item in items]
    real_values = [value for value in values if value is not None]
    if real_values:
        total = round(sum(real_values), 2)
        return money_text(total) if money else rental_property_number_text(total)
    return "unknown"


def rental_property_net_text(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    direct = rental_property_display_net_amount(raw, items)
    if direct is not None:
        return money_text(direct)
    return "unknown"


def rental_property_display_net_amount(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> Optional[float]:
    if rental_property_amount_conflict(raw, items, "net_loss"):
        return None
    if rental_property_net_loss_component_conflicts(raw, items):
        return None
    explicit = rental_property_net_loss_amount_value(raw.get("net_loss"))
    if explicit is not None:
        if rental_property_component_amounts_need_evidence(raw):
            return None
        return explicit
    if rental_property_supplied_amount_needs_evidence(raw, items, "net_loss"):
        return None
    item_explicit_net_values = [rental_property_net_loss_amount_value(item.get("net_loss")) for item in items]
    real_item_explicit_net_values = [value for value in item_explicit_net_values if value is not None]
    if real_item_explicit_net_values:
        if rental_property_item_amounts_need_evidence(items):
            return None
        if len(real_item_explicit_net_values) == len(items):
            return round(sum(real_item_explicit_net_values), 2)
        if rental_property_private_use_expense_apportionment_blocks_net(raw, items):
            return None
        item_net_values = [rental_property_net_amount(item) for item in items]
        real_item_net_values = [value for value in item_net_values if value is not None]
        if len(real_item_net_values) == len(items):
            return round(sum(real_item_net_values), 2)
        return None
    if rental_property_private_use_expense_apportionment_blocks_net(raw, items):
        return None
    if rental_property_supplied_amount_needs_evidence(raw, items, "income"):
        return None
    income = rental_property_display_amount_value(raw, items, "income")
    if income is None:
        return None
    if rental_property_expense_amounts_incomplete(raw, items):
        return None
    if any(rental_property_supplied_amount_needs_evidence(raw, items, key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS):
        return None
    expenses = [rental_property_display_amount_value(raw, items, key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS]
    known_expenses = [amount for amount in expenses if amount is not None]
    if not known_expenses:
        return income
    return round(income - sum(known_expenses), 2)


def rental_property_supplied_amount_text(value: Any) -> str:
    if contains_unknown(value) or rental_property_amount_missing_document_value(value):
        return display_value(value)
    return "unknown"


def rental_property_private_use_expense_apportionment_blocks_net(
    raw: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> bool:
    if not rental_property_has_private_use(raw, items):
        return False
    expense_values = [rental_property_display_amount_value(raw, items, key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS]
    return any(amount is not None and amount > 0 for amount in expense_values)


def rental_property_display_amount_value(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> Optional[float]:
    if key == "income" and rental_property_items_income_partially_incomplete(items):
        return None
    if rental_property_amount_conflict(raw, items, key):
        return None
    if rental_property_supplied_field_needs_evidence(raw, key):
        return None
    if rental_property_item_supplied_amount_needs_evidence(items, key):
        return None
    direct = rental_property_usable_amount_value(raw.get(key), key)
    if direct is not None:
        return direct
    values = [rental_property_usable_amount_value(item.get(key), key) for item in items]
    real_values = [value for value in values if value is not None]
    return round(sum(real_values), 2) if real_values else None


def rental_property_supplied_amount_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> bool:
    return (
        (key == "income" and rental_property_items_income_partially_incomplete(items))
        or rental_property_supplied_field_needs_evidence(raw, key)
        or rental_property_item_supplied_amount_needs_evidence(items, key)
        or rental_property_amount_conflict(raw, items, key)
    )


def rental_property_item_supplied_amount_needs_evidence(items: List[Dict[str, Any]], key: str) -> bool:
    return any(rental_property_supplied_field_needs_evidence(item, key) for item in items)


def rental_property_item_amounts_need_evidence(items: List[Dict[str, Any]]) -> bool:
    return any(
        rental_property_supplied_field_needs_evidence(item, key)
        for item in items
        for key in RENTAL_PROPERTY_AMOUNT_FIELDS
    ) or any(
        rental_property_record_requires_expense_resolution(item)
        and rental_property_record_expense_amounts_incomplete(item)
        for item in items
    ) or any(
        rental_property_explicit_net_component_amounts_need_evidence(item)
        for item in items
    )


def rental_property_expense_amounts_incomplete(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    records = items if items else [raw]
    return any(
        rental_property_record_requires_expense_resolution(record)
        and rental_property_record_expense_amounts_incomplete(record)
        for record in records
    )


def rental_property_record_requires_expense_resolution(record: Dict[str, Any]) -> bool:
    return (
        rental_property_usable_amount_value(record.get("income"), "income") is not None
        and rental_property_net_loss_amount_value(record.get("net_loss")) is None
    )


def rental_property_any_explicit_net_component_amounts_need_evidence(
    raw: Dict[str, Any],
    items: List[Dict[str, Any]],
) -> bool:
    return any(rental_property_explicit_net_component_amounts_need_evidence(record) for record in [raw, *items])


def rental_property_explicit_net_component_amounts_need_evidence(record: Dict[str, Any]) -> bool:
    return (
        rental_property_net_loss_amount_value(record.get("net_loss")) is not None
        and rental_property_component_amounts_need_evidence(record)
    )


def rental_property_component_amounts_need_evidence(record: Dict[str, Any]) -> bool:
    if not rental_property_has_component_amounts(record):
        return False
    if rental_property_supplied_field_needs_evidence(record, "income"):
        return True
    if rental_property_usable_amount_value(record.get("income"), "income") is None:
        return True
    return rental_property_record_expense_amounts_incomplete(record)


def rental_property_has_component_amounts(record: Dict[str, Any]) -> bool:
    return any(key in record for key in ("income", *RENTAL_PROPERTY_EXPENSE_FIELDS))


def rental_property_record_expense_amounts_incomplete(record: Dict[str, Any]) -> bool:
    return any(not rental_property_expense_field_resolved(record, key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS)


def rental_property_expense_field_resolved(record: Dict[str, Any], key: str) -> bool:
    if key not in record:
        return False
    value = record.get(key)
    if rental_property_field_absence_value(key, value):
        return True
    return rental_property_usable_amount_value(value, key) is not None


def rental_property_supplied_field_needs_evidence(record: Dict[str, Any], key: str) -> bool:
    if key not in record:
        return False
    value = record.get(key)
    if key == "net_loss" and rental_property_net_loss_false(value):
        return False
    if rental_property_field_absence_value(key, value):
        return False
    return rental_property_amount_needs_evidence(value, key)


def rental_property_usable_amount_value(value: Any, key: str) -> Optional[float]:
    if rental_property_amount_needs_evidence(value, key):
        return None
    if rental_property_zero_amount_absence_value(value, key):
        return 0.0
    return rental_property_amount_value(value)


def rental_property_amount_conflicts(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return any(rental_property_amount_conflict(raw, items, key) for key in RENTAL_PROPERTY_AMOUNT_FIELDS)


def rental_property_net_loss_component_conflicts(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return rental_property_record_net_loss_component_conflict(raw) or any(
        rental_property_record_net_loss_component_conflict(item) for item in items
    )


def rental_property_record_net_loss_component_conflict(record: Dict[str, Any]) -> bool:
    explicit = rental_property_net_loss_amount_value(record.get("net_loss"))
    if explicit is None:
        return False
    component_net = rental_property_component_net_amount(record)
    return component_net is not None and round(component_net, 2) != round(explicit, 2)


def rental_property_component_net_amount(record: Dict[str, Any]) -> Optional[float]:
    income = rental_property_usable_amount_value(record.get("income"), "income")
    if income is None:
        return None
    if rental_property_record_expense_amounts_incomplete(record):
        return None
    expenses = [rental_property_usable_amount_value(record.get(key), key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS]
    known_expenses = [amount for amount in expenses if amount is not None]
    if not known_expenses:
        return None
    return round(income - sum(known_expenses), 2)


def rental_property_amount_conflict(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> bool:
    direct = rental_property_reconciliation_amount_value(raw.get(key), key)
    if direct is None:
        return False
    item_values = rental_property_reconciliation_item_amount_values(items, key)
    real_item_values = [value for value in item_values if value is not None]
    if key == "net_loss" and items and len(real_item_values) != len(items):
        return True
    if not real_item_values:
        return False
    item_total = round(sum(real_item_values), 2)
    return round(direct, 2) != item_total


def rental_property_reconciliation_item_amount_values(items: List[Dict[str, Any]], key: str) -> List[Optional[float]]:
    if key == "net_loss":
        return [rental_property_item_net_loss_reconciliation_value(item) for item in items]
    return [rental_property_reconciliation_amount_value(item.get(key), key) for item in items]


def rental_property_item_net_loss_reconciliation_value(item: Dict[str, Any]) -> Optional[float]:
    explicit = rental_property_net_loss_amount_value(item.get("net_loss"))
    if explicit is not None:
        return explicit
    return rental_property_net_amount(item)


def rental_property_reconciliation_amount_value(value: Any, key: str) -> Optional[float]:
    if rental_property_zero_amount_absence_value(value, key):
        return 0.0
    if key == "net_loss":
        return rental_property_net_loss_amount_value(value)
    return rental_property_usable_amount_value(value, key)


def rental_property_zero_amount_absence_value(value: Any, key: str) -> bool:
    return key in RENTAL_PROPERTY_EXPENSE_FIELDS and rental_property_field_absence_value(key, value)


def rental_property_net_loss_amount_value(value: Any) -> Optional[float]:
    if rental_property_net_loss_false(value):
        return None
    amount = rental_property_amount_value(value)
    if amount is None:
        return None
    return -amount if amount > 0 else amount


def rental_property_items_text(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    details: List[str] = []
    for idx, item in enumerate(items, start=1):
        label = rental_property_record_field_text(item, "address") or f"property {idx}"
        details.append(
            f"{label}: owner {rental_property_item_text_or_inherited(raw, item, 'ownership')}, "
            f"income {rental_property_item_amount_text(item, 'income')}, "
            f"interest {rental_property_item_amount_text(item, 'interest')}, "
            f"repairs {rental_property_item_amount_text(item, 'repairs')}, "
            f"capital works {rental_property_item_amount_text(item, 'capital_works')}, "
            f"depreciation {rental_property_item_amount_text(item, 'depreciation')}, "
            f"other expenses {rental_property_item_amount_text(item, 'other_expenses')}, "
            f"private days {rental_property_item_amount_text(item, 'private_use_days', money=False)}, "
            f"available days {rental_property_item_amount_text(item, 'available_days', money=False)}, "
            f"net loss {rental_property_item_net_loss_text(item)}, "
            f"private use {rental_property_item_private_use_text(raw, item)}, "
            f"records {rental_property_item_text_or_inherited(raw, item, 'records')}"
        )
    return " | ".join(details)


def rental_property_item_amount_text(item: Dict[str, Any], key: str, money: bool = True) -> str:
    value = item.get(key)
    if rental_property_amount_missing_document_value(value):
        return display_value(value)
    if rental_property_field_absence_value(key, value):
        return display_value(value)
    amount = rental_property_usable_amount_value(value, key)
    return money_text(amount) if money else rental_property_number_text(amount)


def rental_property_item_net_loss_text(item: Dict[str, Any]) -> str:
    value = item.get("net_loss")
    amount = rental_property_net_loss_amount_value(value)
    if amount is not None:
        return money_text(amount)
    if rental_property_net_loss_false(value):
        return "none"
    if rental_property_net_loss_signal(value) or rental_property_amount_needs_evidence(value, "net_loss"):
        return display_value(value)
    return "unknown"


def rental_property_item_private_use_text(raw: Dict[str, Any], item: Dict[str, Any]) -> str:
    if rental_property_private_use_conflict(item):
        return "unknown"
    value = rental_property_record_field_text(item, "private_use")
    if value:
        return value
    if rental_property_private_use_signal(item):
        return "true"
    value = rental_property_record_field_text(raw, "private_use")
    return value if value else "unknown"


def rental_property_item_text_or_inherited(raw: Dict[str, Any], item: Dict[str, Any], key: str) -> str:
    value = rental_property_record_field_text(item, key)
    if value:
        return value
    value = rental_property_record_field_text(raw, key)
    return value if value else "unknown"


def rental_property_text_or_unknown(record: Dict[str, Any], key: str) -> str:
    value = rental_property_record_field_text(record, key)
    return value if value != "" else "unknown"


def rental_property_record_field_text(record: Dict[str, Any], key: str) -> str:
    if rental_property_field_absence_value(key, record.get(key)):
        return ""
    return display_value(record.get(key))


def rental_property_decline_signal_text(raw: Dict[str, Any]) -> str:
    signals = raw.get(RENTAL_PROPERTY_DECLINE_SIGNAL_KEY)
    if not isinstance(signals, list):
        return ""
    return ", ".join(display_value(signal) for signal in signals if display_value(signal))


def rental_property_number_text(value: Optional[float]) -> str:
    return "unknown" if value is None else f"{value:.8g}"


def rental_property_tab_text(evidence: List[str], review: List[str]) -> str:
    if evidence and review:
        return (
            f"Rental property worksheet needs {', '.join(evidence)} and stays accountant review for "
            f"{', '.join(review)} before entry."
        )
    if evidence:
        return f"Rental property worksheet needs {', '.join(evidence)} before accountant review."
    if review:
        return f"Rental property worksheet requires accountant review before entry because of {', '.join(review)}."
    return "Rental property worksheet requires accountant review before entry."


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
    flat_values = {key: value for key, value in fields.items() if has_meaningful_ess_flat_value(key, value)}
    flat_declines = ess_decline_values(fields)
    if not isinstance(raw, dict):
        return ess_values_with_declines(flat_values, flat_declines)
    if not has_meaningful_value(raw):
        return ess_values_with_declines(flat_values, flat_declines)
    raw_declines = ess_decline_values(raw)
    merged = dict(flat_values)
    for key, value in raw.items():
        if has_meaningful_ess_override(key, value):
            merged[key] = value
        elif key not in merged and has_explicit_ess_evidence_gap(key, value):
            merged[key] = value
    return ess_values_with_declines(merged, {**flat_declines, **raw_declines})


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
    decline_evidence = ess_decline_contradiction(raw, items)
    status = "Evidence" if statement_evidence or amount_conflict or amount_evidence or decline_evidence else "Accountant review"
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
    decline_text = ess_decline_signal_text(raw, items)
    if decline_text:
        answer = f"{answer}; decline signals {decline_text}"
    tab_text = ess_tab_text(statement_evidence, amount_conflict, amount_evidence, decline_evidence)
    return [
        guide_row(
            "ESS",
            "Employee share schemes",
            "ESS statement and discount workflow",
            answer,
            "ESS discounts need the ESS statement, deferred taxing-point timing, foreign-source split, and label mapping reviewed before entry.",
            status,
            [ATO_ESS_SOURCE, ATO_ESS_STATEMENT_SOURCE],
            tab_text=tab_text,
            row_kind="extended-section",
            facts=[
                *handoff_facts(
                    ("employer", "Employer", raw.get("employer")),
                    ("provider", "Provider", raw.get("provider")),
                    ("scheme", "Scheme", raw.get("scheme")),
                    ("taxed-upfront-discount", "Prepared taxed-upfront discount total", taxed_upfront),
                    ("deferred-discount", "Prepared deferred discount total", deferred),
                    ("foreign-source-discount", "Prepared foreign-source discount total", foreign_source),
                    ("tfn-withheld", "Prepared TFN amount withheld total", tfn_withheld),
                    ("statement", "ESS statement", raw.get("statement")),
                    ("decline-signals", "Decline signals", decline_text or "none"),
                ),
                *indexed_item_handoff_facts("ess-item", "ESS item", items),
            ],
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
    if key in ESS_SOURCE_KEY_FACTS and (
        ess_source_declines_workflow(key, value) or ess_field_absence_value(key, value)
    ):
        return False
    if contains_unknown(value):
        return False
    return has_meaningful_ess_value(value)


def has_meaningful_ess_flat_value(key: str, value: Any) -> bool:
    if key in ESS_FLAT_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    source_key = key.removeprefix("ess_")
    if source_key in ESS_SOURCE_KEY_FACTS and (
        ess_source_declines_workflow(source_key, value) or ess_field_absence_value(source_key, value)
    ):
        return False
    return has_meaningful_value(value)


def has_meaningful_ess_override(key: str, value: Any) -> bool:
    if key == "items":
        return bool(ess_item_values(value))
    if not has_meaningful_value(value) or contains_unknown(value):
        return False
    if key in ESS_SOURCE_KEY_FACTS and (
        ess_source_declines_workflow(key, value) or ess_field_absence_value(key, value)
    ):
        return False
    if key in ESS_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    return True


def has_explicit_ess_evidence_gap(key: str, value: Any) -> bool:
    if key in ESS_SOURCE_KEY_FACTS and (
        ess_source_declines_workflow(key, value) or ess_field_absence_value(key, value)
    ):
        return False
    if key not in ("statement", *ESS_AMOUNT_FIELDS):
        return False
    if key in ESS_AMOUNT_FIELDS and isinstance(value, bool):
        return False
    return has_meaningful_value(value) and contains_unknown(value)


def ess_values_with_declines(values: Dict[str, Any], declines: Dict[str, Any]) -> Dict[str, Any]:
    if not declines or not ess_has_facts(values):
        return values
    merged = dict(values)
    signals: List[str] = []
    for key, value in declines.items():
        signals.append(f"{key} {display_value(value)}")
        if not has_meaningful_ess_signal(key, merged.get(key)):
            merged[key] = value
    merged[ESS_DECLINE_SIGNAL_KEY] = signals
    return merged


def ess_decline_values(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key.removeprefix("ess_"): value
        for key, value in record.items()
        if key.removeprefix("ess_") in ESS_SOURCE_KEY_FACTS
        and ess_source_declines_workflow(key.removeprefix("ess_"), value)
    }


def ess_has_facts(record: Dict[str, Any]) -> bool:
    if ess_item_values(record.get("items")):
        return True
    return any(
        has_meaningful_ess_signal(key, value) or has_explicit_ess_evidence_gap(key, value)
        for key, value in record.items()
        if key not in ("items", ESS_DECLINE_SIGNAL_KEY)
        and not ess_source_declines_workflow(key, value)
        and not ess_field_absence_value(key, value)
    )


def ess_amount_value(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> Optional[float]:
    item_total = ess_item_amount_total(items, key)
    if item_total is not None:
        return item_total
    return ess_money_value(raw.get(key))


def ess_item_amount_total(items: List[Dict[str, Any]], key: str) -> Optional[float]:
    item_amounts = [ess_money_value(item.get(key)) for item in items if key in item and not is_missing(item.get(key))]
    if not item_amounts or any(amount is None for amount in item_amounts):
        return None
    return round(sum(item_amounts), 2)


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


def ess_tab_text(
    statement_evidence: bool,
    amount_conflict: bool,
    amount_evidence: bool,
    decline_evidence: bool = False,
) -> str:
    if decline_evidence:
        evidence = ["no-ESS answer with ESS facts"]
        if amount_conflict:
            evidence.append("corrected amount totals")
        if statement_evidence:
            evidence.append("ESS statement evidence")
        if amount_evidence:
            evidence.append("numeric amount evidence")
        return f"ESS discounts need {', '.join(evidence)} before accountant review."
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


def ess_decline_contradiction(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return ess_declines_with_facts(raw) or any(ess_declines_with_facts(item) for item in items)


def ess_declines_with_facts(record: Dict[str, Any]) -> bool:
    if record.get(ESS_DECLINE_SIGNAL_KEY):
        return True
    if not ess_decline_values(record):
        return False
    return ess_has_facts(record)


def ess_decline_signal_text(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    signals = raw.get(ESS_DECLINE_SIGNAL_KEY)
    values = [display_value(signal) for signal in signals if display_value(signal)] if isinstance(signals, list) else []
    for idx, item in enumerate(items, start=1):
        values.extend(
            f"item {idx} {key} {display_value(value)}"
            for key, value in ess_decline_values(item).items()
            if display_value(value)
        )
    return ", ".join(values)


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
    return ess_display_text(raw, "employer") or ess_display_text(raw, "scheme") or ess_display_text(raw, "provider")


def ess_display_text(raw: Dict[str, Any], key: str) -> str:
    if ess_field_absence_value(key, raw.get(key)):
        return ""
    return display_value(raw.get(key))


def has_ess_inputs(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    if ess_declines_without_facts(raw):
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


def ess_declines_without_facts(raw: Dict[str, Any]) -> bool:
    if not ess_decline_values(raw):
        return False
    return not ess_has_facts(raw)


def ess_statement_declines_workflow(statement: Any) -> bool:
    if not isinstance(statement, str):
        return False
    lowered = statement.strip().lower()
    return lowered in ESS_DECLINE_PHRASES


def ess_source_declines_workflow(key: str, value: Any) -> bool:
    if ess_field_absence_value(key, value):
        return False
    return ess_statement_declines_workflow(value)


def ess_field_absence_value(key: str, value: Any) -> bool:
    if key == "statement" or not isinstance(value, str) or contains_unknown(value):
        return False
    lowered = value.strip().lower()
    if lowered in {"no ess", "no employee share scheme", "no employee share schemes"}:
        return False
    return lowered in GENERIC_FIELD_ABSENCE_PHRASES


def has_meaningful_ess_value(value: Any) -> bool:
    return has_meaningful_value(value)


PARTNERSHIP_TRUST_ITEM_ALIASES = {
    "partnership": (
        "partnership_share_items",
        "partnership_statement_items",
        "partnership_shares",
    ),
    "trust": (
        "trust_share_items",
        "trust_beneficiary_statement_items",
        "trust_beneficiary_share_items",
    ),
}
PARTNERSHIP_TRUST_FLAT_FIELDS = {
    "partnership": {
        "entity_name": ("partnership_entity_name", "partnership_name", "partnership"),
        "abn": ("partnership_abn",),
        "tfn": ("partnership_tfn",),
        "statement": ("partnership_statement", "partnership_statement_status"),
        "income": ("partnership_income", "partnership_share_income"),
        "loss": ("partnership_loss", "partnership_share_loss"),
        "tax_withheld": ("partnership_tax_withheld",),
        "credits": ("partnership_credits",),
        "entity_return_context": ("partnership_entity_return_context",),
    },
    "trust": {
        "entity_name": (
            "trust_share_entity_name",
            "trust_beneficiary_entity_name",
            "trust_name",
            "trust",
        ),
        "abn": ("trust_share_abn", "trust_beneficiary_abn"),
        "tfn": ("trust_share_tfn", "trust_beneficiary_tfn"),
        "statement": (
            "trust_share_statement", "trust_share_statement_status",
            "trust_beneficiary_statement", "trust_beneficiary_statement_status",
        ),
        "income": ("trust_share_income", "trust_beneficiary_income"),
        "loss": ("trust_share_loss", "trust_beneficiary_loss"),
        "tax_withheld": ("trust_share_tax_withheld", "trust_beneficiary_tax_withheld"),
        "credits": ("trust_share_credits", "trust_beneficiary_credits"),
        "entity_return_context": ("trust_entity_return_context", "trust_beneficiary_entity_return_context"),
    },
}
PARTNERSHIP_TRUST_FLAT_METADATA_ALIASES = {
    "partnership": {
        "source_url": ("partnership_source_url", "partnership_share_source_url"),
        "source_urls": ("partnership_source_urls", "partnership_share_source_urls"),
        "checked_at": ("partnership_checked_at", "partnership_share_checked_at"),
        "source_checked_at": ("partnership_source_checked_at", "partnership_share_source_checked_at"),
        "status": ("partnership_status", "partnership_share_status"),
        "evidence_status": ("partnership_evidence_status", "partnership_share_evidence_status"),
        "mixed_components": ("partnership_mixed_components", "partnership_share_mixed_components"),
    },
    "trust": {
        "source_url": ("trust_source_url", "trust_share_source_url", "trust_beneficiary_source_url"),
        "source_urls": ("trust_source_urls", "trust_share_source_urls", "trust_beneficiary_source_urls"),
        "checked_at": ("trust_checked_at", "trust_share_checked_at", "trust_beneficiary_checked_at"),
        "source_checked_at": (
            "trust_source_checked_at", "trust_share_source_checked_at", "trust_beneficiary_source_checked_at",
        ),
        "status": ("trust_status", "trust_share_status", "trust_beneficiary_status"),
        "evidence_status": (
            "trust_evidence_status", "trust_share_evidence_status", "trust_beneficiary_evidence_status",
        ),
        "mixed_components": (
            "trust_mixed_components", "trust_share_mixed_components", "trust_beneficiary_mixed_components",
        ),
    },
}
PARTNERSHIP_TRUST_AMOUNT_FIELDS = (
    "income",
    "income_amount",
    "income_components",
    "loss",
    "loss_amount",
    "loss_components",
    "tax_withheld",
    "withholding",
    "credits",
)
PARTNERSHIP_TRUST_ROW_SIGNAL_FIELDS = frozenset(
    {"statement", "statement_status", "evidence", *PARTNERSHIP_TRUST_AMOUNT_FIELDS}
)


def partnership_trust_share_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    counts = {"partnership": 0, "trust": 0}
    for kind, item in partnership_trust_share_items(answers):
        counts[kind] += 1
        evidence_gap = partnership_trust_evidence_gap(item)
        status = review_first_status(item, evidence_gap)
        label = "Partnership share statement" if kind == "partnership" else "Trust beneficiary/share statement"
        answer = partnership_trust_answer(kind, item)
        sources = [ATO_PARTNERSHIP_TRUST_INCOME_SOURCE, *supplied_source_urls(item)]
        rows.append(
            guide_row(
                f"{'PART' if kind == 'partnership' else 'TRUST'}-SHARE-{counts[kind]}",
                "13 Partnerships and trusts",
                f"{label} routing for individual return",
                answer,
                "Individual statement facts stay prep-only. Allocation, entitlement, losses, credits, mixed components, and entity-return work require accountant review; full entity returns belong to #42/#43.",
                status,
                list(dict.fromkeys(sources)),
                tab_text=(
                    f"{label} needs statement and numeric evidence before accountant review."
                    if evidence_gap and status == "Evidence"
                    else f"{label} needs accountant review; no allocation or entitlement is decided."
                ),
                row_kind="supplementary-income",
                facts=routing_handoff_facts(f"{kind}-share", f"{label} fact", item),
                checked_at=supplied_checked_at(item),
            )
        )
    return rows


def partnership_trust_share_items(answers: Dict[str, Any]) -> List[tuple[str, Dict[str, Any]]]:
    records: List[tuple[str, Dict[str, Any]]] = []
    containers = [answers]
    for key in ("individual_income", "supplementary_income"):
        nested = answers.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    for kind, aliases in PARTNERSHIP_TRUST_ITEM_ALIASES.items():
        for container in containers:
            container_items: List[Dict[str, Any]] = []
            empty_dict_alias = ""
            for alias in aliases:
                if alias not in container:
                    continue
                value = container.get(alias)
                if has_meaningful_value(value):
                    container_items.extend(structured_income_items(value, alias))
                elif isinstance(value, dict) and not value and not empty_dict_alias:
                    empty_dict_alias = alias
            if not container_items and empty_dict_alias:
                container_items.extend(structured_income_items({}, empty_dict_alias))
            container_items = [normalize_partnership_trust_structured_item(kind, item) for item in container_items]
            flat_item = partnership_trust_flat_item(container, kind)
            flat_substantive = partnership_trust_flat_has_substantive_facts(flat_item)
            if flat_item and flat_substantive:
                container_items = [item for item in container_items if item.get("_empty_placeholder") is not True]
            if container_items and flat_item:
                if len(container_items) == 1:
                    merged = merge_partnership_trust_complements(kind, container_items[0], flat_item)
                    if merged is not None:
                        container_items = [merged]
                        flat_item = {}
                elif flat_substantive:
                    flat_item.setdefault("alias_conflicts", {})["structured_row_assignment"] = [
                        "Flat identity cannot be assigned across multiple statement rows"
                    ]
                    container_items.append(flat_item)
                    flat_item = {}
            records.extend((kind, item) for item in container_items)
            if flat_item and partnership_trust_flat_has_substantive_facts(flat_item):
                records.append((kind, flat_item))
            elif flat_item:
                records.append((kind, {**flat_item, "_metadata_only": True}))
    return coalesce_partnership_trust_records(records)


def coalesce_partnership_trust_records(
    records: List[tuple[str, Dict[str, Any]]],
) -> List[tuple[str, Dict[str, Any]]]:
    coalesced: List[tuple[str, Dict[str, Any]]] = []
    for kind, item in records:
        compatible: List[tuple[int, Dict[str, Any]]] = []
        for index, (existing_kind, existing) in enumerate(coalesced):
            if existing_kind != kind:
                continue
            merged = merge_partnership_trust_complements(kind, existing, item)
            if merged is not None:
                compatible.append((index, merged))
        if len(compatible) == 1:
            index, merged = compatible[0]
            coalesced[index] = (kind, merged)
        elif item.get("_metadata_only") is not True:
            coalesced.append((kind, item))
    return [
        (kind, {key: value for key, value in item.items() if key != "_metadata_only"})
        for kind, item in coalesced
    ]


PARTNERSHIP_TRUST_MERGE_GROUPS = {
    "entity_name": ("entity_name", "partnership", "trust", "name"),
    "abn": ("abn",),
    "tfn": ("tfn",),
    "statement": ("statement", "statement_status", "evidence"),
    "income": ("income", "income_amount"),
    "loss": ("loss", "loss_amount"),
    "tax_withheld": ("tax_withheld", "withholding"),
    "credits": ("credits",),
    "entity_return_context": ("entity_return_context",),
    "mixed_components": ("mixed_components",),
}


def merge_partnership_trust_complements(
    kind: str,
    structured: Dict[str, Any],
    flat: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if structured.get("_malformed") is True:
        return None
    identity_groups = ("entity_name", "abn", "tfn")
    if not any(
        has_meaningful_value(first_meaningful_present(item, PARTNERSHIP_TRUST_MERGE_GROUPS[group]))
        for item in (structured, flat)
        for group in identity_groups
    ):
        return None
    for group in identity_groups:
        left = first_meaningful_present(structured, PARTNERSHIP_TRUST_MERGE_GROUPS[group])
        right = first_meaningful_present(flat, PARTNERSHIP_TRUST_MERGE_GROUPS[group])
        if has_meaningful_value(left) and has_meaningful_value(right) and not income_alias_values_equivalent(left, right):
            return None
    if partnership_trust_item_complete(kind, structured) and partnership_trust_item_complete(kind, flat):
        return None

    merged = dict(structured)
    conflicts: Dict[str, Any] = {}
    for item in (structured, flat):
        existing = item.get("alias_conflicts")
        if isinstance(existing, dict):
            conflicts.update(existing)
    handled = {alias for aliases in PARTNERSHIP_TRUST_MERGE_GROUPS.values() for alias in aliases}
    for canonical, aliases in PARTNERSHIP_TRUST_MERGE_GROUPS.items():
        left = first_meaningful_present(structured, aliases)
        right = first_meaningful_present(flat, aliases)
        if not has_meaningful_value(left) and has_meaningful_value(right):
            merged[canonical] = right
        elif has_meaningful_value(left) and has_meaningful_value(right) and not income_alias_values_equivalent(left, right):
            conflicts[f"structured_flat_{canonical}"] = [left, right]

    merged_sources, invalid_sources = source_provenance_values(
        [
            structured.get("source_url"), structured.get("source_urls"),
            flat.get("source_url"), flat.get("source_urls"),
        ]
    )
    if merged_sources:
        merged["source_urls"] = merged_sources
    if invalid_sources:
        merged["unresolved_source_provenance"] = list(dict.fromkeys(map(display_value, invalid_sources)))
    checked_values, invalid_checked = checked_at_provenance_values(
        [
            structured.get("checked_at"), structured.get("source_checked_at"),
            flat.get("checked_at"), flat.get("source_checked_at"),
        ]
    )
    if checked_values:
        merged["checked_at"] = checked_values[0]
        if len(set(checked_values)) > 1:
            conflicts["structured_flat_checked_at"] = checked_values
    if invalid_checked:
        merged["unresolved_checked_at_provenance"] = list(dict.fromkeys(map(display_value, invalid_checked)))
    status_values = [item.get("status") for item in (structured, flat) if has_meaningful_value(item.get("status"))]
    if status_values:
        merged["status"] = canonical_review_status(status_values)
    for key, value in flat.items():
        if key in handled or key in {
            "_metadata_only", "alias_conflicts", "source_url", "source_urls",
            "checked_at", "source_checked_at", "status",
        }:
            continue
        if not has_meaningful_value(merged.get(key)):
            merged[key] = value
        elif has_meaningful_value(value) and not income_alias_values_equivalent(merged.get(key), value):
            conflicts[f"structured_flat_{key}"] = [merged.get(key), value]
    if conflicts:
        merged["alias_conflicts"] = conflicts
    return merged


def partnership_trust_item_complete(kind: str, item: Dict[str, Any]) -> bool:
    identity = first_meaningful_present(item, ("entity_name", kind, "name", "abn", "tfn"))
    statement = first_meaningful_present(item, ("statement", "statement_status", "evidence"))
    amounts = [item.get(field) for field in PARTNERSHIP_TRUST_AMOUNT_FIELDS if has_meaningful_value(item.get(field))]
    return has_meaningful_value(identity) and has_meaningful_value(statement) and bool(amounts)


def partnership_trust_flat_item(answers: Dict[str, Any], kind: str) -> Dict[str, Any]:
    item: Dict[str, Any] = {}
    conflicts: Dict[str, Any] = {}
    for field, aliases in PARTNERSHIP_TRUST_FLAT_FIELDS[kind].items():
        values = scalar_alias_values(answers, aliases)
        if not values:
            continue
        item[field] = values[0]
        if any(not income_alias_values_equivalent(value, values[0]) for value in values[1:]):
            conflicts[field] = values
    metadata = PARTNERSHIP_TRUST_FLAT_METADATA_ALIASES[kind]
    source_values = [
        answers.get(alias)
        for field in ("source_url", "source_urls")
        for alias in metadata[field]
        if has_meaningful_value(answers.get(alias))
    ]
    valid_urls, invalid_urls = source_provenance_values(source_values)
    if valid_urls:
        item["source_urls"] = valid_urls
    if invalid_urls:
        item["unresolved_source_provenance"] = invalid_urls
    checked_values = [
        answers.get(alias)
        for field in ("checked_at", "source_checked_at")
        for alias in metadata[field]
        if has_meaningful_value(answers.get(alias))
    ]
    valid_checked, invalid_checked = checked_at_provenance_values(checked_values)
    if valid_checked:
        item["checked_at"] = valid_checked[0]
        if len(valid_checked) > 1:
            conflicts["checked_at"] = valid_checked
    if invalid_checked:
        item["unresolved_checked_at_provenance"] = invalid_checked
    status_values = [
        answers.get(alias)
        for field in ("status", "evidence_status")
        for alias in metadata[field]
        if has_meaningful_value(answers.get(alias))
    ]
    if status_values:
        item["status"] = canonical_review_status(status_values)
    mixed_values = meaningful_alias_values(answers, metadata["mixed_components"])
    if mixed_values:
        item["mixed_components"] = mixed_values[0]
        if any(not income_alias_values_equivalent(value, mixed_values[0]) for value in mixed_values[1:]):
            conflicts["mixed_components"] = mixed_values
    if conflicts:
        item["alias_conflicts"] = conflicts
    return item


def partnership_trust_flat_has_statement_facts(item: Dict[str, Any]) -> bool:
    return any(has_meaningful_value(item.get(field)) for field in PARTNERSHIP_TRUST_ROW_SIGNAL_FIELDS)


def partnership_trust_flat_has_substantive_facts(item: Dict[str, Any]) -> bool:
    return any(
        has_meaningful_value(item.get(field))
        for field in (*PARTNERSHIP_TRUST_FLAT_FIELDS["partnership"].keys(), "mixed_components")
    )


def scalar_alias_values(values: Dict[str, Any], aliases: tuple[str, ...]) -> List[Any]:
    return [
        values.get(alias)
        for alias in aliases
        if has_meaningful_value(values.get(alias)) and not isinstance(values.get(alias), (dict, list))
    ]


def meaningful_alias_values(values: Dict[str, Any], aliases: tuple[str, ...]) -> List[Any]:
    return [values.get(alias) for alias in aliases if has_meaningful_value(values.get(alias))]


def income_alias_values_equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    return left == right


def first_meaningful_present(values: Dict[str, Any], aliases: tuple[str, ...]) -> Any:
    for alias in aliases:
        value = values.get(alias)
        if has_meaningful_value(value):
            return value
    return None


def structured_income_items(value: Any, alias: str) -> List[Dict[str, Any]]:
    if isinstance(value, dict):
        value = [value] if value else [
            {"unparsed_input": f"Empty {alias} item", "_malformed": True, "_empty_placeholder": True}
        ]
    if not isinstance(value, list):
        if is_missing(value):
            return []
        return [{"unparsed_input": value, "_malformed": True}]
    items: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict) and has_meaningful_value(item):
            items.append(dict(item))
        elif isinstance(item, dict):
            items.append(
                {"unparsed_input": f"Empty {alias} item", "_malformed": True, "_empty_placeholder": True}
            )
        elif not is_missing(item):
            items.append({"unparsed_input": item, "_malformed": True})
    return items


def normalize_partnership_trust_structured_item(kind: str, item: Dict[str, Any]) -> Dict[str, Any]:
    if item.get("_malformed") is True:
        return dict(item)
    normalized = dict(item)
    conflicts = dict(item.get("alias_conflicts")) if isinstance(item.get("alias_conflicts"), dict) else {}
    groups = {
        "entity_name": ("entity_name", kind, "name", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["entity_name"]),
        "abn": ("abn", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["abn"]),
        "tfn": ("tfn", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["tfn"]),
        "statement": ("statement", "statement_status", "evidence", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["statement"]),
        "income": ("income", "income_amount", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["income"]),
        "loss": ("loss", "loss_amount", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["loss"]),
        "tax_withheld": ("tax_withheld", "withholding", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["tax_withheld"]),
        "credits": ("credits", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["credits"]),
        "entity_return_context": (
            "entity_return_context", *PARTNERSHIP_TRUST_FLAT_FIELDS[kind]["entity_return_context"],
        ),
    }
    for canonical, aliases in groups.items():
        values = [item.get(alias) for alias in dict.fromkeys(aliases) if has_meaningful_value(item.get(alias))]
        if not values:
            continue
        normalized[canonical] = values[0]
        if any(not income_alias_values_equivalent(value, values[0]) for value in values[1:]):
            conflicts[f"structured_{canonical}"] = values

    metadata = PARTNERSHIP_TRUST_FLAT_METADATA_ALIASES[kind]
    source_values = [
        item.get(alias)
        for field in ("source_url", "source_urls")
        for alias in (field, *metadata[field])
        if alias in item and not is_missing(item.get(alias))
    ]
    valid_urls, invalid_urls = source_provenance_values(source_values)
    if valid_urls:
        normalized["source_urls"] = valid_urls
    if invalid_urls:
        normalized["unresolved_source_provenance"] = invalid_urls
    checked_values = [
        item.get(alias)
        for field in ("checked_at", "source_checked_at")
        for alias in (field, *metadata[field])
        if alias in item and not is_missing(item.get(alias))
    ]
    valid_checked, invalid_checked = checked_at_provenance_values(checked_values)
    if valid_checked:
        normalized["checked_at"] = valid_checked[0]
        if len(valid_checked) > 1:
            conflicts["structured_checked_at"] = valid_checked
    if invalid_checked:
        normalized["unresolved_checked_at_provenance"] = invalid_checked
    status_values = [
        item.get(alias)
        for field in ("status", "evidence_status")
        for alias in (field, *metadata[field])
        if has_meaningful_value(item.get(alias))
    ]
    if status_values:
        normalized["status"] = canonical_review_status(status_values)
    mixed_values = [
        item.get(alias)
        for alias in ("mixed_components", *metadata["mixed_components"])
        if has_meaningful_value(item.get(alias))
    ]
    if mixed_values:
        normalized["mixed_components"] = mixed_values[0]
        if any(not income_alias_values_equivalent(value, mixed_values[0]) for value in mixed_values[1:]):
            conflicts["structured_mixed_components"] = mixed_values
    if conflicts:
        normalized["alias_conflicts"] = conflicts
    return normalized


def partnership_trust_evidence_gap(item: Dict[str, Any]) -> bool:
    statement = first_meaningful_present(item, ("statement", "statement_status", "evidence"))
    amount_values = [item.get(field) for field in PARTNERSHIP_TRUST_AMOUNT_FIELDS if field in item]
    return (
        item.get("_malformed") is True
        or has_routing_conflict(item)
        or provenance_has_errors(item)
        or is_missing(first_meaningful_present(item, ("entity_name", "partnership", "trust", "name")))
        or investment_statement_missing(statement)
        or not amount_values
        or any(income_amount_needs_evidence(value) for value in amount_values)
    )


def income_amount_needs_evidence(value: Any) -> bool:
    if isinstance(value, dict):
        return not value or any(income_amount_needs_evidence(item) for item in value.values())
    if isinstance(value, list):
        return not value or any(income_amount_needs_evidence(item) for item in value)
    return (
        isinstance(value, bool)
        or is_missing(value)
        or contains_unknown(value)
        or investment_amount_malformed(value)
    )


def partnership_trust_answer(kind: str, item: Dict[str, Any]) -> str:
    entity = first_meaningful_present(item, ("entity_name", kind, "name"))
    parts = [f"entity {display_value(entity)}"] if not is_missing(entity) else []
    labels = (
        ("abn", "ABN"),
        ("tfn", "TFN"),
        ("statement", "statement"),
        ("statement_status", "statement status"),
        ("income", "income"),
        ("income_amount", "income"),
        ("income_components", "income components"),
        ("loss", "loss"),
        ("loss_amount", "loss"),
        ("loss_components", "loss components"),
        ("tax_withheld", "tax withheld"),
        ("withholding", "tax withheld"),
        ("credits", "credits"),
        ("entity_return_context", "entity return context"),
        ("mixed_components", "mixed components"),
        ("evidence_status", "evidence status"),
        ("unparsed_input", "unparsed input"),
        ("alias_conflicts", "alias conflicts"),
        ("unresolved_source_provenance", "unresolved source provenance"),
        ("unresolved_checked_at_provenance", "unresolved checked-at provenance"),
    )
    used: set[str] = set()
    for key, label in labels:
        if label in used or key not in item or not has_meaningful_value(item.get(key)):
            continue
        used.add(label)
        value = item.get(key)
        amount = None
        if key in PARTNERSHIP_TRUST_AMOUNT_FIELDS and not isinstance(value, (dict, list)):
            amount = investment_money_value(value)
        rendered = money_text(amount) if amount is not None else display_value(value)
        parts.append(f"{label} {rendered}")
    return "; ".join(parts) or f"{kind} statement details not supplied"


def partnership_trust_share_evidence_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for kind, item in partnership_trust_share_items(answers):
        if not partnership_trust_evidence_gap(item) or explicit_accountant_review(item):
            continue
        rows.append(
            guide_row(
                f"PT-EVID-{len(rows) + 1}",
                "13 Partnerships and trusts",
                "Partnership/trust statement evidence required",
                partnership_trust_answer(kind, item),
                "Statement and numeric component evidence must be resolved before accountant review.",
                "Evidence",
                list(dict.fromkeys([ATO_PARTNERSHIP_TRUST_INCOME_SOURCE, *supplied_source_urls(item)])),
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("statement-evidence", "Statement evidence needed", partnership_trust_answer(kind, item)),
                ),
                checked_at=supplied_checked_at(item),
            )
        )
    return rows


def supplied_source_urls(item: Dict[str, Any]) -> List[str]:
    valid, _invalid = source_provenance_values([item.get("source_urls"), item.get("source_url")])
    return valid


def supplied_checked_at(item: Dict[str, Any]) -> Optional[str]:
    valid, _invalid = checked_at_provenance_values([item.get("checked_at"), item.get("source_checked_at")])
    return valid[0] if valid else None


def source_provenance_values(values: Any) -> tuple[List[str], List[str]]:
    valid: List[str] = []
    invalid: List[str] = []

    def collect(value: Any) -> None:
        if is_missing(value):
            return
        if isinstance(value, list):
            for entry in value:
                collect(entry)
            return
        if isinstance(value, str) and re.match(r"^https?://[^\s]+$", value.strip()):
            valid.append(value.strip())
            return
        invalid.append(display_value(value))

    collect(values)
    return list(dict.fromkeys(valid)), list(dict.fromkeys(invalid))


def checked_at_provenance_values(values: Any) -> tuple[List[str], List[str]]:
    valid: List[str] = []
    invalid: List[str] = []

    def collect(value: Any) -> None:
        if is_missing(value):
            return
        if isinstance(value, list):
            for entry in value:
                collect(entry)
            return
        if isinstance(value, str):
            candidate = value.strip()
            try:
                datetime.fromisoformat(candidate.replace("Z", "+00:00"))
                valid.append(candidate)
                return
            except ValueError:
                pass
        invalid.append(display_value(value))

    collect(values)
    return list(dict.fromkeys(valid)), list(dict.fromkeys(invalid))


def provenance_has_errors(item: Dict[str, Any]) -> bool:
    _urls, invalid_urls = source_provenance_values([item.get("source_urls"), item.get("source_url")])
    checked, invalid_checked = checked_at_provenance_values([item.get("checked_at"), item.get("source_checked_at")])
    return bool(
        invalid_urls
        or invalid_checked
        or has_meaningful_value(item.get("unresolved_source_provenance"))
        or has_meaningful_value(item.get("unresolved_checked_at_provenance"))
        or len(checked) > 1
    )


def has_routing_conflict(item: Dict[str, Any]) -> bool:
    return has_meaningful_value(item.get("alias_conflicts"))


def canonical_review_status(values: List[Any]) -> str:
    kind = taxmate_handoff.effective_status_kind(*values)
    if kind == "review":
        return "Accountant review"
    if kind == "evidence":
        return "Evidence"
    return display_value(values[0])


def routing_handoff_facts(key_prefix: str, label_prefix: str, item: Dict[str, Any]) -> List[Dict[str, Any]]:
    metadata = {"source_url", "source_urls", "checked_at", "source_checked_at", "status", "status_kind", "tab_kind"}
    facts = atomic_handoff_facts(
        key_prefix,
        label_prefix,
        {key: value for key, value in item.items() if key not in metadata},
    )
    _urls, invalid_urls = source_provenance_values([item.get("source_urls"), item.get("source_url")])
    _checked, invalid_checked = checked_at_provenance_values([item.get("checked_at"), item.get("source_checked_at")])
    if invalid_urls:
        facts.extend(atomic_handoff_facts(f"{key_prefix}-source", f"{label_prefix} unresolved source", invalid_urls))
    if invalid_checked:
        facts.extend(atomic_handoff_facts(f"{key_prefix}-checked-at", f"{label_prefix} unresolved checked at", invalid_checked))
    if not facts:
        return handoff_facts((key_prefix, label_prefix, "Evidence details not supplied"))
    return facts


def explicit_accountant_review(item: Dict[str, Any]) -> bool:
    status_keys = ("status_kind", "status", "tab_kind", "evidence_status")
    if not any(not is_missing(item.get(key)) for key in status_keys):
        return False
    return taxmate_handoff.effective_status_kind(
        item.get("status_kind"),
        item.get("status"),
        item.get("tab_kind"),
        item.get("evidence_status"),
    ) == "review"


def review_first_status(item: Dict[str, Any], evidence_gap: bool) -> str:
    if explicit_accountant_review(item):
        return "Accountant review"
    return "Evidence" if evidence_gap else "Accountant review"


UNCOMMON_INCOME_ALIASES = ("uncommon_income", "uncommon_income_items", "other_income_items")
UNCOMMON_INCOME_DESCRIPTION_FIELDS = ("category", "type", "income_type", "label", "details", "notes")


def uncommon_income_items(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    containers = [answers]
    for key in ("individual_income", "supplementary_income"):
        nested = answers.get(key)
        if isinstance(nested, dict):
            containers.append(nested)
    for container in containers:
        container_items: List[Dict[str, Any]] = []
        empty_dict_alias = ""
        for alias in UNCOMMON_INCOME_ALIASES:
            if alias not in container:
                continue
            value = container.get(alias)
            if has_meaningful_value(value):
                container_items.extend(structured_uncommon_income_items(value, alias))
            elif isinstance(value, dict) and not value and not empty_dict_alias:
                empty_dict_alias = alias
        if not container_items and empty_dict_alias:
            container_items.extend(structured_uncommon_income_items({}, empty_dict_alias))
        items.extend(container_items)
    return items


def structured_uncommon_income_items(value: Any, alias: str) -> List[Dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    items: List[Dict[str, Any]] = []
    for item in values:
        if isinstance(item, dict) and has_meaningful_value(item):
            items.append(item)
        elif isinstance(item, dict):
            items.append({"details": f"Empty {alias} item", "_malformed": True})
        elif not is_missing(item):
            items.append({"details": item, "_malformed": not isinstance(item, str)})
    return items


def uncommon_income_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in uncommon_income_items(answers):
        route, question, sources = uncommon_income_route(item)
        evidence_gap = uncommon_income_evidence_gap(item)
        status = review_first_status(item, evidence_gap)
        idx = len(rows) + 1
        rows.append(
            guide_row(
                f"UNC-{idx}",
                "Supplementary / uncommon income",
                question,
                uncommon_income_answer(item),
                f"{route} facts stay prep-only. TaxMate preserves the supplied facts and does not decide final treatment or destination.",
                status,
                list(dict.fromkeys([*sources, *supplied_source_urls(item)])),
                tab_text=(
                    "Uncommon income needs category, amount, or statement evidence before accountant review."
                    if evidence_gap and status == "Evidence"
                    else "Uncommon income needs accountant review before entry."
                ),
                row_kind="supplementary-income",
                facts=routing_handoff_facts("uncommon-income", "Uncommon income fact", item),
                checked_at=supplied_checked_at(item),
            )
        )
    return rows


def uncommon_income_route(item: Dict[str, Any]) -> tuple[str, str, List[str]]:
    descriptions = " ".join(
        text(item.get(field)).lower()
        for field in UNCOMMON_INCOME_DESCRIPTION_FIELDS
        if not is_missing(item.get(field))
    )
    insurance = re.search(r"\binsurance\b", descriptions) is not None and (
        re.search(r"\b(payment|payout|settlement|proceeds|claim|benefit)s?\b", descriptions) is not None
        or "general insurance" in descriptions
    )
    compensation = "compensation" in descriptions or insurance
    scholarship = any(term in descriptions for term in ("scholarship", "prize", "award"))
    if compensation and not scholarship:
        return "Compensation or insurance payment", "Compensation or insurance payment review", [ATO_COMPENSATION_INCOME_SOURCE]
    if scholarship and not compensation:
        return "Scholarship, prize or award", "Scholarship, prize or award review", [ATO_SCHOLARSHIP_PRIZE_SOURCE]
    return "Unsupported or residual uncommon income", "Uncommon income review", [ATO_INDIVIDUAL_SOURCE]


def uncommon_income_answer(item: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key, value in item.items():
        metadata_keys = {"source_url", "source_urls", "checked_at", "source_checked_at"}
        if key.startswith("_") or key in metadata_keys or is_missing(value):
            continue
        amount = investment_money_value(value) if key in {"amount", "gross", "tax_withheld", "credits"} else None
        rendered = money_text(amount) if amount is not None else display_value(value)
        parts.append(f"{handoff_label_part(key).lower()} {rendered}")
    return "; ".join(parts) or "Uncommon income details not supplied"


def uncommon_income_evidence_gap(item: Dict[str, Any]) -> bool:
    descriptions = [item.get(field) for field in UNCOMMON_INCOME_DESCRIPTION_FIELDS if not is_missing(item.get(field))]
    if (
        item.get("_malformed") is True
        or has_routing_conflict(item)
        or provenance_has_errors(item)
        or not descriptions
        or any(contains_unknown(value) for value in descriptions)
    ):
        return True
    amount_values = [item.get(key) for key in ("amount", "gross") if key in item]
    if not amount_values or any(income_amount_needs_evidence(value) for value in amount_values):
        return True
    statement = first_meaningful_present(item, ("statement", "evidence", "records"))
    return investment_statement_missing(statement)


def uncommon_income_evidence_rows(answers: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in uncommon_income_items(answers):
        if not uncommon_income_evidence_gap(item) or explicit_accountant_review(item):
            continue
        rows.append(
            guide_row(
                f"UNC-EVID-{len(rows) + 1}",
                "Supplementary / uncommon income",
                "Uncommon income evidence required",
                uncommon_income_answer(item),
                "Category, amount, or statement evidence must be resolved before accountant review.",
                "Evidence",
                list(dict.fromkeys([*uncommon_income_route(item)[2], *supplied_source_urls(item)])),
                row_kind="evidence-queue",
                facts=handoff_facts(
                    ("uncommon-income-evidence", "Uncommon income evidence needed", uncommon_income_answer(item)),
                ),
                checked_at=supplied_checked_at(item),
            )
        )
    return rows


def handoff_facts(
    *entries: tuple[str, str, Any],
) -> List[Dict[str, Any]]:
    """Build explicit non-mapped facts for an intake-owned row."""
    supplied = [entry for entry in entries if not is_missing(entry[2])]
    if not supplied and entries:
        key, label, _value = entries[0]
        supplied = [(key, label, "Not supplied")]
    return [
        taxmate_handoff.fact(key, label, value)
        for key, label, value in supplied
    ]


def atomic_handoff_facts(
    key_prefix: str,
    label_prefix: str,
    value: Any,
    *,
    action_kind: str = "",
) -> List[Dict[str, Any]]:
    """Flatten a supplied container into stable labelled scalar facts."""
    if isinstance(value, dict):
        facts: List[Dict[str, Any]] = []
        for key, item in value.items():
            if str(key).startswith("_"):
                continue
            key_part = handoff_key_part(key)
            label_part = handoff_label_part(key)
            facts.extend(
                atomic_handoff_facts(
                    f"{key_prefix}-{key_part}",
                    f"{label_prefix} - {label_part}",
                    item,
                    action_kind=action_kind,
                )
            )
        return facts
    if isinstance(value, (list, tuple)):
        facts = []
        for index, item in enumerate(value, start=1):
            facts.extend(
                atomic_handoff_facts(
                    f"{key_prefix}-{index}",
                    f"{label_prefix} {index}",
                    item,
                    action_kind=action_kind,
                )
            )
        return facts
    if is_missing(value):
        return []
    return [
        taxmate_handoff.fact(
            key_prefix,
            label_prefix,
            value,
            action_kind=action_kind,
        )
    ]


def indexed_item_handoff_facts(
    key_prefix: str,
    label_prefix: str,
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    facts: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        facts.extend(
            atomic_handoff_facts(
                f"{key_prefix}-{index}",
                f"{label_prefix} {index}",
                item,
            )
        )
    return facts


def handoff_key_part(value: Any) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", text(value).strip().lower()).strip("-")
    return key or "value"


HANDOFF_LABEL_ACRONYMS = {
    "abn": "ABN",
    "bas": "BAS",
    "cgt": "CGT",
    "ess": "ESS",
    "gst": "GST",
    "id": "ID",
    "mls": "MLS",
    "payg": "PAYG",
    "psb": "PSB",
    "psi": "PSI",
    "tfn": "TFN",
    "url": "URL",
    "wfh": "WFH",
}


def handoff_label_part(value: Any) -> str:
    words = re.sub(r"[_-]+", " ", text(value)).strip().lower().split()
    if not words:
        return "Value"
    return " ".join(
        HANDOFF_LABEL_ACRONYMS.get(word, word.capitalize() if index == 0 else word)
        for index, word in enumerate(words)
    )


def guide_row(
    number: Any,
    area: Any,
    question: Any,
    answer: Any,
    why: Any,
    status: Any,
    source: Any,
    tab_text: Optional[str] = None,
    *,
    row_kind: str,
    facts: List[Dict[str, Any]],
    checked_at: Optional[str] = None,
) -> Dict[str, Any]:
    if not row_kind.strip():
        raise ValueError("guide row_kind must be nonblank")
    if not facts:
        raise ValueError("guide facts must be non-empty")
    contract = taxmate_handoff.build_row_contract(
        row_kind,
        status,
        facts,
        income_year=DEFAULT_INCOME_YEAR,
    )
    return {
        "number": number,
        "ato_area": area,
        "question": question,
        "answer": answer,
        "why_included": why,
        "status": status,
        "source_urls": source if isinstance(source, list) else [source],
        "checked_at": checked_at if checked_at is not None else generation_checked_at(),
        "tab_text": tab_text or why,
        **contract,
    }


def finalize_guide_row(row: Dict[str, Any], income_year: str) -> Dict[str, Any]:
    normalized = dict(row)
    facts = normalized.get("facts")
    if not isinstance(facts, list) or not facts:
        raise ValueError("internal guide row missing explicit facts")
    row_kind = text(normalized.get("row_kind")).strip()
    if not row_kind:
        raise ValueError("internal guide row missing explicit row_kind")
    contract = taxmate_handoff.build_row_contract(
        row_kind,
        normalized.get("status"),
        facts,
        income_year=income_year,
    )
    normalized.update(contract)
    return normalized


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
