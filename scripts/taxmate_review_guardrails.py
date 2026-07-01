#!/usr/bin/env python3
"""Review-pattern guardrails learned from Codex PR feedback."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List


ROOT_MARKER = os.path.join(".codex-plugin", "plugin.json")
TAXPACK_OUTPUT_LAYER = "taxpack_output_layer_contract"
INDIVIDUAL_INTAKE_CONTRACT = "individual_intake_contract"
ATO_FETCH_BOUNDARY = "ato_fetch_boundary"
GENERATED_ARTIFACT_CONTRACT = "generated_artifact_contract"
FINANCE_JSON_WIRE_CONTRACT = "finance_json_wire_contract"
CALCULATOR_NUMERIC_CONTRACT = "calculator_numeric_contract"
CALCULATOR_TEMPORAL_CONTRACT = "calculator_temporal_scope_contract"
PUBLIC_CLAIM_SURFACE_CONTRACT = "public_claim_surface_contract"
RELEASE_GUARDRAIL_CONTRACT = "release_guardrail_contract"
ENVIRONMENT_WORKTREE_CONTRACT = "environment_worktree_contract"
LOCAL_PLUGIN_MARKETPLACE_CONTRACT = "local_plugin_marketplace_contract"
PRE_COMMIT_CONTRACT = "pre_commit_contract"
REVIEW_GUARDRAIL_DOCS = "review_guardrail_docs"
OUTPUT_DOCS_CONTRACT = "output_docs_contract"
MARKETPLACE_ADD_PREFIX = "codex plugin marketplace add "
LOCAL_MARKETPLACE_ADD_COMMAND = "codex plugin marketplace add ."
LOCAL_PLUGIN_ADD_COMMAND = "codex plugin add taxmate-australia@{name}"


@dataclass
class Finding:
    check: str
    detail: str


@dataclass
class ReviewPattern:
    id: str
    check: str
    summary: str


REVIEW_PATTERNS: List[ReviewPattern] = [
    ReviewPattern(
        "PR #7",
        f"{FINANCE_JSON_WIRE_CONTRACT}, {CALCULATOR_NUMERIC_CONTRACT}, {CALCULATOR_TEMPORAL_CONTRACT}, {GENERATED_ARTIFACT_CONTRACT}",
        "Preserve public JSON wire formats, reject non-finite numbers, keep half-up cent rounding, gate year-specific calculators by supported temporal scope, preserve generated source provenance, compare tracked generated artifacts, and remove stale Go/runtime docs.",
    ),
    ReviewPattern(
        "PR #8",
        ENVIRONMENT_WORKTREE_CONTRACT,
        "Keep Codex setup/cleanup safe in linked Git worktrees, do not dirty a clean checkout, and avoid unsafe find-delete patterns.",
    ),
    ReviewPattern(
        "PR #10",
        PUBLIC_CLAIM_SURFACE_CONTRACT,
        "Public metadata must describe the real bash and Python runtime.",
    ),
    ReviewPattern(
        "PR #22",
        PUBLIC_CLAIM_SURFACE_CONTRACT,
        "Public claim scanners must include wrappers, discovery docs, workflows, and endorsement phrasing in both directions around ATO.",
    ),
    ReviewPattern(
        "PR #25",
        ATO_FETCH_BOUNDARY,
        "ATO fetches must call curl --disable -L so user curl config cannot alter source refreshes.",
    ),
    ReviewPattern(
        "PR #27 / PR #53",
        TAXPACK_OUTPUT_LAYER,
        "Output layers must preserve Accountant review in main and extended sections, source provenance, falsey display values, dynamic generated dates, unique anchors, safe tab target lookup, and neutral mixed-area headings.",
    ),
    ReviewPattern(
        "PR #53 intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Individual intake must keep missing, malformed, unparseable, or nested unknown answers as Evidence/review, require literal boolean AI confirmation while preserving review-like extraction metadata, keep BAS values as review, use taxpayer state plus state-wide holidays only for supported WFH income years/date ranges, route limited/regional/partial-day public holidays to Evidence, keep unknown WFH parser inputs and incomplete records out of calculated candidates, avoid stale checked-at literals, and keep mixed-use assets under review.",
    ),
    ReviewPattern(
        "PR #55 ESS intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "ESS intake must normalize nested items field-by-field, preserve item amounts when sibling labels, statements, or amounts are unknown, reject placeholder-only item labels, keep concrete statement-only inputs visible for review, skip explicit no-ESS/not-applicable answers only when no ESS facts exist, preserve no-ESS decline signals across flat-only facts, item facts, and flat/nested merges when facts exist, keep field-specific n/a values out of no-ESS decline signals, keep no-ESS plus facts visible in answer/tab text, and keep unknown or malformed ESS amounts as Evidence instead of accountant review.",
    ),
    ReviewPattern(
        "Issue #50 complex payments",
        INDIVIDUAL_INTAKE_CONTRACT,
        "ETP, lump sum in arrears, super lump sum, and super income stream intake must use group-specific no-answer handling, skip explicit no only when no facts exist even when entered into any flat or nested payment source field, distinguish do/don't/dont-have payment denials from missing statement/payment-summary evidence, suppress standalone flat no-payment answers from workflow and base rows through nested-key mapping, preserve no-payment decline signals across flat-only facts and flat/nested merges when facts exist, keep field-specific n/a values out of no-payment decline signals, preserve zero amounts, keep no-plus-facts, unknown statements, unknown amounts, and malformed amounts as Evidence, and keep official-source-backed prep-only guidance aligned across runtime, docs, and portable skills.",
    ),
    ReviewPattern(
        "Issue #48 foreign income",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Foreign income intake must skip explicit no-income/employment/pension answers only when no facts exist even when entered into any flat or nested foreign-income source field, suppress standalone flat no-foreign answers from workflow and base rows through nested-key mapping, inspect item lists before decline matching treats a workflow as factless, preserve no-foreign-income decline signals across flat-only facts, item facts, and flat/nested merges when facts exist, keep field-specific n/a values out of no-foreign-income decline signals, let unknown or uncertain wording override decline matching, avoid no-tax-paid wording as a workflow decline, block tax-paid contexts before any no-income absence phrase, treat do/don't/dont-have income wording as no-income only when it is not tax-paid or statement/payment-summary context, block decline matching for all statement/payment-summary document contexts, keep no foreign income payment summary and no foreign employment statement as Evidence, match short decline tokens exactly, preserve nested and flat false foreign-income claim booleans once another signal renders the row, suppress standalone flat negative claim strings, never let nested false booleans or field-specific negative claim strings clear an existing flat true offset/exemption signal, do not let negative offset/exemption claim-only strings keep a no-income workflow alive, treat no-offset and no-foreign-income-tax-offset wording as negative offset claims, treat no-exemption and no-foreign-employment-exemption wording as negative exemption claims, preserve zero foreign tax paid for display, require positive foreign-tax-paid support for affirmative offset claims, keep no-plus-facts, missing statement phrases, unknown or malformed amounts, residency uncertainty, boolean, missing, malformed, zero, or negative exchange rates with numeric amounts, exchange-rate gaps, item-specific exchange-rate support for top-level totals, and top-level-vs-item total conflicts as Evidence, keep affirmative or ambiguous top-level offset claims without top-level or item-level positive foreign-tax-paid evidence as Evidence, require each explicit item-level offset claim to carry that item's own positive foreign-tax-paid evidence instead of using top-level or sibling tax-paid amounts to clear it, never add exchange rates together, require item-level statement evidence unless a valid top-level statement only covers omitted item statements, and keep all completed foreign income rows under Accountant review.",
    ),
    ReviewPattern(
        "Issue #51 PSI",
        INDIVIDUAL_INTAKE_CONTRACT,
        "PSI intake must skip explicit no-PSI answers only when no facts exist even when entered into any PSI prompt, distinguish do/don't/dont-have PSI denials from missing contract/invoice evidence, preserve no-PSI decline signals across flat/nested merges when facts exist, keep field-specific n/a values out of no-PSI decline signals, preserve zero income and false PSI test answers once another signal renders the row, keep no-PSI plus facts, missing contracts, malformed income, unknown or maybe/possibly/unclear tests, missing attribution, deductions, or structure facts as Evidence, never decide PSI treatment as final, and keep completed PSI rows under Accountant review.",
    ),
    ReviewPattern(
        "Issue #47 crypto CGT",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Crypto CGT intake must skip explicit no-crypto answers only when no facts exist even when entered into any crypto prompt, ignore standalone false default crypto booleans including serialized false/no/0/off/unchecked strings in base rows, preserve zero amounts and false transfer/business/private-use booleans once another signal renders the row, render item-level records and use context when top-level fields are missing, require both business and private use context flags before accountant review, accept textual yes/no/true/false/1/0/on/off/checked/unchecked business/private-use flags as complete context, let complete top-level business/private-use context satisfy omitted item use flags while explicit item uncertainty stays Evidence, preserve explicit item-level dates, exchange/wallet, transfer, records, ownership, business-use, and private-use context in item text even when top-level context is complete, keep conflicting top-level-vs-item business/private use flags as Evidence, let non-missing top-level crypto event, identity, wallet records, ownership, and transfer context satisfy omitted item context while explicit item denial/absence/uncertainty stays Evidence, require each item to satisfy amount/date/reward evidence under inherited top-level sale/exchange/reward event context without using top-level or sibling item amounts to clear that item, require each inherited transfer item to carry own-wallet support unless top-level support exists, preserve no-crypto decline signals across flat-only facts, same-field conflicts, and flat/nested merges when facts exist, preserve nested same-field facts for display and calculations when flat no-crypto answers conflict, keep field-specific absence values such as no staking rewards or date/record n/a out of no-crypto decline signals and item amount/date evidence loops, render amount-field no-crypto contradictions instead of hiding them as unknown, treat nested items as contradiction facts, keep top-level and per-item no-crypto plus facts, missing wallet records including natural no/missing/without record wording and do/don't/dont-have wallet or exchange record wording, do not treat unrelated record notes such as no-disposal notes as missing records, malformed amounts or dates, missing asset/exchange identity, missing per-item identity/dates/ownership context, top-level-vs-item total conflicts, item-specific quantity display/comparison when item quantities span different crypto assets, missing ownership, missing own-wallet support for transfer events, non-own-wallet transfer prep gaps including natural not-own-wallet wording and serialized false transfer flags, exchange/convert/conversion disposal-like prep gaps without treating own-wallet exchange transfers as disposals, transfer ambiguity including sentence-shaped maybe/possibly/unclear boolean wording, and missing either business or private use context as Evidence, never decide final CGT treatment, and keep completed crypto rows under Accountant review.",
    ),
    ReviewPattern(
        "Issue #45 rental property",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Rental intake must preserve explicit unknown, records-none, boolean-true amount, and missing-document answers as Evidence, calculate worksheet net from the same flat/item facts shown to the user only when supplied amount facts are parseable or clearly absent, exclude any amount that needs Evidence from field totals, worksheet net math, item net math, and private-use day completeness checks including raw or item net_loss evidence gaps, flag top-level-vs-item amount conflicts as reconciliation Evidence and block aggregate field/net math instead of letting top-level values discard itemized facts, reconcile top-level net-loss amounts against explicit item net-loss values or computed item net amounts before trusting them, reconcile explicit raw or item net-loss amounts against same-record income and expense components before trusting them, block computed worksheet net when private-use apportionment affects expense amounts and no explicit net-loss amount was supplied, keep mixed explicit/computed item net-loss math unknown when private-use apportionment affects expense amounts unless every item supplies an explicit usable net-loss amount, render item-level amount facts that affect worksheet math or review routing including other expenses, private days, available days, and net loss, preserve item-level missing-document amount text in item details, show inherited top-level ownership, private-use, and records facts in item details only when they do not contradict item-level private-use signals, treat true private-use apportionment as incomplete when private days are zero, available days are zero, or private days exceed available days, treat serialized false/no/n/0/off/unchecked and natural-language no-loss/profit net_loss answers as absent rather than malformed standalone worksheet facts, preserve Accountant review status and review-queue routing whenever rental review flags exist even if evidence gaps also exist, normalize positive net_loss fields as losses, require per-property income evidence before any aggregate-income short-circuit, keep standalone, item-level, and mixed net-loss flags visible before aggregate worksheet math, treat positive private-use days and serialized true/on/checked private-use answers as private-use review even when the boolean field is false, treat negated private-use and serialized false/off/unchecked holiday-home text as false without adding private-use review, keep uncertain private-use wording including maybe/possibly/unclear/not clear as Evidence, and keep completed rental rows under Accountant review.",
    ),
    ReviewPattern(
        "PR #38",
        LOCAL_PLUGIN_MARKETPLACE_CONTRACT,
        "Local Codex plugin setup docs must point codex plugin marketplace add at the repo root when .agents/plugins/marketplace.json uses source.path ./.",
    ),
    ReviewPattern(
        "Issue #79 output docs",
        OUTPUT_DOCS_CONTRACT,
        "README and install docs must describe portable-vs-runtime output, HTML-only prep handoff sections, screenshot refresh commands, synthetic data, manual-copy boundaries, and the docs-update rule for user-facing output changes.",
    ),
    ReviewPattern(
        "Release guardrails",
        RELEASE_GUARDRAIL_CONTRACT,
        "Release workflow edits must preserve green-CI checks, unchanged-main checks, version manifest alignment, and the Release Please bootstrap SHA.",
    ),
]


def repo_root() -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if candidate.joinpath(ROOT_MARKER).exists():
            return candidate
    return Path.cwd()


def read(root: Path, rel: str) -> str:
    return root.joinpath(rel).read_text(encoding="utf-8")


def read_optional(root: Path, rel: str) -> str:
    path = root.joinpath(rel)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def contains_in_order(text: str, tokens: Iterable[str]) -> bool:
    offset = 0
    for token in tokens:
        found = text.find(token, offset)
        if found < 0:
            return False
        offset = found + len(token)
    return True


def missing_tokens(text: str, tokens: Iterable[str]) -> List[str]:
    return [token for token in tokens if token not in text]


def fail_if_missing(check: str, text: str, tokens: Iterable[str]) -> List[Finding]:
    missing = missing_tokens(text, tokens)
    if missing:
        return [Finding(check, "missing: " + ", ".join(missing))]
    return []


def fail_if_file_missing(root: Path, check: str, rel: str, tokens: Iterable[str]) -> List[Finding]:
    return fail_if_missing(check, read(root, rel), tokens)


def command_lines(text: str) -> List[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def wrong_local_marketplace_commands(commands: Iterable[str]) -> List[str]:
    return [
        command
        for command in commands
        if command.startswith(MARKETPLACE_ADD_PREFIX) and command != LOCAL_MARKETPLACE_ADD_COMMAND
    ]


def check_taxpack_output_layer_text(text: str) -> List[Finding]:
    findings: List[Finding] = []
    required = [
        "def scalar_text(",
        "def text_value(",
        "def source_urls(",
        "def render_provenance(",
        "def is_review_like_key(",
        "def effective_status_kind(",
        "def effective_tab_kind(",
        "def review_text(",
        "def queue_item_text(",
        "def render_review_queue(items: List[str])",
        '<ul class="review-list">',
        "def tab_title(item: GuideItem, row_index: int)",
        "return \"Evidence queue\"",
        "return \"Missing facts queue\"",
        "fallback_tab_text(item.number, effective_status_kind(item))",
        "def row_anchor(item: GuideItem, row_index: int)",
        "render_queue(\"Missing facts queue\", data.missing_facts, 400)",
        "render_queue(\"Evidence queue\", data.evidence_items, 500)",
        "def render_queue(title: str, items: List[GuideItem], offset: int)",
        "data-anchor=\"{row_anchor(item, offset + index)}",
        "def rendered_tab_items(",
        "data.abn_items",
        "data.bas_items",
        "data.missing_facts",
        "data.evidence_items",
        "400 + index",
        "500 + index",
        "for item, row_index in tab_items",
        "findTarget(spread,value)",
        "el.dataset.anchor===value",
        "default_generated_date()",
        "canonical_status(item_status_kind)",
        "def malformed_section_item(",
        "def malformed_extraction_row(",
        "def extraction_status_kind(",
        "if raw.get(\"confirmed\") is True:",
    ]
    findings.extend(fail_if_missing(TAXPACK_OUTPUT_LAYER, text, required))
    forbidden = [
        'querySelector(`[data-anchor="${',
        "querySelector('[data-anchor=\"' +",
        'querySelector("[data-anchor=\\"" +',
        '"generated_date":',
        " or \"\"",
        " or ''",
        "review_queue = \"; \".join",
    ]
    hits = [token for token in forbidden if token in text]
    if hits:
        findings.append(Finding(TAXPACK_OUTPUT_LAYER, "forbidden pattern: " + ", ".join(hits)))
    return findings


def check_taxpack_output_layer(root: Path) -> List[Finding]:
    return check_taxpack_output_layer_text(read(root, "scripts/taxmate_taxpack.py"))


def check_individual_intake_contract(root: Path) -> List[Finding]:
    text = read(root, "scripts/taxmate_intake.py")
    skill_text = read_optional(root, "skills/individual-return/SKILL.md")
    skill_rules = read_optional(root, "skills/individual-return/references/rules.md")
    findings: List[Finding] = []
    route_line = ""
    for line in skill_text.splitlines():
        if "Route tax-treatment decisions" in line:
            route_line = line
            break
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            route_line,
            [
                "`payg-employer`",
                "`abn-business`",
                "`gst-bas`",
                "`employment-deductions`",
                "`work-from-home`",
                "`private-health-medicare`",
                "`superannuation`",
                "`shares-etfs-managed-funds`",
                "`capital-gains-tax`",
                "`crypto-assets`",
                "`property-rental-cgt`",
                "`records-evidence`",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            text,
            [
                "def contains_unknown(",
                "\"uncertain\"",
                "STATE_ALIASES = {",
                "WEEKDAY_ALIASES = {",
                "def normalize_state(",
                "def wfh_answers(",
                "def has_abn_inputs(",
                "def has_bas_inputs(",
                "def parse_gst_registration(",
                "def base_item_status(",
                "def should_render_base_item(",
                "REVIEWABLE_COMPLEX_FIELDS = (",
                "isinstance(value, (dict, list))",
                "key in REVIEWABLE_ABN_FIELDS or key in REVIEWABLE_BAS_FIELDS or key == \"gst_registered\"",
                "items.extend(wfh_rows(wfh_answers(answers)))",
                "items.extend(asset_rows(asset_answers(answers)))",
                "gst_registered = answers.get(\"gst_registered\")",
                "gst_status = parse_gst_registration(gst_registered)",
                "unknown_as_missing=True",
                "math.isfinite(amount)",
                "raise ValueError(f\"invalid money value: {value}\") from None",
                "phrase in lowered",
                '"not confirmed"',
                "confirmed = raw.get(\"confirmed\") is True",
                '"confirmed": confirmed',
                "def extraction_status(",
                "def contains_review_status(",
                'taxmate_taxpack.known_kind(value) == "review"',
                "def preserve_review_kinds(",
                "for key in (\"status\", \"status_kind\", \"tab_kind\")",
                "for key in (\"status_kind\", \"tab_kind\")",
                "row[key] = raw.get(key)",
                "state_key = normalize_state(enriched.get(\"state\"))",
                "if state_key is not None:",
                "enriched[\"income_year\"] = text(answers.get(\"income_year\"), DEFAULT_INCOME_YEAR)",
                "state_key = normalize_state(raw.get(\"state\"))",
                "if state_key is None:",
                "state_key = normalize_state(state)",
                "def normalize_state(value: Any) -> Optional[str]:",
                "SUPPORTED_WFH_START = date(2025, 7, 1)",
                "SUPPORTED_WFH_END = date(2026, 6, 30)",
                "LIMITED_PUBLIC_HOLIDAYS_BY_STATE = {",
                '"NSW": {"2025-08-04"}',
                '"TAS": {"2025-10-23", "2025-11-03", "2026-02-09", "2026-04-07"}',
                '"VIC": {"2025-09-26", "2026-03-09", "2026-04-04", "2026-04-05", "2026-06-08"}',
                '"NSW": {"2025-10-06", "2026-04-04", "2026-04-05", "2026-04-27", "2026-06-08"}',
                '"QLD": {"2025-10-06", "2026-04-04", "2026-04-05", "2026-05-04"}',
                '"SA": {"2025-10-06", "2026-03-09", "2026-04-04", "2026-04-05", "2026-06-08"}',
                '"TAS": {"2026-03-09", "2026-06-08"}',
                '"WA": {"2026-03-02", "2026-04-05", "2026-04-27", "2026-06-01"}',
                '"ACT": {"2025-10-06", "2026-03-09", "2026-04-04", "2026-04-05", "2026-04-27", "2026-06-01", "2026-06-08"}',
                '"NT": {"2025-08-04", "2026-04-04", "2026-04-05", "2026-05-04", "2026-06-08"}',
                "https://www.fairwork.gov.au/employment-conditions/public-holidays/2025-public-holidays",
                "https://www.fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays",
                "*PUBLIC_HOLIDAY_SOURCES",
                "holiday_not_worked = current in holidays and current not in worked_public",
                "holiday_worked = current in worked_public",
                "limited_holidays = limited_public_holidays(state_key)",
                "def limited_public_holidays(",
                "def limited_public_holiday_may_affect_period(",
                "if \"start\" not in raw or \"end\" not in raw:",
                "start = parse_iso_date(raw.get(\"start\"))",
                "end = parse_iso_date(raw.get(\"end\"))",
                "if not supported_wfh_income_year(raw):",
                "if not dates_within_supported_income_year(start, end):",
                "def supported_wfh_income_year(",
                "def dates_within_supported_income_year(",
                "weekdays = parse_weekdays(raw)",
                "if weekdays is None:",
                "def parse_weekdays(",
                '"weekdays" not in raw',
                "parsed_day = parse_weekday(day)",
                "if parsed_day is None:",
                "def parse_weekday(",
                "hours_per_day = money_value(raw.get(\"hours_per_day\"), unknown_as_missing=True)",
                "hours_per_day is None or hours_per_day <= 0 or hours_per_day > 24",
                "def has_complete_wfh_records(",
                "def wfh_fixed_rate_candidate(",
                "fixed_candidate = wfh_fixed_rate_candidate(hours, raw)",
                "actual_cost_record_value = raw.get(\"actual_cost_records\")",
                "or is_missing(actual_cost_record_value)",
                "if leave is None or worked_public is None or worked_weekends is None:",
                "fixed_rate_text = money_text(fixed_candidate)",
                "def wfh_adjustment_dates(",
                "required_keys = (\"leave_dates\", \"worked_public_holidays\", \"worked_weekends\")",
                "def valid_wfh_adjustment_dates(",
                "day not in holidays for day in worked_public",
                "day.weekday() < 5 for day in worked_weekends",
                "def asset_answers(",
                "if isinstance(raw_assets, list) and has_meaningful_value(raw_assets):",
                "work_use != 100",
                "mixed-use",
                "ATO_ESS_SOURCE = \"https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/employee-share-schemes\"",
                "ATO_ESS_STATEMENT_SOURCE = \"https://www.ato.gov.au/forms-and-instructions/employee-share-scheme-statement\"",
                "REVIEWABLE_ESS_FIELDS = (",
                "ESS_AMOUNT_FIELDS = (",
                "ESS_FLAT_AMOUNT_FIELDS = tuple(f\"ess_{field}\" for field in ESS_AMOUNT_FIELDS)",
                "ESS_ITEM_SIGNAL_FIELDS = (\"employer\"",
                "ESS_STATEMENT_MISSING_PHRASES = (",
                "\"statement not received\"",
                "\"do not have\"",
                "ESS_DECLINE_PHRASES = (",
                "GENERIC_FIELD_ABSENCE_PHRASES = (",
                "\"no employee share scheme\"",
                "\"not applicable\"",
                "def has_meaningful_value(",
                "if isinstance(value, bool):",
                "return True",
                "if spec.key in ESS_FLAT_AMOUNT_FIELDS and isinstance(value, bool):",
                "ess_source_declines_workflow(spec.key.removeprefix(\"ess_\"), value)",
                "ess_field_absence_value(spec.key.removeprefix(\"ess_\"), value)",
                "return spec.required or has_meaningful_value(value)",
                "if key == \"ess_statement\" and ess_statement_missing(value):",
                "if key in ESS_FLAT_AMOUNT_FIELDS and ess_amount_malformed(value):",
                "if not has_meaningful_value(raw):",
                "not has_meaningful_value(enriched.get(\"records\"))",
                "not has_meaningful_value(enriched.get(\"state\"))",
                "if not has_meaningful_value(asset):",
                "if not has_meaningful_value(value):",
                "not has_meaningful_value(raw)",
                "ess_taxed_upfront_discount",
                "ess_deferred_discount",
                "ess_foreign_source_discount",
                "ess_tfn_amount_withheld",
                "items.extend(ess_rows(ess_answers(answers)))",
                "def ess_answers(",
                "flat_values = {key: value for key, value in fields.items() if has_meaningful_ess_flat_value(key, value)}",
                "ESS_DECLINE_SIGNAL_KEY",
                "def has_meaningful_ess_flat_value(",
                "def ess_values_with_declines(",
                "def ess_decline_values(",
                "def ess_has_facts(",
                "def ess_decline_contradiction(",
                "def ess_decline_signal_text(",
                "merged = dict(flat_values)",
                "has_explicit_ess_evidence_gap(key, value)",
                "def ess_rows(",
                "statement_evidence = ess_statement_missing(statement) or ess_items_need_statement_evidence(items)",
                "amount_conflict = ess_amount_conflict(raw, items)",
                "amount_evidence = ess_amounts_need_evidence(raw, items)",
                "tab_text = ess_tab_text(statement_evidence, amount_conflict, amount_evidence, decline_evidence)",
                "def ess_item_values(",
                "def has_meaningful_ess_item(",
                "any(ess_amount_needs_evidence(item.get(key)) for key in ESS_AMOUNT_FIELDS)",
                "def has_meaningful_ess_signal(",
                "if contains_unknown(value):\n        return False",
                "def has_meaningful_ess_override(",
                "if key == \"items\":\n        return bool(ess_item_values(value))",
                "key in ESS_AMOUNT_FIELDS and isinstance(value, bool)",
                "def has_explicit_ess_evidence_gap(",
                "def ess_amount_value(",
                "def ess_item_amount_total(",
                "def ess_amount_conflict(",
                "def ess_amounts_need_evidence(",
                "ess_amount_needs_evidence(raw.get(key))",
                "ess_amount_needs_evidence(item.get(key))",
                "def ess_amount_needs_evidence(",
                "return contains_unknown(value) or ess_amount_malformed(value)",
                "def ess_amount_malformed(",
                "def ess_money_value(",
                "except ValueError:",
                "return None",
                "def ess_tab_text(",
                "ESS top-level and item amounts conflict; correct ESS amount totals before accountant review.",
                "no-ESS answer with ESS facts",
                "ESS discounts need ESS statement evidence and numeric amount evidence before accountant review.",
                "ESS amount fields need numeric evidence before accountant review.",
                "def ess_statement_missing(",
                "if isinstance(statement, bool):",
                "return not statement",
                "if ess_statement_declines_workflow(statement):",
                "return any(phrase in lowered for phrase in ESS_STATEMENT_MISSING_PHRASES)",
                "def ess_items_need_statement_evidence(",
                "return any(ess_statement_missing(item.get(\"statement\")) for item in items)",
                "def ess_items_text(",
                "def ess_employer_text(",
                "def ess_label_text(",
                "def ess_display_text(",
                "ess_field_absence_value(key, raw.get(key))",
                "def has_ess_inputs(",
                "if has_meaningful_ess_statement(raw.get(\"statement\")):",
                "has_explicit_ess_evidence_gap(key, raw.get(key))",
                "def has_meaningful_ess_statement(",
                "return not ess_statement_declines_workflow(value)",
                "def ess_statement_declines_workflow(",
                "def ess_source_declines_workflow(",
                "REVIEWABLE_INVESTMENT_FIELDS = (",
                "INVESTMENT_INTEREST_AMOUNT_FIELDS = (\"amount\", \"tfn_withheld\")",
                "INVESTMENT_DIVIDEND_AMOUNT_FIELDS = (\"franked_amount\", \"unfranked_amount\", \"franking_credit\", \"tfn_withheld\")",
                "INVESTMENT_DISTRIBUTION_AMOUNT_FIELDS = (",
                "INVESTMENT_TRUST_AMOUNT_FIELDS = (",
                "INVESTMENT_SOURCES = [",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/investment-income",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/investing-in-bank-accounts-and-income-bonds",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals",
                "investment = investment_answers(answers)",
                "items.extend(investment_rows(investment, answers))",
                "rows.extend(investment_evidence_rows(investment_answers(answers), answers))",
                "def investment_answers(",
                "def investment_rows(",
                "def investment_interest_row(",
                "def investment_dividend_row(",
                "def investment_distribution_row(",
                "def investment_trust_row(",
                "def investment_reconciliation_row(",
                "def investment_evidence_rows(",
                "def first_investment_items(",
                "def investment_statement_missing(",
                "def investment_franking_uncertain(",
                "def investment_total_conflict(",
                "def dividend_distribution_total(",
                "def first_present(",
                "foreign components {display_value(item.get('foreign_components'))}",
                "TFN withholding {money_text(investment_money_value(item.get('tfn_withheld')))}",
                "franking credit {money_text(investment_money_value(item.get('franking_credit')))}",
                "Trust distribution routing for individual beneficiary",
                "TaxMate does not prepare a trust return",
                "Investment totals need corrected reconciliation",
                "def ess_field_absence_value(",
                "return lowered in ESS_DECLINE_PHRASES",
                "def has_meaningful_ess_value(",
                "if isinstance(value, list):",
                "return any(has_meaningful_value(item) for item in value)",
                "taxed-upfront discount",
                "deferred discount",
                "foreign-source discount",
                "TFN amount withheld",
                "ESS discounts need the ESS statement",
                "ATO_ETP_SOURCE = \"https://www.ato.gov.au/tax-rates-and-codes/payg-withholding-schedule-11-tax-table-for-employment-termination-payments\"",
                "ATO_LUMP_SUM_ARREARS_SOURCE = \"https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/lump-sum-payment-in-arrears\"",
                "ATO_SUPER_PENSIONS_SOURCE = \"https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/superannuation-pensions-and-annuities\"",
                "ATO_SUPER_LUMP_SUM_SOURCE = \"https://www.ato.gov.au/tax-rates-and-codes/schedule-12-tax-table-for-superannuation-lump-sums\"",
                "ATO_SUPER_STREAM_SOURCE = \"https://www.ato.gov.au/tax-rates-and-codes/schedule-13-tax-table-for-superannuation-income-streams\"",
                "REVIEWABLE_COMPLEX_PAYMENT_FIELDS = (",
                "COMPLEX_PAYMENT_STATEMENT_FLAT_FIELDS = (",
                "COMPLEX_PAYMENT_FLAT_FIELD_GROUPS = {",
                "COMPLEX_PAYMENT_FLAT_FIELD_KEYS = {",
                "COMPLEX_PAYMENT_AMOUNT_FIELDS = (",
                "COMPLEX_PAYMENT_SOURCE_KEY_FACTS = (",
                "COMPLEX_PAYMENT_FLAT_AMOUNT_FIELDS = (",
                "COMPLEX_PAYMENT_STATEMENT_MISSING_PHRASES = (",
                "\"statement not received\"",
                "\"do not have\"",
                "\"dont have\"",
                "COMPLEX_PAYMENT_DECLINE_PHRASES_BY_GROUP = {",
                "items.extend(complex_payment_rows(complex_payment_answers(answers)))",
                "if spec.key in COMPLEX_PAYMENT_FLAT_AMOUNT_FIELDS and isinstance(value, bool):",
                "if spec.key in REVIEWABLE_COMPLEX_PAYMENT_FIELDS and complex_payment_flat_value_is_absent(",
                "if key in REVIEWABLE_COMPLEX_PAYMENT_FIELDS:",
                "def complex_payment_flat_value_is_absent(",
                "def complex_payment_flat_field_key(",
                "complex_payment_source_declines_workflow(nested_key, value, group)",
                "complex_payment_field_absence_value(",
                "def complex_payment_answers(",
                "def merge_payment_answers(",
                "def complex_payment_rows(",
                "def etp_rows(",
                "def lump_sum_arrears_rows(",
                "def super_income_rows(",
                "def has_complex_payment_inputs(",
                "PAYMENT_DECLINE_SIGNAL_KEY",
                "def payment_decline_values(",
                "def payment_values_with_declines(",
                "def payment_declines_without_facts(",
                "def payment_decline_contradiction(",
                "def payment_decline_signal_text(",
                "def has_meaningful_payment_signal(",
                "def has_explicit_payment_evidence_gap(",
                "def complex_payment_statement_missing(",
                "phrase in lowered for phrase in COMPLEX_PAYMENT_STATEMENT_MISSING_PHRASES",
                "def complex_payment_declines_workflow(",
                "def complex_payment_absence_decline_phrase(",
                "def complex_payment_document_context(",
                "def complex_payment_source_declines_workflow(",
                "def complex_payment_field_absence_value(",
                "def payment_amounts_need_evidence(",
                "def complex_payment_amount_needs_evidence(",
                "def complex_payment_amount_malformed(",
                "def complex_payment_money_value(",
                "def complex_payment_display_text(",
                "complex_payment_field_absence_value(key, raw.get(key), group)",
                "def complex_payment_tab_text(",
                "def lump_sum_arrears_tab_text(",
                "{label} needs statement evidence and numeric amount evidence before accountant review.",
                "{label} amount fields need numeric amount evidence before accountant review.",
                "prior-year allocation evidence",
                "{label} needs source-backed accountant review.",
                "Employment termination payments",
                "Lump sum payment in arrears",
                "Superannuation lump sum or income stream",
                "ATO_FOREIGN_WORLDWIDE_SOURCE = \"https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income\"",
                "ATO_FOREIGN_RESIDENT_INCOME_SOURCE = \"https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/australian-resident-for-tax-purposes-foreign-and-worldwide-income\"",
                "ATO_FOREIGN_TEMP_RESIDENT_SOURCE = \"https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/foreign-and-temporary-resident-income\"",
                "ATO_FOREIGN_EMPLOYMENT_EXEMPT_SOURCE = \"https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/tax-exempt-income-from-foreign-employment\"",
                "ATO_FOREIGN_INCOME_TAX_OFFSET_SOURCE = \"https://www.ato.gov.au/forms-and-instructions/foreign-income-tax-offset-rules-guide-2026\"",
                "REVIEWABLE_FOREIGN_INCOME_FIELDS = (",
                "FOREIGN_INCOME_AMOUNT_FIELDS = (",
                "FOREIGN_INCOME_FLAT_AMOUNT_FIELDS = (",
                "FOREIGN_INCOME_SIGNAL_FIELDS = (",
                "FOREIGN_INCOME_SOURCE_KEY_FACTS = FOREIGN_INCOME_SIGNAL_FIELDS",
                "FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS = (\"foreign_tax_offset_claim\", \"foreign_employment_exempt_claim\")",
                "FOREIGN_INCOME_FLAT_BOOLEAN_FIELDS = (\"foreign_income_tax_offset_claim\", \"foreign_employment_exempt_claim\")",
                "FOREIGN_INCOME_FLAT_FIELD_KEYS = {",
                "FOREIGN_INCOME_STATEMENT_MISSING_PHRASES = (",
                "\"no foreign pension statement\"",
                "FOREIGN_INCOME_DECLINE_PHRASES = (",
                "\"no foreign income\"",
                "\"statement not received\"",
                "\"do not have\"",
                "\"dont have\"",
                "items.extend(foreign_income_rows(foreign_income_answers(answers)))",
                "if spec.key in REVIEWABLE_FOREIGN_INCOME_FIELDS and foreign_income_flat_value_is_absent(spec.key, value):",
                "if spec.key in FOREIGN_INCOME_FLAT_BOOLEAN_FIELDS and foreign_income_negative_claim_signal(",
                "foreign_income_nested_claim_key(spec.key)",
                "def foreign_income_flat_value_is_absent(",
                "def foreign_income_flat_field_key(",
                "foreign_income_source_declines_workflow(nested_key, value)",
                "def foreign_income_answers(",
                "def has_meaningful_foreign_income_flat_value(",
                "if key in FOREIGN_INCOME_AMOUNT_FIELDS and isinstance(value, bool):",
                "if foreign_income_should_ignore_boolean_signal(merged, key, value):",
                "if foreign_income_should_merge_boolean_signal(merged, key, value):",
                "merged[key] = value",
                "def foreign_income_should_merge_boolean_signal(",
                "return not foreign_income_should_ignore_boolean_signal(merged, key, value)",
                "def foreign_income_should_ignore_boolean_signal(",
                "foreign_income_positive_claim_signal(key, merged.get(key))",
                "def foreign_income_positive_claim_signal(",
                "def foreign_income_exemption_claimed(",
                "def foreign_income_negative_claim_signal(",
                "def foreign_income_nested_claim_key(",
                "def foreign_income_claim_negative(",
                "def foreign_income_exemption_claim_negative(",
                "def foreign_income_rows(",
                "exchange_rate = foreign_income_summary_exchange_rate_text(raw, items)",
                "statement_evidence = foreign_income_statement_evidence(raw, items)",
                "def foreign_income_item_values(",
                "def has_meaningful_foreign_income_item(",
                "def has_meaningful_foreign_income_override(",
                "def has_meaningful_foreign_income_signal(",
                "if key in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS and isinstance(value, bool):",
                "return value",
                "if key in FOREIGN_INCOME_BOOLEAN_SIGNAL_FIELDS and foreign_income_claim_negative(key, value):",
                "return False",
                "def has_explicit_foreign_income_evidence_gap(",
                "def has_foreign_income_inputs(",
                "def foreign_income_declines_without_facts(",
                "FOREIGN_INCOME_DECLINE_SIGNAL_KEY",
                "def foreign_income_decline_values(",
                "def foreign_income_values_with_declines(",
                "def foreign_income_has_facts(",
                "def foreign_income_decline_contradiction(",
                "def foreign_income_decline_signal_text(",
                "if foreign_income_item_values(raw.get(\"items\")):",
                "def foreign_income_statement_missing(",
                "def foreign_income_source_declines_workflow(",
                "def foreign_income_field_absence_value(",
                "phrase in lowered for phrase in FOREIGN_INCOME_STATEMENT_MISSING_PHRASES",
                "def foreign_income_declines_workflow(",
                "if contains_unknown(statement):",
                "if foreign_income_decline_phrase_is_tax_paid_context(lowered):",
                "if foreign_income_absence_decline_phrase(lowered):",
                "if foreign_income_document_context(lowered):",
                "return False",
                "def foreign_income_absence_decline_phrase(",
                "foreign_income_document_context(lowered) or foreign_income_decline_phrase_is_tax_paid_context(lowered)",
                "\"do not have any foreign income\"",
                "\"dont have any foreign income\"",
                "def foreign_income_document_context(",
                "def foreign_income_document_denial_phrase(",
                "def foreign_income_document_positive_phrase(",
                "lowered.startswith((\"no \", \"without \", \"missing \"))",
                "def foreign_income_decline_phrase_matches(",
                "def foreign_income_decline_phrase_is_tax_paid_context(",
                "\"no foreign income tax\" in lowered",
                "if phrase in {\"na\", \"n/a\"}:",
                "return lowered == phrase",
                "def foreign_income_statement_evidence(",
                "def foreign_income_items_need_statement_evidence(",
                "def foreign_income_items_have_explicit_statement_gap(",
                "def foreign_income_residency_needs_evidence(",
                "def foreign_income_tax_paid_needs_evidence(",
                "raw_has_tax_paid = foreign_income_raw_has_tax_paid(raw)",
                "foreign_income_offset_claim_needs_tax_paid(item.get(\"foreign_tax_offset_claim\"))",
                "not raw_has_tax_paid",
                "not foreign_income_has_tax_paid_value(item.get(\"foreign_tax_paid\"))",
                "def foreign_income_raw_has_tax_paid(",
                "def foreign_income_items_have_tax_paid(",
                "def foreign_income_has_tax_paid_value(",
                "return amount > 0",
                "def foreign_income_offset_claimed(",
                "def foreign_income_offset_claim_needs_tax_paid(",
                "return has_meaningful_value(value) and not foreign_income_offset_claim_negative(value)",
                "def foreign_income_offset_claim_negative(",
                "\"no offset\"",
                "\"no foreign income tax offset\"",
                "\"no exemption\"",
                "\"no foreign employment exemption\"",
                "phrase in lowered for phrase in",
                "def foreign_income_amounts_need_evidence(",
                "if foreign_income_amount_values_conflict(raw, items):",
                "def foreign_income_amount_values_conflict(",
                "def foreign_income_amount_value_conflicts(",
                "def foreign_income_exchange_rate_missing(",
                "if foreign_income_exchange_rate_missing(raw, items):",
                "item_rate_gap = any(",
                "if foreign_income_items_have_exchange_rate_support(items):",
                "return foreign_income_exchange_rate_invalid_when_present(raw.get(\"exchange_rate\"))",
                "def foreign_income_items_have_exchange_rate_support(",
                "def foreign_income_exchange_rate_invalid_when_present(",
                "def foreign_income_exchange_rate_needs_evidence(",
                "if is_missing(value) or isinstance(value, bool) or contains_unknown(value):",
                "rate = foreign_income_money_value(value)",
                "return rate is None or rate <= 0",
                "def foreign_income_amount_needs_evidence(",
                "def foreign_income_amount_malformed(",
                "def foreign_income_money_value(",
                "def foreign_income_amount_value(",
                "def foreign_income_summary_exchange_rate_text(",
                "def foreign_income_record_field_text(",
                "foreign_income_field_absence_value(key, record.get(key))",
                "return \"item-specific\"",
                "def foreign_income_field_text(",
                "def foreign_income_claim_text(",
                "def foreign_income_items_text(",
                "def foreign_income_tab_text(",
                "residency or temporary-resident evidence",
                "foreign tax paid evidence",
                "Foreign and worldwide income",
                "ATO_PSI_SOURCE = \"https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income\"",
                "REVIEWABLE_PSI_FIELDS = (",
                "PSI_AMOUNT_FIELDS = (\"income\",)",
                "PSI_FLAT_AMOUNT_FIELDS = (\"psi_income\",)",
                "PSI_BOOLEAN_FIELDS = (",
                "BOOLEAN_UNCERTAIN_PHRASES",
                "PSI_FLAT_BOOLEAN_FIELDS = (",
                "PSI_DECLINE_PHRASES = (",
                "\"occupation\"",
                "\"client\"",
                "\"no personal services income\"",
                "items.extend(psi_rows(psi_answers(answers)))",
                "if spec.key in PSI_FLAT_AMOUNT_FIELDS and isinstance(value, bool):",
                "psi_source_declines_workflow(spec.key.removeprefix(\"psi_\"), value)",
                "psi_field_absence_value(spec.key.removeprefix(\"psi_\"), value)",
                "if key in REVIEWABLE_PSI_FIELDS:",
                "def psi_answers(",
                "PSI_DECLINE_SIGNAL_KEY",
                "def psi_values_with_declines(",
                "def psi_decline_values(",
                "def psi_has_facts(",
                "def psi_decline_contradiction(",
                "def psi_rows(",
                "status = \"Evidence\" if evidence else \"Accountant review\"",
                "PSI tests, attribution, deductions, and structure workflow",
                "def has_meaningful_psi_flat_value(",
                "if key in PSI_AMOUNT_FIELDS and isinstance(value, bool):",
                "psi_source_declines_workflow(key, value)",
                "def has_meaningful_psi_override(",
                "def has_explicit_psi_evidence_gap(",
                "psi_field_absence_value(key, value)",
                "def has_psi_inputs(",
                "def psi_declines_without_facts(",
                "def has_meaningful_psi_signal(",
                "if key in PSI_SIGNAL_FIELDS and (psi_source_declines_workflow(key, value) or psi_field_absence_value(key, value)):",
                "def psi_evidence_gaps(",
                "numeric income evidence",
                "contract or invoice evidence",
                "80% client concentration test",
                "attribution evidence",
                "business structure evidence",
                "def psi_contract_evidence_missing(",
                "def psi_declines_workflow(",
                "def psi_source_declines_workflow(",
                "def psi_field_absence_value(",
                "if psi_document_context(lowered):",
                "\"do not have personal services income\"",
                "def psi_document_context(",
                "if lowered in PSI_DECLINE_PHRASES:",
                "def psi_test_needs_evidence(",
                "boolean_answer_needs_evidence(value)",
                "def psi_amount_needs_evidence(",
                "if psi_declines_workflow(value):",
                "def psi_amount_malformed(",
                "def psi_money_value(",
                "def psi_bool_text(",
                "def psi_display_text(",
                "psi_field_absence_value(key, raw.get(key))",
                "ATO_CRYPTO_ASSETS_SOURCE = \"https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments\"",
                "ATO_CRYPTO_RECORDS_SOURCE = \"https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments/keeping-crypto-records\"",
                "ATO_CRYPTO_BUSINESS_SOURCE = \"https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/crypto-assets-and-business\"",
                "REVIEWABLE_CRYPTO_FIELDS = (",
                "CRYPTO_AMOUNT_FIELDS = (",
                "CRYPTO_FLAT_AMOUNT_FIELDS = (",
                "CRYPTO_DATE_FIELDS = (",
                "CRYPTO_FLAT_DATE_FIELDS = (",
                "CRYPTO_BOOLEAN_FIELDS = (",
                "CRYPTO_USE_CONTEXT_FIELDS = (",
                "CRYPTO_FLAT_BOOLEAN_FIELDS",
                "CRYPTO_IDENTITY_FIELDS = (",
                "CRYPTO_ITEM_PARENT_CONTEXT_FIELDS = (",
                "CRYPTO_DECLINE_PHRASES = (",
                "CRYPTO_FIELD_ABSENCE_PHRASES = (",
                "CRYPTO_DECLINE_SIGNAL_KEY",
                "\"no crypto assets\"",
                "BOOLEAN_UNCERTAIN_PHRASES",
                "items.extend(crypto_rows(crypto_answers(answers)))",
                "if spec.key in CRYPTO_FLAT_AMOUNT_FIELDS and isinstance(value, bool):",
                "if spec.key in CRYPTO_FLAT_BOOLEAN_FIELDS and crypto_boolean_false(value):",
                "crypto_source_declines_workflow(spec.key.removeprefix(\"crypto_\"), value)",
                "crypto_field_absence_value(spec.key.removeprefix(\"crypto_\"), value)",
                "if key in REVIEWABLE_CRYPTO_FIELDS:",
                "def crypto_answers(",
                "def crypto_rows(",
                "Crypto disposals, swaps, exchanges, conversions, rewards, transfers, wallet records, and cost-base workflow",
                "def has_meaningful_crypto_flat_value(",
                "if key in CRYPTO_AMOUNT_FIELDS and isinstance(value, bool):",
                "crypto_source_declines_workflow(key, value)",
                "crypto_field_absence_value(key, value)",
                "def has_meaningful_crypto_override(",
                "def has_explicit_crypto_evidence_gap(",
                "\"exchange_or_wallet\", \"asset\"",
                "def crypto_values_with_declines(",
                "if not crypto_has_field_value(merged, key):",
                "def crypto_decline_values(",
                "def crypto_item_values(",
                "def has_meaningful_crypto_item(",
                "def crypto_amount_field_needs_evidence(",
                "def crypto_date_field_needs_evidence(",
                "value = record.get(key)",
                "not crypto_field_absence_value(key, value)",
                "def has_crypto_inputs(",
                "def crypto_has_facts(",
                "def crypto_declines_without_facts(",
                "def has_meaningful_crypto_signal(",
                "if key in CRYPTO_BOOLEAN_FIELDS:",
                "if crypto_boolean_true(value):",
                "if crypto_boolean_false(value):",
                "def crypto_evidence_gaps(",
                "asset and exchange/wallet identity evidence",
                "per-item crypto evidence",
                "top-level and item amount reconciliation",
                "wallet or exchange records",
                "numeric proceeds, cost-base, quantity, or rewards evidence",
                "def crypto_event_is_disposal(",
                "def crypto_record_disposal_like(",
                "\"exchange\"",
                "\"convert\"",
                "\"conversion\"",
                "BOOLEAN_UNCERTAIN_PHRASES",
                "business/private use context",
                "def boolean_answer_needs_evidence(",
                "def crypto_use_context_complete(",
                "def crypto_use_context_conflicts(",
                "def crypto_item_use_context_conflicts(",
                "def crypto_boolean_complete(",
                "def crypto_boolean_value(",
                "def crypto_items_need_evidence(",
                "def crypto_item_needs_evidence(",
                "def crypto_item_context_field_needs_evidence(",
                "def crypto_item_records_need_evidence(",
                "def crypto_item_amounts_need_evidence(",
                "def crypto_item_dates_need_evidence(",
                "def crypto_item_disposal_like(",
                "def crypto_item_reward_like(",
                "def crypto_item_effective_value(",
                "def crypto_item_transfer_needs_evidence(",
                "crypto_item_effective_value(raw, item, \"event_type\")",
                "def crypto_item_use_context_needs_evidence(",
                "if crypto_use_context_complete(raw):",
                "crypto_item_records_need_evidence(raw, item)",
                "return not crypto_has_field_value(raw, key)",
                "return not crypto_has_field_value(raw, \"wallet_records\")",
                "def crypto_amount_conflicts(",
                "def crypto_decline_contradiction(",
                "def crypto_declines_with_facts(",
                "def crypto_bool_field_text(",
                "def crypto_item_context_text(",
                "acquired {crypto_record_field_text(item, 'acquired_date')",
                "(\"exchange_or_wallet\", \"exchange/wallet\")",
                "crypto_field_text(raw, items, 'wallet_records')",
                "def crypto_amount_field_text(",
                "def crypto_item_amount_text(",
                "def crypto_record_field_text(",
                "crypto_field_absence_value(key, record.get(key))",
                "def crypto_decline_signal_text(",
                "def crypto_event_is_transfer(",
                "def crypto_boolean_true(",
                "def crypto_boolean_false(",
                '"1", "on", "checked"',
                '"0", "off", "unchecked"',
                "if contains_unknown(value):\n        return False",
                "\"not own wallet\"",
                "def crypto_records_missing(",
                "def crypto_record_absence_phrase(",
                "transaction\\s+history",
                "\"do not have\"",
                "\"don't have\"",
                "\"dont have\"",
                "def crypto_identity_absence_value(",
                "\"no exchange\"",
                "\"no wallet\"",
                "\"no ownership entity\"",
                "def crypto_declines_workflow(",
                "def crypto_source_declines_workflow(",
                "def crypto_field_absence_value(",
                "if crypto_identity_absence_value(key, lowered):",
                "def crypto_has_field_value(",
                "def crypto_record_context(",
                "def crypto_amount_needs_evidence(",
                "if crypto_declines_workflow(value):",
                "def crypto_amount_malformed(",
                "amount is not None and amount < 0",
                "def crypto_date_needs_evidence(",
                "ATO_RENTAL_RECORDS_SOURCE = \"https://www.ato.gov.au/individuals-and-families/investments-and-assets/property-and-land/residential-rental-properties/records-for-rental-properties-and-holiday-homes\"",
                "ATO_RENTAL_HOME_USE_SOURCE = \"https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax/your-main-residence-home/using-your-home-for-rental-or-business\"",
                "REVIEWABLE_RENTAL_PROPERTY_FIELDS = (",
                "RENTAL_PROPERTY_FLAT_FIELD_KEYS = {",
                "RENTAL_PROPERTY_AMOUNT_FIELDS = (",
                "RENTAL_PROPERTY_DECLINE_SIGNAL_KEY",
                "def rental_property_decline_text_matches(",
                "have\\W+no\\W+(?:a\\W+|any\\W+)?(?:rental|investment)\\W+propert(?:y|ies)",
                "no\\W+(?:rental|investment)\\W+propert(?:y|ies)(?:\\W+this\\W+year)?",
                "not\\W+(?:a\\W+)?landlord",
                "if spec.key == \"rental_property_private_use\" and rental_property_private_use_false(value):",
                "items.extend(rental_property_rows(rental_property_answers(answers)))",
                "def rental_property_answers(",
                "flat_values = rental_property_answer_values(fields)",
                "raw_has_context = any(rental_property_answer_context_value(key, value) for key, value in raw.items())",
                "elif key not in merged and rental_property_preserved_absence_value(key, value, raw_has_context):",
                "def rental_property_rows(",
                "status = rental_property_status(evidence, review)",
                "def rental_property_status(",
                "Rental income, interest, repairs/capital, private use, depreciation, and net loss review",
                "def rental_property_answer_context_value(",
                "def rental_property_preserved_absence_value(",
                "return has_context and key in RENTAL_PROPERTY_EXPENSE_FIELDS and rental_property_field_absence_value(key, value)",
                "def rental_property_evidence_gaps(",
                "no-rental answer with rental facts",
                "rental records",
                "repairs versus capital classification",
                "private-use apportionment evidence",
                "top-level and per-property amount reconciliation",
                "net-loss amount reconciliation",
                "def rental_property_has_signal(",
                "def rental_property_review_flags(",
                "capital works or depreciation review",
                "net rental loss review",
                "if any(rental_property_record_has_net_loss(record) for record in [raw, *items]):\n        return True",
                "if display_net is not None:\n        return display_net < 0",
                "def rental_property_record_has_net_loss(",
                "def rental_property_records_missing(",
                "def rental_property_no_loan_records_answer(",
                "def rental_property_no_loan_missing_record_answer(",
                "(\"agent statement\", \"records held\", \"invoice held\")",
                "if rental_property_no_loan_records_answer(lowered):\n        return False",
                "if rental_property_no_loan_missing_record_answer(lowered):\n        return True",
                "if key == \"records\" and rental_property_records_missing(value):\n        return False",
                "def rental_property_declines_workflow(",
                "def rental_property_source_declines_workflow(",
                "def rental_property_field_absence_value(",
                "def rental_property_flat_value_is_absent(",
                "if nested_key == \"net_loss\" and rental_property_net_loss_false(value):\n        return True",
                "def rental_property_amount_missing_document_text(",
                "\"schedule\"",
                "def rental_property_amount_missing_document_value(",
                "def rental_property_has_field_value(",
                "if rental_property_field_absence_value(key, raw.get(key)):\n        return display_value(raw.get(key))",
                "if rental_property_field_absence_value(key, value):\n        return display_value(value)",
                "RENTAL_PROPERTY_NET_LOSS_FALSE_PHRASES = frozenset(",
                "def rental_property_net_loss_false(",
                "def rental_property_net_loss_negative_text(",
                "re.search(r\"\\bno\\W+(?:net\\W+)?(?:rental\\W+)?loss(?:es)?\\b\", lowered)",
                "or re.search(r\"\\bprofit(?:able)?\\b\", lowered)",
                "return lowered in RENTAL_PROPERTY_NET_LOSS_FALSE_PHRASES",
                "if key in RENTAL_PROPERTY_AMOUNT_FIELDS and isinstance(value, bool):",
                "return key == \"net_loss\" and value is True",
                "def rental_property_boolean_amount_evidence_gap(",
                "key != \"net_loss\" and value is True",
                "def rental_property_display_amount_value(",
                "if rental_property_supplied_field_needs_evidence(raw, key):\n        return rental_property_supplied_amount_text(raw.get(key))",
                "if rental_property_item_supplied_amount_needs_evidence(items, key):\n        return \"unknown\"",
                "if rental_property_amount_conflict(raw, items, key):\n        return None",
                "if rental_property_supplied_field_needs_evidence(raw, key):\n        return None",
                "if rental_property_item_supplied_amount_needs_evidence(items, key):\n        return None",
                "if rental_property_net_loss_component_conflicts(raw, items):\n        return None",
                "or rental_property_expense_amounts_incomplete(raw, items)",
                "or rental_property_any_explicit_net_component_amounts_need_evidence(raw, items)",
                "def rental_property_expense_amounts_incomplete(",
                "def rental_property_record_requires_expense_resolution(",
                "def rental_property_any_explicit_net_component_amounts_need_evidence(",
                "def rental_property_explicit_net_component_amounts_need_evidence(",
                "def rental_property_component_amounts_need_evidence(",
                "def rental_property_has_component_amounts(",
                "def rental_property_record_expense_amounts_incomplete(",
                "def rental_property_expense_field_resolved(",
                "if rental_property_expense_amounts_incomplete(raw, items):\n        return None",
                "if rental_property_component_amounts_need_evidence(raw):\n            return None",
                "if rental_property_record_expense_amounts_incomplete(record):\n        return None",
                "if rental_property_supplied_amount_needs_evidence(raw, items, \"net_loss\"):\n        return None",
                "item_explicit_net_values = [rental_property_net_loss_amount_value(item.get(\"net_loss\")) for item in items]",
                "if len(real_item_explicit_net_values) == len(items):\n            return round(sum(real_item_explicit_net_values), 2)",
                "if rental_property_private_use_expense_apportionment_blocks_net(raw, items):\n            return None",
                "if rental_property_item_amounts_need_evidence(items):\n            return None",
                "if rental_property_private_use_expense_apportionment_blocks_net(raw, items):\n        return None",
                "if any(rental_property_supplied_amount_needs_evidence(raw, items, key) for key in RENTAL_PROPERTY_EXPENSE_FIELDS):\n        return None",
                "if rental_property_supplied_amount_needs_evidence(raw, items, \"income\"):\n        return None",
                "return not all(complete)",
                "def rental_property_supplied_amount_text(",
                "def rental_property_item_supplied_amount_needs_evidence(",
                "def rental_property_private_use_expense_apportionment_blocks_net(",
                "def rental_property_item_amounts_need_evidence(",
                "def rental_property_usable_amount_value(",
                "def rental_property_zero_amount_absence_value(",
                "return key in RENTAL_PROPERTY_EXPENSE_FIELDS and rental_property_field_absence_value(key, value)",
                "def rental_property_supplied_amount_needs_evidence(",
                "or rental_property_amount_conflict(raw, items, key)",
                "def rental_property_supplied_field_needs_evidence(",
                "return rental_property_amount_needs_evidence(value, key)",
                "def rental_property_amount_conflicts(",
                "or rental_property_net_loss_component_conflicts(raw, items)",
                "def rental_property_net_loss_component_conflicts(",
                "def rental_property_record_net_loss_component_conflict(",
                "def rental_property_component_net_amount(",
                "def rental_property_amount_conflict(",
                "item_values = rental_property_reconciliation_item_amount_values(items, key)",
                "if key == \"net_loss\" and items and len(real_item_values) != len(items):",
                "def rental_property_reconciliation_item_amount_values(",
                "def rental_property_item_net_loss_reconciliation_value(",
                "return rental_property_net_amount(item)",
                "def rental_property_reconciliation_amount_value(",
                "def rental_property_item_amount_text(",
                "if rental_property_amount_missing_document_value(value):\n        return display_value(value)",
                "def rental_property_item_net_loss_text(",
                "def rental_property_item_text_or_inherited(",
                "f\"other expenses {rental_property_item_amount_text(item, 'other_expenses')}, \"",
                "f\"private days {rental_property_item_amount_text(item, 'private_use_days', money=False)}, \"",
                "f\"available days {rental_property_item_amount_text(item, 'available_days', money=False)}, \"",
                "f\"net loss {rental_property_item_net_loss_text(item)}, \"",
                "if items:\n        return rental_property_items_income_need_evidence(items)",
                "def rental_property_items_income_need_evidence(",
                "def rental_property_item_income_needs_evidence(",
                "def rental_property_items_income_partially_incomplete(",
                "(key == \"income\" and rental_property_items_income_partially_incomplete(items))",
                "rental_property_private_use_needs_evidence(raw, [item])",
                "def rental_property_apportionment_needs_evidence(",
                "if rental_property_private_use_true(record.get(\"private_use\")) and private_days <= 0:",
                "if available_days <= 0:",
                "return private_days > available_days",
                "def rental_property_private_use_summary_conflict(",
                "if rental_property_private_use_true(raw.get(\"private_use\")) and items:",
                "if key == \"private_use\" and rental_property_private_use_summary_conflict(raw, items):",
                "def rental_property_item_private_use_text(",
                "if rental_property_private_use_signal(item):\n        return \"true\"",
                "def rental_property_net_loss_signal(",
                "if contains_unknown(value):\n        return False",
                "def rental_property_net_loss_amount_value(",
                "return -amount if amount > 0 else amount",
                "def rental_property_answer_values(",
                "has_explicit_rental_property_evidence_gap(key, value)",
                "item_net_values = [rental_property_net_amount(item) for item in items]",
                "def rental_property_private_use_negative_text(",
                "def rental_property_private_use_uncertain(",
                "\"1\", \"on\", \"checked\"",
                "\"0\", \"off\", \"unchecked\"",
                "BOOLEAN_UNCERTAIN_PHRASES",
                "def rental_property_private_use_signal(",
                "def rental_property_positive_private_use_days(",
                "def rental_property_private_use_conflict(",
                "not for private use",
                "no holiday home use",
                "if contains_unknown(value):\n        return False",
                "if rental_property_private_use_false(value):",
                "def rental_property_text_or_unknown(",
                "def rental_property_tab_text(",
                "def crypto_bool_text(",
                "def parse_iso_date(",
                "def parse_dates(raw_values: Any) -> Optional[Set[date]]:",
                "if contains_unknown(raw_values):",
                "if start is None or end is None or end < start:",
                "def generation_checked_at(",
                '"checked_at": generation_checked_at()',
            ],
        )
    )
    if '"checked_at": "2026-06-29"' in text:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "forbidden stale checked_at literal"))
    if '"no foreign tax"' in text:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "foreign income decline list must not treat no-tax-paid wording as no foreign income"))
    for forbidden in [
        'raw.get("start", "2025-07-01")',
        'raw.get("end", "2026-06-30")',
        'raw.get("leave_dates", [])',
        'raw.get("worked_public_holidays", [])',
        'raw.get("worked_weekends", [])',
        "return {int(day) for day in weekdays",
        "round(hours * WFH_FIXED_RATE_2025_26, 2)",
        '"status": "Used" if confirmed else "Evidence"',
    ]:
        if forbidden in text:
            findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, f"forbidden parser fallback: {forbidden}"))
    stale_holiday_source = "https://data.gov.au/data/dataset/australian-holidays-machine-readable-dataset"
    if stale_holiday_source in text or stale_holiday_source in skill_rules:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "forbidden inactive public holiday source"))
    holiday_guidance = skill_text + "\n" + skill_rules
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            holiday_guidance,
            [
                "state-wide public holidays",
                "regional, capital-city-only, sector-only, and partial-day",
                "Evidence or `Accountant review`",
            ],
        )
    )
    ess_guidance = skill_text + "\n" + skill_rules
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            ess_guidance,
            [
                "including PAYG, ESS, ETP",
                "employee share scheme",
                "ESS statement",
                "taxed-upfront discount",
                "deferred discount",
                "foreign-source discount",
                "TFN amount withheld",
                "malformed or conflicting amount",
                "https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/employee-share-schemes",
                "https://www.ato.gov.au/forms-and-instructions/employee-share-scheme-statement",
            ],
        )
    )
    complex_payment_guidance = skill_text + "\n" + skill_rules
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            complex_payment_guidance,
            [
                "including PAYG, ESS, ETP",
                "employment termination payment",
                "ETP payment summary",
                "lump sum in arrears",
                "super income stream",
                "taxable and tax-free components",
                "prior-year allocation",
                "contradictory no-payment plus amount facts",
                "https://www.ato.gov.au/tax-rates-and-codes/payg-withholding-schedule-11-tax-table-for-employment-termination-payments",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/lump-sum-payment-in-arrears",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/superannuation-pensions-and-annuities",
                "https://www.ato.gov.au/tax-rates-and-codes/schedule-12-tax-table-for-superannuation-lump-sums",
                "https://www.ato.gov.au/tax-rates-and-codes/schedule-13-tax-table-for-superannuation-income-streams",
            ],
        )
    )
    foreign_income_guidance = skill_text + "\n" + skill_rules
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            foreign_income_guidance,
            [
                "foreign income",
                "foreign employment",
                "foreign income tax offset",
                "residency-specific",
                "no-foreign-income plus amount facts",
                "residency or temporary-resident evidence",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/australian-resident-for-tax-purposes-foreign-and-worldwide-income",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/foreign-and-temporary-resident-income",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/foreign-and-worldwide-income/tax-exempt-income-from-foreign-employment",
                "https://www.ato.gov.au/forms-and-instructions/foreign-income-tax-offset-rules-guide-2026",
            ],
        )
    )
    out_of_scope = ""
    if "## Out Of Scope" in skill_text and "## Method" in skill_text:
        out_of_scope = skill_text.split("## Out Of Scope", 1)[1].split("## Method", 1)[0]
    if "ESS" in out_of_scope or "employee share scheme" in out_of_scope.lower():
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "individual-return out-of-scope must not list ESS"))
    if "ETP" in out_of_scope or "lump sum" in out_of_scope.lower():
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "individual-return out-of-scope must not list ETP/lump sum"))
    if "foreign income" in out_of_scope.lower():
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "individual-return out-of-scope must not list foreign income"))
    psi_guidance = skill_text + "\n" + skill_rules
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            psi_guidance,
            [
                "PSI deep",
                "personal services income",
                "results test",
                "80% client concentration",
                "unrelated clients test",
                "employment test",
                "business premises test",
                "attribution",
                "deductions",
                "business structure",
                "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income",
            ],
        )
    )
    if "PSI deep" in out_of_scope or "personal services income" in out_of_scope.lower():
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "individual-return out-of-scope must not list PSI deep"))
    crypto_guidance = skill_text + "\n" + skill_rules
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            crypto_guidance,
            [
                "crypto CGT",
                "staking",
                "wallet",
                "cost base",
                "capital proceeds",
                "ownership/entity",
                "both business and private",
                "no-crypto plus facts",
                "`crypto-assets`",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/crypto-asset-investments/keeping-crypto-records",
                "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/crypto-assets-and-business",
            ],
        )
    )
    if "crypto CGT" in out_of_scope or "crypto" in out_of_scope.lower():
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "individual-return out-of-scope must not list crypto CGT"))
    individual_prep_doc = read_optional(root, "docs/INDIVIDUAL_RETURN_PREP.md")
    prep_docs = (
        read_optional(root, "README.md")
        + "\n"
        + individual_prep_doc
        + "\n"
        + read_optional(root, "docs/FULL_PLUGIN_INSTALL.md")
    )
    root_router = read_optional(root, "skills/taxmate-australia/SKILL.md")
    root_individual_route = ""
    for line in root_router.splitlines():
        if "`individual-return`: V1 individual return intake" in line:
            root_individual_route = line
            break
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            root_individual_route,
            [
                "`individual-return`: V1 individual return intake",
                "PSI",
                "crypto CGT",
            ],
        )
    )
    prep_cgt_route = ""
    for line in individual_prep_doc.splitlines():
        if "`shares-etfs-managed-funds`" in line:
            prep_cgt_route = line
            break
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            prep_cgt_route,
            [
                "`shares-etfs-managed-funds`",
                "`capital-gains-tax`",
                "`crypto-assets`",
                "`property-rental-cgt`",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            prep_docs,
            [
                "Individual Return Prep",
                "docs/INDIVIDUAL_RETURN_PREP.md",
                "TaxMate is prep-only",
                "No-answer plus facts stays Evidence",
                "./scripts/taxmate intake individual --help",
                "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json",
                "--answers /tmp/taxmate-answers.json",
            ],
        )
    )
    stale_prep_commands = [
        "./scripts/taxmate taxpack sample-json --output /tmp/taxmate-guide-input.json",
        "--input /tmp/taxmate-guide-input.json",
    ]
    for command in stale_prep_commands:
        if command in prep_docs:
            findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, f"individual prep docs use renderer-only command: {command}"))
    return findings


def check_fetch_boundary(root: Path) -> List[Finding]:
    text = read(root, "scripts/atodata.py")
    findings: List[Finding] = []
    if "urllib.request.urlopen" in text:
        findings.append(Finding(ATO_FETCH_BOUNDARY, "urllib.request.urlopen must not return"))
    if not contains_in_order(text, ['"curl"', '"--disable"', '"-L"']):
        findings.append(Finding(ATO_FETCH_BOUNDARY, "curl command must start curl, --disable, -L"))
    required = ['"--write-out"', '"%{http_code}\\n%{url_effective}"', "FetchResult(status=status, final_url=final_url, body=body)"]
    findings.extend(fail_if_missing(ATO_FETCH_BOUNDARY, text, required))
    return findings


def check_generated_artifact_contract(root: Path) -> List[Finding]:
    return fail_if_file_missing(
        root,
        GENERATED_ARTIFACT_CONTRACT,
        "scripts/skillgen.py",
        [
            "def gitTrackedGeneratedArtifacts(",
            "def trackedGeneratedArtifacts(",
            "expected_files = set(trackedGeneratedArtifacts(root))",
            "generated_files = set(trackedGeneratedArtifacts(generated_root))",
            "isGeneratedArtifactPath",
            "current-values.json",
            "source_id",
            "checked_at",
            "content_hash",
        ],
    )


def check_finance_and_calc_wire_contract(root: Path) -> List[Finding]:
    finance = read(root, "scripts/taxmate_finance.py")
    calc = read(root, "scripts/taxmate_calc.py")
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            FINANCE_JSON_WIRE_CONTRACT,
            finance,
            [
                '"generated_at"',
                '"findings"',
                "tax_treatment",
                '"bas_summary"',
                "json.dump(payload, out, indent=2, allow_nan=False)",
                "ROUND_HALF_UP",
                "math.isfinite",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            CALCULATOR_NUMERIC_CONTRACT,
            calc,
            [
                "def finite_float(",
                "math.isfinite",
                "ROUND_HALF_UP",
                "json.dump(result, out, indent=2, allow_nan=False)",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            CALCULATOR_TEMPORAL_CONTRACT,
            calc,
            [
                'SUPPORTED_INCOME_YEAR = "2025-26"',
                'SUPPORTED_FBT_YEAR = "2026"',
                "def supported_income_year(",
                "def supported_fbt_year(",
                "def not_calculated_result(",
                "def normalize_fbt_type(",
                "if not supported_income_year(income_year):",
                "if not supported_fbt_year(fbt_year):",
                '"calculation": "not_calculated"',
                'parser.add_argument("--income-year", default=SUPPORTED_INCOME_YEAR)',
                'parser.add_argument("--fbt-year", default=SUPPORTED_FBT_YEAR)',
            ],
        )
    )
    if re.search(r"\bround\([^)]*\)", calc) or re.search(r"\bround\([^)]*\)", finance):
        findings.append(Finding(CALCULATOR_NUMERIC_CONTRACT, "use Decimal ROUND_HALF_UP, not builtin round"))
    return findings


def check_public_claim_surfaces(root: Path) -> List[Finding]:
    return fail_if_file_missing(
        root,
        PUBLIC_CLAIM_SURFACE_CONTRACT,
        "scripts/taxmate_validate.py",
        [
            'os.path.join("docs", "DISCOVERY.md")',
            '"wrappers"',
            '"docs"',
            'os.path.join(".github", "workflows", "ci.yml")',
            'os.path.join(".github", "workflows", "release.yml")',
            'os.path.join(".github", "dependabot.yml")',
            "ato_endorsement_claim_hits",
            "public_metadata_no_go_runtime_claims",
        ],
    )


def check_release_contract(root: Path) -> List[Finding]:
    release = read(root, ".github/workflows/release.yml")
    development = read(root, "docs/DEVELOPMENT.md")
    config = json.loads(read(root, "release-please-config.json"))
    findings: List[Finding] = []
    required = [
        "workflow_dispatch:",
        "workflow_run:",
        'workflows: ["CI"]',
        "types: [completed]",
        "branches: [main]",
        "Require green CI",
        "GH_REPO: nijanthan-dev/taxmate-australia",
        "--workflow CI --branch main --commit",
        "Require main unchanged",
        "git ls-remote https://github.com/nijanthan-dev/taxmate-australia.git refs/heads/main",
        "RELEASE_PLEASE_TOKEN",
        "release-please-action@",
        "target-branch: main",
        "manifest-file: .release-please-manifest.json",
    ]
    findings.extend(fail_if_missing(RELEASE_GUARDRAIL_CONTRACT, release, required))
    if "workflow_run:" in release and "actions/checkout@" in release:
        findings.append(Finding(RELEASE_GUARDRAIL_CONTRACT, "release workflow_run must not checkout repository code"))
    bootstrap_sha = config.get("bootstrap-sha")
    if not isinstance(bootstrap_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", bootstrap_sha):
        findings.append(Finding(RELEASE_GUARDRAIL_CONTRACT, "release-please-config.json missing 40-char bootstrap-sha"))
    if "workflow_run:" not in release and "automatically" in development.lower():
        findings.append(Finding(RELEASE_GUARDRAIL_CONTRACT, "manual release workflow must not be documented as automatic"))
    return findings


def check_environment_contract(root: Path) -> List[Finding]:
    ci = read(root, ".github/workflows/ci.yml")
    setup = read(root, "scripts/codex-env-setup.sh")
    cleanup = read(root, "scripts/codex-env-cleanup.sh")
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            ENVIRONMENT_WORKTREE_CONTRACT,
            ci,
            [
                "bash scripts/test-codex-env-cleanup.sh",
                "bash scripts/test-codex-env-setup-clean.sh",
                "./scripts/taxmate review-guardrails",
            ],
        )
    )
    for rel, text in [("scripts/codex-env-setup.sh", setup), ("scripts/codex-env-cleanup.sh", cleanup)]:
        if "rev-parse --show-toplevel" not in text:
            findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, f"{rel} must resolve linked worktree root with git rev-parse"))
    if "find " in cleanup and " -delete" in cleanup:
        findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, "cleanup must not combine find -delete with prune"))
    if "PYTHONDONTWRITEBYTECODE" not in setup:
        findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, "setup must disable Python bytecode writes"))
    return findings


def check_local_plugin_marketplace_contract(root: Path) -> List[Finding]:
    marketplace_path = root.joinpath(".agents", "plugins", "marketplace.json")
    docs = read(root, "docs/FULL_PLUGIN_INSTALL.md")
    findings: List[Finding] = []
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, f"invalid .agents/plugins/marketplace.json: {exc}")]

    if not isinstance(marketplace, dict):
        return [Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace root must be an object")]

    name = marketplace.get("name")
    plugins = marketplace.get("plugins")
    if not isinstance(name, str) or not name:
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing name"))
    if not isinstance(plugins, list) or not plugins:
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing plugins"))
        return findings

    plugin_entries = [plugin for plugin in plugins if isinstance(plugin, dict)]
    if len(plugin_entries) != len(plugins):
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace plugins entries must be objects"))

    taxmate_plugin = next((plugin for plugin in plugin_entries if plugin.get("name") == "taxmate-australia"), None)
    if not isinstance(taxmate_plugin, dict):
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing taxmate-australia plugin"))
        return findings

    source = taxmate_plugin.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if source_path == "./":
        commands = command_lines(docs)
        plugin_command = LOCAL_PLUGIN_ADD_COMMAND.format(name=name)
        for command in [LOCAL_MARKETPLACE_ADD_COMMAND, plugin_command]:
            if command not in commands:
                findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, f"missing exact command: {command}"))
        if wrong_local_marketplace_commands(commands):
            findings.append(
                Finding(
                    LOCAL_PLUGIN_MARKETPLACE_CONTRACT,
                    "docs must add repo root exactly because marketplace source.path is ./",
                )
            )
    else:
        findings.append(
            Finding(
                LOCAL_PLUGIN_MARKETPLACE_CONTRACT,
                "unexpected marketplace source.path; update docs and guardrail together",
            )
        )
    return findings


def check_precommit_contract(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for rel in [".pre-commit-config.yaml", ".githooks/pre-commit"]:
        path = root.joinpath(rel)
        if not path.exists():
            findings.append(Finding(PRE_COMMIT_CONTRACT, f"missing {rel}"))
            continue
        text = path.read_text(encoding="utf-8")
        if "./scripts/taxmate review-guardrails" not in text:
            findings.append(Finding(PRE_COMMIT_CONTRACT, f"{rel} must run ./scripts/taxmate review-guardrails"))
    return findings


def check_review_guardrail_docs(root: Path) -> List[Finding]:
    path = root.joinpath("docs", "DEVELOPMENT.md")
    if not path.exists():
        return [Finding(REVIEW_GUARDRAIL_DOCS, "missing docs/DEVELOPMENT.md")]
    text = path.read_text(encoding="utf-8")
    commands = command_lines(text)
    required_commands = [
        "./scripts/taxmate review-guardrails",
        "./scripts/taxmate review-guardrails --list-patterns",
        "./scripts/taxmate review-guardrails --list-patterns --format json",
    ]
    findings = [
        Finding(REVIEW_GUARDRAIL_DOCS, f"missing exact command: {command}")
        for command in required_commands
        if command not in commands
    ]
    findings.extend(
        fail_if_missing(
            REVIEW_GUARDRAIL_DOCS,
            text,
            [
                "The script is the canonical pattern inventory",
                "Do not duplicate PR pattern bullets",
            ],
        )
    )
    if re.search(r"^- PR #\d+:", text, re.MULTILINE):
        findings.append(Finding(REVIEW_GUARDRAIL_DOCS, "docs must not duplicate PR pattern bullets"))
    return findings


def check_output_docs_contract(root: Path) -> List[Finding]:
    readme = read(root, "README.md")
    install = read(root, "docs/INSTALLATION.md")
    full_install = read(root, "docs/FULL_PLUGIN_INSTALL.md")
    prep = read(root, "docs/INDIVIDUAL_RETURN_PREP.md")
    development = read(root, "docs/DEVELOPMENT.md")
    disclaimer = read(root, "DISCLAIMER.md")
    public_metadata = read(root, "skill.json") + "\n" + read(root, ".codex-plugin/plugin.json")
    packaged_output_surfaces = "\n".join(
        [
            read_optional(root, "skills/taxpack/SKILL.md"),
            read_optional(root, "skills/taxpack/agents/openai.yaml"),
            read_optional(root, "skills/taxpack/references/rules.md"),
            read_optional(root, "skills/taxmate-australia/SKILL.md"),
            read_optional(root, "skills/taxmate-australia/references/rules.md"),
            read_optional(root, "skills/individual-return/SKILL.md"),
            read_optional(root, "skills/individual-return/references/rules.md"),
            read_optional(root, "wrappers/taxmate-australia-taxpack/SKILL.md"),
            read_optional(root, "scripts/taxmate_taxpack.py"),
        ]
    )
    docs = "\n".join([readme, install, full_install, prep])
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            OUTPUT_DOCS_CONTRACT,
            readme,
            [
                "Portable skills produce source-backed guidance",
                "full runtime produces a print-first HTML handoff",
                "custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable",
                "manually copy reviewed values into myTax, paper ATO forms, or an accountant handoff",
                "AI extraction confirmation table",
                "individual return field guide",
                "ABN prep section and BAS worksheet",
                "missing facts queue, evidence queue, and accountant-review queue",
                "source/provenance appendix",
                "Screenshot refresh commands",
                "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json",
                "--answers /tmp/taxmate-answers.json",
                "The sample data is synthetic",
                "Any PR that changes user-facing output",
                "must update README/docs in the same PR, or state why no docs update is needed",
            ],
        )
    )
    required_output_surfaces = [
        (
            "docs/INSTALLATION.md",
            install,
            [
                "Portable skills produce source-backed guidance",
                "do not render the full runtime handoff",
                "full runtime handoff is a custom preparation aid",
                "not an ATO form",
                "not lodgment software",
                "not final tax advice",
                "not fileable",
                "manually copy reviewed values",
            ],
        ),
        (
            "docs/FULL_PLUGIN_INSTALL.md",
            full_install,
            [
                "print-first HTML handoff",
                "custom preparation aid",
                "not an ATO form",
                "not lodgment software",
                "not final tax advice",
                "not fileable",
                "manually copy reviewed values",
                "missing facts",
                "evidence gaps",
                "Accountant review",
                "source/provenance appendix",
            ],
        ),
        (
            "docs/INDIVIDUAL_RETURN_PREP.md",
            prep,
            [
                "prep-only",
                "manual-copy handoff",
                "does not lodge",
                "Runtime Path",
                "Open the HTML",
                "prep-only boundary",
                "manual-copy warning",
                "AI extraction confirmation table",
                "source/provenance appendix",
            ],
        ),
        (
            "DISCLAIMER.md",
            disclaimer,
            [
                "custom print-first HTML handoffs",
                "not official ATO PDFs",
                "do not fill official ATO forms",
                "must not be treated as a return",
            ],
        ),
        (
            "skills/taxpack/SKILL.md",
            read_optional(root, "skills/taxpack/SKILL.md"),
            ["manual-copy guidance", "not rendered files", "full runtime for print-first HTML handoff generation"],
        ),
        (
            "skills/individual-return/SKILL.md",
            read_optional(root, "skills/individual-return/SKILL.md"),
            ["manual-copy handoff guidance", "full runtime for HTML handoff generation", "when a full runtime is available"],
        ),
        (
            "skills/taxmate-australia/SKILL.md",
            read_optional(root, "skills/taxmate-australia/SKILL.md"),
            ["manual-copy handoff guidance", "full runtime for HTML handoff generation"],
        ),
    ]
    for label, surface_text, tokens in required_output_surfaces:
        missing = missing_tokens(surface_text, tokens)
        if missing:
            findings.append(Finding(OUTPUT_DOCS_CONTRACT, f"{label} missing: " + ", ".join(missing)))
    findings.extend(
        fail_if_missing(
            OUTPUT_DOCS_CONTRACT,
            development,
            [
                "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json",
                "./scripts/taxmate intake individual --answers /tmp/taxmate-answers.json --output /tmp/taxmate-guide.html",
            ],
        )
    )
    for rel in [
        "assets/readme/taxmate-guide-john-doe.png",
        "assets/readme/taxmate-guide-john-doe-worksheet.png",
    ]:
        if not root.joinpath(rel).exists():
            findings.append(Finding(OUTPUT_DOCS_CONTRACT, f"missing screenshot asset: {rel}"))
    stale_terms = [
        "ATO-aligned manual guide PDFs",
        "ATO-aligned manual guide PDF outputs",
        "ATO-aligned guide PDFs",
        "guide PDFs",
        "custom guide PDFs",
        "future PDF/form drafts",
        "Self-prepared guide PDF",
        "custom manual-copy HTML guides",
        "portable taxpack skill will render",
        "and HTML handoff. Use when",
        "dependants, and HTML handoff",
        "HTML tax pack",
        "The final handoff is HTML only. It must include",
        "./scripts/taxmate taxpack guide-html --output /tmp/taxmate-guide.html",
        "from PIL import Image",
        "Image.open(",
        "./scripts/taxmate.py refresh --help",
    ]
    stale_haystack = "\n".join([docs, development, disclaimer, public_metadata, packaged_output_surfaces])
    stale_hits = [term for term in stale_terms if term in stale_haystack]
    if stale_hits:
        findings.append(Finding(OUTPUT_DOCS_CONTRACT, "stale output docs: " + ", ".join(stale_hits)))
    return findings


def review_patterns_payload() -> List[dict]:
    return [pattern.__dict__ for pattern in REVIEW_PATTERNS]


def render_review_patterns(fmt: str) -> str:
    if fmt == "json":
        return json.dumps({"patterns": review_patterns_payload()}, indent=2) + "\n"
    if fmt == "markdown":
        lines = ["| Pattern | Guardrail check | Contract |", "| --- | --- | --- |"]
        for pattern in REVIEW_PATTERNS:
            lines.append(f"| {pattern.id} | `{pattern.check}` | {pattern.summary} |")
        return "\n".join(lines) + "\n"
    lines = []
    for pattern in REVIEW_PATTERNS:
        lines.append(f"{pattern.id}: {pattern.check} - {pattern.summary}")
    return "\n".join(lines) + "\n"


CHECKS: List[Callable[[Path], List[Finding]]] = [
    check_taxpack_output_layer,
    check_individual_intake_contract,
    check_fetch_boundary,
    check_generated_artifact_contract,
    check_finance_and_calc_wire_contract,
    check_public_claim_surfaces,
    check_release_contract,
    check_environment_contract,
    check_local_plugin_marketplace_contract,
    check_precommit_contract,
    check_review_guardrail_docs,
    check_output_docs_contract,
]


def run(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for check in CHECKS:
        findings.extend(check(root))
    return findings


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="./scripts/taxmate review-guardrails",
        description="Run static guardrails learned from repeated Codex PR review comments.",
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--list-patterns", action="store_true", help="Print canonical review-pattern inventory and exit.")
    args = parser.parse_args(argv)
    if args.list_patterns:
        sys.stdout.write(render_review_patterns(args.format))
        return 0
    findings = run(repo_root())
    if args.format == "json":
        payload = {"ok": not findings, "findings": [finding.__dict__ for finding in findings]}
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif findings:
        for finding in findings:
            print(f"{finding.check}: {finding.detail}", file=sys.stderr)
    else:
        print("review guardrails passed")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
