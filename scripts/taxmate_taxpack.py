#!/usr/bin/env python3
"""TaxMate Australia taxpack guide renderer."""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_INCOME_YEAR = "2025-26"
FORBIDDEN_VISIBLE_PHRASES = [
    "Prepared by " + "TaxMate",
    "lodgment-" + "ready",
    "file with the " + "ATO",
    "submit this guide",
    "submit this PDF",
]
ANSWER_STATUS_KEYS = {"answer", "answer-used", "used", "green"}
ATO_STATUS_KEYS = {"ato", "ato-label", "label", "blue"}
EVIDENCE_STATUS_KEYS = {"evidence", "evidence-needed", "missing-evidence", "yellow"}
REVIEW_STATUS_KEYS = {"review", "accountant-review", "red"}
SKIPPED_STATUS_KEYS = {
    "skipped",
    "skip",
    "n/a",
    "na",
    "n-a",
    "n/a-skipped",
    "not-applicable",
    "grey",
    "gray",
}


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


def sample_payload() -> Dict[str, Any]:
    return {
        "income_year": DEFAULT_INCOME_YEAR,
        "summary_note": "Tabs point directly to the exact item they explain. Hide tabs when you want a clean copy.",
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
            },
        ],
    }


def load_guide_data(path: Optional[str]) -> GuideData:
    payload = sample_payload() if not path else read_json(path)
    return load_guide_payload(payload)


def load_guide_payload(payload: Dict[str, Any]) -> GuideData:
    items = [guide_item(raw) for raw in payload.get("items", [])]
    if not items:
        raise ValueError("guide input must include at least one item")
    generated_date = text_value(payload, "generated_date", default_generated_date())
    return GuideData(
        income_year=text_value(payload, "income_year", DEFAULT_INCOME_YEAR),
        generated_date=generated_date,
        summary_note=text_value(payload, "summary_note", sample_payload()["summary_note"]),
        items=items,
        extracted_values=extracted_values(payload.get("extracted_values", [])),
        abn_items=section_items(payload, "abn_items"),
        bas_items=section_items(payload, "bas_items"),
        missing_facts=section_items(payload, "missing_facts"),
        evidence_items=section_items(payload, "evidence_items"),
    )


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("guide input must be a JSON object")
    return payload


def section_items(payload: Dict[str, Any], key: str) -> List[GuideItem]:
    raw_items = payload.get(key, [])
    if not isinstance(raw_items, list):
        return []
    return [guide_item(raw) for raw in raw_items if isinstance(raw, dict)]


def extracted_values(raw_items: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    return [raw for raw in raw_items if isinstance(raw, dict)]


def guide_item(raw: Dict[str, Any]) -> GuideItem:
    if not isinstance(raw, dict):
        raise ValueError("guide items must be JSON objects")
    number = text_value(raw, "number").strip()
    if not number:
        raise ValueError("guide item missing number")
    status_kind = item_status_kind(raw)
    tab_kind = item_tab_kind(raw, status_kind)
    tab_title = first_text(raw, ["tab_title"], f"Row {number} {short_status(status_kind)}")
    tab_text = first_text(raw, ["tab_text", "why_included"], fallback_tab_text(number, status_kind))
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
    )


def item_status_kind(raw: Dict[str, Any]) -> str:
    status_kind = known_kind(raw.get("status_kind"))
    status = known_kind(raw.get("status"))
    tab_kind = known_kind(raw.get("tab_kind"))
    if status_kind == "review" or status == "review" or tab_kind == "review":
        return "review"
    return status_kind or status or "review"


def item_tab_kind(raw: Dict[str, Any], status_kind: str) -> str:
    tab_value = text_value(raw, "tab_kind", status_kind)
    tab_kind = normal_kind(tab_value)
    if status_kind == "review":
        return "review"
    return tab_kind


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


def normal_kind(value: Any) -> str:
    return known_kind(value) or "review"


def known_kind(value: Any) -> Optional[str]:
    key = scalar_text(value).strip().lower().replace("_", "-").replace(" ", "-")
    if key in ANSWER_STATUS_KEYS:
        return "answer"
    if key in ATO_STATUS_KEYS:
        return "ato"
    if key in EVIDENCE_STATUS_KEYS:
        return "evidence"
    if key in REVIEW_STATUS_KEYS or is_review_like_key(key):
        return "review"
    if key in SKIPPED_STATUS_KEYS:
        return "skipped"
    return None


def is_review_like_key(key: str) -> bool:
    parts = {part for part in key.split("-") if part}
    if "accountant" in parts:
        return True
    if "review" in parts and parts.intersection({"required", "requires", "need", "needs", "needed", "must"}):
        return True
    if "review" in parts and "agent" in parts:
        return True
    return False


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
    text = scalar_text(value)
    key = text.strip().lower().replace("_", " ")
    slug = key.replace(" ", "-")
    if "evidence" in key:
        return "Evidence"
    if "review" in key or "accountant" in key:
        return "Accountant review"
    if slug in SKIPPED_STATUS_KEYS:
        return "N/A skipped"
    if key in {"answer", "answer used", "used"}:
        return "Used"
    return text.strip() or "Review"


def default_generated_date() -> str:
    return datetime.now(timezone.utc).strftime("%d %b %Y").lstrip("0")


def render_html(data: GuideData) -> str:
    indexed_items = list(enumerate(data.items, start=1))
    rows = "\n".join(render_row(item, row_index) for row_index, item in indexed_items)
    tab_items = rendered_tab_items(data)
    row_tabs = "\n".join(render_item_tab(item, row_index) for item, row_index in tab_items)
    review_items = [
        review_text(item)
        for item, _row_index in tab_items
        if effective_status_kind(item) == "review" or effective_tab_kind(item) == "review"
    ]
    review_queue = "; ".join(review_items) if review_items else "No review-only items supplied."
    output = HTML_TEMPLATE.format(
        income_year=esc(data.income_year),
        generated_date=esc(data.generated_date),
        summary_note=esc(data.summary_note),
        extraction_table=render_extraction_table(data.extracted_values),
        abn_section=render_section("ABN prep section", data.abn_items, 200),
        bas_section=render_section("BAS worksheet", data.bas_items, 300),
        missing_queue=render_queue("Missing facts queue", data.missing_facts),
        evidence_queue=render_queue("Evidence queue", data.evidence_items),
        source_appendix=render_source_appendix(all_guide_items(data)) if has_extended_pack(data) else "",
        rows=rows,
        row_tabs=row_tabs,
        review_queue=esc(review_queue),
    )
    assert_visible_boundaries(output)
    return output


def render_row(item: GuideItem, row_index: int) -> str:
    anchor = row_anchor(item, row_index)
    item_status_kind = effective_status_kind(item)
    return (
        "<tr>"
        f"<td>{esc(item.number)}</td>"
        f"<td>{esc(item.ato_area)}</td>"
        f"<td>{esc(item.question)}</td>"
        f"<td>{esc(item.answer)}</td>"
        f"<td>{esc(item.why_included)}</td>"
        f"<td class=\"provenance\">{render_provenance(item)}</td>"
        f'<td data-anchor="{anchor}"><span class="status {status_class(item_status_kind)}">{esc(canonical_status(item_status_kind))}</span></td>'
        "</tr>"
    )


def render_section(title: str, items: List[GuideItem], offset: int) -> str:
    if not items:
        return f"<h2>{esc(title)}</h2><p class=\"summary-note\">No rows supplied.</p>"
    rows = "\n".join(render_row(item, offset + index) for index, item in enumerate(items, start=1))
    return (
        f"<h2>{esc(title)}</h2>"
        '<table class="table section-table"><thead><tr><th></th><th>ATO area</th><th>Question</th>'
        "<th>Answer/value</th><th>Why included</th><th>Source</th><th>Status</th></tr></thead><tbody>"
        f"{rows}</tbody></table>"
    )


def render_queue(title: str, items: List[GuideItem]) -> str:
    if not items:
        return f"<h2>{esc(title)}</h2><p class=\"summary-note\">No items supplied.</p>"
    entries = "".join(f"<li>{esc(queue_item_text(item))}</li>" for item in items)
    return f"<h2>{esc(title)}</h2><ul class=\"queue-list\">{entries}</ul>"


def queue_item_text(item: GuideItem) -> str:
    question = scalar_text(item.question).strip()
    answer = scalar_text(item.answer).strip()
    status = canonical_status(effective_status_kind(item))
    if question and answer:
        return f"{question}: {answer} ({status})"
    if question:
        return f"{question} ({status})"
    if answer:
        return f"{answer} ({status})"
    return fallback_tab_text(item.number, effective_status_kind(item))


def render_extraction_table(values: List[Dict[str, Any]]) -> str:
    if not values:
        return '<h2>AI extraction confirmation table</h2><p class="summary-note">No AI-extracted values supplied.</p>'
    rows: List[str] = []
    for raw in values:
        kind = normal_kind(raw.get("status"))
        status = canonical_status(kind)
        rows.append(
            "<tr>"
            f"<td>{esc(raw.get('number', 'AI'))}</td>"
            f"<td>{esc(raw.get('document'))}</td>"
            f"<td>{esc(raw.get('page'))}</td>"
            f"<td>{esc(raw.get('field'))}</td>"
            f"<td>{esc(raw.get('value'))}</td>"
            f"<td>{esc(raw.get('confidence'))}</td>"
            f"<td>{esc(raw.get('target_label'))}</td>"
            f"<td><span class=\"status {status_class(kind)}\">{esc(status)}</span></td>"
            "</tr>"
        )
    return (
        "<h2>AI extraction confirmation table</h2>"
        '<table class="table extraction-table"><thead><tr><th></th><th>Document</th><th>Page</th>'
        "<th>Field</th><th>Extracted value</th><th>Confidence</th><th>Target label</th><th>Status</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def render_source_appendix(items: List[GuideItem]) -> str:
    urls: List[str] = []
    for item in items:
        for url in item.source_urls:
            text = scalar_text(url).strip()
            if text and text not in urls:
                urls.append(text)
    if not urls:
        return '<h2>Source/provenance appendix</h2><p class="summary-note">No source URLs supplied.</p>'
    rows = "".join(f"<li><span class=\"source-url\">{esc(url)}</span></li>" for url in urls)
    return f"<h2>Source/provenance appendix</h2><ul class=\"source-list\">{rows}</ul>"


def rendered_tab_items(data: GuideData) -> List[tuple[GuideItem, int]]:
    items = [(item, index) for index, item in enumerate(data.items, start=1)]
    items.extend((item, 200 + index) for index, item in enumerate(data.abn_items, start=1))
    items.extend((item, 300 + index) for index, item in enumerate(data.bas_items, start=1))
    items.extend((item, 400 + index) for index, item in enumerate(data.missing_facts, start=1))
    items.extend((item, 500 + index) for index, item in enumerate(data.evidence_items, start=1))
    return items


def all_guide_items(data: GuideData) -> List[GuideItem]:
    return data.items + data.abn_items + data.bas_items + data.missing_facts + data.evidence_items


def has_extended_pack(data: GuideData) -> bool:
    return bool(data.extracted_values or data.abn_items or data.bas_items or data.missing_facts or data.evidence_items)


def render_provenance(item: GuideItem) -> str:
    parts = [f'<span class="source-url">{esc(url)}</span>' for url in item.source_urls]
    checked_at = scalar_text(item.checked_at).strip()
    if checked_at:
        parts.append(f'<span class="checked-at">Checked {esc(checked_at)}</span>')
    return "<br>".join(parts) if parts else "-"


def render_item_tab(item: GuideItem, row_index: int) -> str:
    item_tab_kind = effective_tab_kind(item)
    color = tab_color(item_tab_kind)
    extra = " review" if item_tab_kind == "review" else ""
    extra += " evidence" if item_tab_kind in {"evidence", "answer"} else ""
    return (
        f'<div class="tab {color}{extra}" data-target="{row_anchor(item, row_index)}">'
        f"<b>{esc(item.tab_title)}</b>"
        f"<p>{esc(review_text(item))}</p>"
        "</div>"
    )


def review_text(item: GuideItem) -> str:
    return scalar_text(item.tab_text).strip() or fallback_tab_text(item.number, effective_status_kind(item))


def effective_status_kind(item: GuideItem) -> str:
    status_kind = normal_kind(item.status_kind)
    status = normal_kind(item.status)
    tab_kind = normal_kind(item.tab_kind)
    if status_kind == "review" or status == "review" or tab_kind == "review":
        return "review"
    return status_kind


def effective_tab_kind(item: GuideItem) -> str:
    status_kind = effective_status_kind(item)
    if status_kind == "review":
        return "review"
    return normal_kind(item.tab_kind or status_kind)


def row_anchor(item: GuideItem, row_index: int) -> str:
    return f"row-{row_index}-{html.escape(scalar_text(item.number), quote=True)}"


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
<title>Self-prepared ATO-aligned Guide</title>
<style>
:root{{--bg:#e9eef4;--ink:#111827;--muted:#64748b;--line:#d9e0e8;--red:#ef6b73;--blue:#6495ed;--green:#53c987;--yellow:#f2b84b;--grey:#94a3b8}}*{{box-sizing:border-box}}html,body{{overflow-x:hidden}}body{{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}.toolbar{{padding:12px 18px;background:#111827;color:#fff;display:flex;gap:12px;align-items:center;box-shadow:0 2px 8px rgba(0,0,0,.18);position:sticky;top:0;z-index:20}}.toolbar strong{{font-size:14px}}.toolbar span{{font-size:12px;color:#cbd5e1;margin-right:auto}}.toolbar button{{border:1px solid #475569;background:#1f2937;color:#fff;border-radius:6px;padding:6px 10px;font-size:11px;font-weight:700;cursor:pointer}}.toolbar button:hover{{background:#374151}}body.hide-tabs .tab{{display:none}}body.only-review .tab:not(.review){{opacity:.18;filter:grayscale(1)}}body.only-evidence .tab:not(.evidence){{opacity:.18;filter:grayscale(1)}}.book{{width:min(1120px,calc(100vw - 24px));margin:18px auto 50px;display:grid;gap:30px}}.spread{{display:grid;grid-template-columns:minmax(0,74%) minmax(190px,26%);align-items:start;position:relative;filter:drop-shadow(0 10px 24px rgba(15,23,42,.16))}}.page{{background:#fff;min-height:1088px;padding:clamp(24px,3.4vw,42px) clamp(24px,3.5vw,48px) 36px clamp(28px,3.8vw,52px);position:relative;overflow:visible}}.page.long{{min-height:1320px}}.side{{min-height:1088px;position:relative;background:transparent;overflow:visible}}.watermark{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:78px;font-weight:900;letter-spacing:.08em;transform:rotate(-28deg);color:rgba(15,23,42,.045);pointer-events:none}}.header{{display:flex;justify-content:space-between;gap:20px;border-bottom:3px solid #111827;padding-bottom:14px;margin-bottom:24px}}.header h1{{margin:0;font-size:clamp(22px,2.8vw,29px);line-height:1.12}}.meta{{text-align:right;color:var(--muted);font-size:clamp(9px,1vw,12px);line-height:1.55}}.notice{{border:2px solid #111827;background:#f8fafc;padding:14px 16px;margin:12px 0 24px;font-size:clamp(10.5px,1.15vw,13px);line-height:1.45;position:relative}}h2{{font-size:clamp(15px,1.8vw,18px);margin:24px 0 10px;border-bottom:1px solid var(--line);padding-bottom:8px}}.steps{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;position:relative}}.step{{border:1px solid var(--line);border-radius:6px;padding:12px;min-height:84px;position:relative}}.step b{{font-size:12px}}.step p{{font-size:11px;color:var(--muted);line-height:1.35}}.legend{{display:flex;gap:8px;flex-wrap:wrap}}.legend span{{font-size:10px;padding:5px 8px;border-radius:4px;background:#f8fafc;border-left:7px solid var(--line)}}.legend .b{{border-color:var(--blue)}}.legend .g{{border-color:var(--green)}}.legend .y{{border-color:var(--yellow)}}.legend .r{{border-color:var(--red)}}.legend .x{{border-color:var(--grey)}}.summary-note,.queue-list,.source-list{{font-size:clamp(9px,1vw,12px);color:#64748b;line-height:1.5;position:relative}}.queue-list,.source-list{{padding-left:18px;color:#334155}}.table{{width:100%;max-width:100%;border-collapse:collapse;font-size:9px;table-layout:fixed;margin-bottom:14px}}.table th{{background:#f1f5f9;color:#475569;text-transform:uppercase;font-size:9px;text-align:left;border:1px solid var(--line);padding:8px}}.table td{{border:1px solid var(--line);padding:8px;vertical-align:top;line-height:1.32;position:relative;height:104px;overflow-wrap:normal;word-break:normal}}.table th:nth-child(1),.table td:nth-child(1){{width:5%;text-align:center}}.table th:nth-child(2){{width:14%}}.table th:nth-child(3){{width:13%}}.table th:nth-child(4){{width:17%}}.table th:nth-child(5){{width:22%}}.table th:nth-child(6){{width:17%}}.table th:nth-child(7){{width:12%}}.extraction-table th:nth-child(2),.extraction-table td:nth-child(2){{width:16%}}.extraction-table th:nth-child(8),.extraction-table td:nth-child(8){{width:12%}}.provenance{{font-size:7.5px;color:#475569;line-height:1.28;overflow-wrap:anywhere!important;word-break:break-word!important}}.source-url{{display:block;overflow-wrap:anywhere}}.checked-at{{display:block;margin-top:4px;color:#64748b;font-weight:700}}.status{{display:inline-block;min-width:86px;padding:4px 5px;border-radius:5px;font-weight:800;font-size:7.5px;white-space:normal;word-break:normal;overflow-wrap:normal;text-align:center;line-height:1.15}}.gap{{background:#fde68a}}.review-badge{{background:#fecaca}}.used{{background:#bbf7d0}}.label{{background:#dbeafe}}.skipped{{background:#e2e8f0}}.callout{{margin-top:20px;border-left:5px solid var(--red);background:#fff1f2;padding:10px 12px;font-size:12px;line-height:1.45;position:relative}}.footer{{position:absolute;left:52px;right:48px;bottom:22px;border-top:1px solid var(--line);padding-top:8px;color:#94a3b8;font-size:10px;display:flex;justify-content:space-between}}.tab{{position:absolute;left:12px;width:calc(100% - 18px);min-height:66px;border-radius:0 12px 12px 0;padding:10px 12px 10px 16px;background:#fff;box-shadow:0 7px 16px rgba(15,23,42,.12);border-left:10px solid currentColor;color:#111827;z-index:5;cursor:pointer}}.tab:before{{content:"";position:absolute;left:-64px;top:50%;width:64px;height:3px;background:currentColor;transform:translateY(-50%)}}.tab:after{{content:"";position:absolute;left:-69px;top:50%;width:9px;height:9px;border-left:3px solid currentColor;border-bottom:3px solid currentColor;transform:translateY(-50%) rotate(45deg);background:transparent}}.tab b{{display:block;font-size:clamp(8px,.85vw,10px);text-transform:uppercase;letter-spacing:.04em;margin-bottom:5px;color:#0f172a}}.tab p{{margin:0;font-size:clamp(9px,.9vw,10.5px);line-height:1.3}}.tab.red{{color:#ef5b63;background:#fff0f1}}.tab.blue{{color:#3f82f6;background:#eef5ff}}.tab.green{{color:#24b96d;background:#effbf4}}.tab.yellow{{color:#df8d00;background:#fff7dc}}.tab.grey{{color:#94a3b8;background:#f8fafc}}.spotlight-target{{outline:2px solid rgba(59,130,246,.45)!important;outline-offset:5px;background:rgba(96,165,250,.08)!important;box-shadow:0 0 0 7px rgba(96,165,250,.08)!important;transition:box-shadow .15s ease,outline-color .15s ease}}.tab.active{{box-shadow:0 0 0 3px rgba(17,24,39,.16),0 10px 22px rgba(15,23,42,.22)}}@media print{{.toolbar{{display:none}}body{{background:#fff}}.book{{width:100%;margin:0;gap:0}}.spread{{filter:none;page-break-after:always;grid-template-columns:74% 26%}}.page,.side{{min-height:100vh}}.page.long{{min-height:100vh}}.tab{{box-shadow:none}}a{{color:#111827;text-decoration:none}}}}
</style>
</head>
<body>
<div class="toolbar"><strong>Self-prepared guide PDF</strong><span>Preview controls are not part of the PDF.</span><button data-mode="all">Show all tabs</button><button data-mode="hide">Hide tabs</button><button data-mode="review">Review only</button><button data-mode="evidence">Evidence only</button></div>
<main class="book">
<section class="spread">
<article class="page">
<div class="watermark">DRAFT GUIDE</div>
<div class="header"><h1>ATO-aligned manual tax guide<br>{income_year}</h1><div class="meta">Prepared by user<br>Generated {generated_date}<br>Not an ATO form</div></div>
<div class="notice" data-anchor="prep-boundary"><b>Preparation aid only. Manual copy only.</b> This self-prepared custom HTML pack can be printed or saved as PDF. It helps you copy reviewed answers into myTax, a paper ATO form, or an accountant handoff. It is not tax, legal, financial, accounting, BAS-agent, or registered-tax-agent advice. It is not an official ATO PDF and cannot be filed, uploaded, mailed, or submitted as a tax return.</div>
<h2>How to use this guide</h2>
<div class="steps" data-anchor="how-to-row"><div class="step"><b>1. Review answers</b><p>Check each value against your records.</p></div><div class="step"><b>2. Follow ATO labels</b><p>Use ATO label references to find where each answer belongs.</p></div><div class="step"><b>3. Clear red flags</b><p>Ask an accountant about every Accountant review item.</p></div><div class="step"><b>4. Copy manually</b><p>Enter reviewed answers into myTax or paper form.</p></div></div>
<h2>Sticky tab legend</h2>
<div class="legend"><span class="b">ATO label</span><span class="g">Answer used</span><span class="y">Evidence needed</span><span class="r">Accountant review</span><span class="x">N/A skipped</span></div>
<h2>Interview summary</h2>
<p class="summary-note" data-anchor="summary-note">{summary_note}</p>
<div class="footer"><span>Self-prepared custom guide. Not an ATO form. Not fileable.</span><span>Page 1</span></div>
</article>
<aside class="side">
<div class="tab red review" data-target="prep-boundary"><b>Prep boundary</b><p>Not fileable. Manual copy only into myTax/paper form or send to accountant.</p></div>
<div class="tab blue" data-target="how-to-row"><b>How-to row</b><p>Use ATO labels, then clear accountant-review flags before copying manually.</p></div>
<div class="tab yellow evidence" data-target="summary-note"><b>Evidence needed</b><p>Points directly to the interview summary note.</p></div>
</aside>
</section>
<section class="spread">
<article class="page long">
<div class="watermark">MANUAL COPY</div>
<div class="header"><h1>Tax items and review flags</h1><div class="meta">Income year {income_year}<br>Self-prepared draft<br>Not an ATO form</div></div>
{extraction_table}
<h2>ATO-aligned manual copy worksheet</h2>
<table class="table"><thead><tr><th></th><th>ATO area</th><th>Question</th><th>Answer/value</th><th>Why included</th><th>Source</th><th>Status</th></tr></thead><tbody>
{rows}
</tbody></table>
{abn_section}
{bas_section}
{missing_queue}
{evidence_queue}
<div class="callout"><b>Accountant review queue:</b> {review_queue}</div>
{source_appendix}
<div class="footer"><span>Self-prepared custom guide. Not an ATO form. Not fileable.</span><span>Page 2</span></div>
</article>
<aside class="side">
{row_tabs}
</aside>
</section>
</main>
<script>
function findTarget(spread,value){{for(const el of spread.querySelectorAll('[data-anchor]')){{if(el.dataset.anchor===value)return el;}}return null;}}
function alignTabs(){{for(const spread of document.querySelectorAll('.spread')){{const side=spread.querySelector('.side');if(!side)continue;const spreadRect=spread.getBoundingClientRect();for(const tab of side.querySelectorAll('.tab[data-target]')){{const target=findTarget(spread,tab.dataset.target);if(!target)continue;const targetRect=target.getBoundingClientRect();const targetCenter=targetRect.top-spreadRect.top+targetRect.height/2;const tabHeight=tab.offsetHeight||66;tab.style.top=Math.max(18,targetCenter-tabHeight/2)+'px';}}}}}}
function clearSpotlight(){{document.querySelectorAll('.spotlight-target').forEach(function(el){{el.classList.remove('spotlight-target');}});document.querySelectorAll('.tab.active').forEach(function(el){{el.classList.remove('active');}});}}
function spotlight(tab){{clearSpotlight();const spread=tab.closest('.spread');const target=spread?findTarget(spread,tab.dataset.target):null;if(!target)return;target.classList.add('spotlight-target');tab.classList.add('active');}}
window.addEventListener('load',alignTabs);window.addEventListener('resize',alignTabs);setTimeout(alignTabs,80);
for(const tab of document.querySelectorAll('.tab[data-target]')){{tab.addEventListener('click',function(){{spotlight(tab);}});}}
for(const button of document.querySelectorAll('[data-mode]')){{button.onclick=function(){{document.body.classList.remove('hide-tabs','only-review','only-evidence');if(button.dataset.mode==='hide')document.body.classList.add('hide-tabs');if(button.dataset.mode==='review')document.body.classList.add('only-review');if(button.dataset.mode==='evidence')document.body.classList.add('only-evidence');clearSpotlight();alignTabs();}};}}
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
