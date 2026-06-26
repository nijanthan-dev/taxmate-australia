#!/usr/bin/env python3
"""TaxMate Australia skills command implementation (Python replacement)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import atodata
import skillgen



def command_root() -> str:
    cwd = os.getcwd()
    if Path(cwd).joinpath(".codex-plugin", "plugin.json").exists():
        return cwd
    return atodata.SkillRoot()


def _exit_json(payload: Dict[str, Any], err: Optional[Exception]) -> int:
    if err is not None:
        out = {"ok": False, "error": str(err)}
        print(json.dumps(out, indent=2))
        return 1
    payload = dict(payload)
    payload["ok"] = True
    print(json.dumps(payload, indent=2))
    return 0


def _read_sources(path: str) -> List[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        raise

    if not isinstance(payload, list):
        raise RuntimeError(f"invalid sources list: {path}")

    out = []
    for row in payload:
        if isinstance(row, dict):
            out.append(row)
    return out


def _source_final_url(row: Dict[str, Any]) -> str:
    return str(row.get("final_url") or row.get("FinalURL") or row.get("url") or "")


def _source_url(row: Dict[str, Any]) -> str:
    return str(row.get("url") or row.get("URL") or "")


def _check_generation(root: str, checked_at: str) -> Tuple[int, Optional[Exception]]:
    work_root = Path(tempfile.mkdtemp(prefix="taxmate-australia-skills-check-"))
    try:
        report = skillgen.Generate(
            skillgen.Options(
                root=root,
                output_root=str(work_root),
                checked_at=checked_at,
            )
        )
        if report is None:
            raise RuntimeError("generation returned empty report")
        count = len(report.sources)
        return count, skillgen.CompareGeneratedArtifacts(root, str(work_root))
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def _refresh(root: str, topic: str, all_sources: bool) -> Dict[str, Any]:
    if not all_sources and not topic:
        raise RuntimeError("use --topic or --all")

    urls: List[str] = []
    for item in skillgen.Topics():
        if not all_sources and item.slug != topic:
            continue
        path = os.path.join(root, "skills", item.slug, "references", "sources.json")
        try:
            sources = _read_sources(path)
        except FileNotFoundError:
            if all_sources:
                continue
            raise
        for row in sources:
            final_url = _source_final_url(row)
            if final_url and skillgen.HostApproved(final_url):
                urls.append(final_url)

    if not urls:
        return {
            "requested": 0,
            "matched": 0,
            "results": [],
        }

    registry = atodata.LoadRegistry(root)
    selected, missing = atodata.SelectByURL(registry.records, urls)

    results: List[Dict[str, Any]] = []
    for raw_url in missing:
        results.append({"url": raw_url, "error": "not in source registry; run taxmate-australia-refresh --url or recrawl first"})

    for rec in selected:
        results.append(atodata.RefreshRecord(root, rec).__dict__)

    atodata.SaveRegistry(root, registry)
    return {
        "requested": len(urls),
        "matched": len(selected),
        "results": results,
    }


def _audit(root: str, output: str, fmt: str, check_only: bool) -> int:
    if check_only:
        return _exit_json({"audit": "source_coverage"}, skillgen.ValidateSourceCoverage(root))

    report = skillgen.WriteCoverageReport(root, fmt)
    if output:
        with open(output, "wb") as f:
            f.write(report)
        return _exit_json({"audit": "source_coverage", "output": output}, None)

    print(report.decode("utf-8"), end="")
    return 0


def run(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="TaxMate skills command")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate")
    gen.add_argument("--checked-at", dest="checked_at", default="", help="verification timestamp")
    gen.add_argument("--check", action="store_true", help="validate generated output without writing tracked files")

    refresh = sub.add_parser("refresh")
    refresh.add_argument("--topic", default="", help="topic slug")
    refresh.add_argument("--all", action="store_true", help="refresh all generated source URLs")

    audit = sub.add_parser("audit")
    audit.add_argument("--format", default="markdown", choices=("markdown", "json"), help="output format")
    audit.add_argument("--output", default="", help="optional output path")
    audit.add_argument("--check", action="store_true", help="validate coverage and exit non-zero on failure")

    sub.add_parser("validate")

    if argv is None:
        import sys
        argv = sys.argv[1:]

    args = parser.parse_args(argv)
    root = command_root()

    if args.command == "generate":
        if args.check:
            sources, err = _check_generation(root, args.checked_at)
            if err is not None:
                return _exit_json(
                    {
                        "generated": True,
                        "sources": sources,
                        "source_coverage": "data/ato_knowledge_base/source_coverage.json",
                    },
                    err,
                )
            return _exit_json(
                {
                    "generated": True,
                    "sources": sources,
                    "source_coverage": "data/ato_knowledge_base/source_coverage.json",
                },
                None,
            )

        report = skillgen.Generate(skillgen.Options(root=root, checked_at=args.checked_at))
        source_count = 0
        if report is not None:
            source_count = len(report.sources)
        return _exit_json(
            {
                "generated": True,
                "sources": source_count,
                "source_coverage": "data/ato_knowledge_base/source_coverage.json",
            },
            None,
        )

    if args.command == "refresh":
        try:
            payload = _refresh(root, topic=args.topic, all_sources=args.all)
            return _exit_json(payload, None)
        except Exception as exc:
            return _exit_json({}, exc)

    if args.command == "audit":
        return _audit(root, args.output, args.format, args.check)

    if args.command == "validate":
        try:
            skillgen.Validate(root)
            return _exit_json({"valid": True}, None)
        except Exception as exc:
            return _exit_json({"valid": False}, exc)

    raise SystemExit(f"unsupported command {args.command}")


def main(argv: Optional[List[str]] = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
