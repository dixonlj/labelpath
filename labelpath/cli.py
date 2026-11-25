"""Command-line interface: python -m labelpath query ..."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from labelpath.query import (
    DEFAULT_NEIGHBOR_LIMIT,
    DEFAULT_PATH_LIMIT,
    DISCLAIMER,
    lookup,
    neighbors,
    paths_between,
    warnings,
)


def _print_disclaimer(as_json: bool) -> None:
    # Text mode: the line is part of stdout. JSON mode keeps stdout valid JSON
    # (disclaimer is also a field in the object) and repeats the line on stderr.
    if as_json:
        sys.stderr.write(DISCLAIMER + "\n")
    else:
        sys.stdout.write(DISCLAIMER + "\n")


def _fmt_source(source: Optional[Dict[str, Any]], indent: str = "     ") -> List[str]:
    if not source:
        return [indent + "Source: (none)"]
    lines = []
    kind = source.get("kind")
    set_id = source.get("set_id")
    url = source.get("source_url")
    snippet = source.get("snippet")
    note = source.get("note")
    if kind:
        lines.append(indent + "Section: %s" % kind)
    if set_id:
        lines.append(indent + "Label set_id: %s" % set_id)
    if url:
        lines.append(indent + "Source URL: %s" % url)
    if snippet:
        lines.append(indent + "Snippet: %s" % snippet)
    if note:
        lines.append(indent + "Note: %s" % note)
    if not lines:
        lines.append(indent + "Source: (no section pointer on this edge)")
    return lines


def _fmt_entity(item: Dict[str, Any]) -> str:
    kind = item.get("kind") or "?"
    key = item.get("key") or "?"
    official = item.get("generic_name") or item.get("name") or key
    return "%s %s (%s)" % (kind, key, official)


def format_lookup(result: Dict[str, Any]) -> str:
    lines = [DISCLAIMER, ""]
    if not result.get("found"):
        lines.append("No drug or ingredient named %r was found in this snapshot." % result.get("query"))
        return "\n".join(lines) + "\n"
    lines.append("Found %s match(es) for %r:" % (len(result["matches"]), result.get("query")))
    for item in result["matches"]:
        lines.append("  - " + _fmt_entity(item))
        brands = item.get("brand_names") or []
        if brands:
            lines.append("      Brand names: %s" % ", ".join(brands))
        apps = item.get("application_numbers") or []
        if apps:
            lines.append("      Application numbers: %s" % ", ".join(apps))
    return "\n".join(lines) + "\n"


def format_paths(result: Dict[str, Any]) -> str:
    lines = [DISCLAIMER, ""]
    start = result.get("start")
    end = result.get("end")
    if result.get("error") and not result.get("found"):
        lines.append(result["error"])
        extras = result.get("start_matches") or result.get("end_matches") or []
        if extras:
            lines.append("Candidates:")
            for item in extras:
                lines.append("  - " + _fmt_entity(item))
        return "\n".join(lines) + "\n"
    lines.append(
        "Paths from %s to %s (max %s hop(s), %s shown):"
        % (
            _fmt_entity(start) if start else result.get("start_query"),
            _fmt_entity(end) if end else result.get("end_query"),
            result.get("max_hops"),
            len(result.get("paths") or []),
        )
    )
    if not result.get("paths"):
        lines.append(result.get("error") or "No path found.")
        return "\n".join(lines) + "\n"
    for index, path in enumerate(result["paths"], start=1):
        nodes = path.get("nodes") or []
        steps = path.get("steps") or []
        if nodes:
            label = " -> ".join("%s" % node.get("key") for node in nodes)
            lines.append("")
            lines.append("Path %s (%s hop(s)): %s" % (index, path.get("hops"), label))
        for step_i, step in enumerate(steps, start=1):
            lines.append(
                "  %s. %s -[:%s]-> %s"
                % (step_i, step.get("from_key"), step.get("rel_type"), step.get("to_key"))
            )
            lines.extend(_fmt_source(step.get("source")))
    return "\n".join(lines) + "\n"


def format_warnings(result: Dict[str, Any]) -> str:
    lines = [DISCLAIMER, ""]
    if not result.get("found"):
        lines.append(result.get("error") or "Not found.")
        return "\n".join(lines) + "\n"
    drug = result["drug"]
    lines.append("Warnings for %s" % _fmt_entity(drug))
    boxed = result.get("boxed_warnings") or []
    if boxed:
        lines.append("")
        lines.append("Boxed warning section(s):")
        for item in boxed:
            lines.extend(_fmt_source(item, indent="  "))
    else:
        lines.append("")
        lines.append("No boxed_warning section is present on the chosen label.")
    contra = result.get("contraindication_sections") or []
    if contra:
        lines.append("")
        lines.append("Contraindications section(s):")
        for item in contra:
            lines.extend(_fmt_source(item, indent="  "))
    else:
        lines.append("")
        lines.append("No contraindications section is present on the chosen label.")
    conditions = result.get("contraindicated_in") or []
    if conditions:
        lines.append("")
        lines.append("CONTRAINDICATED_IN phrase matches:")
        for item in conditions:
            lines.append("  - %s" % (item.get("name") or item.get("key")))
            lines.extend(_fmt_source(item.get("source")))
    return "\n".join(lines) + "\n"


def format_neighbors(result: Dict[str, Any]) -> str:
    lines = [DISCLAIMER, ""]
    if not result.get("found"):
        lines.append(result.get("error") or "Not found.")
        return "\n".join(lines) + "\n"
    drug = result["drug"]
    items = result.get("neighbors") or []
    lines.append("Neighbors of %s (%s shown):" % (_fmt_entity(drug), len(items)))
    if not items:
        lines.append("No neighbors in this snapshot.")
        return "\n".join(lines) + "\n"
    for item in items:
        neighbor = item.get("neighbor") or {}
        if item.get("direction") == "outgoing":
            desc = "%s -[:%s]-> %s %s (%s)" % (
                drug.get("key"),
                item.get("rel_type"),
                neighbor.get("kind"),
                neighbor.get("key"),
                neighbor.get("name"),
            )
        else:
            desc = "%s %s (%s) -[:%s]-> %s" % (
                neighbor.get("kind"),
                neighbor.get("key"),
                neighbor.get("name"),
                item.get("rel_type"),
                drug.get("key"),
            )
        lines.append("  - " + desc)
        lines.extend(_fmt_source(item.get("source")))
    return "\n".join(lines) + "\n"


def _emit(result: Dict[str, Any], as_json: bool, formatter) -> int:
    _print_disclaimer(as_json)
    if as_json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        # formatter already includes the disclaimer as the first line
        text = formatter(result)
        if text.startswith(DISCLAIMER):
            text = text[len(DISCLAIMER) :].lstrip("\n")
            sys.stdout.write(text)
            if not text.endswith("\n"):
                sys.stdout.write("\n")
        else:
            sys.stdout.write(text)
    if result.get("found") is False:
        return 0
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m labelpath",
        description=(
            "Query the LabelPath Relate store. Educational only, not medical advice. "
            "The store is opened read-only."
        ),
    )
    parser.add_argument(
        "--database",
        default=None,
        help="Path to a .rl store (default: data/labelpath.rl).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print one JSON object to stdout (the disclaimer line goes to stderr).",
    )
    sub = parser.add_subparsers(dest="group")
    query = sub.add_parser("query", help="Run a lookup, path, warnings, or neighbors query.")
    qsub = query.add_subparsers(dest="action", required=True)

    p_lookup = qsub.add_parser("lookup", help="Find a drug or ingredient by name.")
    p_lookup.add_argument("name")

    p_path = qsub.add_parser("path", help="Find bounded labeled paths between two names.")
    p_path.add_argument("start")
    p_path.add_argument("end")
    p_path.add_argument("--max-hops", type=int, default=3)
    p_path.add_argument("--limit", type=int, default=DEFAULT_PATH_LIMIT)

    p_warn = qsub.add_parser("warnings", help="Show boxed warnings and contraindications.")
    p_warn.add_argument("name")

    p_nei = qsub.add_parser("neighbors", help="List labeled neighbors of a drug.")
    p_nei.add_argument("name")
    p_nei.add_argument("--limit", type=int, default=DEFAULT_NEIGHBOR_LIMIT)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.group != "query" or not args.action:
        parser.print_help()
        return 2
    database = args.database
    as_json = args.as_json
    try:
        if args.action == "lookup":
            result = lookup(args.name, database=database)
            return _emit(result, as_json, format_lookup)
        if args.action == "path":
            result = paths_between(
                args.start,
                args.end,
                max_hops=args.max_hops,
                database=database,
                limit=args.limit,
            )
            return _emit(result, as_json, format_paths)
        if args.action == "warnings":
            result = warnings(args.name, database=database)
            return _emit(result, as_json, format_warnings)
        if args.action == "neighbors":
            result = neighbors(args.name, database=database, limit=args.limit)
            return _emit(result, as_json, format_neighbors)
    except Exception as exc:
        _print_disclaimer(as_json)
        message = "%s: %s" % (type(exc).__name__, exc)
        if as_json:
            json.dump(
                {"disclaimer": DISCLAIMER, "found": False, "error": message},
                sys.stdout,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            sys.stdout.write(message + "\n")
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
