#!/usr/bin/env python3
"""TaxMate Australia taxpack guide renderer."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import taxmate_handoff


DEFAULT_INCOME_YEAR = "2025-26"
FORBIDDEN_VISIBLE_PHRASES = [
    "Prepared by " + "TaxMate",
    "lodgment-" + "ready",
    "file with the " + "ATO",
    "submit this guide",
    "submit this PDF",
]
@dataclass
class GuideItem:
    number: Any
    ato_area: Any
    question: Any
    answer: Any
    why_included: Any
    source_urls: List[Any]
    checked_at: Any
    status: Any
    status_kind: Any
    tab_title: Any
    tab_text: Any
    tab_kind: Any
    row_kind: Any = "external-row"
    facts: List[Dict[str, Any]] = field(default_factory=list)
    handoff: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GuideData:
    income_year: Any
    generated_date: Any
    summary_note: Any
    items: List[GuideItem]
    extracted_values: List[Dict[str, Any]] = field(default_factory=list)
    abn_items: List[GuideItem] = field(default_factory=list)
    bas_items: List[GuideItem] = field(default_factory=list)
    missing_facts: List[GuideItem] = field(default_factory=list)
    evidence_items: List[GuideItem] = field(default_factory=list)


@dataclass
class RenderRow:
    section: str
    section_title: str
    ordinal: int
    item: GuideItem
    anchor: str
    contract: Dict[str, Any]


@dataclass
class SourceGroup:
    anchor: str
    label: str
    url: str
    titles: List[str] = field(default_factory=list)
    checked_at: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    rows: List[RenderRow] = field(default_factory=list)


def sample_payload() -> Dict[str, Any]:
    return {
        "income_year": DEFAULT_INCOME_YEAR,
        "summary_note": "The item index links to each prepared row, next action, destination, and source context.",
        "items": [
            {
                "number": "5",
                "ato_area": "Deductions - work-related expenses",
                "question": "Did you work from home?",
                "answer": "843 hours; fixed-rate method candidate",
                "why_included": "May support WFH deduction if ATO rate, records, and eligibility align.",
                "source_url": "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method",
                "checked_at": "2026-06-23T09:04:57Z",
                "status": "Evidence",
                "status_kind": "evidence",
                "tab_title": "Row 5 answer used",
                "tab_text": "WFH hours need diary/timesheet and current-year rate support.",
                "tab_kind": "answer",
                "row_kind": "work-from-home",
                "facts": [
                    {"key": "hours", "label": "Hours", "value": 843},
                    {"key": "method", "label": "Method", "value": "Fixed-rate method candidate"},
                ],
            },
            {
                "number": "6",
                "ato_area": "Deductions - tools/equipment",
                "question": "Any work devices or software?",
                "answer": "Laptop, $1,850, 70% work use claimed",
                "why_included": "Mixed-use percentage and decline-in-value method need review.",
                "source_url": "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/tools-computers-and-items-you-use-for-work/computers-laptops-and-software",
                "checked_at": "2026-06-23T09:04:57Z",
                "status": "Review",
                "status_kind": "review",
                "tab_title": "Row 6 mixed use",
                "tab_text": "Work-use percentage is not final without review.",
                "tab_kind": "review",
                "row_kind": "work-asset",
                "facts": [
                    {"key": "asset", "label": "Asset", "value": "Laptop"},
                    {"key": "cost", "label": "Cost", "value": "$1,850"},
                    {"key": "work-use", "label": "Work use supplied", "value": "70%"},
                ],
            },
            {
                "number": "7",
                "ato_area": "Business income/expenses",
                "question": "Any ABN or side activity?",
                "answer": "ABN active; $0 income; startup costs",
                "why_included": "Business-vs-hobby, pre-revenue timing, and non-commercial loss rules may apply.",
                "source_url": "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/overview-of-business-income-and-deductions",
                "checked_at": "2026-06-23T09:04:57Z",
                "status": "Review",
                "status_kind": "review",
                "tab_title": "Row 7 ABN/pre-revenue",
                "tab_text": "Startup costs require accountant review.",
                "tab_kind": "review",
                "row_kind": "abn-business",
                "facts": [
                    {"key": "abn", "label": "ABN status", "value": "Active"},
                    {"key": "income", "label": "Income supplied", "value": 0},
                    {"key": "costs", "label": "Costs", "value": "Startup costs supplied"},
                ],
            },
            {
                "number": "8",
                "ato_area": "Private health / Medicare",
                "question": "Private hospital cover?",
                "answer": "Insurer statement missing",
                "why_included": "Needed for Medicare levy surcharge/private health rebate labels.",
                "source_url": "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/private-health-insurance-rebate/your-private-health-insurance-statement",
                "checked_at": "2026-06-23T09:04:57Z",
                "status": "Evidence",
                "status_kind": "evidence",
                "tab_title": "Row 8 missing statement",
                "tab_text": "Private health statement missing.",
                "tab_kind": "evidence",
                "row_kind": "private-health",
                "facts": [
                    {"key": "statement", "label": "Insurer statement", "value": "Missing"},
                ],
            },
        ],
    }


def load_guide_data(path: Optional[str]) -> GuideData:
    payload = sample_payload() if not path else read_json(path)
    return load_guide_payload(payload)


def load_guide_payload(payload: Dict[str, Any]) -> GuideData:
    if not isinstance(payload, dict):
        raise ValueError("guide input must be a JSON object")
    income_year = text_value(payload, "income_year", DEFAULT_INCOME_YEAR)
    raw_items = payload.get("items", [])
    if not isinstance(raw_items, list):
        raw_items = [
            {
                "number": "MALFORMED-items",
                "ato_area": "Input shape review",
                "question": "Malformed items input",
                "answer": scalar_text(raw_items),
                "why_included": "Input section had the wrong shape and was kept for accountant review instead of being dropped.",
                "status": "Accountant review",
            }
        ]
    items = [
        guide_item(raw, income_year=income_year, fallback_number=f"ITEM-{index}")
        if isinstance(raw, dict)
        else malformed_section_item(f"items-{index}", raw, income_year)
        for index, raw in enumerate(raw_items, start=1)
    ]
    extraction_rows = extracted_values(payload.get("extracted_values", []), income_year)
    abn_items = section_items(payload, "abn_items", income_year, "ABN")
    bas_items = section_items(payload, "bas_items", income_year, "BAS")
    missing_facts = section_items(payload, "missing_facts", income_year, "MISS")
    evidence_items = section_items(payload, "evidence_items", income_year, "EVID")
    if not any((items, extraction_rows, abn_items, bas_items, missing_facts, evidence_items)):
        raise ValueError("guide input must include at least one row or queue item")
    generated_date = text_value(payload, "generated_date", default_generated_date())
    return GuideData(
        income_year=income_year,
        generated_date=generated_date,
        summary_note=text_value(payload, "summary_note", sample_payload()["summary_note"]),
        items=items,
        extracted_values=extraction_rows,
        abn_items=abn_items,
        bas_items=bas_items,
        missing_facts=missing_facts,
        evidence_items=evidence_items,
    )


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("guide input must be a JSON object")
    return payload


def section_items(
    payload: Dict[str, Any],
    key: str,
    income_year: str = DEFAULT_INCOME_YEAR,
    fallback_prefix: str = "ITEM",
) -> List[GuideItem]:
    raw_items = payload.get(key, [])
    if not isinstance(raw_items, list):
        return [malformed_section_item(key, raw_items, income_year)]
    items: List[GuideItem] = []
    for index, raw in enumerate(raw_items, start=1):
        if isinstance(raw, dict):
            items.append(
                guide_item(
                    raw,
                    income_year=income_year,
                    fallback_number=f"{fallback_prefix}-{index}",
                )
            )
        else:
            items.append(malformed_section_item(f"{key}-{index}", raw, income_year))
    return items


def extracted_values(raw_items: Any, income_year: str = DEFAULT_INCOME_YEAR) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        normalized = normalize_extraction_row(
            malformed_extraction_row(raw_items, index=1),
            income_year,
            index=1,
        )
        return [normalized] if normalized is not None else []
    rows: List[Dict[str, Any]] = []
    for index, raw in enumerate(raw_items, start=1):
        normalized = normalize_extraction_row(raw, income_year, index=index)
        if normalized is not None:
            rows.append(normalized)
    return rows


def malformed_section_item(key: str, value: Any, income_year: str = DEFAULT_INCOME_YEAR) -> GuideItem:
    return guide_item(
        {
            "number": f"MALFORMED-{key}",
            "ato_area": "Input shape review",
            "question": f"Malformed {key} input",
            "answer": scalar_text(value),
            "why_included": "Input section had the wrong shape and was kept for accountant review instead of being dropped.",
            "status": "Accountant review",
            "tab_kind": "review",
            "tab_text": f"Malformed {key} input requires review before entry.",
        },
        income_year=income_year,
    )


def malformed_extraction_row(value: Any, index: int = 1) -> Dict[str, Any]:
    return {
        "number": f"AI-MALFORMED-{index}",
        "document": "Malformed AI extraction input",
        "page": "",
        "field": "AI extraction",
        "value": scalar_text(value),
        "confidence": "",
        "target_label": "",
        "status": "Accountant review",
    }


def normalize_extraction_row(
    raw: Any,
    income_year: str,
    *,
    index: int = 1,
) -> Optional[Dict[str, Any]]:
    normalized = taxmate_handoff.normalize_extraction_row(
        raw,
        income_year,
        index=index,
    )
    return dict(normalized) if isinstance(normalized, dict) else None


def guide_item(
    raw: Dict[str, Any],
    income_year: str = DEFAULT_INCOME_YEAR,
    fallback_number: str = "ITEM",
) -> GuideItem:
    if not isinstance(raw, dict):
        raise ValueError("guide items must be JSON objects")
    number = text_value(raw, "number").strip() or fallback_number
    status_kind = item_status_kind(raw)
    tab_kind = item_tab_kind(raw, status_kind)
    tab_title = first_text(raw, ["tab_title"], f"Row {number} {short_status(status_kind)}")
    tab_text = first_text(raw, ["tab_text", "why_included"], fallback_tab_text(number, status_kind))
    contract = taxmate_handoff.normalize_row_contract(
        row_kind=raw.get("row_kind"),
        facts=raw.get("facts"),
        handoff=raw.get("handoff"),
        status=status_kind,
        income_year=income_year,
        question=raw.get("question"),
        answer=raw.get("answer"),
        why=raw.get("why_included"),
    )
    return GuideItem(
        number=number,
        ato_area=text_value(raw, "ato_area"),
        question=text_value(raw, "question"),
        answer=text_value(raw, "answer"),
        why_included=text_value(raw, "why_included"),
        source_urls=source_urls(raw),
        checked_at=text_value(raw, "checked_at"),
        status=canonical_status(status_kind),
        status_kind=status_kind,
        tab_title=tab_title,
        tab_text=tab_text,
        tab_kind=tab_kind,
        row_kind=contract["row_kind"],
        facts=contract["facts"],
        handoff=contract["handoff"],
    )


def item_status_kind(raw: Dict[str, Any]) -> str:
    return taxmate_handoff.effective_status_kind(
        raw.get("status_kind"),
        raw.get("status"),
        raw.get("tab_kind"),
    )


def item_tab_kind(raw: Dict[str, Any], status_kind: str) -> str:
    return taxmate_handoff.effective_status_kind(status_kind, raw.get("tab_kind"))


_MISSING = object()


def text_value(raw: Dict[str, Any], key: str, default: str = "") -> str:
    value = raw.get(key, _MISSING)
    if value is _MISSING or value is None:
        return default
    text = scalar_text(value)
    return text if text.strip() else default


def first_text(raw: Dict[str, Any], keys: List[str], default: str = "") -> str:
    for key in keys:
        text = text_value(raw, key)
        if text:
            return text
    return default


def fallback_tab_text(number: Any, status_kind: str) -> str:
    return f"Row {scalar_text(number)}: {canonical_status(status_kind)}."


def source_urls(raw: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    single = text_value(raw, "source_url").strip()
    if single:
        urls.append(single)
    multiple = raw.get("source_urls")
    if isinstance(multiple, list):
        for item in multiple:
            url = scalar_text(item).strip()
            if url and url not in urls:
                urls.append(url)
    return urls


def canonical_status(kind: str) -> str:
    if kind == "evidence":
        return "Evidence"
    if kind == "answer":
        return "Used"
    if kind == "ato":
        return "ATO label"
    if kind == "skipped":
        return "N/A skipped"
    return "Accountant review"


def short_status(value: Any) -> str:
    return canonical_status(taxmate_handoff.effective_status_kind(value))


def default_generated_date() -> str:
    return datetime.now().astimezone().strftime("%d %b %Y").lstrip("0")


def render_html(data: GuideData) -> str:
    rows = build_render_rows(data)
    source_groups, row_sources = build_source_groups(rows)
    output = HTML_TEMPLATE.format(
        income_year=esc(data.income_year),
        generated_date=esc(data.generated_date),
        summary_note=esc(data.summary_note),
        taxonomy_legend=render_taxonomy_legend(),
        context_index=render_context_index(rows),
        guide_sections=render_sections(rows, row_sources),
        review_queue=render_review_queue(rows),
        source_appendix=render_source_appendix(source_groups),
        source_appendix_screen_css=(
            ".source-appendix{break-before:page;border-top:2px solid var(--line)}"
            if source_groups
            else ""
        ),
        source_appendix_print_css=(
            ".source-appendix{break-before:page;page-break-before:always}"
            "details.source-appendix:not([open]) > :not(summary){display:block!important}"
            if source_groups
            else ""
        ),
    )
    assert_visible_boundaries(output)
    return output


def item_contract(item: GuideItem, income_year: str) -> Dict[str, Any]:
    status = effective_status_kind(item)
    return taxmate_handoff.normalize_row_contract(
        row_kind=item.row_kind,
        facts=item.facts,
        handoff=item.handoff,
        status=status,
        income_year=income_year,
        question=item.question,
        answer=item.answer,
        why=item.why_included,
    )


def extraction_guide_item(raw: Any, index: int, income_year: str) -> Optional[GuideItem]:
    normalized = normalize_extraction_row(raw, income_year, index=index)
    if normalized is None:
        return None
    payload = dict(normalized)
    payload.setdefault("number", f"AI-{index}")
    payload.setdefault("ato_area", "AI extraction confirmation")
    payload.setdefault("question", text_value(payload, "field", "Extracted document fact"))
    payload.setdefault("answer", payload.get("value"))
    payload.setdefault(
        "why_included",
        "Confirm the supplied extraction against the source document before use.",
    )
    payload.setdefault("tab_text", payload.get("why_included"))
    payload.setdefault("row_kind", "ai-extraction")
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list) or not raw_facts:
        raw_facts = []
        for key, label in (
            ("document", "Source document"),
            ("page", "Page"),
            ("field", "Extracted field"),
            ("value", "Extracted value"),
            ("confidence", "Extraction confidence"),
            ("target_label", "Target label supplied (unverified)"),
        ):
            value = payload.get(key, _MISSING)
            if value is _MISSING or value is None or not scalar_text(value).strip():
                continue
            raw_facts.append({"key": key.replace("_", "-"), "label": label, "value": value})
        payload["facts"] = raw_facts
    return guide_item(
        payload,
        income_year=income_year,
        fallback_number=f"AI-{index}",
    )


def build_render_rows(data: GuideData) -> List[RenderRow]:
    income_year = scalar_text(data.income_year, DEFAULT_INCOME_YEAR)
    extraction_items: List[GuideItem] = []
    for index, raw in enumerate(data.extracted_values, start=1):
        item = extraction_guide_item(raw, index, income_year)
        if item is not None:
            extraction_items.append(item)
    sections = (
        ("main", "Prepared return items", data.items),
        ("ai", "AI extraction confirmation", extraction_items),
        ("abn", "ABN preparation", data.abn_items),
        ("bas", "BAS preparation", data.bas_items),
        ("missing", "Missing facts queue", data.missing_facts),
        ("evidence", "Evidence queue", data.evidence_items),
    )
    rows: List[RenderRow] = []
    for section, title, items in sections:
        for ordinal, item in enumerate(items, start=1):
            rows.append(
                RenderRow(
                    section=section,
                    section_title=title,
                    ordinal=ordinal,
                    item=item,
                    anchor=row_context_anchor(section, ordinal, item),
                    contract=item_contract(item, income_year),
                )
            )
    return rows


def row_context_anchor(section: str, ordinal: int, item: GuideItem) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", scalar_text(item.number).strip()).strip("-") or "item"
    return f"row-{section}-{ordinal}-{token}"


def row_anchor(item: GuideItem, row_index: int) -> str:
    return row_context_anchor("main", row_index, item)


def row_reference(row: RenderRow) -> str:
    supplied = scalar_text(row.item.number).strip()
    if supplied:
        return supplied
    prefixes = {
        "main": "Prepared item",
        "ai": "AI extraction",
        "abn": "ABN item",
        "bas": "BAS item",
        "missing": "Missing fact",
        "evidence": "Evidence item",
    }
    return f"{prefixes.get(row.section, 'Item')} {row.ordinal}"


def row_context_label(row: RenderRow) -> str:
    reference = row_reference(row)
    question = scalar_text(row.item.question).strip()
    area = scalar_text(row.item.ato_area).strip()
    detail = question or area or review_text(row.item)
    return f"{reference} - {detail}" if detail and detail != reference else reference


def source_row_context_label(row: RenderRow) -> str:
    return f"{row.section_title} #{row.ordinal}: {row_context_label(row)}"


def handoff_requires_review(handoff: Dict[str, Any]) -> bool:
    return scalar_text(handoff.get("kind")).strip() in {
        "accountant-handoff-only",
        "destination-requires-review",
    }


def row_review_required(row: RenderRow) -> bool:
    status = effective_status_kind(row.item)
    if status == "evidence":
        return False
    if status == "review" or handoff_requires_review(row.contract["handoff"]):
        return True
    return any(handoff_requires_review(fact["handoff"]) for fact in row.contract["facts"])


def row_review_handoff(row: RenderRow) -> Dict[str, Any]:
    candidates = [row.contract["handoff"]]
    candidates.extend(fact["handoff"] for fact in row.contract["facts"])
    for handoff in candidates:
        if handoff_requires_review(handoff):
            return handoff
    return row.contract["handoff"]


def unique_display_facts(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for fact in facts:
        marker = json.dumps(fact, sort_keys=True, ensure_ascii=False, default=scalar_text)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(fact)
    return unique


def fact_value_text(value: Any) -> str:
    if value is None:
        return "Not supplied"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return "\n".join(fact_value_text(item) for item in value) or "Not supplied"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=scalar_text)
    return str(value)


def handoff_signature(handoff: Dict[str, Any]) -> tuple[str, str]:
    return (
        scalar_text(handoff.get("kind")).strip(),
        scalar_text(handoff.get("next_action")).strip(),
    )


def render_row(item: GuideItem, row_index: int, income_year: str = DEFAULT_INCOME_YEAR) -> str:
    row = RenderRow(
        section="main",
        section_title="Prepared return items",
        ordinal=row_index,
        item=item,
        anchor=row_context_anchor("main", row_index, item),
        contract=item_contract(item, income_year),
    )
    return render_card(row, [])


def render_card(row: RenderRow, sources: List[SourceGroup]) -> str:
    item = row.item
    kind = effective_status_kind(item)
    facts = unique_display_facts(row.contract["facts"])
    fact_html = "".join(render_fact(fact, row.contract["handoff"]) for fact in facts)
    row_handoff = row.contract["handoff"]
    why = scalar_text(item.why_included).strip() or review_text(item)
    density = sum(len(fact_value_text(fact.get("value"))) for fact in facts)
    split_class = " allow-page-split" if len(facts) >= 9 or density > 1600 else ""
    return (
        f'<article class="handoff-card status-{esc(kind)}{split_class}" id="{row.anchor}" '
        f'data-anchor="{row.anchor}" data-status="{esc(kind)}" '
        f'data-review-required="{str(row_review_required(row)).lower()}" data-filter-row>'
        '<header class="card-header">'
        f'<div><span class="row-number">{esc(row_reference(row))}</span><p class="ato-area">{esc(item.ato_area)}</p>'
        f'<h3>{esc(item.question) or "Prepared item"}</h3></div>'
        f'<span class="status {status_class(kind)}">{esc(canonical_status(kind))}</span>'
        "</header>"
        '<div class="handoff-summary">'
        f'<section><h4>Next action</h4><p class="action-name">{esc(row_handoff["label"])}</p>'
        f'<p>{esc(row_handoff["next_action"])}</p></section>'
        f'<section><h4>Where it belongs</h4>{render_destination_summary(row_handoff["destination"])}</section>'
        "</div>"
        f'<ul class="fact-list">{fact_html}</ul>'
        f'<section class="why-block"><h4>Why this action</h4><p>{esc(why)}</p></section>'
        f'{render_source_summary(sources)}'
        "</article>"
    )


def render_fact(fact: Dict[str, Any], row_handoff: Dict[str, Any]) -> str:
    handoff = fact["handoff"]
    why = scalar_text(fact.get("why")).strip()
    detail = f'<p class="fact-why">{esc(why)}</p>' if why else ""
    destination = ""
    if handoff["destination"] != row_handoff["destination"]:
        destination = (
            '<div class="fact-destination">'
            f'{render_destination_summary(handoff["destination"], compact=True)}</div>'
        )
    action = ""
    if handoff_signature(handoff) != handoff_signature(row_handoff):
        action = (
            f'<p class="fact-action"><b>{esc(handoff["label"])}:</b> '
            f'{esc(handoff["next_action"])}</p>'
        )
    return (
        '<li class="fact-item">'
        '<div class="fact-line">'
        f'<span class="fact-label">{esc(fact["label"])}</span>'
        f'<span class="fact-value">{esc(fact_value_text(fact.get("value")))}</span>'
        "</div>"
        f"{destination}{action}{detail}</li>"
    )


def render_destination_summary(destination: Dict[str, Any], *, compact: bool = False) -> str:
    kind = scalar_text(destination.get("kind"))
    label = scalar_text(destination.get("label"), "Destination requires review.")
    if kind == "verified":
        visible_label = "Verified destination" if compact else label
        return (
            f'<p class="destination-label verified">{esc(visible_label)}</p>'
            f'<dl class="destination-channels"><dt>myTax</dt><dd>{esc(destination.get("mytax"))}</dd>'
            f'<dt>Paper return</dt><dd>{esc(destination.get("paper"))}</dd></dl>'
        )
    return f'<p class="destination-label {esc(kind or "requires-review")}">{esc(label)}</p>'


def supporting_source_entries(item: GuideItem) -> List[tuple[str, str, str]]:
    checked = scalar_text(item.checked_at).strip()
    entries: List[tuple[str, str, str]] = []
    for raw_url in item.source_urls:
        url = scalar_text(raw_url).strip()
        if url and (url, checked, "Supporting source") not in entries:
            entries.append((url, checked, "Supporting source"))
    return entries


def build_source_groups(rows: List[RenderRow]) -> tuple[List[SourceGroup], Dict[str, List[SourceGroup]]]:
    groups: List[SourceGroup] = []
    by_url: Dict[str, SourceGroup] = {}
    row_groups: Dict[str, List[SourceGroup]] = {row.anchor: [] for row in rows}
    for row in rows:
        records: List[tuple[str, str, str, str]] = [
            (url, checked, role, "")
            for url, checked, role in supporting_source_entries(row.item)
        ]
        destinations = [row.contract["handoff"]["destination"]]
        destinations.extend(
            fact["handoff"]["destination"]
            for fact in row.contract["facts"]
        )
        for destination in destinations:
            raw_sources = destination.get("sources")
            if not isinstance(raw_sources, list):
                continue
            for source in raw_sources:
                if not isinstance(source, dict):
                    continue
                url = scalar_text(source.get("url")).strip()
                if url:
                    records.append(
                        (
                            url,
                            scalar_text(source.get("checked_at")).strip(),
                            "Destination mapping",
                            scalar_text(source.get("title")).strip(),
                        )
                    )
        for url, checked, role, title in records:
            group = by_url.get(url)
            if group is None:
                source_number = len(groups) + 1
                group = SourceGroup(
                    anchor=f"source-{source_number}",
                    label=f"Source {source_number}",
                    url=url,
                )
                by_url[url] = group
                groups.append(group)
            if title and title not in group.titles:
                group.titles.append(title)
            if checked and checked not in group.checked_at:
                group.checked_at.append(checked)
            if role and role not in group.roles:
                group.roles.append(role)
            if all(existing.anchor != row.anchor for existing in group.rows):
                group.rows.append(row)
            if all(existing.anchor != group.anchor for existing in row_groups[row.anchor]):
                row_groups[row.anchor].append(group)
    return groups, row_groups


def render_source_summary(groups: List[SourceGroup]) -> str:
    if not groups:
        return (
            '<footer class="source-summary"><h4>Source context</h4>'
            '<p class="not-supplied">No supporting source supplied.</p></footer>'
        )
    links = ", ".join(
        f'<a class="source-ref" href="#{group.anchor}">{esc(group.label)}</a>'
        for group in groups
    )
    return (
        '<footer class="source-summary"><h4>Source context</h4>'
        f'<p>{len(groups)} source{"s" if len(groups) != 1 else ""}: {links}</p></footer>'
    )


def render_sections(rows: List[RenderRow], row_sources: Dict[str, List[SourceGroup]]) -> str:
    sections: List[str] = []
    section_order: List[str] = []
    for row in rows:
        if row.section not in section_order:
            section_order.append(row.section)
    for section in section_order:
        section_rows = [row for row in rows if row.section == section]
        if not section_rows:
            continue
        cards = "\n".join(
            render_card(row, row_sources.get(row.anchor, []))
            for row in section_rows
        )
        sections.append(
            f'<section class="guide-section" data-filter-section="{esc(section)}">'
            f'<h2>{esc(section_rows[0].section_title)}</h2>'
            f'<div class="card-list">{cards}</div></section>'
        )
    return "\n".join(sections)


def render_context_index(rows: List[RenderRow]) -> str:
    if not rows:
        return ""
    links = "".join(
        f'<li class="context-item" data-status="{esc(effective_status_kind(row.item))}" '
        f'data-review-required="{str(row_review_required(row)).lower()}">'
        f'<a class="context-link tab {tab_color(effective_tab_kind(row.item))}" href="#{row.anchor}">'
        f'<b>{esc(row_context_label(row))}</b></a></li>'
        for row in rows
    )
    return (
        '<details class="context-index"><summary>'
        f'Item index ({len(rows)})</summary><nav aria-label="Prepared item index"><ul>{links}</ul></nav></details>'
    )


def render_review_queue(rows: List[RenderRow]) -> str:
    review_rows = [row for row in rows if row_review_required(row)]
    if not review_rows:
        return ""

    def render_queue_group(title: str, group_rows: List[RenderRow]) -> str:
        if not group_rows:
            return ""
        items: List[str] = []
        for row in group_rows:
            kind = effective_status_kind(row.item)
            handoff = row_review_handoff(row)
            items.append(
                f'<li class="queue-item" data-status="{esc(kind)}" data-review-required="true" '
                f'data-action-kind="{esc(handoff["kind"])}">'
                '<div class="queue-item-head">'
                f'<a class="queue-link" href="#{row.anchor}">{esc(row_context_label(row))}</a>'
                f'<span class="status {status_class(kind)}">{esc(canonical_status(kind))}</span></div>'
                f'<p class="queue-action"><b>Next action:</b> '
                f'<span class="queue-action-name">{esc(handoff["label"])}.</span></p>'
                '<div class="queue-destination"><b>Destination:</b> '
                f'{render_destination_summary(handoff["destination"])}</div></li>'
            )
        return (
            f'<div class="queue-group"><h3>{esc(title)}</h3>'
            f'<ul class="review-list">{"".join(items)}</ul></div>'
        )

    accountant_rows = [
        row for row in review_rows if effective_status_kind(row.item) == "review"
    ]
    destination_rows = [
        row for row in review_rows if effective_status_kind(row.item) != "review"
    ]
    return (
        '<section class="callout review-callout"><h2>Review-required queue</h2>'
        '<p class="queue-intro">Each item keeps its original status and states the required handoff.</p>'
        f'{render_queue_group("Accountant review queue", accountant_rows)}'
        f'{render_queue_group("Destination review queue", destination_rows)}</section>'
    )


def render_source_appendix(groups: List[SourceGroup]) -> str:
    if not groups:
        return ""
    entries: List[str] = []
    for group in groups:
        title = " / ".join(group.titles) if group.titles else "ATO source"
        roles = " / ".join(group.roles)
        checked = "".join(
            f'<span class="checked-at">Checked {esc(value)}</span>'
            for value in group.checked_at
        )
        contexts = "".join(
            f'<li class="source-context" data-status="{esc(effective_status_kind(row.item))}" '
            f'data-review-required="{str(row_review_required(row)).lower()}">'
            f'<a href="#{row.anchor}">{esc(source_row_context_label(row))}</a></li>'
            for row in group.rows
        )
        entries.append(
            f'<li class="source-group" id="{group.anchor}"><b>'
            f'<span class="source-id">{esc(group.label)}</span> {esc(title)}</b>'
            f'<span class="source-kind">{esc(roles)}</span>'
            f'<span class="source-url">{esc(group.url)}</span>{checked}'
            f'<ul class="source-context-list">{contexts}</ul></li>'
        )
    return (
        '<details class="guide-section source-appendix" id="source-appendix" data-provenance-appendix>'
        f'<summary>Source/provenance appendix ({len(groups)})</summary>'
        f'<ul class="source-list">{"".join(entries)}</ul></details>'
    )


def render_taxonomy_legend() -> str:
    entries = "".join(
        f'<li><b>{esc(entry["label"])}</b><span>{esc(entry["description"])}</span></li>'
        for entry in taxmate_handoff.TAXONOMY.values()
    )
    return (
        '<details class="taxonomy-legend"><summary>Next-action legend</summary>'
        f'<ul class="taxonomy-list">{entries}</ul></details>'
    )


def tab_title(item: GuideItem, row_index: int) -> str:
    title = scalar_text(item.tab_title).strip()
    reference = scalar_text(item.number).strip() or f"Item {row_index}"
    return title or f"Row {reference} {short_status(effective_status_kind(item))}"


def review_text(item: GuideItem) -> str:
    return tab_text_value(item.tab_text).strip() or fallback_tab_text(item.number, effective_status_kind(item))


def tab_text_value(value: Any) -> str:
    if value is False:
        return ""
    text = scalar_text(value)
    return "" if text.strip().lower() == "false" else text


def effective_status_kind(item: GuideItem) -> str:
    return taxmate_handoff.effective_status_kind(
        item.status_kind,
        item.status,
        item.tab_kind,
    )


def effective_tab_kind(item: GuideItem) -> str:
    return effective_status_kind(item)


def context_label(item: GuideItem, row_index: int) -> str:
    question = scalar_text(item.question).strip()
    return question or tab_title(item, row_index) or fallback_tab_text(item.number, effective_status_kind(item))


def status_class(kind: str) -> str:
    if kind == "evidence":
        return "gap"
    if kind == "answer":
        return "used"
    if kind == "ato":
        return "label"
    if kind == "skipped":
        return "skipped"
    return "review-badge"


def tab_color(kind: str) -> str:
    if kind == "answer":
        return "green"
    if kind == "ato":
        return "blue"
    if kind == "evidence":
        return "yellow"
    if kind == "skipped":
        return "grey"
    return "red"


def assert_visible_boundaries(output: str) -> None:
    visible = strip_scripts(output)
    for phrase in FORBIDDEN_VISIBLE_PHRASES:
        if phrase.lower() in visible.lower():
            raise ValueError(f"forbidden guide phrase: {phrase}")
    required = ["Prepared by user", "Not an ATO form", "Not fileable", "Preparation aid only"]
    missing = [phrase for phrase in required if phrase not in visible]
    if missing:
        raise ValueError(f"missing guide boundary text: {', '.join(missing)}")
    if 'class="target-dot"' in output or "border-radius:50%" in output:
        raise ValueError("guide tabs must not use target circles")


def strip_scripts(output: str) -> str:
    lower = output.lower()
    start = lower.find("<script")
    if start < 0:
        return output
    end = lower.find("</script>", start)
    if end < 0:
        return output[:start]
    return output[:start] + output[end + len("</script>") :]


def scalar_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def esc(value: Any) -> str:
    return html.escape(scalar_text(value), quote=True)


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Self-prepared return handoff guide</title>
<style>
:root{{--bg:#eef2f6;--paper:#fff;--ink:#142033;--muted:#5d6b7e;--line:#d7dee8;--accent:#2457a6;--review:#a43b45;--review-bg:#fff4f4;--evidence:#8a5a00;--evidence-bg:#fff8df;--used:#17623b;--used-bg:#eefbf4;--label:#174e82;--label-bg:#eef6ff;--skipped:#566273;--skipped-bg:#f1f4f7}}
*{{box-sizing:border-box}}
html,body{{max-width:100%;margin:0}}
body{{background:var(--bg);color:var(--ink);font:15px/1.5 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow-wrap:anywhere}}
a{{color:#174f91;text-underline-offset:3px}}
button,a{{touch-action:manipulation}}
[hidden]{{display:none!important}}
.toolbar{{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:8px;padding:10px max(12px,calc((100vw - 960px)/2));background:#142033;color:#fff;box-shadow:0 2px 10px rgba(20,32,51,.2)}}
.toolbar>*{{min-width:0}}
.toolbar strong{{margin-right:auto}}
.filter-summary{{font-size:13px;color:#dce6f4}}
.toolbar button{{min-height:44px;border:1px solid #69768a;border-radius:8px;background:#243249;color:#fff;padding:8px 12px;font:inherit;font-size:13px;font-weight:700;cursor:pointer}}
.toolbar button[aria-pressed="true"]{{background:#fff;color:#142033;border-color:#fff}}
.book{{width:min(960px,calc(100% - 32px));margin:24px auto 56px}}
.page{{background:var(--paper);padding:clamp(22px,4vw,48px);box-shadow:0 12px 34px rgba(28,44,69,.12)}}
.header{{display:flex;justify-content:space-between;gap:24px;padding-bottom:18px;border-bottom:3px solid var(--ink)}}
.header h1{{max-width:680px;margin:0;font-size:clamp(26px,5vw,42px);line-height:1.08;letter-spacing:-.025em}}
.meta{{min-width:150px;text-align:right;color:var(--muted);font-size:14px}}
.notice{{margin:24px 0;padding:16px 18px;border:1px solid #b7c5d9;border-left:6px solid var(--accent);border-radius:8px;background:#f4f8fd}}
.notice b{{display:block;margin-bottom:4px}}
h2{{margin:34px 0 14px;font-size:23px;line-height:1.2}}
h3{{margin:3px 0 0;font-size:20px;line-height:1.28}}
h4{{margin:0 0 6px;font-size:13px;line-height:1.3;text-transform:uppercase;letter-spacing:.055em;color:#46566d}}
p{{margin:0 0 8px}}
.summary-note{{color:var(--muted)}}
.steps{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}}
.step{{padding:13px;border:1px solid var(--line);border-radius:9px;background:#fbfcfe}}
.step b{{display:block;margin-bottom:4px}}
.step p{{color:var(--muted);font-size:14px}}
.taxonomy-legend,.context-index{{margin:24px 0;border:1px solid var(--line);border-radius:10px;background:#f8fafc}}
.taxonomy-legend>summary,.context-index>summary,[data-provenance-appendix]>summary{{cursor:pointer;padding:14px 16px;font-weight:800}}
.taxonomy-list{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px 18px;margin:0;padding:0 20px 16px 38px}}
.taxonomy-list li span{{display:block;color:var(--muted);font-size:13px}}
.context-index ul{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0;padding:0 16px 16px;list-style:none}}
.context-link{{display:block;height:100%;padding:10px 11px;border-left:5px solid #77869a;border-radius:5px;background:#fff;color:var(--ink);text-decoration:none;box-shadow:0 1px 3px rgba(20,32,51,.08)}}
.context-link b,.tab-text{{display:block}}
.context-link b{{font-size:13px}}
.tab-text{{margin-top:2px;color:var(--muted);font-size:13px}}
.context-link.red{{border-color:#c34f59}}.context-link.yellow{{border-color:#d19a29}}.context-link.green{{border-color:#37a66d}}.context-link.blue{{border-color:#4e87c4}}.context-link.grey{{border-color:#8894a4}}
.guide-section{{margin-top:36px}}
.guide-section>h2{{padding-bottom:9px;border-bottom:1px solid var(--line)}}
.card-list{{display:grid;gap:15px}}
.handoff-card{{break-inside:avoid-page;page-break-inside:avoid;scroll-margin-top:78px;border:1px solid #cbd5e1;border-radius:11px;background:#fff;box-shadow:0 3px 12px rgba(20,32,51,.06);overflow:hidden}}
.handoff-card:target{{outline:3px solid rgba(36,87,166,.38);outline-offset:4px}}
.card-header{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:15px 17px;border-bottom:1px solid var(--line);background:#f8fafc}}
.row-number{{display:inline-block;margin-right:7px;border-radius:5px;background:#e5ebf2;padding:3px 7px;font-size:13px;font-weight:800}}
.ato-area{{display:inline;color:var(--muted);font-size:14px}}
.status{{flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;max-width:180px;min-height:31px;border-radius:999px;padding:6px 10px;text-align:center;font-size:12px;font-weight:800;line-height:1.2}}
.gap{{background:var(--evidence-bg);color:var(--evidence)}}.review-badge{{background:#ffe2e4;color:#8e2933}}.used{{background:var(--used-bg);color:var(--used)}}.label{{background:var(--label-bg);color:var(--label)}}.skipped{{background:var(--skipped-bg);color:var(--skipped)}}
.handoff-summary{{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--line)}}
.handoff-summary section{{padding:14px 17px}}
.handoff-summary section+section{{border-left:1px solid var(--line)}}
.action-name{{font-size:17px;font-weight:800;color:#183b6b}}
.destination-label{{font-weight:750}}
.destination-label.verified{{color:var(--used)}}.destination-label.requires-review{{color:var(--review)}}.destination-label.not-entered{{color:var(--skipped)}}
.destination-channels{{display:grid;grid-template-columns:82px minmax(0,1fr);gap:4px 9px;margin:7px 0 0}}
.destination-channels dt{{font-weight:800}}.destination-channels dd{{min-width:0;margin:0;overflow-wrap:anywhere}}
.fact-list{{margin:0;padding:13px 17px 8px 38px;border-bottom:1px solid var(--line)}}
.fact-item{{padding:3px 0 10px 2px}}
.fact-line{{display:grid;grid-template-columns:minmax(145px,32%) minmax(0,1fr);gap:12px}}
.fact-label{{font-weight:800}}
.fact-value{{min-width:0;white-space:pre-wrap;overflow-wrap:anywhere}}
.fact-destination{{margin-top:4px;color:var(--muted);font-size:13px}}
.fact-destination .destination-label{{margin:0}}
.fact-destination .destination-channels{{font-size:13px}}
.fact-action,.fact-why{{margin:4px 0 0;color:var(--muted);font-size:13px}}
.fact-action b{{color:#34445a}}
.why-block,.source-summary{{padding:13px 17px;border-bottom:1px solid var(--line)}}
.source-summary{{border-bottom:0;background:#fbfcfe}}
.source-list,.review-list{{margin:0;padding-left:20px}}
.callout{{margin-top:34px;padding:16px 18px;border:1px solid #efb7bb;border-left:6px solid var(--review);border-radius:9px;background:var(--review-bg)}}
.callout h2{{margin:0 0 8px;font-size:20px}}
.queue-intro{{color:var(--muted)}}
.queue-group+ .queue-group{{margin-top:18px}}
.queue-group h3{{margin:12px 0 8px;font-size:16px}}
.review-list{{display:grid;gap:8px;padding:0;list-style:none}}
.queue-item{{padding:11px 12px;border:1px solid #e2aeb3;border-radius:8px;background:#fff}}
.queue-item-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}}
.queue-link{{font-weight:800}}
.queue-action{{margin-top:7px}}
.queue-action-name{{font-weight:800}}
.queue-destination{{color:var(--muted);font-size:13px}}
.queue-destination>.destination-label{{display:inline;margin-left:4px}}
.queue-destination .destination-channels{{margin-left:0}}
{source_appendix_screen_css}
.source-list{{padding:0 18px 16px 38px}}
.source-group{{margin-bottom:14px;scroll-margin-top:78px;break-inside:avoid}}
.source-group:target{{outline:3px solid rgba(36,87,166,.38);outline-offset:3px}}
.source-id{{display:inline-block;margin-right:4px;color:var(--accent)}}
.source-kind,.source-url,.checked-at{{display:block}}
.source-kind{{color:var(--muted);font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.04em}}
.source-url{{color:#42536a;font-size:13px;overflow-wrap:anywhere;word-break:break-word}}
.checked-at{{color:#617086;font-size:12px;font-weight:700}}
.source-context-list{{margin-top:5px;padding-left:20px}}
.not-supplied{{color:var(--muted)}}
.footer{{margin-top:40px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}}
@media screen and (max-width:520px){{
  .toolbar{{position:static;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:10px}}
  .toolbar strong,.filter-summary{{grid-column:1/-1}}
  .toolbar button{{min-width:0;width:100%;min-height:44px;padding:7px 4px;font-size:12px;line-height:1.2}}
  .book{{width:100%;margin:0}}
  .page{{padding:18px 12px;box-shadow:none}}
  .header{{display:block}}.header>*,.steps>*,.handoff-summary>*,.queue-item>*{{min-width:0}}.meta{{min-width:0;margin-top:10px;text-align:left}}
  .steps,.taxonomy-list,.context-index ul{{grid-template-columns:1fr}}
  .handoff-summary{{grid-template-columns:1fr}}
  .handoff-summary section+section{{border-left:0;border-top:1px solid var(--line)}}
  .card-header{{display:block;padding:14px}}
  .card-header .status{{margin-top:10px}}
  .row-number,.ato-area{{display:block;width:max-content;max-width:100%}}
  .ato-area{{margin-top:5px}}
  .fact-list{{padding:12px 14px 7px 32px}}
  .fact-line{{grid-template-columns:1fr;gap:2px}}
  .fact-value{{min-width:0;max-width:100%;overflow-wrap:anywhere}}
  .why-block,.source-summary{{padding:12px 14px}}
  .queue-item-head{{display:block}}
  .queue-item-head .status{{margin-top:8px}}
  .destination-channels{{grid-template-columns:1fr}}
  .destination-channels dd{{min-width:0;margin-bottom:4px;overflow-wrap:anywhere}}
}}
@media print{{
  @page{{margin:13mm}}
  *{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
  body{{background:#fff;font-size:10.5pt}}
  .toolbar,.context-index{{display:none!important}}
  .book{{width:100%;margin:0}}.page{{padding:0;box-shadow:none}}
  .handoff-card{{box-shadow:none;break-inside:avoid-page;page-break-inside:avoid}}
  .handoff-card.allow-page-split{{break-inside:auto;page-break-inside:auto}}
  .fact-item{{break-inside:avoid;page-break-inside:avoid}}
  .queue-item{{break-inside:avoid;page-break-inside:avoid}}
  .card-header,.handoff-summary,.why-block,.source-summary{{break-inside:avoid}}
  .guide-section>h2{{break-after:avoid-page}}
  .guide-section{{margin-top:22px}}
  {source_appendix_print_css}
  details.taxonomy-legend:not([open]) > :not(summary){{display:block!important}}
  details>summary{{list-style:none}}
  a{{color:inherit;text-decoration:none}}
}}
</style>
</head>
<body>
<div class="toolbar" role="group" aria-label="Worksheet filters"><strong>Self-prepared HTML guide</strong><span class="filter-summary" aria-live="polite"></span><button type="button" data-filter="all" aria-controls="guide-content" aria-pressed="true">Show all</button><button type="button" data-filter="review" aria-controls="guide-content" aria-pressed="false">Review required</button><button type="button" data-filter="evidence" aria-controls="guide-content" aria-pressed="false">Evidence required</button></div>
<main class="book" id="guide-content"><article class="page" id="taxmate-guide-worksheet">
<header class="header"><h1>Return fields and next actions</h1><div class="meta">Income year {income_year}<br>Prepared by user<br>Generated {generated_date}<br>Not an ATO form</div></header>
<div class="notice" id="prep-boundary"><b>Preparation aid only. Manual review required.</b>This custom guide is not tax, legal, financial, accounting, BAS-agent, or registered-tax-agent advice. It is not an official ATO form and is not fileable. Only reviewed facts with an exact verified destination may be entered manually in myTax or a paper return. Give every Accountant review item to a qualified professional before entry.</div>
<section><h2>How to use this guide</h2><div class="steps"><div class="step"><b>1. Check the facts</b><p>Compare each bullet with the record or answer you supplied.</p></div><div class="step"><b>2. Follow the next action</b><p>Use the exact destination only when the card identifies a verified mapping.</p></div><div class="step"><b>3. Resolve review items</b><p>Resolve destination-review items and send Accountant review items for professional review before entry.</p></div></div></section>
<section><h2>Interview summary</h2><p class="summary-note">{summary_note}</p></section>
{taxonomy_legend}
{context_index}
{guide_sections}
{review_queue}
{source_appendix}
<footer class="footer">Self-prepared custom guide. Not an ATO form. Not fileable. Preparation aid only.</footer>
</article></main>
<script>
const filterButtons=[...document.querySelectorAll('[data-filter]')];
const filterSummary=document.querySelector('.filter-summary');
let activeFilter='all';
let filterBeforePrint='all';
const detailsBeforePrint=new Map();
function matchesFilter(element,filter){{
  if(filter==='all'){{return true;}}
  if(filter==='review'){{return element.dataset.reviewRequired==='true';}}
  return element.dataset.status===filter;
}}
function applyFilter(filter){{
  activeFilter=filter;
  const cards=[...document.querySelectorAll('.handoff-card[data-status]')];
  for(const card of cards){{card.hidden=!matchesFilter(card,filter);}}
  for(const item of document.querySelectorAll('.context-index [data-status]')){{item.hidden=!matchesFilter(item,filter);}}
  for(const item of document.querySelectorAll('.review-list [data-status]')){{item.hidden=!matchesFilter(item,filter);}}
  for(const item of document.querySelectorAll('.source-context[data-status]')){{item.hidden=!matchesFilter(item,filter);}}
  for(const section of document.querySelectorAll('[data-filter-section]')){{section.hidden=![...section.querySelectorAll('.handoff-card')].some(card=>!card.hidden);}}
  const reviewQueue=document.querySelector('.review-callout');
  if(reviewQueue){{reviewQueue.hidden=![...reviewQueue.querySelectorAll('[data-status]')].some(item=>!item.hidden);}}
  for(const group of document.querySelectorAll('.source-group')){{group.hidden=![...group.querySelectorAll('.source-context')].some(item=>!item.hidden);}}
  const appendix=document.querySelector('[data-provenance-appendix]');
  if(appendix){{appendix.hidden=![...appendix.querySelectorAll('.source-group')].some(group=>!group.hidden);}}
  const visible=cards.filter(card=>!card.hidden).length;
  if(filterSummary){{filterSummary.textContent=`${{visible}} of ${{cards.length}} items`;}}
  for(const button of filterButtons){{button.setAttribute('aria-pressed',String(button.dataset.filter===filter));}}
}}
function revealHashTarget(){{
  const raw=window.location.hash.slice(1);
  if(!raw){{return;}}
  let identifier=raw;
  try{{identifier=decodeURIComponent(raw);}}catch(error){{identifier=raw;}}
  const target=document.getElementById(identifier);
  if(!target){{return;}}
  const card=target.classList.contains('handoff-card')?target:target.closest('.handoff-card');
  if(card&&card.hidden){{
    const targetFilter=card.dataset.status==='evidence'
      ?'evidence'
      :(card.dataset.reviewRequired==='true'?'review':'all');
    applyFilter(targetFilter);
  }}
  const group=target.classList.contains('source-group')?target:target.closest('.source-group');
  if(group&&group.hidden){{applyFilter('all');}}
  const details=target.closest('details');
  if(details){{details.open=true;}}
  if(group){{group.scrollIntoView({{block:'center'}});}}
}}
for(const button of filterButtons){{button.addEventListener('click',function(){{applyFilter(button.dataset.filter);}});}}
window.addEventListener('hashchange',revealHashTarget);
window.addEventListener('beforeprint',function(){{
  filterBeforePrint=activeFilter;
  applyFilter('all');
  for(const details of document.querySelectorAll('details')){{detailsBeforePrint.set(details,details.open);details.open=true;}}
}});
window.addEventListener('afterprint',function(){{
  for(const [details,wasOpen] of detailsBeforePrint){{details.open=wasOpen;}}
  detailsBeforePrint.clear();
  applyFilter(filterBeforePrint);
}});
applyFilter('all');
revealHashTarget();
</script>
</body>
</html>
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="./scripts/taxmate taxpack", description="TaxMate Australia taxpack outputs.")
    sub = parser.add_subparsers(dest="command")
    guide = sub.add_parser("guide-html", help="Render the self-prepared ATO-aligned HTML guide.")
    guide.add_argument("--input", default="", help="JSON guide input. Omit for the built-in sample.")
    guide.add_argument("--output", required=True, help="HTML output path.")
    sample = sub.add_parser("sample-json", help="Write sample guide input JSON.")
    sample.add_argument("--output", required=True, help="JSON output path.")
    return parser


def write_text(path: str, text: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(text, encoding="utf-8")


def main(argv: List[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "sample-json":
        write_text(args.output, json.dumps(sample_payload(), indent=2) + "\n")
        return 0
    if args.command == "guide-html":
        try:
            data = load_guide_data(args.input or None)
            write_text(args.output, render_html(data))
        except Exception as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
