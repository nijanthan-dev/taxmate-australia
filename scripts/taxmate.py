#!/usr/bin/env python3
"""TaxMate Australia full-runtime command launcher."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List


COMMANDS = {
    "calc": "taxmate_calc.py",
    "coverage": "taxmate_coverage.py",
    "finance": "taxmate_finance.py",
    "intake": "taxmate_intake.py",
    "refresh": "taxmate_refresh.py",
    "review-guardrails": "taxmate_review_guardrails.py",
    "skills": "taxmate_skills.py",
    "taxpack": "taxmate_taxpack.py",
    "validate": "taxmate_validate.py",
}

CALLER_CWD_COMMANDS = {"calc", "finance", "intake", "taxpack"}
ROOT_CWD_COMMANDS = {"coverage", "refresh", "review-guardrails", "skills", "validate"}


def _find_repo_root(start: Path) -> Path:
    explicit_root = os.environ.get("TAXMATE_AUSTRALIA_ROOT")
    if explicit_root:
        candidate = Path(explicit_root).expanduser().resolve()
        if candidate.joinpath(".codex-plugin", "plugin.json").exists():
            return candidate

    for candidate in (start, *start.parents):
        if candidate.joinpath(".codex-plugin", "plugin.json").exists():
            return candidate

    return Path.cwd()


def _run_python_command(script: str, args: List[str], root: Path, caller_cwd: Path) -> int:
    script_path = Path(__file__).resolve().parent / script
    if not script_path.exists():
        print(f"error: missing script {script}", file=sys.stderr)
        return 1
    env = {
        **os.environ,
        "TAXMATE_AUSTRALIA_ROOT": str(root),
        "PYTHONDONTWRITEBYTECODE": os.environ.get("PYTHONDONTWRITEBYTECODE", "1"),
    }
    return subprocess.run([sys.executable, str(script_path), *args], cwd=str(caller_cwd), env=env).returncode


def _dispatch(command: str, args: List[str]) -> int:
    caller_cwd = Path.cwd()
    root = _find_repo_root(caller_cwd)
    command_cwd = caller_cwd if command in CALLER_CWD_COMMANDS else root
    return _run_python_command(COMMANDS[command], args, root, command_cwd)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="./scripts/taxmate", description="Run full-runtime TaxMate Australia commands.")
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main(argv: List[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return _dispatch(args.command, list(args.args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
