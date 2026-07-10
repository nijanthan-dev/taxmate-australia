#!/usr/bin/env python3
"""Review-pattern guardrails learned from Codex PR feedback."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List

import taxmate_handoff
import taxmate_validate


ROOT_MARKER = os.path.join(".codex-plugin", "plugin.json")
TAXPACK_OUTPUT_LAYER = "taxpack_output_layer_contract"
HANDOFF_DESTINATION_CONTRACT = "handoff_destination_contract"
INDIVIDUAL_INTAKE_CONTRACT = "individual_intake_contract"
PRIVATE_HEALTH_MEDICARE_CONTRACT = "private_health_medicare_contract"
ATO_FETCH_BOUNDARY = "ato_fetch_boundary"
GENERATED_ARTIFACT_CONTRACT = "generated_artifact_contract"
FINANCE_JSON_WIRE_CONTRACT = "finance_json_wire_contract"
CALCULATOR_NUMERIC_CONTRACT = "calculator_numeric_contract"
CALCULATOR_TEMPORAL_CONTRACT = "calculator_temporal_scope_contract"
PUBLIC_CLAIM_SURFACE_CONTRACT = "public_claim_surface_contract"
RELEASE_GUARDRAIL_CONTRACT = "release_guardrail_contract"
ENVIRONMENT_WORKTREE_CONTRACT = "environment_worktree_contract"
LOCAL_PLUGIN_MARKETPLACE_CONTRACT = "local_plugin_marketplace_contract"
PLUGIN_MCP_CONTRACT = "plugin_mcp_contract"
LOCAL_CI_CONTRACT = "local_ci_contract"
PRE_COMMIT_CONTRACT = "pre_commit_contract"
REVIEW_GUARDRAIL_DOCS = "review_guardrail_docs"
OUTPUT_DOCS_CONTRACT = "output_docs_contract"
HANDOFF_TAXONOMY = {
    "enter-reviewed-value",
    "answer-guided-question",
    "retain-evidence",
    "resolve-before-entry",
    "accountant-handoff-only",
    "not-entered-directly",
    "destination-requires-review",
}
REQUIRED_HANDOFF_DESTINATIONS = {
    "phi-tax-claim-code",
    "phi-premiums-j",
    "phi-rebate-k",
    "phi-benefit-code-l",
    "m1-exemption-question",
    "m1-full-days-v",
    "m1-half-days-w",
    "m2-cover-question-e",
    "m2-days-not-liable-a",
    "spouse-had-question",
}
HANDOFF_DESTINATION_SOURCE_IDS = {
    "phi-tax-claim-code": {"mytax": "ato-f99c3a4ad079", "paper": "ato-2a2cf8a8c462"},
    "phi-premiums-j": {"mytax": "ato-f99c3a4ad079", "paper": "ato-2a2cf8a8c462"},
    "phi-rebate-k": {"mytax": "ato-f99c3a4ad079", "paper": "ato-2a2cf8a8c462"},
    "phi-benefit-code-l": {"mytax": "ato-f99c3a4ad079", "paper": "ato-2a2cf8a8c462"},
    "m1-exemption-question": {"mytax": "ato-4cedc9f93767", "paper": "ato-39155fe09d00"},
    "m1-full-days-v": {"mytax": "ato-4cedc9f93767", "paper": "ato-39155fe09d00"},
    "m1-half-days-w": {"mytax": "ato-4cedc9f93767", "paper": "ato-39155fe09d00"},
    "m2-cover-question-e": {"mytax": "ato-836a84c52e60", "paper": "ato-b8cc03014dc1"},
    "m2-days-not-liable-a": {"mytax": "ato-836a84c52e60", "paper": "ato-b8cc03014dc1"},
    "spouse-had-question": {"mytax": "ato-815a889d0a59", "paper": "ato-29a73bbec8f5"},
}
HANDOFF_DESTINATION_PRODUCERS = {
    "phi-tax-claim-code": {"private_health_statement_rows"},
    "phi-premiums-j": {"private_health_statement_rows"},
    "phi-rebate-k": {"private_health_statement_rows"},
    "phi-benefit-code-l": {"private_health_statement_rows"},
    "m1-exemption-question": {"medicare_levy_row"},
    "m1-full-days-v": {"medicare_levy_row"},
    "m1-half-days-w": {"medicare_levy_row"},
    "m2-cover-question-e": {"mls_review_row"},
    "m2-days-not-liable-a": {"mls_review_row"},
    "spouse-had-question": {"spouse_review_row"},
}
MARKETPLACE_ADD_PREFIX = "codex plugin marketplace add "
LOCAL_MARKETPLACE_ADD_COMMAND = "codex plugin marketplace add ."
LOCAL_PLUGIN_ADD_COMMAND = "codex plugin add taxmate-australia@{name}"
PLUGIN_MCP_REQUIRED_FRAGMENTS = [
    '"coverage",',
    '["command", "cwd"]',
    '["output_path", "cwd"]',
    '["answers_path", "output_path", "cwd"]',
    "function resolveCallerCwd(",
    "function resolveUserPath(value, callerCwd)",
    "cwd: callerCwd",
    "TAXMATE_AUSTRALIA_ROOT: PLUGIN_ROOT",
    "path.resolve(callerCwd, userPath)",
    "caller_cwd: callerCwd",
    'return runTaxmate("validate", [], PLUGIN_ROOT)',
    "caller_cwd = Path.cwd()",
    "cwd=str(caller_cwd)",
    "CALLER_CWD_COMMANDS",
    "ROOT_CWD_COMMANDS",
    "command_cwd = caller_cwd if command in CALLER_CWD_COMMANDS else root",
    '"TAXMATE_AUSTRALIA_ROOT": str(root)',
]
PUBLIC_OUTPUT_DOCS = [
    "README.md",
    "docs/INSTALLATION.md",
    "docs/FULL_PLUGIN_INSTALL.md",
    "docs/INDIVIDUAL_RETURN_PREP.md",
]
DEVELOPER_ONLY_PUBLIC_DOC_TERMS = [
    "Screenshot refresh commands",
    "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome",
    "--headless",
    "--screenshot=",
    "python3 scripts/png_crop.py",
    "taxmate-guide-full.png",
    "Any PR that changes user-facing output",
    "codex plugin marketplace list",
    "codex plugin list",
    "claude plugin marketplace list",
    "claude plugin list",
]
DEVELOPER_ONLY_PUBLIC_DOC_PATTERNS = []
PRIVATE_HEALTH_MEDICARE_RUNTIME_FUNCTIONS = (
    "private_health_medicare_answers",
    "has_private_health_medicare_inputs",
    "private_health_statement_answers",
    "private_health_medicare_rows",
    "private_health_statement_rows",
    "private_health_medicare_evidence_rows",
)
PRIVATE_HEALTH_MEDICARE_SOURCE_BINDINGS = (
    ("ATO_PRIVATE_HEALTH_STATEMENT_SOURCE", "ato-53b20854d6fb"),
    ("ATO_PRIVATE_HEALTH_REBATE_CLAIM_SOURCE", "ato-3aea64d5fad8"),
    ("ATO_MEDICARE_LEVY_SOURCE", "ato-6c86d5e34fe1"),
    ("ATO_MLS_RETURN_SOURCE", "ato-6c536ed6d9ac"),
    ("ATO_MLS_THRESHOLDS_SOURCE", "ato-92c78bc815df"),
    ("ATO_MLS_FAMILY_DEPENDANTS_SOURCE", "ato-33a006afaddd"),
    ("ATO_MLS_PAYING_SOURCE", "ato-cadde338173c"),
)
PRIVATE_HEALTH_MEDICARE_SOURCE_IDS = tuple(
    sorted(source_id for _, source_id in PRIVATE_HEALTH_MEDICARE_SOURCE_BINDINGS)
)
PRIVATE_HEALTH_MEDICARE_TESTS = (
    "RuntimeCoverageTests",
    "PrivateHealthMedicareWorkflowTests",
)
PRIVATE_HEALTH_MEDICARE_DOCS = (
    "docs/INDIVIDUAL_RETURN_PREP.md",
    "skills/individual-return/SKILL.md",
    "skills/private-health-medicare/references/rules.md",
)
PRIVATE_HEALTH_MEDICARE_ISOLATION_SYMBOLS = (
    "PRIVATE_HEALTH_MEDICARE_FLAT_FIELD_ALIASES",
    "private_health_flat_alias_subset",
    "PRIVATE_HEALTH_SUPPORTED_BENEFIT_CODES",
)
PRIVATE_HEALTH_MEDICARE_TYPED_HELPERS = (
    ("private_health_collection_entries", "List[Dict[str, Any]]"),
    ("private_health_scoped_dependant_none", "bool"),
    ("private_health_provenance_urls", "List[str]"),
    ("private_health_sanitized_value", "Any"),
    ("private_health_sanitized_note_value", "Any"),
    ("private_health_metadata_aliases", "tuple[set[str], set[str]]"),
    ("private_health_detail_with_metadata", "tuple[Any, Dict[str, Any]]"),
    ("private_health_note_detail_with_metadata", "tuple[Any, Dict[str, Any]]"),
    ("private_health_filter_record_values", "Dict[str, Any]"),
    ("private_health_statement_items", "List[Dict[str, Any]]"),
    ("private_health_dependant_items", "List[Dict[str, Any]]"),
    ("private_health_dependant_item_container", "bool"),
    ("private_health_dependant_entries", "List[Dict[str, Any]]"),
    ("private_health_dependant_collection_notes", "List[Any]"),
    ("private_health_dependant_qualified_denial_text", "bool"),
    ("private_health_dependant_denial_candidate", "bool"),
    ("private_health_dependant_denial_scalars", "List[Any]"),
    ("private_health_dependant_denial_value", "bool"),
    ("private_health_dependant_remaining_record", "tuple[Any, Dict[str, Any]]"),
    ("private_health_dependant_supplemental_detail", "tuple[Any, Dict[str, Any]]"),
    ("private_health_dependant_item_record", "Dict[str, Any]"),
    ("private_health_dependant_metadata", "Dict[str, Any]"),
    ("private_health_dependant_count_records", "List[Dict[str, Any]]"),
    ("private_health_normalize_dependant_summary", "Dict[str, Any]"),
    ("private_health_dependant_denial_records", "List[Dict[str, Any]]"),
    ("private_health_dependant_summary_entries", "List[Dict[str, Any]]"),
    ("private_health_dependant_summary_base", "Dict[str, Any]"),
    ("private_health_dependant_summary_from_values", "Dict[str, Any]"),
    ("private_health_dependant_summary_records", "List[Dict[str, Any]]"),
    ("private_health_dependant_supplemental_records", "List[tuple[Any, Dict[str, Any]]]"),
    ("private_health_dependant_supplemental_values", "List[Any]"),
    ("private_health_statement_supplemental_records", "List[tuple[Any, Dict[str, Any]]]"),
    ("private_health_statement_collection_metadata", "Dict[str, Any]"),
    ("private_health_dependant_collection_metadata", "Dict[str, Any]"),
    ("private_health_medicare_supplemental_metadata", "Dict[str, Any]"),
    ("private_health_medicare_wrapper_known_keys", "set[str]"),
    ("private_health_workflow_note_metadata", "Dict[str, Any]"),
    ("private_health_unknown_metadata", "Dict[str, Any]"),
    ("private_health_recursive_urls", "List[str]"),
    ("private_health_source_like_text", "bool"),
    ("private_health_epistemic_uncertainty_text", "bool"),
    ("private_health_full_income_year_range_text", "bool"),
    ("private_health_qualified_period_text", "bool"),
    ("private_health_partial_text", "bool"),
    ("private_health_negated_partial_cover_text", "bool"),
    ("private_health_continuous_cover_text", "bool"),
    ("private_health_cover_duration_status", "Optional[str]"),
    ("private_health_partial_cover_text", "bool"),
    ("private_health_negated_spouse_absence_text", "bool"),
    ("private_health_false_only_placeholder", "bool"),
    ("private_health_without_false_period_placeholders", "Dict[str, Any]"),
    ("private_health_period_fact_supplied", "bool"),
    ("private_health_false_cover_period_gaps", "List[str]"),
    ("private_health_record_metadata", "Dict[str, Any]"),
    ("private_health_value_with_income_year", "Any"),
    ("private_health_workflow_section_record", "Dict[str, Any]"),
    ("private_health_normalize_workflow_boundary", "Dict[str, Any]"),
    ("private_health_workflow_with_income_year", "Dict[str, Any]"),
    ("private_health_mls_inherited_aliases", "Dict[str, tuple[str, ...]]"),
    ("private_health_mls_inherited_cover_has_inputs", "bool"),
    ("private_health_mls_inherited_conflicts", "List[str]"),
    ("private_health_singleton_value", "Any"),
    ("private_health_valid_checked_at_values", "List[str]"),
    ("private_health_invalid_source_values", "List[Any]"),
    ("private_health_invalid_checked_at_values", "List[Any]"),
    ("private_health_capture_cover_lineage", "None"),
    ("private_health_add_metadata", "None"),
)
PRIVATE_HEALTH_MEDICARE_NOOP_FRAGMENTS = (
    "PRIVATE_HEALTH_NOOP_TEXT = frozenset(",
    "PRIVATE_HEALTH_NO_VALUE = object()",
    "PRIVATE_HEALTH_DEPENDANT_DENIAL_KEYS = (",
    "notes.extend(private_health_collection_notes(item))",
    "private_health_detail_with_metadata(",
    'notes = private_health_sanitized_note_value(raw.get("notes"))',
    'statements = private_health_statement_items(raw.get("statements"))',
    'dependants = private_health_dependant_items(raw.get("dependants"))',
    "dependant_notes = private_health_dependant_collection_notes(answers)",
    'result["dependant_summary"]["dependant_supplemental_facts"] = dependant_notes',
    'scalar_key = "notes" if records else private_health_section_scalar_key(section_keys)',
    "private_health_statement_collection_metadata(answers)",
    "private_health_dependant_collection_metadata(answers)",
    "private_health_medicare_supplemental_metadata(answers)",
    "private_health_add_metadata(groups[name][index], metadata, field_aliases)",
    "sources.extend(private_health_recursive_urls(raw[key]))",
    "| set(PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS)",
)
PRIVATE_HEALTH_MEDICARE_NOOP_DOC_PHRASE = (
    "Recursively exclude blank or no-op note and metadata containers before alias merge or rendering"
)
PRIVATE_HEALTH_MEDICARE_PROVENANCE_DOC_PHRASE = (
    "Carry matching valid source URLs and checked-at dates onto the review row whenever supplemental facts survive"
)
PRIVATE_HEALTH_MEDICARE_DEPENDANT_DENIAL_DOC_PHRASE = (
    "Normalize explicit dependant collection or count denials to integer 0 before collection filtering"
)
PRIVATE_HEALTH_MEDICARE_PARTIAL_COVER_DOC_PHRASE = (
    "Treat temporal, partial, mixed, or qualified-negative cover wording as review input before categorical no-cover classification"
)


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
        "PR #107",
        OUTPUT_DOCS_CONTRACT,
        "Plugin install docs and public metadata must disclose that the MCP launcher requires Node.js while TaxMate commands run on the bash and Python runtime; tests must derive plugin versions from release-managed manifests.",
    ),
    ReviewPattern(
        "PR #107 MCP",
        OUTPUT_DOCS_CONTRACT,
        "Keep Codex MCP metadata in root .mcp.json with the live mcpServers schema, require explicit workspace cwd for user relative paths, keep plugin root only as TAXMATE_AUSTRALIA_ROOT, and keep Claude-specific MCP launch settings in .claude-plugin/plugin.json.",
    ),
    ReviewPattern(
        "PR #107 CI",
        LOCAL_CI_CONTRACT,
        "Keep CI automatic triggers in workflow YAML, pause hosted-runner spend by disabling GitHub workflows when needed, run the local act workflow before push, and keep review/package invariants enforced by pre-commit and publication checks.",
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
        "Issues #111/#112 phone intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Phone intake must apply negation before positive GST and employer-marker matches, group same-concept paid/reimbursed/provided markers, preserve mixed-use and unknown nested phone fields as visible free-form Evidence, request GST-status evidence for missing or unknown ABN phone GST facts, and avoid blank phone rows from metadata-only inputs.",
    ),
    ReviewPattern(
        "PR #55 ESS intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "ESS intake must normalize nested items field-by-field, preserve item amounts when sibling labels, statements, or unrelated amount labels are unknown, reject placeholder-only item labels, keep concrete statement-only inputs visible for review, skip explicit no-ESS/not-applicable answers only when no ESS facts exist, preserve no-ESS decline signals across flat-only facts, item facts, and flat/nested merges when facts exist, keep field-specific n/a values out of no-ESS decline signals, keep no-ESS plus facts visible in answer/tab text, and keep unknown or malformed ESS amounts as Evidence instead of accountant review without rendering partial same-label item totals.",
    ),
    ReviewPattern(
        "Issue #50 complex payments",
        INDIVIDUAL_INTAKE_CONTRACT,
        "ETP, lump sum in arrears, super lump sum, and super income stream intake must use group-specific no-answer handling, skip explicit no only when no facts exist even when entered into any flat or nested payment source field, distinguish do/don't/dont-have payment denials from missing statement/payment-summary evidence, suppress standalone flat no-payment answers from workflow and base rows through nested-key mapping, preserve no-payment decline signals across flat-only facts and flat/nested merges when facts exist, keep field-specific n/a values out of no-payment decline signals, preserve zero amounts, keep no-plus-facts, unknown statements, unknown amounts, and malformed amounts as Evidence, and keep official-source-backed prep-only guidance aligned across runtime, docs, and portable skills.",
    ),
    ReviewPattern(
        "Issue #48 foreign income",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Foreign income intake must skip explicit no-income/employment/pension answers only when no facts exist even when entered into any flat or nested foreign-income source field, suppress standalone flat no-foreign answers from workflow and base rows through nested-key mapping, inspect item lists before decline matching treats a workflow as factless, preserve no-foreign-income decline signals across flat-only facts, item facts, and flat/nested merges when facts exist, keep field-specific n/a values out of no-foreign-income decline signals, let unknown or uncertain wording override decline matching, avoid no-tax-paid wording as a workflow decline, block tax-paid contexts before any no-income absence phrase, treat do/don't/dont-have income wording as no-income only when it is not tax-paid or statement/payment-summary context, block decline matching for all statement/payment-summary document contexts, keep no foreign income payment summary and no foreign employment statement as Evidence, match short decline tokens exactly, preserve nested and flat false foreign-income claim booleans once another signal renders the row, suppress standalone flat negative claim strings, never let nested false booleans or field-specific negative claim strings clear an existing flat true offset/exemption signal, do not let negative offset/exemption claim-only strings keep a no-income workflow alive, treat no-offset and no-foreign-income-tax-offset wording as negative offset claims, treat no-exemption and no-foreign-employment-exemption wording as negative exemption claims, preserve zero foreign tax paid for display, require positive foreign-tax-paid support for affirmative offset claims, keep no-plus-facts, missing statement phrases, unknown or malformed amounts, residency uncertainty, boolean, missing, malformed, zero, or negative exchange rates with numeric amounts, exchange-rate gaps, item-specific exchange-rate support for top-level totals, top-level-vs-item total conflicts, and any missing or unknown item amount in a rendered item list as Evidence, keep affirmative or ambiguous top-level offset claims without top-level or item-level positive foreign-tax-paid evidence as Evidence, require each explicit item-level offset claim to carry that item's own positive foreign-tax-paid evidence instead of using top-level or sibling tax-paid amounts to clear it, never add exchange rates together, require item-level statement evidence unless a valid top-level statement only covers omitted item statements, and keep all completed foreign income rows under Accountant review.",
    ),
    ReviewPattern(
        "Issue #69 investment income",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Investment income intake must keep missing statements, common not-provided statement wording, absent core amount/component values, zero-only withholding/franking/auxiliary components, unknown or malformed amounts, conflicting direct amount aliases, direct-vs-component dividend conflicts, direct-vs-taxable distribution conflicts, top-level-vs-nested aggregate conflicts, nested direct-vs-alias item conflicts, uncertain or negative-string franking confirmations, AMIT/cost-base adjustments, foreign components, trust distributions, scalar flat investment fields, relevant aggregate-vs-item total conflicts, and supplied aggregates with any unknown relevant item total in Evidence or Accountant review while preserving aggregate-only base rows from canonical fields and accepted aliases, keeping conflicting aggregate-only aliases out of Used, zero withholding, zero franking credits, false foreign components, zero aggregate reconciliation for empty investment categories, source provenance, flat/nested item aliases, nonblank top-level or alias aggregates when nested canonical aggregate placeholders are blank, direct dividend/distribution amount aliases, no fake reconciliation rows when no aggregate was supplied, and every accepted investment amount field in rendered rows.",
    ),
    ReviewPattern(
        "Issue #72 PAYG income statements",
        INDIVIDUAL_INTAKE_CONTRACT,
        "PAYG income statement intake must centralize accepted fields and aliases, include accepted aliases in decline/fact scans, normalize top-level PAYG aliases before routing without treating nested container dict/list values, sole-trader ABN profile facts, or no-PAYG decline phrases as scalar amount aliases, accept documented flat PAYG field keys inside itemized statement records, merge accepted nested PAYG containers before deciding no facts, preserve aggregate-only base rows without duplicating direct flat row numbers, canonical flat malformed values, or legacy main_occupation as normalized rows, render itemized primary and secondary payer details with employer name, ABN, occupation, gross, withholding, allowances, RFBA, RESC, lump sum labels, statement evidence, finalisation status, and source provenance, prefer concrete PAYG aliases over earlier unknown placeholders while still surfacing alias conflicts, preserve zero withholding/RFBA/RESC/allowances and false finalised/tax-ready flags as visible item facts, preserve unknown flat PAYG details in supplemental rows when itemized statements exist, normalize yes/no/true/false/0/1 booleans explicitly, conflict-check statement and finalised evidence across nested PAYG containers even when one value is missing or ambiguous text, use explicit missing checks when falling back from payg_occupation to main_occupation, keep no-PAYG plus facts as Evidence, ignore placeholder-only no-PAYG item rows when no facts exist, prefer non-empty nested PAYG item rows including nested item aliases over stale top-level item aliases and surface item alias conflicts, conflict-check nested direct items against nested item aliases before choosing either surface, never parse non-amount PAYG fields as malformed amount evidence, drop field-level n/a/not-applicable aliases before PAYG amount normalization and nested aggregate reconciliation, treat direct and aliased statement n/a/not-applicable placeholders as missing statement evidence, treat generic lump_sum n/a/not-applicable placeholders as absent labels, keep field-level n/a/not-applicable placeholders out of no-PAYG decline signals, keep nested scalar statement aliases visible before item-alias cleanup, keep raw-level no-PAYG or missing-statement evidence visible in both evidence queues and row surfaces even when itemized PAYG rows exist, keep missing statements, unfinalised statements, conflicting finalised/tax-ready aliases, unknown payer details, malformed item or aggregate amounts, direct alias conflicts, ambiguous lump sum labels, top-level-vs-item reconciliation gaps, and any unknown item amount that affects totals in Evidence, keep top-level totals from clearing item-level Evidence or Accountant review, never let unusable flat placeholders or unknown flat values hide normalized nested aggregate facts, separate row status from evidence queue rows, avoid fake reconciliation rows or evidence when only aggregate totals exist, and cover flat, nested, scalar-flat, aggregate-only, itemized, mixed aggregate+itemized, and empty-list inputs.",
    ),
    ReviewPattern(
        "Issue #75 general CGT schedule",
        INDIVIDUAL_INTAKE_CONTRACT,
        "General CGT event intake must render one review-first schedule row for flat, nested, and scalar facts, skip explicit no-CGT only when no facts exist, keep no-CGT plus facts visible as Evidence, preserve zero proceeds and cost-base values plus false exemption/discount/concession/business/private-use flags, keep missing records, unknown or malformed dates and amounts, ownership uncertainty, mixed/private/business flags, exemption/discount/concession flags, source URLs, checked-at provenance, and evidence queues visible, and state that no capital gain or loss amount is worked out.",
    ),
    ReviewPattern(
        "Issue #76 itemized CGT events",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Itemized CGT event intake must accept flat cgt_items and nested cgt.items, normalize scalar/nested/flat aliases without hiding accepted fields, merge complementary non-conflicting item fields across flat and nested CGT item aliases, preserve extra alias items when CGT item alias lists differ in length, preserve conflicting same-index CGT item alias facts, preserve conflicting per-item alias names and values in rendered evidence, render deterministic per-item event rows with asset, owner, dates, proceeds, cost base, incidental costs, losses, records, and review signals, compare flat and nested item facts semantically instead of raw JSON, preserve zero amounts plus false and true review flags, inherit top-level concrete review flags onto item rows without creating fake top-level schedules, keep top-level summary-only itemized context visible without single-event evidence gaps, keep itemized top-level evidence narrowed to supplied top-level problems instead of the single-event required-field checklist, keep malformed top-level aggregate amounts in Evidence without adding fake single-event gaps, keep item-level Evidence or Accountant review from being cleared by top-level totals, avoid fake reconciliation or top-level schedule rows when no aggregate or top-level fact was supplied, never count item conflicts or no-CGT decline signals as top-level CGT facts, keep no-CGT plus item-only facts visible without adding top-level evidence gaps, require item proceeds and cost base while keeping incidental costs and losses optional unless supplied malformed, flag partial or malformed item totals and top-level-vs-item conflicts as Evidence, and keep source provenance plus no-amount-worked-out wording visible.",
    ),
    ReviewPattern(
        "Issue #77 loss and discount review",
        INDIVIDUAL_INTAKE_CONTRACT,
        "CGT loss and discount review workflow must preserve current-year capital losses and carried-forward losses as prep-only review facts with false/zero visibility, capture discount claim, discount timing/eligibility, and foreign-resident discount signals as review or evidence inputs, preserve unknown or malformed loss/discount evidence in Evidence, keep source URLs covering loss and discount handling, keep top-level loss/discount context visible alongside itemized facts, preserve no-amount-worked-out wording, and avoid treatment or discount/loss calculations.",
    ),
    ReviewPattern(
        "Issue #74 main residence CGT",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Main residence CGT intake and generated portable skills must preserve claim, ownership, occupancy, rental/business use, absence, spouse/partner conflict, and property-record facts across flat, nested, and itemized rows; keep missing or unknown periods, missing records, rental/business use, absence, and spouse conflicts as Evidence or Accountant review when another CGT/main-residence signal exists or itemized CGT rows provide context; preserve false claim/use/conflict values and 0-day text with context; never let standalone main-residence period or property-record defaults create CGT facts or fallback base rows; inherit top-level false, true, and ambiguous main-residence review flags plus text and property-record facts into item rows when itemized context exists without creating fake top-level CGT schedules; keep flat-vs-nested property-record conflicts visible as Evidence; attach main-residence, rental/business-use, and property-record source URLs to rows and evidence queues; keep capital-gains-tax skill/rules/evidence and individual-return routing aligned through scripts/skillgen.py where generated; never calculate a final exemption; and never downgrade rental-property Accountant review.",
    ),
    ReviewPattern(
        "Issue #78 small business CGT concessions",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Small business CGT concession intake must preserve claim status, concession type, business asset, active asset, entity/affiliate/connected entity, retirement exemption, rollover, 15-year exemption, 50% active asset reduction, business/private use, and concession evidence across flat, nested, and itemized rows; keep missing evidence, entity/affiliate/connected entity facts, active asset uncertainty, concession type uncertainty, and business/private use visible as Evidence or Accountant review; preserve false concession and related false review flags with CGT context; inherit top-level small-business concession fields into item rows without fake top-level schedules; attach small-business CGT concession source URLs to rows and evidence queues; keep generated capital-gains-tax and individual-return guidance aligned through scripts/skillgen.py; never determine eligibility, work out concession amounts, or use eligible/final/claimable/lodgment-ready/calculated wording in small-business CGT output.",
    ),
    ReviewPattern(
        "Issue #73 ABN/BAS intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Sole-trader ABN and BAS worksheet intake must preserve flat and nested ABN/BAS facts, itemized income streams and expense categories, zero amounts, false GST registration, source provenance, and prep-only/no-lodgment wording; keep unknown, placeholder, or malformed ABN/BAS amounts, structured missing evidence, no-records wording, missing tax invoices, unknown or placeholder accounting basis, and unknown or placeholder BAS period coverage visible in Evidence rows without downgrading ABN/BAS section rows from Accountant review; compare itemized ABN amount aliases even when item evidence is unknown and keep malformed sibling amount aliases visible as amount evidence; keep false ABN review flags visible when real business context exists without letting standalone default false review flags, including numeric 0 and serialized false/no/0/off/unchecked values, create blank ABN rows or payload sections; disambiguate bare top-level ABNs between PAYG-only employer ABNs and sole-trader business ABNs based on surrounding context; keep completed complex ABN/BAS rows under Accountant review; and never imply BAS lodgment, official-form filling, copy-ready treatment, or final business schedule treatment.",
    ),
    ReviewPattern(
        "Issue #51 PSI",
        INDIVIDUAL_INTAKE_CONTRACT,
        "PSI intake must skip explicit no-PSI answers only when no facts exist even when entered into any PSI prompt, distinguish do/don't/dont-have PSI denials from missing contract/invoice evidence, preserve no-PSI decline signals across flat/nested merges when facts exist, keep field-specific n/a values out of no-PSI decline signals, preserve zero income and false PSI test answers once another signal renders the row, keep no-PSI plus facts, missing contracts, malformed income, unknown or maybe/possibly/unclear tests, missing attribution, deductions, or structure facts as Evidence, never decide PSI treatment as final, and keep completed PSI rows under Accountant review.",
    ),
    ReviewPattern(
        "Issue #47 crypto CGT",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Crypto CGT intake must skip explicit no-crypto answers only when no facts exist even when entered into any crypto prompt, ignore standalone false default crypto booleans including serialized false/no/0/off/unchecked strings in base rows, preserve zero amounts and false transfer/business/private-use booleans once another signal renders the row, render item-level records and use context when top-level fields are missing, require both business and private use context flags before accountant review, accept textual yes/no/true/false/1/0/on/off/checked/unchecked business/private-use flags as complete context, let complete top-level business/private-use context satisfy omitted item use flags while explicit item uncertainty stays Evidence, preserve explicit item-level dates, exchange/wallet, transfer, records, ownership, business-use, and private-use context in item text even when top-level context is complete, keep conflicting top-level-vs-item business/private use flags as Evidence, let non-missing top-level crypto event, identity, wallet records, ownership, and transfer context satisfy omitted item context while explicit item denial/absence/uncertainty stays Evidence, require each item to satisfy amount/date/reward evidence under inherited top-level sale/exchange/reward event context without using top-level or sibling item amounts to clear that item, require each inherited transfer item to carry own-wallet support unless top-level support exists, preserve no-crypto decline signals across flat-only facts, same-field conflicts, and flat/nested merges when facts exist, preserve nested same-field facts for display and calculations when flat no-crypto answers conflict, keep field-specific absence values such as no staking rewards or date/record n/a out of no-crypto decline signals and item amount/date evidence loops, render amount-field no-crypto contradictions instead of hiding them as unknown, treat nested items as contradiction facts, keep top-level and per-item no-crypto plus facts, missing wallet records including natural no/missing/without record wording and do/don't/dont-have wallet or exchange record wording, do not treat unrelated record notes such as no-disposal notes as missing records, malformed amounts or dates, missing asset/exchange identity, missing per-item identity/dates/ownership context, top-level-vs-item total conflicts, item-specific quantity display/comparison when item quantities span different crypto assets, missing ownership, missing own-wallet support for transfer events, non-own-wallet transfer prep gaps including natural not-own-wallet wording and serialized false transfer flags, exchange/convert/conversion disposal-like prep gaps without treating own-wallet exchange transfers as disposals, transfer ambiguity including sentence-shaped maybe/possibly/unclear boolean wording, and missing either business or private use context as Evidence, never decide CGT treatment, and keep completed crypto rows under Accountant review.",
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
        "README and install docs must describe portable-vs-runtime output, HTML-only prep handoff sections, synthetic data, and manual-copy boundaries while developer docs carry screenshot refresh commands and the docs-update rule for user-facing output changes.",
    ),
    ReviewPattern(
        "Issue #124 handoff destinations",
        HANDOFF_DESTINATION_CONTRACT,
        "Runtime-owned handoff actions must use the documented taxonomy, preserve review precedence and falsey values, fail closed for malformed or unverified destinations, keep source provenance, and give every row, queue item, extraction, and fact a nonblank next action plus a verified destination or explicit non-entry/review wording.",
    ),
    ReviewPattern(
        "Issue #70 deduction/offset intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Deduction, personal-super, and offset intake must keep source provenance specific to the row kind, gate GST/BAS sources on the deduction row's GST/BAS signal rather than global BAS inputs, match short deduction routing tokens such as car as whole words, classify software/tool items before broad licence/membership matches, surface offset evidence gaps when claim is omitted, uncertain, or only a supported offset type is supplied but suppress them for boolean or phrase-based negative claims, derive false-only structured placeholders from field alias maps including numeric 0 false defaults while preserving false flags attached to core facts, ignore boolean false amount-only placeholders while preserving zero amount rows, skip natural-language no-op scalar item entries and top-level scalar no-op aliases before row creation, keep partial reimbursement/employer-paid/provided and partial offset eligibility/review phrases in evidence instead of treating them as clean negatives, prefer concrete aliases over earlier unknown or serialized-false placeholders, compare 0/1 amount aliases as money rather than booleans, compare equivalent evidence/NOI/ack denials and boolean aliases by field-aware canonical meaning including negative boolean phrases, suppress negative review phrases before evidence gating, treat explicit document/evidence denials and false evidence/NOI/ack values as concrete facts, preserve false aliases in conflicting boolean alias groups, validate malformed personal-super contribution dates before clearing evidence, surface conflicting concrete aliases in row and evidence text, preserve scalar/free-form facts beside structured rows, inside mixed lists, in nested parent notes, under item alias keys beside item arrays, in note-only containers, in supplemental note dictionaries, in recognized item-level notes, in unrecognized dictionaries, in unrecognized/partially recognized dict list items, in partially recognized dictionaries with unknown sibling keys, and in recognized parent-level aliases beside nested item arrays across all deduction/super/offset alias groups without letting raw notes satisfy evidence/NOI/ack fields, keep receipt/statement/NOI/acknowledgement denials including bare not-sent/not-acknowledged and denial-only super NOI/ack wording in evidence queues, and keep recognized direct-item aliases such as description with their amount/evidence fields intact while keeping super-specific offset sources off spouse, zone/remote, other, unsupported, and scalar generic offset fallback rows while preserving them for super offset rows.",
    ),
    ReviewPattern(
        "Issue #71 private health/Medicare intake",
        PRIVATE_HEALTH_MEDICARE_CONTRACT,
        "Private-health and Medicare intake must isolate namespaced flat aliases so generic keys from unrelated workflows never leak into this workflow; preserve direct, flat, nested, itemized, mixed scalar/dict, sibling, unknown, zero, and false values; distinguish explicit no/false and no-statement/not-held/not-supplied/not-received/missing/without denial variants from uncertainty; preserve each insurer statement and dependant as a distinct line; recursively suppress metadata-only, empty, no-op, and default-false containers before alias merge or rendering without dropping real mixed-container siblings; validate supported benefit and tax-claim codes, amounts, dates, day ranges, counts, reconciliation, and contradictions; union every valid supplied provenance URL with only the matching verified statement, levy, MLS, and family/dependant sources; keep missing statements, partial-year cover, malformed periods, spouse/dependant uncertainty, levy exemption/reduction ambiguity, and MLS uncertainty in Evidence or Accountant review; and remain prep-only without final levy, surcharge, rebate, or lodgment advice.",
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


def python_function_text(text: str, name: str) -> str:
    match = re.search(
        rf"^def {re.escape(name)}\(.*?(?=^def |\Z)",
        text,
        re.DOTALL | re.MULTILINE,
    )
    return match.group(0) if match else ""


def missing_tokens(text: str, tokens: Iterable[str]) -> List[str]:
    return [token for token in tokens if token not in text]


def fail_if_missing(check: str, text: str, tokens: Iterable[str]) -> List[Finding]:
    missing = missing_tokens(text, tokens)
    if missing:
        return [Finding(check, "missing: " + ", ".join(missing))]
    return []


def fail_if_file_missing(root: Path, check: str, rel: str, tokens: Iterable[str]) -> List[Finding]:
    return fail_if_missing(check, read(root, rel), tokens)


def developer_only_public_doc_hits(text: str) -> List[str]:
    hits = [term for term in DEVELOPER_ONLY_PUBLIC_DOC_TERMS if term in text]
    hits.extend(label for pattern, label in DEVELOPER_ONLY_PUBLIC_DOC_PATTERNS if pattern.search(text))
    return hits


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


def ast_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return f"{node.func.value.id}.{node.func.attr}"
    return ""


def ast_parent_map(tree: ast.AST) -> Dict[ast.AST, ast.AST]:
    parents: Dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def ast_enclosing_function(node: ast.AST, parents: Dict[ast.AST, ast.AST]) -> str:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
    return "<module>"


def destination_kind_literals(text: str, name: str) -> set[str]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        value = node.value
        if isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            return {
                item.value
                for item in value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
    return set()


def handoff_ast_findings(intake_text: str, taxpack_text: str, mapping_ids: set[str]) -> List[Finding]:
    findings: List[Finding] = []
    try:
        intake_tree = ast.parse(intake_text)
    except SyntaxError as exc:
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"intake AST is invalid: {exc}"))
        intake_tree = None
    if intake_tree is not None:
        guide_calls = [
            node
            for node in ast.walk(intake_tree)
            if isinstance(node, ast.Call) and ast_call_name(node) == "guide_row"
        ]
        if len(guide_calls) != 67:
            findings.append(
                Finding(
                    HANDOFF_DESTINATION_CONTRACT,
                    f"intake must retain 67 explicit guide_row producers; found {len(guide_calls)}",
                )
            )
        for node in guide_calls:
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            if "facts" not in keywords or (
                isinstance(keywords["facts"], ast.Constant) and keywords["facts"].value is None
            ):
                findings.append(
                    Finding(
                        HANDOFF_DESTINATION_CONTRACT,
                        f"guide_row call missing explicit facts at line {node.lineno}",
                    )
                )
            row_kind = keywords.get("row_kind")
            if not isinstance(row_kind, ast.Constant) or not isinstance(row_kind.value, str) or not row_kind.value.strip():
                findings.append(
                    Finding(
                        HANDOFF_DESTINATION_CONTRACT,
                        f"guide_row call missing literal row_kind at line {node.lineno}",
                    )
                )
        for node in ast.walk(intake_tree):
            if isinstance(node, ast.Call) and ast_call_name(node) == "taxmate_handoff.compatibility_facts":
                findings.append(
                    Finding(
                        HANDOFF_DESTINATION_CONTRACT,
                        f"intake uses compatibility fact synthesis at line {node.lineno}",
                    )
                )

        parents = ast_parent_map(intake_tree)
        for node in ast.walk(intake_tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or node.value not in mapping_ids:
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(parent, ast.Call):
                parent = parents.get(parent)
            function = ast_enclosing_function(node, parents)
            destination_values = [
                keyword.value
                for keyword in parent.keywords
                if isinstance(parent, ast.Call) and keyword.arg == "destination_key"
            ] if isinstance(parent, ast.Call) else []
            if (
                not isinstance(parent, ast.Call)
                or ast_call_name(parent) != "taxmate_handoff.fact"
                or node not in destination_values
                or function not in HANDOFF_DESTINATION_PRODUCERS.get(node.value, set())
            ):
                findings.append(
                    Finding(
                        HANDOFF_DESTINATION_CONTRACT,
                        f"destination mapping used outside approved producer: {node.value} at line {node.lineno}",
                    )
                )

    try:
        taxpack_tree = ast.parse(taxpack_text)
    except SyntaxError as exc:
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"taxpack AST is invalid: {exc}"))
        taxpack_tree = None
    if taxpack_tree is not None:
        output_logic: List[str] = []
        forbidden_calls = {
            "taxmate_handoff.fact",
            "taxmate_handoff.verified_destination",
            "taxmate_handoff.destination_source",
            "taxmate_handoff.requested_fact_handoff",
        }
        for node in ast.walk(taxpack_tree):
            if isinstance(node, ast.Call):
                name = ast_call_name(node)
                if name in forbidden_calls:
                    output_logic.append(f"{name} at line {node.lineno}")
                for keyword in node.keywords:
                    if keyword.arg in {"action_kind", "destination_key"}:
                        output_logic.append(f"{keyword.arg} at line {node.lineno}")
        for detail in sorted(set(output_logic)):
            findings.append(
                Finding(
                    HANDOFF_DESTINATION_CONTRACT,
                    "output layer constructs handoff facts or destinations: " + detail,
                )
            )
    return findings


def handoff_source_state_findings(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    try:
        coverage, registry = taxmate_handoff.source_state(root)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return [Finding(HANDOFF_DESTINATION_CONTRACT, f"handoff source state unavailable: {exc}")]
    for source_id, (expected_url, expected_checked_at) in taxmate_validate.HANDOFF_EXPECTED_SOURCE_STATE.items():
        covered = coverage.get(source_id)
        record = registry.get(source_id)
        if not isinstance(covered, dict) or not isinstance(record, dict):
            findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"source state missing verified binding: {source_id}"))
            continue
        expected_hash = taxmate_validate.HANDOFF_EXPECTED_HASHES[source_id]
        registry_url = taxmate_handoff.canonical_url(str(record.get("final_url") or record.get("url") or ""))
        if covered.get("canonical_url") != expected_url or registry_url != expected_url:
            findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"coverage-registry URL mismatch: {source_id}"))
        if covered.get("content_hash") != expected_hash or record.get("content_hash") != expected_hash:
            findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"coverage-registry hash mismatch: {source_id}"))
        if covered.get("checked_at") != expected_checked_at or record.get("last_checked") != expected_checked_at:
            findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"coverage-registry date mismatch: {source_id}"))
        if covered.get("status") != "verified" or record.get("content_verified") is not True:
            findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"source state is not verified: {source_id}"))
    return findings


def check_handoff_contract(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    runtime_text = read_optional(root, "scripts/taxmate_handoff.py")
    intake_text = read_optional(root, "scripts/taxmate_intake.py")
    taxpack_text = read_optional(root, "scripts/taxmate_taxpack.py")
    validate_text = read_optional(root, "scripts/taxmate_validate.py")
    test_text = "\n".join(
        [
            read_optional(root, "tests/test_handoff_contract.py"),
            read_optional(root, "tests/test_handoff_repository_contract.py"),
        ]
    )

    findings.extend(
        fail_if_missing(
            HANDOFF_DESTINATION_CONTRACT,
            runtime_text,
            [
                "TAXONOMY:",
                "ACTION_TEXT =",
                "def scalar_text(",
                "if value is None:",
                "if isinstance(value, bool):",
                "def mapping_channel_errors(",
                "def destination_mapping_errors(",
                'record.get("content_verified") is not True',
                'covered.get("content_hash")',
                'covered.get("checked_at")',
                "def unresolved_destination(",
                "def not_entered_destination(",
                "def effective_action_kind(",
                'if effective_status == "review":',
                'return "accountant-handoff-only"',
                "def normalize_handoff(",
                "def normalize_fact(",
                "def normalize_row_contract(",
                "def build_row_contract(",
            ],
        )
    )
    findings.extend(handoff_ast_findings(intake_text, taxpack_text, REQUIRED_HANDOFF_DESTINATIONS))
    runtime_destination_kinds = destination_kind_literals(runtime_text, "DESTINATION_KINDS")
    validator_destination_kinds = destination_kind_literals(validate_text, "HANDOFF_DESTINATION_KINDS")
    if "field-level" in runtime_destination_kinds or "field-level" in validator_destination_kinds:
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, "field-level destination kind is forbidden"))
    if set(taxmate_handoff.TAXONOMY) != HANDOFF_TAXONOMY:
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, "handoff taxonomy does not match the documented seven actions"))
    elif any(
        not str(entry.get("label", "")).strip() or not str(entry.get("description", "")).strip()
        for entry in taxmate_handoff.TAXONOMY.values()
    ):
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, "handoff taxonomy label or description is blank"))

    findings.extend(
        fail_if_missing(
            HANDOFF_DESTINATION_CONTRACT,
            intake_text,
            [
                "import taxmate_handoff",
                "taxmate_handoff.build_row_contract(",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            HANDOFF_DESTINATION_CONTRACT,
            taxpack_text,
            [
                "import taxmate_handoff",
                "taxmate_handoff.normalize_row_contract(",
                'class="handoff-card',
                'class="fact-list"',
                "Next action",
                "Where it belongs",
                "Why this action",
                "Source context",
            ],
        )
    )
    renderer_mapping_hits = sorted(mapping_id for mapping_id in REQUIRED_HANDOFF_DESTINATIONS if mapping_id in taxpack_text)
    if renderer_mapping_hits:
        findings.append(
            Finding(
                HANDOFF_DESTINATION_CONTRACT,
                "output layer contains destination mapping identifiers: " + ", ".join(renderer_mapping_hits),
            )
        )

    findings.extend(
        fail_if_missing(
            HANDOFF_DESTINATION_CONTRACT,
            validate_text,
            [
                "def handoff_destination_contract(",
                'add("handoff_destination_contract", handoff_destination_contract(), "")',
                "taxmate_handoff.destination_mapping_errors(",
                "taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())",
                "HANDOFF_ENTRY_WORDING",
                "taxmate_handoff.ACTION_TEXT[action_kind]",
                "taxmate_handoff.effective_status_kind(",
                'canonical["facts"] != facts',
                "canonical_extraction != extraction",
                "source_urls",
                "checked_at",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            HANDOFF_DESTINATION_CONTRACT,
            test_text,
            [
                "EXPECTED_TAXONOMY",
                "test_destination_mappings_match_verified_source_state",
                "test_every_runtime_row_fact_queue_and_extraction_has_handoff",
                "test_accountant_review_blocks_entry_and_copy_wording",
                "test_missing_malformed_and_direct_handoffs_fail_closed",
                "test_falsey_structured_fact_values_remain_visible",
                "test_repository_validation_checks_cover_the_handoff_contract",
                "test_all_guide_row_calls_supply_literal_row_kind_and_facts",
                "test_compatibility_fallback_preserves_one_full_semicolon_value",
                "test_action_destination_matrix_is_exact",
                "test_field_level_is_not_a_destination_kind",
                "test_duplicate_fact_keys_fail_payload_validation",
                "test_queue_only_and_extended_only_payloads_validate",
                "test_payload_validation_requires_canonical_handoff_label_and_action",
                "test_payload_validation_rejects_forged_destination_mapping_and_sources",
                "test_payload_validation_rejects_binding_key_bypass",
                "test_payload_validation_rejects_stale_status_contracts",
                "test_payload_validation_rederives_all_runtime_rows_and_preserves_falsey_values",
                "test_extraction_payload_requires_shared_normalizer_idempotence",
                "test_resolved_destinations_keep_channel_review_state_and_provenance",
            ],
        )
    )

    manifest_text = read_optional(root, "config/handoff-destinations.json")
    try:
        manifest = json.loads(manifest_text)
    except (TypeError, json.JSONDecodeError) as exc:
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"invalid destination manifest: {exc}"))
        manifest = {}
    if not isinstance(manifest, dict):
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, "destination manifest must be an object"))
        manifest = {}
    destinations = manifest.get("destinations")
    if manifest.get("schema_version") != 2 or manifest.get("income_year") != "2025-26":
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, "destination manifest schema or income year is invalid"))
    if not isinstance(destinations, dict):
        findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, "destination manifest mappings are missing"))
    else:
        if set(destinations) != REQUIRED_HANDOFF_DESTINATIONS:
            findings.append(
                Finding(
                    HANDOFF_DESTINATION_CONTRACT,
                    "destination manifest must match exact mapping set",
                )
            )
        dynamic_renderer_hits = sorted(mapping_id for mapping_id in destinations if mapping_id in taxpack_text)
        dynamic_renderer_hits = sorted(set(dynamic_renderer_hits).difference(renderer_mapping_hits))
        if dynamic_renderer_hits:
            findings.append(
                Finding(
                    HANDOFF_DESTINATION_CONTRACT,
                    "output layer contains destination mapping identifiers: " + ", ".join(dynamic_renderer_hits),
                )
            )
        for mapping_id in REQUIRED_HANDOFF_DESTINATIONS:
            mapping = destinations.get(mapping_id)
            if not isinstance(mapping, dict) or not str(mapping.get("label", "")).strip():
                findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"{mapping_id}: mapping label is blank"))
                continue
            for channel_name in ("mytax", "paper"):
                channel = mapping.get(channel_name)
                if not isinstance(channel, dict) or not str(channel.get("location", "")).strip():
                    findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, f"{mapping_id}.{channel_name}: location is blank"))
                    continue
                expected_kind = taxmate_validate.HANDOFF_EXPECTED_CHANNEL_KINDS[mapping_id][channel_name]
                expected_location = taxmate_validate.HANDOFF_EXPECTED_LOCATIONS[mapping_id][channel_name]
                expected_source_id = HANDOFF_DESTINATION_SOURCE_IDS[mapping_id][channel_name]
                expected_hash = taxmate_validate.HANDOFF_EXPECTED_HASHES[expected_source_id]
                if channel.get("kind") != expected_kind:
                    findings.append(
                        Finding(
                            HANDOFF_DESTINATION_CONTRACT,
                            f"destination channel kind does not match verified binding: {mapping_id}.{channel_name}",
                        )
                    )
                if channel.get("location") != expected_location:
                    findings.append(
                        Finding(
                            HANDOFF_DESTINATION_CONTRACT,
                            f"destination location does not match verified binding: {mapping_id}.{channel_name}",
                        )
                    )
                if channel.get("source_id") != expected_source_id:
                    findings.append(
                        Finding(
                            HANDOFF_DESTINATION_CONTRACT,
                            f"source is unrelated to the verified destination: {mapping_id}.{channel_name}",
                        )
                    )
                if channel.get("content_hash") != expected_hash:
                    findings.append(
                        Finding(
                            HANDOFF_DESTINATION_CONTRACT,
                            f"destination hash does not match verified binding: {mapping_id}.{channel_name}",
                        )
                    )

    findings.extend(handoff_source_state_findings(root))
    if manifest_text:
        for error in taxmate_handoff.destination_mapping_errors(root):
            findings.append(Finding(HANDOFF_DESTINATION_CONTRACT, error))
    return findings


def check_taxpack_output_layer_text(text: str) -> List[Finding]:
    findings: List[Finding] = []
    required = [
        "def scalar_text(",
        "def text_value(",
        "def source_urls(",
        "def render_source_summary(",
        "taxmate_handoff.normalize_row_contract(",
        "def item_contract(",
        "def build_render_rows(",
        "def render_card(",
        "def render_fact(",
        "taxmate_handoff.effective_status_kind(",
        "def effective_status_kind(",
        "def effective_tab_kind(",
        "def review_text(",
        "return tab_text_value(item.tab_text).strip() or fallback_tab_text(item.number, effective_status_kind(item))",
        "def tab_text_value(",
        "if value is False:",
        "return \"\" if text.strip().lower() == \"false\" else text",
        "def render_review_queue(rows: List[RenderRow])",
        '<ul class="review-list">',
        "def tab_title(item: GuideItem, row_index: int)",
        "fallback_tab_text(item.number, effective_status_kind(item))",
        "def row_anchor(item: GuideItem, row_index: int)",
        "def row_context_anchor(",
        "def render_sections(",
        'data-anchor="{row.anchor}"',
        "def render_context_index(",
        'href="#{row.anchor}"',
        "def render_source_appendix(",
        "data.abn_items",
        "data.bas_items",
        "data.missing_facts",
        "data.evidence_items",
        "default_generated_date()",
        "canonical_status(kind)",
        "def malformed_section_item(",
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
    capital_gains_skill = read_optional(root, "skills/capital-gains-tax/SKILL.md")
    capital_gains_rules = read_optional(root, "skills/capital-gains-tax/references/rules.md")
    capital_gains_evidence = read_optional(root, "skills/capital-gains-tax/references/evidence.md")
    findings: List[Finding] = []
    generic_offset_sources = re.search(r"ATO_OFFSET_SOURCES\s*=\s*\[(.*?)\]\nATO_SUPER_OFFSET_SOURCES", text, re.DOTALL)
    if not generic_offset_sources:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "missing split generic/super offset source constants"))
    elif any(
        super_source in generic_offset_sources.group(1)
        for super_source in ["ATO_SUPER_COCONTRIBUTION_SOURCE", "ATO_INVESTMENTS_INSURANCE_SUPER_SOURCE"]
    ):
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "generic offset sources include super-specific provenance"))
    false_only_start = text.find("FALSE_ONLY_ITEM_FIELDS = frozenset(")
    false_only_end = text.find("def false_only_alias_keys(", false_only_start)
    false_only_block = text[false_only_start:false_only_end] if false_only_start != -1 and false_only_end != -1 else ""
    if '"notice_of_intent"' in false_only_block or '"fund_acknowledgement"' in false_only_block:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "super NOI/ack denial aliases must not be false-only placeholders"))
    if "or has_bas_inputs(answers):\n        sources = [*sources, ATO_GST_CREDITS_SOURCE, ATO_TAX_INVOICES_SOURCE]" in text:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "deduction GST/BAS sources must be gated by row-level GST/BAS signal"))
    if not contains_in_order(text, ["def item_alias_conflict_key(", "amount = safe_money_value(value)", "parsed_bool = phone_bool(value)"]):
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "item alias conflict keys must parse money before bool for 0/1 amounts"))
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            text,
            [
                "ATO_OFFSET_SOURCES = [ATO_TAX_OFFSETS_SOURCE]",
                "ATO_SUPER_OFFSET_SOURCES = [",
                "return ATO_SUPER_OFFSET_SOURCES",
                "return ATO_OFFSET_SOURCES",
                "tokens = set(normalized.split())",
                'tokens.intersection({"travel", "car", "vehicle", "taxi", "rideshare", "uber"})',
                "def offset_claim_false(",
                "def offset_claim_partial_value(",
                "def deduction_flag_negative(",
                "def deduction_flag_partial_value(",
                "def partial_negative_context_value(",
                "def review_flag_partial_value(",
                "if deduction_flag_partial_value(value):",
                "if review_flag_partial_value(value):",
                "if offset_claim_partial_value(value):",
                "def deduction_private_use_negative(",
                "claim_false = offset_claim_false(claim)",
                "if is_missing(value) or contains_unknown(value):",
                'r"\\b(not|no|never)\\b.*\\b(claim|claiming|claimed|apply|applying|applied|eligible|entitled|entitlement)\\b"',
                'r"\\b(ineligible|unentitled)\\b"',
                'r"\\b(not|no|never|without)\\b.*\\b(reimburs|employer|paid|provided|gst|bas|duplicate|risk|overlap)\\w*\\b"',
                'r"\\b(no|not|without|zero)\\b.*\\b(private|personal|non work|nonwork|mixed)\\b"',
                "review_offset_facts = not claim_false",
                'kind != "unsupported"',
                "or not is_missing(amount)",
                "def false_only_item_placeholder(",
                "def false_only_item_value(",
                "def issue70_false_only_item_value(",
                "def false_only_placeholder_value(",
                "def scalar_noop_item_value(",
                "def false_only_scalar_placeholder(",
                "if false_only_scalar_placeholder(value):",
                "scalar_noop_item_value(value)",
                "AMOUNT_ONLY_FALSE_ITEM_KEYS = tuple(",
                "key in AMOUNT_ONLY_FALSE_ITEM_KEYS and value is False",
                "value == 0",
                "if issue70_false_only_item_value(spec.key, value):",
                "if false_only_item_value(value, item_keys, recognized_keys, false_only_keys):",
                "false_only_scalar_placeholder(item)",
                "false_only_item_placeholder(raw, recognized_keys, false_only_keys)",
                "false_only_item_placeholder(item, recognized_keys, false_only_keys)",
                "def field_has_structured_item_answers(",
                "structured_deduction_fields = {",
                "structured_super_contribution_fields = {",
                "structured_offset_fields = {",
                "if spec.key in structured_deduction_fields:",
                "if spec.key in structured_super_contribution_fields:",
                "if spec.key in structured_offset_fields:",
                "def item_values_with_scalar_entries(",
                "item_values_with_scalar_entries(value, scalar_key, recognized_keys, false_only_keys)",
                "def item_key_value_entries(",
                "item_key_value_entries(value.get(item_key), scalar_key, recognized_keys, false_only_keys)",
                "FALSE_ONLY_ITEM_FIELDS = frozenset(",
                "def false_only_alias_keys(",
                "false_only_alias_keys(DEDUCTION_FIELD_ALIASES)",
                "false_only_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES)",
                "false_only_alias_keys(OFFSET_FIELD_ALIASES)",
                "FALSE_CONCRETE_ALIAS_GROUPS = (",
                "BOOLEAN_FALSE_CONCRETE_ALIAS_GROUPS = (",
                "def false_concrete_alias_group(",
                "include_boolean and aliases in BOOLEAN_FALSE_CONCRETE_ALIAS_GROUPS",
                "false_concrete_alias_group(aliases, include_boolean=True)",
                "def concrete_item_alias_value(",
                "def explicit_evidence_denial_value(",
                '"not sent"',
                '"not acknowledged"',
                "def normalized_item_field(",
                "def item_alias_conflict_key(",
                "ITEM_ALIAS_AMOUNT_FIELDS = frozenset(",
                "ITEM_ALIAS_EVIDENCE_FIELDS = frozenset(",
                "ITEM_ALIAS_BOOLEAN_FIELDS = frozenset(",
                "if field in ITEM_ALIAS_EVIDENCE_FIELDS:",
                "item_alias_negative_boolean_value(field, value)",
                "def item_alias_negative_boolean_value(",
                "def review_flag_review(",
                "def review_flag_negative(",
                "if review_flag_review(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES[\"concessional_cap_review\"])):",
                "if review_flag_review(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES[\"division_293_review\"])):",
                "if review_offset_facts and review_flag_review(normalized_item_field(item, OFFSET_FIELD_ALIASES[\"review_signal\"])):",
                "def item_alias_conflict_details(",
                "def item_alias_conflict_text(",
                "terms.extend(item_alias_conflict_details(item, DEDUCTION_FIELD_ALIASES))",
                "terms.extend(item_alias_conflict_details(item, SUPER_CONTRIBUTION_FIELD_ALIASES))",
                "terms.extend(item_alias_conflict_details(item, OFFSET_FIELD_ALIASES))",
                "alias conflicts {conflicts}",
                "if concrete_item_alias_value(value, false_is_concrete):",
                "if contains_unknown(value):",
                "rows.append(raw_text_item_entry(display_value(item), scalar_key))",
                "DEDUCTION_NESTED_KEYS,",
                "DEDUCTION_ITEM_KEYS,",
                "item_alias_keys(SUPER_CONTRIBUTION_FIELD_ALIASES)",
                "OFFSET_NESTED_KEYS,",
                "OFFSET_ITEM_KEYS,",
                "SUPPLEMENTAL_ITEM_NOTE_KEYS = frozenset(",
                "def supplemental_note_entries(",
                "def supplemental_scalar_item_entries(",
                "rows.extend(supplemental_scalar_item_entries(item, (), scalar_key, recognized_keys))",
                "supplemental_items = supplemental_scalar_item_entries(value, item_keys, scalar_key, recognized_keys)",
                "key in recognized_keys",
                "def raw_fallback_item_entry(",
                "fallback_item = raw_fallback_item_entry(value, scalar_key, recognized_keys, false_only_keys)",
                "def unrecognized_sibling_item_entry(",
                "def recognized_parent_item_entry(",
                "parent_item = recognized_parent_item_entry(value, item_keys, recognized_keys, false_only_keys)",
                "sibling_item = unrecognized_sibling_item_entry(value, item_keys, scalar_key, recognized_keys)",
                "if parent_item is not None:",
                "rows.extend(supplemental_items)",
                "elif supplemental_items:",
                "is_recognized_item_dict(value, recognized_keys, false_only_keys)",
                "if sibling_item is not None:",
                "return {scalar_key: raw_text}",
                '"receipt not held"',
                '"without receipt"',
                '"no statement"',
                '"notice not sent"',
                '"notice of intent not lodged"',
                '"no notice of intent"',
                '"no acknowledgement"',
                "def personal_super_contribution_subject(",
                "personal_super_contribution_subject(item)",
                "contribution_date = normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES[\"contribution_date\"])",
                "if evidence_missing(contribution_date) or parse_iso_date(contribution_date) is None:",
                "def offset_subject(",
                "offset_subject(item, kind)",
                "raw type {display_value(normalized_item_field(item, OFFSET_FIELD_ALIASES['kind']))}",
                'f"notes {display_value(normalized_item_field(item, SUPER_CONTRIBUTION_FIELD_ALIASES[\'notes\']))}"',
                'QuestionSpec("deductions", "Deductions", "Deduction notes", "D1-D10 deductions", False)',
                'QuestionSpec("offsets", "Offsets", "Offset notes", "Tax offsets", False)',
                'QuestionSpec("tax_offsets", "Offsets", "Tax offset notes", "Tax offsets", False)',
                'if key in SUPER_CONTRIBUTION_NESTED_KEYS:',
                'if key in OFFSET_NESTED_KEYS:',
            ],
        )
    )
    if not contains_in_order(
        text,
        [
            '("self education", "self-education", "education", "training", "seminar", "course")',
            '("tool", "equipment", "asset", "computer", "laptop", "software", "monitor")',
            '("union", "professional", "membership", "accreditation", "licence", "license")',
        ],
    ):
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "software/tool routing must precede broad licence/membership routing"))
    amount_malformed_match = re.search(r"def amount_malformed\(.*?^def ", text, re.DOTALL | re.MULTILINE)
    if amount_malformed_match and re.search(r"amount\s*<\s*0", amount_malformed_match.group(0)):
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "shared amount_malformed must not reject signed BAS amounts"))
    raw_text_match = re.search(r"def raw_text_item_entry\(.*?^def ", text, re.DOTALL | re.MULTILINE)
    if raw_text_match and re.search(r"\[\"(evidence|notice_of_intent|fund_acknowledgement|review_signal)\"\]\s*=\s*raw_text", raw_text_match.group(0)):
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "raw free-form item text must not satisfy evidence fields"))
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
                "`taxmate-australia-payg-employer`",
                "`taxmate-australia-abn-business`",
                "`taxmate-australia-gst-bas`",
                "`taxmate-australia-employment-deductions`",
                "`taxmate-australia-work-from-home`",
                "`taxmate-australia-private-health-medicare`",
                "`taxmate-australia-superannuation`",
                "`taxmate-australia-shares-etfs-managed-funds`",
                "`taxmate-australia-capital-gains-tax`",
                "`taxmate-australia-crypto-assets`",
                "`taxmate-australia-property-rental-cgt`",
                "`taxmate-australia-records-evidence`",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            "\n".join([skill_text, skill_rules, capital_gains_skill, capital_gains_rules, capital_gains_evidence]),
            [
                "main residence exemption claim",
                "ownership period",
                "occupancy period",
                "rental or business use",
                "absence periods",
                "spouse or partner main-residence conflict",
                "property records",
                "main-residence source URLs",
                "review-first and prep-only",
                "Preserve false claim/use/conflict/concession values",
                "valid `0` or `0 days` values",
                "Do not work out exemption amounts",
                "fill official ATO PDFs",
                "main residence exemption",
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
                "ABN_NESTED_KEYS = (",
                "BAS_NESTED_KEYS = (",
                "ABN_FIELD_ALIASES = {",
                "ABN_NESTED_FIELD_ALIASES = {",
                "\"income_total\": (\"abn_income\", \"business_income\", \"income_total\", \"gross_income\", \"income\")",
                "\"expense_total\": (\"abn_expenses\", \"business_expenses\", \"expense_total\", \"expenses\")",
                "ABN_BUSINESS_SIGNAL_FIELDS = (",
                "ABN_CONTEXT_SIGNAL_FIELDS = tuple(key for key in ABN_BUSINESS_SIGNAL_FIELDS if key != \"psi\")",
                "BAS_FIELD_ALIASES = {",
                "\"period\": (\"bas_period\",)",
                "\"period_coverage\": (\"bas_period_coverage\",)",
                "\"payg_withholding\": (\"payg_withholding\", \"bas_payg_withholding\", \"bas_payg_withheld\", \"w2\", \"bas_w2\")",
                "BAS_NESTED_FIELD_ALIASES = {",
                "\"period\": (\"bas_period\", \"period\", \"tax_period\")",
                "BAS_CONTEXTUAL_FIELD_ALIASES = {",
                "\"gst_registered\": (\"registered\",)",
                "\"accounting_basis\": (\"accounting_basis\",)",
                "\"period_coverage\": (\"period_coverage\", \"coverage\")",
                "\"adjustments\": (\"adjustments\",)",
                "\"tax_invoice_evidence\": (\"invoice_evidence\", \"invoices\")",
                "ABN_CONTEXTUAL_FIELD_ALIASES = {",
                "\"activity\": (\"activity\",)",
                "\"income_total\": (\"income\",)",
                "\"expense_total\": (\"expenses\",)",
                "ABN_AMOUNT_SIGNAL_KEYS = {",
                "BAS_AMOUNT_SIGNAL_KEYS = set(BAS_AMOUNT_FIELDS).union(",
                "PHONE_EMPLOYER_MARKER_GROUPS = (",
                "PHONE_NESTED_ALIAS_GROUPS = (",
                "def phone_normalized_nested_raw(",
                "def phone_nested_known_field(",
                "def phone_freeform_mixed_use(",
                "def phone_text_has_affirmed_marker(",
                "def phone_marker_match_negated(",
                "def phone_gst_registration_unknown(",
                "return is_missing(value) or parse_gst_registration(value) is None",
                "def phone_user_paid_false(",
                "return phone_text_has_affirmed_marker(normalized, PHONE_EMPLOYER_MARKERS)",
                "def abn_amount_signal_key(",
                "def bas_amount_signal_key(",
                "def alias_answer_value(",
                "def normalized_alias_key(",
                "def alias_keys(",
                "alias.casefold()",
                "re.sub(r\"[^a-z0-9]+\", \"\", key.casefold())",
                "normalized_alias_key(key) == alias_normalized",
                "amount: bool = False",
                "for actual_key in alias_keys(values, key):",
                "if amount and amount_alias_default_false(value):",
                "if fallback is None:\n                    fallback = value",
                "if not contains_unknown(value):\n                return value",
                "if value is not None and not contains_unknown(value):",
                "def alias_candidates(",
                "def answer_candidates(",
                "def normalized_alias_values(",
                "gst_registration: bool = False",
                "if amount and amount_alias_default_false(value):",
                "def amount_alias_default_false(",
                "return value.strip().lower() in {\"false\", \"no\", \"n\", \"off\", \"unchecked\", \"none\", \"n/a\", \"not applicable\"}",
                "parsed = parse_gst_registration(value)",
                "item_total = supplied_item_total(item_values(value))",
                "json.dumps(value, sort_keys=True, default=str)",
                "def alias_values_conflict(",
                "def abn_alias_conflicts(",
                "contextual = abn_contextual_aliases_allowed(answers)",
                "ABN_CONTEXTUAL_FIELD_ALIASES.get(key, ()) if contextual else ()",
                "amount=key in {\"income_total\", \"expense_total\", \"income_streams\", \"expense_categories\"}",
                "def bas_alias_conflicts(",
                "contextual = has_bas_contextual_signal(answers) or has_bas_contextual_input_signal(answers)",
                "def abn_answer(",
                "if abn_contextual_aliases_allowed(answers):",
                "def abn_contextual_aliases_allowed(",
                "def has_abn_contextual_alias_signal(",
                "def bas_answer(",
                "def has_bas_contextual_signal(",
                "def has_bas_contextual_input_signal(",
                "exclude: set[str] | None = None",
                "def bas_contextual_answer(",
                "def bas_gst_registration_answer(",
                "def bas_contextual_input_signal(",
                "for aliases in BAS_FIELD_ALIASES.values()",
                "alias_candidates(answers, aliases)",
                "for nested_key in BAS_NESTED_KEYS:",
                "for aliases in BAS_NESTED_FIELD_ALIASES.values()",
                "alias_candidates(nested, aliases)",
                "amount = safe_money_value(item.get(key))",
                "if amount is not None:\n                values.append(amount)",
                "def item_amount_values(",
                "def item_amount_alias_conflict(",
                "def item_amount_alias_malformed(",
                "return item_amount(item) is None or item_amount_alias_conflict(item)",
                "if not amounts or any(amount is None for amount in amounts):\n        return None",
                "def supplied_item_total_conflict(",
                "def abn_summary(",
                "def bas_summary(",
                "raw[\"alias_conflicts\"] = alias_conflicts",
                "raw[\"alias_conflict\"] = bool(alias_conflicts)",
                "status = \"Accountant review\" if has_abn_inputs(answers) else \"N/A skipped\"",
                "status = \"Accountant review\" if has_bas_inputs(answers) else \"N/A skipped\"",
                "if supplied_item_total_conflict(income_total, income_streams):",
                "if supplied_item_total_conflict(expense_total, expense_categories):",
                "if any(item_amount_alias_conflict(item) for item in income_streams):",
                "if any(item_amount_alias_conflict(item) for item in expense_categories):",
                "or \"income_total\" in alias_conflicts",
                "or \"expense_total\" in alias_conflicts",
                "and \"income_streams\" not in alias_conflicts",
                "and \"expense_categories\" not in alias_conflicts",
                "or \"income_streams\" in alias_conflicts",
                "or \"expense_categories\" in alias_conflicts",
                "if key in alias_conflicts:\n            raw[key] = None",
                "if has_bas_contextual_signal(answers) or has_bas_contextual_input_signal(answers):",
                "candidate = alias_answer_value(answers, BAS_CONTEXTUAL_FIELD_ALIASES.get(key, ()), amount=key in BAS_AMOUNT_FIELDS)",
                "def abn_business_evidence_rows(",
                "def bas_evidence_rows(",
                "ATO_ABN_BUSINESS_SOURCES = [",
                "ATO_BAS_SOURCES = [",
                "if contains_unknown(value):\n        return True",
                "if isinstance(value, list):\n        return not value or any(evidence_missing(item) for item in value)",
                "if isinstance(value, dict):\n        return not value or any(evidence_missing(item) for item in value.values())",
                "\"no records\"",
                "\"no bookkeeping records\"",
                "\"no business records\"",
                "\"record not held\"",
                "\"without records\"",
                "\"n/a\"",
                "\"not applicable\"",
                "\"no tax invoice\"",
                "\"tax invoice not applicable\"",
                "\"tax invoices not available\"",
                "\"not available\"",
                "\"unavailable\"",
                "if isinstance(raw_income_total, (dict, list)):",
                "if isinstance(raw_expense_total, (dict, list)):",
                "def item_amount_evidence_needed(",
                "return item_amount(item) is None",
                "or any(item_amount_evidence_needed(item) for item in income_streams + expense_categories)",
                "raw[\"record_system_required\"] = any(",
                "raw[\"record_evidence\"] = raw[\"record_system_required\"] and evidence_missing(raw.get(\"record_system\"))",
                "bool(income_streams or expense_categories or raw[\"amount_evidence\"])",
                "abn_items = abn_rows(answers) if has_abn_inputs(answers) else []",
                "bas_items = bas_rows(answers) if has_bas_inputs(answers) else []",
                "if key in answers and bas_input_signal(key, answers.get(key)):",
                "if has_bas_contextual_input_signal(answers):",
                "def bas_negative_gst_only_payg_context(",
                "gst_registered = bas_gst_registration_answer(answers)",
                "return not (gst_status is False and bas_negative_gst_only_payg_context(answers))",
                "return not has_bas_contextual_input_signal(answers, exclude={\"gst_registered\"})",
                "return any(bas_input_signal(key, bas_answer(answers, key)) for key in BAS_FIELD_ALIASES)",
                "if has_nested_abn_inputs(answers):",
                "def has_nested_abn_inputs(",
                "for key in ABN_FIELD_ALIASES:",
                "def abn_input_signal(",
                "if abn_amount_signal_key(key) and amount_alias_default_false(value):",
                "return not abn_review_flag_false(value)",
                "def bas_input_signal(",
                "if bas_amount_signal_key(key) and amount_alias_default_false(value):",
                "if key == \"tax_invoice_evidence\":",
                "return contains_unknown(value)",
                "def abn_review_flag_false(",
                "isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0",
                "\"unchecked\"",
                "if abn_review_flag_false(value):\n            terms.append(f\"{key.replace('_', ' ')} false\")",
                "key != \"abn\" or not bare_abn_is_payg(answers)",
                "raw[\"worksheet_facts\"] = any(",
                "raw[\"basis_evidence\"] = contains_unknown(raw.get(\"accounting_basis\")) or (",
                "raw[\"worksheet_facts\"] and evidence_missing(raw.get(\"accounting_basis\"))",
                "raw[\"period_coverage_evidence\"] = contains_unknown(raw.get(\"period_coverage\"))",
                "raw[\"worksheet_facts\"] and evidence_missing(raw.get(\"period_coverage\"))",
                "summary.get(\"basis_evidence\")",
                "summary.get(\"period_coverage_evidence\")",
                "summary.get(\"alias_conflict\")",
                "\"ABN alias reconciliation required\"",
                "\"BAS alias reconciliation required\"",
                "abn = abn_summary(answers) if has_abn_inputs(answers) else {}",
                "bas = bas_summary(answers) if has_bas_inputs(answers) else {}",
                "if key in answers and abn_input_signal(key, answers.get(key)):",
                "for key in ABN_CONTEXT_SIGNAL_FIELDS",
                "def base_item_status(",
                "def should_render_base_item(",
                "def abn_flat_value_is_absent(",
                "def bas_flat_value_is_absent(",
                "REVIEWABLE_COMPLEX_FIELDS = (",
                "isinstance(value, (dict, list))",
                "key in REVIEWABLE_ABN_FIELDS or key in REVIEWABLE_BAS_FIELDS or key == \"gst_registered\"",
                "items.extend(wfh_rows(wfh_answers(answers)))",
                "items.extend(asset_rows(asset_answers(answers)))",
                "def bare_abn_is_payg(",
                "def has_business_context_for_bare_abn(",
                "if has_bas_inputs(answers):",
                "def has_payg_context_for_bare_abn(",
                "if payg_item_context_for_bare_abn(answers):\n        return True",
                "if payg_item_context_for_bare_abn(nested):\n                return True",
                "def payg_item_context_for_bare_abn(",
                "first_payg_items(record) is not None or bool(payg_item_values(record.get(\"items\")))",
                "def has_business_context_for_bare_abn(",
                "if has_bas_inputs(answers):\n        return True",
                "if has_abn_contextual_alias_signal(answers):\n        return True",
                "gst_registered = bas_gst_registration_answer(answers)",
                "gst_status = parse_gst_registration(gst_registered)",
                "rows.extend(abn_business_evidence_rows(answers))",
                "rows.extend(bas_evidence_rows(answers))",
                "unknown_as_missing=True",
                "math.isfinite(amount)",
                "raise ValueError(f\"invalid money value: {value}\") from None",
                "phrase in lowered",
                '"not confirmed"',
                "def extraction_rows(",
                "taxmate_handoff.normalize_extraction_row(",
                "if normalized is not None:",
                "def finalize_guide_row(",
                'raise ValueError("internal guide row missing explicit facts")',
                'raise ValueError("internal guide row missing explicit row_kind")',
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
                "PAYG_AMOUNT_FIELDS = (",
                "PAYG_SUPPLEMENTAL_FIELDS = (",
                "PAYG_FIELD_ALIASES = {",
                "\"payg_employer_name\"",
                "\"payg_employer_abn\"",
                "\"amount_withheld\"",
                "PAYG_NESTED_BASE_FIELD_KEYS = {",
                "PAYG_ITEM_ALIASES = (",
                "PAYG_SOURCES = [",
                "items.extend(payg_rows(payg, answers))",
                "rows.extend(payg_evidence_rows(payg_answers(answers), answers))",
                "def payg_answers(",
                "merged = payg_drop_absence_fields(merged)",
                "normalized_answer_fields = normalize_payg_fields(payg_top_level_alias_answers(answers))",
                "def payg_top_level_alias_answers(",
                "narrowed.pop(\"abn\", None)",
                "def payg_rows(",
                "def payg_statement_row(",
                "def payg_supplemental_row(",
                "def payg_supplemental_needs_evidence(",
                "def payg_supplemental_tab_text(",
                "def payg_reconciliation_row(",
                "def payg_evidence_rows(",
                "def payg_merge_flat_values(",
                "def payg_prefer_merged_value(",
                "def payg_values_with_declines(",
                "canonical = PAYG_FLAT_FIELD_KEYS.get(key, PAYG_ALIAS_TO_FIELD.get(key, key))",
                "if canonical in PAYG_AMOUNT_FIELDS:",
                "def payg_scalar_statement_gap_value(",
                "def payg_item_values(",
                "def has_meaningful_payg_item_value(",
                "if key == \"finalised\" and value is False:",
                "def payg_alias_values(raw: Dict[str, Any], aliases: tuple[str, ...], canonical: str)",
                "def payg_alias_value_usable(",
                "def payg_concrete_alias_value(",
                "if canonical in PAYG_AMOUNT_FIELDS and isinstance(raw.get(alias), (dict, list)):",
                "if canonical in PAYG_AMOUNT_FIELDS and payg_source_declines_workflow(canonical, raw.get(alias)):",
                "not payg_field_absence_value(canonical, raw.get(alias))",
                "if nested_key in PAYG_ITEM_ALIASES and isinstance(value, (dict, list)):",
                "return not payg_item_values(value)",
                "def normalize_payg_item(",
                "def normalize_payg_fields(",
                "def payg_drop_absence_fields(",
                "def payg_merge_nested_values(",
                "def payg_nested_base_rows(",
                "def payg_flat_row_covers_nested_fact(",
                "payg_field_absence_value(key, flat_value)",
                "has_unknown_payg_flat_value(key, flat_value)",
                "payg_amount_field_needs_evidence(key, flat_value)",
                "return True",
                "flat_value == nested_value",
                "def payg_statement_missing(",
                "def payg_finalised_missing(",
                "return bool(lowered)",
                "lowered in GENERIC_FIELD_ABSENCE_PHRASES",
                "def parse_payg_bool(",
                "def payg_item_amounts_need_evidence(",
                "def payg_aggregate_value(",
                "def payg_aggregate_evidence_gaps(",
                "def payg_aggregate_payer_detail_gap(",
                "def payg_reconciliation_conflict(",
                "payg_aggregate_value(raw, \"gross\")",
                "payg_aggregate_value(raw, \"withheld\")",
                "payg_nested_base_status(",
                "PAYG aggregate facts: confirm",
                "def payg_alias_amount_conflict(",
                "def payg_values_conflict(",
                "def payg_statement_values_conflict(",
                "def payg_lump_sum_label_evidence(",
                "def payg_decline_contradiction(",
                "def payg_alias_conflict_text(",
                "has_item_context = bool(nested_items or top_level_items or nested_alias_items)",
                "elif nested_alias_items:",
                "def has_unknown_payg_flat_value(",
                "has_item_context and has_unknown_payg_flat_value(key, value)",
                "answers.get(\"main_occupation\")",
                "def payg_amount_field_needs_evidence(",
                "payg_amount_field_needs_evidence(key, value)",
                "payg_aggregate_evidence_gaps(payg)",
                "answer_declines = payg_decline_values(answers)",
                "scalar_statement_gap = payg_scalar_statement_gap_value(answers)",
                "nested_items = payg_item_values(raw_items)",
                "nested_alias_raw_items = first_payg_items(merged)",
                "def payg_items_conflict(",
                "payg_items_conflict(raw_items, nested_alias_raw_items)",
                "merged[\"_alias_conflicts\"] = sorted(set(list(merged.get(\"_alias_conflicts\") or []) + [\"items\"]))",
                "merged = payg_merge_flat_values(merged, flat_values)",
                "merged = payg_backfill_single_item_context(merged)",
                "def payg_backfill_single_item_context(",
                "if len(items) != 1:",
                "for key in (\"abn\",):",
                "moved_keys.append(key)",
                "merged.pop(key, None)",
                "no payg statements",
                "PAYG statement needs",
                "PAYG aggregate supplied details",
                "PAYG totals need corrected reconciliation",
                "tax withheld {money_text(payg_amount_value(item.get('withheld')))}",
                "RFBA {money_text(payg_amount_value(item.get('rfba')))}",
                "RESC {money_text(payg_amount_value(item.get('resc')))}",
                "payg_field_absence_value(\"lump_sum\", item.get(\"lump_sum\"))",
                "lump sum A {money_text(payg_amount_value(item.get('lump_sum_a')))}",
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
                "if not item_amounts or any(amount is None for amount in item_amounts):",
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
                "INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS = (\"amount\", \"dividend_amount\", \"cash_amount\")",
                "INVESTMENT_DIVIDEND_AMOUNT_FIELDS = (",
                "INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS = (\"amount\", \"distribution_amount\")",
                "INVESTMENT_DISTRIBUTION_AMOUNT_FIELDS = (",
                "INVESTMENT_TRUST_AMOUNT_FIELDS = (",
                "INVESTMENT_INTEREST_REQUIRED_AMOUNT_GROUPS = ((\"amount\",),)",
                "INVESTMENT_DIVIDEND_REQUIRED_AMOUNT_GROUPS = (",
                "INVESTMENT_DISTRIBUTION_REQUIRED_AMOUNT_GROUPS = (",
                "INVESTMENT_TRUST_REQUIRED_AMOUNT_GROUPS = (",
                "INVESTMENT_ZERO_COMPONENT_AMOUNT_FIELDS = (",
                "\"franked_amount\",",
                "\"unfranked_amount\",",
                "\"franked_distribution\",",
                "INVESTMENT_SOURCES = [",
                "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/investment-income",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/investing-in-bank-accounts-and-income-bonds",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/shares-funds-and-trusts/investing-in-shares/refund-of-franking-credits-for-individuals",
                "investment = investment_answers(answers)",
                "items.extend(investment_rows(investment, answers))",
                "rows.extend(investment_evidence_rows(investment_answers(answers), answers))",
                "def base_item_sources(",
                "return PAYG_SOURCES",
                "if spec.key in REVIEWABLE_INVESTMENT_FIELDS",
                "INVESTMENT_ITEM_ALIASES = {",
                "INVESTMENT_AGGREGATE_ALIASES = {",
                "def investment_answers(",
                "def investment_aggregate_alias_values(",
                "def investment_aggregate_record_conflict(",
                "def investment_aggregate_values_conflict(",
                "\"_aggregate_conflicts\"",
                "\"_item_conflicts\"",
                "def investment_item_alias_record_conflict(",
                "def investment_items_conflict(",
                "def investment_item_conflict_keys(",
                "investment_item_values(nested_value) and investment_item_values(answer_value)",
                "item alias conflicts",
                "def investment_rows(",
                "investment_base_item_value(",
                "def investment_reconciliation_needs_evidence(",
                "def investment_aggregate_needs_evidence(",
                "def investment_interest_row(",
                "def investment_dividend_row(",
                "def investment_distribution_row(",
                "def investment_trust_row(",
                "def investment_reconciliation_row(",
                "def investment_evidence_rows(",
                "def first_investment_items(",
                "first_investment_items(merged, source_keys)",
                "first_investment_items(answers, source_keys)",
                "if not investment_item_values(merged.get(key)) and investment_item_values(value):",
                "def investment_reconciliation_evidence_text(",
                "def investment_has_reconciliation_target(",
                "investment_has_reconciliation_target(raw, interest_items, dividend_items, distribution_items)",
                "def investment_aggregate_value(",
                "investment_aggregate_value(raw, \"interest_income\")",
                "investment_aggregate_value(raw, \"dividend_income\")",
                "def investment_statement_missing(",
                "\"statement not received\"",
                "\"statement not provided\"",
                "\"not provided\"",
                "\"do not have\"",
                "\"don't have\"",
                "def investment_required_amount_groups(",
                "def investment_required_amount_missing(",
                "def investment_amount_is_supplied(",
                "if key in INVESTMENT_ZERO_COMPONENT_AMOUNT_FIELDS and amount == 0:",
                "def investment_franking_credit_missing(",
                "investment_franking_credit_missing(item, franked_key)",
                "def investment_has_direct_amount(",
                "def investment_direct_amount_value(",
                "def investment_direct_amount_unresolved(",
                "investment_direct_amount_unresolved(item, INVESTMENT_DIVIDEND_DIRECT_AMOUNT_FIELDS)",
                "investment_direct_amount_unresolved(item, INVESTMENT_DISTRIBUTION_DIRECT_AMOUNT_FIELDS)",
                "def investment_direct_amount_conflict(",
                "\"dividend_amount\",",
                "\"cash_amount\"",
                "\"distribution_amount\",",
                "def investment_franking_uncertain(",
                "if lowered in {\"no\", \"n\", \"false\", \"0\", \"not confirmed\", \"not held\", \"not available\", \"none\"}:",
                "def dividend_amounts_need_evidence(",
                "dividend_amounts_need_evidence(item)",
                "def dividend_component_total(",
                "return investment_itemized_total(values)",
                "def dividend_direct_component_conflict(",
                "dividend_direct_component_conflict(item)",
                "def distribution_amounts_need_evidence(",
                "distribution_amounts_need_evidence(item)",
                "def distribution_direct_taxable_conflict(",
                "distribution_direct_taxable_conflict(item)",
                "def investment_amount_present(",
                "def investment_total_conflict(",
                "def investment_reconciliation_conflict(",
                "def investment_category_total(",
                "def investment_itemized_total(",
                "def interest_category_total(",
                "def dividend_distribution_category_total(",
                "def dividend_distribution_total(",
                "def first_present(",
                "cash dividend {money_text(dividend_item_total(item))}",
                "distribution {money_text(distribution_item_total(item))}",
                "return item_total is None or investment_total_conflict(aggregate_value, item_total)",
                "if key in REVIEWABLE_INVESTMENT_FIELDS:",
                "if investment_statement_missing(value):",
                "foreign components {investment_foreign_components_text(item)}",
                "def investment_review_flag_sentence(",
                "def investment_review_flag_value(",
                "def investment_boolean_flag_value(",
                "def investment_foreign_components_text(",
                "if value is True:",
                "if value is False:",
                "return \"false\"",
                "cost-base adjustment {cost_base}",
                "AMIT {amit}",
                "TFN withholding {money_text(investment_money_value(item.get('tfn_withheld')))}",
                "franking credit {money_text(investment_money_value(item.get('franking_credit')))}",
                "foreign tax offset {money_text(investment_money_value(item.get('foreign_tax_offset')))}",
                "non-assessable payment {money_text(investment_money_value(item.get('non_assessable_payment')))}",
                "Trust distribution routing for individual beneficiary",
                "TaxMate does not prepare a trust return",
                "Investment totals need corrected reconciliation",
                "REVIEWABLE_CGT_FIELDS = (",
                "\"cgt_items\"",
                "CGT_FLAT_FIELD_KEYS = {",
                "\"cgt_event_type\": \"event_type\"",
                "\"cgt_summary\": \"summary\"",
                "CGT_NESTED_FIELD_KEYS = {",
                "\"asset_description\": \"asset\"",
                "CGT_ITEM_ALIASES = (",
                "CGT_ITEM_FIELD_ALIASES = {",
                "def cgt_canonical_field_key(",
                "CGT_RECONCILIATION_FIELDS = (\"proceeds\", \"cost_base\", \"incidental_costs\", \"losses\")",
                "CGT_LOSS_REVIEW_AMOUNT_FIELDS = (\"current_year_losses\", \"carried_forward_losses\")",
                "CGT_AMOUNT_FIELDS = (*CGT_RECONCILIATION_FIELDS, *CGT_LOSS_REVIEW_AMOUNT_FIELDS)",
                "CGT_DISCOUNT_REVIEW_TEXT_FIELDS = (\"discount_timing\", \"discount_eligibility\")",
                "CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS = (",
                "CGT_SMALL_BUSINESS_CONCESSION_FLAG_FIELDS = (",
                "CGT_SMALL_BUSINESS_CONCESSION_FIELDS = (",
                "CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS = (",
                "CGT_MAIN_RESIDENCE_REVIEW_FLAG_FIELDS = (",
                "CGT_MAIN_RESIDENCE_REVIEW_FIELDS = (",
                "CGT_FLAT_AMOUNT_FIELDS = tuple(",
                "CGT_DATE_FIELDS = (\"acquisition_date\", \"disposal_date\")",
                "CGT_BOOLEAN_REVIEW_FIELDS = (",
                "CGT_DECLINE_SIGNAL_KEY = \"_decline_signals\"",
                "CGT_CONFLICT_SIGNAL_KEY = \"_conflict_signals\"",
                "ATO_CGT_SOURCES = [",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-events",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/how-to-calculate-your-cgt",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/cost-base-of-asset",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/capital-proceeds-from-disposing-of-assets",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount",
                "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/foreign-residents-and-capital-gains-tax/cgt-discount-for-foreign-residents",
                "ATO_PROPERTY_RECORDS_SOURCE = \"https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax/keeping-records-for-property\"",
                "ATO_CGT_MAIN_RESIDENCE_ELIGIBILITY_SOURCE = \"https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/property-and-capital-gains-tax/your-main-residence-home/eligibility-for-main-residence-exemption\"",
                "ATO_CGT_MAIN_RESIDENCE_SOURCES = [",
                "ATO_CGT_SMALL_BUSINESS_CONCESSIONS_SOURCE = \"https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions\"",
                "ATO_CGT_SMALL_BUSINESS_CONCESSION_SOURCES = [",
                "items.extend(cgt_rows(cgt))",
                "rows.extend(cgt_evidence_rows(cgt_answers(answers)))",
                "def cgt_answers(",
                "field_conflicts: List[str] = []",
                "if cgt_values_conflict(nested_key, existing, value):",
                "item_conflicts: List[str] = []",
                "raw_context = isinstance(raw, dict)",
                "existing_context=bool(flat_items) or raw_context",
                "def cgt_flat_alias_should_replace(",
                "def cgt_answer_values(",
                "signal = has_meaningful_cgt_signal(canonical_key, value)",
                "signal and (has_context or not cgt_fact_requires_context(canonical_key))",
                "def cgt_item_values(",
                "existing_context=bool(flat_items)",
                "review_conflicts = cgt_itemized_review_field_conflicts(merged, items)",
                "def cgt_itemized_review_field_conflicts(",
                "CGT_MAIN_RESIDENCE_REVIEW_FIELDS + CGT_SMALL_BUSINESS_CONCESSION_FIELDS",
                "def cgt_items_with_inherited_review_flags(",
                "for key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS",
                "for key in CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS",
                "for key in CGT_BOOLEAN_REVIEW_FIELDS",
                "cgt_inherited_review_flag(",
                "cgt_boolean_false(value) or cgt_review_flag_has_signal(value) or cgt_boolean_needs_evidence(value)",
                "def cgt_merge_item_values(",
                "def cgt_merge_item_value(",
                "merged_item[key] = cgt_merge_value(canonical, merged_item.get(key), value)",
                "def normalize_cgt_item(",
                "def cgt_item_alias_conflict_detail(",
                "\"_alias_conflict_details\"",
                "def cgt_items_conflict(",
                "def cgt_item_values_conflict(",
                "for index in range(max(len(left_items), len(right_items))):",
                "merged_items.append(right_item)",
                "has_context = any(cgt_answer_context_value(key, value) for key, value in item.items())",
                "canonical_key = cgt_canonical_field_key(key)",
                "if canonical_key == \"no_cgt\" and cgt_summary_has_event_fact(value):",
                "values.setdefault(CGT_CONFLICT_SIGNAL_KEY, [])",
                "if key == CGT_CONFLICT_SIGNAL_KEY:",
                "def cgt_merge_value(",
                "def cgt_values_conflict(",
                "def cgt_conflict_value(",
                "if cgt_evidence_gap_requires_context(key) and has_explicit_cgt_evidence_gap(key, value):",
                "def cgt_rows(",
                "def cgt_evidence_rows(",
                "CGT-SCHEDULE",
                "CGT-EVENT-",
                "CGT-RECON",
                "General CGT event intake and accountant-review schedule",
                "No capital gain or loss amount is worked out.",
                "def cgt_evidence_gaps(",
                "def cgt_item_evidence_gaps(",
                "def cgt_reconciliation_conflicts(",
                "def cgt_item_amount_total(",
                "def cgt_reconciliation_row(",
                "def cgt_has_top_level_details(",
                "has_item_context = bool(cgt_item_values(raw.get(\"items\")) or cgt_item_values(raw.get(\"cgt_items\")))",
                "has_context = has_item_context or any(",
                "not (has_item_context and cgt_itemized_inherited_main_residence_key(key))",
                "def cgt_itemized_inherited_main_residence_key(",
                "return key in CGT_MAIN_RESIDENCE_REVIEW_FIELDS",
                "or key in CGT_SMALL_BUSINESS_CONCESSION_FIELDS",
                "has_context or not cgt_fact_requires_context(key)",
                "and (has_context or not cgt_evidence_gap_requires_context(key))",
                "def cgt_itemized_top_level_evidence(",
                "def cgt_itemized_top_level_evidence_gaps(",
                "def cgt_itemized_summary_evidence(",
                "def cgt_loss_amounts_need_evidence(",
                "def cgt_discount_text_needs_evidence(",
                "def cgt_discount_or_residency_has_review_signal(",
                "def cgt_small_business_concession_has_review_signal(",
                "def cgt_small_business_concession_text_has_signal(",
                "def cgt_small_business_concession_evidence_gaps(",
                "def cgt_main_residence_has_review_signal(",
                "cgt_review_flag_has_signal(raw.get(key)) or cgt_boolean_needs_evidence(raw.get(key))",
                "def cgt_main_residence_has_source_signal(",
                "def cgt_small_business_concession_has_source_signal(",
                "key in raw and cgt_boolean_false(raw.get(key))",
                "def cgt_main_residence_text_has_signal(",
                "def cgt_main_residence_evidence_gaps(",
                "def cgt_evidence_gap_requires_context(",
                "return key == \"records\" or key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS",
                "def cgt_fact_requires_context(",
                "return key == \"records\" or key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS",
                "def cgt_row_sources(",
                "main residence claim {cgt_boolean_flag_text(raw.get('main_residence_claim'))}",
                "main residence property records {cgt_field_text(raw, 'main_residence_property_records')}",
                "spouse/partner main residence conflict {cgt_boolean_flag_text(raw.get('main_residence_spouse_conflict'))}",
                "main residence exemption review",
                "small business CGT concession review",
                "rental/business use or spouse/partner main-residence conflict",
                "small business CGT concession type evidence",
                "active asset evidence",
                "entity, affiliate, or connected entity evidence",
                "small business CGT concession evidence",
                "CGT item review field conflicts",
                "main residence ownership/occupancy/absence evidence",
                "main residence property records",
                "no-CGT answer with CGT facts",
                "CGT field conflicts",
                "CGT item alias conflicts",
                "CGT item totals need corrected reconciliation",
                "key not in (\"items\", \"cgt_items\", \"_item_conflicts\", CGT_DECLINE_SIGNAL_KEY, CGT_CONFLICT_SIGNAL_KEY)",
                "CGT itemized facts need",
                "for key in (\"proceeds\", \"cost_base\")",
                "for key in (\"incidental_costs\", \"losses\")",
                "CGT item {idx} needs",
                "signal.startswith(\"records \")",
                "conflict signals {conflict_text}",
                "CGT event needs",
                "before accountant review; no capital gain or loss amount worked out.",
                "def cgt_review_terms(",
                "def cgt_values_with_declines(",
                "def cgt_decline_values(",
                "def cgt_declines_without_facts(",
                "def cgt_has_facts(",
                "def cgt_has_signal(",
                "def cgt_review_flag_has_signal(",
                "def has_explicit_cgt_evidence_gap(",
                "if key in CGT_BOOLEAN_REVIEW_FIELDS:\n        return cgt_boolean_needs_evidence(value)",
                "if key in CGT_DISCOUNT_REVIEW_TEXT_FIELDS:\n        return has_meaningful_value(value) and contains_unknown(value)",
                "if key in CGT_SMALL_BUSINESS_CONCESSION_TEXT_FIELDS:",
                "if key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS:",
                "return has_meaningful_value(value) and contains_unknown(value)",
                "evidence.extend(cgt_main_residence_evidence_gaps(raw))",
                "cgt_row_sources(item)",
                "cgt_row_sources(raw)",
                "def cgt_decline_contradiction(",
                "def cgt_declines_workflow(",
                "def cgt_source_declines_workflow(",
                "def cgt_summary_has_event_fact(",
                "if key == \"summary\" and cgt_summary_has_event_fact(value):",
                "if lowered in CGT_DECLINE_PHRASES:",
                "\"cgt event\"",
                "\"capital gains tax event\"",
                "\"selling\"",
                "\"sell\"",
                "\"gifted\"",
                "\"transferred\"",
                "def cgt_field_absence_value(",
                "if key == \"no_cgt\":",
                "return cgt_boolean_true(value) or cgt_declines_workflow(value)",
                "if key == \"no_cgt\":\n        return False",
                "if nested_key in CGT_AMOUNT_FIELDS and isinstance(value, bool):",
                "not cgt_evidence_gap_requires_context(key)",
                "if key in (\"records\", \"main_residence_property_records\") and cgt_records_missing(value):",
                "if nested_key in (\"records\", \"main_residence_property_records\") and cgt_records_missing(value):",
                "if nested_key in CGT_MAIN_RESIDENCE_REVIEW_TEXT_FIELDS:",
                "def cgt_records_missing(",
                "\"record not held\"",
                "\"receipt not held\"",
                "\"do not have\"",
                "def cgt_amount_needs_evidence(",
                "def cgt_amount_malformed(",
                "def cgt_money_value(",
                "def cgt_date_needs_evidence(",
                "def cgt_boolean_flag_text(",
                "def cgt_bool_text(",
                "def cgt_amount_text(",
                "proceeds {cgt_amount_text(raw.get('proceeds'))}",
                "cost base {cgt_amount_text(raw.get('cost_base'))}",
                "incidental costs {cgt_amount_text(item.get('incidental_costs'))}",
                "losses {cgt_amount_text(item.get('losses'))}",
                "current-year losses {cgt_amount_text(item.get('current_year_losses'))}",
                "carried-forward losses {cgt_amount_text(item.get('carried_forward_losses'))}",
                "exemption flag {cgt_boolean_flag_text(raw.get('exemption_flag'))}",
                "discount flag {cgt_boolean_flag_text(raw.get('discount_flag'))}",
                "discount claim {cgt_boolean_flag_text(raw.get('discount_claim'))}",
                "discount timing {cgt_field_text(raw, 'discount_timing')}",
                "discount eligibility {cgt_field_text(raw, 'discount_eligibility')}",
                "foreign resident discount {cgt_boolean_flag_text(raw.get('foreign_resident_discount'))}",
                "concession flag {cgt_boolean_flag_text(raw.get('concession_flag'))}",
                "concession type {cgt_field_text(raw, 'concession_type')}",
                "business asset {cgt_boolean_flag_text(raw.get('business_asset'))}",
                "active asset {cgt_boolean_flag_text(raw.get('active_asset'))}",
                "entity/affiliate/connected entity {cgt_boolean_flag_text(raw.get('entity_affiliate_connected_entity'))}",
                "retirement exemption {cgt_boolean_flag_text(raw.get('retirement_exemption'))}",
                "rollover {cgt_boolean_flag_text(raw.get('rollover'))}",
                "15-year exemption {cgt_boolean_flag_text(raw.get('fifteen_year_exemption'))}",
                "50% active asset reduction {cgt_boolean_flag_text(raw.get('active_asset_reduction_50'))}",
                "concession evidence {cgt_field_text(raw, 'concession_evidence')}",
                "business use {cgt_boolean_flag_text(raw.get('business_use'))}",
                "private use {cgt_boolean_flag_text(raw.get('private_use'))}",
                "row[\"tab_kind\"] = \"review\"",
                "cgt_review_flag_has_signal(raw.get(key))",
                "if spec.key in CGT_FLAT_AMOUNT_FIELDS and isinstance(value, bool):",
                "cgt_flat_alias_should_replace(nested_key, existing, value)",
                "existing_flat_context",
                "has_meaningful_cgt_signal(key, existing)",
                "if nested_key == \"no_cgt\" and cgt_boolean_false(value):",
                "if nested_key in (\"records\", \"main_residence_property_records\") and cgt_records_missing(value):",
                "if nested_key in CGT_BOOLEAN_REVIEW_FIELDS and cgt_boolean_false(value):",
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
                "if foreign_income_items_need_amount_evidence(items):",
                "def foreign_income_items_need_amount_evidence(",
                "def foreign_income_amount_is_supplied(",
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
                "def foreign_income_item_amount_total(",
                "if not amounts or any(amount is None for amount in amounts):",
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
                "def private_health_row_checked_at(",
                "def generation_checked_at(",
                '"checked_at": checked_at if checked_at is not None else generation_checked_at()',
            ],
        )
    )
    for stale in [
        "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/bringing-losses-forward",
        "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt/capital-gains-tax-discount",
        "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/if-you-are-not-an-australian-resident",
    ]:
        if stale in text:
            findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, f"stale CGT source URL: {stale}"))
    source_state = read_optional(root, "data/ato_knowledge_base/source_registry.json") + "\n" + read_optional(root, "data/ato_knowledge_base/source_coverage.json")
    if source_state.strip():
        findings.extend(
            fail_if_missing(
                INDIVIDUAL_INTAKE_CONTRACT,
                source_state,
                [
                    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt",
                    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount",
                    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/foreign-residents-and-capital-gains-tax/cgt-discount-for-foreign-residents",
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
                "`taxmate-australia-crypto-assets`",
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
        if "`taxmate-australia-individual-return`: V1 individual return intake" in line:
            root_individual_route = line
            break
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            root_individual_route,
            [
                "`taxmate-australia-individual-return`: V1 individual return intake",
                "PSI",
                "crypto CGT",
            ],
        )
    )
    prep_cgt_route = ""
    for line in individual_prep_doc.splitlines():
        if "`taxmate-australia-shares-etfs-managed-funds`" in line:
            prep_cgt_route = line
            break
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            prep_cgt_route,
            [
                "`taxmate-australia-shares-etfs-managed-funds`",
                "`taxmate-australia-capital-gains-tax`",
                "`taxmate-australia-crypto-assets`",
                "`taxmate-australia-property-rental-cgt`",
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


def check_private_health_medicare_contract(root: Path) -> List[Finding]:
    intake = read(root, "scripts/taxmate_intake.py")
    findings = fail_if_missing(
        PRIVATE_HEALTH_MEDICARE_CONTRACT,
        intake,
        [
            *(f"def {name}(" for name in PRIVATE_HEALTH_MEDICARE_RUNTIME_FUNCTIONS),
            *(f"def {name}(" for name, _ in PRIVATE_HEALTH_MEDICARE_TYPED_HELPERS),
            "PRIVATE_HEALTH_MEDICARE_FLAT_FIELD_ALIASES = {",
            "def private_health_flat_alias_subset(",
            "PRIVATE_HEALTH_SUPPORTED_BENEFIT_CODES = frozenset(",
            "ATO_PRIVATE_HEALTH_STATEMENT_SOURCE =",
            "ATO_PRIVATE_HEALTH_REBATE_CLAIM_SOURCE =",
            "ATO_MEDICARE_LEVY_SOURCE =",
            "ATO_MLS_RETURN_SOURCE =",
            "ATO_MLS_THRESHOLDS_SOURCE =",
            "ATO_MLS_FAMILY_DEPENDANTS_SOURCE =",
            "ATO_MLS_PAYING_SOURCE =",
            "ATO_PRIVATE_HEALTH_STATEMENT_SOURCES = [",
            "ATO_MEDICARE_LEVY_SOURCES = [",
            "ATO_MLS_SOURCES = [",
            "ATO_SPOUSE_DEPENDANT_SOURCES = [",
            "items.extend(private_health_medicare_rows(private_health_medicare))",
            "rows.extend(private_health_medicare_evidence_rows(private_health_medicare))",
            *PRIVATE_HEALTH_MEDICARE_NOOP_FRAGMENTS,
        ],
    )
    sanitizer = python_function_text(intake, "private_health_sanitized_value")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            sanitizer,
            (
                "if not contains_unknown(value) and normalized in PRIVATE_HEALTH_NOOP_TEXT:",
                "if isinstance(value, list):",
                "if isinstance(value, dict):",
                "private_health_sanitized_value(item, false_is_value=false_is_value)",
                "if not contains_unknown(value) and normalized in PRIVATE_HEALTH_NOOP_TEXT:\n"
                "            return PRIVATE_HEALTH_NO_VALUE",
                "return sanitized_items if sanitized_items else PRIVATE_HEALTH_NO_VALUE",
                "return sanitized_record if sanitized_record else PRIVATE_HEALTH_NO_VALUE",
            ),
        )
    )
    filter_record = python_function_text(intake, "private_health_filter_record_values")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            filter_record,
            (
                'if field == "source_urls":',
                'if field == "checked_at":',
                'field == "count"',
                'value.strip().lower() == "none"',
                "private_health_detail_with_metadata(",
                "private_health_add_metadata(filtered, metadata, field_aliases)",
            ),
        )
    )
    collection_entries = python_function_text(
        intake,
        "private_health_collection_entries",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            collection_entries,
            ("private_health_scoped_dependant_none(value)",),
        )
    )
    scoped_none = python_function_text(
        intake,
        "private_health_scoped_dependant_none",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            scoped_none,
            (
                'DEPENDANT_SUMMARY_FIELD_ALIASES["count"]',
                "for key in DEPENDANT_SECTION_KEYS:",
                "if is_none(dependant_value):",
            ),
        )
    )
    merge_records = python_function_text(intake, "private_health_merge_records")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            merge_records,
            (
                "inherited_conflicts: List[Any] = []",
                'if key == "_source_conflicts":',
                "inherited_conflicts.extend(",
                "private_health_recursive_scalar_values(value)",
                "all_conflicts = private_health_unique_values(",
                "[*inherited_conflicts, *conflicts]",
                'merged["_source_conflicts"] = all_conflicts',
            ),
        )
    )
    base_items_text = python_function_text(intake, "base_items")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            base_items_text,
            (
                "has_private_health_structure = any(",
                "key in answers for key in MEDICARE_PRIVATE_HEALTH_BASE_FIELDS",
                "has_private_health_medicare or has_private_health_structure",
            ),
        )
    )
    root_known_keys = python_function_text(intake, "private_health_root_known_keys")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            root_known_keys,
            ('| {"income_year"}',),
        )
    )
    detail_with_metadata = python_function_text(
        intake,
        "private_health_detail_with_metadata",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            detail_with_metadata,
            (
                'if key.startswith("_"):',
                "private_health_invalid_source_values(item)",
                "private_health_invalid_checked_at_values(item)",
                'details["unresolved_source_provenance"]',
                'details["unresolved_checked_at_provenance"]',
                "if not details:\n            return PRIVATE_HEALTH_NO_VALUE, {}",
                "private_health_add_metadata(\n            metadata,\n            local_metadata,",
            ),
        )
    )
    note_detail = python_function_text(
        intake,
        "private_health_note_detail_with_metadata",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            note_detail,
            (
                "private_health_note_detail_with_metadata(item)",
                "false_is_value=isinstance(value, dict)",
            ),
        )
    )
    workflow_section = python_function_text(
        intake,
        "private_health_workflow_section_record",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            workflow_section,
            (
                "private_health_section_records(",
                "private_health_merge_records(records, field_aliases)",
                "if field_aliases is PRIVATE_HEALTH_FIELD_ALIASES:",
                "private_health_capture_cover_lineage(merged, records)",
            ),
        )
    )
    workflow_boundary = python_function_text(
        intake,
        "private_health_normalize_workflow_boundary",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            workflow_boundary,
            (
                "private_health_workflow_section_record(",
                "private_health_dependant_summary_from_values(",
                "private_health_dependant_supplemental_records(",
                'workflow["dependant_summary"]["dependant_supplemental_facts"]',
                "private_health_statement_items(statement_value)",
                "private_health_statement_supplemental_records(",
                'note: Dict[str, Any] = {"private_health_statement": detail}',
            ),
        )
    )
    workflow_income_year = python_function_text(
        intake,
        "private_health_workflow_with_income_year",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            workflow_income_year,
            (
                "raw = private_health_normalize_workflow_boundary(raw)",
                'income_year = text(raw.get("income_year"), DEFAULT_INCOME_YEAR)',
                'workflow["income_year"] = income_year',
                "private_health_value_with_income_year(",
            ),
        )
    )
    value_income_year = python_function_text(
        intake,
        "private_health_value_with_income_year",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            value_income_year,
            (
                "set(PRIVATE_HEALTH_STATEMENT_ITEM_KEYS)",
                "PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS",
                'record["_income_year"] = income_year',
            ),
        )
    )
    if 'setdefault("_income_year"' in value_income_year:
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "direct workflow income year must override stale internal markers",
            )
        )
    epistemic_uncertainty = python_function_text(
        intake,
        "private_health_epistemic_uncertainty_text",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            epistemic_uncertainty,
            (
                "return bool(",
                "cannot|can\\s+t|unable\\s+to",
                "uncertain|unsure|unconfirmed|possibly|probably|maybe|perhaps|likely|unlikely",
                "(?:may|might|could)\\s+(?:not\\s+)?(?:have|be)",
                "not\\s+true\\s+that",
                "\\bif\\b",
            ),
        )
    )
    qualified_period = python_function_text(
        intake,
        "private_health_qualified_period_text",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            qualified_period,
            (
                "if private_health_partial_text(normalized):\n        return True",
                "except|excluding|apart\\s+from|other\\s+than|besides|save\\s+for|unless",
                "fully|always|continuously",
                "throughout\\s+(?:the\\s+)?(?:income\\s+)?year",
                "if private_health_epistemic_uncertainty_text(normalized):\n        return True",
                "currently|at\\s+present|right\\s+now|at\\s+the\\s+moment",
                "zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\\d{1,4}",
                "return amount != limit",
                "\\bbetween\\b.+\\band\\b|\\bfrom\\b.+\\bto\\b",
                "if re.search(r\"\\b(?:from|until|since|before|after)\\b\", normalized):",
                "\\bat\\s+any\\s+time\\b|\\bthroughout",
                "return False",
            ),
        )
    )
    full_income_year_range = python_function_text(
        intake,
        "private_health_full_income_year_range_text",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            full_income_year_range,
            (
                'separator = r"(?:(?:to|and|until|through(?:\\s+to)?)\\s+)?"',
                "(?:(?:from|between)\\s+)?",
                "0?1\\s+0?7",
                "30\\s+0?6",
                "int(match.group(2)) == int(match.group(1)) + 1",
            ),
        )
    )
    categorical_period = "if re.search(\n        r\"\\bat\\s+any\\s+time\\b|\\bthroughout"
    if not contains_in_order(
        qualified_period,
        (
            "private_health_epistemic_uncertainty_text(normalized)",
            "return amount != limit",
            "if re.search(\n        rf\"\\bbetween",
            categorical_period,
        ),
    ):
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "qualified period checks must precede categorical full-year fallback",
            )
        )
    qualified_denial = python_function_text(
        intake,
        "private_health_dependant_qualified_denial_text",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            qualified_denial,
            (
                "if private_health_qualified_period_text(value):\n        return True",
                "more\\s+than|less\\s+than|at\\s+least|at\\s+most",
                'positive = (',
                'zero = rf"(?:0|zero|no|none|nil)',
                "\\bor\\b",
                "\\bunlikely\\b",
            ),
        )
    )
    source_like = python_function_text(intake, "private_health_source_like_text")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            source_like,
            (
                "return bool(",
                "(?:https?|file)://",
                "[a-z]{2,24}",
                'or "/" in stripped',
                "csv|docx?|html?|json|md|pdf|txt|xlsx?|xml|ya?ml",
            ),
        )
    )
    dependant_denial_candidate = python_function_text(
        intake,
        "private_health_dependant_denial_candidate",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            dependant_denial_candidate,
            (
                "return bare",
                "if private_health_source_like_text(value):\n        return False",
                "private_health_dependant_qualified_denial_text(value)",
                'if bare and normalized in {"0", "false", "no", "nil", "zero"}:',
                'subject = r"(?:dependants?|dependents?|child(?:ren)?|students?)"',
                "(?:no|none|nil|zero|0|without)",
                "(?:dependant|dependent)\\s+count",
            ),
        )
    )
    denial_scalars = python_function_text(
        intake,
        "private_health_dependant_denial_scalars",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            denial_scalars,
            (
                "values.extend(private_health_dependant_denial_scalars(item, bare=bare))",
                "bare=bare if key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS else False",
                "private_health_dependant_denial_candidate(value, bare=bare)",
            ),
        )
    )
    dependant_denial = python_function_text(
        intake,
        "private_health_dependant_denial_value",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            dependant_denial,
            (
                "return any(private_health_dependant_denial_value(item) for item in value)",
                "item_shaped = private_health_dependant_record_has_signal(value)",
                "for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS",
                "for key in PRIVATE_HEALTH_DEPENDANT_DENIAL_KEYS",
                "bare=False",
            ),
        )
    )
    remaining_record = python_function_text(
        intake,
        "private_health_dependant_remaining_record",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            remaining_record,
            (
                "kept, supplied = private_health_dependant_remaining_record(",
                "local_metadata = private_health_dependant_metadata(",
                "if key.startswith(\"_\") or key in PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS:\n                continue",
                "bare=bare if key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS else False",
                "if private_health_dependant_denial_candidate(value, bare=bare):",
                "return PRIVATE_HEALTH_NO_VALUE, {}",
                "private_health_sanitized_value(value, false_is_value=True)",
                "(PRIVATE_HEALTH_NO_VALUE, {})",
            ),
        )
    )
    supplemental_detail = python_function_text(
        intake,
        "private_health_dependant_supplemental_detail",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            supplemental_detail,
            (
                "detail, supplied = private_health_dependant_supplemental_detail(",
                "local_metadata = private_health_dependant_metadata(",
                "if key.startswith(\"_\") or key in PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS:\n                continue",
                "private_health_sanitized_value(value, false_is_value=True)",
                "(PRIVATE_HEALTH_NO_VALUE, {})",
            ),
        )
    )
    dependant_item_record = python_function_text(
        intake,
        "private_health_dependant_item_record",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            dependant_item_record,
            (
                "inherited_metadata = private_health_dependant_metadata(value)",
                'if key.startswith("_"):',
                "if key in metadata_aliases:\n            continue",
                "detail, supplied = private_health_dependant_supplemental_detail(",
                'for wrapper in ("value", "answer", "response")',
                "if len(wrapper_keys) == 1 and len(detail) == 1:",
                "private_health_add_metadata(\n            metadata,",
                "private_health_add_metadata(record, metadata, DEPENDANT_FIELD_ALIASES)",
                "return private_health_filter_record_values(record, DEPENDANT_FIELD_ALIASES)",
            ),
        )
    )
    dependant_metadata = python_function_text(
        intake,
        "private_health_dependant_metadata",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            dependant_metadata,
            (
                'set(DEPENDANT_FIELD_ALIASES["source_urls"])',
                'set(DEPENDANT_SUMMARY_FIELD_ALIASES["source_urls"])',
                'set(DEPENDANT_FIELD_ALIASES["checked_at"])',
                'set(DEPENDANT_SUMMARY_FIELD_ALIASES["checked_at"])',
                "private_health_add_metadata(",
            ),
        )
    )
    count_records = python_function_text(
        intake,
        "private_health_dependant_count_records",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            count_records,
            (
                "private_health_dependant_count_records(\n                    item,\n                    metadata,\n                    allow_bare_none=False,",
                'records[0]["count_candidates"] = count_candidates',
                "metadata = private_health_dependant_metadata(value, metadata)",
                "value_keys = [key for key in PRIVATE_HEALTH_DEPENDANT_VALUE_KEYS if key in payload]",
                "context, context_metadata = private_health_dependant_supplemental_detail(",
                "if context is PRIVATE_HEALTH_NO_VALUE:\n                return []",
                'record["count_context"] = context',
                "denial = private_health_dependant_denial_candidate(value, bare=True)",
                "0\n            if denial",
                "private_health_add_metadata(record, metadata or {}, DEPENDANT_SUMMARY_FIELD_ALIASES)",
            ),
        )
    )
    denial_records = python_function_text(
        intake,
        "private_health_dependant_denial_records",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            denial_records,
            (
                "private_health_dependant_denial_records(",
                "local_metadata = private_health_dependant_metadata(value, metadata)",
                "if key.startswith(\"_\") or key in PRIVATE_HEALTH_WORKFLOW_METADATA_KEYS:\n                continue",
                "if not private_health_dependant_denial_candidate(value, bare=bare):",
                'record: Dict[str, Any] = {"count": 0}',
                "if preserve_note and isinstance(value, str):",
                "private_health_add_metadata(record, metadata or {}, DEPENDANT_SUMMARY_FIELD_ALIASES)",
            ),
        )
    )
    summary_entries = python_function_text(
        intake,
        "private_health_dependant_summary_entries",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            summary_entries,
            (
                "private_health_dependant_summary_entries(\n                    item,\n                    inherited_metadata,\n                    allow_bare_none=False,",
                "metadata = private_health_dependant_metadata(value, inherited_metadata)",
                "for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS:",
                "item_shaped = private_health_dependant_record_has_signal(value)",
                "for key in DEPENDANT_SUMMARY_FIELD_ALIASES[\"count\"]:",
                "private_health_dependant_count_records(value[key], metadata)",
                "private_health_dependant_denial_records(",
                "remaining, status_metadata = private_health_dependant_remaining_record(",
                "remaining, note_metadata = private_health_dependant_remaining_record(",
            ),
        )
    )
    if not contains_in_order(
        summary_entries,
        (
            "item_shaped = private_health_dependant_record_has_signal(value)",
            'for key in DEPENDANT_SUMMARY_FIELD_ALIASES["count"]:',
            "if not item_shaped:",
        ),
    ):
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "dependant count aliases must survive item-shaped records",
            )
        )
    summary_base = python_function_text(
        intake,
        "private_health_dependant_summary_base",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            summary_base,
            (
                "record = private_health_filter_record_values(value, DEPENDANT_SUMMARY_FIELD_ALIASES)",
                '*DEPENDANT_SUMMARY_FIELD_ALIASES["count"],',
                '*DEPENDANT_SUMMARY_FIELD_ALIASES["notes"],',
                "*PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS,",
                "record.pop(key, None)",
                "detail, supplied = private_health_dependant_supplemental_detail(item)",
                "if detail is PRIVATE_HEALTH_NO_VALUE:\n            record.pop(key)",
                "private_health_add_metadata(\n        record,\n        metadata,",
            ),
        )
    )
    dependant_summary = python_function_text(
        intake,
        "private_health_normalize_dependant_summary",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            dependant_summary,
            (
                "private_health_dependant_summary_base(value)",
                "*private_health_dependant_summary_entries(value)",
                "return private_health_merge_records(records, DEPENDANT_SUMMARY_FIELD_ALIASES)",
            ),
        )
    )
    summary_from_values = python_function_text(
        intake,
        "private_health_dependant_summary_from_values",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            summary_from_values,
            (
                "private_health_normalize_dependant_summary(summary)",
                "*private_health_dependant_summary_entries(dependants)",
                "private_health_merge_records(records, DEPENDANT_SUMMARY_FIELD_ALIASES)",
            ),
        )
    )
    summary_records = python_function_text(
        intake,
        "private_health_dependant_summary_records",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            summary_records,
            (
                'private_health_flat_alias_subset(record, "dependant_summary")',
                "for key in DEPENDANT_SECTION_KEYS:",
                'if key in {"dependant_summary", "dependent_summary"}:',
                "summary_base = private_health_dependant_summary_base(value)",
                "rows.extend(private_health_dependant_summary_entries(value))",
            ),
        )
    )
    item_container = python_function_text(
        intake,
        "private_health_dependant_item_container",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            item_container,
            (
                "if any(key in value for key in PRIVATE_HEALTH_DEPENDANT_ITEM_KEYS):",
                "if private_health_dependant_record_has_signal(value):",
            ),
        )
    )
    dependant_answers = python_function_text(
        intake,
        "private_health_dependant_answers",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            dependant_answers,
            (
                "for row in private_health_dependant_entries(value)",
                "if private_health_dependant_record_has_signal(row)",
            ),
        )
    )
    dependant_entries = python_function_text(
        intake,
        "private_health_dependant_entries",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            dependant_entries,
            (
                "rows.extend(private_health_dependant_entries(value.get(key)))",
                "parent = private_health_dependant_item_record(parent_value)",
                "rows.insert(0, parent)",
                "rows.append(parent)",
                "if private_health_dependant_denial_value(parent):\n            return []",
            ),
        )
    )
    if not contains_in_order(
        dependant_entries,
        (
            "rows.insert(0, parent)",
            "rows.append(parent)",
            "if private_health_dependant_denial_value(parent):",
        ),
    ):
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "dependant item facts must be preserved before denial-only filtering",
            )
        )
    supplemental_records = python_function_text(
        intake,
        "private_health_dependant_supplemental_records",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            supplemental_records,
            (
                'if key in DEPENDANT_SUMMARY_FIELD_ALIASES["count"] or key in {',
                '"dependant_supplemental_facts",',
                '"status",',
                "sanitized, supplied = private_health_dependant_remaining_record(",
                "sanitized, supplied = private_health_dependant_supplemental_detail(",
                "details_metadata",
                "if details:\n            records.append((details, details_metadata))",
                "private_health_record_metadata(\n                parent,\n                source_aliases,\n                checked_at_aliases,",
                "if private_health_summary_substantive(summary):\n            represented.update(summary)",
                "if wrapper_keys:\n            represented.update(parent)",
                "or private_health_dependant_summary_entries(value)",
            ),
        )
    )
    count_records_none = python_function_text(
        intake,
        "private_health_dependant_count_records",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            count_records_none,
            (
                "allow_bare_none: bool = True",
                "allow_bare_none=False",
                'strip() == "none"',
            ),
        )
    )
    medicare_answers = python_function_text(
        intake,
        "private_health_medicare_answers",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            medicare_answers,
            (
                "if key not in PRIVATE_HEALTH_WORKFLOW_NOTE_KEYS",
                "private_health_workflow_note_metadata(root)",
                "private_health_unknown_metadata(root, root_known_keys)",
                'result["private_health"],\n        record_groups["private_health"],',
                "private_health_add_metadata(\n        result[\"private_health\"],\n        supplemental_metadata,",
            ),
        )
    )
    summary_helper_by_boundary = {
        "private_health_medicare_required_answer": "private_health_dependant_summary_from_values(",
        "has_private_health_medicare_inputs": "private_health_dependant_summary_from_values(",
        "private_health_mls_has_context": "private_health_dependant_summary_from_values(",
        "dependant_rows": "private_health_dependant_summary_from_values(",
        "private_health_medicare_evidence_rows": "private_health_dependant_summary_from_values(",
        "private_health_medicare_answers": "private_health_normalize_dependant_summary(",
        "private_health_dependant_summary_has_inputs": "private_health_normalize_dependant_summary(",
        "dependant_summary_gaps": "private_health_normalize_dependant_summary(",
    }
    for function_name, helper in summary_helper_by_boundary.items():
        function_text = python_function_text(intake, function_name)
        if helper not in function_text:
            findings.append(
                Finding(
                    PRIVATE_HEALTH_MEDICARE_CONTRACT,
                    f"dependant denial normalization missing from {function_name}",
                )
            )

    partial_text = python_function_text(intake, "private_health_partial_text")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            partial_text,
            (
                're.sub(r"[^a-z0-9]+", " ", value.lower()).strip()',
                "part\\s+(?:of\\s+(?:the\\s+)?)?(?:income\\s+)?year",
                "some(?:\\s+but\\s+not\\s+all)?\\s+of",
                "return any(re.search(pattern, normalized) for pattern in patterns)",
            ),
        )
    )
    partial_cover = python_function_text(intake, "private_health_partial_cover_text")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            partial_cover,
            (
                "if private_health_negated_partial_cover_text(normalized):\n        return False",
                "if private_health_epistemic_uncertainty_text(normalized):\n        return False",
                "duration_status = private_health_cover_duration_status(normalized)",
                'if duration_status is not None:\n        return duration_status == "partial"',
                "if private_health_qualified_period_text(normalized):\n        return True",
                "if private_health_continuous_cover_text(normalized):\n        return False",
                "mixed\\s+(?:hospital\\s+|health\\s+)?cover",
                "intermittent(?:ly)?",
                "(?:started|ended|lapsed|expired)",
                "(?:gaps?|breaks?|interruptions?|lapses?)",
                "all(?:\\s+of)?\\s+(?:the\\s+)?(?:income\\s+)?year",
                "except|excluding|apart\\s+from|but",
                "\\ball\\s+but\\b",
                "(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven)\\s+months?",
                "if any(re.search(pattern, normalized) for pattern in patterns):\n        return True",
                "return months is not None and 0 < int(months.group(1)) < 12",
            ),
        )
    )
    if not contains_in_order(
        partial_cover,
        (
            "private_health_negated_partial_cover_text(normalized)",
            "private_health_epistemic_uncertainty_text(normalized)",
            "private_health_cover_duration_status(normalized)",
            "private_health_continuous_cover_text(normalized)",
            "private_health_qualified_period_text(normalized)",
            "patterns = (",
        ),
    ):
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "partial cover exclusions and duration classification must precede broad phrase matching",
            )
        )
    cover_bool = python_function_text(intake, "private_health_cover_bool")
    partial_cover_block = "if private_health_partial_cover_text(normalized):\n        return True"
    categorical_no_cover = (
        'if re.search(rf"\\b{negative}\\b(?:\\s+\\w+){{0,5}}\\s+\\b{cover}\\b", normalized):'
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            cover_bool,
            (
                "if private_health_epistemic_uncertainty_text(normalized):\n        return None",
                "if private_health_negated_partial_cover_text(normalized):\n        return None",
                "duration_status = private_health_cover_duration_status(normalized)",
                'if duration_status == "invalid":\n        return None',
                'if duration_status == "partial":\n        return True',
                "if private_health_continuous_cover_text(normalized):\n        return True",
                partial_cover_block,
                categorical_no_cover,
                "if private_health_full_income_year_range_text(normalized):\n        return True",
                'if duration_status == "full":\n        return True',
                "return None",
            ),
        )
    )
    if not contains_in_order(
        cover_bool,
        (
            "private_health_epistemic_uncertainty_text(normalized)",
            "private_health_negated_partial_cover_text(normalized)",
            'duration_status == "partial"',
            "private_health_continuous_cover_text(normalized)",
            partial_cover_block,
            categorical_no_cover,
            "private_health_full_income_year_range_text(normalized)",
            'duration_status == "full"',
        ),
    ):
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "partial cover classification must precede categorical no-cover classification",
            )
        )
    spouse_bool = python_function_text(intake, "private_health_spouse_bool")
    negated_spouse_absence = python_function_text(
        intake,
        "private_health_negated_spouse_absence_text",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            negated_spouse_absence,
            (
                "negated_absence = (",
                "without",
                "lack(?:ed|ing)?",
                "(?:go|went)",
            ),
        )
    )
    spouse_partial_block = 'if re.search(r"\\b(spouse|partner)\\b", normalized) and ('
    spouse_negative = (
        'if re.search(rf"\\b{negative}\\b(?:\\s+\\w+){{0,5}}\\s+\\b(spouse|partner)\\b", normalized):'
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            spouse_bool,
            (
                "if private_health_negated_spouse_absence_text(normalized):\n        return True",
                spouse_partial_block,
                "private_health_epistemic_uncertainty_text(normalized)",
                "private_health_qualified_period_text(normalized)",
                're.search(r"\\b(no longer|separated)\\b", normalized)',
                spouse_negative,
                "if private_health_full_income_year_range_text(normalized):\n        return True",
                "throughout\\s+(?:the\\s+)?(?:income\\s+)?year",
            ),
        )
    )
    if not contains_in_order(
        spouse_bool,
        (
            "private_health_negated_spouse_absence_text(normalized)",
            spouse_partial_block,
            "private_health_epistemic_uncertainty_text(normalized)",
            "private_health_qualified_period_text(normalized)",
            spouse_negative,
            "private_health_full_income_year_range_text(normalized)",
        ),
    ):
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "partial spouse classification must precede categorical no-spouse classification",
            )
        )
    overview_gaps = python_function_text(intake, "private_health_overview_gaps")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            overview_gaps,
            (
                "private_health_partial_cover_text(covered_raw)",
                "private_health_false_cover_period_gaps(",
                "PRIVATE_HEALTH_FIELD_ALIASES,",
                "no-cover answer conflicts with a supplied private hospital cover period",
            ),
        )
    )
    mls_gaps = python_function_text(intake, "mls_review_gaps")
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            mls_gaps,
            (
                "private_health_false_cover_period_gaps(",
                "MLS_FIELD_ALIASES,",
                "no-cover answer conflicts with a supplied hospital cover period",
            ),
        )
    )
    if mls_gaps.count("private_health_partial_cover_text(cover_raw)") < 2:
        findings.append(
            Finding(
                PRIVATE_HEALTH_MEDICARE_CONTRACT,
                "MLS review must use partial cover classification for gaps and evidence",
            )
        )
    effective_mls = python_function_text(
        intake,
        "private_health_effective_mls_record",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            effective_mls,
            (
                "private_health_false_only_placeholder(local.get(alias))",
                "private_health_mls_inherited_cover_has_inputs(private_health)",
                'if "_cover_source_urls" in private_health',
                'if "_cover_checked_at" in private_health',
                'if "_cover_source_conflicts" in private_health',
                "inherited.pop(inherited_key, None)",
                "private_health_provenance_urls(local)",
                "*inherited_conflicts,\n            *local_conflicts,",
            ),
        )
    )
    capture_lineage = python_function_text(
        intake,
        "private_health_capture_cover_lineage",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            capture_lineage,
            (
                "eligible_supplied = [",
                'if "_cover_source_urls" in supplied',
                'if "_cover_checked_at" in supplied',
                'supplied.get("_cover_source_conflicts")',
                "private_health_mls_inherited_conflicts(supplied)",
                'record["_cover_source_urls"]',
                'record["_cover_checked_at"]',
                'record["_cover_source_conflicts"]',
            ),
        )
    )
    inherited_mls_conflicts = python_function_text(
        intake,
        "private_health_mls_inherited_conflicts",
    )
    findings.extend(
        fail_if_missing(
            PRIVATE_HEALTH_MEDICARE_CONTRACT,
            inherited_mls_conflicts,
            ('if field not in {"source_urls", "checked_at"}',),
        )
    )
    for rel in (
        "scripts/skillgen.py",
        "skills/private-health-medicare/references/rules.md",
        "skills/individual-return/SKILL.md",
        "skills/individual-return/references/rules.md",
        "docs/INDIVIDUAL_RETURN_PREP.md",
    ):
        text = read_optional(root, rel)
        for phrase, label in (
            (PRIVATE_HEALTH_MEDICARE_NOOP_DOC_PHRASE, "recursive no-op"),
            (PRIVATE_HEALTH_MEDICARE_PROVENANCE_DOC_PHRASE, "supplemental provenance"),
            (PRIVATE_HEALTH_MEDICARE_DEPENDANT_DENIAL_DOC_PHRASE, "dependant denial"),
            (PRIVATE_HEALTH_MEDICARE_PARTIAL_COVER_DOC_PHRASE, "partial cover"),
        ):
            if phrase not in text:
                findings.append(
                    Finding(
                        PRIVATE_HEALTH_MEDICARE_CONTRACT,
                        f"{label} contract missing from {rel}",
                    )
                )
    for name in PRIVATE_HEALTH_MEDICARE_RUNTIME_FUNCTIONS:
        if f"def {name}(" in intake and intake.count(f"{name}(") < 2:
            findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, f"runtime function not wired: {name}"))
    for symbol in PRIVATE_HEALTH_MEDICARE_ISOLATION_SYMBOLS:
        if symbol in intake and intake.count(symbol) < 2:
            findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, f"isolation symbol not wired: {symbol}"))
    for name, return_type in PRIVATE_HEALTH_MEDICARE_TYPED_HELPERS:
        if f"def {name}(" not in intake:
            continue
        signature = re.search(
            rf"^def {re.escape(name)}\(.*?\)\s*->\s*{re.escape(return_type)}:",
            intake,
            re.DOTALL | re.MULTILINE,
        )
        if signature is None:
            findings.append(
                Finding(
                    PRIVATE_HEALTH_MEDICARE_CONTRACT,
                    f"typed helper must return {return_type}: {name}",
                )
            )
        if intake.count(f"{name}(") < 2:
            findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, f"typed helper not wired: {name}"))
    mls_sources = re.search(r"ATO_MLS_SOURCES\s*=\s*\[(.*?)\]", intake, re.DOTALL)
    if mls_sources is None or "ATO_MLS_PAYING_SOURCE" not in mls_sources.group(1):
        findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, "MLS paying source missing from ATO_MLS_SOURCES"))

    try:
        manifest = json.loads(read(root, "config/runtime-coverage.json"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, f"runtime coverage unreadable: {exc}"))
        return findings
    concepts = manifest.get("concepts")
    if not isinstance(concepts, list):
        findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, "runtime coverage concepts must be a list"))
        return findings
    concept = next(
        (
            item
            for item in concepts
            if isinstance(item, dict) and item.get("id") == "private-health-medicare-spouse-dependants"
        ),
        None,
    )
    if concept is None:
        findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, "missing runtime coverage concept"))
        return findings
    try:
        source_coverage = json.loads(read(root, "data/ato_knowledge_base/source_coverage.json"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, f"source coverage unreadable: {exc}"))
        return findings
    sources = source_coverage.get("sources")
    if not isinstance(sources, list):
        findings.append(Finding(PRIVATE_HEALTH_MEDICARE_CONTRACT, "source coverage sources must be a list"))
        return findings
    sources_by_id = {
        str(source.get("source_id", "")): source
        for source in sources
        if isinstance(source, dict) and source.get("status") == "verified"
    }
    for constant_name, source_id in PRIVATE_HEALTH_MEDICARE_SOURCE_BINDINGS:
        match = re.search(rf'^{re.escape(constant_name)}\s*=\s*"([^"]+)"', intake, re.MULTILINE)
        if match is None:
            continue
        source = sources_by_id.get(source_id)
        if source is None:
            findings.append(
                Finding(
                    PRIVATE_HEALTH_MEDICARE_CONTRACT,
                    f"verified source binding missing: {constant_name} -> {source_id}",
                )
            )
            continue
        source_urls = {str(source.get("canonical_url", "")), str(source.get("original_url", ""))}
        if match.group(1) not in source_urls:
            findings.append(
                Finding(
                    PRIVATE_HEALTH_MEDICARE_CONTRACT,
                    f"runtime source binding mismatch: {constant_name} -> {source_id}",
                )
            )
    expected_fields = {
        "runtime_status": "structured",
        "source_skills": ["private-health-medicare"],
        "source_ids": list(PRIVATE_HEALTH_MEDICARE_SOURCE_IDS),
        "runtime_functions": list(PRIVATE_HEALTH_MEDICARE_RUNTIME_FUNCTIONS),
        "tests": list(PRIVATE_HEALTH_MEDICARE_TESTS),
        "docs": list(PRIVATE_HEALTH_MEDICARE_DOCS),
        "issue": "#71",
    }
    for field, expected in expected_fields.items():
        if concept.get(field) != expected:
            findings.append(
                Finding(
                    PRIVATE_HEALTH_MEDICARE_CONTRACT,
                    f"runtime coverage {field} must be {expected!r}",
                )
            )
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
    plugin = json.loads(read(root, ".codex-plugin/plugin.json"))
    tests = read(root, "tests/test_python_guardrails.py")
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
    root_package = config.get("packages", {}).get(".")
    extra_files = root_package.get("extra-files") if isinstance(root_package, dict) else None
    seen = {
        (item.get("path"), item.get("jsonpath"))
        for item in extra_files or []
        if isinstance(item, dict) and item.get("type") == "json"
    }
    required_extra_files = {
        (".codex-plugin/plugin.json", "$.version"),
        (".claude-plugin/plugin.json", "$.version"),
        ("skill.json", "$.version"),
        ("plugin.lock.json", "$.pluginVersion"),
    }
    missing_extra_files = sorted(f"{path}:{jsonpath}" for path, jsonpath in required_extra_files - seen)
    if missing_extra_files:
        findings.append(
            Finding(
                RELEASE_GUARDRAIL_CONTRACT,
                "release-please-config.json missing version bump files: " + ", ".join(missing_extra_files),
            )
        )
    version = plugin.get("version")
    if isinstance(version, str) and version and version in tests:
        findings.append(Finding(RELEASE_GUARDRAIL_CONTRACT, "tests must derive plugin version from manifests, not hard-code current version"))
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
    if "./scripts/install-local-skills.sh --agent codex" not in setup:
        findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, "setup must attempt repo-local workflow skill install for Codex"))
    if "warning: local workflow skill install skipped" not in setup:
        findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, "setup must keep local workflow skill install non-blocking"))
    return findings


def check_local_plugin_marketplace_contract(root: Path) -> List[Finding]:
    marketplace_path = root.joinpath(".agents", "plugins", "marketplace.json")
    docs = read(root, "docs/DEVELOPMENT.md")
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


def check_plugin_mcp_contract(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    if root.joinpath(".codex-plugin/mcp.json").exists():
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "stale .codex-plugin/mcp.json must not be packaged; use root .mcp.json"))
    ci = read_optional(root, ".github/workflows/ci.yml")
    if "test -f .codex-plugin/mcp.json" in ci or "test ! -f .mcp.json" in ci or "mcp_servers" in ci:
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "CI plugin package check must require root .mcp.json and reject stale .codex-plugin/mcp.json"))

    try:
        codex_plugin = json.loads(read(root, ".codex-plugin/plugin.json"))
    except json.JSONDecodeError as exc:
        return [Finding(PLUGIN_MCP_CONTRACT, f"invalid .codex-plugin/plugin.json: {exc}")]
    if codex_plugin.get("mcpServers") != "./.mcp.json":
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "Codex plugin must point at root .mcp.json"))

    try:
        codex_mcp = json.loads(read(root, ".mcp.json"))
    except json.JSONDecodeError as exc:
        return [Finding(PLUGIN_MCP_CONTRACT, f"invalid .mcp.json: {exc}")]
    codex_servers = codex_mcp.get("mcpServers")
    codex_server = codex_servers.get("taxmateAustralia") if isinstance(codex_servers, dict) else None
    if not isinstance(codex_server, dict):
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "Codex MCP manifest missing taxmateAustralia server"))
    elif codex_server.get("cwd") != "." or codex_server.get("args") != ["./mcp/server.cjs", "--stdio"]:
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "Codex MCP manifest must stay plugin-root relative"))

    try:
        claude_plugin = json.loads(read(root, ".claude-plugin/plugin.json"))
    except json.JSONDecodeError as exc:
        return [Finding(PLUGIN_MCP_CONTRACT, f"invalid .claude-plugin/plugin.json: {exc}")]
    claude_server = claude_plugin.get("mcpServers", {}).get("taxmateAustralia")
    claude_env = claude_server.get("env") if isinstance(claude_server, dict) else None
    if not isinstance(claude_server, dict):
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "Claude plugin missing taxmateAustralia MCP server"))
    elif claude_server.get("args") != ["${CLAUDE_PLUGIN_ROOT}/mcp/server.cjs", "--stdio"]:
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "Claude MCP server must use CLAUDE_PLUGIN_ROOT path"))
    elif not isinstance(claude_env, dict) or claude_env.get("TAXMATE_AUSTRALIA_ROOT") != "${CLAUDE_PLUGIN_ROOT}":
        findings.append(Finding(PLUGIN_MCP_CONTRACT, "Claude MCP server must set TAXMATE_AUSTRALIA_ROOT from CLAUDE_PLUGIN_ROOT"))
    server = read(root, "mcp/server.cjs")
    launcher = read(root, "scripts/taxmate.py")
    findings.extend(
        fail_if_missing(
            PLUGIN_MCP_CONTRACT,
            server + "\n" + launcher,
            PLUGIN_MCP_REQUIRED_FRAGMENTS,
        )
    )
    return findings


def workflow_has_required_ci_triggers(text: str) -> bool:
    return (
        "workflow_dispatch:" in text
        and any(re.match(r"^\s*pull_request:\s*$", line) for line in text.splitlines())
        and any(re.match(r"^\s*push:\s*$", line) for line in text.splitlines())
        and "branches: [main]" in text
    )


def check_local_ci_contract(root: Path) -> List[Finding]:
    ci = read(root, ".github/workflows/ci.yml")
    scanner = read(root, ".github/workflows/hol-plugin-scanner.yml")
    local_ci = read(root, ".github/workflows/local-ci.yml")
    actrc = read(root, ".actrc")
    run_script = read(root, "scripts/run-local-ci-act.sh")
    check_script = read(root, "scripts/check-local-ci-ready.sh")
    precommit = read(root, ".pre-commit-config.yaml")
    publication = read(root, "scripts/check-publication-ready.sh")
    development = read(root, "docs/DEVELOPMENT.md")
    findings: List[Finding] = []
    if not workflow_has_required_ci_triggers(ci):
        findings.append(Finding(LOCAL_CI_CONTRACT, "GitHub CI must keep automatic pull_request and main push triggers"))
    findings.extend(
        fail_if_missing(
            LOCAL_CI_CONTRACT,
            "\n".join([ci, scanner, local_ci, actrc, run_script, check_script, precommit, publication, development]),
            [
                "workflow_dispatch:",
                "catthehacker/ubuntu:act-22.04",
                "act workflow_dispatch -W .github/workflows/local-ci.yml",
                "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
                "rm -rf .git",
                "git commit -m act-baseline",
                "docker info",
                "gitleaks dir . --redact --no-banner",
                "gitleaks detect --source . --redact --no-banner",
                "bash scripts/check-publication-ready.sh",
                "./scripts/taxmate review-guardrails",
                "./scripts/taxmate validate",
                "bash scripts/test-mcp-server.sh",
                "bash scripts/check-local-ci-ready.sh",
                "taxmate-local-ci-ready",
                "Automatic CI triggers stay in workflow YAML",
                "disabled_manually",
            ],
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
                "When independent review exposes an invariant, encode that invariant broadly in validation checks and tests before fixing the narrow line.",
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
    stale_handoff_terms = [
        term
        for term in (
            "AI extraction confirmation table",
            "individual return field guide",
            "side tabs",
            "side-tabs",
        )
        if term in docs or term in packaged_output_surfaces
    ]
    if stale_handoff_terms:
        findings.append(
            Finding(
                OUTPUT_DOCS_CONTRACT,
                "stale handoff wording: " + ", ".join(stale_handoff_terms),
            )
        )
    findings.extend(
        fail_if_missing(
            OUTPUT_DOCS_CONTRACT,
            readme,
            [
                "Plugin install",
                "Node.js 20+ for the MCP launcher",
                "`npx skills` guidance only",
                "The plugin runtime produces a print-first HTML handoff",
                "custom preparation aid, not an ATO form, not lodgment software, not final tax advice, and not fileable",
                "Each worksheet card shows the supplied facts as labelled bullets",
                "exact verified myTax/paper destination or explicit non-entry/review wording",
                "The runtime-owned handoff taxonomy is",
                "Output layers render this contract and do not infer destinations",
                "intake summary and AI extraction confirmation",
                "individual return action cards with labelled fact bullets",
                "ABN prep section and BAS worksheet",
                "missing facts queue, evidence queue, and accountant-review queue",
                "row-associated supporting provenance and verified destination-mapping sources",
                "The sample data is synthetic",
                "Screenshot maintenance is a contributor task documented in [docs/DEVELOPMENT.md]",
            ],
        )
    )
    public_docs = {rel: read(root, rel) for rel in PUBLIC_OUTPUT_DOCS}
    for label, surface_text in public_docs.items():
        developer_hits = developer_only_public_doc_hits(surface_text)
        if developer_hits:
            findings.append(
                Finding(
                    OUTPUT_DOCS_CONTRACT,
                    f"{label} contains developer-only maintenance detail: " + ", ".join(developer_hits),
                )
            )
    required_output_surfaces = [
        (
            "docs/INSTALLATION.md",
            install,
            [
                "Plugin Install",
                "codex plugin marketplace add nijanthan-dev/taxmate-australia",
                "claude plugin marketplace add nijanthan-dev/taxmate-australia",
                "claude plugin install taxmate-australia@taxmate-australia",
                "Node.js 20+ for the MCP launcher",
                "Use `npx skills` only when you want guidance in chat",
                "does not include the renderer",
                "Use `--agent claude-code` instead of `--agent codex`",
                "Claude Code users who need generated files should use the plugin install",
                "Cowork currently uses guidance-only public skills",
                "HTML guide",
                "custom preparation aid",
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
                "Plugin Runtime Setup",
                "The plugin install is the runtime install",
                "codex plugin marketplace add nijanthan-dev/taxmate-australia",
                "claude plugin marketplace add nijanthan-dev/taxmate-australia",
                "claude plugin install taxmate-australia@taxmate-australia",
                "Node.js 20+ for the MCP launcher",
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
                "action-card context index",
                "labelled fact bullets",
                "verified myTax/paper destinations or explicit non-entry/review wording",
                "row-associated provenance",
            ],
        ),
        (
            "docs/INDIVIDUAL_RETURN_PREP.md",
            prep,
            [
                "prep-only",
                "manual-copy handoff",
                "does not lodge",
                "Plugin Runtime Path",
                "Node.js 20+ for the MCP launcher",
                "Open the HTML",
                "Every worksheet row and queue item uses the same runtime-owned handoff contract",
                "labelled supplied facts",
                "verified destination or explicit non-entry/review wording",
                "Output layers render that contract and do not infer destinations",
                "The seven handoff actions are",
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
                "Screenshot refresh commands are developer-only",
                "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json",
                "./scripts/taxmate intake individual --answers /tmp/taxmate-answers.json --output /tmp/taxmate-guide.html",
                "/Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome",
                "--screenshot=assets/readme/taxmate-guide-john-doe.png",
                "--screenshot=/tmp/taxmate-guide-full.png",
                "python3 scripts/png_crop.py /tmp/taxmate-guide-full.png",
                "Any PR that changes user-facing output",
                "must update README/docs in the same PR, or state why no docs update is needed",
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
        "full runtime checkout",
        "full checkout",
        "TaxMate checkout available",
        "Rendering the HTML file needs a full runtime checkout",
        "npx skills installs the renderer",
        "npx skills installs the runtime",
        "npx skills provides runtime HTML output",
        "npx skills can render the HTML guide",
        "install Node.js only if you want optional",
        "turn Australian tax records into",
        "turn those records into",
        "move from tax records",
        "tax records into",
        "messy tax records",
        "accountant-ready prep outputs",
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
    check_handoff_contract,
    check_taxpack_output_layer,
    check_individual_intake_contract,
    check_private_health_medicare_contract,
    check_fetch_boundary,
    check_generated_artifact_contract,
    check_finance_and_calc_wire_contract,
    check_public_claim_surfaces,
    check_release_contract,
    check_environment_contract,
    check_local_plugin_marketplace_contract,
    check_plugin_mcp_contract,
    check_local_ci_contract,
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
