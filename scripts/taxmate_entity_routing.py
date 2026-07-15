"""Shared prep-only entity-return intake routing."""

from __future__ import annotations

import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

CHECKED_AT = "2026-07-13"
SOURCES = {
    "company": "https://www.ato.gov.au/forms-and-instructions/company-tax-return-2026-instructions",
    "trust": "https://www.ato.gov.au/forms-and-instructions/trust-tax-return-2026-instructions",
    "partnership": "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions",
}
ALIASES = {
    "company": ("company_return", "company_intake", "company_entity"),
    "trust": ("trust_return", "trust_intake", "trust_entity"),
    "partnership": ("partnership_return", "partnership_intake", "partnership_entity"),
}
FIELDS = {
    "company": (
        "name", "abn", "acn", "tfn", "income_year", "residency",
        "business_activity", "directors", "shareholders", "related_entities",
    ),
    "trust": (
        "name", "tfn", "abn", "trustee", "trust_type", "income_year",
        "residency", "deed_evidence", "election_evidence", "beneficiaries",
    ),
    "partnership": (
        "name", "abn", "tfn", "income_year", "partners", "share_percentages",
        "business_activity", "accounting_basis", "agreement_evidence",
    ),
}
REQUIRED = {
    "company": (
        "name", "income_year", "residency", "business_activity", "directors", "shareholders",
    ),
    "trust": (
        "name", "trustee", "trust_type", "income_year", "residency",
        "deed_evidence", "beneficiaries",
    ),
    "partnership": (
        "name", "income_year", "partners", "share_percentages",
        "business_activity", "accounting_basis", "agreement_evidence",
    ),
}
LABELS = {"company": "Company", "trust": "Trust", "partnership": "Partnership"}
ROUTING_METADATA = {
    "entity_type", "type", "source_url", "source_urls", "checked_at",
    "status", "review_status",
}
REQUEST_MARKER = "__entity_return_requested__"
LEGACY_SHARE_FIELDS = {
    "trust": (
        "trust", "trust_share_entity_name", "trust_beneficiary_entity_name",
        "trust_share_abn", "trust_beneficiary_abn", "trust_share_tfn",
        "trust_beneficiary_tfn", "trust_share_statement", "trust_share_statement_status",
        "trust_beneficiary_statement", "trust_beneficiary_statement_status",
        "trust_share_income", "trust_beneficiary_income", "trust_share_loss",
        "trust_beneficiary_loss", "trust_share_tax_withheld", "trust_beneficiary_tax_withheld",
        "trust_share_credits", "trust_beneficiary_credits", "trust_entity_return_context",
        "trust_beneficiary_entity_return_context",
    ),
    "partnership": (
        "partnership", "partnership_entity_name", "partnership_statement",
        "partnership_statement_status", "partnership_income", "partnership_share_income",
        "partnership_loss", "partnership_share_loss", "partnership_tax_withheld",
        "partnership_credits", "partnership_entity_return_context",
    ),
}
CHILD_COLLECTIONS = {
    "trust": (
        "beneficiary_statements",
        "beneficiary_distribution_statements",
        "beneficiary_statement_items",
    ),
    "partnership": (
        "partner_statements",
        "partner_distribution_statements",
        "partner_statement_items",
    ),
}
CHILD_FIELDS = {
    "trust": {
        "name": ("name", "beneficiary_name"),
        "tfn": ("tfn", "beneficiary_tfn"),
        "abn": ("abn", "beneficiary_abn"),
        "entity_type": ("entity_type", "beneficiary_entity_type", "beneficiary_type"),
        "residency": ("residency", "residency_status", "beneficiary_residency", "beneficiary_residency_status"),
        "beneficiary_status": ("beneficiary_status",),
        "present_entitlement": ("present_entitlement",),
        "statement_status": ("statement_status", "statement_received"),
        "income_components": ("income_components",),
        "credits": ("credits",),
        "tax_withheld": ("tax_withheld", "withholding"),
        "notes": ("notes",),
        "issues": ("issues",),
        "status": ("status",),
        "review_status": ("review_status",),
        "accountant_review": ("accountant_review",),
        "checked_at": ("checked_at",),
    },
    "partnership": {
        "name": ("name", "partner_name"),
        "tfn": ("tfn", "partner_tfn"),
        "abn": ("abn", "partner_abn"),
        "entity_type": ("entity_type", "partner_entity_type", "partner_type"),
        "residency": ("residency", "residency_status", "partner_residency", "partner_residency_status"),
        "share_percentage": ("share_percentage", "ownership_percentage"),
        "statement_status": ("statement_status", "statement_received"),
        "income_share": ("income_share",),
        "loss_share": ("loss_share",),
        "credits": ("credits",),
        "tax_withheld": ("tax_withheld", "withholding"),
        "drawings": ("drawings",),
        "distributions": ("distributions",),
        "notes": ("notes",),
        "issues": ("issues",),
        "status": ("status",),
        "review_status": ("review_status",),
        "accountant_review": ("accountant_review",),
        "checked_at": ("checked_at",),
    },
}
CHILD_EVIDENCE_ALIASES = ("evidence", "evidence_files", "statement_files", "documents")
CHILD_PARENT_ALIASES = {
    "trust": {"name": ("trust_name",), "abn": ("trust_abn",)},
    "partnership": {"name": ("partnership_name",), "abn": ("partnership_abn",)},
}
CHILD_REQUIRED = {
    "trust": (
        "residency", "beneficiary_status", "present_entitlement", "statement_status",
        "income_components", "credits", "tax_withheld", "evidence",
    ),
    "partnership": (
        "residency", "share_percentage", "statement_status", "income_share", "loss_share",
        "credits", "tax_withheld", "drawings", "distributions", "evidence",
    ),
}
CHILD_AMOUNT_FIELDS = {
    "trust": ("income_components", "credits", "tax_withheld"),
    "partnership": (
        "income_share", "loss_share", "credits", "tax_withheld", "drawings", "distributions",
    ),
}
CHILD_ROW_PREFIX = {"trust": "TRUST-BEN", "partnership": "PARTNER-DIST"}
CHILD_LABEL = {"trust": "Trust beneficiary", "partnership": "Partnership partner"}
CHILD_ROW_KIND = {
    "trust": "entity-return-trust-beneficiary-statement",
    "partnership": "entity-return-partnership-partner-statement",
}
CHILD_REVIEW_FIELDS = {
    "trust": ("present_entitlement", "beneficiary_status", "status", "review_status", "accountant_review"),
    "partnership": ("share_percentage", "income_share", "loss_share", "status", "review_status", "accountant_review"),
}
COMPONENT_METADATA_FIELDS = {"code", "description", "label", "name", "type"}


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        values = value.values() if isinstance(value, dict) else value
        return not any(not _missing(item) for item in values)
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return not normalized or normalized in {
        "unknown", "unclear", "missing", "n/a", "not applicable",
    }


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return not value or all(_blank(item) for item in value.values())
    if isinstance(value, list):
        return not value or all(_blank(item) for item in value)
    return False


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def valid_checked_at(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def source_provenance(record: Dict[str, Any]) -> Tuple[List[str], List[Any]]:
    supplied: List[Any] = []
    for source_key in ("source_urls", "source_url"):
        source_value = record.get(source_key)
        if _missing(source_value):
            continue
        supplied.extend(source_value if isinstance(source_value, list) else [source_value])
    valid = [
        value.strip()
        for value in supplied
        if isinstance(value, str) and re.fullmatch(r"https?://[^\s]+", value.strip())
    ]
    invalid = [
        value
        for value in supplied
        if not isinstance(value, str) or not re.fullmatch(r"https?://[^\s]+", value.strip())
    ]
    return valid, invalid


def _decline(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
        return True
    return isinstance(value, str) and value.strip().lower() in {
        "no", "false", "none", "not applicable", "0", "off", "unchecked",
    }


def _entity_marker(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in {"yes", "true", "on", "checked"}


def _entity_input(value: Any) -> bool:
    return not _decline(value) and not _missing(value)


def _first_meaningful(record: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if not _missing(value):
            return value
    return None


def _values(value: Any) -> List[Any]:
    return value if isinstance(value, list) else [value]


def _dedupe(values: List[Any]) -> List[Any]:
    unique: List[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
        if marker not in seen:
            seen.add(marker)
            unique.append(value)
    return unique


def _child_collection_value(left: Any, right: Any) -> List[Any]:
    values = [*_values(left), *_values(right)]
    populated = [value for value in values if not _blank(value)]
    return _dedupe(populated or values[:1])


def _child_collection_present(record: Dict[str, Any], kind: str) -> bool:
    return any(key in record for key in CHILD_COLLECTIONS.get(kind, ()))


def _normalize_identifier(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).strip().lower())


def _child_matches(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    return any(
        not _missing(left.get(key))
        and not _missing(right.get(key))
        and _normalize_identifier(left[key]) == _normalize_identifier(right[key])
        for key in ("tfn", "abn", "name")
    )


def _combined_alias_values(record: Dict[str, Any], aliases: Tuple[str, ...]) -> List[Any]:
    values: List[Any] = []
    for alias in aliases:
        if alias not in record or _missing(record[alias]):
            continue
        values.extend(_values(record[alias]))
    return _dedupe(values)


def _normalize_child(kind: str, raw: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    consumed = set(CHILD_EVIDENCE_ALIASES) | {"source_url", "source_urls"}
    for aliases in CHILD_PARENT_ALIASES[kind].values():
        consumed.update(aliases)
    for canonical, aliases in CHILD_FIELDS[kind].items():
        consumed.update(aliases)
        present = [(alias, raw[alias]) for alias in aliases if alias in raw]
        supplied = [(alias, value) for alias, value in present if not _missing(value)]
        if not supplied:
            if present:
                normalized[canonical] = present[0][1]
            continue
        normalized[canonical] = supplied[0][1]
        conflicts = [value for _, value in supplied[1:] if value != normalized[canonical]]
        if conflicts:
            normalized.setdefault("_conflicts", {})[canonical] = [normalized[canonical], *conflicts]
    evidence = _combined_alias_values(raw, CHILD_EVIDENCE_ALIASES)
    if evidence:
        normalized["evidence"] = evidence
    valid_sources, invalid_sources = source_provenance(raw)
    if valid_sources:
        normalized["source_urls"] = _dedupe(valid_sources)
    if invalid_sources:
        normalized["_invalid_sources"] = invalid_sources
    for canonical, aliases in CHILD_PARENT_ALIASES[kind].items():
        value = _first_meaningful(raw, aliases)
        if not _missing(value):
            normalized[f"_parent_{canonical}"] = value
    unsupported = {key: value for key, value in raw.items() if key not in consumed}
    if unsupported:
        normalized["_unsupported"] = unsupported
    return normalized


def _merge_child(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if key == "source_urls":
            merged[key] = _dedupe([*_values(merged.get(key, [])), *_values(value)])
        elif key in {"evidence", "_invalid_sources"}:
            merged[key] = _dedupe([*_values(merged.get(key, [])), *_values(value)])
        elif key == "_unsupported":
            bucket = dict(merged.get(key, {}))
            for field, supplied in value.items():
                if field not in bucket:
                    bucket[field] = supplied
                elif bucket[field] != supplied:
                    merged.setdefault("_conflicts", {})[f"unsupported.{field}"] = _dedupe([
                        bucket[field], supplied,
                    ])
            merged[key] = bucket
        elif key == "_conflicts":
            bucket = dict(merged.get(key, {}))
            for field, supplied in value.items():
                bucket[field] = _dedupe([*_values(bucket.get(field, [])), *_values(supplied)])
            merged[key] = bucket
        elif key not in merged or _missing(merged[key]):
            merged[key] = value
        elif merged[key] != value:
            merged.setdefault("_conflicts", {})[key] = _dedupe([merged[key], value])
    return merged


def _parent_matches(kind: str, child: Dict[str, Any], parent: Dict[str, Any]) -> bool:
    supplied = False
    for key in ("abn", "name"):
        child_value = child.get(f"_parent_{key}")
        if _missing(child_value):
            continue
        supplied = True
        if _normalize_identifier(child_value) != _normalize_identifier(parent.get(key, "")):
            return False
    return supplied


def _parent_record(record: Dict[str, Any], kind: str) -> bool:
    return any(field in record and not _missing(record[field]) for field in FIELDS[kind])


def _child_records(kind: str, records: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], Optional[int], Optional[str]]]:
    parents = [index for index, record in enumerate(records) if _parent_record(record, kind)]
    candidates: List[Tuple[Dict[str, Any], Optional[int], Optional[str]]] = []
    for source_index, record in enumerate(records):
        supplied_items: List[Any] = []
        empty_marker: Any = None
        collection_supplied = False
        for collection_key in CHILD_COLLECTIONS[kind]:
            if collection_key not in record:
                continue
            collection_supplied = True
            value = record[collection_key]
            if _blank(value):
                empty_marker = value
                continue
            supplied_items.extend(_values(value))
        if not supplied_items and collection_supplied:
            supplied_items = [{REQUEST_MARKER: empty_marker}]
        elif supplied_items:
            populated_items = [
                item
                for item in supplied_items
                if not isinstance(item, dict) or not _blank(item)
            ]
            supplied_items = populated_items or [{REQUEST_MARKER: supplied_items}]
        for raw in supplied_items:
            if not isinstance(raw, dict):
                candidates.append(({"_malformed": raw}, None, "statement item shape"))
                continue
            if REQUEST_MARKER in raw:
                candidates.append(({"_request_marker": raw[REQUEST_MARKER]}, None, "statement collection"))
                continue
            child = _normalize_child(kind, raw)
            parent_index: Optional[int] = source_index if source_index in parents else None
            parent_issue: Optional[str] = None
            has_reference = any(not _missing(child.get(f"_parent_{key}")) for key in ("abn", "name"))
            if parent_index is not None and has_reference and not _parent_matches(kind, child, records[parent_index]):
                parent_issue = "conflicting parent entity association"
            elif parent_index is None:
                matches = [index for index in parents if _parent_matches(kind, child, records[index])]
                if len(matches) == 1:
                    parent_index = matches[0]
                elif not has_reference and len(parents) == 1:
                    parent_index = parents[0]
                elif matches:
                    parent_issue = "ambiguous parent entity association"
                elif has_reference:
                    parent_issue = "unmatched parent entity association"
                else:
                    parent_issue = "parent entity identity"
            candidates.append((child, parent_index, parent_issue))

    merged: List[Tuple[Dict[str, Any], Optional[int], Optional[str]]] = []
    exact: set[str] = set()
    for child, parent_index, parent_issue in candidates:
        marker = json.dumps([child, parent_index, parent_issue], sort_keys=True, ensure_ascii=False, default=str)
        if marker in exact:
            continue
        exact.add(marker)
        if child.get("_malformed") is not None or "_request_marker" in child:
            merged.append((child, parent_index, parent_issue))
            continue
        merge_index = next((
            index
            for index, (prior, prior_parent, _) in enumerate(merged)
            if prior_parent == parent_index and _child_matches(prior, child)
        ), None)
        if merge_index is None:
            merged.append((child, parent_index, parent_issue))
            continue
        prior, prior_parent, prior_issue = merged[merge_index]
        merged[merge_index] = (
            _merge_child(prior, child),
            prior_parent,
            prior_issue or parent_issue,
        )
    return merged


def _amount_value_state(value: Any, field_name: str = "") -> Tuple[bool, bool]:
    if _missing(value):
        return False, False
    if isinstance(value, bool):
        return False, False
    if isinstance(value, (int, float, Decimal)):
        valid = Decimal(str(value)).is_finite()
        return valid, valid
    if isinstance(value, dict):
        states = [_amount_value_state(item, str(key)) for key, item in value.items()]
        return bool(states) and all(valid for valid, _ in states), any(amount for _, amount in states)
    if isinstance(value, list):
        states = [_amount_value_state(item) for item in value]
        return bool(states) and all(valid for valid, _ in states), any(amount for _, amount in states)
    if isinstance(value, str):
        if field_name.strip().lower() in COMPONENT_METADATA_FIELDS:
            return bool(value.strip()), False
        try:
            valid = Decimal(value.strip().replace(",", "")).is_finite()
            return valid, valid
        except InvalidOperation:
            return False, False
    return False, False


def _valid_amount_value(value: Any, field_name: str = "") -> bool:
    valid, has_amount = _amount_value_state(value, field_name)
    return valid and has_amount


def _valid_percentage(value: Any) -> bool:
    if isinstance(value, bool) or _missing(value):
        return False
    try:
        number = Decimal(str(value).strip().replace("%", ""))
    except (InvalidOperation, ValueError):
        return False
    return number.is_finite() and Decimal("0") <= number <= Decimal("100")


def _evidence_available(value: Any) -> bool:
    return any(not _missing(item) and not _decline(item) for item in _values(value))


def _statement_received(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in {
        "yes", "received", "available", "provided", "complete",
    }


def _review_signal(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        lowered = value.strip().lower()
        return any(token in lowered for token in (
            "accountant review", "unclear", "unknown", "ambiguous", "disputed",
            "contingent", "partial", "mixed", "qualified", "estimate",
        ))
    if isinstance(value, dict):
        return any(_review_signal(item) for item in value.values())
    if isinstance(value, list):
        return any(_review_signal(item) for item in value)
    return False


def _child_fact_pairs(
    kind: str,
    child: Dict[str, Any],
    parent: Dict[str, Any],
    parent_attached: bool,
) -> List[Tuple[str, Any]]:
    facts: List[Tuple[str, Any]] = []
    for field in ("name", "abn"):
        value = parent.get(field)
        if not _missing(value):
            facts.append((f"{kind}_{field}", value))
    if not parent_attached:
        for field in ("name", "abn"):
            value = child.get(f"_parent_{field}")
            if not _missing(value):
                facts.append((f"{kind}_{field}", value))
    for field in CHILD_FIELDS[kind]:
        if field in child and field not in {"status", "review_status", "accountant_review"}:
            facts.append((field, child[field]))
    if "evidence" in child:
        facts.append(("evidence", child["evidence"]))
    return facts


def _child_gaps(
    kind: str,
    child: Dict[str, Any],
    parent_issue: Optional[str],
) -> Tuple[List[str], List[Any], Dict[str, Any], Dict[str, Any]]:
    gaps: List[str] = []
    if not any(not _missing(child.get(field)) for field in ("name", "tfn", "abn")):
        gaps.append(f"{CHILD_LABEL[kind].lower()} identity")
    if parent_issue:
        gaps.append(parent_issue)
    for field in CHILD_REQUIRED[kind]:
        if field == "evidence":
            missing_field = field not in child or not _evidence_available(child.get(field))
        else:
            missing_field = field not in child or _missing(child.get(field))
        if missing_field:
            gaps.append(field.replace("_", " "))
    if "statement_status" in child and not _statement_received(child["statement_status"]):
        gaps.append("received statement")
    for field in CHILD_AMOUNT_FIELDS[kind]:
        if field == "distributions" and isinstance(child.get(field), bool):
            continue
        if field in child and not _valid_amount_value(child[field]):
            gaps.append(f"valid {field.replace('_', ' ')}")
    if kind == "partnership" and "share_percentage" in child and not _valid_percentage(child["share_percentage"]):
        gaps.append("partner share percentage between 0 and 100")

    invalid_sources = child.get("_invalid_sources", [])
    if invalid_sources:
        gaps.append("source provenance")
    checked_at = child.get("checked_at")
    if "checked_at" in child and not _missing(checked_at) and not valid_checked_at(checked_at):
        gaps.append(f"checked-at provenance ({_display(checked_at)})")
    conflicts = child.get("_conflicts", {})
    if conflicts:
        gaps.append("conflicting statement facts")
    unsupported = child.get("_unsupported", {})
    if unsupported:
        gaps.append("unsupported statement facts")
    return list(dict.fromkeys(gaps)), invalid_sources, conflicts, unsupported


def _child_row(
    kind: str,
    index: int,
    child: Dict[str, Any],
    facts: List[Tuple[str, Any]],
) -> Dict[str, Any]:
    label = CHILD_LABEL[kind]
    checked_at = child.get("checked_at")
    valid_sources = child.get("source_urls", [])
    return {
        "number": f"{CHILD_ROW_PREFIX[kind]}-{index}",
        "ato_area": f"{label} statement preparation",
        "question": f"{label} distribution statement",
        "answer": "; ".join(f"{field.replace('_', ' ')} {_display(value)}" for field, value in facts),
        "why_included": "Separate prep-only entity-return statement routing; no allocation, entitlement decision, tax treatment, or lodgment.",
        "status": "Accountant review",
        "source_urls": list(dict.fromkeys([SOURCES[kind], *valid_sources])),
        "checked_at": checked_at if valid_checked_at(checked_at) else CHECKED_AT,
        "row_kind": CHILD_ROW_KIND[kind],
        "facts": [
            {"key": field.replace("_", "-"), "label": field.replace("_", " ").title(), "value": value}
            for field, value in facts
        ],
        "tab_text": f"{label} statement facts require accountant review in the separate {kind} return workflow.",
    }


def _child_followup_row(
    kind: str,
    child: Dict[str, Any],
    gaps: List[str],
    invalid_sources: List[Any],
    conflicts: Dict[str, Any],
    unsupported: Dict[str, Any],
    evidence_index: int,
) -> Dict[str, Any]:
    gap_facts: List[Dict[str, Any]] = [{
        "key": "missing",
        "label": "Missing or ambiguous facts",
        "value": gaps,
    }]
    if conflicts:
        gap_facts.append({"key": "conflicts", "label": "Conflicting facts", "value": conflicts})
    if unsupported:
        gap_facts.append({"key": "unsupported", "label": "Unsupported facts", "value": unsupported})
    if invalid_sources:
        gap_facts.append({
            "key": "unresolved-source-provenance",
            "label": "Unresolved source provenance",
            "value": invalid_sources,
        })
    review_required = bool(conflicts) or any(
        _review_signal(child.get(field))
        for field in CHILD_REVIEW_FIELDS[kind]
    )
    checked_at = child.get("checked_at")
    valid_sources = child.get("source_urls", [])
    label = CHILD_LABEL[kind]
    return {
        "number": f"ENTITY-EVID-{evidence_index}",
        "ato_area": f"{label} statement evidence",
        "question": f"{label} statement requires follow-up",
        "answer": f"Confirm {', '.join(gaps)}",
        "why_included": "Incomplete, conflicting, or unsupported statement facts fail closed before handoff.",
        "status": "Accountant review" if review_required else "Evidence",
        "source_urls": list(dict.fromkeys([SOURCES[kind], *valid_sources])),
        "checked_at": checked_at if valid_checked_at(checked_at) else CHECKED_AT,
        "row_kind": f"{CHILD_ROW_KIND[kind]}-evidence",
        "facts": gap_facts,
    }


def _unresolved_child_row(kind: str, raw: Any, evidence_index: int) -> Dict[str, Any]:
    label = CHILD_LABEL[kind]
    return {
        "number": f"ENTITY-EVID-{evidence_index}",
        "ato_area": f"{label} statement evidence",
        "question": f"{label} statement facts required",
        "answer": f"Preserved unresolved statement input: {_display(raw)}",
        "why_included": "Missing or malformed statement input fails closed instead of being treated as no distribution.",
        "status": "Evidence", "source_urls": [SOURCES[kind]], "checked_at": CHECKED_AT,
        "row_kind": f"{CHILD_ROW_KIND[kind]}-evidence",
        "facts": [{"key": "raw", "label": "Raw statement input", "value": raw}],
    }


def _child_rows(
    kind: str,
    records: List[Dict[str, Any]],
    evidence_index: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    rows: List[Dict[str, Any]] = []
    evidence_rows: List[Dict[str, Any]] = []
    for index, (child, parent_index, parent_issue) in enumerate(_child_records(kind, records), start=1):
        if "_malformed" in child or "_request_marker" in child:
            raw = child.get("_malformed", child.get("_request_marker"))
            evidence_rows.append(_unresolved_child_row(kind, raw, evidence_index))
            evidence_index += 1
            continue

        parent = records[parent_index] if parent_index is not None else {}
        facts = _child_fact_pairs(kind, child, parent, parent_index is not None)
        rows.append(_child_row(kind, index, child, facts))
        gaps, invalid_sources, conflicts, unsupported = _child_gaps(kind, child, parent_issue)
        if gaps:
            evidence_rows.append(_child_followup_row(
                kind,
                child,
                gaps,
                invalid_sources,
                conflicts,
                unsupported,
                evidence_index,
            ))
            evidence_index += 1
    return rows, evidence_rows, evidence_index


def _flat_record(answers: Dict[str, Any], kind: str) -> Dict[str, Any]:
    record: Dict[str, Any] = {}
    has_legacy_marker = any(
        _entity_marker(answers.get(alias))
        for alias in ALIASES[kind]
    )
    for field in FIELDS[kind]:
        return_key = f"{kind}_return_{field}"
        legacy_key = f"{kind}_{field}"
        if return_key in answers:
            record[field] = answers[return_key]
        elif has_legacy_marker and legacy_key in answers:
            record[field] = answers[legacy_key]
        elif field == "name" and has_legacy_marker and kind in {"trust", "partnership"} and kind in answers:
            record[field] = answers[kind]
    for field in ("source_url", "source_urls", "checked_at", "status", "review_status"):
        return_key = f"{kind}_return_{field}"
        legacy_key = f"{kind}_{field}"
        if return_key in answers:
            record[field] = answers[return_key]
        elif has_legacy_marker and legacy_key in answers:
            record[field] = answers[legacy_key]
    prefix = f"{kind}_return_"
    for key, value in answers.items():
        if key.startswith(prefix):
            record.setdefault(key[len(prefix):], value)
    return record


def individual_share_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(answers)
    metadata_fields = ("source_url", "source_urls", "checked_at", "status", "review_status")
    for kind in ("trust", "partnership"):
        if not _entity_request_present(answers, kind):
            continue
        for field in (*FIELDS[kind], *metadata_fields):
            sanitized.pop(f"{kind}_{field}", None)
        for key in LEGACY_SHARE_FIELDS[kind]:
            sanitized.pop(key, None)
    return sanitized


def _entity_request_present(answers: Dict[str, Any], kind: str) -> bool:
    if any(key.startswith(f"{kind}_return_") for key in answers):
        return True
    return any(
        alias in answers
        and not _decline(answers[alias])
        and (
            _entity_input(answers[alias])
            or isinstance(answers[alias], (dict, list))
        )
        for alias in ALIASES[kind]
    )


def entity_facts_present(value: Any) -> bool:
    return not _missing(value)


def _unsupported_evidence(kind: str, unsupported: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "number": f"ENTITY-EVID-{index}",
        "ato_area": f"{LABELS[kind]} return scope review",
        "question": f"{LABELS[kind]} facts outside skeleton scope",
        "answer": f"Preserved for accountant review only: {_display(unsupported)}",
        "why_included": "Facts outside skeleton routing are retained without importing downstream tax treatment.",
        "status": "Accountant review", "source_urls": [SOURCES[kind]],
        "checked_at": CHECKED_AT, "row_kind": f"entity-return-{kind}-unsupported",
        "facts": [{"key": "unsupported", "label": "Unsupported entity facts", "value": unsupported}],
    }


def _records(answers: Dict[str, Any]) -> Tuple[Dict[str, List[Any]], List[Any]]:
    grouped = {kind: [] for kind in ALIASES}
    malformed: List[Any] = []
    for kind, aliases in ALIASES.items():
        initial_count = len(grouped[kind])
        request_marker: Any = None
        for alias in aliases:
            if alias not in answers or _decline(answers[alias]) or answers[alias] is None:
                continue
            value = answers[alias]
            if isinstance(value, (dict, list)) and _missing(value):
                request_marker = value
                continue
            if _missing(value):
                continue
            if _entity_marker(value):
                request_marker = value
                continue
            grouped[kind].extend(value if isinstance(value, list) else [value])
        flat = _flat_record(answers, kind)
        if flat:
            if len(grouped[kind]) == initial_count + 1 and isinstance(grouped[kind][-1], dict):
                nested = grouped[kind][-1]
                conflicts: Dict[str, Dict[str, Any]] = {}
                for key, value in flat.items():
                    if key not in nested:
                        nested[key] = value
                    elif key in CHILD_COLLECTIONS.get(kind, ()) and nested[key] != value:
                        nested[key] = _child_collection_value(nested[key], value)
                    elif nested[key] != value:
                        conflicts[key] = {"nested": nested[key], "flat": value}
                if conflicts:
                    nested["conflicting_flat_facts"] = conflicts
            else:
                grouped[kind].append(flat)
        elif request_marker is not None and len(grouped[kind]) == initial_count:
            grouped[kind].append({REQUEST_MARKER: request_marker})
    for collection_key in ("entities", "entity_returns"):
        entities = answers.get(collection_key, [])
        if _decline(entities) or _missing(entities):
            continue
        collection = entities if isinstance(entities, list) else [entities]
        for item in collection:
            if not isinstance(item, dict):
                malformed.append(item)
                continue
            kind = str(_first_meaningful(item, ("entity_type", "type")) or "").strip().lower()
            if kind in grouped:
                grouped[kind].append(item)
            elif kind not in {"individual", "sole trader", "sole_trader"}:
                malformed.append(item)
    for kind, values in grouped.items():
        unique: List[Any] = []
        seen: set[str] = set()
        for value in values:
            marker = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(value)
        grouped[kind] = unique
    return grouped, malformed


def route_entity_returns(
    answers: Dict[str, Any],
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    grouped, malformed = _records(answers)
    sections = {f"{kind}_items": [] for kind in grouped}
    evidence: List[Dict[str, Any]] = []
    evidence_index = 1
    for kind, records in grouped.items():
        valid_records = [raw for raw in records if isinstance(raw, dict)]
        malformed.extend(raw for raw in records if not isinstance(raw, dict))
        for index, raw in enumerate(valid_records, start=1):
            if REQUEST_MARKER in raw:
                missing = [field.replace("_", " ") for field in REQUIRED[kind]]
                evidence.append({
                    "number": f"ENTITY-EVID-{evidence_index}",
                    "ato_area": f"{LABELS[kind]} return intake evidence",
                    "question": f"{LABELS[kind]} return requested; intake facts required",
                    "answer": f"Confirm {', '.join(missing)}",
                    "why_included": "An explicit entity-return request fails closed until skeleton intake facts are supplied.",
                    "status": "Evidence", "source_urls": [SOURCES[kind]],
                    "checked_at": CHECKED_AT, "row_kind": f"entity-return-{kind}-request",
                    "facts": [{"key": "request", "label": "Entity return requested", "value": raw[REQUEST_MARKER]}],
                })
                evidence_index += 1
                continue
            facts = [(field, raw[field]) for field in FIELDS[kind] if field in raw]
            unsupported = {
                key: value
                for key, value in raw.items()
                if key not in FIELDS[kind]
                and key not in ROUTING_METADATA
                and key not in CHILD_COLLECTIONS.get(kind, ())
            }
            if not facts:
                if unsupported:
                    evidence.append(_unsupported_evidence(kind, unsupported, evidence_index))
                    evidence_index += 1
                elif _child_collection_present(raw, kind):
                    pass
                else:
                    malformed.append(raw)
                continue
            gaps = [
                field.replace("_", " ")
                for field in REQUIRED[kind]
                if field not in raw or _missing(raw.get(field))
            ]
            if kind == "partnership" and "share_percentages" in raw:
                values = raw["share_percentages"]
                valid_values = (
                    isinstance(values, list)
                    and bool(values)
                    and all(
                        isinstance(value, (int, float)) and not isinstance(value, bool)
                        for value in values
                    )
                    and sum(values) == 100
                )
                if not valid_values:
                    gaps.append("partner share percentages")
            answer = "; ".join(f"{field.replace('_', ' ')} {_display(value)}" for field, value in facts)
            valid_sources, invalid_sources = source_provenance(raw)
            if invalid_sources:
                gaps.append("source provenance")
            checked_at = raw.get("checked_at")
            if "checked_at" in raw and not _missing(checked_at) and not valid_checked_at(checked_at):
                gaps.append(f"checked-at provenance ({_display(checked_at)})")
            source_urls = [SOURCES[kind], *valid_sources]
            row = {
                "number": f"{kind.upper()}-{index}", "ato_area": f"{LABELS[kind]} return preparation",
                "question": f"{LABELS[kind]} return intake", "answer": answer,
                "why_included": f"Separate prep-only {kind} return routing; no individual-return entry or final treatment.",
                "status": "Accountant review", "source_urls": list(dict.fromkeys(source_urls)),
                "checked_at": checked_at if valid_checked_at(checked_at) else CHECKED_AT,
                "row_kind": f"entity-return-{kind}",
                "facts": [{"key": field.replace("_", "-"), "label": field.replace("_", " ").title(), "value": value} for field, value in facts],
                "tab_text": f"{LABELS[kind]} facts stay in the separate prep-only workflow and require accountant review.",
            }
            sections[f"{kind}_items"].append(row)
            if unsupported:
                evidence.append(_unsupported_evidence(kind, unsupported, evidence_index))
                evidence_index += 1
            if gaps:
                gap_facts = [{
                    "key": "missing",
                    "label": "Missing or ambiguous facts",
                    "value": list(dict.fromkeys(gaps)),
                }]
                if invalid_sources:
                    gap_facts.append({
                        "key": "unresolved-source-provenance",
                        "label": "Unresolved source provenance",
                        "value": invalid_sources,
                    })
                evidence.append({
                    "number": f"ENTITY-EVID-{evidence_index}", "ato_area": f"{LABELS[kind]} return evidence",
                    "question": f"{LABELS[kind]} evidence required", "answer": f"Confirm {', '.join(dict.fromkeys(gaps))}",
                    "why_included": "Incomplete or ambiguous entity facts fail closed before any workflow handoff.",
                    "status": "Evidence", "source_urls": [SOURCES[kind]], "checked_at": CHECKED_AT,
                    "row_kind": f"entity-return-{kind}-evidence",
                    "facts": gap_facts,
                })
                evidence_index += 1
        if kind in CHILD_COLLECTIONS:
            child_items, child_evidence, evidence_index = _child_rows(
                kind,
                valid_records,
                evidence_index,
            )
            sections[f"{kind}_items"].extend(child_items)
            evidence.extend(child_evidence)
    for value in malformed:
        evidence.append({
            "number": f"ENTITY-EVID-{evidence_index}", "ato_area": "Entity return input shape review",
            "question": "Malformed entity item", "answer": f"Malformed entity item preserved: {_display(value)}",
            "why_included": "Malformed entity input fails closed instead of crossing a workflow boundary.",
            "status": "Evidence", "source_urls": [], "checked_at": CHECKED_AT,
            "row_kind": "entity-return-malformed", "facts": [{"key": "raw", "label": "Raw entity input", "value": value}],
        })
        evidence_index += 1
    return sections, evidence
