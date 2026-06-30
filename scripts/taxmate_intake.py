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
ATO_BUSINESS_INCOME_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business"
ATO_PSI_SOURCE = "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income"
ATO_PSI_SOURCES = [
    ATO_PSI_SOURCE,
    ATO_BUSINESS_INCOME_SOURCE,
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
ATO_RENTAL_PROPERTY_SOURCES = [
    ATO_RENTAL_RECORDS_SOURCE,
    ATO_RENTAL_CGT_SOURCE,
    ATO_RENTAL_HOME_USE_SOURCE,
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
    items.extend(psi_rows(psi_answers(answers)))
    items.extend(crypto_rows(crypto_answers(answers)))
    items.extend(rental_property_rows(rental_property_answers(answers)))
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
    return spec.required or has_meaningful_value(value)


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
    return rental_property_source_declines_workflow(nested_key, value) or rental_property_field_absence_value(
        nested_key,
        value,
    )


def rental_property_flat_field_key(key: str) -> str:
    return RENTAL_PROPERTY_FLAT_FIELD_KEYS.get(key, key)


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
    merged = dict(flat_values)
    for key, value in raw.items():
        if has_meaningful_rental_property_override(key, value):
            merged[key] = value
        elif key not in merged and has_explicit_rental_property_evidence_gap(key, value):
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
    for key, value in record.items():
        if has_meaningful_rental_property_flat_value(key, value) or has_explicit_rental_property_evidence_gap(key, value):
            values[key] = value
    return values


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
        return any(rental_property_item_income_needs_evidence(item) for item in items)
    if rental_property_has_field_value(raw, "income"):
        return rental_property_amount_needs_evidence(raw.get("income"), "income")
    return rental_property_has_facts(raw) or bool(items)


def rental_property_item_income_needs_evidence(item: Dict[str, Any]) -> bool:
    if not rental_property_has_field_value(item, "income"):
        return True
    return rental_property_amount_needs_evidence(item.get("income"), "income")


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
    if meaningful and not any(rental_property_has_field_value(record, "private_use") for record in meaningful):
        return True
    if any(rental_property_private_use_uncertain(record.get("private_use")) for record in meaningful):
        return True
    if any(rental_property_private_use_signal(record) for record in meaningful):
        return any(
            rental_property_usable_amount_value(record.get("private_use_days"), "private_use_days") is None
            or rental_property_usable_amount_value(record.get("available_days"), "available_days") is None
            for record in meaningful
            if rental_property_private_use_signal(record)
        )
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
    net_amount = rental_property_net_amount(record)
    if net_amount is not None and net_amount < 0:
        return True
    return rental_property_net_loss_signal(record.get("net_loss"))


def rental_property_net_amount(record: Dict[str, Any]) -> Optional[float]:
    explicit = rental_property_net_loss_amount_value(record.get("net_loss"))
    if explicit is not None:
        return explicit
    income = rental_property_usable_amount_value(record.get("income"), "income")
    if income is None:
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
    if rental_property_record_context(lowered) and lowered.startswith(("no ", "without ", "missing ")):
        return True
    if rental_property_record_context(lowered) and any(
        phrase in lowered for phrase in ("do not have", "don't have", "dont have", "not held", "not available", "not provided")
    ):
        return True
    return lowered in {"no", "n", "false", "none", "not held", "not available"}


def rental_property_record_context(lowered: str) -> bool:
    return any(term in lowered for term in ("record", "records", "statement", "invoice", "invoices", "agent", "loan", "interest"))


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
    return lowered in RENTAL_PROPERTY_NET_LOSS_FALSE_PHRASES


def rental_property_field_text(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> str:
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
    if rental_property_amount_conflict(raw, items, key):
        return "unknown"
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
    explicit = rental_property_net_loss_amount_value(raw.get("net_loss"))
    if explicit is not None:
        return explicit
    if rental_property_supplied_amount_needs_evidence(raw, items, "net_loss"):
        return None
    if any(rental_property_net_loss_amount_value(item.get("net_loss")) is not None for item in items):
        item_net_values = [rental_property_net_amount(item) for item in items]
        real_item_net_values = [value for value in item_net_values if value is not None]
        if len(real_item_net_values) == len(items):
            return round(sum(real_item_net_values), 2)
        return None
    if rental_property_supplied_amount_needs_evidence(raw, items, "income"):
        return None
    income = rental_property_display_amount_value(raw, items, "income")
    if income is None:
        return None
    if any(rental_property_supplied_amount_needs_evidence(raw, items, key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS):
        return None
    expenses = [rental_property_display_amount_value(raw, items, key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS]
    known_expenses = [amount for amount in expenses if amount is not None]
    if not known_expenses:
        return income
    return round(income - sum(known_expenses), 2)


def rental_property_display_amount_value(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> Optional[float]:
    if rental_property_amount_conflict(raw, items, key):
        return None
    direct = rental_property_usable_amount_value(raw.get(key), key)
    if direct is not None:
        return direct
    values = [rental_property_usable_amount_value(item.get(key), key) for item in items]
    real_values = [value for value in values if value is not None]
    return round(sum(real_values), 2) if real_values else None


def rental_property_supplied_amount_needs_evidence(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> bool:
    return (
        rental_property_supplied_field_needs_evidence(raw, key)
        or any(rental_property_supplied_field_needs_evidence(item, key) for item in items)
        or rental_property_amount_conflict(raw, items, key)
    )


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
    return rental_property_amount_value(value)


def rental_property_amount_conflicts(raw: Dict[str, Any], items: List[Dict[str, Any]]) -> bool:
    return any(rental_property_amount_conflict(raw, items, key) for key in RENTAL_PROPERTY_AMOUNT_FIELDS)


def rental_property_amount_conflict(raw: Dict[str, Any], items: List[Dict[str, Any]], key: str) -> bool:
    direct = rental_property_reconciliation_amount_value(raw.get(key), key)
    if direct is None:
        return False
    item_values = [rental_property_reconciliation_amount_value(item.get(key), key) for item in items]
    real_item_values = [value for value in item_values if value is not None]
    if not real_item_values:
        return False
    item_total = round(sum(real_item_values), 2)
    return round(direct, 2) != item_total


def rental_property_reconciliation_amount_value(value: Any, key: str) -> Optional[float]:
    if key == "net_loss":
        return rental_property_net_loss_amount_value(value)
    return rental_property_usable_amount_value(value, key)


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
            f"private use {rental_property_item_text_or_inherited(raw, item, 'private_use')}, "
            f"records {rental_property_item_text_or_inherited(raw, item, 'records')}"
        )
    return " | ".join(details)


def rental_property_item_amount_text(item: Dict[str, Any], key: str, money: bool = True) -> str:
    value = item.get(key)
    if rental_property_amount_missing_document_value(value):
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
