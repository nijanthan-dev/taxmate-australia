#!/usr/bin/env python3
"""TaxMate Australia refresh command implementation (Python replacement)."""

from __future__ import annotations

import argparse
from typing import List, Optional

import atodata


def command_root() -> str:
    return atodata.SkillRoot()


def run(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="./scripts/taxmate refresh", description="Refresh TaxMate source registry")
    parser.add_argument("--query", default="", help="Refresh indexed pages matching a topic query.")
    parser.add_argument("--all", action="store_true", help="Refresh all indexed pages.")
    parser.add_argument("--recrawl", action="store_true", help="Rebuild scoped ATO source pack from seed URLs.")
    parser.add_argument("--limit", type=int, default=12, help="Max query matches to refresh.")
    parser.add_argument("--max-pages", type=int, default=250, help="Max pages for --recrawl.")
    parser.add_argument("--url", action="append", default=[], help="Refresh explicit indexed ATO URL. Repeatable.")

    args = parser.parse_args(argv)

    try:
        root = command_root()
    except Exception as exc:
        atodata.Errorf("%s", exc)
        return 1

    if args.recrawl:
        try:
            registry = atodata.Recrawl(root, args.max_pages)
        except Exception as exc:
            atodata.Errorf("%s", exc)
            return 1
        atodata.WriteJSON(
            {
                "records": len(registry.records),
                "failures": len(registry.failures),
                "registry": atodata.RegistryPath(root),
            }
        )
        return 0

    try:
        registry = atodata.LoadRegistry(root)
    except Exception as exc:
        atodata.Errorf("%s", exc)
        return 1

    selected = []
    missing: List[str] = []
    if args.all:
        selected = registry.records
    elif len(args.url) > 0:
        selected, missing = atodata.SelectByURL(registry.records, args.url)
    elif args.query:
        selected = atodata.SelectByQuery(root, registry.records, args.query, args.limit)
    else:
        atodata.Errorf("use --query, --url, --all, or --recrawl")
        return 2

    results = []
    for raw_url in missing:
        results.append(atodata.RefreshResult(url=raw_url, error="not in source registry").to_dict())

    changed = 0
    for rec in selected:
        item = atodata.RefreshRecord(root, rec)
        if item.changed:
            changed += 1
        results.append(item.to_dict())

    if selected:
        try:
            atodata.SaveRegistry(root, registry)
        except Exception as exc:
            atodata.Errorf("%s", exc)
            return 1

    atodata.WriteJSON(
        {
            "matched": len(selected),
            "changed": changed,
            "results": results,
        }
    )
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        import sys

        argv = sys.argv[1:]
    return run(argv)


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
