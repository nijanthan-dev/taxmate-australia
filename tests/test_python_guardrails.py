from __future__ import annotations

import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any, Optional


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import atodata  # noqa: E402
import skillgen  # noqa: E402
import taxmate  # noqa: E402
import taxmate_calc  # noqa: E402
import taxmate_finance  # noqa: E402
import taxmate_intake  # noqa: E402
import taxmate_review_guardrails  # noqa: E402
import taxmate_taxpack  # noqa: E402
import taxmate_validate  # noqa: E402


MARKETPLACE_NAME = "taxmate-local-marketplace"
PLUGIN_ADD_COMMAND = f"codex plugin add taxmate-australia@{MARKETPLACE_NAME}"


def write_local_marketplace_fixture(root: Path, docs_text: str, plugins: Optional[list[Any]] = None) -> None:
    marketplace_dir = root / ".agents" / "plugins"
    docs_dir = root / "docs"
    marketplace_dir.mkdir(parents=True)
    docs_dir.mkdir()
    (root / ".codex-plugin").mkdir()
    (root / ".codex-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    (marketplace_dir / "marketplace.json").write_text(
        json.dumps(
            {
                "name": MARKETPLACE_NAME,
                "plugins": plugins
                if plugins is not None
                else [
                    {
                        "name": "taxmate-australia",
                        "source": {"source": "local", "path": "./"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (docs_dir / "FULL_PLUGIN_INSTALL.md").write_text(docs_text, encoding="utf-8")


def local_marketplace_docs(marketplace_command: str) -> str:
    return marketplace_command + "\n" + PLUGIN_ADD_COMMAND + "\n"


def date_weekday(value: str) -> int:
    return date.fromisoformat(value).weekday()


class ReviewGuardrailTests(unittest.TestCase):
    def test_review_guardrails_pass_current_repo(self) -> None:
        self.assertEqual([], taxmate_review_guardrails.run(ROOT))

    def test_review_guardrails_detect_taxpack_truthiness_fallback(self) -> None:
        text = 'def scalar_text(): pass\nvalue = raw.get("answer") or ""\n'
        findings = taxmate_review_guardrails.check_taxpack_output_layer_text(text)

        self.assertTrue(any("forbidden pattern" in finding.detail for finding in findings))

    def test_review_guardrails_require_extended_taxpack_review_tabs(self) -> None:
        text = (
            "def scalar_text(): pass\n"
            "def text_value(): pass\n"
            "def source_urls(): pass\n"
            "def render_provenance(): pass\n"
            "def is_review_like_key(): pass\n"
            "def effective_status_kind(): pass\n"
            "def effective_tab_kind(): pass\n"
            "def review_text(): pass\n"
            "def row_anchor(item: GuideItem, row_index: int): pass\n"
            "row_tabs = ''.join(render_item_tab(item, row_index) for row_index, item in indexed_items)\n"
            "review_items = [review_text(item) for item in data.items]\n"
            "findTarget(spread,value)\n"
            "el.dataset.anchor===value\n"
            "default_generated_date()\n"
            "canonical_status(item_status_kind)\n"
        )

        findings = taxmate_review_guardrails.check_taxpack_output_layer_text(text)

        self.assertTrue(any("def rendered_tab_items(" in finding.detail for finding in findings))
        self.assertTrue(any("queue_item_text" in finding.detail for finding in findings))
        self.assertTrue(any("data.abn_items" in finding.detail for finding in findings))
        self.assertTrue(any("data.bas_items" in finding.detail for finding in findings))

    def test_review_guardrails_require_individual_intake_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "taxmate_intake.py").write_text(
                "status = \"Used\" if not is_unknown(value) else \"Evidence\"\n"
                '"VIC": {"2025-11-04", "2026-03-09"}\n',
                encoding="utf-8",
            )

            findings = taxmate_review_guardrails.check_individual_intake_contract(root)

        self.assertTrue(any("contains_unknown" in finding.detail for finding in findings))
        self.assertTrue(any("normalize_state" in finding.detail for finding in findings))
        self.assertTrue(any("WEEKDAY_ALIASES" in finding.detail for finding in findings))
        self.assertTrue(any("parse_weekday" in finding.detail for finding in findings))
        self.assertTrue(any("wfh_answers" in finding.detail for finding in findings))
        self.assertTrue(any("has_abn_inputs" in finding.detail for finding in findings))
        self.assertTrue(any("has_bas_inputs" in finding.detail for finding in findings))
        self.assertTrue(any("parse_gst_registration" in finding.detail for finding in findings))
        self.assertTrue(any("confirmed" in finding.detail for finding in findings))
        self.assertTrue(any("2025-09-26" in finding.detail for finding in findings))
        self.assertTrue(any("2026-06-08" in finding.detail for finding in findings))
        self.assertTrue(any("hours_per_day" in finding.detail for finding in findings))
        self.assertTrue(any("has_complete_wfh_records" in finding.detail for finding in findings))
        self.assertTrue(any("valid_wfh_adjustment_dates" in finding.detail for finding in findings))
        self.assertTrue(any("work_use != 100" in finding.detail for finding in findings))
        self.assertTrue(any("2026-04-04" in finding.detail for finding in findings))
        self.assertTrue(any("parse_iso_date" in finding.detail for finding in findings))
        self.assertTrue(any("parse_dates" in finding.detail for finding in findings))
        self.assertTrue(any("generation_checked_at" in finding.detail for finding in findings))

    def test_review_guardrails_detect_wfh_parser_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "taxmate_intake.py").write_text(
                'start = parse_iso_date(raw.get("start", "2025-07-01"))\n'
                'end = parse_iso_date(raw.get("end", "2026-06-30"))\n'
                'leave = parse_dates(raw.get("leave_dates", []))\n'
                'worked_public = parse_dates(raw.get("worked_public_holidays", []))\n'
                'worked_weekends = parse_dates(raw.get("worked_weekends", []))\n'
                "fixed_candidate = round(hours * WFH_FIXED_RATE_2025_26, 2)\n"
                "return {int(day) for day in weekdays if isinstance(day, int) or str(day).isdigit()}\n",
                encoding="utf-8",
            )

            findings = taxmate_review_guardrails.check_individual_intake_contract(root)

        self.assertTrue(any('raw.get("start", "2025-07-01")' in finding.detail for finding in findings))
        self.assertTrue(any('raw.get("end", "2026-06-30")' in finding.detail for finding in findings))
        self.assertTrue(any('raw.get("leave_dates", [])' in finding.detail for finding in findings))
        self.assertTrue(any('raw.get("worked_public_holidays", [])' in finding.detail for finding in findings))
        self.assertTrue(any('raw.get("worked_weekends", [])' in finding.detail for finding in findings))
        self.assertTrue(any("round(hours * WFH_FIXED_RATE_2025_26, 2)" in finding.detail for finding in findings))
        self.assertTrue(any("return {int(day) for day in weekdays" in finding.detail for finding in findings))

    def test_review_guardrails_require_calculator_temporal_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "taxmate_finance.py").write_text(
                '"generated_at"\n"findings"\ntax_treatment\n"bas_summary"\n'
                "json.dump(payload, out, indent=2, allow_nan=False)\nROUND_HALF_UP\nmath.isfinite\n",
                encoding="utf-8",
            )
            (scripts / "taxmate_calc.py").write_text(
                "def finite_float(): pass\n"
                "math.isfinite\n"
                "ROUND_HALF_UP\n"
                "json.dump(result, out, indent=2, allow_nan=False)\n",
                encoding="utf-8",
            )

            findings = taxmate_review_guardrails.check_finance_and_calc_wire_contract(root)

        self.assertTrue(any(taxmate_review_guardrails.CALCULATOR_TEMPORAL_CONTRACT == finding.check for finding in findings))

    def test_review_guardrails_detect_wrong_local_marketplace_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_local_marketplace_fixture(
                root,
                local_marketplace_docs("codex plugin marketplace add .agents/plugins"),
            )

            findings = taxmate_review_guardrails.check_local_plugin_marketplace_contract(root)

        self.assertTrue(any("repo root" in finding.detail for finding in findings))

    def test_review_guardrails_rejects_marketplace_command_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_local_marketplace_fixture(
                root,
                local_marketplace_docs("codex plugin marketplace add ./marketplace"),
            )

            findings = taxmate_review_guardrails.check_local_plugin_marketplace_contract(root)

        self.assertTrue(
            any("missing exact command: codex plugin marketplace add ." in finding.detail for finding in findings)
        )
        self.assertTrue(any("repo root exactly" in finding.detail for finding in findings))

    def test_review_guardrails_reports_malformed_marketplace_plugin_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_local_marketplace_fixture(
                root,
                local_marketplace_docs("codex plugin marketplace add ."),
                plugins=[
                    "bad entry",
                    {
                        "name": "taxmate-australia",
                        "source": {"source": "local", "path": "./"},
                    },
                ],
            )

            findings = taxmate_review_guardrails.check_local_plugin_marketplace_contract(root)

        self.assertTrue(any("plugins entries must be objects" in finding.detail for finding in findings))

    def test_review_guardrails_list_patterns_as_json(self) -> None:
        payload = json.loads(taxmate_review_guardrails.render_review_patterns("json"))

        patterns = payload["patterns"]

        self.assertTrue(any(pattern["id"] == "PR #38" for pattern in patterns))
        self.assertTrue(any(pattern["id"] == "PR #27 / PR #53" for pattern in patterns))
        self.assertTrue(any(pattern["id"] == "PR #53 intake" for pattern in patterns))
        self.assertTrue(any(pattern["check"] == "local_plugin_marketplace_contract" for pattern in patterns))

    def test_review_guardrails_list_patterns_as_markdown(self) -> None:
        rendered = taxmate_review_guardrails.render_review_patterns("markdown")

        self.assertIn("| Pattern | Guardrail check | Contract |", rendered)
        self.assertIn("| PR #38 | `local_plugin_marketplace_contract` |", rendered)

    def test_review_guardrail_docs_rejects_duplicated_pr_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            (docs / "DEVELOPMENT.md").write_text(
                "./scripts/taxmate review-guardrails\n"
                "./scripts/taxmate review-guardrails --list-patterns\n"
                "./scripts/taxmate review-guardrails --list-patterns --format json\n"
                "The script is the canonical pattern inventory\n"
                "- PR #38: duplicate\n",
                encoding="utf-8",
            )

            findings = taxmate_review_guardrails.check_review_guardrail_docs(root)

        self.assertTrue(any("must not duplicate" in finding.detail for finding in findings))

    def test_review_guardrail_docs_require_exact_base_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            (docs / "DEVELOPMENT.md").write_text(
                "./scripts/taxmate review-guardrails --list-patterns\n"
                "./scripts/taxmate review-guardrails --list-patterns --format json\n"
                "The script is the canonical pattern inventory\n"
                "Do not duplicate PR pattern bullets\n",
                encoding="utf-8",
            )

            findings = taxmate_review_guardrails.check_review_guardrail_docs(root)

        self.assertTrue(
            any(
                "missing exact command: ./scripts/taxmate review-guardrails" in finding.detail
                for finding in findings
            )
        )


class CalculatorTests(unittest.TestCase):
    def test_cgt_discount_rejects_exact_calendar_year(self) -> None:
        result = taxmate_calc.cgt(
            proceeds=1200,
            cost_base=200,
            capital_losses=0,
            acquired="2024-07-01",
            disposed="2025-07-01",
            discount=True,
        )

        self.assertEqual(result["outputs"]["held_months"], 11)
        self.assertFalse(result["outputs"]["discount_allowed"])

    def test_cgt_discount_allows_day_after_calendar_year(self) -> None:
        result = taxmate_calc.cgt(
            proceeds=1200,
            cost_base=200,
            capital_losses=0,
            acquired="2024-07-01",
            disposed="2025-07-02",
            discount=True,
        )

        self.assertEqual(result["outputs"]["held_months"], 12)
        self.assertTrue(result["outputs"]["discount_allowed"])
        self.assertEqual(result["outputs"]["discount_amount"], 500)
        self.assertEqual(result["outputs"]["net_capital_gain_est"], 500)

    def test_non_finite_calculator_input_rejected(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            taxmate_calc.finite_float("nan")
        with self.assertRaises(argparse.ArgumentTypeError):
            taxmate_calc.finite_float("inf")

    def test_payg_defaults_invalid_periods_to_weekly(self) -> None:
        result = taxmate_calc.payg_estimate(
            gross_pay=1500,
            periods_per_year=0,
            tax_free_threshold=True,
            medicare=True,
        )

        self.assertEqual(result["inputs"]["periods_per_year"], 52)
        self.assertGreater(result["outputs"]["estimated_withholding_per_period"], 0)

    def test_year_specific_calculators_reject_unsupported_years(self) -> None:
        cases = [
            taxmate_calc.bas(100, 20, 0, 0, 0, income_year="2024-25"),
            taxmate_calc.super_guarantee(1000, 0, income_year="2024-25"),
            taxmate_calc.fbt(1000, "type2", fbt_year="2025"),
            taxmate_calc.payg_estimate(1500, 52, True, True, income_year="2024-25"),
        ]

        for result in cases:
            with self.subTest(tool=result["tool"]):
                self.assertEqual("not_calculated", result["outputs"]["calculation"])
                self.assertTrue(result["review_flags"])

        self.assertEqual(0, cases[1]["inputs"]["sg_rate_percent"])
        self.assertNotIn("fbt_rate", cases[2]["inputs"])
        self.assertNotIn("estimated_fbt", cases[2]["outputs"])

    def test_bas_is_not_nil_when_gst_activity_cancels_out(self) -> None:
        result = taxmate_calc.bas(
            sales_gst=100,
            purchase_gst=100,
            payg_withheld=0,
            fuel_tax_credit=0,
            adjustments=0,
        )

        self.assertEqual(result["outputs"]["estimated_bas_total"], 0)
        self.assertFalse(result["outputs"]["nil_bas"])


class IndividualIntakeTests(unittest.TestCase):
    def test_launcher_exposes_intake_command(self) -> None:
        self.assertEqual(taxmate.COMMANDS["intake"], "taxmate_intake.py")

    def test_omitted_scope_issues_are_individual_and_prep_only(self) -> None:
        issues = taxmate_intake.omitted_scope_issues()
        titles = {item["title"] for item in issues}

        self.assertIn("feat: add company return intake", titles)
        self.assertIn("feat: add advanced document extraction", titles)
        self.assertEqual(12, len(issues))
        for item in issues:
            self.assertIn("Omitted from V1", item["body"])
            self.assertIn("prep-only", item["body"])

    def test_long_checklist_covers_required_sections(self) -> None:
        sections = {spec.section for spec in taxmate_intake.question_specs()}
        keys = {spec.key for spec in taxmate_intake.question_specs()}

        self.assertTrue(
            {
                "Taxpayer",
                "Spouse",
                "Private health",
                "PAYG",
                "Income",
                "ABN",
                "BAS",
                "Deductions",
                "WFH",
                "Assets",
            }.issubset(sections)
        )
        self.assertTrue({"resident", "state", "spouse_had", "gst_registered", "asset_items"}.issubset(keys))

    def test_missing_required_answers_block_without_allow_missing(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers.pop("resident")

        missing = taxmate_intake.missing_required_answers(answers)

        self.assertEqual(["resident"], [item.key for item in missing])

    def test_missing_required_answers_render_as_evidence_when_allowed(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers.pop("resident")

        rows = taxmate_intake.base_items(answers)
        resident = next(row for row in rows if row["number"] == "resident")

        self.assertEqual("Evidence", resident["status"])
        self.assertEqual("", resident["answer"])

    def test_nested_unknown_answers_render_as_evidence(self) -> None:
        rows = taxmate_intake.base_items(taxmate_intake.sample_answers())
        deductions = next(row for row in rows if row["number"] == "employee_deductions")

        self.assertEqual("Evidence", deductions["status"])

    def test_complex_checklist_answers_do_not_render_used(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["employee_deductions"] = [{"label": "Union fees", "amount": 120}]
        answers["wfh_work_pattern"] = {"weekdays": ["Tuesday"]}
        answers["wfh_records"] = "timesheet"
        answers["asset_items"] = [{"description": "monitor", "cost": 250, "work_use_percent": 80}]

        rows = taxmate_intake.base_items(answers)
        by_number = {row["number"]: row for row in rows}

        for key in ["employee_deductions", "wfh_work_pattern", "wfh_records", "asset_items"]:
            with self.subTest(key=key):
                self.assertEqual("Accountant review", by_number[key]["status"])

    def test_asset_items_alias_gets_typed_asset_review(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers.pop("assets")
        answers["asset_items"] = [
            {"description": "$250 monitor", "cost": 250, "work_use_percent": 80, "evidence": "receipt"}
        ]

        payload = taxmate_intake.answers_to_pack_payload(answers)
        asset = next(row for row in payload["items"] if row["number"] == "ASSET-1")

        self.assertEqual("Accountant review", asset["status"])
        self.assertIn("mixed-use", asset["answer"])

    def test_wfh_work_pattern_alias_gets_typed_wfh_review(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers.pop("wfh")
        answers["wfh_work_pattern"] = {
            "state": "VIC",
            "start": "2026-06-09",
            "end": "2026-06-10",
            "weekdays": ["Tuesday", "Wednesday"],
            "hours_per_day": 8,
            "actual_cost_records": "none",
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }
        answers["wfh_records"] = "timesheet"

        payload = taxmate_intake.answers_to_pack_payload(answers)
        wfh = next(row for row in payload["items"] if row["number"] == "WFH")

        self.assertEqual("Accountant review", wfh["status"])
        self.assertIn("16.00 hours; fixed-rate candidate 11.20", wfh["answer"])

    def test_embedded_unconfirmed_answers_render_as_evidence(self) -> None:
        rows = taxmate_intake.base_items(taxmate_intake.sample_answers())
        private_health = next(row for row in rows if row["number"] == "private_health_cover")

        self.assertEqual("Evidence", private_health["status"])

    def test_ai_extracted_values_require_confirmation(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        data = taxmate_taxpack.load_guide_payload(payload)
        body = taxmate_taxpack.render_html(data)

        self.assertIn("AI extraction confirmation table", body)
        self.assertIn("PAYG gross", body)
        self.assertIn("<span class=\"status gap\">Evidence</span>", body)

    def test_ai_extracted_values_require_literal_true_confirmation(self) -> None:
        rows = taxmate_intake.extraction_rows(
            [
                {"field": "gross", "value": "100", "confirmed": "false"},
                {"field": "tax", "value": "30", "confirmed": True},
            ]
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertEqual("Used", rows[1]["status"])

    def test_ai_extracted_values_preserve_review_tags(self) -> None:
        rows = taxmate_intake.extraction_rows(
            [
                {"field": "gross", "value": "100", "confirmed": True, "status": "Accountant review"},
                {"field": "tax", "value": "30", "confirmed": True, "status_kind": "review"},
                {"field": "label", "value": "D5", "confirmed": True, "tab_kind": "review"},
                {"field": "flag", "value": "D5", "confirmed": True, "status": "red"},
            ]
        )

        for row in rows:
            self.assertEqual("Accountant review", row["status"])
        self.assertEqual("review", rows[1]["status_kind"])
        self.assertEqual("review", rows[2]["tab_kind"])

    def test_confirmed_ai_review_tags_render_as_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        payload["extracted_values"] = taxmate_intake.extraction_rows(
            [{"field": "GST credits", "value": "140", "confirmed": True, "status_kind": "review"}]
        )
        data = taxmate_taxpack.load_guide_payload(payload)
        body = taxmate_taxpack.render_html(data)

        self.assertIn("GST credits", body)
        self.assertIn("<span class=\"status review-badge\">Accountant review</span>", body)

    def test_wfh_calendar_excludes_leave_and_unworked_public_holidays(self) -> None:
        raw = {
            "state": "VIC",
            "start": "2026-01-23",
            "end": "2026-01-27",
            "weekdays": [0, 1, 2, 3, 4],
            "hours_per_day": 8,
            "leave_dates": ["2026-01-27"],
            "worked_public_holidays": [],
            "worked_weekends": ["2026-01-24"],
        }

        self.assertEqual(taxmate_intake.calculate_wfh_hours(raw), 16)

        raw["worked_public_holidays"] = ["2026-01-26"]
        self.assertEqual(taxmate_intake.calculate_wfh_hours(raw), 24)

    def test_wfh_rejects_unsupported_income_year(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "income_year": "2024-25",
                "state": "VIC",
                "start": "2024-12-25",
                "end": "2024-12-25",
                "weekdays": [2],
                "hours_per_day": 8,
                "records": "timesheet",
                "actual_cost_records": "none",
                "leave_dates": [],
                "worked_public_holidays": [],
                "worked_weekends": [],
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_rejects_dates_outside_supported_year(self) -> None:
        raw = {
            "income_year": "2025-26",
            "state": "VIC",
            "start": "2024-12-25",
            "end": "2024-12-25",
            "weekdays": [2],
            "hours_per_day": 8,
            "records": "timesheet",
            "actual_cost_records": "none",
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        self.assertIsNone(taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_uses_top_level_income_year_for_support_gate(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["income_year"] = "2024-25"
        answers["wfh"] = {
            "state": "VIC",
            "start": "2024-12-25",
            "end": "2024-12-25",
            "weekdays": [2],
            "hours_per_day": 8,
            "records": "timesheet",
            "actual_cost_records": "none",
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        wfh = next(row for row in payload["items"] if row["number"] == "WFH")

        self.assertEqual("Evidence", wfh["status"])
        self.assertIn("unknown hours; fixed-rate candidate unknown", wfh["answer"])

    def test_wfh_calendar_excludes_vic_kings_birthday(self) -> None:
        raw = {
            "state": "VIC",
            "start": "2026-06-08",
            "end": "2026-06-08",
            "weekdays": [0],
            "hours_per_day": 8,
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        self.assertEqual(0, taxmate_intake.calculate_wfh_hours(raw))

        raw["worked_public_holidays"] = ["2026-06-08"]
        self.assertEqual(8, taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_calendar_excludes_vic_grand_final_friday(self) -> None:
        raw = {
            "state": "VIC",
            "start": "2025-09-26",
            "end": "2025-09-26",
            "weekdays": [4],
            "hours_per_day": 8,
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        self.assertEqual(0, taxmate_intake.calculate_wfh_hours(raw))

        raw["worked_public_holidays"] = ["2025-09-26"]
        self.assertEqual(8, taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_calendar_excludes_vic_easter_weekend(self) -> None:
        raw = {
            "state": "VIC",
            "start": "2026-04-04",
            "end": "2026-04-05",
            "weekdays": [5, 6],
            "hours_per_day": 8,
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        self.assertEqual(0, taxmate_intake.calculate_wfh_hours(raw))

        raw["worked_public_holidays"] = ["2026-04-04"]
        self.assertEqual(8, taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_calendar_excludes_non_vic_easter_weekend(self) -> None:
        expectations = {
            "NSW": 0,
            "QLD": 0,
            "SA": 0,
            "WA": 8,
        }
        for state, expected_hours in expectations.items():
            with self.subTest(state=state):
                raw = {
                    "state": state,
                    "start": "2026-04-04",
                    "end": "2026-04-05",
                    "weekdays": [5, 6],
                    "hours_per_day": 8,
                    "leave_dates": [],
                    "worked_public_holidays": [],
                    "worked_weekends": [],
                }

                self.assertEqual(expected_hours, taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_uses_current_public_holiday_source(self) -> None:
        self.assertEqual(
            "https://www.fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays",
            taxmate_intake.PUBLIC_HOLIDAY_SOURCE,
        )
        self.assertEqual(
            [
                "https://www.fairwork.gov.au/employment-conditions/public-holidays/2025-public-holidays",
                "https://www.fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays",
            ],
            taxmate_intake.PUBLIC_HOLIDAY_SOURCES,
        )

    def test_wfh_calendar_excludes_kings_birthday_states(self) -> None:
        for state in ["VIC", "NSW", "SA", "TAS", "ACT", "NT"]:
            with self.subTest(state=state):
                raw = {
                    "state": state,
                    "start": "2026-06-08",
                    "end": "2026-06-08",
                    "weekdays": [0],
                    "hours_per_day": 8,
                    "leave_dates": [],
                    "worked_public_holidays": [],
                    "worked_weekends": [],
                }

                self.assertEqual(0, taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_calendar_excludes_anzac_substitute_states(self) -> None:
        for state in ["NSW", "ACT", "WA"]:
            with self.subTest(state=state):
                raw = {
                    "state": state,
                    "start": "2026-04-27",
                    "end": "2026-04-27",
                    "weekdays": [0],
                    "hours_per_day": 8,
                    "leave_dates": [],
                    "worked_public_holidays": [],
                    "worked_weekends": [],
                }

                self.assertEqual(0, taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_uses_taxpayer_state_when_nested_state_missing(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["state"] = "VIC"
        answers["wfh"] = {
            "start": "2026-06-08",
            "end": "2026-06-08",
            "weekdays": [0],
            "hours_per_day": 8,
            "records": "timesheet",
            "actual_cost_records": "none",
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        wfh = next(row for row in payload["items"] if row["number"] == "WFH")

        self.assertIn("0.00 hours", wfh["answer"])

    def test_wfh_normalizes_full_state_names(self) -> None:
        expectations = {
            " vic ": ("2026-06-08", 0),
            "Victoria": ("2026-06-08", 0),
            "New South Wales": ("2026-06-08", 0),
            "Queensland": ("2025-10-06", 0),
            "South Australia": ("2026-06-08", 0),
            "Western Australia": ("2026-06-01", 0),
            "Tasmania": ("2026-06-08", 0),
            "Australian Capital Territory": ("2026-06-08", 0),
            "Northern Territory": ("2026-06-08", 0),
        }
        for state, (holiday, expected_hours) in expectations.items():
            with self.subTest(state=state):
                raw = {
                    "state": state,
                    "start": holiday,
                    "end": holiday,
                    "weekdays": [date_weekday(holiday)],
                    "hours_per_day": 8,
                    "leave_dates": [],
                    "worked_public_holidays": [],
                    "worked_weekends": [],
                }

                self.assertEqual(expected_hours, taxmate_intake.calculate_wfh_hours(raw))

    def test_wfh_normalizes_taxpayer_state_fallback(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["state"] = " Victoria "
        answers["wfh"] = {
            "start": "2026-06-08",
            "end": "2026-06-08",
            "weekdays": [0],
            "hours_per_day": 8,
            "records": "timesheet",
            "actual_cost_records": "none",
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        wfh = next(row for row in payload["items"] if row["number"] == "WFH")

        self.assertIn("0.00 hours", wfh["answer"])

    def test_unknown_wfh_state_remains_evidence(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "state": "unknown place",
                "start": "2026-06-08",
                "end": "2026-06-08",
                "weekdays": [0],
                "hours_per_day": 8,
                "records": "timesheet",
                "actual_cost_records": "none",
                "leave_dates": [],
                "worked_public_holidays": [],
                "worked_weekends": [],
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_missing_period_remains_evidence(self) -> None:
        for omitted_key in ["start", "end"]:
            with self.subTest(omitted_key=omitted_key):
                raw = {
                    "state": "VIC",
                    "start": "2025-07-01",
                    "end": "2026-06-30",
                    "weekdays": [0, 1, 2, 3, 4],
                    "hours_per_day": 8,
                    "records": "timesheet",
                    "actual_cost_records": "none",
                }
                del raw[omitted_key]

                rows = taxmate_intake.wfh_rows(raw)

                self.assertEqual("Evidence", rows[0]["status"])
                self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_weekday_names_parse_without_zeroing_hours(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "state": "VIC",
                "start": "2026-06-09",
                "end": "2026-06-10",
                "weekdays": ["Tuesday", "Wednesday"],
                "hours_per_day": 8,
                "records": "timesheet",
                "actual_cost_records": "none",
                "leave_dates": [],
                "worked_public_holidays": [],
                "worked_weekends": [],
            }
        )

        self.assertEqual("Accountant review", rows[0]["status"])
        self.assertIn("16.00 hours; fixed-rate candidate 11.20", rows[0]["answer"])

    def test_wfh_unparseable_weekdays_remain_evidence(self) -> None:
        for weekdays in [["Monday", "Funday"], [], [7], [True]]:
            with self.subTest(weekdays=weekdays):
                rows = taxmate_intake.wfh_rows(
                    {
                        "state": "VIC",
                        "start": "2026-06-09",
                        "end": "2026-06-10",
                        "weekdays": weekdays,
                        "hours_per_day": 8,
                        "records": "timesheet",
                        "actual_cost_records": "none",
                    }
                )

                self.assertEqual("Evidence", rows[0]["status"])
                self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_unparseable_adjustment_dates_remain_evidence(self) -> None:
        for key in ["leave_dates", "worked_public_holidays", "worked_weekends"]:
            with self.subTest(key=key):
                raw = {
                    "state": "VIC",
                    "start": "2026-06-09",
                    "end": "2026-06-10",
                    "weekdays": [1, 2],
                    "hours_per_day": 8,
                    "records": "timesheet",
                    "actual_cost_records": "none",
                    "leave_dates": [],
                    "worked_public_holidays": [],
                    "worked_weekends": [],
                }
                raw[key] = ["not-a-date"]

                rows = taxmate_intake.wfh_rows(raw)

                self.assertEqual("Evidence", rows[0]["status"])
                self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_adjustment_dates_must_be_explicit(self) -> None:
        for key in ["leave_dates", "worked_public_holidays", "worked_weekends"]:
            with self.subTest(key=key):
                raw = {
                    "state": "VIC",
                    "start": "2026-06-09",
                    "end": "2026-06-10",
                    "weekdays": [1, 2],
                    "hours_per_day": 8,
                    "records": "timesheet",
                    "actual_cost_records": "none",
                    "leave_dates": [],
                    "worked_public_holidays": [],
                    "worked_weekends": [],
                }
                del raw[key]

                rows = taxmate_intake.wfh_rows(raw)

                self.assertEqual("Evidence", rows[0]["status"])
                self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_adjustment_dates_must_match_category(self) -> None:
        cases = [
            ("leave outside period", {"leave_dates": ["2026-07-01"]}),
            ("leave on non-workday", {"leave_dates": ["2026-06-13"]}),
            ("worked public holiday on non-holiday", {"worked_public_holidays": ["2026-06-09"]}),
            ("worked weekend on weekday", {"worked_weekends": ["2026-06-09"]}),
        ]
        for label, updates in cases:
            with self.subTest(label=label):
                raw = {
                    "state": "VIC",
                    "start": "2026-06-09",
                    "end": "2026-06-14",
                    "weekdays": [1, 2, 3, 4],
                    "hours_per_day": 8,
                    "records": "timesheet",
                    "actual_cost_records": "none",
                    "leave_dates": [],
                    "worked_public_holidays": [],
                    "worked_weekends": [],
                }
                raw.update(updates)

                rows = taxmate_intake.wfh_rows(raw)

                self.assertEqual("Evidence", rows[0]["status"])
                self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_invalid_daily_hours_remain_evidence(self) -> None:
        for hours_per_day in [0, -8, 25]:
            with self.subTest(hours_per_day=hours_per_day):
                rows = taxmate_intake.wfh_rows(
                    {
                        "state": "VIC",
                        "start": "2026-06-09",
                        "end": "2026-06-10",
                        "weekdays": [1, 2],
                        "hours_per_day": hours_per_day,
                        "records": "timesheet",
                        "actual_cost_records": "none",
                        "leave_dates": [],
                        "worked_public_holidays": [],
                        "worked_weekends": [],
                    }
                )

                self.assertEqual("Evidence", rows[0]["status"])
                self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_missing_records_block_fixed_rate_candidate(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "state": "VIC",
                "start": "2026-06-09",
                "end": "2026-06-10",
                "weekdays": [1, 2],
                "hours_per_day": 8,
                "actual_cost_records": "none",
                "leave_dates": [],
                "worked_public_holidays": [],
                "worked_weekends": [],
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("16.00 hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_missing_actual_cost_records_stays_evidence(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "state": "VIC",
                "start": "2026-06-09",
                "end": "2026-06-10",
                "weekdays": [1, 2],
                "hours_per_day": 8,
                "records": "timesheet",
                "leave_dates": [],
                "worked_public_holidays": [],
                "worked_weekends": [],
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("16.00 hours; fixed-rate candidate 11.20; actual-cost records unknown", rows[0]["answer"])

    def test_intake_cli_keeps_unparseable_wfh_as_evidence(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["wfh"] = {
            "state": "VIC",
            "start": "2026-06-09",
            "end": "2026-06-10",
            "weekdays": ["Funday"],
            "hours_per_day": 8,
            "records": "timesheet",
            "actual_cost_records": "none",
        }
        with tempfile.TemporaryDirectory() as tmp:
            answers_path = Path(tmp) / "answers.json"
            output_path = Path(tmp) / "pack.html"
            answers_path.write_text(json.dumps(answers), encoding="utf-8")

            result = taxmate_intake.main(["individual", "--answers", str(answers_path), "--output", str(output_path)])

            self.assertEqual(0, result)
            body = output_path.read_text(encoding="utf-8")
            self.assertIn("unknown hours; fixed-rate candidate unknown", body)
            self.assertNotIn("0.00 hours; fixed-rate candidate 0.00", body)

    def test_wfh_unknown_hours_remain_evidence(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "state": "VIC",
                "start": "2026-06-09",
                "end": "2026-06-09",
                "weekdays": [1],
                "hours_per_day": "not sure",
                "records": "timesheet",
                "actual_cost_records": "unknown",
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_invalid_period_remains_evidence(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "state": "VIC",
                "start": "not a date",
                "end": "2026-06-09",
                "weekdays": [1],
                "hours_per_day": 8,
                "records": "timesheet",
                "actual_cost_records": "none",
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_wfh_missing_weekdays_remain_evidence(self) -> None:
        rows = taxmate_intake.wfh_rows(
            {
                "state": "VIC",
                "start": "2026-06-09",
                "end": "2026-06-09",
                "hours_per_day": 8,
                "records": "timesheet",
                "actual_cost_records": "none",
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("unknown hours; fixed-rate candidate unknown", rows[0]["answer"])

    def test_intake_rows_use_generation_checked_at(self) -> None:
        row = taxmate_intake.guide_row("N", "Area", "Question", "Answer", "Why", "Used", "https://example.test")

        self.assertEqual(taxmate_intake.generation_checked_at(), row["checked_at"])

    def test_monitor_over_300_is_not_full_immediate_claim(self) -> None:
        rows = taxmate_intake.asset_rows(
            [
                {
                    "description": "$400 monitor",
                    "cost": 400,
                    "work_use_percent": 80,
                    "method_preference": "depreciation",
                    "evidence": "receipt",
                }
            ]
        )

        self.assertEqual(rows[0]["status"], "Accountant review")
        self.assertIn("work-use amount 320.00", rows[0]["answer"])
        self.assertIn("not full immediate claim", rows[0]["answer"])

    def test_low_cost_mixed_use_asset_stays_review(self) -> None:
        rows = taxmate_intake.asset_rows(
            [
                {
                    "description": "$250 monitor",
                    "cost": 250,
                    "work_use_percent": 80,
                    "method_preference": "immediate",
                    "evidence": "receipt",
                }
            ]
        )

        self.assertEqual("Accountant review", rows[0]["status"])
        self.assertIn("mixed-use", rows[0]["answer"])

    def test_bas_worksheet_calculates_totals_and_stays_review(self) -> None:
        rows = taxmate_intake.bas_rows(
            {
                "gst_registered": True,
                "gst_collected": 300,
                "gst_credits": 110,
            }
        )

        self.assertEqual(rows[0]["status"], "Accountant review")
        self.assertIn("net GST 190.00", rows[0]["answer"])
        self.assertIn("BAS worksheet only", rows[0]["why_included"])

    def test_bas_amounts_stay_review_when_registration_flag_missing(self) -> None:
        rows = taxmate_intake.bas_rows({"gst_collected": 300, "gst_credits": 110})

        self.assertEqual("Accountant review", rows[0]["status"])

    def test_unknown_gst_registration_keeps_bas_visible(self) -> None:
        rows = taxmate_intake.bas_rows({"gst_registered": "not sure"})

        self.assertEqual("Accountant review", rows[0]["status"])
        self.assertIn("1A unknown; 1B unknown; net GST unknown", rows[0]["answer"])

    def test_gst_registration_strings_do_not_skip_bas_review(self) -> None:
        for value in ["yes", "true", "registered", "maybe"]:
            with self.subTest(value=value):
                rows = taxmate_intake.bas_rows({"gst_registered": value})

                self.assertEqual("Accountant review", rows[0]["status"])
                self.assertIn("1A unknown; 1B unknown; net GST unknown", rows[0]["answer"])

        rows = taxmate_intake.bas_rows({"gst_registered": "no"})
        self.assertEqual("N/A skipped", rows[0]["status"])

    def test_zero_amount_abn_answers_stay_review(self) -> None:
        rows = taxmate_intake.abn_rows({"abn_income": 0, "abn_expenses": 0})

        self.assertEqual("Accountant review", rows[0]["status"])

    def test_abn_and_bas_base_answers_stay_review(self) -> None:
        rows = taxmate_intake.base_items(taxmate_intake.sample_answers())
        by_number = {row["number"]: row for row in rows}

        self.assertEqual("Accountant review", by_number["abn_income"]["status"])
        self.assertEqual("Accountant review", by_number["gst_collected"]["status"])
        self.assertEqual("Accountant review", by_number["gst_credits"]["status"])

    def test_non_finite_intake_money_rejected(self) -> None:
        for raw in ["nan", "inf", "-inf"]:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    taxmate_intake.money(raw)

    def test_unparseable_intake_money_is_not_zeroed(self) -> None:
        with self.assertRaises(ValueError):
            taxmate_intake.money("not sure")

        bas = taxmate_intake.bas_rows({"gst_collected": "unknown", "gst_credits": 110})
        asset = taxmate_intake.asset_rows(
            [{"description": "monitor", "cost": "unknown receipt", "work_use_percent": 80}]
        )

        self.assertEqual("Accountant review", bas[0]["status"])
        self.assertIn("1A unknown; 1B 110.00; net GST unknown", bas[0]["answer"])
        self.assertEqual("Evidence", asset[0]["status"])
        self.assertIn("Cost unknown; work use 80%; work-use amount unknown", asset[0]["answer"])

    def test_embedded_unconfirmed_answers_create_evidence_rows(self) -> None:
        rows = taxmate_intake.evidence_rows(taxmate_intake.sample_answers())

        self.assertTrue(any(row["ato_area"] == "M2 / Private health" for row in rows))

    def test_individual_html_pack_has_print_boundary_sections(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Manual copy only", body)
        self.assertIn("AI extraction confirmation table", body)
        self.assertIn("ABN prep section", body)
        self.assertIn("BAS worksheet", body)
        self.assertIn("Missing facts queue", body)
        self.assertIn("Evidence queue", body)
        self.assertIn("Source/provenance appendix", body)
        self.assertNotIn("lodgment-ready", body)
        self.assertNotIn("Prepared by " + "TaxMate", body)

    def test_extended_review_rows_appear_in_tabs_and_queue(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["abn_income"] = 1000
        answers["gst_registered"] = True
        answers["gst_collected"] = 110
        answers["gst_credits"] = 55

        payload = taxmate_intake.answers_to_pack_payload(answers)
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn('data-target="row-201-ABN"', body)
        self.assertIn('data-target="row-301-BAS"', body)
        self.assertIn("ABN figures are prep-only and not a final business schedule.", body)
        self.assertIn("BAS prep only. No BAS lodgment support.", body)


class FinanceTests(unittest.TestCase):
    def test_csv_reader_trims_quoted_values_and_parentheses(self) -> None:
        body = 'date,description,amount,gst,owner\n2026-01-01, "Desk",($120.50),$10.95,owner\n'

        rows = taxmate_finance.read_csv(io.StringIO(body))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].description, "Desk")
        self.assertEqual(rows[0].amount, -120.50)
        self.assertEqual(rows[0].gst, 10.95)
        self.assertEqual(rows[0].direction, "expense")

    def test_csv_rejects_non_finite_money(self) -> None:
        body = "date,description,amount,gst\n2026-01-01,Bad,nan,0\n"

        with self.assertRaises(ValueError):
            taxmate_finance.read_csv(io.StringIO(body))

    def test_csv_rejects_malformed_money(self) -> None:
        body = "date,description,amount,gst\n2026-01-01,Bad,N/A,0\n"

        with self.assertRaises(ValueError):
            taxmate_finance.read_csv(io.StringIO(body))

    def test_csv_prefers_amount_without_parsing_unused_debit_credit(self) -> None:
        body = "date,description,amount,debit,credit,gst\n2026-01-01,Desk,-120.50,N/A,-,0\n"

        rows = taxmate_finance.read_csv(io.StringIO(body))

        self.assertEqual(rows[0].amount, -120.50)
        self.assertEqual(rows[0].direction, "expense")

    def test_csv_credit_fallback_ignores_debit_placeholder(self) -> None:
        body = "date,description,debit,credit,gst\n2026-01-01,Refund,N/A,120.50,0\n"

        rows = taxmate_finance.read_csv(io.StringIO(body))

        self.assertEqual(rows[0].amount, 120.50)
        self.assertEqual(rows[0].direction, "income")

    def test_csv_fallback_rejects_malformed_debit_even_with_credit(self) -> None:
        body = "date,description,debit,credit,gst\n2026-01-01,Refund,bad,120.50,0\n"

        with self.assertRaises(ValueError):
            taxmate_finance.read_csv(io.StringIO(body))

    def test_csv_fallback_rejects_malformed_credit_even_with_debit(self) -> None:
        body = "date,description,debit,credit,gst\n2026-01-01,Desk,120.50,bad,0\n"

        with self.assertRaises(ValueError):
            taxmate_finance.read_csv(io.StringIO(body))

    def test_csv_optional_gst_units_placeholders_are_zero(self) -> None:
        body = "date,description,amount,gst,units\n2026-01-01,Desk,-120.50,N/A,-\n"

        rows = taxmate_finance.read_csv(io.StringIO(body))

        self.assertEqual(rows[0].gst, 0)
        self.assertEqual(rows[0].units, 0)

    def test_private_health_classifies_before_income(self) -> None:
        tx = taxmate_finance.Transaction(
            row=2,
            description="Private health premium",
            amount=120,
            direction="income",
            category="private health",
        )

        finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)

        self.assertEqual(finding.bucket, "private_health")
        self.assertEqual(finding.tax_treatment, "tax_return_info_only")
        self.assertTrue(finding.accountant_review)

    def test_investment_income_outranks_business_tag(self) -> None:
        tx = taxmate_finance.Transaction(
            row=2,
            description="ETF dividend distribution",
            amount=50,
            direction="income",
            purpose="business records",
            abn="12345678901",
            asset="ETF",
            units=10,
        )

        finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)

        self.assertEqual(finding.bucket, "investment_income")
        self.assertEqual(finding.tax_treatment, "tax_statement_record")

    def test_business_gst_requires_invoice_support(self) -> None:
        tx = taxmate_finance.Transaction(
            row=2,
            description="API subscription",
            amount=-110,
            gst=10,
            direction="expense",
            purpose="ABN app business",
            evidence="card statement",
        )

        finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)

        self.assertEqual(finding.bucket, "abn_business_software")
        self.assertTrue(finding.gst_credit_candidate)
        self.assertIn("valid tax invoice", finding.records_needed)

    def test_business_wfh_stays_business_review(self) -> None:
        tx = taxmate_finance.Transaction(
            row=2,
            description="Home internet",
            amount=-80,
            gst=-7.27,
            direction="expense",
            abn="12345678901",
            purpose="ABN app business",
            evidence="tax invoice",
        )

        finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)

        self.assertEqual(finding.bucket, "abn_business_home_office")
        self.assertEqual(finding.tax_treatment, "accountant_review")
        self.assertTrue(finding.gst_credit_candidate)
        self.assertEqual(finding.gst_credit_amount, 7.27)

    def test_health_flags_negative_gst_candidate_without_invoice(self) -> None:
        tx = taxmate_finance.Transaction(
            row=2,
            description="Home internet",
            amount=-80,
            gst=-7.27,
            direction="expense",
            abn="12345678901",
            purpose="ABN app business",
            evidence="card statement",
        )
        finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)

        checks = {check.name: check for check in taxmate_finance.health([tx], [finding])}

        self.assertTrue(finding.gst_credit_candidate)
        self.assertFalse(checks["gst_tax_invoice_support"].passed)
        self.assertEqual(checks["gst_tax_invoice_support"].rows, [2])

    def test_business_entertainment_stays_accountant_review(self) -> None:
        tx = taxmate_finance.Transaction(
            row=2,
            description="Client restaurant meal",
            amount=-140,
            direction="expense",
            abn="12345678901",
            purpose="ABN business development",
            evidence="tax invoice",
        )

        finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)

        self.assertEqual(finding.bucket, "business_entertainment_fbt")
        self.assertEqual(finding.tax_treatment, "accountant_review")
        self.assertTrue(finding.accountant_review)

    def test_health_check_flags_duplicate_rows(self) -> None:
        tx1 = taxmate_finance.Transaction(
            row=2,
            date="2026-01-01",
            description="API",
            amount=-10,
            evidence="invoice",
        )
        tx2 = taxmate_finance.Transaction(
            row=3,
            date="2026-01-01",
            description="API",
            amount=-10,
            evidence="invoice",
        )
        findings = [
            taxmate_finance.classify(tx1, taxmate_finance.ModeStrict),
            taxmate_finance.classify(tx2, taxmate_finance.ModeStrict),
        ]

        checks = {check.name: check for check in taxmate_finance.health([tx1, tx2], findings)}

        self.assertFalse(checks["duplicate_scan"].passed)
        self.assertEqual(checks["duplicate_scan"].rows, [2, 3])


class SourceHelperTests(unittest.TestCase):
    def run_fetch_with_curl(
        self,
        status: int,
        final_url: str,
        body: bytes,
        returncode: int = 0,
        stderr: bytes = b"",
    ) -> atodata.FetchResult:
        original_run = atodata.subprocess.run

        def fake_run(command, **_kwargs):
            self.assertEqual(command[0], "curl")
            self.assertEqual(command[1], "--disable")
            self.assertEqual(command[2], "-L")
            output_path = command[command.index("--output") + 1]
            Path(output_path).write_bytes(body)
            stdout = f"{status}\n{final_url}".encode("utf-8")
            return subprocess.CompletedProcess(command, returncode, stdout, stderr)

        atodata.subprocess.run = fake_run
        try:
            return atodata.Fetch("https://www.ato.gov.au/start")
        finally:
            atodata.subprocess.run = original_run

    def test_fetch_uses_curl_and_preserves_200_body(self) -> None:
        fetched = self.run_fetch_with_curl(200, "https://www.ato.gov.au/start", b"<html>ok</html>")

        self.assertEqual(fetched.status, 200)
        self.assertEqual(fetched.final_url, "https://www.ato.gov.au/start")
        self.assertEqual(fetched.body, b"<html>ok</html>")

    def test_fetch_preserves_redirect_final_url(self) -> None:
        fetched = self.run_fetch_with_curl(200, "https://www.ato.gov.au/final", b"redirected")

        self.assertEqual(fetched.status, 200)
        self.assertEqual(fetched.final_url, "https://www.ato.gov.au/final")
        self.assertEqual(fetched.body, b"redirected")

    def test_fetch_preserves_404_status_and_body(self) -> None:
        fetched = self.run_fetch_with_curl(404, "https://www.ato.gov.au/missing", b"not found")

        self.assertEqual(fetched.status, 404)
        self.assertEqual(fetched.final_url, "https://www.ato.gov.au/missing")
        self.assertEqual(fetched.body, b"not found")

    def test_fetch_network_failure_uses_curl_error(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Could not resolve host"):
            self.run_fetch_with_curl(
                0,
                "",
                b"",
                returncode=6,
                stderr=b"curl: (6) Could not resolve host: www.ato.gov.au",
            )

    def test_clean_text_removes_scripts_and_unescapes_html(self) -> None:
        body = b"<main>Claim &amp; keep<script>bad()</script><style>x{}</style> records</main>"

        self.assertEqual(atodata.clean_text(body), "Claim & keep records")

    def test_select_by_url_matches_original_and_final_urls(self) -> None:
        records = [
            atodata.SourceRecord(
                url="https://www.ato.gov.au/a",
                final_url="https://www.ato.gov.au/final",
                status=200,
                title="",
                last_updated="",
                raw_file="",
                text_file="",
            ),
        ]

        selected, missing = atodata.select_by_url(
            records,
            ["https://www.ato.gov.au/final", "https://www.ato.gov.au/missing"],
        )

        self.assertEqual(selected, records)
        self.assertEqual(missing, ["https://www.ato.gov.au/missing"])

    def test_discover_links_filters_to_approved_ato_paths(self) -> None:
        body = b"""
        <a href="/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/">ok</a>
        <a href="https://example.com/individuals-and-families/income-deductions-offsets-and-records">bad host</a>
        <a href="/unrelated">bad path</a>
        """

        links = atodata.discover_links("https://www.ato.gov.au/start", body)

        self.assertEqual(
            links,
            ["https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim"],
        )


class SkillGenerationTests(unittest.TestCase):
    def test_canonical_url_strips_query_fragment_and_trailing_slash(self) -> None:
        self.assertEqual(
            skillgen.canonicalURL("https://www.ATO.gov.au/path/to/?utm=1#section"),
            "https://www.ato.gov.au/path/to",
        )

    def test_current_value_validation_requires_verified_source(self) -> None:
        value = skillgen.ValueFact(
            topic="work-from-home",
            value="70 cents",
            unit="cents",
            context="2025-26 fixed rate 70 cents",
            jurisdiction="Australia",
            income_year="2025-26",
            source_url="https://www.ato.gov.au/example",
            source_title="Example",
            checked_at="2026-06-27T00:00:00Z",
            content_hash="a" * 64,
        )

        self.assertIsNone(skillgen.ValidateCurrentValue(value, "2025-26", True))
        with self.assertRaises(RuntimeError):
            skillgen.ValidateCurrentValue(value, "2025-26", False)

    def test_runtime_only_skills_have_guardrails(self) -> None:
        self.assertIsNone(skillgen.validateRuntimeOnlySkills(str(ROOT)))

    def test_generated_topic_frontmatter_is_portable_skill_shape(self) -> None:
        body = skillgen.skillMarkdown(skillgen.Topics()[0])
        frontmatter = taxmate_validate.parse_frontmatter(body)

        self.assertIsNotNone(frontmatter)
        self.assertEqual(frontmatter["name"], skillgen.Topics()[0].slug)
        self.assertIn("Use for", frontmatter["description"])
        self.assertIn("Claude Code", frontmatter["compatibility"])
        self.assertIn("Cowork", frontmatter["compatibility"])

    def test_source_coverage_error_is_returned_not_thrown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "data", "ato_knowledge_base").mkdir(parents=True)
            Path(tmp, "data", "ato_knowledge_base", "source_coverage.json").write_text("{}", encoding="utf-8")

            err = skillgen.ValidateSourceCoverage(tmp)

        self.assertIsInstance(err, RuntimeError)


class ValidatorAndCliTests(unittest.TestCase):
    def test_parse_frontmatter_requires_valid_block(self) -> None:
        self.assertEqual(taxmate_validate.parse_frontmatter("---\nname: sample\n---\nBody\n"), {"name": "sample"})
        self.assertIsNone(taxmate_validate.parse_frontmatter("name: sample\nBody\n"))

    def test_claude_skill_frontmatter_issues_catches_bad_skill_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "bad_skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\n"
                "name: Bad Skill\n"
                "description: Helps things.\n"
                "compatibility: x\n"
                "---\n"
                "# Bad\n",
                encoding="utf-8",
            )

            issues = taxmate_validate.claude_skill_frontmatter_issues(tmp)

        self.assertTrue(any("name must match folder" in issue for issue in issues))
        self.assertTrue(any("name must be kebab-case" in issue for issue in issues))
        self.assertTrue(any("description missing use trigger" in issue for issue in issues))

    def test_skill_dirs_without_skill_md_catches_orphan_skill_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            orphan = Path(tmp) / "skills" / "research" / "agents"
            orphan.mkdir(parents=True)
            (orphan / "openai.yaml").write_text("interface: {}\n", encoding="utf-8")

            missing = taxmate_validate.skill_dirs_without_skill_md(tmp)

        self.assertEqual(missing, ["skills/research"])

    def test_validate_json_uses_check_field(self) -> None:
        self.assertTrue(taxmate_validate.validate_json_uses_check_field())

    def test_launcher_finds_repo_root_from_explicit_env(self) -> None:
        original = taxmate.os.environ.get("TAXMATE_AUSTRALIA_ROOT")
        taxmate.os.environ["TAXMATE_AUSTRALIA_ROOT"] = str(ROOT)
        try:
            self.assertEqual(taxmate._find_repo_root(Path("/tmp")), ROOT)
        finally:
            if original is None:
                taxmate.os.environ.pop("TAXMATE_AUSTRALIA_ROOT", None)
            else:
                taxmate.os.environ["TAXMATE_AUSTRALIA_ROOT"] = original

    def test_launcher_exposes_taxpack_command(self) -> None:
        self.assertEqual(taxmate.COMMANDS["taxpack"], "taxmate_taxpack.py")

    def test_finish_report_has_check_names(self) -> None:
        checks = [{"check": "sample", "passed": True, "detail": ""}]

        report, ok = taxmate_validate.finish(str(ROOT), checks, None, False)

        self.assertTrue(ok)
        self.assertEqual(report["checks"], checks)
        self.assertEqual(report["score"], 100)

    def test_codex_environment_toml_valid(self) -> None:
        self.assertTrue(taxmate_validate.codex_environment_toml_valid(str(ROOT)))

    def test_codex_environment_toml_rejects_malformed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_dir = Path(tmp) / ".codex" / "environments"
            env_dir.mkdir(parents=True)
            (env_dir / "environment.toml").write_text(
                '\n'.join(
                    [
                        "version = 1",
                        "[setup]",
                        'script = "bash scripts/codex-env-setup.sh"',
                        "[cleanup]",
                        'script = "bash scripts/codex-env-cleanup.sh"',
                        "[[actions]]",
                        'name = "Full check',
                        'icon = "tool"',
                        'command = "bash scripts/codex-env-full-check.sh"',
                    ]
                ),
                encoding="utf-8",
            )

            self.assertFalse(taxmate_validate.codex_environment_toml_valid(tmp))

    def test_gitleaks_has_no_broad_cache_allowlist(self) -> None:
        self.assertTrue(taxmate_validate.gitleaks_no_broad_cache_allowlist(str(ROOT)))

    def test_release_workflow_auto_runs_after_green_ci(self) -> None:
        self.assertTrue(taxmate_validate.release_workflow_auto_after_ci(str(ROOT)))

    def test_release_workflow_rejects_manual_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            workflow = tmp_root / ".github" / "workflows" / "release.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                (ROOT / ".github" / "workflows" / "release.yml")
                .read_text(encoding="utf-8")
                .replace(
                    '  workflow_run:\n    workflows: ["CI"]\n    types: [completed]\n    branches: [main]\n',
                    "",
                ),
                encoding="utf-8",
            )

            self.assertFalse(taxmate_validate.release_workflow_auto_after_ci(tmp))

    def test_release_workflow_rejects_privileged_head_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            workflow = tmp_root / ".github" / "workflows" / "release.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                (ROOT / ".github" / "workflows" / "release.yml")
                .read_text(encoding="utf-8")
                .replace(
                    "      - name: Require green CI\n",
                    "      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683\n"
                    "        with:\n"
                    "          ref: ${{ steps.target.outputs.sha }}\n"
                    "      - name: Require green CI\n",
                ),
                encoding="utf-8",
            )

            self.assertFalse(taxmate_validate.release_workflow_auto_after_ci(tmp))

    def test_release_workflow_requires_gh_repo_without_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            workflow = tmp_root / ".github" / "workflows" / "release.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                (ROOT / ".github" / "workflows" / "release.yml")
                .read_text(encoding="utf-8")
                .replace("          GH_REPO: nijanthan-dev/taxmate-australia\n", ""),
                encoding="utf-8",
            )

            self.assertFalse(taxmate_validate.release_workflow_auto_after_ci(tmp))

    def test_release_config_tracks_manifest_versions(self) -> None:
        self.assertTrue(taxmate_validate.release_config_tracks_manifest_versions(str(ROOT)))

    def test_release_config_requires_bootstrap_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            for rel in [
                "release-please-config.json",
                ".release-please-manifest.json",
                ".codex-plugin/plugin.json",
                "skill.json",
                "plugin.lock.json",
            ]:
                src = ROOT / rel
                dst = tmp_root / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)

            config_path = tmp_root / "release-please-config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config.pop("bootstrap-sha", None)
            config_path.write_text(json.dumps(config), encoding="utf-8")

            self.assertFalse(taxmate_validate.release_config_tracks_manifest_versions(str(tmp_root)))

    def test_ato_endorsement_scan_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text("This is ATO-backed tax prep.\n", encoding="utf-8")

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, ["README.md:ATO-backed"])

    def test_ato_endorsement_scan_includes_discovery_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            discovery = Path(tmp) / "docs" / "DISCOVERY.md"
            discovery.parent.mkdir(parents=True)
            discovery.write_text("TaxMate is backed by ATO.\n", encoding="utf-8")

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, ["docs/DISCOVERY.md:backed by ATO"])

    def test_ato_endorsement_scan_includes_all_wrapper_skills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wrapper = Path(tmp) / "wrappers" / "taxmate-australia-extra" / "SKILL.md"
            wrapper.parent.mkdir(parents=True)
            wrapper.write_text("description: ATO-supported workflow.\n", encoding="utf-8")

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, ["wrappers/taxmate-australia-extra/SKILL.md:ATO-supported"])

    def test_ato_endorsement_scan_includes_skill_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "skill.json"
            manifest.write_text('{"description":"ATO partner"}\n', encoding="utf-8")

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, ["skill.json:ATO partner"])

    def test_ato_endorsement_scan_blocks_verb_before_ato(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "TaxMate is endorsed by ATO and approved by the Australian Taxation Office.\n",
                encoding="utf-8",
            )

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(
            hits,
            [
                "README.md:endorsed by ATO",
                "README.md:approved by the Australian Taxation Office",
            ],
        )

    def test_ato_endorsement_scan_blocks_related_endorsement_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "\n".join(
                    [
                        "TaxMate is sponsored by ATO.",
                        "TaxMate is certified by the Australian Taxation Office.",
                        "TaxMate is authorised by the ATO.",
                        "TaxMate is authorized by ATO.",
                        "TaxMate is partnered with ATO.",
                        "TaxMate is in partnership with the ATO.",
                        "TaxMate is ATO-certified.",
                        "TaxMate is Australian Taxation Office approved.",
                        "TaxMate is an official Australian Taxation Office partner.",
                    ]
                ),
                encoding="utf-8",
            )

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(
            hits,
            [
                "README.md:sponsored by ATO",
                "README.md:certified by the Australian Taxation Office",
                "README.md:authorised by the ATO",
                "README.md:authorized by ATO",
                "README.md:partnered with ATO",
                "README.md:in partnership with the ATO",
                "README.md:Australian Taxation Office approved",
                "README.md:ATO-certified",
                "README.md:Australian Taxation Office partner",
                "README.md:official Australian Taxation Office partner",
            ],
        )

    def test_ato_endorsement_scan_allows_negated_disclaimer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "TaxMate is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office.\n",
                encoding="utf-8",
            )

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, [])

    def test_ato_endorsement_scan_blocks_unrelated_negation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "TaxMate is not only accountant-ready, it is ATO-backed.\n",
                encoding="utf-8",
            )

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, ["README.md:ATO-backed"])

    def test_ato_endorsement_scan_blocks_contrasted_negation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "TaxMate is not affiliated with ATO but ATO-approved.\n",
                encoding="utf-8",
            )

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, ["README.md:ATO-approved"])


class TaxpackGuideTests(unittest.TestCase):
    def test_sample_guide_uses_current_generated_date(self) -> None:
        self.assertNotIn("generated_date", taxmate_taxpack.sample_payload())
        self.assertEqual(
            taxmate_taxpack.default_generated_date(),
            taxmate_taxpack.load_guide_data(None).generated_date,
        )

    def test_sample_guide_matches_approved_tab_contract(self) -> None:
        data = taxmate_taxpack.load_guide_data(None)

        body = taxmate_taxpack.render_html(data)

        self.assertIn("Self-prepared guide PDF", body)
        self.assertIn("Prepared by user", body)
        self.assertIn("Not an ATO form", body)
        self.assertIn("Not fileable", body)
        self.assertIn("Prep boundary", body)
        self.assertIn("--bg:#e9eef4", body)
        self.assertIn("background:#fff0f1", body)
        self.assertIn("background:#eef5ff", body)
        self.assertIn("background:#effbf4", body)
        self.assertIn("background:#fff7dc", body)
        self.assertIn("left:-64px", body)
        self.assertIn("spotlight-target", body)
        self.assertIn("show all tabs", body.lower())
        self.assertIn("hide tabs", body.lower())
        self.assertIn("Tax items and review flags", body)
        self.assertIn("ATO-aligned manual copy worksheet", body)
        self.assertIn("<th>Source</th>", body)
        self.assertIn("source-url", body)
        self.assertIn("Checked 2026-06-23T09:04:57Z", body)
        self.assertNotIn("Deductions and review flags", body)
        self.assertNotIn("ATO-aligned deduction worksheet", body)
        self.assertNotIn("target-dot", body)
        self.assertNotIn("border-radius:50%", body)
        self.assertNotIn("Global warning", body)
        self.assertNotIn("Prepared by " + "TaxMate", body)

    def test_guide_tabs_resolve_to_existing_anchors(self) -> None:
        data = taxmate_taxpack.load_guide_data(None)
        body = taxmate_taxpack.render_html(data)
        targets = set(re.findall(r'data-target="([^"]+)"', body))
        anchors = set(re.findall(r'data-anchor="([^"]+)"', body))

        self.assertTrue(targets)
        self.assertEqual(set(), targets - anchors)
        self.assertIn("function findTarget", body)
        self.assertNotIn("querySelector('[data-anchor=\"'+tab.dataset.target", body)

    def test_guide_does_not_query_user_controlled_anchor_selectors(self) -> None:
        item = taxmate_taxpack.guide_item(
            {
                "number": "D\"1",
                "ato_area": "Other",
                "question": "Quoted number?",
                "answer": "User-entered value",
                "why_included": "Selector escape regression.",
                "status": "Evidence",
                "tab_text": "Quoted row number should not break tabs.",
            }
        )
        data = taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date="28 Jun 2026",
            summary_note="Selector regression.",
            items=[item],
        )

        body = taxmate_taxpack.render_html(data)

        self.assertIn('data-anchor="row-1-D&quot;1"', body)
        self.assertIn('data-target="row-1-D&quot;1"', body)
        self.assertIn("findTarget(spread,tab.dataset.target)", body)
        self.assertNotIn("tab.dataset.target+'", body)

    def test_guide_anchors_stay_unique_for_duplicate_item_numbers(self) -> None:
        item_payload = {
            "number": "D1",
            "ato_area": "Other",
            "question": "Duplicate number?",
            "answer": "User-entered value",
            "why_included": "Duplicate anchor regression.",
            "status": "Evidence",
            "tab_text": "Duplicate row should keep its own target.",
        }
        data = taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date="28 Jun 2026",
            summary_note="Duplicate regression.",
            items=[
                taxmate_taxpack.guide_item(item_payload),
                taxmate_taxpack.guide_item(item_payload),
            ],
        )

        body = taxmate_taxpack.render_html(data)
        row_anchors = re.findall(r'<td data-anchor="([^"]+)"', body)
        row_targets = [
            target
            for target in re.findall(r'<div class="tab [^"]+" data-target="([^"]+)"', body)
            if target.startswith("row-")
        ]

        self.assertEqual(["row-1-D1", "row-2-D1"], row_anchors)
        self.assertEqual(["row-1-D1", "row-2-D1"], row_targets)
        self.assertEqual(len(row_anchors), len(set(row_anchors)))

    def test_custom_guide_input_escapes_values_and_shortens_status(self) -> None:
        payload = {
            "income_year": "2025-26",
            "generated_date": "28 Jun 2026",
            "items": [
                {
                    "number": "9",
                    "ato_area": "Other <area>",
                    "question": "Need review?",
                    "answer": "User says <yes>",
                    "why_included": "Complex & mixed-use.",
                    "status": "Accountant review",
                    "status_kind": "accountant_review",
                    "tab_title": "Row 9 review",
                    "tab_text": "Review before copying.",
                    "tab_kind": "review",
                }
            ],
        }

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            json.dump(payload, handle)
            input_path = handle.name
        try:
            data = taxmate_taxpack.load_guide_data(input_path)
        finally:
            Path(input_path).unlink()

        body = taxmate_taxpack.render_html(data)

        self.assertIn("Other &lt;area&gt;", body)
        self.assertIn("User says &lt;yes&gt;", body)
        self.assertIn("<span class=\"status review-badge\">Accountant review</span>", body)

    def test_direct_taxpack_ai_used_requires_literal_confirmation(self) -> None:
        payload = {
            "income_year": "2025-26",
            "generated_date": "28 Jun 2026",
            "items": [
                {
                    "number": "1",
                    "ato_area": "Salary",
                    "question": "PAYG gross",
                    "answer": "100",
                    "why_included": "Base row.",
                    "status": "Evidence",
                }
            ],
            "extracted_values": [
                {"number": "AI1", "field": "gross", "value": "100", "status": "Used"},
                {"number": "AI2", "field": "tax", "value": "30", "status": "Used", "confirmed": True},
                {"number": "AI3", "field": "review", "value": "x", "status": "Accountant review", "confirmed": True},
            ],
        }

        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("<td>AI1</td><td></td><td></td><td>gross</td><td>100</td><td></td><td></td><td><span class=\"status gap\">Evidence</span></td>", body)
        self.assertIn("<td>AI2</td><td></td><td></td><td>tax</td><td>30</td><td></td><td></td><td><span class=\"status used\">Used</span></td>", body)
        self.assertIn("<td>AI3</td><td></td><td></td><td>review</td><td>x</td><td></td><td></td><td><span class=\"status review-badge\">Accountant review</span></td>", body)

    def test_malformed_taxpack_sections_remain_visible_review_rows(self) -> None:
        payload = {
            "income_year": "2025-26",
            "generated_date": "28 Jun 2026",
            "items": [
                {
                    "number": "1",
                    "ato_area": "Salary",
                    "question": "PAYG gross",
                    "answer": "100",
                    "why_included": "Base row.",
                    "status": "Evidence",
                }
            ],
            "missing_facts": {"bad": "shape"},
            "evidence_items": ["bad row"],
        }

        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Malformed missing_facts input", body)
        self.assertIn("Malformed evidence_items-1 input", body)
        self.assertIn("class=\"tab red review\"", body)
        self.assertIn("(Accountant review)", body)
        self.assertNotIn("No items supplied.", body)

    def test_malformed_taxpack_extraction_input_stays_review(self) -> None:
        payload = {
            "income_year": "2025-26",
            "generated_date": "28 Jun 2026",
            "items": [
                {
                    "number": "1",
                    "ato_area": "Salary",
                    "question": "PAYG gross",
                    "answer": "100",
                    "why_included": "Base row.",
                    "status": "Evidence",
                }
            ],
            "extracted_values": {"bad": "shape"},
        }

        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("AI-MALFORMED-1", body)
        self.assertIn("Malformed AI extraction input", body)
        self.assertIn("<span class=\"status review-badge\">Accountant review</span>", body)

    def test_guide_preserves_source_provenance(self) -> None:
        source_url = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/records-you-need-to-keep"
        second_url = "https://www.ato.gov.au/individuals-and-families/your-tax-return/how-to-lodge-your-tax-return"
        item = taxmate_taxpack.guide_item(
            {
                "number": "9",
                "ato_area": "Other",
                "question": "Has records?",
                "answer": "User-entered value",
                "why_included": "Source-backed handoff row.",
                "source_url": source_url,
                "source_urls": [source_url, second_url],
                "checked_at": "2026-06-28T00:00:00Z",
                "status": "Evidence",
                "tab_text": "Keep records visible.",
            }
        )
        data = taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date="28 Jun 2026",
            summary_note="Provenance regression.",
            items=[item],
        )

        body = taxmate_taxpack.render_html(data)

        self.assertIn(f'<span class="source-url">{source_url}</span>', body)
        self.assertIn(f'<span class="source-url">{second_url}</span>', body)
        self.assertIn('<span class="checked-at">Checked 2026-06-28T00:00:00Z</span>', body)
        self.assertEqual(1, body.count(f'<span class="source-url">{source_url}</span>'))

    def test_guide_preserves_skipped_statuses(self) -> None:
        payload = {
            "income_year": "2025-26",
            "generated_date": "28 Jun 2026",
            "items": [
                {
                    "number": "10",
                    "ato_area": "Other",
                    "question": "Not applicable?",
                    "answer": "Skipped by user",
                    "why_included": "Question was not applicable.",
                    "status": "N/A skipped",
                    "status_kind": "grey",
                    "tab_title": "Row 10 skipped",
                    "tab_text": "Skipped item.",
                    "tab_kind": "N/A skipped",
                }
            ],
        }
        data = taxmate_taxpack.GuideData(
            income_year=payload["income_year"],
            generated_date=payload["generated_date"],
            summary_note="Skipped regression.",
            items=[taxmate_taxpack.guide_item(payload["items"][0])],
        )

        body = taxmate_taxpack.render_html(data)

        self.assertIn("<span class=\"status skipped\">N/A skipped</span>", body)
        self.assertIn("class=\"tab grey\"", body)
        self.assertIn("No review-only items supplied.", body)
        self.assertNotIn("<span class=\"status review-badge\">", body)

    def test_guide_defaults_unknown_status_labels_to_review(self) -> None:
        item = taxmate_taxpack.guide_item(
            {
                "number": "11",
                "ato_area": "Other",
                "question": "Ready to claim?",
                "answer": "User-entered value",
                "why_included": "Freeform status should not look final.",
                "status": "Claimable",
                "tab_text": "Unknown status needs review.",
            }
        )
        data = taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date="28 Jun 2026",
            summary_note="Unknown status regression.",
            items=[item],
        )

        body = taxmate_taxpack.render_html(data)

        self.assertIn("<span class=\"status review-badge\">Accountant review</span>", body)
        self.assertIn("Unknown status needs review.", body)
        self.assertNotIn(">Claimable<", body)

    def test_guide_review_status_wins_over_stale_kind_fields(self) -> None:
        stale_kinds = ["evidence", "answer", "ato", "skipped", "grey"]
        downgraded_badges = [
            '<span class="status gap">Evidence</span>',
            '<span class="status used">Used</span>',
            '<span class="status label">ATO label</span>',
            '<span class="status skipped">N/A skipped</span>',
        ]

        for status_kind in stale_kinds:
            for tab_kind in stale_kinds:
                with self.subTest(status_kind=status_kind, tab_kind=tab_kind):
                    item = taxmate_taxpack.guide_item(
                        {
                            "number": "12",
                            "ato_area": "Other",
                            "question": "Conflicting reviewed row?",
                            "answer": "User-entered value",
                            "why_included": "Explicit review status must not be downgraded.",
                            "status": "Accountant review",
                            "status_kind": status_kind,
                            "tab_kind": tab_kind,
                            "tab_text": "Conflicting status fields require accountant review.",
                        }
                    )
                    data = taxmate_taxpack.GuideData(
                        income_year="2025-26",
                        generated_date="28 Jun 2026",
                        summary_note="Conflicting status regression.",
                        items=[item],
                    )

                    body = taxmate_taxpack.render_html(data)

                    self.assertEqual("review", item.status_kind)
                    self.assertEqual("review", item.tab_kind)
                    self.assertIn("<span class=\"status review-badge\">Accountant review</span>", body)
                    self.assertIn("class=\"tab red review\"", body)
                    self.assertIn(
                        "<b>Accountant review queue:</b> Conflicting status fields require accountant review.",
                        body,
                    )
                    for downgraded_badge in downgraded_badges:
                        self.assertNotIn(downgraded_badge, body)

        for field in ("status", "status_kind", "tab_kind"):
            with self.subTest(review_field=field):
                raw = {
                    "number": "12",
                    "ato_area": "Other",
                    "question": "Split reviewed row?",
                    "answer": "User-entered value",
                    "why_included": "Any explicit review field must control output.",
                    "status": "Evidence",
                    "status_kind": "evidence",
                    "tab_kind": "evidence",
                    "tab_text": "One field still requires accountant review.",
                }
                raw[field] = "Accountant review"
                item = taxmate_taxpack.guide_item(raw)
                body = taxmate_taxpack.render_html(
                    taxmate_taxpack.GuideData(
                        income_year="2025-26",
                        generated_date="28 Jun 2026",
                        summary_note="Split status regression.",
                        items=[item],
                    )
                )
                self.assertEqual("review", item.status_kind)
                self.assertEqual("review", item.tab_kind)
                self.assertIn("<b>Accountant review queue:</b> One field still requires accountant review.", body)

        review_like_labels = [
            "Accountant review required",
            "Requires accountant review",
            "Review required",
            "Needs review",
            "Tax agent review required",
        ]
        for label in review_like_labels:
            with self.subTest(review_like_label=label):
                item = taxmate_taxpack.guide_item(
                    {
                        "number": "12",
                        "ato_area": "Other",
                        "question": "Review-like label?",
                        "answer": "User-entered value",
                        "why_included": "Review-like status labels must not be downgraded.",
                        "status": label,
                        "status_kind": "evidence",
                        "tab_kind": "answer",
                        "tab_text": "Review-like label requires accountant review.",
                    }
                )
                body = taxmate_taxpack.render_html(
                    taxmate_taxpack.GuideData(
                        income_year="2025-26",
                        generated_date="28 Jun 2026",
                        summary_note="Review-like status regression.",
                        items=[item],
                    )
                )
                self.assertEqual("review", item.status_kind)
                self.assertEqual("review", item.tab_kind)
                self.assertIn("<span class=\"status review-badge\">Accountant review</span>", body)
                self.assertIn("<b>Accountant review queue:</b> Review-like label requires accountant review.", body)

        blank_review = taxmate_taxpack.guide_item(
            {
                "number": "13",
                "ato_area": "Other",
                "question": "Blank review explanation?",
                "answer": "User-entered value",
                "status": "Accountant review",
                "status_kind": "review",
                "tab_kind": "review",
            }
        )
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="28 Jun 2026",
                summary_note="Blank review regression.",
                items=[blank_review],
            )
        )
        self.assertEqual("Row 13: Accountant review.", blank_review.tab_text)
        self.assertIn("<b>Accountant review queue:</b> Row 13: Accountant review.", body)
        self.assertIn("<p>Row 13: Accountant review.</p>", body)

        blank_queue = taxmate_taxpack.GuideItem(
            number="Q1",
            ato_area="Other",
            question="",
            answer="",
            why_included="",
            source_urls=[],
            checked_at="",
            status="Evidence",
            status_kind="evidence",
            tab_kind="evidence",
            tab_text="",
            tab_title="",
        )
        queue_body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="28 Jun 2026",
                summary_note="Blank queue regression.",
                items=[],
                missing_facts=[blank_queue],
            )
        )
        self.assertIn('<li data-anchor="row-401-Q1">Row Q1: Evidence.</li>', queue_body)
        self.assertNotIn("<li>:  (Evidence)</li>", queue_body)

        direct_blank = taxmate_taxpack.GuideItem(
            number="14",
            ato_area="Other",
            question="Direct blank review?",
            answer="User-entered value",
            why_included="",
            source_urls=[],
            checked_at="",
            status="Accountant review",
            status_kind="review",
            tab_title="Row 14 direct review",
            tab_text="",
            tab_kind="review",
        )
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="28 Jun 2026",
                summary_note="Direct blank review regression.",
                items=[direct_blank],
            )
        )
        self.assertIn("<b>Accountant review queue:</b> Row 14: Accountant review.", body)
        self.assertIn("<p>Row 14: Accountant review.</p>", body)

        direct_conflict = taxmate_taxpack.GuideItem(
            number="15",
            ato_area="Other",
            question="Direct conflicting review?",
            answer="User-entered value",
            why_included="",
            source_urls=[],
            checked_at="",
            status="Accountant review required",
            status_kind="evidence",
            tab_title="Row 15 direct conflict",
            tab_text="",
            tab_kind="answer",
        )
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="28 Jun 2026",
                summary_note="Direct conflict regression.",
                items=[direct_conflict],
            )
        )
        self.assertIn("<span class=\"status review-badge\">Accountant review</span>", body)
        self.assertIn("class=\"tab red review\"", body)
        self.assertIn("<b>Accountant review queue:</b> Row 15: Accountant review.", body)

    def test_extended_review_rows_appear_in_tabs_and_review_queue(self) -> None:
        missing_review = taxmate_taxpack.guide_item(
            {
                "number": "MISS-1",
                "ato_area": "Missing facts",
                "question": "Confirm WFH pattern",
                "answer": "Missing weekdays",
                "status": "Accountant review",
                "tab_text": "Missing WFH pattern requires accountant review.",
            }
        )
        evidence_review = taxmate_taxpack.guide_item(
            {
                "number": "EVID-1",
                "ato_area": "Evidence",
                "question": "Receipt gap",
                "answer": "Mixed-use asset receipt",
                "status": "Accountant review",
                "tab_text": "Evidence gap requires accountant review.",
            }
        )

        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="29 Jun 2026",
                summary_note="Extended review regression.",
                items=[],
                missing_facts=[missing_review],
                evidence_items=[evidence_review],
            )
        )

        self.assertIn('data-target="row-401-MISS-1"', body)
        self.assertIn('data-target="row-501-EVID-1"', body)
        self.assertIn('data-anchor="row-401-MISS-1"', body)
        self.assertIn('data-anchor="row-501-EVID-1"', body)
        self.assertIn("Missing WFH pattern requires accountant review.", body)
        self.assertIn("Evidence gap requires accountant review.", body)
        self.assertIn(
            "<b>Accountant review queue:</b> Missing WFH pattern requires accountant review.; Evidence gap requires accountant review.",
            body,
        )

    def test_guide_canonicalizes_color_status_aliases(self) -> None:
        aliases = {
            "red": "Accountant review",
            "yellow": "Evidence",
            "green": "Used",
            "blue": "ATO label",
            "grey": "N/A skipped",
        }

        for alias, expected in aliases.items():
            with self.subTest(alias=alias):
                item = taxmate_taxpack.guide_item(
                    {
                        "number": alias,
                        "ato_area": "Other",
                        "question": "Alias?",
                        "answer": "Alias input",
                        "why_included": "Color alias regression.",
                        "status": alias,
                        "tab_text": "Alias item.",
                    }
                )

                self.assertEqual(expected, item.status)
                self.assertNotEqual(alias, item.status)

    def test_guide_preserves_falsey_display_values(self) -> None:
        item = taxmate_taxpack.guide_item(
            {
                "number": 0,
                "ato_area": 0,
                "question": False,
                "answer": 0,
                "why_included": 0,
                "checked_at": 0,
                "status": "Evidence",
                "tab_title": 0,
                "tab_text": 0,
                "source_urls": [False],
            }
        )

        self.assertEqual("0", item.number)
        self.assertEqual("0", item.ato_area)
        self.assertEqual("false", item.question)
        self.assertEqual("0", item.answer)
        self.assertEqual("0", item.why_included)
        self.assertEqual("0", item.checked_at)
        self.assertEqual("0", item.tab_title)
        self.assertEqual("0", item.tab_text)
        self.assertEqual(["false"], item.source_urls)

        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="28 Jun 2026",
                summary_note="Falsey value regression.",
                items=[item],
            )
        )
        self.assertIn("<td>0</td>", body)
        self.assertIn("<td>false</td>", body)
        self.assertIn("<b>0</b>", body)
        self.assertIn("<p>0</p>", body)
        self.assertIn("Checked 0", body)
        self.assertIn("<span class=\"source-url\">false</span>", body)

        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            json.dump(
                {
                    "income_year": 0,
                    "generated_date": False,
                    "summary_note": 0,
                    "items": [
                        {
                            "number": 0,
                            "ato_area": 0,
                            "question": False,
                            "answer": 0,
                            "why_included": 0,
                            "status": "Evidence",
                        }
                    ],
                },
                handle,
            )
            handle.flush()
            data = taxmate_taxpack.load_guide_data(handle.name)

        self.assertEqual("0", data.income_year)
        self.assertEqual("false", data.generated_date)
        self.assertEqual("0", data.summary_note)
        body = taxmate_taxpack.render_html(data)
        self.assertIn("Income year 0", body)
        self.assertIn("Generated false", body)
        self.assertIn("0</p>", body)

        direct = taxmate_taxpack.GuideItem(
            number=0,
            ato_area=0,
            question=False,
            answer=0,
            why_included=0,
            source_urls=[0],
            checked_at=0,
            status="Evidence",
            status_kind="evidence",
            tab_title=0,
            tab_text=0,
            tab_kind="evidence",
        )
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="28 Jun 2026",
                summary_note="Direct falsey value regression.",
                items=[direct],
            )
        )
        self.assertIn("<td>0</td>", body)
        self.assertIn("<td>false</td>", body)
        self.assertIn("<span class=\"source-url\">0</span>", body)
        self.assertIn("<b>0</b>", body)
        self.assertIn("<p>0</p>", body)
        self.assertIn("Checked 0", body)
        self.assertIn("data-anchor=\"row-1-0\"", body)

        direct_blank = taxmate_taxpack.GuideItem(
            number=False,
            ato_area="Other",
            question="Direct false number?",
            answer=0,
            why_included="",
            source_urls=[],
            checked_at="",
            status="Accountant review",
            status_kind="review",
            tab_title="Direct false number",
            tab_text="",
            tab_kind="review",
        )
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="28 Jun 2026",
                summary_note="Direct false number fallback.",
                items=[direct_blank],
            )
        )
        self.assertIn("Row false: Accountant review.", body)
        self.assertIn("data-anchor=\"row-1-false\"", body)

    def test_guide_rejects_forbidden_visible_taxpack_language(self) -> None:
        data = taxmate_taxpack.load_guide_data(None)
        bad = taxmate_taxpack.render_html(data).replace("Prepared by user", "Prepared by " + "TaxMate")

        with self.assertRaises(ValueError):
            taxmate_taxpack.assert_visible_boundaries(bad)


if __name__ == "__main__":
    unittest.main()
