#!/usr/bin/env python3
"""TaxMate Australia individual intake command."""

from __future__ import annotations

import argparse
import json
import math
import re
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
    "employee_deductions",
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
ATO_INDIVIDUAL_SOURCE = "https://www.ato.gov.au/forms-and-instructions/individual-tax-return-instructions-2026"
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
        QuestionSpec("employee_deductions", "Deductions", "Employee deductions", "D1-D10 deductions", False),
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
        "spouse_had": True,
        "dependant_children": 0,
        "private_health_cover": "partial year; statement not confirmed",
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
        "employee_deductions": [{"label": "Union fees", "amount": 0, "evidence": "unknown"}],
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
    investment = investment_answers(answers)
    payg = payg_answers(answers)
    cgt = cgt_answers(answers)
    items = base_items(answers)
    extracted_values = extraction_rows(answers.get("extracted_values", []))
    abn_items = abn_rows(answers) if has_abn_inputs(answers) else []
    bas_items = bas_rows(answers) if has_bas_inputs(answers) else []
    missing_items = missing_fact_rows(answers)
    evidence_items = evidence_rows(answers)
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
    investment = investment_answers(answers)
    payg = payg_answers(answers)
    cgt = cgt_answers(answers)
    has_payg_items = bool(payg_item_values(payg.get("items")))
    has_cgt = has_cgt_inputs(cgt)
    has_phone = has_phone_inputs(phone_answers(answers))
    abn = abn_summary(answers) if has_abn_inputs(answers) else {}
    bas = bas_summary(answers) if has_bas_inputs(answers) else {}
    for spec in question_specs():
        value = investment_base_item_value(spec.key, answers, investment)
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
                    "Long-checklist intake answer for manual copy guidance.",
                    status,
                    base_item_sources(spec.key),
                    tab_text=f"{spec.prompt}: {display_value(value)}",
                )
            )
    return rows


def investment_base_item_value(key: str, answers: Dict[str, Any], investment: Dict[str, Any]) -> Any:
    if key in INVESTMENT_AGGREGATE_ALIASES:
        value = investment_aggregate_value(investment, key)
        if not is_missing(value):
            return value
    return answers.get(key)


def base_item_sources(key: str) -> Any:
    if key in REVIEWABLE_INVESTMENT_FIELDS:
        return INVESTMENT_SOURCES
    if key in REVIEWABLE_PAYG_FIELDS:
        return PAYG_SOURCES
    if key in REVIEWABLE_CGT_FIELDS:
        return ATO_CGT_SOURCES
    return ATO_INDIVIDUAL_SOURCE


def should_render_base_item(spec: QuestionSpec, value: Any) -> bool:
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


def safe_money_value(value: Any) -> Optional[float]:
    try:
        return money_value(value, unknown_as_missing=True)
    except ValueError:
        return None


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
    if is_missing(value) or contains_unknown(value):
        return True
    if isinstance(value, list):
        return not value or any(evidence_missing(item) for item in value)
    if isinstance(value, dict):
        return not value or any(evidence_missing(item) for item in value.values())
    lowered = text(value).strip().lower()
    return lowered in {"no", "n", "false", "none", "n/a", "na", "not applicable", "not held", "not available", "missing"} or any(
        phrase in lowered
        for phrase in (
            "no record",
            "no records",
            "no bookkeeping records",
            "no business records",
            "record not held",
            "records not held",
            "without records",
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
            "tax invoices not available",
            "not available",
            "unavailable",
        )
    )


def item_list_text(label: str, items: List[Dict[str, Any]]) -> str:
    if not items:
        return f"{label} none supplied"
    parts = [f"{item_label(item)} {money_text(item_amount(item))}" for item in items[:4]]
    if len(items) > 4:
        parts.append(f"{len(items) - 4} more")
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
            "BAS worksheet only. Confirm 1A, 1B, GST-free/input-taxed sales, adjustments, PAYG labels, tax invoices, period coverage, and accounting basis before manual use.",
            status,
            ATO_BAS_SOURCES,
            tab_text=bas_tab_text(summary),
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
    negative_registration = canonical in {"no", "n", "false", "not registered", "not gst registered"} or re.search(
        r"\b(not|no|without)\b(?:\s+\w+){0,3}\s+gst\b(?:\s+\w+){0,3}\s+registered\b",
        canonical,
    ) or re.search(
        r"\b(not|no|without)\b(?:\s+\w+){0,3}\s+registered\b(?:\s+\w+){0,3}\s+gst\b",
        canonical,
    )
    if negative_registration:
        return False
    positive_registration = canonical in {"yes", "y", "true", "registered", "gst registered"} or re.search(
        r"\bgst\b(?:\s+\w+){0,3}\s+registered\b",
        canonical,
    ) or re.search(
        r"\bregistered\b(?:\s+\w+){0,3}\s+gst\b",
        canonical,
    )
    if positive_registration:
        return True
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
    rows.extend(phone_evidence_rows(phone_answers(answers), answers))
    rows.extend(investment_evidence_rows(investment_answers(answers), answers))
    rows.extend(payg_evidence_rows(payg_answers(answers), answers))
    rows.extend(abn_business_evidence_rows(answers))
    rows.extend(bas_evidence_rows(answers))
    rows.extend(cgt_evidence_rows(cgt_answers(answers)))
    return rows


def evidence_row(number: Any, area: str, evidence: str) -> Dict[str, Any]:
    return guide_row(number, area, "Evidence required", evidence, "Draft value remains not copy-ready until evidence is confirmed.", "Evidence", ATO_INDIVIDUAL_SOURCE)


PHONE_NESTED_KEYS = ("phone", "phone_deduction", "mobile_phone", "mobile")
PHONE_FIELD_ALIASES = {
    "context": ("phone_context", "phone_work_context"),
    "paid_by_user": ("phone_paid_by_user", "phone_user_paid"),
    "employer_reimbursed": ("phone_employer_reimbursed", "phone_reimbursed"),
    "employer_paid": ("phone_employer_paid",),
    "employer_provided": ("phone_employer_provided", "employer_provided_phone"),
    "wfh_method": ("phone_wfh_method", "wfh_method"),
}
PHONE_GST_STATUS_KEYS = ("gst_registered", "gst_registration_status", "registered")
PHONE_GST_DATE_KEYS = ("gst_registration_date", "registered_from", "registration_date")
PHONE_METADATA_KEYS = {
    "context",
    "paid_by_user",
    "employer_reimbursed",
    "employer_paid",
    "employer_provided",
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
    raw["device"] = phone_child_answers(raw.get("device"), raw, answers, PHONE_DEVICE_ALIASES, PHONE_DEVICE_SIGNAL_KEYS)
    raw["plan"] = phone_child_answers(raw.get("plan"), raw, answers, PHONE_PLAN_ALIASES, PHONE_PLAN_SIGNAL_KEYS)
    raw["incidental"] = phone_child_answers(raw.get("incidental"), raw, answers, PHONE_INCIDENTAL_ALIASES, PHONE_INCIDENTAL_SIGNAL_KEYS)
    if not has_phone_inputs(raw):
        return {}
    if is_missing(raw.get("context")) and (has_abn_inputs(answers) or has_bas_inputs(answers)):
        raw["context"] = "employee" if phone_context_is_employee(display_value(raw.get("freeform"))) else "abn"
    return raw


def phone_normalized_nested_raw(raw: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in raw.items():
        normalized_key = str(key).strip().lower()
        if normalized_key in PHONE_OPT_OUT_KEYS and phone_freeform_absent(value):
            continue
        if normalized_key in PHONE_NEGATIVE_OPT_OUT_KEYS:
            if phone_bool(value) is True:
                continue
            if phone_bool(value) is False or is_missing(value):
                continue
        result[key] = value
    return result


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
    elif cost is None or work_use is None or evidence_gap:
        status = "Evidence"
        treatment = "evidence needed before method review"
    elif cost > 300:
        status = "Accountant review"
        treatment = "decline-in-value review; not full immediate claim"
    elif immediate_candidate:
        status = "Accountant review"
        treatment = "immediate deduction candidate if source-backed conditions and evidence hold"
    else:
        status = "Evidence"
        treatment = "under-300 conditions incomplete; no immediate candidate yet"
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
    tab_text = "Incidental phone use needs basic records and fixed-rate double-dip review."
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
    tokens = set(normalized.split())
    if value in {"abn", "business", "sole trader", "sole-trader", "both"}:
        return True
    return "abn" in tokens or "business" in tokens or {"sole", "trader"}.issubset(tokens)


def phone_context_has_negated_abn(normalized: str) -> bool:
    return bool(
        re.search(r"\b(not|no|without)\b\s+(a\s+|an\s+)?\b(abn|business)\b", normalized)
        or re.search(r"\bnon\s+(abn|business)\b", normalized)
    )


def phone_context_is_employee(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    tokens = set(normalized.split())
    if phone_context_is_abn(value):
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
    subject = r"(phone|mobile|internet|device|handset)"
    claim_word = r"(claim|claimed|claiming|deduction|expense|expenses|cost|costs)"
    no_word = r"no(?!\s+idea)"
    opt_out_patterns = (
        rf"\b({no_word}|without)\b.*\b{subject}\b.*\b{claim_word}\b",
        rf"\b({no_word}|without)\b.*\b{claim_word}\b.*\b{subject}\b",
        rf"\bnot\s+(claim|claimed|claiming|deducting)\b.*\b{subject}\b",
        rf"\b{subject}\b.*\b{claim_word}\b.*\b(none|nil|zero)\b",
        rf"\b{subject}\b.*\b(not|never)\b.*\b(claimed|claiming|used)\b",
        rf"\bnot eligible\b.*\b{subject}\b.*\b{claim_word}\b",
        rf"\b{subject}\b.*\b{claim_word}\b.*\bnot eligible\b",
    )
    if any(re.search(pattern, normalized) for pattern in opt_out_patterns):
        return True
    return False


def phone_gst_registered(raw: Dict[str, Any], answers: Dict[str, Any]) -> bool:
    gst = first_alias_value(raw, PHONE_GST_STATUS_KEYS)
    if is_missing(gst):
        gst = bas_gst_registration_answer(answers)
    return parse_gst_registration(gst) is True


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
    method = display_value(raw.get("wfh_method")).strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", method.replace("_", " ").replace("-", " ")).strip()
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


def phone_text_has_negated_marker(normalized: str, markers: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"\b(no|not|never|without|dont|don t|didnt|didn t|did not)\b(?:\s+\w+){{0,4}}\s+\b{marker}\b", normalized)
        or re.search(rf"\b{marker}\b(?:\s+\w+){{0,4}}\s+\b(no|not|never|without|n a|not applicable)\b", normalized)
        for marker in markers
    )


def phone_text_has_marker(normalized: str, markers: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{marker}\b", normalized) for marker in markers)


def phone_user_paid_false(value: Any) -> bool:
    parsed = phone_bool(value)
    if parsed is not None:
        return parsed is False
    normalized = phone_flag_text(value)
    if phone_user_paid_unanswered_text(normalized):
        return False
    if re.match(r"^(no|n|false|off|unchecked)\b", normalized):
        return True
    if not normalized or phone_text_has_negated_marker(normalized, ("reimburs\\w*", "employer paid", "paid by employer", "provided")):
        return False
    if re.search(r"\b(not|never|did not|dont|don t|didnt|didn t)\b(?:\s+\w+){0,3}\s+\b(pay|paid)\b", normalized):
        return True
    return phone_text_has_marker(normalized, ("reimburs\\w*", "employer paid", "paid by employer", "provided by employer", "company provided"))


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
    return bool(normalized) and not phone_text_has_negated_marker(normalized, markers) and phone_text_has_marker(normalized, markers)


def phone_employee_excluded(raw: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    if phone_user_paid_false(raw.get("paid_by_user")):
        terms.append("not paid by user")
    if phone_employer_flag_true(raw.get("employer_reimbursed"), ("reimburs\\w*",)):
        terms.append("employer reimbursed")
    if phone_employer_flag_true(raw.get("employer_paid"), ("employer paid", "paid by employer", "company paid")):
        terms.append("employer paid")
    if phone_employer_flag_true(raw.get("employer_provided"), ("employer provided", "provided by employer", "company provided")):
        terms.append("employer provided")
    return terms


def phone_blocking_terms(raw: Dict[str, Any]) -> List[str]:
    terms = phone_employee_excluded(raw)
    if phone_wfh_fixed_rate(raw):
        terms.append("WFH fixed-rate double-dip")
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
    if isinstance(value, str):
        lowered = value.strip().lower()
        for suffix in ("%", " percent", " per cent"):
            if lowered.endswith(suffix):
                parsed = safe_money_value(lowered[: -len(suffix)].strip())
                break
    if parsed is None:
        parsed = safe_money_value(value)
    if parsed is None or parsed < 0 or parsed > 100:
        return None
    return parsed


def phone_nonnegative_money_value(value: Any) -> Optional[float]:
    parsed = safe_money_value(value)
    if parsed is None or parsed < 0:
        return None
    return parsed


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
    return "Phone plan candidate stays prep-only and needs accountant review before manual copy."


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
                "Confirm malformed or unknown business income and expense amounts before manual use.",
                "ABN income and expense rows stay not copy-ready until amount records are reconciled.",
                "Evidence",
                ATO_ABN_BUSINESS_SOURCES,
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
                "Confirm malformed or unknown BAS label amounts before manual use.",
                "BAS label rows stay not copy-ready until 1A, 1B, GST-free/input-taxed, adjustment, and PAYG amounts are reconciled.",
                "Evidence",
                ATO_BAS_SOURCES,
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
        "Itemized bank interest is prep-only and needs statement support before manual copy.",
        status,
        INVESTMENT_SOURCES[:2],
        tab_text=investment_tab_text("Bank interest", evidence_terms(statement_evidence, amount_evidence, conflict), []),
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
        "Itemized investment rows are reconciled to supplied aggregate totals before manual copy.",
        status,
        INVESTMENT_SOURCES,
        tab_text=investment_reconciliation_tab_text(interest_conflict, dividend_conflict),
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
                        "Investment prep row remains not copy-ready until statement and amount evidence are confirmed.",
                        "Evidence",
                        INVESTMENT_SOURCES,
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
        return f"{label} stays accountant review for {', '.join(reviews)} before manual copy."
    return f"{label} stays accountant review before manual copy."


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
    status = (
        "Evidence"
        if statement_evidence
        or finalised_evidence
        or payer_evidence
        or amount_evidence
        or lump_sum_evidence
        or decline_evidence
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
        "PAYG statement rows are prep-only. Confirm income statement evidence, payer identity, amounts, allowances, RFBA, RESC, and any lump sum labels before manual copy.",
        status,
        PAYG_SOURCES,
        tab_text=payg_tab_text(statement_evidence, finalised_evidence, payer_evidence, amount_evidence, lump_sum_evidence, decline_evidence, conflict),
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
                "PAYG aggregate-only fact is prep-only and needs source evidence before manual copy.",
                payg_nested_base_status(nested_key, value, raw),
                PAYG_SOURCES,
                tab_text=f"{payg_nested_base_question(nested_key)}: {display_value(value)}",
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
        "Itemized PAYG statement totals are reconciled to supplied aggregate salary/wages and withholding before manual copy.",
        status,
        PAYG_SOURCES,
        tab_text=payg_reconciliation_tab_text(gross_conflict, withheld_conflict, aggregate_alias_conflict),
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
                "PAYG aggregate rows remain not copy-ready until supplied salary/wages facts and statement evidence are reconciled.",
                "Evidence",
                PAYG_SOURCES,
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
        if statement or finalised or payer or amounts or lump or decline:
            rows.append(
                guide_row(
                    f"PAYG-EVID-{len(rows) + 1}",
                    "1 Salary or wages",
                    "PAYG evidence required",
                    payg_evidence_text(idx, statement, finalised, payer, amounts, lump, decline, alias),
                    "PAYG prep row remains not copy-ready until statement, payer, amount, finalisation, and label evidence are resolved.",
                    "Evidence",
                    PAYG_SOURCES,
                )
            )
    if items and payg_supplemental_needs_evidence(raw):
        rows.append(
            guide_row(
                f"PAYG-EVID-{len(rows) + 1}",
                "1 Salary or wages",
                "PAYG aggregate detail evidence required",
                payg_supplemental_tab_text(raw),
                "Flat PAYG details supplied with itemized statements remain not copy-ready until amount, payer, and alias evidence is resolved.",
                "Evidence",
                PAYG_SOURCES,
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
    return "PAYG statement stays accountant review before manual copy."


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
            "ETP records need payment summary/income statement evidence, payment code, component split, cap context, and accountant review before manual copy.",
            status,
            ATO_ETP_SOURCE,
            tab_text=complex_payment_tab_text("ETP", statement_evidence, amount_evidence, decline_evidence),
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
            "Lump sum in arrears records need statement evidence, prior-year allocation, amount, withholding, and accountant review before manual copy.",
            status,
            ATO_LUMP_SUM_ARREARS_SOURCE,
            tab_text=lump_sum_arrears_tab_text(statement_evidence, prior_year_evidence, amount_evidence, decline_evidence),
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
            "Super lump sums and income streams need fund statement evidence, component split, withholding, age/condition context, and accountant review before manual copy.",
            status,
            [ATO_SUPER_PENSIONS_SOURCE, ATO_SUPER_LUMP_SUM_SOURCE, ATO_SUPER_STREAM_SOURCE],
            tab_text=complex_payment_tab_text("Super income", statement_evidence, amount_evidence, decline_evidence),
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
            "Foreign income needs source statement evidence, residency or temporary-resident context, foreign tax paid records, exchange-rate support, and accountant review before manual copy.",
            status,
            ATO_FOREIGN_INCOME_SOURCES,
            tab_text=foreign_income_tab_text(
                statement_evidence,
                amount_evidence,
                residency_evidence,
                tax_paid_evidence,
                decline_evidence,
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
            "PSI handling collects test facts, contracts, client concentration, attribution, deductions, and structure impacts for accountant review before manual copy.",
            status,
            ATO_PSI_SOURCES,
            tab_text=psi_tab_text(evidence),
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
    return "PSI tests, attribution, deductions, and structure stay accountant review before manual copy."


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
            items.append(item)
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
                        "CGT item row remains not copy-ready until evidence gaps are resolved.",
                        "Evidence",
                        cgt_row_sources(item),
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
                    f"{subject} remain not copy-ready until evidence gaps are resolved.",
                    "Evidence",
                    cgt_row_sources(raw),
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
                "CGT schedule row remains not copy-ready until evidence gaps are resolved.",
                "Evidence",
                cgt_row_sources(raw),
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
            "Crypto handling collects event type, asset, dates, proceeds, cost base, rewards, wallet records, ownership, and both business and private use context flags for accountant review before manual copy.",
            status,
            ATO_CRYPTO_SOURCES,
            tab_text=crypto_tab_text(evidence),
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
    return "Crypto disposals, swaps, exchanges, conversions, rewards, transfers, wallet records, and cost base stay accountant review before manual copy."


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
            "Rental property handling collects income, expenses, records, private-use apportionment, repairs versus capital indicators, depreciation, and net-loss flags for accountant review before manual copy.",
            status,
            ATO_RENTAL_PROPERTY_SOURCES,
            tab_text=rental_property_tab_text(evidence, review),
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
            f"{', '.join(review)} before manual copy."
        )
    if evidence:
        return f"Rental property worksheet needs {', '.join(evidence)} before accountant review."
    if review:
        return f"Rental property worksheet stays accountant review for {', '.join(review)} before manual copy."
    return "Rental property worksheet stays accountant review before manual copy."


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
