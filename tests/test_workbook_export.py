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
import taxmate_intake  # noqa: E402
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

    def test_raw_intake_file_uses_canonical_pack_conversion(self) -> None:
        answers = taxmate_intake.sample_answers()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "answers.json"
            source.write_text(json.dumps(answers), encoding="utf-8")

            data = taxmate_workbook.load_workbook_data(str(source))
            tabs = taxmate_workbook.build_tabs(data)

        self.assertGreater(len(tabs["employee"]), len(answers.get("extracted_values", [])))
        self.assertTrue(tabs["abn"])
        self.assertTrue(tabs["bas"])
        self.assertTrue(tabs["investments"])
        self.assertTrue(tabs["accountant_review"])

    def test_guide_file_is_not_reconverted_as_intake_answers(self) -> None:
        payload = {"items": [row("GUIDE-1", "Evidence")]}
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "guide.json"
            source.write_text(json.dumps(payload), encoding="utf-8")

            data = taxmate_workbook.load_workbook_data(str(source))

        self.assertEqual(["GUIDE-1"], [item.number for item in data.items])

    def test_extracted_value_only_guide_is_not_reconverted(self) -> None:
        payload = {
            "income_year": "2025-26",
            "extracted_values": [
                {
                    "number": "AI-ONLY-1",
                    "document": "Reviewed statement",
                    "field": "Reviewed value",
                    "value": 0,
                    "status": "Evidence",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "guide.json"
            source.write_text(json.dumps(payload), encoding="utf-8")

            data = taxmate_workbook.load_workbook_data(str(source))
            tabs = taxmate_workbook.build_tabs(data)

        self.assertEqual(["AI-ONLY-1"], [row["number"] for row in tabs["employee"]])
        self.assertFalse(tabs["abn"])
        self.assertFalse(tabs["bas"])
        self.assertEqual(1, len(tabs["evidence"]))

    def test_csv_writer_neutralizes_formula_prefixes_in_every_cell(self) -> None:
        dangerous = ("=1+1", "+cmd", "-2+3", "@SUM(A1:A2)", " \t=hidden")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "safe.csv"
            taxmate_workbook.write_csv(
                output,
                [{f"field_{index}": value for index, value in enumerate(dangerous)}],
                (),
            )
            with output.open(encoding="utf-8", newline="") as handle:
                exported = next(csv.DictReader(handle))

        self.assertEqual(
            {f"field_{index}": f"'{value}" for index, value in enumerate(dangerous)},
            exported,
        )

    def test_sources_include_row_and_fact_destination_mapping_provenance(self) -> None:
        data = taxmate_taxpack.load_guide_payload(
            taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        )
        tabs = taxmate_workbook.build_tabs(data)
        phi_sources = [row for row in tabs["sources"] if row["number"] == "PHI-STMT-1"]

        mapping_sources = [row for row in phi_sources if "Destination mapping" in row["source_role"]]
        self.assertGreaterEqual(len(mapping_sources), 2)
        self.assertTrue(all(row["source_url"].startswith("https://www.ato.gov.au/") for row in mapping_sources))
        self.assertTrue(all(row["source_title"] for row in mapping_sources))
        self.assertTrue(all(row["checked_at"] for row in mapping_sources))
        self.assertEqual(
            len({(row["number"], row["source_url"]) for row in phi_sources}),
            len(phi_sources),
        )

    def test_shared_url_metadata_stays_row_specific(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        data = taxmate_taxpack.load_guide_payload(payload)
        phi_row = next(row for row in taxmate_taxpack.build_render_rows(data) if row.item.number == "PHI-STMT-1")
        mapping_url = next(
            url
            for url, _, role, _ in taxmate_taxpack.row_source_entries(phi_row)
            if role == "Destination mapping"
        )
        data.items.insert(
            0,
            taxmate_taxpack.guide_item(
                {
                    "number": "SUPPORT-ONLY",
                    "ato_area": "Records",
                    "question": "Supporting source only?",
                    "answer": 0,
                    "status": "Evidence",
                    "source_url": mapping_url,
                    "checked_at": "2026-01-02",
                }
            ),
        )

        sources = taxmate_workbook.build_tabs(data)["sources"]
        supporting = next(row for row in sources if row["number"] == "SUPPORT-ONLY")

        self.assertEqual(mapping_url, supporting["source_url"])
        self.assertEqual("Supporting source", supporting["source_role"])
        self.assertEqual("", supporting["source_title"])
        self.assertEqual("2026-01-02", supporting["checked_at"])


if __name__ == "__main__":
    unittest.main()
