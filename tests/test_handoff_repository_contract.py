from __future__ import annotations

import ast
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import taxmate_handoff  # noqa: E402
import taxmate_intake  # noqa: E402
import taxmate_review_guardrails  # noqa: E402
import taxmate_taxpack  # noqa: E402
import taxmate_validate  # noqa: E402


DESTINATION_IDS = {
    "phi-tax-claim-code",
    "phi-premiums-j",
    "phi-rebate-k",
    "phi-benefit-code-l",
    "m1-exemption-question",
    "m1-full-days-v",
    "m1-half-days-w",
    "m2-cover-question-e",
    "m2-days-not-liable-a",
    "spouse-had-question",
}

APPROVED_DESTINATION_PRODUCERS = {
    "phi-tax-claim-code": {"private_health_statement_rows"},
    "phi-premiums-j": {"private_health_statement_rows"},
    "phi-rebate-k": {"private_health_statement_rows"},
    "phi-benefit-code-l": {"private_health_statement_rows"},
    "m1-exemption-question": {"medicare_levy_row"},
    "m1-full-days-v": {"medicare_levy_row"},
    "m1-half-days-w": {"medicare_levy_row"},
    "m2-cover-question-e": {"mls_review_row"},
    "m2-days-not-liable-a": {"mls_review_row"},
    "spouse-had-question": {"spouse_review_row"},
}

EXPECTED_DESTINATIONS = {
    "phi-tax-claim-code": {
        "label": "Private health insurance statement line - Tax claim code",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance > Private health insurance > Statement line panel > Tax claim code",
            "source_id": "ato-f99c3a4ad079",
            "content_hash": "da3592fbaa5668af33905a526362d13a976695834084d0d0f8b7bbc405e4d1d1",
        },
        "paper": {
            "kind": "verified",
            "location": "Private health insurance policy details > Tax claim code box",
            "source_id": "ato-2a2cf8a8c462",
            "content_hash": "38a3018c329e8c1e168a6b169a35530c730f89f1a199bc834e81488003117cc6",
        },
    },
    "phi-premiums-j": {
        "label": "Private health insurance statement line - Premiums eligible for rebate",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance > Private health insurance > Your premiums eligible for Australian Government rebate",
            "source_id": "ato-f99c3a4ad079",
            "content_hash": "da3592fbaa5668af33905a526362d13a976695834084d0d0f8b7bbc405e4d1d1",
        },
        "paper": {
            "kind": "verified",
            "location": "Private health insurance policy details > label J",
            "source_id": "ato-2a2cf8a8c462",
            "content_hash": "38a3018c329e8c1e168a6b169a35530c730f89f1a199bc834e81488003117cc6",
        },
    },
    "phi-rebate-k": {
        "label": "Private health insurance statement line - Rebate received",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance > Private health insurance > Your Australian Government rebate received",
            "source_id": "ato-f99c3a4ad079",
            "content_hash": "da3592fbaa5668af33905a526362d13a976695834084d0d0f8b7bbc405e4d1d1",
        },
        "paper": {
            "kind": "verified",
            "location": "Private health insurance policy details > label K",
            "source_id": "ato-2a2cf8a8c462",
            "content_hash": "38a3018c329e8c1e168a6b169a35530c730f89f1a199bc834e81488003117cc6",
        },
    },
    "phi-benefit-code-l": {
        "label": "Private health insurance statement line - Benefit code",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance > Private health insurance > Benefit code",
            "source_id": "ato-f99c3a4ad079",
            "content_hash": "da3592fbaa5668af33905a526362d13a976695834084d0d0f8b7bbc405e4d1d1",
        },
        "paper": {
            "kind": "verified",
            "location": "Private health insurance policy details > label L",
            "source_id": "ato-2a2cf8a8c462",
            "content_hash": "38a3018c329e8c1e168a6b169a35530c730f89f1a199bc834e81488003117cc6",
        },
    },
    "m1-exemption-question": {
        "label": "Medicare levy exemption category question",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance details > Medicare levy exemption > Were you in an exemption category during 2025-26?",
            "source_id": "ato-4cedc9f93767",
            "content_hash": "2c7c4e2623459a338d146c41899f7a3b5ad5f2ea70c1b95640d950e9cad6d23c",
        },
        "paper": {
            "kind": "requires-review",
            "location": "Question M1 category instructions; no equivalent generic paper yes/no label is verified",
            "source_id": "ato-39155fe09d00",
            "content_hash": "272598694ee4ca50ee47cef9b8130dbd93a7c16dbcdb868aedeeaed5abc752b7",
        },
    },
    "m1-full-days-v": {
        "label": "Medicare levy full exemption days",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance details > Full 2% levy exemption - number of days",
            "source_id": "ato-4cedc9f93767",
            "content_hash": "2c7c4e2623459a338d146c41899f7a3b5ad5f2ea70c1b95640d950e9cad6d23c",
        },
        "paper": {
            "kind": "verified",
            "location": "Question M1 > label V",
            "source_id": "ato-39155fe09d00",
            "content_hash": "272598694ee4ca50ee47cef9b8130dbd93a7c16dbcdb868aedeeaed5abc752b7",
        },
    },
    "m1-half-days-w": {
        "label": "Medicare levy half exemption days",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance details > Half 2% levy exemption - number of days",
            "source_id": "ato-4cedc9f93767",
            "content_hash": "2c7c4e2623459a338d146c41899f7a3b5ad5f2ea70c1b95640d950e9cad6d23c",
        },
        "paper": {
            "kind": "verified",
            "location": "Question M1 > label W",
            "source_id": "ato-39155fe09d00",
            "content_hash": "272598694ee4ca50ee47cef9b8130dbd93a7c16dbcdb868aedeeaed5abc752b7",
        },
    },
    "m2-cover-question-e": {
        "label": "Medicare levy surcharge full-year appropriate family cover question",
        "mytax": {
            "kind": "verified",
            "location": "Prepare return > Medicare and private health insurance > Medicare levy surcharge > Were you and all your dependants covered by an appropriate level of private patient hospital cover from 1 July 2025 to 30 June 2026?",
            "source_id": "ato-836a84c52e60",
            "content_hash": "ef48900dec7c99657f728f1751f49f83fd3eea6ff5d9401476cffc5554874f24",
        },
        "paper": {
            "kind": "verified",
            "location": "Question M2 > label E Yes/No - full-year appropriate private patient hospital cover for you and all dependants",
            "source_id": "ato-b8cc03014dc1",
            "content_hash": "b604f09774f9a6ee18e63d98afa7fee9e678cb6f7429b1f71fba9a5a0797c163",
        },
    },
    "m2-days-not-liable-a": {
        "label": "Medicare levy surcharge days not liable",
        "mytax": {
            "kind": "requires-review",
            "location": "After an explicit No to full-year appropriate family cover, myTax may skip this field after its income check; if shown: Number of days you do not have to pay the surcharge",
            "source_id": "ato-836a84c52e60",
            "content_hash": "ef48900dec7c99657f728f1751f49f83fd3eea6ff5d9401476cffc5554874f24",
        },
        "paper": {
            "kind": "verified",
            "location": "Question M2 > label A",
            "source_id": "ato-b8cc03014dc1",
            "content_hash": "b604f09774f9a6ee18e63d98afa7fee9e678cb6f7429b1f71fba9a5a0797c163",
        },
    },
    "spouse-had-question": {
        "label": "Spouse details participation question",
        "mytax": {
            "kind": "verified",
            "location": "Personalise return > Did you have a spouse at any time between 1 July 2025 and 30 June 2026?",
            "source_id": "ato-815a889d0a59",
            "content_hash": "ea256593bfa3b5d30a4cc742970e6a88d02c9645ccb2db497ae4b1e35728d016",
        },
        "paper": {
            "kind": "requires-review",
            "location": "Spouse details - married or de facto section; no separate paper had-spouse label is verified",
            "source_id": "ato-29a73bbec8f5",
            "content_hash": "29f2101f9c146bcfd111bd457799c3eb049a6a725b4362175ea4abb4670c99fe",
        },
    },
}

EXPECTED_PHI_CONTEXTS = {
    "phi-tax-claim-code": {
        "key": "tax_claim_code",
        "channels": {
            "mytax": {
                "A": "verified",
                "B": "verified",
                "C": "verified",
                "D": "read-only",
                "E": "verified",
                "F": "verified",
                "default": "requires-review",
            },
            "paper": {
                "A": "verified",
                "B": "verified",
                "C": "verified",
                "D": "verified",
                "E": "verified",
                "F": "verified",
                "default": "requires-review",
            },
        },
    },
    **{
        mapping_id: {
            "key": "tax_claim_code",
            "channels": {
                "mytax": {
                    "A": "verified",
                    "B": "verified",
                    "C": "verified",
                    "D": "read-only",
                    "E": "not-entered",
                    "F": "not-entered",
                    "default": "requires-review",
                },
                "paper": {
                    "A": "verified",
                    "B": "verified",
                    "C": "verified",
                    "D": "verified",
                    "E": "verified",
                    "F": "not-entered",
                    "default": "requires-review",
                },
            },
        }
        for mapping_id in ("phi-premiums-j", "phi-rebate-k", "phi-benefit-code-l")
    },
}

EXPECTED_PHI_STATE_LOCATIONS = {
    "phi-tax-claim-code": {
        "mytax": {
            "read-only": "Read-only spouse-share statement line created by myTax with tax claim code D",
            "requires-review": "Tax claim code destination requires review",
        },
        "paper": {"requires-review": "Tax claim code destination requires review"},
    },
    "phi-premiums-j": {
        "mytax": {
            "read-only": "Read-only spouse-share statement line created by myTax",
            "not-entered": "Not entered in myTax for this tax claim code",
            "requires-review": "Premium destination requires review",
        },
        "paper": {
            "not-entered": "Not entered at label J for tax claim code F",
            "requires-review": "Label J destination requires review",
        },
    },
    "phi-rebate-k": {
        "mytax": {
            "read-only": "Read-only spouse-share statement line created by myTax",
            "not-entered": "Not entered in myTax for this tax claim code",
            "requires-review": "Rebate destination requires review",
        },
        "paper": {
            "not-entered": "Not entered at label K for tax claim code F",
            "requires-review": "Label K destination requires review",
        },
    },
    "phi-benefit-code-l": {
        "mytax": {
            "read-only": "Read-only spouse-share statement line created by myTax",
            "not-entered": "Not entered in myTax for this tax claim code",
            "requires-review": "Benefit code destination requires review",
        },
        "paper": {
            "not-entered": "Not entered at label L for tax claim code F",
            "requires-review": "Label L destination requires review",
        },
    },
}

EXPECTED_SOURCES = {
    "ato-f99c3a4ad079": {
        "url": "https://www.ato.gov.au/individuals-and-families/your-tax-return/instructions-to-complete-your-tax-return/mytax-instructions/2026/medicare-and-private-health-insurance/private-health-insurance",
        "content_hash": "da3592fbaa5668af33905a526362d13a976695834084d0d0f8b7bbc405e4d1d1",
        "checked_at": "2026-07-10T06:27:17Z",
    },
    "ato-2a2cf8a8c462": {
        "url": "https://www.ato.gov.au/forms-and-instructions/individual-tax-return-2026-instructions/medicare-levy-questions-m1-m2-individual-tax-return-2026/private-health-insurance-policy-details-2026",
        "content_hash": "38a3018c329e8c1e168a6b169a35530c730f89f1a199bc834e81488003117cc6",
        "checked_at": "2026-07-10T06:27:17Z",
    },
    "ato-4cedc9f93767": {
        "url": "https://www.ato.gov.au/individuals-and-families/your-tax-return/instructions-to-complete-your-tax-return/mytax-instructions/2026/medicare-and-private-health-insurance/medicare-levy-reduction-or-exemption",
        "content_hash": "2c7c4e2623459a338d146c41899f7a3b5ad5f2ea70c1b95640d950e9cad6d23c",
        "checked_at": "2026-07-10T06:27:17Z",
    },
    "ato-39155fe09d00": {
        "url": "https://www.ato.gov.au/forms-and-instructions/individual-tax-return-2026-instructions/medicare-levy-questions-m1-m2-individual-tax-return-2026/m1-medicare-levy-reduction-or-exemption-2026",
        "content_hash": "272598694ee4ca50ee47cef9b8130dbd93a7c16dbcdb868aedeeaed5abc752b7",
        "checked_at": "2026-07-10T06:27:17Z",
    },
    "ato-836a84c52e60": {
        "url": "https://www.ato.gov.au/individuals-and-families/your-tax-return/instructions-to-complete-your-tax-return/mytax-instructions/2026/medicare-and-private-health-insurance/medicare-levy-surcharge",
        "content_hash": "ef48900dec7c99657f728f1751f49f83fd3eea6ff5d9401476cffc5554874f24",
        "checked_at": "2026-07-10T06:27:18Z",
    },
    "ato-b8cc03014dc1": {
        "url": "https://www.ato.gov.au/forms-and-instructions/individual-tax-return-2026-instructions/medicare-levy-questions-m1-m2-individual-tax-return-2026/m2-medicare-levy-surcharge-2026",
        "content_hash": "b604f09774f9a6ee18e63d98afa7fee9e678cb6f7429b1f71fba9a5a0797c163",
        "checked_at": "2026-07-10T06:27:18Z",
    },
    "ato-815a889d0a59": {
        "url": "https://www.ato.gov.au/individuals-and-families/your-tax-return/instructions-to-complete-your-tax-return/mytax-instructions/2026/other-mytax-instructions-including-spouse-details-and-income-tests/spouse-details",
        "content_hash": "ea256593bfa3b5d30a4cc742970e6a88d02c9645ccb2db497ae4b1e35728d016",
        "checked_at": "2026-07-10T06:27:18Z",
    },
    "ato-29a73bbec8f5": {
        "url": "https://www.ato.gov.au/forms-and-instructions/individual-tax-return-2026-instructions/spouse-details-married-or-de-facto-2026",
        "content_hash": "29f2101f9c146bcfd111bd457799c3eb049a6a725b4362175ea4abb4670c99fe",
        "checked_at": "2026-07-10T06:27:48Z",
    },
}

ACTION_DESTINATION_MATRIX = {
    "enter-reviewed-value": {"verified"},
    "answer-guided-question": {"verified"},
    "retain-evidence": {"not-entered"},
    "resolve-before-entry": {"verified", "requires-review"},
    "accountant-handoff-only": {"verified", "requires-review", "not-entered"},
    "not-entered-directly": {"not-entered"},
    "destination-requires-review": {"requires-review"},
}

CONTRACT_COPY_PATHS = (
    "scripts/taxmate_handoff.py",
    "scripts/taxmate_intake.py",
    "scripts/taxmate_taxpack.py",
    "scripts/taxmate_validate.py",
    "config/handoff-destinations.json",
    "data/ato_knowledge_base/source_coverage.json",
    "data/ato_knowledge_base/source_registry.json",
    "tests/test_handoff_contract.py",
    "tests/test_handoff_repository_contract.py",
)


def call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
        return f"{node.func.value.id}.{node.func.attr}"
    return ""


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
    return "<module>"


def copy_contract_repo(destination: Path) -> None:
    for rel in CONTRACT_COPY_PATHS:
        source = ROOT / rel
        if not source.exists():
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def copy_destination_state(destination: Path) -> None:
    for rel in (
        "config/handoff-destinations.json",
        "data/ato_knowledge_base/source_coverage.json",
        "data/ato_knowledge_base/source_registry.json",
    ):
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)


def finding_count(root: Path, fragment: str) -> int:
    return sum(
        fragment in finding.detail
        for finding in taxmate_review_guardrails.check_handoff_contract(root)
    )


def normalized_row(
    number: str,
    row_kind: str,
    status: str,
    *,
    action_kind: str,
) -> dict[str, Any]:
    contract = taxmate_handoff.build_row_contract(
        row_kind,
        status,
        [taxmate_handoff.fact("value", "Supplied value", 0, action_kind=action_kind)],
        root=ROOT,
    )
    return {
        "number": number,
        "status": status,
        "source_urls": [],
        "checked_at": "",
        **contract,
    }


class RepositoryAstContractTests(unittest.TestCase):
    def test_all_guide_row_calls_supply_literal_row_kind_and_facts(self) -> None:
        tree = ast.parse((SCRIPTS / "taxmate_intake.py").read_text(encoding="utf-8"))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and call_name(node) == "guide_row"]
        self.assertEqual(70, len(calls))

        violations: list[str] = []
        for node in calls:
            keywords = {keyword.arg: keyword.value for keyword in node.keywords if keyword.arg}
            row_kind = keywords.get("row_kind")
            if not isinstance(row_kind, ast.Constant) or not isinstance(row_kind.value, str) or not row_kind.value.strip():
                violations.append(f"line {node.lineno}: row_kind must be a nonblank string literal")
            if "facts" not in keywords or isinstance(keywords["facts"], ast.Constant) and keywords["facts"].value is None:
                violations.append(f"line {node.lineno}: facts must be explicit")

        self.assertEqual([], violations)

    def test_intake_does_not_use_compatibility_fact_synthesis(self) -> None:
        tree = ast.parse((SCRIPTS / "taxmate_intake.py").read_text(encoding="utf-8"))
        lines = [
            node.lineno
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and call_name(node) == "taxmate_handoff.compatibility_facts"
        ]
        self.assertEqual([], lines)

    def test_taxpack_contains_no_fact_action_or_destination_mapping_logic(self) -> None:
        tree = ast.parse((SCRIPTS / "taxmate_taxpack.py").read_text(encoding="utf-8"))
        violations: list[str] = []
        forbidden_calls = {
            "taxmate_handoff.fact",
            "taxmate_handoff.verified_destination",
            "taxmate_handoff.destination_source",
            "taxmate_handoff.requested_fact_handoff",
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = call_name(node)
                if name in forbidden_calls:
                    violations.append(f"line {node.lineno}: {name}")
                for keyword in node.keywords:
                    if keyword.arg in {"action_kind", "destination_key"}:
                        violations.append(f"line {node.lineno}: {keyword.arg}")
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in DESTINATION_IDS:
                violations.append(f"line {node.lineno}: mapping id {node.value}")

        self.assertEqual([], violations)

    def test_destination_mapping_ids_are_literal_and_producer_scoped(self) -> None:
        tree = ast.parse((SCRIPTS / "taxmate_intake.py").read_text(encoding="utf-8"))
        parents = parent_map(tree)
        violations: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or node.value not in DESTINATION_IDS:
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(parent, ast.Call):
                parent = parents.get(parent)
            function = enclosing_function(node, parents)
            if not isinstance(parent, ast.Call) or call_name(parent) != "taxmate_handoff.fact":
                violations.append(f"line {node.lineno}: {node.value} is not a fact destination")
                continue
            destination_values = [
                keyword.value
                for keyword in parent.keywords
                if keyword.arg == "destination_key"
            ]
            if node not in destination_values:
                violations.append(f"line {node.lineno}: {node.value} is not destination_key")
            if function not in APPROVED_DESTINATION_PRODUCERS[node.value]:
                violations.append(f"line {node.lineno}: {node.value} used by {function}")

        self.assertEqual([], violations)


class RuntimeContractTests(unittest.TestCase):
    def test_compatibility_fallback_preserves_one_full_semicolon_value(self) -> None:
        value = "zero 0; false false; user-supplied explanation"
        facts = taxmate_handoff.compatibility_facts("Supplied details", value, "Keep visible.")

        self.assertEqual(1, len(facts))
        self.assertEqual(value, facts[0]["value"])
        self.assertFalse(str(facts[0]["key"]).startswith("prepared-detail-"))
        self.assertNotRegex(str(facts[0]["label"]), r"^Prepared detail\b")

    def test_action_destination_matrix_is_exact(self) -> None:
        destinations = {
            "verified": taxmate_handoff.verified_destination(
                "m1-full-days-v",
                income_year="2025-26",
                root=ROOT,
            ),
            "requires-review": taxmate_handoff.unresolved_destination(),
            "not-entered": taxmate_handoff.not_entered_destination(),
        }
        for action_kind in taxmate_handoff.TAXONOMY:
            for destination_kind, destination in destinations.items():
                with self.subTest(action=action_kind, destination=destination_kind):
                    valid = taxmate_validate.handoff_destination_valid(
                        {
                            "kind": action_kind,
                            "label": taxmate_handoff.TAXONOMY[action_kind]["label"],
                            "next_action": taxmate_handoff.ACTION_TEXT[action_kind],
                            "destination": destination,
                        }
                    )
                    self.assertEqual(
                        destination_kind in ACTION_DESTINATION_MATRIX[action_kind],
                        valid,
                    )

    def test_field_level_is_not_a_destination_kind(self) -> None:
        self.assertNotIn("field-level", taxmate_handoff.DESTINATION_KINDS)
        self.assertNotIn("field-level", taxmate_validate.HANDOFF_DESTINATION_KINDS)
        normalized = taxmate_handoff.normalize_handoff(
            {
                "kind": "accountant-handoff-only",
                "next_action": "Give this fact to an accountant.",
                "destination": {"kind": "field-level", "label": "Field-level destinations."},
            },
            status_kind="review",
            root=ROOT,
        )
        self.assertEqual("requires-review", normalized["destination"]["kind"])

    def test_supplied_row_handoff_cannot_weaken_fact_aggregate(self) -> None:
        mixed = taxmate_handoff.normalize_row_contract(
            row_kind="private-health-statement",
            facts=[
                taxmate_handoff.fact(
                    "premiums-eligible-for-rebate",
                    "Premiums eligible for rebate",
                    100,
                    action_kind="enter-reviewed-value",
                    destination_key="phi-premiums-j",
                ),
                taxmate_handoff.fact(
                    "statement-evidence",
                    "Statement evidence",
                    "supporting only",
                    action_kind="not-entered-directly",
                ),
            ],
            handoff={
                "kind": "enter-reviewed-value",
                "next_action": "Use this value.",
                "destination": taxmate_handoff.verified_destination(
                    "phi-premiums-j",
                    income_year="2025-26",
                    root=ROOT,
                ),
            },
            status="Used",
            income_year="2025-26",
            question="",
            answer="",
            why="",
            root=ROOT,
        )
        self.assertEqual("destination-requires-review", mixed["handoff"]["kind"])

        evidence = taxmate_handoff.normalize_row_contract(
            row_kind="evidence-test",
            facts=[
                taxmate_handoff.fact(
                    "gap",
                    "Evidence gap",
                    "missing",
                    action_kind="resolve-before-entry",
                )
            ],
            handoff={
                "kind": "retain-evidence",
                "next_action": "Retain this record.",
                "destination": taxmate_handoff.not_entered_destination(),
            },
            status="Evidence",
            income_year="2025-26",
            question="",
            answer="",
            why="",
            root=ROOT,
        )
        self.assertEqual("resolve-before-entry", evidence["handoff"]["kind"])

    def test_duplicate_fact_keys_fail_payload_validation(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = payload["items"][0]
        duplicate = copy.deepcopy(row["facts"][0])
        row["facts"].append(duplicate)

        self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_payload_validation_covers_each_entity_section(self) -> None:
        answers = taxmate_intake.sample_answers()
        answers.update({
            "company_return": {"name": "Example Co", "residency": "Australian"},
            "trust_return": {"name": "Example Trust", "trustee": "Example Pty Ltd"},
            "partnership_return": {
                "name": "Example Partnership",
                "partners": 2,
                "share_percentages": [50, 50],
            },
        })
        baseline = taxmate_intake.answers_to_pack_payload(answers)
        self.assertTrue(taxmate_validate.handoff_payload_contract(baseline))

        for section in ("company_items", "trust_items", "partnership_items"):
            with self.subTest(section=section):
                payload = copy.deepcopy(baseline)
                payload[section][0].pop("facts")
                self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_payload_validation_requires_entity_section_lists(self) -> None:
        baseline = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        for section in ("company_items", "trust_items", "partnership_items"):
            absent = copy.deepcopy(baseline)
            absent.pop(section)
            self.assertTrue(taxmate_validate.handoff_payload_contract(absent))
            for invalid in (None, {}):
                with self.subTest(section=section, invalid=invalid):
                    payload = copy.deepcopy(baseline)
                    payload[section] = invalid
                    self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_payload_validation_requires_canonical_handoff_label_and_action(self) -> None:
        baseline = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = baseline["items"][0]
        fact = row["facts"][0]
        self.assertTrue(taxmate_validate.handoff_payload_contract(baseline))

        mutations = (
            ("row label", row["number"], None, "label", "Use this row"),
            ("row action", row["number"], None, "next_action", "Copy now"),
            ("fact label", row["number"], fact["key"], "label", "Use this fact"),
            ("fact action", row["number"], fact["key"], "next_action", "Copy now"),
        )
        for label, number, fact_key, field, value in mutations:
            with self.subTest(label=label):
                payload = copy.deepcopy(baseline)
                target_row = next(item for item in payload["items"] if item["number"] == number)
                handoff = target_row["handoff"]
                if fact_key is not None:
                    handoff = next(item for item in target_row["facts"] if item["key"] == fact_key)["handoff"]
                handoff[field] = value

                self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_payload_validation_rejects_forged_destination_mapping_and_sources(self) -> None:
        baseline = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = next(item for item in baseline["items"] if item["number"] == "PHI-STMT-1")
        fact = next(item for item in row["facts"] if item["key"] == "premiums-eligible-for-rebate")
        self.assertEqual("phi-premiums-j", fact["handoff"]["destination"]["mapping_id"])

        def forged_mapping(target: dict[str, Any]) -> None:
            target["handoff"]["destination"]["mapping_id"] = "phi-rebate-k"

        def forged_source(target: dict[str, Any]) -> None:
            destination = target["handoff"]["destination"]
            destination["sources"][0]["url"] = "https://www.ato.gov.au/about-ato"
            destination["channels"]["mytax"]["sources"][0]["url"] = "https://www.ato.gov.au/about-ato"

        def forged_declaration(target: dict[str, Any]) -> None:
            target["destination_key"] = "phi-rebate-k"

        for label, mutate in (
            ("mapping", forged_mapping),
            ("source", forged_source),
            ("declaration", forged_declaration),
        ):
            with self.subTest(label=label):
                payload = copy.deepcopy(baseline)
                target_row = next(item for item in payload["items"] if item["number"] == "PHI-STMT-1")
                target_fact = next(
                    item for item in target_row["facts"] if item["key"] == "premiums-eligible-for-rebate"
                )
                mutate(target_fact)

                self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_payload_validation_rejects_binding_key_bypass(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = next(item for item in payload["items"] if item["number"] == "PHI-STMT-1")
        fact = next(item for item in row["facts"] if item["key"] == "premiums-eligible-for-rebate")
        fact["key"] = "gross-interest"
        fact["binding_key"] = "premiums-eligible-for-rebate"

        self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_payload_validation_rejects_stale_status_contracts(self) -> None:
        baseline = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        mutations = (
            ("used plus evidence", "items", "income_year", "status_kind", "Evidence"),
            ("evidence marked used", "items", "WFH", "status", "Used"),
            ("used marked skipped", "items", "resident", "status", "N/A skipped"),
        )
        for label, section, number, field, value in mutations:
            with self.subTest(label=label):
                payload = copy.deepcopy(baseline)
                row = next(item for item in payload[section] if item["number"] == number)
                row[field] = value

                self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_payload_validation_rederives_all_runtime_rows_and_preserves_falsey_values(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        values = [
            fact["value"]
            for section in (
                "items", "abn_items", "bas_items", "company_items", "trust_items",
                "partnership_items", "missing_facts", "evidence_items",
            )
            for row in payload[section]
            for fact in row["facts"]
        ]

        self.assertTrue(any(type(value) is int and value == 0 for value in values))
        self.assertTrue(any(value is False for value in values))
        self.assertTrue(taxmate_validate.handoff_payload_contract(payload))

    def test_extraction_payload_requires_shared_normalizer_idempotence(self) -> None:
        baseline = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        extraction = baseline["extracted_values"][0]
        renormalized = taxmate_handoff.normalize_extraction_row(
            copy.deepcopy(extraction),
            baseline["income_year"],
            index=1,
            root=ROOT,
        )
        self.assertEqual(extraction, renormalized)

        payload = copy.deepcopy(baseline)
        payload["extracted_values"][0]["facts"][0]["handoff"]["next_action"] = "Copy now"

        self.assertFalse(taxmate_validate.handoff_payload_contract(payload))

    def test_arbitrary_destination_text_fails_closed(self) -> None:
        normalized = taxmate_handoff.normalize_destination(
            {
                "kind": "requires-review",
                "label": "Review this destination.",
                "mytax": "Unverified myTax path supplied by a row.",
                "paper": "Unverified paper label supplied by a row.",
            },
            ROOT,
            "2025-26",
        )

        self.assertEqual("requires-review", normalized["kind"])
        self.assertEqual("", normalized["mapping_id"])
        self.assertEqual("Not verified for direct use.", normalized["mytax"])
        self.assertEqual("Not verified for direct use.", normalized["paper"])
        self.assertEqual([], normalized["sources"])

    def test_queue_only_and_extended_only_payloads_validate(self) -> None:
        empty_sections: dict[str, Any] = {
            "items": [],
            "abn_items": [],
            "bas_items": [],
            "company_items": [],
            "trust_items": [],
            "partnership_items": [],
            "missing_facts": [],
            "evidence_items": [],
            "extracted_values": [],
        }
        queue_only = copy.deepcopy(empty_sections)
        queue_only["evidence_items"] = [
            normalized_row("EVID-ONLY", "evidence-queue", "Evidence", action_kind="retain-evidence")
        ]
        extended_only = copy.deepcopy(empty_sections)
        extended_only["abn_items"] = [
            normalized_row("ABN", "abn-business", "Accountant review", action_kind="accountant-handoff-only")
        ]
        extended_only["bas_items"] = [
            normalized_row("BAS", "bas", "Accountant review", action_kind="accountant-handoff-only")
        ]

        self.assertTrue(taxmate_validate.handoff_payload_contract(queue_only))
        self.assertTrue(taxmate_validate.handoff_payload_contract(extended_only))

    def test_supporting_source_never_becomes_destination_mapping(self) -> None:
        source = EXPECTED_SOURCES["ato-f99c3a4ad079"]
        item = taxmate_taxpack.guide_item(
            {
                "number": "SOURCE-ONLY",
                "ato_area": "Private health context",
                "question": "Source-only fact",
                "answer": 0,
                "why_included": "A supporting source does not verify a destination.",
                "status": "Used",
                "row_kind": "source-only-test",
                "facts": [taxmate_handoff.fact("value", "Value", 0)],
                "source_urls": [source["url"]],
                "checked_at": source["checked_at"],
            }
        )
        contract = taxmate_taxpack.item_contract(item, "2025-26")

        self.assertNotEqual("verified", contract["handoff"]["destination"]["kind"])
        for fact in contract["facts"]:
            self.assertNotEqual("verified", fact["handoff"]["destination"]["kind"])
            self.assertEqual("", fact["handoff"]["destination"]["mapping_id"])


class DestinationManifestContractTests(unittest.TestCase):
    def test_destination_manifest_matches_exact_verified_bindings(self) -> None:
        manifest = taxmate_handoff.load_destination_manifest(ROOT)

        self.assertEqual(2, manifest["schema_version"])
        self.assertEqual("2025-26", manifest["income_year"])
        self.assertEqual(DESTINATION_IDS, set(manifest["destinations"]))
        for mapping_id, expected in EXPECTED_DESTINATIONS.items():
            with self.subTest(mapping_id=mapping_id):
                actual = manifest["destinations"][mapping_id]
                expected_top_keys = {"label", "mytax", "paper"}
                if mapping_id in EXPECTED_PHI_CONTEXTS:
                    expected_top_keys.add("context")
                    self.assertEqual(EXPECTED_PHI_CONTEXTS[mapping_id], actual.get("context"))
                self.assertEqual(expected_top_keys, set(actual))
                self.assertEqual(expected["label"], actual["label"])
                for channel_name in ("mytax", "paper"):
                    expected_channel = expected[channel_name]
                    actual_channel = actual[channel_name]
                    expected_channel_keys = {"kind", "location", "source_id", "content_hash"}
                    if mapping_id in EXPECTED_PHI_STATE_LOCATIONS:
                        expected_channel_keys.add("state_locations")
                        self.assertEqual(
                            EXPECTED_PHI_STATE_LOCATIONS[mapping_id][channel_name],
                            actual_channel.get("state_locations"),
                        )
                    self.assertEqual(expected_channel_keys, set(actual_channel))
                    self.assertEqual(expected_channel, {key: actual_channel[key] for key in expected_channel})

    def test_resolved_destinations_keep_channel_review_state_and_provenance(self) -> None:
        for mapping_id, paper_source_id in (
            ("m1-exemption-question", "ato-39155fe09d00"),
            ("spouse-had-question", "ato-29a73bbec8f5"),
        ):
            with self.subTest(mapping_id=mapping_id):
                destination = taxmate_handoff.verified_destination(
                    mapping_id,
                    income_year="2025-26",
                    root=ROOT,
                )
                channels = destination.get("channels")
                self.assertIsInstance(channels, dict)
                self.assertEqual("verified", channels["mytax"]["kind"])
                self.assertEqual("requires-review", channels["paper"]["kind"])
                self.assertEqual(destination["mytax"], channels["mytax"]["location"])
                self.assertEqual(destination["paper"], channels["paper"]["location"])
                paper_sources = channels["paper"]["sources"]
                self.assertEqual([paper_source_id], [source["source_id"] for source in paper_sources])

    def test_destination_sources_match_exact_url_hash_and_dates(self) -> None:
        coverage, registry = taxmate_handoff.source_state(ROOT)
        self.assertTrue(set(EXPECTED_SOURCES).issubset(coverage))
        self.assertTrue(set(EXPECTED_SOURCES).issubset(registry))

        for source_id, expected in EXPECTED_SOURCES.items():
            with self.subTest(source_id=source_id):
                covered = coverage[source_id]
                record = registry[source_id]
                self.assertEqual("verified", covered["status"])
                self.assertEqual(expected["url"], covered["canonical_url"])
                self.assertEqual(expected["content_hash"], covered["content_hash"])
                self.assertEqual(expected["checked_at"], covered["checked_at"])
                self.assertTrue(str(covered.get("source_title", "")).strip())
                self.assertIs(record.get("content_verified"), True)
                self.assertEqual(expected["content_hash"], record["content_hash"])
                self.assertEqual(expected["checked_at"], record["last_checked"])
                self.assertEqual(
                    expected["url"],
                    taxmate_handoff.canonical_url(str(record.get("final_url") or record.get("url"))),
                )

    def test_destination_hashes_are_lowercase_sha256(self) -> None:
        for mapping in EXPECTED_DESTINATIONS.values():
            for channel_name in ("mytax", "paper"):
                digest = mapping[channel_name]["content_hash"]
                self.assertRegex(digest, r"^[0-9a-f]{64}$")

    def test_mapping_validation_rejects_source_hash_url_and_date_drift(self) -> None:
        mutations = {
            "manifest hash": lambda manifest, coverage, registry: manifest["destinations"][
                "phi-premiums-j"
            ]["mytax"].update(content_hash="0" * 64),
            "coverage URL": lambda manifest, coverage, registry: next(
                entry for entry in coverage["sources"] if entry.get("source_id") == "ato-f99c3a4ad079"
            ).update(canonical_url="https://www.ato.gov.au/about-ato"),
            "coverage date": lambda manifest, coverage, registry: next(
                entry for entry in coverage["sources"] if entry.get("source_id") == "ato-f99c3a4ad079"
            ).update(checked_at=""),
            "registry date": lambda manifest, coverage, registry: next(
                entry
                for entry in registry["records"]
                if entry.get("content_hash") == EXPECTED_SOURCES["ato-f99c3a4ad079"]["content_hash"]
            ).update(last_checked=""),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                copy_destination_state(root)
                manifest_path = root / "config/handoff-destinations.json"
                coverage_path = root / "data/ato_knowledge_base/source_coverage.json"
                registry_path = root / "data/ato_knowledge_base/source_registry.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
                registry = json.loads(registry_path.read_text(encoding="utf-8"))
                mutate(manifest, coverage, registry)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
                registry_path.write_text(json.dumps(registry), encoding="utf-8")

                self.assertTrue(taxmate_handoff.destination_mapping_errors(root))

    def test_mapping_validation_rejects_non_sha256_hash_even_when_state_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_destination_state(root)
            invalid_hash = "z" * 64
            manifest_path = root / "config/handoff-destinations.json"
            coverage_path = root / "data/ato_knowledge_base/source_coverage.json"
            registry_path = root / "data/ato_knowledge_base/source_registry.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            manifest["destinations"]["phi-premiums-j"]["mytax"]["content_hash"] = invalid_hash
            next(
                entry for entry in coverage["sources"] if entry.get("source_id") == "ato-f99c3a4ad079"
            )["content_hash"] = invalid_hash
            next(
                entry
                for entry in registry["records"]
                if entry.get("content_hash") == EXPECTED_SOURCES["ato-f99c3a4ad079"]["content_hash"]
            )["content_hash"] = invalid_hash
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            coverage_path.write_text(json.dumps(coverage), encoding="utf-8")
            registry_path.write_text(json.dumps(registry), encoding="utf-8")

            errors = taxmate_handoff.destination_mapping_errors(root)

        self.assertTrue(any("content_hash is invalid" in error for error in errors))


class GuardrailMutationTests(unittest.TestCase):
    def test_guardrail_detects_new_missing_guide_row_facts(self) -> None:
        class RemoveFirstFacts(ast.NodeTransformer):
            removed = False

            def visit_Call(self, node: ast.Call) -> ast.AST:
                self.generic_visit(node)
                if self.removed or call_name(node) != "guide_row":
                    return node
                if any(keyword.arg == "facts" for keyword in node.keywords):
                    node.keywords = [keyword for keyword in node.keywords if keyword.arg != "facts"]
                    self.removed = True
                return node

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            before = finding_count(root, "guide_row call missing explicit facts")
            path = root / "scripts/taxmate_intake.py"
            tree = ast.parse(path.read_text(encoding="utf-8"))
            transformer = RemoveFirstFacts()
            tree = transformer.visit(tree)
            self.assertTrue(transformer.removed)
            ast.fix_missing_locations(tree)
            path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
            after = finding_count(root, "guide_row call missing explicit facts")

        self.assertEqual(before + 1, after)

    def test_guardrail_detects_new_nonliteral_guide_row_kind(self) -> None:
        class SetFirstRowKind(ast.NodeTransformer):
            def __init__(self, value: ast.expr) -> None:
                self.value = value
                self.changed = False

            def visit_Call(self, node: ast.Call) -> ast.AST:
                self.generic_visit(node)
                if self.changed or call_name(node) != "guide_row":
                    return node
                node.keywords = [keyword for keyword in node.keywords if keyword.arg != "row_kind"]
                node.keywords.append(ast.keyword(arg="row_kind", value=self.value))
                self.changed = True
                return node

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            path = root / "scripts/taxmate_intake.py"
            tree = ast.parse(path.read_text(encoding="utf-8"))
            baseline_transformer = SetFirstRowKind(ast.Constant(value="individual-return"))
            tree = baseline_transformer.visit(tree)
            self.assertTrue(baseline_transformer.changed)
            ast.fix_missing_locations(tree)
            path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
            before = finding_count(root, "guide_row call missing literal row_kind")

            tree = ast.parse(path.read_text(encoding="utf-8"))
            mutation = SetFirstRowKind(ast.Name(id="dynamic_row_kind", ctx=ast.Load()))
            tree = mutation.visit(tree)
            self.assertTrue(mutation.changed)
            ast.fix_missing_locations(tree)
            path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
            after = finding_count(root, "guide_row call missing literal row_kind")

        self.assertEqual(before + 1, after)

    def test_guardrail_detects_output_owned_fact_logic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            before = finding_count(root, "output layer constructs handoff facts or destinations")
            path = root / "scripts/taxmate_taxpack.py"
            path.write_text(
                path.read_text(encoding="utf-8")
                + '\n_OUTPUT_OWNED = taxmate_handoff.fact("x", "X", 1)\n',
                encoding="utf-8",
            )
            after = finding_count(root, "output layer constructs handoff facts or destinations")

        self.assertEqual(before + 1, after)

    def test_guardrail_detects_dynamic_renderer_mapping_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            before = finding_count(root, "output layer contains destination mapping identifiers")
            manifest_path = root / "config/handoff-destinations.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["destinations"]["rogue-destination"] = copy.deepcopy(
                manifest["destinations"]["phi-premiums-j"]
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            taxpack_path = root / "scripts/taxmate_taxpack.py"
            taxpack_path.write_text(
                taxpack_path.read_text(encoding="utf-8") + '\n_RENDERER_MAPPING = "rogue-destination"\n',
                encoding="utf-8",
            )
            after = finding_count(root, "output layer contains destination mapping identifiers")

        self.assertEqual(before + 1, after)

    def test_guardrail_rejects_field_level_destination_kind(self) -> None:
        class SetDestinationKinds(ast.NodeTransformer):
            def __init__(self, include_field_level: bool) -> None:
                self.include_field_level = include_field_level

            def visit_Assign(self, node: ast.Assign) -> ast.AST:
                self.generic_visit(node)
                if not any(
                    isinstance(target, ast.Name)
                    and target.id in {"DESTINATION_KINDS", "HANDOFF_DESTINATION_KINDS"}
                    for target in node.targets
                ):
                    return node
                if isinstance(node.value, ast.Set):
                    values = {
                        item.value
                        for item in node.value.elts
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    }
                    values.discard("field-level")
                    if self.include_field_level:
                        values.add("field-level")
                    node.value.elts = [ast.Constant(value=value) for value in sorted(values)]
                return node

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            for rel in ("scripts/taxmate_handoff.py", "scripts/taxmate_validate.py"):
                path = root / rel
                tree = SetDestinationKinds(False).visit(ast.parse(path.read_text(encoding="utf-8")))
                ast.fix_missing_locations(tree)
                path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
            before = finding_count(root, "field-level destination kind is forbidden")
            runtime_path = root / "scripts/taxmate_handoff.py"
            tree = SetDestinationKinds(True).visit(ast.parse(runtime_path.read_text(encoding="utf-8")))
            ast.fix_missing_locations(tree)
            runtime_path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
            after = finding_count(root, "field-level destination kind is forbidden")

        self.assertEqual(before + 1, after)

    def test_guardrail_detects_mapping_used_by_wrong_producer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            before = finding_count(root, "destination mapping used outside approved producer")
            path = root / "scripts/taxmate_intake.py"
            body = path.read_text(encoding="utf-8")
            mutated = body.replace(
                'destination_key="m1-full-days-v"',
                'destination_key="phi-premiums-j"',
                1,
            )
            self.assertNotEqual(body, mutated)
            path.write_text(mutated, encoding="utf-8")
            after = finding_count(root, "destination mapping used outside approved producer")

        self.assertEqual(before + 1, after)

    def test_guardrail_detects_extra_mapping_and_changed_location(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            exact_before = finding_count(root, "destination manifest must match exact mapping set")
            location_before = finding_count(root, "destination location does not match verified binding")
            path = root / "config/handoff-destinations.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["destinations"]["rogue-destination"] = copy.deepcopy(
                manifest["destinations"]["phi-premiums-j"]
            )
            manifest["destinations"]["phi-premiums-j"]["mytax"]["location"] = "Private health"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            exact_after = finding_count(root, "destination manifest must match exact mapping set")
            location_after = finding_count(root, "destination location does not match verified binding")

        self.assertEqual(exact_before + 1, exact_after)
        self.assertEqual(location_before + 1, location_after)

    def test_guardrail_detects_exact_channel_kind_source_and_hash_changes(self) -> None:
        mutations = {
            "destination channel kind does not match verified binding": lambda channel: channel.update(
                kind="requires-review"
            ),
            "source is unrelated to the verified destination": lambda channel: channel.update(
                source_id="ato-39155fe09d00"
            ),
            "destination hash does not match verified binding": lambda channel: channel.update(
                content_hash="0" * 64
            ),
        }
        for fragment, mutate in mutations.items():
            with self.subTest(fragment=fragment), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                copy_contract_repo(root)
                path = root / "config/handoff-destinations.json"
                path.write_text(
                    json.dumps(
                        {
                            "schema_version": 2,
                            "income_year": "2025-26",
                            "destinations": copy.deepcopy(EXPECTED_DESTINATIONS),
                        }
                    ),
                    encoding="utf-8",
                )
                before = finding_count(root, fragment)
                manifest = json.loads(path.read_text(encoding="utf-8"))
                mutate(manifest["destinations"]["phi-premiums-j"]["mytax"])
                path.write_text(json.dumps(manifest), encoding="utf-8")
                after = finding_count(root, fragment)

            self.assertEqual(before + 1, after)

    def test_guardrail_detects_coverage_registry_url_date_and_hash_mismatch(self) -> None:
        mutations = {
            "coverage-registry URL mismatch": lambda entry: entry.update(
                canonical_url="https://www.ato.gov.au/about-ato"
            ),
            "coverage-registry date mismatch": lambda entry: entry.update(checked_at=""),
            "coverage-registry hash mismatch": lambda entry: entry.update(content_hash="0" * 64),
        }
        for fragment, mutate in mutations.items():
            with self.subTest(fragment=fragment), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                copy_contract_repo(root)
                before = finding_count(root, fragment)
                path = root / "data/ato_knowledge_base/source_coverage.json"
                coverage = json.loads(path.read_text(encoding="utf-8"))
                entry = next(
                    item for item in coverage["sources"] if item.get("source_id") == "ato-f99c3a4ad079"
                )
                mutate(entry)
                path.write_text(json.dumps(coverage), encoding="utf-8")
                after = finding_count(root, fragment)

            self.assertEqual(before + 1, after)

    def test_guardrail_requires_compatibility_duplicate_and_extended_payload_tests(self) -> None:
        names = (
            "test_compatibility_fallback_preserves_one_full_semicolon_value",
            "test_duplicate_fact_keys_fail_payload_validation",
            "test_queue_only_and_extended_only_payloads_validate",
            "test_payload_validation_requires_canonical_handoff_label_and_action",
            "test_payload_validation_rejects_forged_destination_mapping_and_sources",
            "test_payload_validation_rejects_binding_key_bypass",
            "test_payload_validation_rejects_stale_status_contracts",
            "test_payload_validation_rederives_all_runtime_rows_and_preserves_falsey_values",
            "test_extraction_payload_requires_shared_normalizer_idempotence",
        )
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                copy_contract_repo(root)
                before = finding_count(root, name)
                path = root / "tests/test_handoff_repository_contract.py"
                body = path.read_text(encoding="utf-8")
                self.assertIn(name, body)
                path.write_text(body.replace(name, "removed_contract_case"), encoding="utf-8")
                after = finding_count(root, name)

            self.assertEqual(before + 1, after)

    def test_guardrail_rejects_valid_but_unrelated_source_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            copy_contract_repo(root)
            before = finding_count(root, "source is unrelated to the verified destination")
            path = root / "config/handoff-destinations.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            unrelated = manifest["destinations"]["m1-full-days-v"]["paper"]
            channel = manifest["destinations"]["phi-premiums-j"]["paper"]
            channel["source_id"] = unrelated["source_id"]
            channel["content_hash"] = unrelated["content_hash"]
            path.write_text(json.dumps(manifest), encoding="utf-8")
            after = finding_count(root, "source is unrelated to the verified destination")

        self.assertEqual(before + 1, after)


class PublicationContractTests(unittest.TestCase):
    def test_publication_checks_require_handoff_runtime_files(self) -> None:
        body = (SCRIPTS / "check-publication-ready.sh").read_text(encoding="utf-8")

        self.assertRegex(body, r"\[\[\s+-f\s+scripts/taxmate_handoff\.py\s+\]\]")
        self.assertRegex(body, r"\[\[\s+-f\s+config/handoff-destinations\.json\s+\]\]")

    def test_installed_plugin_smokes_require_handoff_runtime_files(self) -> None:
        for rel in ("scripts/test-codex-plugin-install.sh", "scripts/test-claude-plugin-install.sh"):
            with self.subTest(rel=rel):
                body = (ROOT / rel).read_text(encoding="utf-8")
                self.assertIn('"scripts/taxmate_handoff.py"', body)
                self.assertIn('"config/handoff-destinations.json"', body)

    def test_plugin_lock_integrity_matches_packaged_skills(self) -> None:
        self.assertTrue(taxmate_validate.plugin_lock_skill_paths_exist(str(ROOT)))


if __name__ == "__main__":
    unittest.main()
