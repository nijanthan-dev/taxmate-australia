from __future__ import annotations

import argparse
import io
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import atodata  # noqa: E402
import skillgen  # noqa: E402
import taxmate  # noqa: E402
import taxmate_calc  # noqa: E402
import taxmate_finance  # noqa: E402
import taxmate_validate  # noqa: E402


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

    def test_release_config_tracks_manifest_versions(self) -> None:
        self.assertTrue(taxmate_validate.release_config_tracks_manifest_versions(str(ROOT)))

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

    def test_ato_endorsement_scan_allows_negated_disclaimer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            readme = Path(tmp) / "README.md"
            readme.write_text(
                "TaxMate is not affiliated with, sponsored by, endorsed by, or approved by the Australian Taxation Office.\n",
                encoding="utf-8",
            )

            hits = taxmate_validate.ato_endorsement_claim_hits(tmp)

        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
