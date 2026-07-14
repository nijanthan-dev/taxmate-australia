from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import taxmate_taxpack  # noqa: E402
import taxmate_workbook  # noqa: E402


def row(number: object, status: str, **extra: object) -> dict[str, object]:
    return {
        "number": number,
        "ato_area": extra.pop("ato_area", "Employment deductions"),
        "question": extra.pop("question", "Reviewed fact?"),
        "answer": extra.pop("answer", 0),
        "why_included": extra.pop("why_included", ""),
        "status": status,
        **extra,
    }


class WorkbookExportTests(unittest.TestCase):
    def test_parsed_rows_preserve_review_precedence_falsey_values_and_provenance(self) -> None:
        data = taxmate_taxpack.load_guide_payload(
            {
                "items": [
                    row(
                        0,
                        "Accountant review required",
                        status_kind="evidence",
                        tab_kind="answer",
                        answer=False,
                        source_urls=[False, "https://www.ato.gov.au/example"],
                        checked_at=0,
                    )
                ]
            }
        )

        exported = taxmate_workbook.build_tabs(data)
        review = exported["accountant_review"][0]

        self.assertEqual("0", review["number"])
        self.assertEqual("false", review["answer"])
        self.assertEqual("Accountant review", review["status"])
        self.assertEqual("0", review["checked_at"])
        self.assertIn('"false"', review["source_urls"])
        self.assertTrue(review["review_note"])
        self.assertEqual(2, len(exported["sources"]))

    def test_file_export_creates_deterministic_tabs_and_keeps_blank_review_fallback(self) -> None:
        payload = {
            "income_year": "2025-26",
            "items": [row("INV-1", "Evidence", ato_area="Investment dividends")],
            "extracted_values": [
                {
                    "number": "AI-1",
                    "document": "PAYG statement",
                    "field": "Gross payments",
                    "value": 0,
                    "status": "Evidence",
                }
            ],
            "abn_items": [row("ABN-1", "Review", ato_area="ABN business")],
            "bas_items": [row("BAS-1", "Evidence", ato_area="BAS")],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.json"
            output = root / "workbook"
            source.write_text(json.dumps(payload), encoding="utf-8")

            taxmate_workbook.export_workbook(taxmate_taxpack.load_guide_data(str(source)), str(output))

            self.assertEqual(
                {
                    "abn.csv",
                    "accountant_review.csv",
                    "bas.csv",
                    "employee.csv",
                    "evidence.csv",
                    "investments.csv",
                    "readme.csv",
                    "sources.csv",
                },
                {path.name for path in output.iterdir()},
            )
            with (output / "accountant_review.csv").open(encoding="utf-8", newline="") as handle:
                review = next(csv.DictReader(handle))
            self.assertEqual("ABN-1", review["number"])
            self.assertEqual("Row ABN-1: Accountant review.", review["review_note"])
            with (output / "investments.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual("INV-1", next(csv.DictReader(handle))["number"])
            with (output / "employee.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual("AI-1", next(csv.DictReader(handle))["number"])

    def test_direct_workbook_row_preserves_zero_and_false(self) -> None:
        direct = taxmate_taxpack.GuideItem(
            number=0,
            ato_area=False,
            question=False,
            answer=0,
            why_included="",
            source_urls=[False],
            checked_at=0,
            status="Evidence",
            status_kind="evidence",
            tab_title="",
            tab_text="",
            tab_kind="evidence",
        )

        exported = taxmate_workbook.workbook_row(direct, "2025-26").as_dict()

        self.assertEqual("0", exported["number"])
        self.assertEqual("false", exported["area"])
        self.assertEqual("false", exported["question"])
        self.assertEqual("0", exported["answer"])
        self.assertEqual("[false]", exported["source_urls"])


if __name__ == "__main__":
    unittest.main()
