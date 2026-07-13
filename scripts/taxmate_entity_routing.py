"""Shared prep-only entity-return intake routing."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

CHECKED_AT = "2026-07-13"
SOURCES = {
    "company": "https://www.ato.gov.au/api/public/content/0-e220713e-6a6f-4401-b966-8bddf3ba96fd",
    "trust": "https://www.ato.gov.au/api/public/content/0-70d99f71-9469-4fd4-97fe-e328d58b37ab",
    "partnership": "https://www.ato.gov.au/api/public/content/1453e44ff39e4eb789ea83eeb6eac10b?v=5c58b86f",
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


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        values = value.values() if isinstance(value, dict) else value
        return not any(not _missing(item) for item in values)
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return not normalized or normalized in {"unknown", "unclear", "missing", "n/a"}


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def _decline(value: Any) -> bool:
    if value is False:
        return True
    return isinstance(value, str) and value.strip().lower() in {
        "no", "false", "none", "not applicable",
    }


def _entity_marker(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in {"yes", "true", "on", "checked"}


def _first_meaningful(record: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if not _missing(value):
            return value
    return None


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
    for field in ("source_url", "source_urls", "checked_at", "status", "review_status"):
        return_key = f"{kind}_return_{field}"
        legacy_key = f"{kind}_{field}"
        if return_key in answers:
            record[field] = answers[return_key]
        elif has_legacy_marker and legacy_key in answers:
            record[field] = answers[legacy_key]
    return record


def _records(answers: Dict[str, Any]) -> Tuple[Dict[str, List[Any]], List[Any]]:
    grouped = {kind: [] for kind in ALIASES}
    malformed: List[Any] = []
    for kind, aliases in ALIASES.items():
        for alias in aliases:
            if alias not in answers or _decline(answers[alias]) or answers[alias] is None:
                continue
            value = answers[alias]
            if _entity_marker(value):
                continue
            grouped[kind].extend(value if isinstance(value, list) else [value])
        flat = _flat_record(answers, kind)
        if flat:
            grouped[kind].append(flat)
    for collection_key in ("entities", "entity_returns"):
        entities = answers.get(collection_key, [])
        if entities in (None, "", [], {}):
            continue
        collection = entities if isinstance(entities, list) else [entities]
        for item in collection:
            if not isinstance(item, dict):
                malformed.append(item)
                continue
            kind = str(_first_meaningful(item, ("entity_type", "type")) or "").strip().lower()
            if kind in grouped:
                grouped[kind].append(item)
            elif kind not in {"", "individual", "sole trader", "sole_trader"}:
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
        for index, raw in enumerate(records, start=1):
            if not isinstance(raw, dict):
                malformed.append(raw)
                continue
            facts = [(field, raw[field]) for field in FIELDS[kind] if field in raw]
            if not facts:
                malformed.append(raw)
                continue
            gaps = [
                field.replace("_", " ")
                for field in REQUIRED[kind]
                if field not in raw or _missing(raw.get(field))
            ]
            if kind == "partnership" and isinstance(raw.get("share_percentages"), list):
                values = raw["share_percentages"]
                invalid_values = any(
                    not isinstance(value, (int, float)) or isinstance(value, bool)
                    for value in values
                )
                if not values or invalid_values or sum(values) != 100:
                    gaps.append("partner share percentages")
            answer = "; ".join(f"{field.replace('_', ' ')} {_display(value)}" for field, value in facts)
            supplied_sources: List[Any] = []
            for source_key in ("source_urls", "source_url"):
                source_value = raw.get(source_key)
                if _missing(source_value):
                    continue
                supplied_sources.extend(source_value if isinstance(source_value, list) else [source_value])
            invalid_sources = [
                value
                for value in supplied_sources
                if not isinstance(value, str)
                or not value.strip().startswith(("https://", "http://"))
            ]
            if invalid_sources:
                gaps.append("source provenance")
            valid_sources = [
                value.strip()
                for value in supplied_sources
                if isinstance(value, str)
                and value.strip().startswith(("https://", "http://"))
            ]
            source_urls = [SOURCES[kind], *valid_sources]
            row = {
                "number": f"{kind.upper()}-{index}", "ato_area": f"{LABELS[kind]} return preparation",
                "question": f"{LABELS[kind]} return intake", "answer": answer,
                "why_included": f"Separate prep-only {kind} return routing; no individual-return entry or final treatment.",
                "status": "Accountant review", "source_urls": list(dict.fromkeys(source_urls)),
                "checked_at": raw.get("checked_at") if not _missing(raw.get("checked_at")) else CHECKED_AT,
                "row_kind": f"entity-return-{kind}",
                "facts": [{"key": field.replace("_", "-"), "label": field.replace("_", " ").title(), "value": value} for field, value in facts],
                "tab_text": f"{LABELS[kind]} facts stay in the separate prep-only workflow and require accountant review.",
            }
            sections[f"{kind}_items"].append(row)
            if gaps:
                evidence.append({
                    "number": f"ENTITY-EVID-{evidence_index}", "ato_area": f"{LABELS[kind]} return evidence",
                    "question": f"{LABELS[kind]} evidence required", "answer": f"Confirm {', '.join(dict.fromkeys(gaps))}",
                    "why_included": "Incomplete or ambiguous entity facts fail closed before any workflow handoff.",
                    "status": "Evidence", "source_urls": [SOURCES[kind]], "checked_at": CHECKED_AT,
                    "row_kind": f"entity-return-{kind}-evidence",
                    "facts": [{"key": "missing", "label": "Missing or ambiguous facts", "value": list(dict.fromkeys(gaps))}],
                })
                evidence_index += 1
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
