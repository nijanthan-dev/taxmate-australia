#!/usr/bin/env python3
"""Export reviewed TaxMate guide data as deterministic CSV workbook tabs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import taxmate_taxpack
import taxmate_intake


ROW_COLUMNS = (
    "number",
    "area",
    "question",
    "answer",
    "status",
    "review_note",
    "row_kind",
    "facts",
    "next_action",
    "destination",
    "source_urls",
    "checked_at",
)
GUIDE_SECTION_KEYS = frozenset(
    {
        "items",
        "abn_items",
        "bas_items",
        "company_items",
        "trust_items",
        "partnership_items",
        "missing_facts",
        "evidence_items",
    }
)
GUIDE_METADATA_KEYS = frozenset({"income_year", "generated_date", "summary_note", "extracted_values"})
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@")


@dataclass(frozen=True)
class WorkbookRow:
    number: Any
    area: Any
    question: Any
    answer: Any
    status: Any
    review_note: Any
    row_kind: Any
    facts: Any
    next_action: Any
    destination: Any
    source_urls: Any
    checked_at: Any

    def as_dict(self) -> Dict[str, str]:
        return {column: display_value(getattr(self, column)) for column in ROW_COLUMNS}


def display_value(value: Any) -> str:
    if value is None:
        return ""
    if value is False:
        return "false"
    if value is True:
        return "true"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def csv_safe_cell(value: Any) -> str:
    text = display_value(value)
    candidate = text.lstrip(" \t\r\n")
    return f"'{text}" if candidate.startswith(CSV_FORMULA_PREFIXES) else text


def is_guide_payload(payload: Dict[str, Any]) -> bool:
    if GUIDE_SECTION_KEYS.intersection(payload):
        return True
    return "extracted_values" in payload and set(payload).issubset(GUIDE_METADATA_KEYS)


def load_workbook_data(path: str) -> taxmate_taxpack.GuideData:
    payload = taxmate_taxpack.read_json(path)
    if not is_guide_payload(payload):
        payload = taxmate_intake.answers_to_pack_payload(payload)
    return taxmate_taxpack.load_guide_payload(payload)


def workbook_row(item: taxmate_taxpack.GuideItem, income_year: str) -> WorkbookRow:
    status_kind = taxmate_taxpack.effective_status_kind(item)
    contract = taxmate_taxpack.item_contract(item, income_year)
    handoff = contract["handoff"]
    destination = handoff.get("destination")
    destination_label = destination.get("label") if isinstance(destination, dict) else ""
    return WorkbookRow(
        number=item.number,
        area=item.ato_area,
        question=item.question,
        answer=item.answer,
        status=taxmate_taxpack.canonical_status(status_kind),
        review_note=taxmate_taxpack.review_text(item),
        row_kind=contract["row_kind"],
        facts=contract["facts"],
        next_action=handoff.get("next_action"),
        destination=destination_label,
        source_urls=item.source_urls,
        checked_at=item.checked_at,
    )


def is_investment(row: WorkbookRow) -> bool:
    value = f"{display_value(row.area)} {display_value(row.row_kind)}".lower()
    return any(term in value for term in ("investment", "interest", "dividend", "managed-fund", "trust-distribution"))


def build_tabs(data: taxmate_taxpack.GuideData) -> Dict[str, List[Dict[str, str]]]:
    section_rows = [
        (render_row.section, workbook_row(render_row.item, display_value(data.income_year)))
        for render_row in taxmate_taxpack.build_render_rows(data)
    ]
    rows = [row for _, row in section_rows]
    main = [row for section, row in section_rows if section in {"main", "ai"}]
    review = [row for row in rows if row.status == "Accountant review"]
    evidence = [row for row in rows if row.status == "Evidence"]
    sources = [
        {
            "number": display_value(row.number),
            "area": display_value(row.area),
            "source_url": display_value(url),
            "checked_at": display_value(row.checked_at),
        }
        for row in rows
        for url in (row.source_urls if isinstance(row.source_urls, list) else [])
    ]
    return {
        "readme": [
            {"key": "income_year", "value": display_value(data.income_year)},
            {"key": "generated_date", "value": display_value(data.generated_date)},
            {"key": "boundary", "value": "Preparation aid only; not fileable; human review required."},
        ],
        "employee": [row.as_dict() for row in main if not is_investment(row)],
        "abn": [row.as_dict() for section, row in section_rows if section == "abn"],
        "bas": [row.as_dict() for section, row in section_rows if section == "bas"],
        "investments": [row.as_dict() for row in main if is_investment(row)],
        "evidence": [row.as_dict() for row in evidence],
        "accountant_review": [row.as_dict() for row in review],
        "sources": sources,
    }


def write_csv(path: Path, rows: Sequence[Dict[str, str]], fallback_columns: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else list(fallback_columns)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_safe_cell(row.get(column)) for column in columns})


def export_workbook(data: taxmate_taxpack.GuideData, output: str) -> None:
    tabs = build_tabs(data)
    fallbacks = {
        "readme": ("key", "value"),
        "sources": ("number", "area", "source_url", "checked_at"),
    }
    for name, rows in tabs.items():
        write_csv(Path(output) / f"{name}.csv", rows, fallbacks.get(name, ROW_COLUMNS))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="./scripts/taxmate workbook",
        description="Export reviewed TaxMate JSON as deterministic CSV workbook tabs.",
    )
    parser.add_argument("--input", required=True, help="Reviewed guide/intake-shaped JSON input.")
    parser.add_argument("--output", required=True, help="Output directory for CSV tabs.")
    return parser


def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        export_workbook(load_workbook_data(args.input), args.output)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
