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
            "company_items": [row("COMPANY-1", "Review", row_kind="entity-return-company")],
            "trust_items": [row("TRUST-1", "Review", row_kind="entity-return-trust")],
            "partnership_items": [row("PARTNERSHIP-1", "Review", row_kind="entity-return-partnership")],
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
                    "capital_gains.csv",
                    "company.csv",
                    "employee.csv",
                    "evidence.csv",
                    "investments.csv",
                    "other.csv",
                    "partnership.csv",
                    "private_health.csv",
                    "property.csv",
                    "readme.csv",
                    "sources.csv",
                    "super.csv",
                    "trust.csv",
                },
                {path.name for path in output.iterdir()},
            )
            with (output / "accountant_review.csv").open(encoding="utf-8", newline="") as handle:
                review = next(csv.DictReader(handle))
            self.assertEqual("ABN-1", review["number"])
            self.assertEqual("Row ABN-1: Accountant review.", review["review_note"])
            with (output / "investments.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual("INV-1", next(csv.DictReader(handle))["number"])
            with (output / "other.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual("AI-1", next(csv.DictReader(handle))["number"])
            for tab, number in (
                ("company", "COMPANY-1"),
                ("trust", "TRUST-1"),
                ("partnership", "PARTNERSHIP-1"),
            ):
                with (output / f"{tab}.csv").open(encoding="utf-8", newline="") as handle:
                    self.assertEqual(number, next(csv.DictReader(handle))["number"])

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

    def test_routed_entity_worksheet_stays_in_entity_tab(self) -> None:
        payload = {
            "income_year": "2025-26",
            "company_return": {
                "name": "Worksheet Co",
                "income_items": [{
                    "category": "interest",
                    "description": "Bank interest",
                    "amount": 0,
                    "evidence": ["statement.pdf"],
                }],
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "answers.json"
            output = Path(temporary) / "workbook"
            source.write_text(json.dumps(payload), encoding="utf-8")
            data = taxmate_workbook.load_workbook_data(str(source))
            tabs = taxmate_workbook.build_tabs(data)
            taxmate_workbook.export_workbook(data, str(output))
            with (output / "company.csv").open(encoding="utf-8", newline="") as handle:
                exported = next(
                    row for row in csv.DictReader(handle)
                    if row["number"].startswith("COMPANY-INCOME")
                )

        self.assertTrue(tabs["company"])
        self.assertFalse(any(
            row["number"].startswith("COMPANY-INCOME")
            for tab in ("employee", "abn", "bas", "investments")
            for row in tabs[tab]
        ))
        self.assertEqual("COMPANY-INCOME-1", exported["number"])

    def test_company_loss_asset_rows_keep_review_and_provenance_in_workbook(self) -> None:
        answers = {
            "income_year": "2025-26",
            "company_return": {
                "name": "Workbook Assets Co",
                "loss_items": [{
                    "carried_forward_loss": 0,
                    "records": ["loss-schedule.pdf"],
                    "source_url": "https://www.ato.gov.au/example-loss",
                    "checked_at": "2026-07-15T10:00:00Z",
                }],
                "capital_allowance_items": [{
                    "asset": "Server",
                    "deduction_amount": 0,
                    "method": "unknown",
                    "evidence": ["asset-register.csv"],
                }],
            },
        }
        data = taxmate_taxpack.load_guide_payload(taxmate_intake.answers_to_pack_payload(answers))
        tabs = taxmate_workbook.build_tabs(data)
        company_numbers = {row["number"] for row in tabs["company"]}
        review_numbers = {row["number"] for row in tabs["accountant_review"]}

        self.assertIn("COMPANY-LOSS-1", company_numbers)
        self.assertIn("COMPANY-CAPITAL-ALLOWANCE-1", company_numbers)
        self.assertIn("COMPANY-LOSS-1", review_numbers)
        loss = next(row for row in tabs["company"] if row["number"] == "COMPANY-LOSS-1")
        self.assertIn("carried forward loss 0", loss["answer"])
        self.assertIn("https://www.ato.gov.au/example-loss", loss["source_urls"])
        self.assertEqual("2026-07-15T10:00:00Z", loss["checked_at"])

    def test_company_dividend_franking_division_7a_rows_stay_in_company_workbook(self) -> None:
        answers = {
            "income_year": "2025-26",
            "company_return": {
                "name": "Workbook Benefits Co",
                "income_items": [{
                    "category": "dividends",
                    "amount": 0,
                    "franking_credit": 0,
                    "evidence": ["dividend.pdf"],
                }],
                "franking_account": {
                    "opening_balance": 0,
                    "closing_balance": 0,
                    "deficit": False,
                    "franking_deficit_tax": -1,
                    "evidence_status": "partial",
                    "records": ["franking.csv"],
                },
                "division_7a": {
                    "loan_amount": 0,
                    "complying_loan_agreement": False,
                    "loan_terms": "written terms pending review",
                    "benchmark_interest_rate": 8.77,
                    "minimum_repayment_made": False,
                    "retained_profit": -1,
                    "evidence_status": "partial",
                    "records": ["ledger.pdf"],
                    "source_url": "https://www.ato.gov.au/example-division-7a",
                    "checked_at": "2026-07-16T10:00:00Z",
                },
            },
        }
        data = taxmate_taxpack.load_guide_payload(taxmate_intake.answers_to_pack_payload(answers))
        tabs = taxmate_workbook.build_tabs(data)
        company_numbers = {row["number"] for row in tabs["company"]}
        review_numbers = {row["number"] for row in tabs["accountant_review"]}

        for number in (
            "COMPANY-DIVIDEND-1",
            "COMPANY-FRANKING-ACCOUNT-1",
            "COMPANY-DIVISION-7A-1",
        ):
            self.assertIn(number, company_numbers)
            self.assertIn(number, review_numbers)
            self.assertFalse(any(
                row["number"] == number
                for tab in ("employee", "abn", "bas", "investments")
                for row in tabs[tab]
            ))
        franking = next(
            row for row in tabs["company"]
            if row["number"] == "COMPANY-FRANKING-ACCOUNT-1"
        )
        self.assertIn("franking deficit tax -1", franking["answer"])
        self.assertIn("evidence status partial", franking["answer"])
        division_7a = next(
            row for row in tabs["company"]
            if row["number"] == "COMPANY-DIVISION-7A-1"
        )
        self.assertIn("loan amount 0", division_7a["answer"])
        self.assertIn("complying loan agreement false", division_7a["answer"])
        self.assertIn("loan terms written terms pending review", division_7a["answer"])
        self.assertIn("benchmark interest rate 8.77", division_7a["answer"])
        self.assertIn("retained profit -1", division_7a["answer"])
        self.assertIn("evidence status partial", division_7a["answer"])
        self.assertIn(
            "https://www.ato.gov.au/example-division-7a",
            division_7a["source_urls"],
        )
        self.assertEqual("2026-07-16T10:00:00Z", division_7a["checked_at"])

    def test_partnership_loss_gst_psi_rows_keep_review_and_provenance(self) -> None:
        answers = {
            "income_year": "2025-26",
            "partnership_return": {
                "name": "Workbook Partners",
                "losses": {"amount": 0, "records": ["accounts.pdf"]},
                "gst_bas_review": {
                    "gst_registered": False,
                    "bas_period": "quarterly",
                    "bas_overlap": True,
                    "records": ["bas.pdf"],
                },
                "psi_review": {
                    "psi": "unknown",
                    "evidence": ["contracts.pdf"],
                    "source_url": "https://www.ato.gov.au/example-psi",
                    "checked_at": "2026-07-15T10:00:00Z",
                },
            },
        }
        data = taxmate_taxpack.load_guide_payload(taxmate_intake.answers_to_pack_payload(answers))
        tabs = taxmate_workbook.build_tabs(data)
        numbers = {row["number"] for row in tabs["partnership"]}
        review_numbers = {row["number"] for row in tabs["accountant_review"]}

        self.assertIn("PARTNERSHIP-LOSS-1", numbers)
        self.assertIn("PARTNERSHIP-GST-BAS-1", numbers)
        self.assertIn("PARTNERSHIP-PSI-1", numbers)
        self.assertIn("PARTNERSHIP-PSI-1", review_numbers)
        psi = next(row for row in tabs["partnership"] if row["number"] == "PARTNERSHIP-PSI-1")
        self.assertIn("https://www.ato.gov.au/example-psi", psi["source_urls"])
        self.assertEqual("2026-07-15T10:00:00Z", psi["checked_at"])

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
        self.assertTrue(tabs["super"])
        self.assertTrue(tabs["private_health"])
        self.assertTrue(tabs["property"])
        self.assertTrue(tabs["capital_gains"])
        self.assertTrue(tabs["other"])
        self.assertTrue(tabs["accountant_review"])
        review_numbers = {row["number"] for row in tabs["accountant_review"]}
        self.assertIn("income_year", review_numbers)
        self.assertIn("resident", review_numbers)

    def test_guide_file_is_not_reconverted_as_intake_answers(self) -> None:
        payload = {"items": [row("GUIDE-1", "Evidence")]}
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "guide.json"
            source.write_text(json.dumps(payload), encoding="utf-8")

            data = taxmate_workbook.load_workbook_data(str(source))

        self.assertEqual(["GUIDE-1"], [item.number for item in data.items])

    def test_raw_intake_with_guide_named_helper_still_uses_conversion(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["items"] = []
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "answers.json"
            source.write_text(json.dumps(answers), encoding="utf-8")

            data = taxmate_workbook.load_workbook_data(str(source))
            tabs = taxmate_workbook.build_tabs(data)

        self.assertTrue(tabs["employee"])
        self.assertTrue(tabs["abn"])
        self.assertTrue(tabs["capital_gains"])

    def test_malformed_guide_section_stays_a_review_row(self) -> None:
        payload = {"income_year": "2025-26", "items": {"unexpected": "object"}}
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "guide.json"
            source.write_text(json.dumps(payload), encoding="utf-8")

            data = taxmate_workbook.load_workbook_data(str(source))
            tabs = taxmate_workbook.build_tabs(data)

        self.assertIn("MALFORMED-items", {row["number"] for row in tabs["accountant_review"]})

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

        self.assertEqual(["AI-ONLY-1"], [row["number"] for row in tabs["other"]])
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

    def test_entity_statement_fixture_exports_review_rows_and_sources(self) -> None:
        source = ROOT / "tests" / "fixtures" / "entity-routing-answers.json"
        data = taxmate_workbook.load_workbook_data(str(source))
        tabs = taxmate_workbook.build_tabs(data)

        review = {row["number"]: row for row in tabs["accountant_review"]}
        self.assertIn("TRUST-BEN-1", review)
        self.assertIn("PARTNER-DIST-1", review)
        self.assertEqual("false", review["TRUST-BEN-1"]["answer"].split("present entitlement ", 1)[1].split(";", 1)[0])
        self.assertIn("loss share -25", review["PARTNER-DIST-1"]["answer"])

        source_numbers = {row["number"] for row in tabs["sources"]}
        self.assertIn("TRUST-BEN-1", source_numbers)
        self.assertIn("PARTNER-DIST-1", source_numbers)

    def test_main_rows_route_to_specific_tabs_without_abn_bas_duplication(self) -> None:
        data = taxmate_taxpack.load_guide_payload(
            taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        )
        tabs = taxmate_workbook.build_tabs(data)
        row_tabs = (
            "employee", "abn", "bas", "investments", "super", "private_health", "property",
            "capital_gains", "other", "evidence", "accountant_review",
        )
        numbers = {tab: {row["number"] for row in tabs[tab]} for tab in row_tabs}

        self.assertIn("PAYG-1", numbers["employee"])
        self.assertIn("INT-1", numbers["investments"])
        self.assertIn("SUPER-INCOME", numbers["super"])
        self.assertIn("PHI-STMT-1", numbers["private_health"])
        self.assertIn("RENTAL-PROPERTY", numbers["property"])
        self.assertIn("CGT-SCHEDULE", numbers["capital_gains"])
        self.assertIn("CRYPTO-CGT", numbers["capital_gains"])
        self.assertNotIn("CRYPTO-CGT", numbers["investments"])
        self.assertIn("income_year", numbers["other"])
        for gate in taxmate_workbook.ABN_BAS_GATE_NUMBERS:
            self.assertFalse(any(gate in numbers[tab] for tab in (
                "employee", "investments", "super", "private_health", "property", "capital_gains", "other"
            )))
        self.assertTrue(numbers["abn"])
        self.assertTrue(numbers["bas"])


if __name__ == "__main__":
    unittest.main()
