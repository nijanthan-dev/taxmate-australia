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
        self.assertTrue(any("state-wide public holidays" in finding.detail for finding in findings))
        self.assertTrue(any("regional, capital-city-only, sector-only, and partial-day" in finding.detail for finding in findings))
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
        self.assertNotIn("feat: add ESS workflow", titles)
        self.assertNotIn("feat: add ETP and lump sum workflow", titles)
        self.assertNotIn("feat: add foreign income workflow", titles)
        self.assertNotIn("feat: add PSI deep workflow", titles)
        self.assertNotIn("feat: add crypto CGT workflow", titles)
        self.assertNotIn("feat: add rental property worksheet", titles)
        self.assertEqual(6, len(issues))
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
                "Complex income",
                "Foreign income",
                "PSI",
                "Crypto",
                "ABN",
                "BAS",
                "Deductions",
                "WFH",
                "Assets",
            }.issubset(sections)
        )
        self.assertTrue(
            {
                "resident",
                "state",
                "spouse_had",
                "gst_registered",
                "asset_items",
                "etp_statement",
                "lump_sum_arrears_statement",
                "lump_sum_arrears_amount",
                "super_income_statement",
                "super_income_stream_taxable_amount",
                "foreign_income_statement",
                "foreign_income_country",
                "foreign_income_amount",
                "foreign_tax_paid",
                "foreign_income_residency_status",
                "foreign_income_tax_offset_claim",
                "psi_income",
                "psi_contract_evidence",
                "psi_results_test",
                "psi_80_percent_test",
                "psi_unrelated_clients_test",
                "psi_business_structure",
                "crypto_event_type",
                "crypto_exchange_or_wallet",
                "crypto_asset",
                "crypto_quantity",
                "crypto_acquired_date",
                "crypto_disposed_date",
                "crypto_cost_base",
                "crypto_capital_proceeds",
                "crypto_rewards_income",
                "crypto_wallet_records",
                "crypto_ownership_entity",
                "crypto_business_use",
                "crypto_private_use",
            }.issubset(keys)
        )

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

    def test_missing_ess_statement_base_rows_stay_evidence(self) -> None:
        for value in [False, "no ESS statement", "statement not received"]:
            with self.subTest(value=value):
                answers = taxmate_intake.sample_answers()
                answers["ess_statement"] = value

                rows = taxmate_intake.base_items(answers)
                ess_statement = next(row for row in rows if row["number"] == "ess_statement")

                self.assertEqual("Evidence", ess_statement["status"])

    def test_malformed_ess_amount_base_rows_stay_evidence(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["ess_taxed_upfront_discount"] = "about $100"

        rows = taxmate_intake.base_items(answers)
        ess_amount = next(row for row in rows if row["number"] == "ess_taxed_upfront_discount")

        self.assertEqual("Evidence", ess_amount["status"])

    def test_boolean_ess_amount_base_rows_are_skipped(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["ess_taxed_upfront_discount"] = False

        rows = taxmate_intake.base_items(answers)
        rendered_numbers = {row["number"] for row in rows}

        self.assertNotIn("ess_taxed_upfront_discount", rendered_numbers)

    def test_no_ess_statement_base_rows_are_skipped(self) -> None:
        for value in ["no employee share scheme", "no employee share schemes", "not applicable", "n/a"]:
            with self.subTest(value=value):
                answers = taxmate_intake.sample_answers()
                answers["ess_statement"] = value

                rows = taxmate_intake.base_items(answers)
                rendered_numbers = {row["number"] for row in rows}

                self.assertNotIn("ess_statement", rendered_numbers)

    def test_complex_payment_workflows_render_statement_backed_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        by_number = {row["number"]: row for row in payload["items"]}

        for number in ["ETP", "LUMP-ARREARS", "SUPER-INCOME"]:
            with self.subTest(number=number):
                self.assertEqual("Accountant review", by_number[number]["status"])

        self.assertIn("taxable component 12000.00", by_number["ETP"]["answer"])
        self.assertIn("tax-free component 3000.00", by_number["ETP"]["answer"])
        self.assertIn("amount 2400.00", by_number["LUMP-ARREARS"]["answer"])
        self.assertIn("tax withheld 500.00", by_number["LUMP-ARREARS"]["answer"])
        self.assertIn("income-stream taxable amount 18000.00", by_number["SUPER-INCOME"]["answer"])
        self.assertIn("tax-free component 0.00", by_number["SUPER-INCOME"]["answer"])
        self.assertIn(taxmate_intake.ATO_ETP_SOURCE, by_number["ETP"]["source_urls"])
        self.assertIn(taxmate_intake.ATO_LUMP_SUM_ARREARS_SOURCE, by_number["LUMP-ARREARS"]["source_urls"])
        self.assertIn(taxmate_intake.ATO_SUPER_STREAM_SOURCE, by_number["SUPER-INCOME"]["source_urls"])

    def test_no_complex_payment_answers_do_not_render_workflow_rows(self) -> None:
        cases = [
            {"etp_statement": "no etp"},
            {"etp_payment_type": "no etp"},
            {"etp_taxable_component": "no etp"},
            {"lump_sum_arrears_statement": "no lump sum in arrears"},
            {"lump_sum_arrears_amount": "no lump sum in arrears"},
            {"super_income_statement": "no super income stream"},
            {"super_income_payment_kind": "no super income stream"},
            {"etp": {"statement": "no employment termination payments"}},
            {"etp": {"statement": "I dont have an ETP"}},
            {"etp": {"payment_type": "no employment termination payments"}},
            {"lump_sum_arrears": {"statement": "not applicable"}},
            {"lump_sum_arrears": {"statement": "I dont have a lump sum in arrears"}},
            {"lump_sum_arrears": {"amount": "no lump sum in arrears"}},
            {"super_income": {"statement": "no super lump sums"}},
            {"super_income": {"statement": "I dont have a super income stream"}},
            {"super_income": {"payment_kind": "no super lump sums"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                rendered_numbers = {row["number"] for row in payload["items"]}

                self.assertFalse({"ETP", "LUMP-ARREARS", "SUPER-INCOME"} & rendered_numbers)
                for key in set(answers) & set(taxmate_intake.REVIEWABLE_COMPLEX_PAYMENT_FIELDS):
                    self.assertNotIn(key, rendered_numbers)

    def test_complex_payment_declines_are_group_specific(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {"etp": {"statement": "no super income stream", "taxable_component": 100}}
        )
        etp = next(row for row in payload["items"] if row["number"] == "ETP")

        self.assertEqual("Accountant review", etp["status"])
        self.assertIn("taxable component 100.00", etp["answer"])

    def test_complex_payment_no_answer_with_amount_stays_evidence(self) -> None:
        cases = [
            ("ETP", "no-payment answer with payment facts", {"etp_statement": "no etp", "etp_taxable_component": 100}),
            (
                "LUMP-ARREARS",
                "no-payment answer with payment facts",
                {"lump_sum_arrears_statement": "no lump sum in arrears", "lump_sum_arrears_amount": 100, "lump_sum_arrears_years": "2024-25"},
            ),
            (
                "SUPER-INCOME",
                "no-payment answer with payment facts",
                {"super_income_statement": "no super income stream", "super_income_stream_taxable_amount": 100},
            ),
        ]
        for number, tab_text, answers in cases:
            with self.subTest(number=number):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == number)

                self.assertEqual("Evidence", row["status"])
                self.assertIn(tab_text, row["tab_text"])
                self.assertIn("100.00", row["answer"])

    def test_complex_payment_missing_statement_phrases_stay_evidence(self) -> None:
        cases = [
            ("ETP", {"etp": {"statement": "statement not provided", "taxable_component": 100}}),
            ("ETP", {"etp": {"statement": "I dont have the ETP payment summary", "taxable_component": 100}}),
            (
                "LUMP-ARREARS",
                {"lump_sum_arrears": {"statement": "do not have statement", "amount": 100, "payment_years": "2024-25"}},
            ),
            ("SUPER-INCOME", {"super_income": {"statement": "fund statement not received", "taxable_amount": 100}}),
            ("ETP", {"etp_statement": "payment summary not held", "etp_taxable_component": 100}),
        ]
        for number, answers in cases:
            with self.subTest(number=number, answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == number)

                self.assertEqual("Evidence", row["status"])
                self.assertIn("statement evidence", row["tab_text"])
                self.assertIn("100.00", row["answer"])

    def test_missing_complex_payment_statement_base_rows_stay_evidence(self) -> None:
        for key, value in [
            ("etp_statement", "statement not received"),
            ("lump_sum_arrears_statement", "income statement not provided"),
            ("super_income_statement", "fund statement not available"),
        ]:
            with self.subTest(key=key):
                answers = taxmate_intake.sample_answers()
                answers[key] = value

                rows = taxmate_intake.base_items(answers)
                statement_row = next(row for row in rows if row["number"] == key)

                self.assertEqual("Evidence", statement_row["status"])

    def test_lump_sum_arrears_missing_prior_years_names_evidence_gap(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {"lump_sum_arrears": {"statement": "income statement held", "amount": 100, "tax_withheld": 10}}
        )
        row = next(item for item in payload["items"] if item["number"] == "LUMP-ARREARS")

        self.assertEqual("Evidence", row["status"])
        self.assertEqual(
            "Lump sum in arrears needs prior-year allocation evidence before accountant review.",
            row["tab_text"],
        )

    def test_unknown_complex_payment_amounts_stay_evidence(self) -> None:
        cases = [
            ("ETP", {"etp": {"statement": "ETP payment summary held", "taxable_component": "unknown"}}),
            (
                "LUMP-ARREARS",
                {"lump_sum_arrears": {"statement": "income statement held", "amount": "unknown", "payment_years": "2024-25"}},
            ),
            ("SUPER-INCOME", {"super_income": {"statement": "fund statement held", "taxable_amount": "unknown"}}),
        ]
        for number, answers in cases:
            with self.subTest(number=number):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == number)

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric amount evidence", row["tab_text"])
                self.assertIn("unknown", row["answer"])

    def test_malformed_complex_payment_amounts_stay_evidence(self) -> None:
        cases = [
            ("ETP", {"etp": {"statement": "ETP payment summary held", "taxable_component": "about $100"}}),
            (
                "LUMP-ARREARS",
                {"lump_sum_arrears": {"statement": "income statement held", "amount": "100 AUD", "payment_years": "2024-25"}},
            ),
            ("SUPER-INCOME", {"super_income": {"statement": "fund statement held", "taxable_amount": "about $100"}}),
        ]
        for number, answers in cases:
            with self.subTest(number=number):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == number)

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric amount evidence", row["tab_text"])

    def test_zero_complex_payment_amounts_are_meaningful(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "etp": {"statement": "ETP payment summary held", "taxable_component": 0, "tax_free_component": 0, "tax_withheld": 0},
                "lump_sum_arrears": {"statement": "income statement held", "amount": 0, "payment_years": "2024-25", "tax_withheld": 0},
                "super_income": {"statement": "fund statement held", "payment_kind": "income stream", "taxable_amount": 0, "tax_withheld": 0},
            }
        )
        by_number = {row["number"]: row for row in payload["items"]}

        self.assertEqual("Accountant review", by_number["ETP"]["status"])
        self.assertEqual("Accountant review", by_number["LUMP-ARREARS"]["status"])
        self.assertEqual("Accountant review", by_number["SUPER-INCOME"]["status"])
        self.assertIn("taxable component 0.00", by_number["ETP"]["answer"])
        self.assertIn("amount 0.00", by_number["LUMP-ARREARS"]["answer"])
        self.assertIn("income-stream taxable amount 0.00", by_number["SUPER-INCOME"]["answer"])

    def test_complex_payment_review_rows_appear_in_html_pack(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Employment termination payments", body)
        self.assertIn("Lump sum payment in arrears", body)
        self.assertIn("Superannuation lump sum or income stream", body)
        self.assertIn("ETP needs source-backed accountant review.", body)
        self.assertNotIn("lodgment-ready", body)

    def test_complex_payment_sources_are_registered_and_covered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "data" / "ato_knowledge_base" / "source_registry.json").read_text())
        coverage = json.loads((root / "data" / "ato_knowledge_base" / "source_coverage.json").read_text())
        registry_urls = {item["url"] for item in registry["records"]}
        covered = {item["canonical_url"]: item for item in coverage["sources"]}

        expected_skills = {
            taxmate_intake.ATO_ETP_SOURCE: "payg-employer",
            taxmate_intake.ATO_LUMP_SUM_ARREARS_SOURCE: "employment-deductions",
            taxmate_intake.ATO_SUPER_PENSIONS_SOURCE: "employment-deductions",
            taxmate_intake.ATO_SUPER_LUMP_SUM_SOURCE: "payg-employer",
            taxmate_intake.ATO_SUPER_STREAM_SOURCE: "payg-employer",
        }
        for url, skill in expected_skills.items():
            with self.subTest(url=url):
                self.assertIn(url, registry_urls)
                self.assertEqual("verified", covered[url]["status"])
                self.assertIn(skill, covered[url]["skills"])

    def test_foreign_income_workflow_renders_statement_backed_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("Country NZ", row["answer"])
        self.assertIn("type employment", row["answer"])
        self.assertIn("amount 5000.00", row["answer"])
        self.assertIn("foreign tax paid 0.00", row["answer"])
        self.assertIn("exchange rate 0.92", row["answer"])
        self.assertIn("residency Australian resident for tax purposes all year", row["answer"])
        self.assertIn(taxmate_intake.ATO_FOREIGN_WORLDWIDE_SOURCE, row["source_urls"])
        self.assertIn(taxmate_intake.ATO_FOREIGN_INCOME_TAX_OFFSET_SOURCE, row["source_urls"])

    def test_no_foreign_income_answers_do_not_render_workflow_row(self) -> None:
        cases = [
            {"foreign_income_statement": "no foreign income"},
            {"foreign_income_country": "no foreign income"},
            {"foreign_income_amount": "no foreign income"},
            {"foreign_income_statement": "I had no foreign income this year"},
            {"foreign_income_statement": "I do not have any foreign income"},
            {"foreign_income_statement": "I don't have foreign income"},
            {"foreign_income_statement": "I dont have foreign income"},
            {"foreign_income_statement": "no foreign employment"},
            {"foreign_income_statement": "not applicable"},
            {"foreign_income": {"statement": "no foreign pensions"}},
            {"foreign_income_tax_offset_claim": False},
            {"foreign_employment_exempt_claim": False},
            {"foreign_income_statement": "no foreign income", "foreign_income_tax_offset_claim": "no offset"},
            {"foreign_income_statement": "no foreign income", "foreign_employment_exempt_claim": "no exemption"},
            {"foreign_income": {"statement": "no foreign income", "foreign_tax_offset_claim": "not claiming"}},
            {"foreign_income": {"country": "no foreign income"}},
            {"foreign_income": {"amount": "no foreign income"}},
            {"foreign_income": {"statement": "no foreign income", "foreign_employment_exempt_claim": "no foreign employment exemption"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                rendered_numbers = {row["number"] for row in payload["items"]}

                self.assertNotIn("FOREIGN-INCOME", rendered_numbers)
                for key in set(answers) & set(taxmate_intake.REVIEWABLE_FOREIGN_INCOME_FIELDS):
                    self.assertNotIn(key, rendered_numbers)

    def test_foreign_income_decline_tokens_are_exact(self) -> None:
        cases = [
            {"foreign_income_statement": "Canadian T4 statement held"},
            {"foreign_income": {"statement": "statement held from Canada"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("residency or temporary-resident evidence", row["tab_text"])

    def test_ambiguous_no_foreign_income_statement_stays_visible(self) -> None:
        for statement in ["unsure, no foreign income?", "uncertain, no foreign income"]:
            with self.subTest(statement=statement):
                payload = taxmate_intake.answers_to_pack_payload({"foreign_income_statement": statement})
                rows = {item["number"]: item for item in payload["items"]}

                self.assertEqual("Evidence", rows["foreign_income_statement"]["status"])
                self.assertEqual("Evidence", rows["FOREIGN-INCOME"]["status"])
                self.assertIn("statement evidence", rows["FOREIGN-INCOME"]["tab_text"])

    def test_false_foreign_income_claim_flags_do_not_render_base_rows(self) -> None:
        rows = taxmate_intake.base_items(
            {
                "foreign_income_tax_offset_claim": False,
                "foreign_employment_exempt_claim": False,
                "foreign_income_statement": "no foreign income",
            }
        )
        rendered_numbers = {row["number"] for row in rows}

        self.assertNotIn("foreign_income_tax_offset_claim", rendered_numbers)
        self.assertNotIn("foreign_employment_exempt_claim", rendered_numbers)

    def test_negative_foreign_income_claim_strings_do_not_render_base_rows(self) -> None:
        rows = taxmate_intake.base_items(
            {
                "foreign_income_tax_offset_claim": "no offset",
                "foreign_employment_exempt_claim": "no exemption",
                "foreign_income_statement": "no foreign income",
            }
        )
        rendered_numbers = {row["number"] for row in rows}

        self.assertNotIn("foreign_income_tax_offset_claim", rendered_numbers)
        self.assertNotIn("foreign_employment_exempt_claim", rendered_numbers)

    def test_nested_false_foreign_income_claim_flags_are_preserved(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "country": "NZ",
                    "amount": 500,
                    "foreign_tax_paid": 0,
                    "exchange_rate": 0.92,
                    "residency_status": "Australian resident",
                    "foreign_tax_offset_claim": False,
                    "foreign_employment_exempt_claim": False,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("foreign tax offset claim false", row["answer"])
        self.assertIn("foreign employment exemption claim false", row["answer"])

    def test_no_foreign_tax_paid_wording_does_not_decline_foreign_income_workflow(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held; no foreign tax paid",
                    "country": "NZ",
                    "amount": 500,
                    "foreign_tax_paid": 0,
                    "exchange_rate": 0.92,
                    "residency_status": "Australian resident",
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertEqual("Foreign income needs source-backed accountant review.", row["tab_text"])
        self.assertIn("foreign tax paid 0.00", row["answer"])

    def test_no_foreign_income_tax_paid_wording_does_not_decline_foreign_income_workflow(self) -> None:
        for statement in [
            "foreign income statement held; no foreign income tax paid",
            "I do not have foreign income tax paid",
            "I don't have foreign income tax paid",
        ]:
            with self.subTest(statement=statement):
                payload = taxmate_intake.answers_to_pack_payload({"foreign_income_statement": statement})
                rows = {item["number"]: item for item in payload["items"]}

                self.assertIn("foreign_income_statement", rows)
                self.assertIn("FOREIGN-INCOME", rows)
                self.assertEqual("Evidence", rows["FOREIGN-INCOME"]["status"])
                self.assertIn("residency or temporary-resident evidence", rows["FOREIGN-INCOME"]["tab_text"])

    def test_foreign_income_no_answer_with_amount_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income_statement": "no foreign income",
                "foreign_income_amount": 100,
                "foreign_income_residency_status": "Australian resident for tax purposes",
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("statement evidence", row["tab_text"])
        self.assertIn("amount 100.00", row["answer"])

    def test_foreign_income_no_answer_with_item_gap_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income_statement": "no foreign income",
                "foreign_income_items": [{"country": "US", "amount": "unknown"}],
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("statement evidence", row["tab_text"])
        self.assertIn("numeric amount or exchange-rate evidence", row["tab_text"])
        self.assertIn("US", row["answer"])

    def test_foreign_income_missing_statement_phrases_stay_evidence(self) -> None:
        cases = [
            {"foreign_income_statement": "statement not provided", "foreign_income_amount": 100, "foreign_income_residency_status": "resident"},
            {"foreign_income": {"statement": "I do not have the foreign income statement", "amount": 100, "residency_status": "resident"}},
            {"foreign_income": {"statement": "I dont have the foreign income statement", "amount": 100, "residency_status": "resident"}},
            {"foreign_income_items": [{"statement": "payment summary not held", "country": "US", "amount": 100, "residency_status": "resident"}]},
            {"foreign_income_statement": "no foreign income statement"},
            {"foreign_income_statement": "no foreign pension statement"},
            {"foreign_income_statement": "no foreign income payment summary"},
            {"foreign_income_statement": "no foreign employment statement"},
            {"foreign_income": {"statement": "without foreign income payment summary", "amount": 100, "residency_status": "resident"}},
            {"foreign_income_items": [{"statement": "missing foreign employment statement", "country": "US", "amount": 100, "residency_status": "resident"}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                rows = {item["number"]: item for item in payload["items"]}
                row = rows["FOREIGN-INCOME"]

                self.assertEqual("Evidence", row["status"])
                self.assertIn("statement evidence", row["tab_text"])
                if "foreign_income_statement" in answers:
                    self.assertEqual("Evidence", rows["foreign_income_statement"]["status"])
                if "amount" in str(answers):
                    self.assertIn("100.00", row["answer"])

    def test_unknown_or_malformed_foreign_income_amounts_stay_evidence(self) -> None:
        cases = [
            {"foreign_income": {"statement": "statement held", "amount": "unknown", "residency_status": "resident"}},
            {"foreign_income": {"statement": "statement held", "amount": "about $100", "residency_status": "resident"}},
            {"foreign_income_items": [{"statement": "statement held", "country": "US", "amount": "100 AUD", "residency_status": "resident"}]},
            {"foreign_income": {"statement": "statement held", "amount": 100, "exchange_rate": "unknown", "residency_status": "resident"}},
            {"foreign_income": {"statement": "statement held", "amount": 100, "exchange_rate": False, "residency_status": "resident"}},
            {"foreign_income": {"statement": "statement held", "amount": 100, "exchange_rate": 0, "residency_status": "resident"}},
            {"foreign_income": {"statement": "statement held", "amount": 100, "exchange_rate": -0.5, "residency_status": "resident"}},
            {"foreign_income_items": [{"statement": "statement held", "country": "US", "amount": 100, "exchange_rate": True, "residency_status": "resident"}]},
            {"foreign_income_items": [{"statement": "statement held", "country": "US", "amount": 100, "exchange_rate": 0, "residency_status": "resident"}]},
            {"foreign_income_items": [{"statement": "statement held", "country": "US", "amount": 100, "exchange_rate": -0.5, "residency_status": "resident"}]},
            {"foreign_income": {"statement": "statement held", "amount": 100, "residency_status": "resident"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric amount or exchange-rate evidence", row["tab_text"])

    def test_foreign_income_item_exchange_rates_support_top_level_totals(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "statement held",
                    "amount": 300,
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "residency_status": "Australian resident",
                        },
                        {
                            "statement": "statement held",
                            "country": "NZ",
                            "amount": 200,
                            "exchange_rate": 0.50,
                            "residency_status": "Australian resident",
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("exchange rate item-specific", row["answer"])
        self.assertNotIn("numeric amount or exchange-rate evidence", row["tab_text"])

    def test_foreign_income_item_exchange_rate_gaps_with_top_level_total_stay_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "statement held",
                    "amount": 300,
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "residency_status": "Australian resident",
                        },
                        {
                            "statement": "statement held",
                            "country": "NZ",
                            "amount": 200,
                            "exchange_rate": "unknown",
                            "residency_status": "Australian resident",
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("numeric amount or exchange-rate evidence", row["tab_text"])

    def test_foreign_income_invalid_aggregate_exchange_rate_with_items_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "statement held",
                    "amount": 300,
                    "exchange_rate": 0,
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "residency_status": "Australian resident",
                        },
                        {
                            "statement": "statement held",
                            "country": "NZ",
                            "amount": 200,
                            "exchange_rate": 0.50,
                            "residency_status": "Australian resident",
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("numeric amount or exchange-rate evidence", row["tab_text"])

    def test_foreign_income_missing_residency_stays_evidence(self) -> None:
        cases = [
            {"foreign_income": {"statement": "statement held", "country": "US", "amount": 100}},
            {"foreign_income": {"statement": "statement held", "country": "US", "amount": 100, "residency_status": "unknown"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("residency or temporary-resident evidence", row["tab_text"])

    def test_foreign_income_offset_claim_without_tax_paid_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "statement held",
                    "country": "US",
                    "amount": 100,
                    "residency_status": "Australian resident",
                    "foreign_tax_offset_claim": True,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_nested_negative_does_not_clear_flat_offset_claim(self) -> None:
        flat_claims = [(True, "true"), ("yes", "yes"), ("claim", "claim")]
        nested_claims = [False, "no", "not claiming", "will not claim", "no offset", "no foreign income tax offset"]
        for flat_claim, expected_claim in flat_claims:
            for nested_claim in nested_claims:
                with self.subTest(flat_claim=flat_claim, nested_claim=nested_claim):
                    payload = taxmate_intake.answers_to_pack_payload(
                        {
                            "foreign_income_tax_offset_claim": flat_claim,
                            "foreign_income": {
                                "statement": "statement held",
                                "country": "US",
                                "amount": 100,
                                "exchange_rate": 0.66,
                                "residency_status": "Australian resident",
                                "foreign_tax_offset_claim": nested_claim,
                            },
                        }
                    )
                    row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                    self.assertEqual("Evidence", row["status"])
                    self.assertIn(f"foreign tax offset claim {expected_claim}", row["answer"])
                    self.assertIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_positive_offset_strings_need_tax_paid(self) -> None:
        for claim in ["yes", "claim", "will claim"]:
            with self.subTest(claim=claim):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "foreign_income_tax_offset_claim": claim,
                        "foreign_income": {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "residency_status": "Australian resident",
                        },
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Evidence", row["status"])
                self.assertIn(f"foreign tax offset claim {claim}", row["answer"])
                self.assertIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_nested_negative_does_not_clear_flat_exemption_claim(self) -> None:
        flat_claims = [(True, "true"), ("yes", "yes"), ("exempt", "exempt")]
        nested_claims = [False, "no", "not claiming", "no exemption", "no foreign employment exemption"]
        for flat_claim, expected_claim in flat_claims:
            for nested_claim in nested_claims:
                with self.subTest(flat_claim=flat_claim, nested_claim=nested_claim):
                    payload = taxmate_intake.answers_to_pack_payload(
                        {
                            "foreign_employment_exempt_claim": flat_claim,
                            "foreign_income": {
                                "statement": "statement held",
                                "country": "US",
                                "amount": 100,
                                "foreign_tax_paid": 5,
                                "exchange_rate": 0.66,
                                "residency_status": "Australian resident",
                                "foreign_employment_exempt_claim": nested_claim,
                            },
                        }
                    )
                    row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                    self.assertEqual("Accountant review", row["status"])
                    self.assertIn(f"foreign employment exemption claim {expected_claim}", row["answer"])

    def test_foreign_income_positive_exemption_strings_are_preserved(self) -> None:
        for claim in ["yes", "exempt", "will claim"]:
            with self.subTest(claim=claim):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "foreign_employment_exempt_claim": claim,
                        "foreign_income": {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "foreign_tax_paid": 5,
                            "exchange_rate": 0.66,
                            "residency_status": "Australian resident",
                        },
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Accountant review", row["status"])
                self.assertIn(f"foreign employment exemption claim {claim}", row["answer"])

    def test_foreign_income_negative_offset_phrases_do_not_need_tax_paid(self) -> None:
        cases = [
            {
                "foreign_income_statement": "statement held",
                "foreign_income_country": "US",
                "foreign_income_amount": 100,
                "foreign_income_exchange_rate": 0.66,
                "foreign_income_residency_status": "Australian resident",
                "foreign_income_tax_offset_claim": "no offset",
            },
            {
                "foreign_income": {
                    "statement": "statement held",
                    "country": "US",
                    "amount": 100,
                    "exchange_rate": 0.66,
                    "residency_status": "Australian resident",
                    "foreign_tax_offset_claim": "no foreign income tax offset",
                }
            },
            {
                "foreign_income_items": [
                    {
                        "statement": "statement held",
                        "country": "US",
                        "amount": 100,
                        "exchange_rate": 0.66,
                        "residency_status": "Australian resident",
                        "foreign_tax_offset_claim": "no offset",
                    }
                ]
            },
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Accountant review", row["status"])
                self.assertNotIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_boolean_tax_paid_is_missing_for_offset_claim(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income_statement": "statement held",
                "foreign_income_amount": 100,
                "foreign_income_exchange_rate": 0.66,
                "foreign_income_residency_status": "Australian resident",
                "foreign_income_tax_offset_claim": True,
                "foreign_tax_paid": False,
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("foreign tax paid evidence", row["tab_text"])
        self.assertIn("foreign tax paid unknown", row["answer"])

    def test_foreign_income_non_positive_tax_paid_is_missing_for_offset_claim(self) -> None:
        cases = [
            {
                "foreign_income_statement": "statement held",
                "foreign_income_amount": 100,
                "foreign_income_exchange_rate": 0.66,
                "foreign_income_residency_status": "Australian resident",
                "foreign_income_tax_offset_claim": True,
                "foreign_tax_paid": 0,
            },
            {
                "foreign_income": {
                    "statement": "statement held",
                    "country": "US",
                    "amount": 100,
                    "exchange_rate": 0.66,
                    "residency_status": "Australian resident",
                    "foreign_tax_offset_claim": True,
                    "tax_paid": -1,
                }
            },
            {
                "foreign_income": {
                    "statement": "statement held",
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "foreign_tax_offset_claim": True,
                            "foreign_tax_paid": 0,
                        }
                    ],
                }
            },
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_affirmative_offset_claim_phrases_need_tax_paid(self) -> None:
        cases = ["yes, claimed", "I will claim"]
        for claim in cases:
            with self.subTest(claim=claim):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "foreign_income": {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "residency_status": "Australian resident",
                            "foreign_tax_offset_claim": claim,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_uncertain_offset_claim_needs_tax_paid(self) -> None:
        for claim in ["unsure whether I will claim", "maybe"]:
            with self.subTest(claim=claim):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "foreign_income": {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "residency_status": "Australian resident",
                            "foreign_tax_offset_claim": claim,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_negative_offset_claim_phrase_does_not_need_tax_paid(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "statement held",
                    "country": "US",
                    "amount": 100,
                    "exchange_rate": 0.66,
                    "residency_status": "Australian resident",
                    "foreign_tax_offset_claim": "not claiming",
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertNotIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_offset_claim_accepts_item_tax_paid_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "foreign_tax_offset_claim": True,
                    "items": [
                        {
                            "country": "US",
                            "amount": 100,
                            "foreign_tax_paid": 10,
                            "exchange_rate": 0.66,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertEqual("Foreign income needs source-backed accountant review.", row["tab_text"])
        self.assertIn("foreign tax paid 10.00", row["answer"])
        self.assertNotIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_item_offset_claim_needs_item_tax_paid_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "foreign_tax_paid": 10,
                    "items": [
                        {
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "foreign_tax_offset_claim": True,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("foreign tax paid evidence", row["tab_text"])
        self.assertIn("foreign tax paid 10.00", row["answer"])

    def test_foreign_income_item_offset_claims_do_not_share_top_level_tax_paid(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "foreign_tax_paid": 100,
                    "items": [
                        {
                            "country": "NZ",
                            "income_type": "employment",
                            "amount": 1000,
                            "exchange_rate": 0.92,
                            "foreign_tax_offset_claim": True,
                        },
                        {
                            "country": "US",
                            "income_type": "dividend",
                            "amount": 500,
                            "exchange_rate": 0.66,
                            "foreign_tax_offset_claim": True,
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("foreign tax paid evidence", row["tab_text"])
        self.assertIn("foreign tax paid 100.00", row["answer"])

    def test_foreign_income_top_level_item_total_conflicts_stay_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "amount": 150,
                    "foreign_tax_paid": 20,
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "country": "US",
                            "amount": 100,
                            "foreign_tax_paid": 10,
                            "exchange_rate": 0.66,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("numeric amount or exchange-rate evidence", row["tab_text"])

    def test_foreign_income_item_uncertain_offset_claim_needs_tax_paid(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "foreign_tax_offset_claim": "unsure",
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("foreign tax paid evidence", row["tab_text"])

    def test_foreign_income_item_boolean_tax_paid_is_missing_for_offset_claim(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "country": "US",
                            "amount": 100,
                            "exchange_rate": 0.66,
                            "foreign_tax_offset_claim": True,
                            "foreign_tax_paid": False,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("foreign tax paid evidence", row["tab_text"])
        self.assertIn("foreign tax paid unknown", row["answer"])

    def test_foreign_income_items_render_item_values(self) -> None:
        item = {
            "statement": "statement held",
            "country": "US",
            "income_type": "pension",
            "amount": 120,
            "foreign_tax_paid": 0,
            "exchange_rate": 0.65,
            "residency_status": "Australian resident",
            "foreign_tax_offset_claim": False,
            "foreign_employment_exempt_claim": False,
        }
        for answers in [{"foreign_income_items": [item]}, {"foreign_income": {"residency_status": "Australian resident", "items": [item]}}]:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

                self.assertEqual("Accountant review", row["status"])
                self.assertIn("Country US", row["answer"])
                self.assertIn("amount 120.00", row["answer"])
                self.assertIn("foreign tax paid 0.00", row["answer"])
                self.assertIn("residency Australian resident", row["answer"])
                self.assertIn("foreign tax offset claim false", row["answer"])
                self.assertIn("foreign employment exemption claim false", row["answer"])
                self.assertIn("items US: type pension, amount 120.00", row["answer"])

    def test_top_level_foreign_statement_covers_itemized_rows(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "country": "US",
                            "income_type": "employment",
                            "amount": 100,
                            "foreign_tax_paid": 10,
                            "exchange_rate": 0.66,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertEqual("Foreign income needs source-backed accountant review.", row["tab_text"])
        self.assertIn("items US: type employment, amount 100.00", row["answer"])

    def test_foreign_income_item_exchange_rates_are_not_added(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "country": "US",
                            "income_type": "employment",
                            "amount": 100,
                            "foreign_tax_paid": 10,
                            "exchange_rate": 0.66,
                        },
                        {
                            "country": "Canada",
                            "income_type": "pension",
                            "amount": 50,
                            "foreign_tax_paid": 5,
                            "exchange_rate": 0.50,
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("exchange rate item-specific", row["answer"])
        self.assertNotIn("exchange rate 1.16", row["answer"])
        self.assertIn("items US: type employment, amount 100.00, foreign tax paid 10.00, exchange rate 0.66", row["answer"])
        self.assertIn("Canada: type pension, amount 50.00, foreign tax paid 5.00, exchange rate 0.5", row["answer"])

    def test_foreign_income_item_missing_statement_stays_evidence_without_top_statement(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "statement": "statement held",
                            "country": "US",
                            "amount": 100,
                            "foreign_tax_paid": 10,
                            "exchange_rate": 0.66,
                        },
                        {
                            "statement": "statement not held",
                            "country": "Canada",
                            "amount": 50,
                            "foreign_tax_paid": 5,
                            "exchange_rate": 0.50,
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("statement evidence", row["tab_text"])

    def test_foreign_income_top_statement_does_not_hide_explicit_item_statement_gap(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "residency_status": "Australian resident",
                    "items": [
                        {
                            "statement": "statement not held",
                            "country": "US",
                            "amount": 100,
                            "foreign_tax_paid": 10,
                            "exchange_rate": 0.66,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "FOREIGN-INCOME")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("statement evidence", row["tab_text"])

    def test_foreign_income_review_row_appears_in_html_pack(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Foreign and worldwide income", body)
        self.assertIn("Foreign income needs source-backed accountant review.", body)
        self.assertIn("foreign tax paid 0.00", body)
        self.assertNotIn("lodgment-ready", body)

    def test_foreign_income_sources_are_registered_and_covered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "data" / "ato_knowledge_base" / "source_registry.json").read_text())
        coverage = json.loads((root / "data" / "ato_knowledge_base" / "source_coverage.json").read_text())
        registry_urls = {item["url"] for item in registry["records"]}
        covered = {item["canonical_url"]: item for item in coverage["sources"]}

        for url in taxmate_intake.ATO_FOREIGN_INCOME_SOURCES:
            with self.subTest(url=url):
                self.assertIn(url, registry_urls)
                self.assertEqual("verified", covered[url]["status"])
                self.assertTrue(covered[url]["skills"])

    def test_individual_return_portable_skill_covers_foreign_income_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "skills" / "individual-return" / "SKILL.md").read_text()
        rules = (root / "skills" / "individual-return" / "references" / "rules.md").read_text()
        out_of_scope = skill.split("## Out Of Scope", 1)[1].split("## Method", 1)[0]

        self.assertIn("foreign income", skill)
        self.assertIn("foreign employment", skill)
        self.assertIn("foreign income tax offset", skill)
        self.assertIn("residency-specific", skill)
        self.assertIn(taxmate_intake.ATO_FOREIGN_WORLDWIDE_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_FOREIGN_RESIDENT_INCOME_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_FOREIGN_TEMP_RESIDENT_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_FOREIGN_EMPLOYMENT_EXEMPT_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_FOREIGN_INCOME_TAX_OFFSET_SOURCE, rules)
        self.assertNotIn("foreign income", out_of_scope.lower())

    def test_psi_workflow_renders_source_backed_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = next(item for item in payload["items"] if item["number"] == "PSI")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("Income 18000.00", row["answer"])
        self.assertIn("type IT consulting", row["answer"])
        self.assertIn("results test true", row["answer"])
        self.assertIn("80% test false", row["answer"])
        self.assertIn("business premises test false", row["answer"])
        self.assertIn("structure sole trader ABN", row["answer"])
        self.assertIn(taxmate_intake.ATO_PSI_SOURCE, row["source_urls"])

    def test_no_psi_answers_do_not_render_workflow_row(self) -> None:
        for answers in [
            {"psi_contract_evidence": "no PSI"},
            {"psi_contract_evidence": "no personal services income"},
            {"psi_income": "no PSI"},
            {"psi_income": "no personal services income"},
            {"psi_income": "not applicable"},
            {"psi_business_structure": "no PSI"},
            {"psi_deductions": "not applicable"},
            {"psi_results_test": "no personal services income"},
            {"psi_contract_evidence": "I do not have personal services income"},
            {"psi": {"contract_evidence": "I don't have PSI"}},
            {"psi": {"contract_evidence": "I dont have PSI"}},
            {"psi": {"income": "no PSI"}},
            {"psi": {"business_structure": "no personal services income"}},
            {"psi": {"contract_evidence": "not applicable"}},
        ]:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                rendered_numbers = {row["number"] for row in payload["items"]}

                self.assertNotIn("PSI", rendered_numbers)
                self.assertNotIn("psi_income", rendered_numbers)
                self.assertNotIn("psi_business_structure", rendered_numbers)
                self.assertNotIn("psi_deductions", rendered_numbers)
                self.assertNotIn("psi_results_test", rendered_numbers)

    def test_psi_document_denial_stays_evidence(self) -> None:
        for statement in ["no PSI contract", "no personal services income invoice", "I dont have the PSI contract"]:
            with self.subTest(statement=statement):
                payload = taxmate_intake.answers_to_pack_payload({"psi_contract_evidence": statement})
                row = next(item for item in payload["items"] if item["number"] == "PSI")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("contract or invoice evidence", row["tab_text"])

    def test_no_psi_plus_facts_stays_evidence(self) -> None:
        cases = [
            {
                "psi_contract_evidence": "no PSI",
                "psi_income": 5000,
                "psi_results_test": True,
                "psi_80_percent_test": False,
            },
            {
                "psi_income": "no PSI",
                "psi_results_test": True,
                "psi_80_percent_test": False,
            },
            {
                "psi": {
                    "income": "no personal services income",
                    "results_test": True,
                    "eighty_percent_test": False,
                }
            },
            {
                "psi_business_structure": "no PSI",
                "psi_results_test": True,
                "psi_80_percent_test": False,
            },
            {
                "psi": {
                    "business_structure": "not applicable",
                    "results_test": True,
                    "eighty_percent_test": False,
                }
            },
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "PSI")
                rendered_numbers = {item["number"] for item in payload["items"]}

                self.assertEqual("Evidence", row["status"])
                if answers.get("psi_income") == "no PSI" or (
                    isinstance(answers.get("psi"), dict) and answers["psi"].get("income") == "no personal services income"
                ):
                    self.assertNotIn("psi_income", rendered_numbers)
                self.assertNotIn("psi_business_structure", rendered_numbers)

    def test_psi_missing_or_ambiguous_facts_stay_evidence(self) -> None:
        cases = [
            {"psi": {"income": "about $100", "contract_evidence": "contracts held"}},
            {"psi": {"income": 100, "contract_evidence": "contracts held", "results_test": "unknown"}},
            {"psi": {"income": 100, "contract_evidence": "contracts held", "results_test": "maybe yes"}},
            {"psi": {"income": 100, "contract_evidence": "contracts held", "results_test": True}},
            {"psi": {"income": 100, "contract_evidence": "contract not provided", "results_test": True}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "PSI")

                self.assertEqual("Evidence", row["status"])

    def test_psi_zero_and_false_values_are_preserved(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "psi": {
                    "income": 0,
                    "income_type": "consulting",
                    "contract_evidence": "contracts and invoices held",
                    "results_test": False,
                    "eighty_percent_test": False,
                    "unrelated_clients_test": False,
                    "employment_test": False,
                    "business_premises_test": False,
                    "psb_determination": False,
                    "attribution_entity": "individual",
                    "deductions": "none",
                    "business_structure": "sole trader",
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "PSI")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("Income 0.00", row["answer"])
        self.assertIn("results test false", row["answer"])
        self.assertIn("PSB determination false", row["answer"])

    def test_psi_review_row_appears_in_html_pack(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Personal services income", body)
        self.assertIn("PSI tests, attribution, deductions, and structure stay accountant review before manual copy.", body)
        self.assertIn("80% test false", body)
        self.assertNotIn("lodgment-ready", body)

    def test_psi_sources_are_registered_and_covered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "data" / "ato_knowledge_base" / "source_registry.json").read_text())
        coverage = json.loads((root / "data" / "ato_knowledge_base" / "source_coverage.json").read_text())
        registry_urls = {item["url"] for item in registry["records"]}
        covered = {item["canonical_url"]: item for item in coverage["sources"]}

        for url in taxmate_intake.ATO_PSI_SOURCES:
            with self.subTest(url=url):
                self.assertIn(url, registry_urls)
                self.assertEqual("verified", covered[url]["status"])
                self.assertIn("abn-business", covered[url]["skills"])

    def test_individual_return_portable_skill_covers_psi_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "skills" / "individual-return" / "SKILL.md").read_text()
        rules = (root / "skills" / "individual-return" / "references" / "rules.md").read_text()
        out_of_scope = skill.split("## Out Of Scope", 1)[1].split("## Method", 1)[0]

        self.assertIn("PSI deep", skill)
        self.assertIn("results test", skill)
        self.assertIn("80% client concentration", skill)
        self.assertIn("unrelated clients test", skill)
        self.assertIn("employment test", skill)
        self.assertIn("business premises test", skill)
        self.assertIn("business structure", skill)
        self.assertIn(taxmate_intake.ATO_PSI_SOURCE, rules)
        self.assertNotIn("PSI deep", out_of_scope)

    def test_crypto_workflow_renders_source_backed_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("Event sale", row["answer"])
        self.assertIn("asset ETH", row["answer"])
        self.assertIn("cost base 3000.00", row["answer"])
        self.assertIn("capital proceeds 4200.00", row["answer"])
        self.assertIn("rewards income 0.00", row["answer"])
        self.assertIn("own-wallet transfer false", row["answer"])
        self.assertIn("business use false", row["answer"])
        self.assertIn("private use true", row["answer"])
        for url in taxmate_intake.ATO_CRYPTO_SOURCES:
            self.assertIn(url, row["source_urls"])

    def test_no_crypto_answers_do_not_render_workflow_or_base_rows(self) -> None:
        cases = [
            {"crypto_event_type": "no crypto"},
            {"crypto_event_type": "no crypto assets"},
            {"crypto_asset": "no cryptocurrency"},
            {"crypto_quantity": "no crypto"},
            {"crypto_acquired_date": "not applicable"},
            {"crypto_disposed_date": "n/a"},
            {"crypto_cost_base": "no crypto"},
            {"crypto_capital_proceeds": "no crypto"},
            {"crypto_rewards_income": "no staking rewards"},
            {"crypto_transfer_between_wallets": "no crypto"},
            {"crypto_wallet_records": "no crypto"},
            {"crypto_ownership_entity": "not applicable"},
            {"crypto_business_use": "no crypto assets"},
            {"crypto_private_use": "no crypto assets"},
            {"crypto": {"event_type": "I don't have crypto"}},
            {"crypto": {"event_type": "I dont have crypto"}},
            {"crypto": {"asset": "no digital currency"}},
            {"crypto": {"wallet_records": "not applicable"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                rendered_numbers = {row["number"] for row in payload["items"]}

                self.assertNotIn("CRYPTO-CGT", rendered_numbers)
                self.assertFalse(any(str(number).startswith("crypto_") for number in rendered_numbers))

    def test_false_crypto_defaults_do_not_render_base_rows(self) -> None:
        cases = [
            {
                "crypto_transfer_between_wallets": False,
                "crypto_business_use": False,
                "crypto_private_use": False,
            },
            {
                "crypto_transfer_between_wallets": "false",
                "crypto_business_use": "false",
                "crypto_private_use": "no",
            },
            {
                "crypto_transfer_between_wallets": "0",
                "crypto_business_use": 0,
                "crypto_private_use": "off",
            },
            {
                "crypto_transfer_between_wallets": "unchecked",
                "crypto_business_use": "unchecked",
                "crypto_private_use": "unchecked",
            },
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                rendered_numbers = {row["number"] for row in payload["items"]}

                self.assertNotIn("CRYPTO-CGT", rendered_numbers)
                self.assertNotIn("crypto_transfer_between_wallets", rendered_numbers)
                self.assertNotIn("crypto_business_use", rendered_numbers)
                self.assertNotIn("crypto_private_use", rendered_numbers)

    def test_crypto_record_denials_stay_evidence(self) -> None:
        for records in [
            "no wallet records",
            "no exchange records",
            "I have no records",
            "we have no exchange records",
            "without any wallet records",
            "missing transaction history",
            "records not provided",
            "do not have wallet records",
            "don't have exchange records",
            "dont have exchange records",
            "I do not have wallet transaction history",
        ]:
            with self.subTest(records=records):
                payload = taxmate_intake.answers_to_pack_payload({"crypto_wallet_records": records})
                rows = {item["number"]: item for item in payload["items"]}

                self.assertEqual("Evidence", rows["crypto_wallet_records"]["status"])
                self.assertEqual("Evidence", rows["CRYPTO-CGT"]["status"])
                self.assertIn("wallet or exchange records", rows["CRYPTO-CGT"]["tab_text"])

    def test_crypto_record_no_disposal_note_is_not_missing_records(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "sale",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 1,
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": 100,
                    "capital_proceeds": 300,
                    "wallet_records": "records show no disposal outside the listed sale",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertNotIn("wallet or exchange records", row["tab_text"])

    def test_crypto_identity_denials_stay_evidence(self) -> None:
        complete_sale = {
            "event_type": "sale",
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 300,
            "wallet_records": "records held",
            "ownership_entity": "individual",
            "business_use": False,
            "private_use": True,
        }
        cases = [
            ("asset and exchange/wallet identity evidence", {"exchange_or_wallet": "no exchange"}),
            ("asset and exchange/wallet identity evidence", {"exchange_or_wallet": "no wallet"}),
            ("asset and exchange/wallet identity evidence", {"exchange_or_wallet": "I do not have a wallet"}),
            ("asset and exchange/wallet identity evidence", {"asset": "no asset"}),
            ("ownership or entity evidence", {"ownership_entity": "no ownership entity"}),
            ("ownership or entity evidence", {"ownership_entity": "missing owner"}),
        ]
        for expected_gap, override in cases:
            with self.subTest(override=override):
                payload = taxmate_intake.answers_to_pack_payload({"crypto": {**complete_sale, **override}})
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn(expected_gap, row["tab_text"])
                self.assertNotIn("no-crypto answer with crypto facts", row["tab_text"])

    def test_crypto_item_identity_denials_stay_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "event_type": "sale",
                        "asset": "ETH",
                        "exchange_or_wallet": "no wallet",
                        "quantity": 1,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": 100,
                        "capital_proceeds": 300,
                        "wallet_records": "records held",
                        "ownership_entity": "individual",
                        "business_use": False,
                        "private_use": True,
                    }
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("per-item crypto evidence", row["tab_text"])

    def test_crypto_item_record_denials_stay_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "event_type": "sale",
                        "asset": "BTC",
                        "exchange_or_wallet": "Exchange CSV",
                        "quantity": 1,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": 100,
                        "capital_proceeds": 300,
                        "wallet_records": "do not have wallet records",
                        "ownership_entity": "individual",
                        "business_use": False,
                        "private_use": True,
                    }
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("per-item crypto evidence", row["tab_text"])

    def test_no_crypto_plus_facts_stays_evidence(self) -> None:
        cases = [
            {"crypto_event_type": "no crypto", "crypto_asset": "BTC"},
            {"crypto_asset": "no cryptocurrency", "crypto_cost_base": 100},
            {"crypto_event_type": "no crypto", "crypto_asset": "unknown"},
            {"crypto": {"event_type": "no crypto assets", "asset": "ETH"}},
            {"crypto": {"event_type": "no crypto assets", "exchange_or_wallet": "unknown"}},
            {"crypto": {"wallet_records": "not applicable", "capital_proceeds": 200}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("before accountant review", row["tab_text"])

    def test_crypto_field_absence_is_not_no_crypto_contradiction(self) -> None:
        complete_sale = {
            "event_type": "sale",
            "asset": "BTC",
            "exchange_or_wallet": "Coinbase",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 200,
            "wallet_records": "records held",
            "ownership_entity": "self",
            "business_use": False,
            "private_use": True,
        }
        payload = taxmate_intake.answers_to_pack_payload(
            {"crypto": {**complete_sale, "rewards_income": "no staking rewards"}}
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertNotIn("no-crypto answer with crypto facts", row["tab_text"])
        self.assertNotIn("decline signals", row["answer"])

        evidence_cases = [
            ("acquisition or disposal date evidence", {"acquired_date": "n/a"}),
            ("wallet or exchange records", {"wallet_records": "not applicable"}),
        ]
        for expected_gap, override in evidence_cases:
            with self.subTest(override=override):
                payload = taxmate_intake.answers_to_pack_payload({"crypto": {**complete_sale, **override}})
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn(expected_gap, row["tab_text"])
                self.assertNotIn("no-crypto answer with crypto facts", row["tab_text"])
                self.assertNotIn("decline signals", row["answer"])

    def test_crypto_item_no_crypto_plus_facts_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "event_type": "no crypto",
                        "asset": "BTC",
                        "exchange_or_wallet": "Exchange CSV",
                        "quantity": 1,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": 100,
                        "capital_proceeds": 300,
                        "wallet_records": "records held",
                        "ownership_entity": "individual",
                        "business_use": False,
                        "private_use": True,
                    }
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("no-crypto answer with crypto facts", row["tab_text"])

    def test_nested_crypto_no_crypto_plus_item_facts_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "no crypto",
                    "items": [
                        {
                            "event_type": "sale",
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                            "wallet_records": "records held",
                            "ownership_entity": "individual",
                            "transfer_between_wallets": False,
                            "business_use": False,
                            "private_use": True,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("no-crypto answer with crypto facts", row["tab_text"])
        self.assertIn("items BTC", row["answer"])

    def test_flat_no_crypto_plus_nested_facts_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_event_type": "no crypto",
                "crypto": {
                    "event_type": "sale",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 1,
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": 100,
                    "capital_proceeds": 300,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "transfer_between_wallets": False,
                    "business_use": False,
                    "private_use": True,
                },
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("no-crypto answer with crypto facts", row["tab_text"])
        self.assertIn("Event sale", row["answer"])
        self.assertIn("decline signals event_type no crypto", row["answer"])
        self.assertIn("asset BTC", row["answer"])

    def test_flat_no_crypto_plus_flat_facts_keeps_contradiction_signal(self) -> None:
        for field in taxmate_intake.CRYPTO_SOURCE_KEY_FACTS:
            answers = {f"crypto_{field}": "no crypto"}
            if field == "asset":
                answers["crypto_event_type"] = "sale"
            else:
                answers["crypto_asset"] = "BTC"
            with self.subTest(field=field):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("no-crypto answer with crypto facts", row["tab_text"])
                self.assertIn("no crypto", row["answer"])

    def test_nested_no_crypto_plus_nested_facts_keeps_contradiction_signal(self) -> None:
        for field in taxmate_intake.CRYPTO_SOURCE_KEY_FACTS:
            crypto = {field: "no crypto"}
            if field == "asset":
                crypto["event_type"] = "sale"
            else:
                crypto["asset"] = "BTC"
            with self.subTest(field=field):
                payload = taxmate_intake.answers_to_pack_payload({"crypto": crypto})
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("no-crypto answer with crypto facts", row["tab_text"])
                self.assertIn("no crypto", row["answer"])

    def test_crypto_same_field_flat_nested_conflicts_keep_decline_signal(self) -> None:
        fact_values = {
            "event_type": "sale",
            "exchange_or_wallet": "Exchange CSV",
            "asset": "BTC",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 300,
            "rewards_income": 0,
            "transfer_between_wallets": False,
            "wallet_records": "records held",
            "ownership_entity": "individual",
            "business_use": False,
            "private_use": True,
        }
        rendered_fact_text = {
            "event_type": "Event sale",
            "exchange_or_wallet": "exchange/wallet Exchange CSV",
            "asset": "asset BTC",
            "quantity": "quantity 1",
            "acquired_date": "acquired 2025-07-01",
            "disposed_date": "disposed 2026-01-01",
            "cost_base": "cost base 100.00",
            "capital_proceeds": "capital proceeds 300.00",
            "rewards_income": "rewards income 0.00",
            "transfer_between_wallets": "own-wallet transfer false",
            "wallet_records": "records records held",
            "ownership_entity": "owner/entity individual",
            "business_use": "business use false",
            "private_use": "private use true",
        }
        for field, fact in fact_values.items():
            with self.subTest(flat_decline_field=field):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        f"crypto_{field}": "no crypto",
                        "crypto": {**fact_values, field: fact},
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("no-crypto answer with crypto facts", row["tab_text"])
                self.assertIn(rendered_fact_text[field], row["answer"])
                self.assertIn(f"{field} no crypto", row["answer"])

    def test_crypto_missing_or_ambiguous_facts_stay_evidence(self) -> None:
        cases = [
            {"crypto": {"event_type": "sale", "asset": "BTC", "wallet_records": "records held"}},
            {
                "crypto": {
                    "event_type": "sale",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": "unknown",
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": "about $100",
                    "capital_proceeds": 300,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                }
            },
            {
                "crypto": {
                    "event_type": "swap",
                    "asset": "ETH",
                    "exchange_or_wallet": "wallet export",
                    "quantity": 1,
                    "acquired_date": "2025/07/01",
                    "disposed_date": "2026-01-01",
                    "cost_base": 100,
                    "capital_proceeds": 300,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                }
            },
            {
                "crypto": {
                    "event_type": "sale",
                    "asset": "ETH",
                    "exchange_or_wallet": "wallet export",
                    "quantity": 1,
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": -100,
                    "capital_proceeds": 300,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                }
            },
            {
                "crypto": {
                    "event_type": "staking rewards",
                    "asset": "SOL",
                    "exchange_or_wallet": "wallet export",
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                }
            },
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("before accountant review", row["tab_text"])

    def test_crypto_exchange_and_conversion_events_require_disposal_facts(self) -> None:
        for event_type in ["exchange", "exchanged BTC for ETH", "convert", "converted to SOL", "conversion"]:
            with self.subTest(event_type=event_type):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "crypto": {
                            "event_type": event_type,
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "wallet_records": "records held",
                            "ownership_entity": "individual",
                            "business_use": False,
                            "private_use": True,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric proceeds, cost-base, quantity, or rewards evidence", row["tab_text"])
                self.assertIn("acquisition or disposal date evidence", row["tab_text"])

    def test_complete_crypto_exchange_stays_accountant_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "exchange BTC for ETH",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 1,
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": 100,
                    "capital_proceeds": 300,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertNotIn("numeric proceeds, cost-base, quantity, or rewards evidence", row["tab_text"])
        self.assertNotIn("acquisition or disposal date evidence", row["tab_text"])

    def test_crypto_zero_amounts_and_false_booleans_are_preserved(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "sale",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 0,
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": 0,
                    "capital_proceeds": 0,
                    "rewards_income": 0,
                    "transfer_between_wallets": False,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": False,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("quantity 0", row["answer"])
        self.assertIn("cost base 0.00", row["answer"])
        self.assertIn("capital proceeds 0.00", row["answer"])
        self.assertIn("own-wallet transfer false", row["answer"])
        self.assertIn("business use false", row["answer"])
        self.assertIn("private use false", row["answer"])

    def test_crypto_textual_use_flags_complete_context(self) -> None:
        base = {
            "event_type": "sale",
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 300,
            "wallet_records": "records held",
            "ownership_entity": "individual",
            "business_use": "no",
            "private_use": "yes",
        }
        cases = [
            {"crypto": base},
            {"crypto_items": [base]},
            {"crypto": {**base, "transfer_between_wallets": "on"}},
            {"crypto_items": [{**base, "transfer_between_wallets": "1"}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Accountant review", row["status"])
                self.assertNotIn("business/private use context", row["tab_text"])
                self.assertIn("business use no", row["answer"])
                self.assertIn("private use yes", row["answer"])

    def test_crypto_item_absence_values_do_not_create_amount_or_date_evidence(self) -> None:
        base = {
            "event_type": "sale",
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 300,
            "wallet_records": "records held",
            "ownership_entity": "individual",
            "business_use": False,
            "private_use": True,
        }
        cases = [
            {"rewards_income": "no staking rewards"},
            {"rewards_income": "n/a"},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                payload = taxmate_intake.answers_to_pack_payload({"crypto_items": [{**base, **extra}]})
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Accountant review", row["status"])
                self.assertNotIn("per-item crypto evidence", row["tab_text"])
                self.assertNotIn("numeric proceeds, cost-base, quantity, or rewards evidence", row["tab_text"])

    def test_crypto_factless_item_absence_values_do_not_render_workflow(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "rewards_income": "no staking rewards",
                        "disposed_date": "n/a",
                    }
                ]
            }
        )
        rendered_numbers = {item["number"] for item in payload["items"]}

        self.assertNotIn("CRYPTO-CGT", rendered_numbers)

    def test_crypto_items_are_validated_individually(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "event_type": "sale",
                        "asset": "BTC",
                        "exchange_or_wallet": "Exchange CSV",
                        "quantity": 1,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": 100,
                        "capital_proceeds": 300,
                        "wallet_records": "records held",
                        "ownership_entity": "individual",
                        "business_use": False,
                        "private_use": True,
                    },
                    {
                        "quantity": 2,
                        "cost_base": 200,
                        "capital_proceeds": 400,
                        "wallet_records": "records held",
                    },
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("per-item crypto evidence", row["tab_text"])
        self.assertIn("item 2", row["answer"])

    def test_crypto_top_level_and_item_amount_conflicts_stay_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "sale",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 10,
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": 1000,
                    "capital_proceeds": 3000,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "event_type": "sale",
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                            "wallet_records": "records held",
                            "ownership_entity": "individual",
                            "business_use": False,
                            "private_use": True,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("top-level and item amount reconciliation", row["tab_text"])

    def test_crypto_multi_asset_quantities_stay_item_specific(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "sale",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 99,
                    "cost_base": 400,
                    "capital_proceeds": 700,
                    "wallet_records": "exchange CSV covers all transactions",
                    "ownership_entity": "individual",
                    "transfer_between_wallets": False,
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "asset": "BTC",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                        },
                        {
                            "asset": "ETH",
                            "quantity": 2,
                            "acquired_date": "2025-08-01",
                            "disposed_date": "2026-02-01",
                            "cost_base": 300,
                            "capital_proceeds": 400,
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("quantity item-specific", row["answer"])
        self.assertNotIn("quantity 3", row["answer"])
        self.assertNotIn("top-level and item amount reconciliation", row["tab_text"])

    def test_crypto_same_asset_quantity_conflicts_stay_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "sale",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 99,
                    "cost_base": 400,
                    "capital_proceeds": 700,
                    "wallet_records": "exchange CSV covers all transactions",
                    "ownership_entity": "individual",
                    "transfer_between_wallets": False,
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                        },
                        {
                            "quantity": 2,
                            "acquired_date": "2025-08-01",
                            "disposed_date": "2026-02-01",
                            "cost_base": 300,
                            "capital_proceeds": 400,
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("quantity 3", row["answer"])
        self.assertIn("top-level and item amount reconciliation", row["tab_text"])

    def test_crypto_item_context_renders_when_top_level_missing(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "event_type": "sale",
                        "asset": "BTC",
                        "exchange_or_wallet": "Exchange CSV",
                        "quantity": 1,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": 100,
                        "capital_proceeds": 300,
                        "wallet_records": "records held",
                        "ownership_entity": "individual",
                        "transfer_between_wallets": False,
                        "business_use": False,
                        "private_use": True,
                    }
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("own-wallet transfer false", row["answer"])
        self.assertIn("records records held", row["answer"])
        self.assertIn("business use false", row["answer"])
        self.assertIn("private use true", row["answer"])

    def test_crypto_items_reuse_complete_top_level_use_context(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "event_type": "sale",
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                            "wallet_records": "records held",
                            "ownership_entity": "individual",
                            "transfer_between_wallets": False,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertNotIn("per-item crypto evidence", row["tab_text"])
        self.assertIn("business use false", row["answer"])
        self.assertIn("private use true", row["answer"])

    def test_crypto_item_use_context_conflict_stays_visible(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "event_type": "sale",
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                            "wallet_records": "records held",
                            "ownership_entity": "individual",
                            "transfer_between_wallets": False,
                            "business_use": True,
                            "private_use": False,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("business/private use context", row["tab_text"])
        self.assertIn("business use false", row["answer"])
        self.assertIn("private use true", row["answer"])
        self.assertIn("acquired 2025-07-01", row["answer"])
        self.assertIn("disposed 2026-01-01", row["answer"])
        self.assertIn("exchange/wallet Exchange CSV", row["answer"])
        self.assertIn("business use true", row["answer"])
        self.assertIn("private use false", row["answer"])

    def test_crypto_items_reuse_top_level_records_and_context(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "sale",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "wallet_records": "exchange CSV covers all transactions",
                    "ownership_entity": "individual",
                    "transfer_between_wallets": False,
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Accountant review", row["status"])
        self.assertNotIn("per-item crypto evidence", row["tab_text"])
        self.assertNotIn("wallet or exchange records", row["tab_text"])
        self.assertIn("records exchange CSV covers all transactions", row["answer"])

    def test_crypto_item_explicit_context_gaps_override_top_level_context(self) -> None:
        base = {
            "event_type": "sale",
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "wallet_records": "exchange CSV covers all transactions",
            "ownership_entity": "individual",
            "transfer_between_wallets": False,
            "business_use": False,
            "private_use": True,
        }
        item = {
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 300,
        }
        cases = [
            {"wallet_records": "not applicable"},
            {"ownership_entity": "unknown"},
            {"asset": "n/a"},
        ]
        for explicit_gap in cases:
            with self.subTest(explicit_gap=explicit_gap):
                payload = taxmate_intake.answers_to_pack_payload(
                    {"crypto": {**base, "items": [{**item, **explicit_gap}]}}
                )
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("per-item crypto evidence", row["tab_text"])

    def test_crypto_items_require_amounts_and_dates_under_top_level_events(self) -> None:
        base = {
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "wallet_records": "exchange CSV covers all transactions",
            "ownership_entity": "individual",
            "business_use": False,
            "private_use": True,
        }
        complete_sale_item = {
            "asset": "BTC",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 300,
        }
        complete_reward_item = {"asset": "SOL", "rewards_income": 25}
        cases = [
            ("sale", complete_sale_item, {"asset": "ETH"}),
            ("exchange BTC for ETH", complete_sale_item, {"asset": "ETH", "quantity": 2}),
            ("staking rewards", complete_reward_item, {"asset": "SOL"}),
        ]
        for event_type, complete_item, incomplete_item in cases:
            with self.subTest(event_type=event_type):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "crypto": {
                            **base,
                            "event_type": event_type,
                            "items": [complete_item, incomplete_item],
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("per-item crypto evidence", row["tab_text"])

    def test_crypto_item_ambiguous_use_context_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "event_type": "sale",
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                            "wallet_records": "records held",
                            "ownership_entity": "individual",
                            "transfer_between_wallets": False,
                            "business_use": "unknown",
                        }
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("per-item crypto evidence", row["tab_text"])

    def test_crypto_requires_both_top_level_use_context_flags(self) -> None:
        for context in [{"business_use": False}, {"business_use": False, "private_use": None}]:
            with self.subTest(context=context):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "crypto": {
                            "event_type": "sale",
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 300,
                            "wallet_records": "records held",
                            "ownership_entity": "individual",
                            **context,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("business/private use context", row["tab_text"])
                self.assertIn("business use false", row["answer"])
                self.assertIn("private use unknown", row["answer"])

    def test_crypto_requires_both_item_use_context_flags(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "event_type": "sale",
                        "asset": "BTC",
                        "exchange_or_wallet": "Exchange CSV",
                        "quantity": 1,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": 100,
                        "capital_proceeds": 300,
                        "wallet_records": "records held",
                        "ownership_entity": "individual",
                        "business_use": False,
                    }
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("business/private use context", row["tab_text"])
        self.assertIn("business use false", row["answer"])
        self.assertIn("private use unknown", row["answer"])

    def test_crypto_transfer_event_requires_own_wallet_support(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "transfer",
                    "asset": "BTC",
                    "exchange_or_wallet": "Exchange CSV",
                    "quantity": 1,
                    "acquired_date": "2025-07-01",
                    "disposed_date": "2026-01-01",
                    "cost_base": 100,
                    "capital_proceeds": 100,
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("own-wallet transfer support", row["tab_text"])
        self.assertIn("own-wallet transfer unknown", row["answer"])

    def test_crypto_ambiguous_boolean_context_stays_evidence(self) -> None:
        cases = [
            (
                {"transfer_between_wallets": "maybe yes", "business_use": False, "private_use": True},
                "own-wallet transfer support",
                "own-wallet transfer maybe yes",
            ),
            (
                {"transfer_between_wallets": "maybe not own wallet", "business_use": False, "private_use": True},
                "own-wallet transfer support",
                "own-wallet transfer maybe not own wallet",
            ),
            (
                {"transfer_between_wallets": True, "business_use": "possibly business use", "private_use": True},
                "business/private use context",
                "business use possibly business use",
            ),
            (
                {"transfer_between_wallets": True, "business_use": False, "private_use": "unclear"},
                "business/private use context",
                "private use unclear",
            ),
        ]
        base = {
            "event_type": "transfer",
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 100,
            "wallet_records": "records held",
            "ownership_entity": "individual",
        }
        for context, expected_gap, expected_answer in cases:
            with self.subTest(context=context):
                payload = taxmate_intake.answers_to_pack_payload({"crypto": {**base, **context}})
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn(expected_gap, row["tab_text"])
                self.assertIn(expected_answer, row["answer"])

    def test_crypto_item_ambiguous_transfer_flag_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto_items": [
                    {
                        "event_type": "transfer",
                        "asset": "BTC",
                        "exchange_or_wallet": "Exchange CSV",
                        "quantity": 1,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": 100,
                        "capital_proceeds": 100,
                        "transfer_between_wallets": "maybe",
                        "wallet_records": "records held",
                        "ownership_entity": "individual",
                        "business_use": False,
                        "private_use": True,
                    }
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("per-item crypto evidence", row["tab_text"])

    def test_crypto_items_inherit_transfer_support_requirement(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "crypto": {
                    "event_type": "transfer",
                    "wallet_records": "records held",
                    "ownership_entity": "individual",
                    "business_use": False,
                    "private_use": True,
                    "items": [
                        {
                            "asset": "BTC",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 1,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 100,
                            "capital_proceeds": 100,
                            "transfer_between_wallets": True,
                        },
                        {
                            "asset": "ETH",
                            "exchange_or_wallet": "Exchange CSV",
                            "quantity": 2,
                            "acquired_date": "2025-07-01",
                            "disposed_date": "2026-01-01",
                            "cost_base": 200,
                            "capital_proceeds": 200,
                        },
                    ],
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("per-item crypto evidence", row["tab_text"])

    def test_crypto_own_wallet_exchange_transfer_does_not_require_disposal_facts(self) -> None:
        base = {
            "event_type": "transfer from exchange to own wallet",
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "transfer_between_wallets": True,
            "wallet_records": "records held",
            "ownership_entity": "individual",
            "business_use": False,
            "private_use": True,
        }
        cases = [
            {"crypto": base},
            {"crypto_items": [base]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Accountant review", row["status"])
                self.assertNotIn("numeric proceeds, cost-base, quantity, or rewards evidence", row["tab_text"])
                self.assertNotIn("acquisition or disposal date evidence", row["tab_text"])

    def test_crypto_non_own_wallet_transfer_needs_disposal_facts(self) -> None:
        base = {
            "event_type": "transfer from exchange to another wallet",
            "asset": "BTC",
            "exchange_or_wallet": "Exchange CSV",
            "wallet_records": "records held",
            "ownership_entity": "individual",
            "business_use": False,
            "private_use": True,
        }
        cases = [
            {"crypto": {**base, "transfer_between_wallets": False}},
            {"crypto": {**base, "transfer_between_wallets": "0"}},
            {"crypto": {**base, "transfer_between_wallets": "off"}},
            {"crypto_items": [{**base, "transfer_between_wallets": "unchecked"}]},
            {"crypto": {**base, "transfer_between_wallets": "not own wallet"}},
            {"crypto_items": [{**base, "transfer_between_wallets": "not between own wallets"}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "CRYPTO-CGT")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric proceeds, cost-base, quantity, or rewards evidence", row["tab_text"])
                self.assertIn("acquisition or disposal date evidence", row["tab_text"])

    def test_crypto_review_row_appears_in_html_pack(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Crypto asset investments", body)
        self.assertIn(
            "Crypto disposals, swaps, exchanges, conversions, rewards, transfers, wallet records, and cost base stay accountant review before manual copy.",
            body,
        )
        self.assertIn("business use false", body)
        self.assertNotIn("lodgment-ready", body)

    def test_crypto_sources_are_registered_and_covered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "data" / "ato_knowledge_base" / "source_registry.json").read_text())
        coverage = json.loads((root / "data" / "ato_knowledge_base" / "source_coverage.json").read_text())
        registry_urls = {item["url"] for item in registry["records"]}
        covered = {item["canonical_url"]: item for item in coverage["sources"]}

        for url in taxmate_intake.ATO_CRYPTO_SOURCES:
            with self.subTest(url=url):
                self.assertIn(url, registry_urls)
                self.assertEqual("verified", covered[url]["status"])
                self.assertIn("crypto-assets", covered[url]["skills"])

    def test_individual_return_portable_skill_covers_crypto_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "skills" / "individual-return" / "SKILL.md").read_text()
        root_skill = (root / "skills" / "taxmate-australia" / "SKILL.md").read_text()
        prep_doc = (root / "docs" / "INDIVIDUAL_RETURN_PREP.md").read_text()
        rules = (root / "skills" / "individual-return" / "references" / "rules.md").read_text()
        out_of_scope = skill.split("## Out Of Scope", 1)[1].split("## Method", 1)[0]

        self.assertIn("crypto CGT", skill)
        self.assertIn("staking/rewards", skill)
        self.assertIn("exchange, conversion", skill)
        self.assertIn("wallet or exchange records", skill)
        self.assertIn("cost base", skill)
        self.assertIn("capital proceeds", skill)
        self.assertIn("`crypto-assets`", skill)
        route_line = next(line for line in skill.splitlines() if "Route tax-treatment decisions" in line)
        for routed_skill in [
            "`shares-etfs-managed-funds`",
            "`capital-gains-tax`",
            "`crypto-assets`",
            "`property-rental-cgt`",
        ]:
            with self.subTest(routed_skill=routed_skill):
                self.assertIn(routed_skill, route_line)
                self.assertIn(routed_skill, prep_doc)
        self.assertIn("PSI, crypto CGT", root_skill)
        self.assertIn(taxmate_intake.ATO_CRYPTO_ASSETS_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_CRYPTO_RECORDS_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_CRYPTO_BUSINESS_SOURCE, rules)
        self.assertNotIn("crypto CGT", out_of_scope)

    def test_rental_property_workflow_renders_source_backed_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("Property Example rental unit", row["answer"])
        self.assertIn("income 18000.00", row["answer"])
        self.assertIn("interest 12500.00", row["answer"])
        self.assertIn("repairs 2400.00", row["answer"])
        self.assertIn("capital works 4500.00", row["answer"])
        self.assertIn("depreciation 1800.00", row["answer"])
        self.assertIn("private use true", row["answer"])
        self.assertIn("private days 14", row["answer"])
        self.assertIn("worksheet net -4800.00", row["answer"])
        self.assertIn("capital works or depreciation review", row["tab_text"])
        self.assertIn("private-use review", row["tab_text"])
        self.assertIn("net rental loss review", row["tab_text"])
        for url in taxmate_intake.ATO_RENTAL_PROPERTY_SOURCES:
            self.assertIn(url, row["source_urls"])

    def test_no_rental_property_answers_do_not_render_workflow_or_base_rows(self) -> None:
        cases = [
            {"rental_property_address": "no rental property"},
            {"rental_property_income": "no rental income this year"},
            {"rental_property": {"address": "I do not have a rental property"}},
            {"rental_property": {"records": "not applicable"}},
            {"rental_property_repairs": "no repairs"},
            {"rental_property_private_use": False},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                rendered_numbers = {row["number"] for row in payload["items"]}

                self.assertNotIn("RENTAL-PROPERTY", rendered_numbers)
                self.assertFalse(any(str(number).startswith("rental_property_") for number in rendered_numbers))

    def test_no_rental_property_plus_facts_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_address": "no rental property",
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 12000,
                    "records": "agent statement held",
                },
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("no-rental answer with rental facts", row["tab_text"])
        self.assertIn("Property Example rental", row["answer"])
        self.assertIn("decline signals address no rental property", row["answer"])

    def test_rental_property_missing_records_stay_evidence(self) -> None:
        for records in [
            "no rental records",
            "without agent statements",
            "records not provided",
            "I do not have loan interest statements",
            "none",
        ]:
            with self.subTest(records=records):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "rental_property": {
                            "address": "Example rental",
                            "ownership": "individual",
                            "income": 12000,
                            "records": records,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("rental records", row["tab_text"])
                self.assertIn(f"records {records}", row["answer"])

    def test_rental_property_flat_records_none_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_address": "Example rental",
                "rental_property_ownership": "individual",
                "rental_property_income": 12000,
                "rental_property_records": "none",
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("rental records", row["tab_text"])
        self.assertIn("records none", row["answer"])

    def test_rental_property_ambiguous_facts_stay_evidence(self) -> None:
        cases = [
            (
                {"repairs": "bathroom renovation and replacement"},
                "repairs versus capital classification",
                "repairs unknown",
                "Evidence",
            ),
            (
                {"private_use": True},
                "private-use apportionment evidence",
                "private use true",
                "Accountant review",
            ),
            (
                {"income": "unknown"},
                "rental income evidence",
                "income unknown",
                "Evidence",
            ),
            (
                {"interest": -10},
                "numeric rental amount evidence",
                "interest unknown",
                "Evidence",
            ),
            (
                {"private_use": None},
                "private-use apportionment evidence",
                "private use unknown",
                "Evidence",
            ),
        ]
        base = {
            "address": "Example rental",
            "ownership": "individual",
            "income": 12000,
            "interest": 5000,
            "records": "agent statement and loan statement held",
            "private_use": False,
        }
        for override, expected_gap, expected_answer, expected_status in cases:
            with self.subTest(override=override):
                payload = taxmate_intake.answers_to_pack_payload({"rental_property": {**base, **override}})
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual(expected_status, row["status"])
                self.assertIn(expected_gap, row["tab_text"])
                self.assertIn(expected_answer, row["answer"])

    def test_rental_property_missing_amount_documents_stay_evidence(self) -> None:
        cases = [
            ({"interest": "no loan statement"}, "interest no loan statement"),
            ({"repairs": "no invoice for repairs"}, "repairs no invoice for repairs"),
        ]
        base = {
            "address": "Example rental",
            "ownership": "individual",
            "income": 12000,
            "records": "agent statement held",
            "private_use": False,
        }
        for override, expected_answer in cases:
            with self.subTest(override=override):
                payload = taxmate_intake.answers_to_pack_payload({"rental_property": {**base, **override}})
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric rental amount evidence", row["tab_text"])
                self.assertIn(expected_answer, row["answer"])
                self.assertIn("worksheet net unknown", row["answer"])

    def test_rental_property_unusable_expense_keeps_net_unknown(self) -> None:
        cases = [
            {"interest": "unknown"},
            {"interest": -10},
            {"repairs": "not sure"},
            {"repairs": -10},
            {"capital_works": True},
            {"capital_works": -10},
            {"depreciation": "no depreciation schedule"},
            {"depreciation": -10},
            {"other_expenses": "invalid amount"},
            {"other_expenses": -10},
        ]
        base = {
            "address": "Example rental",
            "ownership": "individual",
            "income": 12000,
            "records": "agent statement held",
            "private_use": False,
        }
        for override in cases:
            with self.subTest(override=override):
                payload = taxmate_intake.answers_to_pack_payload({"rental_property": {**base, **override}})
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric rental amount evidence", row["tab_text"])
                self.assertIn("worksheet net unknown", row["answer"])

    def test_rental_property_unusable_income_keeps_net_unknown(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": -12000,
                    "interest": 1000,
                    "records": "agent statement held",
                    "private_use": False,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("numeric rental amount evidence", row["tab_text"])
        self.assertIn("income unknown", row["answer"])
        self.assertIn("worksheet net unknown", row["answer"])

    def test_rental_property_unusable_item_amount_keeps_net_unknown(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_records": "agent statement held",
                "rental_property_private_use": False,
                "rental_property_items": [
                    {"address": "Unit 1", "ownership": "individual", "income": 12000, "interest": -10},
                    {"address": "Unit 2", "ownership": "individual", "income": 8000, "interest": 1000},
                ],
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("numeric rental amount evidence", row["tab_text"])
        self.assertIn("interest 1000.00", row["answer"])
        self.assertIn("Unit 1: owner individual, income 12000.00, interest unknown", row["answer"])
        self.assertNotIn("interest -10.00", row["answer"])
        self.assertIn("worksheet net unknown", row["answer"])

    def test_rental_property_malformed_private_days_need_apportionment_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 12000,
                    "records": "agent statement held",
                    "private_use": True,
                    "private_use_days": -1,
                    "available_days": 365,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("numeric rental amount evidence", row["tab_text"])
        self.assertIn("private-use apportionment evidence", row["tab_text"])
        self.assertIn("private days unknown", row["answer"])

    def test_rental_property_flat_unknown_answers_render_workflow(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload({"rental_property_income": "unknown"})
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Evidence", row["status"])
        self.assertIn("rental income evidence", row["tab_text"])
        self.assertIn("income unknown", row["answer"])
        for url in taxmate_intake.ATO_RENTAL_PROPERTY_SOURCES:
            self.assertIn(url, row["source_urls"])

    def test_rental_property_negative_private_use_text_stays_false(self) -> None:
        cases = [
            "no private use",
            "no personal use",
            "not private use",
            "not for private use",
            "no holiday home use",
            "0",
            "off",
            "unchecked",
        ]
        for private_use in cases:
            with self.subTest(private_use=private_use):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "rental_property": {
                            "address": "Example rental",
                            "ownership": "individual",
                            "income": 12000,
                            "records": "agent statement held",
                            "private_use": private_use,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Accountant review", row["status"])
                self.assertIn(f"private use {private_use}", row["answer"])
                self.assertNotIn("private-use apportionment evidence", row["tab_text"])
                self.assertNotIn("private-use review", row["tab_text"])

    def test_rental_property_uncertain_private_use_stays_evidence(self) -> None:
        cases = ["not sure private use", "maybe", "possibly", "unclear", "not clear", "possibly private use"]
        for private_use in cases:
            with self.subTest(private_use=private_use):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "rental_property": {
                            "address": "Example rental",
                            "ownership": "individual",
                            "income": 12000,
                            "records": "agent statement held",
                            "private_use": private_use,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("private-use apportionment evidence", row["tab_text"])
                self.assertNotIn("private-use review", row["tab_text"])

    def test_rental_property_serialized_private_use_true_routes_review(self) -> None:
        for private_use in ["1", "on", "checked"]:
            with self.subTest(private_use=private_use):
                payload = taxmate_intake.answers_to_pack_payload(
                    {
                        "rental_property": {
                            "address": "Example rental",
                            "ownership": "individual",
                            "income": 12000,
                            "records": "agent statement held",
                            "private_use": private_use,
                        }
                    }
                )
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Accountant review", row["status"])
                self.assertIn("private-use apportionment evidence", row["tab_text"])
                self.assertIn("private-use review", row["tab_text"])

    def test_rental_property_false_private_use_and_net_loss_are_preserved(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_address": "Example rental",
                "rental_property_ownership": "individual",
                "rental_property_income": 10000,
                "rental_property_interest": 12000,
                "rental_property_records": "agent statement and loan statement held",
                "rental_property_private_use": False,
                "rental_property_net_loss": -2000,
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("private use false", row["answer"])
        self.assertIn("worksheet net -2000.00", row["answer"])
        self.assertIn("net rental loss review", row["tab_text"])
        self.assertNotIn("numeric rental amount evidence", row["tab_text"])

    def test_rental_property_positive_net_loss_amount_renders_as_loss(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 10000,
                    "interest": 12000,
                    "records": "agent statement and loan statement held",
                    "private_use": False,
                    "net_loss": 2000,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("worksheet net -2000.00", row["answer"])
        self.assertIn("net rental loss review", row["tab_text"])

    def test_rental_property_boolean_amounts_stay_evidence(self) -> None:
        cases = [
            *[
                {
                    "rental_property": {
                        "address": "Example rental",
                        "ownership": "individual",
                        "income": 10000,
                        "records": "agent statement held",
                        "private_use": False,
                        key: True,
                    }
                }
                for key in taxmate_intake.RENTAL_PROPERTY_AMOUNT_FIELDS
                if key != "net_loss"
            ],
            {
                "rental_property_income": True,
                "rental_property_address": "Example rental",
                "rental_property_ownership": "individual",
                "rental_property_records": "agent statement held",
                "rental_property_private_use": False,
            },
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 10000,
                    "records": "agent statement held",
                    "private_use": False,
                    "items": [{"address": "Unit 1", "capital_works": True, "records": "agent statement held"}],
                }
            },
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric rental amount evidence", row["tab_text"])
                self.assertNotIn("income true", row["answer"])

        payload = taxmate_intake.answers_to_pack_payload({"rental_property": {"net_loss": True}})
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")
        self.assertEqual("Accountant review", row["status"])
        self.assertIn("net rental loss review", row["tab_text"])
        self.assertNotIn("numeric rental amount evidence", row["tab_text"])

    def test_rental_property_standalone_net_loss_flag_renders_review(self) -> None:
        cases = [
            {"rental_property_net_loss": True},
            {"rental_property": {"net_loss": True}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Accountant review", row["status"])
                self.assertIn("net rental loss review", row["tab_text"])
                self.assertIn("worksheet net unknown", row["answer"])

    def test_rental_property_serialized_false_net_loss_is_absent(self) -> None:
        cases = [False, "false", "no", "n", "0", "off", "unchecked", "no loss", "no net loss", 0]
        for net_loss in cases:
            with self.subTest(net_loss=net_loss):
                nested = taxmate_intake.answers_to_pack_payload({"rental_property": {"net_loss": net_loss}})
                flat = taxmate_intake.answers_to_pack_payload({"rental_property_net_loss": net_loss})

                self.assertFalse(any(item["number"] == "RENTAL-PROPERTY" for item in nested["items"]))
                self.assertFalse(any(item["number"] == "RENTAL-PROPERTY" for item in flat["items"]))

    def test_rental_property_serialized_false_net_loss_keeps_real_facts(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 10000,
                    "records": "agent statement held",
                    "private_use": False,
                    "net_loss": "off",
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("worksheet net 10000.00", row["answer"])
        self.assertNotIn("numeric rental amount evidence", row["tab_text"])
        self.assertNotIn("net rental loss review", row["tab_text"])

    def test_rental_property_unresolved_net_loss_blocks_display_net(self) -> None:
        cases = [
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 10000,
                    "records": "agent statement held",
                    "private_use": False,
                    "net_loss": "unknown",
                }
            },
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 10000,
                    "records": "agent statement held",
                    "private_use": False,
                    "net_loss": "invalid amount",
                }
            },
            {
                "rental_property": {
                    "records": "agent statement held",
                    "private_use": False,
                    "items": [
                        {
                            "address": "Unit 1",
                            "ownership": "individual",
                            "income": 10000,
                            "records": "agent statement held",
                            "private_use": False,
                            "net_loss": "unknown",
                        }
                    ],
                }
            },
            {
                "rental_property": {
                    "records": "agent statement held",
                    "private_use": False,
                    "items": [
                        {
                            "address": "Unit 1",
                            "ownership": "individual",
                            "income": 10000,
                            "records": "agent statement held",
                            "private_use": False,
                            "net_loss": "invalid amount",
                        }
                    ],
                }
            },
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual("Evidence", row["status"])
                self.assertIn("numeric rental amount evidence", row["tab_text"])
                self.assertIn("worksheet net unknown", row["answer"])
                self.assertNotIn("worksheet net 10000.00", row["answer"])

    def test_rental_property_net_loss_flag_overrides_positive_worksheet_net(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 10000,
                    "records": "agent statement held",
                    "private_use": False,
                    "net_loss": True,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("worksheet net 10000.00", row["answer"])
        self.assertIn("net rental loss review", row["tab_text"])

    def test_rental_property_private_days_override_false_private_use(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property": {
                    "address": "Example rental",
                    "ownership": "individual",
                    "income": 12000,
                    "records": "agent statement held",
                    "private_use": False,
                    "private_use_days": 7,
                    "available_days": 358,
                }
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("private use false", row["answer"])
        self.assertIn("private days 7", row["answer"])
        self.assertIn("private-use apportionment evidence", row["tab_text"])
        self.assertIn("private-use review", row["tab_text"])

    def test_rental_property_items_require_income_per_property(self) -> None:
        itemized = [
            {
                "address": "Unit 1",
                "ownership": "individual",
                "income": 10000,
                "records": "agent statement held",
                "private_use": False,
            },
            {
                "address": "Unit 2",
                "ownership": "individual",
                "interest": 12000,
                "records": "loan statement held",
                "private_use": False,
            },
        ]
        cases = [
            ({"rental_property_items": itemized}, "Accountant review"),
            ({"rental_property_income": 22000, "rental_property_items": itemized}, "Evidence"),
        ]
        for answers, expected_status in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

                self.assertEqual(expected_status, row["status"])
                self.assertIn("rental income evidence", row["tab_text"])

    def test_rental_property_net_uses_displayed_item_expenses(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_income": 10000,
                "rental_property_ownership": "individual",
                "rental_property_records": "agent statement held",
                "rental_property_private_use": False,
                "rental_property_items": [
                    {"address": "Unit 1", "interest": 7000, "records": "loan statement held", "private_use": False},
                    {"address": "Unit 2", "interest": 6000, "records": "loan statement held", "private_use": False},
                ],
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertIn("interest 13000.00", row["answer"])
        self.assertIn("worksheet net -3000.00", row["answer"])
        self.assertIn("net rental loss review", row["tab_text"])

    def test_rental_property_item_net_loss_amounts_render_as_losses(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_records": "agent statement held",
                "rental_property_private_use": False,
                "rental_property_items": [
                    {"address": "Unit 1", "ownership": "individual", "income": 10000, "net_loss": 1500},
                    {"address": "Unit 2", "ownership": "individual", "income": 8000, "net_loss": 500},
                ],
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertIn("worksheet net -2000.00", row["answer"])
        self.assertIn("Unit 1: owner individual, income 10000.00", row["answer"])
        self.assertIn("net loss -1500.00", row["answer"])
        self.assertIn("Unit 2: owner individual, income 8000.00", row["answer"])
        self.assertIn("net loss -500.00", row["answer"])
        self.assertIn("net rental loss review", row["tab_text"])

    def test_rental_property_mixed_item_net_loss_uses_all_item_nets(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_records": "agent statement held",
                "rental_property_private_use": False,
                "rental_property_items": [
                    {"address": "Unit 1", "ownership": "individual", "income": 10000, "net_loss": 1500},
                    {"address": "Unit 2", "ownership": "individual", "income": 10000, "interest": 2000},
                ],
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertIn("income 20000.00", row["answer"])
        self.assertIn("interest 2000.00", row["answer"])
        self.assertIn("worksheet net 6500.00", row["answer"])
        self.assertIn("Unit 1: owner individual, income 10000.00", row["answer"])
        self.assertIn("net loss -1500.00", row["answer"])
        self.assertIn("net rental loss review", row["tab_text"])

    def test_rental_property_item_detail_renders_all_item_amount_facts(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_records": "agent statement held",
                "rental_property_private_use": False,
                "rental_property_items": [
                    {
                        "address": "Unit 1",
                        "ownership": "individual",
                        "income": 10000,
                        "interest": 2000,
                        "repairs": 300,
                        "capital_works": 400,
                        "depreciation": 500,
                        "other_expenses": 600,
                        "private_use_days": 7,
                        "available_days": 365,
                        "net_loss": "no",
                    }
                ],
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertIn("income 10000.00", row["answer"])
        self.assertIn("interest 2000.00", row["answer"])
        self.assertIn("repairs 300.00", row["answer"])
        self.assertIn("capital works 400.00", row["answer"])
        self.assertIn("depreciation 500.00", row["answer"])
        self.assertIn("other expenses 600.00", row["answer"])
        self.assertIn("private days 7", row["answer"])
        self.assertIn("available days 365", row["answer"])
        self.assertIn("net loss none", row["answer"])
        self.assertIn("private use false", row["answer"])
        self.assertIn("records agent statement held", row["answer"])

    def test_rental_property_item_loss_overrides_positive_aggregate_net(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_records": "agent statement held",
                "rental_property_private_use": False,
                "rental_property_items": [
                    {"address": "Unit 1", "ownership": "individual", "income": 1000, "interest": 1500},
                    {"address": "Unit 2", "ownership": "individual", "income": 10000, "interest": 1000},
                ],
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertIn("worksheet net 8500.00", row["answer"])
        self.assertIn("net rental loss review", row["tab_text"])

    def test_rental_property_items_render_and_review_queue(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "rental_property_items": [
                    {
                        "address": "Unit 1",
                        "ownership": "individual",
                        "income": 10000,
                        "interest": 7000,
                        "repairs": 500,
                        "capital_works": 1000,
                        "records": "agent statement held",
                        "private_use": False,
                    },
                    {
                        "address": "Holiday unit",
                        "ownership": "individual",
                        "income": 4000,
                        "interest": 5000,
                        "records": "agent statement held",
                        "private_use": True,
                    },
                ]
            }
        )
        row = next(item for item in payload["items"] if item["number"] == "RENTAL-PROPERTY")

        self.assertEqual("Accountant review", row["status"])
        self.assertIn("properties Unit 1", row["answer"])
        self.assertIn("Holiday unit", row["answer"])
        self.assertIn("per-property rental evidence", row["tab_text"])
        self.assertIn("private-use apportionment evidence", row["tab_text"])
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))
        self.assertIn("<b>Accountant review queue:</b>", body)
        self.assertIn("Rental property worksheet needs", body)
        self.assertIn("stays accountant review", body)

    def test_rental_property_review_row_appears_in_html_pack(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Rental property worksheet", body)
        self.assertIn("Rental property worksheet stays accountant review", body)
        self.assertIn("net rental loss review", body)
        self.assertNotIn("lodgment-ready", body)

    def test_rental_property_sources_are_registered_and_covered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "data" / "ato_knowledge_base" / "source_registry.json").read_text())
        coverage = json.loads((root / "data" / "ato_knowledge_base" / "source_coverage.json").read_text())
        registry_urls = {item["url"] for item in registry["records"]}
        covered = {item["canonical_url"]: item for item in coverage["sources"]}

        for url in taxmate_intake.ATO_RENTAL_PROPERTY_SOURCES:
            with self.subTest(url=url):
                self.assertIn(url, registry_urls)
                self.assertEqual("verified", covered[url]["status"])
                self.assertIn("property-rental-cgt", covered[url]["skills"])

    def test_individual_return_portable_skill_covers_rental_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "skills" / "individual-return" / "SKILL.md").read_text()
        root_skill = (root / "skills" / "taxmate-australia" / "SKILL.md").read_text()
        prep_doc = (root / "docs" / "INDIVIDUAL_RETURN_PREP.md").read_text()
        rules = (root / "skills" / "individual-return" / "references" / "rules.md").read_text()
        out_of_scope = skill.split("## Out Of Scope", 1)[1].split("## Method", 1)[0]

        self.assertIn("rental property worksheet", skill)
        self.assertIn("repairs versus capital", skill)
        self.assertIn("net rental loss", skill)
        self.assertIn("`property-rental-cgt`", skill)
        self.assertIn("rental property worksheet", prep_doc)
        self.assertIn("rental property", root_skill)
        self.assertIn(taxmate_intake.ATO_RENTAL_RECORDS_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_RENTAL_HOME_USE_SOURCE, rules)
        self.assertNotIn("rental property", out_of_scope)

    def test_no_answer_signals_survive_flat_nested_merges(self) -> None:
        cases = [
            (
                "ESS",
                "no-ESS answer with ESS facts",
                "statement no employee share scheme",
                {
                    "ess_statement": "no employee share scheme",
                    "ess": {
                        "statement": "ESS statement held",
                        "employer": "Employer",
                        "taxed_upfront_discount": 100,
                    },
                },
            ),
            (
                "ESS",
                "no-ESS answer with ESS facts",
                "taxed_upfront_discount no ess",
                {
                    "ess_taxed_upfront_discount": "no ess",
                    "ess": {
                        "statement": "ESS statement held",
                        "employer": "Employer",
                        "taxed_upfront_discount": 100,
                    },
                },
            ),
            (
                "PSI",
                "no-PSI answer with PSI facts",
                "income no psi",
                {
                    "psi_income": "no psi",
                    "psi": {
                        "income": 1000,
                        "income_type": "consulting",
                        "contract_evidence": "contract held",
                        "results_test": True,
                        "eighty_percent_test": False,
                        "unrelated_clients_test": True,
                        "employment_test": False,
                        "business_premises_test": False,
                        "psb_determination": False,
                        "attribution_entity": "self",
                        "deductions": "none",
                        "business_structure": "sole trader",
                    },
                },
            ),
            (
                "PSI",
                "no-PSI answer with PSI facts",
                "client no psi",
                {
                    "psi_client": "no psi",
                    "psi": {
                        "income": 1000,
                        "income_type": "consulting",
                        "contract_evidence": "contract held",
                        "results_test": True,
                        "eighty_percent_test": False,
                        "unrelated_clients_test": True,
                        "employment_test": False,
                        "business_premises_test": False,
                        "psb_determination": False,
                        "attribution_entity": "self",
                        "deductions": "none",
                        "business_structure": "sole trader",
                    },
                },
            ),
            (
                "FOREIGN-INCOME",
                "no-foreign-income answer with foreign income facts",
                "statement no foreign income",
                {
                    "foreign_income_statement": "no foreign income",
                    "foreign_income": {
                        "statement": "statement held",
                        "country": "NZ",
                        "income_type": "employment",
                        "amount": 100,
                        "foreign_tax_paid": 10,
                        "exchange_rate": 1.1,
                        "residency_status": "resident",
                    },
                },
            ),
            (
                "FOREIGN-INCOME",
                "no-foreign-income answer with foreign income facts",
                "statement no foreign income",
                {
                    "foreign_income_statement": "no foreign income",
                    "foreign_income": {"statement": "statement held"},
                },
            ),
            (
                "FOREIGN-INCOME",
                "no-foreign-income answer with foreign income facts",
                "country no foreign income",
                {
                    "foreign_income_country": "no foreign income",
                    "foreign_income": {
                        "statement": "statement held",
                        "country": "NZ",
                        "amount": 100,
                        "exchange_rate": 1.1,
                        "residency_status": "resident",
                    },
                },
            ),
            (
                "ETP",
                "no-payment answer with payment facts",
                "statement no ETP",
                {
                    "etp_statement": "no ETP",
                    "etp": {
                        "statement": "statement held",
                        "payer": "Employer",
                        "payment_type": "ETP",
                        "taxable_component": 100,
                        "tax_withheld": 20,
                    },
                },
            ),
            (
                "ETP",
                "no-payment answer with payment facts",
                "taxable_component no ETP",
                {
                    "etp_taxable_component": "no ETP",
                    "etp": {
                        "statement": "statement held",
                        "payer": "Employer",
                        "payment_type": "ETP",
                        "taxable_component": 100,
                        "tax_withheld": 20,
                    },
                },
            ),
            (
                "ETP",
                "no-payment answer with payment facts",
                "statement no ETP",
                {
                    "etp_statement": "no ETP",
                    "etp": {"statement": "statement held"},
                },
            ),
            (
                "LUMP-ARREARS",
                "no-payment answer with payment facts",
                "statement no lump sum in arrears",
                {
                    "lump_sum_arrears_statement": "no lump sum in arrears",
                    "lump_sum_arrears": {
                        "statement": "statement held",
                        "payer": "Employer",
                        "amount": 100,
                        "payment_years": "2024-25",
                        "tax_withheld": 20,
                    },
                },
            ),
            (
                "SUPER-INCOME",
                "no-payment answer with payment facts",
                "statement no super income stream",
                {
                    "super_income_statement": "no super income stream",
                    "super_income": {
                        "statement": "statement held",
                        "fund": "Fund",
                        "payment_kind": "income stream",
                        "taxable_amount": 100,
                        "tax_withheld": 20,
                    },
                },
            ),
        ]
        for number, tab_text, signal, answers in cases:
            with self.subTest(number=number):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == number)

                self.assertEqual("Evidence", row["status"])
                self.assertIn(tab_text, row["tab_text"])
                self.assertIn(signal, row["answer"])

    def test_field_absence_values_do_not_become_workflow_declines(self) -> None:
        complete_psi = {
            "income": 100,
            "income_type": "consulting",
            "contract_evidence": "contract held",
            "results_test": True,
            "eighty_percent_test": False,
            "unrelated_clients_test": True,
            "employment_test": False,
            "business_premises_test": False,
            "psb_determination": False,
            "attribution_entity": "self",
            "deductions": "none",
            "business_structure": "sole trader",
        }
        complete_crypto = {
            "event_type": "sale",
            "asset": "BTC",
            "exchange_or_wallet": "Coinbase",
            "quantity": 1,
            "acquired_date": "2025-07-01",
            "disposed_date": "2026-01-01",
            "cost_base": 100,
            "capital_proceeds": 200,
            "wallet_records": "records held",
            "ownership_entity": "self",
            "business_use": False,
            "private_use": True,
        }
        cases = [
            (
                "PSI",
                {"psi": {**complete_psi, "deductions": "not applicable"}},
                "deduction evidence",
                "not applicable",
            ),
            (
                "ETP",
                {
                    "etp": {
                        "statement": "statement held",
                        "payer": "n/a",
                        "payment_type": "ETP",
                        "taxable_component": 100,
                        "tax_free_component": 0,
                        "tax_withheld": "n/a",
                    }
                },
                "numeric amount evidence",
                "Payer n/a",
            ),
            (
                "FOREIGN-INCOME",
                {
                    "foreign_income": {
                        "statement": "statement held",
                        "country": "n/a",
                        "income_type": "employment",
                        "payer": "not applicable",
                        "amount": 100,
                        "foreign_tax_paid": 10,
                        "exchange_rate": 1.1,
                        "residency_status": "resident",
                    }
                },
                "source-backed accountant review",
                "not applicable",
            ),
            (
                "ESS",
                {
                    "ess": {
                        "statement": "ESS statement held",
                        "employer": "n/a",
                        "scheme": "not applicable",
                        "provider": "ESS provider",
                        "taxed_upfront_discount": "n/a",
                        "deferred_discount": 0,
                        "foreign_source_discount": 0,
                        "tfn_amount_withheld": 0,
                    }
                },
                "statement-backed accountant review",
                "Employer n/a",
            ),
            (
                "CRYPTO-CGT",
                {"crypto": {**complete_crypto, "rewards_income": "no staking rewards"}},
                "accountant review before manual copy",
                "no staking rewards",
            ),
            (
                "CRYPTO-CGT",
                {"crypto": {**complete_crypto, "wallet_records": "not applicable"}},
                "wallet or exchange records",
                "records not applicable",
            ),
            (
                "CRYPTO-CGT",
                {"crypto": {**complete_crypto, "exchange_or_wallet": "no exchange"}},
                "asset and exchange/wallet identity evidence",
                "exchange/wallet no exchange",
            ),
        ]
        for number, answers, expected_tab, absent_answer in cases:
            with self.subTest(number=number):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                row = next(item for item in payload["items"] if item["number"] == number)

                self.assertIn(expected_tab, row["tab_text"])
                self.assertNotIn("decline signals", row["answer"])
                self.assertNotIn("no-", row["tab_text"].lower())
                self.assertNotIn(absent_answer, row["answer"])

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

    def test_ess_workflow_renders_statement_backed_review(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Accountant review", ess["status"])
        self.assertIn("taxed-upfront discount 1500.00", ess["answer"])
        self.assertIn("deferred discount 2400.00", ess["answer"])
        self.assertIn("foreign-source discount 300.00", ess["answer"])
        self.assertIn("TFN amount withheld 0.00", ess["answer"])
        self.assertIn(taxmate_intake.ATO_ESS_SOURCE, ess["source_urls"])
        self.assertIn(taxmate_intake.ATO_ESS_STATEMENT_SOURCE, ess["source_urls"])

    def test_ess_missing_statement_stays_evidence(self) -> None:
        rows = taxmate_intake.ess_rows(
            {
                "taxed_upfront_discount": 500,
                "deferred_discount": 0,
                "foreign_source_discount": "unknown",
                "tfn_amount_withheld": 0,
            }
        )

        self.assertEqual("Evidence", rows[0]["status"])
        self.assertIn("deferred discount 0.00", rows[0]["answer"])
        self.assertIn("foreign-source discount unknown", rows[0]["answer"])

    def test_ess_flat_answers_get_typed_review_row(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers.pop("ess")
        answers["ess_employer"] = "Acme Pty Ltd"
        answers["ess_statement"] = "ESS statement held"
        answers["ess_taxed_upfront_discount"] = 100
        answers["ess_deferred_discount"] = 0
        answers["ess_foreign_source_discount"] = 25
        answers["ess_tfn_amount_withheld"] = 12

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Accountant review", ess["status"])
        self.assertIn("Employer Acme Pty Ltd", ess["answer"])
        self.assertIn("taxed-upfront discount 100.00", ess["answer"])
        self.assertIn("deferred discount 0.00", ess["answer"])
        self.assertIn("TFN amount withheld 12.00", ess["answer"])

    def test_ess_natural_language_missing_statement_stays_evidence(self) -> None:
        cases = [
            {"ess_statement": "no ESS statement", "ess_taxed_upfront_discount": 100},
            {"ess": {"statement": "statement not held", "taxed_upfront_discount": 100}},
            {"ess_items": [{"statement": "statement not available", "taxed_upfront_discount": 100}]},
            {"ess_statement": "statement not received", "ess_taxed_upfront_discount": 100},
            {"ess": {"statement": "statement not provided", "taxed_upfront_discount": 100}},
            {"ess_items": [{"statement": "not supplied", "taxed_upfront_discount": 100}]},
            {"ess_statement": "I do not have the ESS statement", "ess_taxed_upfront_discount": 100},
            {"ess": {"statement": "I don't have the ESS statement", "taxed_upfront_discount": 100}},
            {"ess": {"statement": "I dont have the ESS statement", "taxed_upfront_discount": 100}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Evidence", ess["status"])
                self.assertEqual("ESS discounts need ESS statement evidence before accountant review.", ess["tab_text"])

    def test_ess_supported_labels_remain_visible(self) -> None:
        cases = [
            ("Acme Pty Ltd", {"ess_employer": "Acme Pty Ltd", "ess_taxed_upfront_discount": 100}),
            ("Acme scheme", {"ess_scheme": "Acme scheme", "ess_taxed_upfront_discount": 100}),
            ("Acme provider", {"ess_provider": "Acme provider", "ess_taxed_upfront_discount": 100}),
            ("Nested scheme", {"ess": {"scheme": "Nested scheme", "taxed_upfront_discount": 100}}),
            ("Nested provider", {"ess": {"provider": "Nested provider", "taxed_upfront_discount": 100}}),
            ("Item provider", {"ess_items": [{"provider": "Item provider", "taxed_upfront_discount": 100}]}),
        ]
        for expected_label, answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertIn(f"Employer {expected_label}", ess["answer"])
                self.assertNotIn("Employer unknown", ess["answer"])
                self.assertNotIn("items item 1", ess["answer"])

    def test_empty_ess_items_do_not_render_workflow_row(self) -> None:
        for ess_value in [{"items": []}, {"items": [{}]}, {}, []]:
            with self.subTest(ess_value=ess_value):
                answers = taxmate_intake.sample_answers()
                answers.pop("ess")
                answers["ess"] = ess_value

                payload = taxmate_intake.answers_to_pack_payload(answers)

                self.assertFalse(any(row["number"] == "ESS" for row in payload["items"]))

    def test_no_ess_answers_do_not_render_workflow_row(self) -> None:
        cases = [
            {"ess_statement": "no employee share scheme"},
            {"ess_statement": "no employee share schemes"},
            {"ess_statement": "not applicable"},
            {"ess_statement": "n/a"},
            {"ess": {"statement": "no employee share scheme"}},
            {"ess": {"statement": "not applicable"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)

                self.assertFalse(any(row["number"] == "ESS" for row in payload["items"]))

    def test_no_ess_statement_with_amount_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {"ess_statement": "no employee share scheme", "ess_taxed_upfront_discount": 100}
        )
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Evidence", ess["status"])
        self.assertIn("no-ESS answer with ESS facts", ess["tab_text"])
        self.assertIn("taxed-upfront discount 100.00", ess["answer"])
        self.assertIn("decline signals statement no employee share scheme", ess["answer"])

    def test_no_ess_declines_survive_flat_nested_and_item_paths(self) -> None:
        cases = [
            (
                {"ess_statement": "no employee share scheme", "ess_taxed_upfront_discount": 100},
                "statement no employee share scheme",
            ),
            (
                {"ess_statement": "no employee share scheme", "ess": {"taxed_upfront_discount": 100}},
                "statement no employee share scheme",
            ),
            (
                {"ess": {"statement": "no employee share scheme", "taxed_upfront_discount": 100}},
                "statement no employee share scheme",
            ),
            (
                {"ess_items": [{"statement": "no employee share scheme", "taxed_upfront_discount": 100}]},
                "item 1 statement no employee share scheme",
            ),
            (
                {"ess_taxed_upfront_discount": "no ess", "ess": {"statement": "ESS statement held", "taxed_upfront_discount": 100}},
                "taxed_upfront_discount no ess",
            ),
        ]
        for answers, signal in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Evidence", ess["status"])
                self.assertIn("no-ESS answer with ESS facts", ess["tab_text"])
                self.assertIn(signal, ess["answer"])

    def test_no_ess_declines_in_any_prompt_skip_when_factless(self) -> None:
        cases = [
            {"ess_statement": "no ess"},
            {"ess_taxed_upfront_discount": "no ess"},
            {"ess": {"statement": "no ess"}},
            {"ess": {"taxed_upfront_discount": "no ess"}},
            {"ess_items": [{"statement": "no ess"}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)

                self.assertFalse(any(row["number"] == "ESS" for row in payload["items"]))

    def test_zero_ess_amount_is_meaningful_input(self) -> None:
        rows = taxmate_intake.ess_rows({"statement": "ESS statement held", "taxed_upfront_discount": 0})

        self.assertEqual("Accountant review", rows[0]["status"])
        self.assertIn("taxed-upfront discount 0.00", rows[0]["answer"])

    def test_ess_items_render_item_values(self) -> None:
        item = {
            "statement": "ESS statement held",
            "employer": "Acme Pty Ltd",
            "taxed_upfront_discount": 123,
            "deferred_discount": 0,
            "foreign_source_discount": 25,
            "tfn_amount_withheld": 0,
        }
        for answers in [{"ess_items": [item]}, {"ess": {"items": [item]}}]:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Accountant review", ess["status"])
                self.assertIn("Employer Acme Pty Ltd", ess["answer"])
                self.assertIn("taxed-upfront discount 123.00", ess["answer"])
                self.assertIn("deferred discount 0.00", ess["answer"])
                self.assertIn("foreign-source discount 25.00", ess["answer"])
                self.assertIn("TFN amount withheld 0.00", ess["answer"])
                self.assertIn("items Acme Pty Ltd: taxed-upfront 123.00", ess["answer"])

    def test_nested_ess_statement_only_renders_review_row(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload({"ess": {"statement": "ESS statement held"}})
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Accountant review", ess["status"])
        self.assertIn("taxed-upfront discount unknown", ess["answer"])
        self.assertIn(taxmate_intake.ATO_ESS_SOURCE, ess["source_urls"])

    def test_nested_ess_items_keep_amounts_with_unknown_statement(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["ess"] = {
            "items": [
                {
                    "statement": "unknown",
                    "employer": "Acme Pty Ltd",
                    "taxed_upfront_discount": 120,
                }
            ]
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Evidence", ess["status"])
        self.assertIn("taxed-upfront discount 120.00", ess["answer"])
        self.assertIn("items Acme Pty Ltd: taxed-upfront 120.00", ess["answer"])
        self.assertEqual("ESS discounts need ESS statement evidence before accountant review.", ess["tab_text"])

    def test_ess_requires_statement_evidence_for_each_rendered_item(self) -> None:
        answers = {
            "ess_items": [
                {"statement": "ESS statement held", "employer": "Acme Pty Ltd", "taxed_upfront_discount": 100},
                {"statement": "unknown", "employer": "Beta Pty Ltd", "deferred_discount": 50},
            ]
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Evidence", ess["status"])
        self.assertIn("taxed-upfront discount 100.00", ess["answer"])
        self.assertIn("deferred discount 50.00", ess["answer"])
        self.assertEqual("ESS discounts need ESS statement evidence before accountant review.", ess["tab_text"])

    def test_top_level_ess_statement_does_not_cover_itemized_amounts(self) -> None:
        answers = {
            "ess": {
                "statement": "ESS statement held",
                "items": [{"employer": "Acme Pty Ltd", "taxed_upfront_discount": 100}],
            }
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Evidence", ess["status"])
        self.assertIn("items Acme Pty Ltd: taxed-upfront 100.00", ess["answer"])

    def test_ess_item_totals_override_conflicting_top_level_amounts(self) -> None:
        answers = {
            "ess": {
                "statement": "ESS statement held",
                "taxed_upfront_discount": 999,
                "items": [{"statement": "ESS statement held", "employer": "Acme Pty Ltd", "taxed_upfront_discount": 100}],
            }
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Evidence", ess["status"])
        self.assertIn("taxed-upfront discount 100.00", ess["answer"])
        self.assertNotIn("taxed-upfront discount 999.00", ess["answer"])
        self.assertEqual(
            "ESS top-level and item amounts conflict; correct ESS amount totals before accountant review.",
            ess["tab_text"],
        )

    def test_malformed_ess_amounts_stay_reviewable(self) -> None:
        cases = [
            {"ess_statement": "ESS statement held", "ess_taxed_upfront_discount": "about $100"},
            {"ess": {"statement": "ESS statement held", "taxed_upfront_discount": "100 AUD"}},
            {"ess_items": [{"statement": "ESS statement held", "employer": "Acme Pty Ltd", "taxed_upfront_discount": "about $100"}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Evidence", ess["status"])
                self.assertIn("taxed-upfront discount unknown", ess["answer"])
                self.assertEqual("ESS amount fields need numeric evidence before accountant review.", ess["tab_text"])

    def test_unknown_ess_amounts_stay_evidence(self) -> None:
        cases = [
            {"ess_statement": "ESS statement held", "ess_taxed_upfront_discount": "unknown"},
            {"ess": {"statement": "ESS statement held", "taxed_upfront_discount": "unknown"}},
            {"ess_items": [{"statement": "ESS statement held", "employer": "Acme Pty Ltd", "taxed_upfront_discount": "unknown"}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Evidence", ess["status"])
                self.assertIn("taxed-upfront discount unknown", ess["answer"])
                self.assertEqual("ESS amount fields need numeric evidence before accountant review.", ess["tab_text"])

    def test_unknown_ess_amount_item_without_label_stays_evidence(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {"ess_items": [{"statement": "ESS statement held", "taxed_upfront_discount": "unknown"}]}
        )
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Evidence", ess["status"])
        self.assertIn("items item 1: taxed-upfront unknown", ess["answer"])
        self.assertEqual("ESS amount fields need numeric evidence before accountant review.", ess["tab_text"])

    def test_item_statement_only_does_not_render_placeholder_detail(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload({"ess": {"items": [{"statement": "ESS statement held"}]}})

        self.assertFalse(any(row["number"] == "ESS" for row in payload["items"]))

    def test_ess_placeholder_item_labels_do_not_create_rows(self) -> None:
        cases = [
            {"ess": {"items": [{"employer": "unknown"}]}},
            {"ess": {"items": [{"scheme": "missing"}]}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)

                self.assertFalse(any(row["number"] == "ESS" for row in payload["items"]))

    def test_ess_items_keep_amounts_with_unknown_labels(self) -> None:
        cases = [
            ("taxed-upfront discount 120.00", {"employer": "unknown", "taxed_upfront_discount": 120}),
            ("deferred discount 50.00", {"scheme": "missing", "deferred_discount": 50}),
            ("taxed-upfront discount 120.00", {"employer": "Acme no receipt", "taxed_upfront_discount": 120}),
        ]
        for expected, item in cases:
            with self.subTest(item=item):
                payload = taxmate_intake.answers_to_pack_payload({"ess": {"items": [item]}})
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Evidence", ess["status"])
                self.assertIn(expected, ess["answer"])

    def test_nested_unknown_ess_values_do_not_override_flat_values(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["ess_statement"] = "ESS statement held"
        answers["ess_taxed_upfront_discount"] = 100
        answers["ess_deferred_discount"] = 0
        answers["ess_foreign_source_discount"] = 25
        answers["ess"] = {
            "statement": "unknown",
            "taxed_upfront_discount": "unknown",
            "deferred_discount": False,
            "foreign_source_discount": "unknown",
        }

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Accountant review", ess["status"])
        self.assertIn("taxed-upfront discount 100.00", ess["answer"])
        self.assertIn("deferred discount 0.00", ess["answer"])
        self.assertIn("foreign-source discount 25.00", ess["answer"])

    def test_nested_unknown_ess_statement_stays_visible(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload({"ess": {"statement": "unknown"}})
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Evidence", ess["status"])
        self.assertEqual(
            "ESS discounts need ESS statement evidence before accountant review.",
            ess["tab_text"],
        )
        self.assertIn("taxed-upfront discount unknown", ess["answer"])

    def test_nested_unknown_ess_amount_inputs_stay_visible(self) -> None:
        cases = [
            {"ess": {"taxed_upfront_discount": "unknown"}},
            {"ess": {"statement": "unknown", "deferred_discount": "unknown"}},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Evidence", ess["status"])
                self.assertEqual(
                    "ESS discounts need ESS statement evidence and numeric amount evidence before accountant review.",
                    ess["tab_text"],
                )
                self.assertIn("taxed-upfront discount unknown", ess["answer"])

    def test_false_ess_statement_stays_evidence_with_amounts(self) -> None:
        cases = [
            {"ess_statement": False, "ess_taxed_upfront_discount": 0},
            {"ess": {"statement": False, "taxed_upfront_discount": 100}},
            {"ess_items": [{"statement": False, "employer": "Acme Pty Ltd", "taxed_upfront_discount": 100}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)
                ess = next(row for row in payload["items"] if row["number"] == "ESS")

                self.assertEqual("Evidence", ess["status"])
                self.assertIn("taxed-upfront discount", ess["answer"])
                self.assertEqual("ESS discounts need ESS statement evidence before accountant review.", ess["tab_text"])

    def test_false_ess_amount_only_does_not_render_row(self) -> None:
        cases = [
            {"ess_taxed_upfront_discount": False},
            {"ess": {"taxed_upfront_discount": False}},
            {"ess_items": [{"taxed_upfront_discount": False}]},
        ]
        for answers in cases:
            with self.subTest(answers=answers):
                payload = taxmate_intake.answers_to_pack_payload(answers)

                self.assertFalse(any(row["number"] == "ESS" for row in payload["items"]))

    def test_empty_optional_containers_do_not_render_base_rows(self) -> None:
        answers = taxmate_intake.sample_answers()
        for key in ["employee_deductions", "wfh_work_pattern", "asset_items", "ess_items", "foreign_income_items"]:
            answers[key] = [] if key.endswith("items") or key == "employee_deductions" else {}

        rows = taxmate_intake.base_items(answers)
        rendered_numbers = {row["number"] for row in rows}

        self.assertNotIn("employee_deductions", rendered_numbers)
        self.assertNotIn("wfh_work_pattern", rendered_numbers)
        self.assertNotIn("asset_items", rendered_numbers)
        self.assertNotIn("ess_items", rendered_numbers)

    def test_explicit_false_optional_answers_still_render_base_rows(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["gst_registered"] = False
        answers["private_health_cover"] = False
        answers["spouse_had"] = False

        rows = taxmate_intake.base_items(answers)
        rendered = {row["number"]: row for row in rows}

        self.assertEqual("Accountant review", rendered["gst_registered"]["status"])
        self.assertEqual("Used", rendered["private_health_cover"]["status"])
        self.assertEqual("Used", rendered["spouse_had"]["status"])
        self.assertEqual("false", rendered["gst_registered"]["answer"])

    def test_empty_nested_ess_falls_back_to_flat_answers(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["ess"] = {"items": []}
        answers["ess_statement"] = "ESS statement held"
        answers["ess_taxed_upfront_discount"] = 100
        answers["ess_deferred_discount"] = 0
        answers["ess_foreign_source_discount"] = 25

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertEqual("Accountant review", ess["status"])
        self.assertIn("taxed-upfront discount 100.00", ess["answer"])
        self.assertIn("deferred discount 0.00", ess["answer"])

    def test_nested_ess_meaningful_values_override_flat_answers(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["ess"] = {"statement": "Nested ESS statement", "taxed_upfront_discount": 200}
        answers["ess_taxed_upfront_discount"] = 100

        payload = taxmate_intake.answers_to_pack_payload(answers)
        ess = next(row for row in payload["items"] if row["number"] == "ESS")

        self.assertIn("taxed-upfront discount 200.00", ess["answer"])

    def test_empty_workflow_containers_do_not_render_rows(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["wfh"] = {}
        answers["wfh_work_pattern"] = {}
        answers["assets"] = [{}]
        answers["uncommon_income"] = [{}]
        answers["extracted_values"] = [{}]
        answers["ess"] = {"items": [{}]}
        answers["foreign_income"] = {"items": [{}]}

        payload = taxmate_intake.answers_to_pack_payload(answers)
        rendered_numbers = {row["number"] for row in payload["items"]}

        self.assertNotIn("WFH", rendered_numbers)
        self.assertNotIn("ASSET-1", rendered_numbers)
        self.assertNotIn("UNC-1", rendered_numbers)
        self.assertNotIn("ESS", rendered_numbers)
        self.assertNotIn("FOREIGN-INCOME", rendered_numbers)
        self.assertEqual([], payload["extracted_values"])

    def test_wfh_placeholder_fields_fall_back_to_flat_answers(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["state"] = "VIC"
        answers["wfh"] = {
            "state": {},
            "records": [],
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

    def test_empty_assets_fall_back_to_asset_items(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers["assets"] = [{}]
        answers["asset_items"] = [{"description": "Monitor", "cost": 280, "work_use_percent": 100}]

        payload = taxmate_intake.answers_to_pack_payload(answers)
        asset = next(row for row in payload["items"] if row["number"] == "ASSET-1")

        self.assertIn("Monitor", asset["question"])
        self.assertIn("immediate deduction candidate", asset["answer"])

    def test_ess_review_row_appears_in_html_pack(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("Employee share schemes", body)
        self.assertIn("ESS discounts need statement-backed accountant review.", body)
        self.assertIn("foreign-source discount 300.00", body)
        self.assertNotIn("lodgment-ready", body)

    def test_ess_sources_are_registered_and_covered(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "data" / "ato_knowledge_base" / "source_registry.json").read_text())
        coverage = json.loads((root / "data" / "ato_knowledge_base" / "source_coverage.json").read_text())
        registry_urls = {item["url"] for item in registry["records"]}
        covered = {item["canonical_url"]: item for item in coverage["sources"]}

        for url in [taxmate_intake.ATO_ESS_SOURCE, taxmate_intake.ATO_ESS_STATEMENT_SOURCE]:
            with self.subTest(url=url):
                self.assertIn(url, registry_urls)
                self.assertEqual("verified", covered[url]["status"])
                self.assertIn("employment-deductions", covered[url]["skills"])

    def test_individual_return_portable_skill_covers_ess_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "skills" / "individual-return" / "SKILL.md").read_text()
        rules = (root / "skills" / "individual-return" / "references" / "rules.md").read_text()
        out_of_scope = skill.split("## Out Of Scope", 1)[1].split("## Method", 1)[0]

        self.assertIn("including PAYG, ESS, ETP", skill)
        self.assertIn("employee share scheme", skill)
        self.assertIn("ESS statement", skill)
        self.assertIn("taxed-upfront discount", skill)
        self.assertIn("foreign-source discount", skill)
        self.assertIn(taxmate_intake.ATO_ESS_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_ESS_STATEMENT_SOURCE, rules)
        self.assertNotIn("ESS", out_of_scope)

    def test_individual_return_portable_skill_covers_complex_payment_scope(self) -> None:
        root = Path(__file__).resolve().parents[1]
        skill = (root / "skills" / "individual-return" / "SKILL.md").read_text()
        rules = (root / "skills" / "individual-return" / "references" / "rules.md").read_text()
        out_of_scope = skill.split("## Out Of Scope", 1)[1].split("## Method", 1)[0]

        self.assertIn("including PAYG, ESS, ETP", skill)
        self.assertIn("employment termination payment", skill)
        self.assertIn("ETP payment summary", skill)
        self.assertIn("lump sum in arrears", skill)
        self.assertIn("super income stream", skill)
        self.assertIn("contradictory no-payment plus amount facts", skill)
        self.assertIn(taxmate_intake.ATO_ETP_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_LUMP_SUM_ARREARS_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_SUPER_PENSIONS_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_SUPER_LUMP_SUM_SOURCE, rules)
        self.assertIn(taxmate_intake.ATO_SUPER_STREAM_SOURCE, rules)
        self.assertNotIn("ETP", out_of_scope)
        self.assertNotIn("lump sum", out_of_scope.lower())

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
            "ACT": 0,
            "NT": 0,
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

    def test_wfh_limited_public_holidays_remain_evidence(self) -> None:
        cases = [
            (state, day)
            for state, days in taxmate_intake.LIMITED_PUBLIC_HOLIDAYS_BY_STATE.items()
            for day in sorted(days)
        ]
        for state, day in cases:
            with self.subTest(state=state, day=day):
                rows = taxmate_intake.wfh_rows(
                    {
                        "state": state,
                        "start": day,
                        "end": day,
                        "weekdays": [date_weekday(day)],
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

    def test_tas_statewide_holidays_still_exclude_hours(self) -> None:
        raw = {
            "state": "TAS",
            "start": "2026-03-09",
            "end": "2026-03-09",
            "weekdays": [0],
            "hours_per_day": 8,
            "records": "timesheet",
            "actual_cost_records": "none",
            "leave_dates": [],
            "worked_public_holidays": [],
            "worked_weekends": [],
        }

        self.assertEqual(0, taxmate_intake.calculate_wfh_hours(raw))

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

    def test_individual_return_prep_docs_are_validated(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertTrue(taxmate_validate.individual_return_prep_docs_ready(str(ROOT), readme))

    def test_individual_return_prep_docs_require_no_answer_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            readme = "Individual Return Prep docs/INDIVIDUAL_RETURN_PREP.md prep-only boundaries"
            (docs / "INDIVIDUAL_RETURN_PREP.md").write_text(
                "TaxMate is prep-only\nindividual-return\n./scripts/taxmate intake individual --help\n"
                "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json\n"
                "./scripts/taxmate intake individual --answers /tmp/taxmate-answers.json\n"
                "`Accountant review`\n"
                "myTax, paper ATO form, or accountant handoff\n",
                encoding="utf-8",
            )

            self.assertFalse(taxmate_validate.individual_return_prep_docs_ready(tmp, readme))

    def test_individual_return_prep_docs_reject_renderer_only_sample_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            docs = root / "docs"
            docs.mkdir()
            readme = (
                "Individual Return Prep docs/INDIVIDUAL_RETURN_PREP.md prep-only boundaries "
                "./scripts/taxmate taxpack sample-json --output /tmp/taxmate-guide-input.json"
            )
            (docs / "INDIVIDUAL_RETURN_PREP.md").write_text(
                "TaxMate is prep-only\nindividual-return\n./scripts/taxmate intake individual --help\n"
                "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json\n"
                "./scripts/taxmate intake individual --answers /tmp/taxmate-answers.json\n"
                "--input /tmp/taxmate-guide-input.json\n"
                "No-answer plus facts stays Evidence\n`Accountant review`\n"
                "myTax, paper ATO form, or accountant handoff\n",
                encoding="utf-8",
            )

            self.assertFalse(taxmate_validate.individual_return_prep_docs_ready(tmp, readme))


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
