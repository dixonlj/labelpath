"""Command-line interface: python -m labelpath query ... or serve."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

import re

from labelpath.query import (
    DEFAULT_NEIGHBOR_LIMIT,
    DEFAULT_PATH_LIMIT,
    DISCLAIMER,
    friendly_label,
    hop_display_label,
    lookup,
    med_list_check,
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


def _highlight_snippet(snippet: Optional[str], matched_name: Optional[str]) -> str:
    text = snippet or ""
    needle = (matched_name or "").strip()
    if not text or not needle:
        return text
    pattern = re.compile(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", re.IGNORECASE)
    return pattern.sub(lambda match: "**" + match.group(0) + "**", text)


def _fmt_source(source: Optional[Dict[str, Any]], indent: str = "     ") -> List[str]:
    if not source:
        return []
    lines = []
    kind = source.get("kind")
    if kind:
        lines.append(indent + "Section: %s" % friendly_label(kind))
    snippet = _highlight_snippet(source.get("snippet"), source.get("matched_name"))
    if snippet:
        lines.append(indent + "Snippet: %s" % snippet)
    note = source.get("note")
    if note:
        lines.append(indent + note)
    url = source.get("source_url")
    set_id = source.get("set_id")
    if url:
        lines.append(indent + "DailyMed: %s" % url)
        lines.append(
            indent
            + "Label on DailyMed (current version may differ from the snapshot)."
        )
    elif set_id:
        lines.append(indent + "FDA label ID: %s" % set_id)
    return lines


def _fmt_cypher(result: Dict[str, Any]) -> List[str]:
    cypher = result.get("cypher") or {}
    statement = cypher.get("statement")
    if not statement:
        return []
    lines = ["", "Cypher:", statement]
    params = cypher.get("parameters")
    if params:
        lines.append("Parameters: %s" % json.dumps(params, ensure_ascii=False))
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
        note = result.get("no_path_note")
        if note and note not in (result.get("error") or ""):
            lines.append(note)
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
    if result.get("excluded_hubs") and not result.get("include_hubs"):
        names = ", ".join(item.get("name") or item.get("key") for item in result["excluded_hubs"])
        lines.append(
            "Generic hub conditions excluded by default (contraindicated in more than %s drugs): %s. "
            "Pass --include-hubs to include them."
            % (result.get("hub_condition_min_drugs"), names)
        )
    if not result.get("paths"):
        lines.append(result.get("error") or "No path found.")
        if result.get("no_path_note") and result.get("no_path_note") not in (result.get("error") or ""):
            lines.append(result["no_path_note"])
        return "\n".join(lines) + "\n"
    if not result.get("direct_mention_found"):
        lines.append("Neither endpoint label mentions the other directly.")
    for index, path in enumerate(result["paths"], start=1):
        nodes = path.get("nodes") or []
        steps = path.get("steps") or []
        if nodes:
            label = " -> ".join("%s" % (node.get("name") or node.get("key")) for node in nodes)
            headline = path.get("headline")
            lines.append("")
            header = "Path %s (%s hop(s)): %s" % (index, path.get("hops"), label)
            if headline:
                header += " — %s" % headline
            lines.append(header)
        if path.get("note") and result.get("direct_mention_found"):
            lines.append("  %s" % path["note"])
        for step_i, step in enumerate(steps, start=1):
            display = step.get("display_label") or hop_display_label(
                step.get("rel_type"),
                source_kinds=step.get("source_kinds"),
            )
            lines.append(
                "  %s. %s -[:%s]-> %s"
                % (step_i, step.get("from_key"), display, step.get("to_key"))
            )
            sources = step.get("sources") or ([step.get("source")] if step.get("source") else [])
            for source in sources:
                lines.extend(_fmt_source(source))
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
                item.get("display_label") or hop_display_label(item.get("rel_type"), source_kind=(item.get("source") or {}).get("kind")),
                neighbor.get("kind"),
                neighbor.get("key"),
                neighbor.get("name"),
            )
        else:
            desc = "%s %s (%s) -[:%s]-> %s" % (
                neighbor.get("kind"),
                neighbor.get("key"),
                neighbor.get("name"),
                item.get("display_label")
                or hop_display_label(
                    item.get("rel_type"),
                    source_kind=(item.get("source") or {}).get("kind"),
                ),
                drug.get("key"),
            )
        lines.append("  - " + desc)
        lines.extend(_fmt_source(item.get("source")))
    return "\n".join(lines) + "\n"


def format_med_list(result: Dict[str, Any]) -> str:
    lines = [DISCLAIMER, ""]
    drugs = result.get("drugs") or result.get("resolved") or []
    if drugs:
        lines.append(
            "Med-list check (%s drugs): %s"
            % (len(drugs), ", ".join(item.get("name") or item.get("key") for item in drugs))
        )
    if result.get("error") and not result.get("found"):
        lines.append(result["error"])
        for err in result.get("errors") or []:
            lines.append("  - %s: %s" % (err.get("query"), err.get("error")))
        return "\n".join(lines) + "\n"
    if not result.get("found"):
        lines.append(result.get("error") or "No label mentions among these drugs were found.")
        return "\n".join(lines) + "\n"
    for pair in result.get("pairs") or []:
        a = (pair.get("a") or {}).get("name") or (pair.get("a") or {}).get("key")
        b = (pair.get("b") or {}).get("name") or (pair.get("b") or {}).get("key")
        if pair.get("mutual"):
            kind = "mutual mentions"
        elif pair.get("one_sided"):
            kind = "one-sided mention"
        else:
            kind = "no mention in either direction"
        lines.append("")
        lines.append("%s — %s (%s)" % (a, b, kind))
        for direction, payload in (
            ("%s mentions %s" % (a, b), pair.get("a_mentions_b")),
            ("%s mentions %s" % (b, a), pair.get("b_mentions_a")),
        ):
            if not payload:
                continue
            lines.append("  %s:" % direction)
            for source in payload.get("sources") or []:
                lines.extend(_fmt_source(source, indent="    "))
    return "\n".join(lines) + "\n"


def _emit(result: Dict[str, Any], as_json: bool, formatter, show_cypher: bool = False) -> int:
    _print_disclaimer(as_json)
    if as_json:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        # formatter already includes the disclaimer as the first line
        text = formatter(result)
        if text.startswith(DISCLAIMER):
            text = text[len(DISCLAIMER) :].lstrip("\n")
        if show_cypher:
            extra = "\n".join(_fmt_cypher(result))
            if extra:
                if not text.endswith("\n"):
                    text += "\n"
                text += extra
                if not text.endswith("\n"):
                    text += "\n"
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
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
    query = sub.add_parser("query", help="Run a lookup, path, warnings, neighbors, or med-list query.")
    qsub = query.add_subparsers(dest="action", required=True)

    p_lookup = qsub.add_parser("lookup", help="Find a drug or ingredient by name.")
    p_lookup.add_argument("name")
    p_lookup.add_argument("--show-cypher", action="store_true")

    p_path = qsub.add_parser("path", help="Find bounded labeled paths between two names.")
    p_path.add_argument("start")
    p_path.add_argument("end")
    p_path.add_argument("--max-hops", type=int, default=3)
    p_path.add_argument("--limit", type=int, default=DEFAULT_PATH_LIMIT)
    p_path.add_argument(
        "--include-hubs",
        action="store_true",
        help="Include generic hub conditions (anaphylaxis, angioedema, asthma, and any other condition contraindicated in more than 10 drugs) in path search.",
    )
    p_path.add_argument(
        "--show-cypher",
        action="store_true",
        help="Print the parameterized Cypher statement that ran.",
    )

    p_warn = qsub.add_parser("warnings", help="Show boxed warnings and contraindications.")
    p_warn.add_argument("name")
    p_warn.add_argument("--show-cypher", action="store_true")

    p_nei = qsub.add_parser("neighbors", help="List labeled neighbors of a drug.")
    p_nei.add_argument("name")
    p_nei.add_argument("--limit", type=int, default=DEFAULT_NEIGHBOR_LIMIT)
    p_nei.add_argument("--show-cypher", action="store_true")

    p_med = qsub.add_parser(
        "med-list",
        help="Check every label mention among 2 to 6 drugs, in both directions.",
    )
    p_med.add_argument("names", nargs="+", help="Two to six drug names.")
    p_med.add_argument("--show-cypher", action="store_true")

    p_serve = sub.add_parser(
        "serve",
        help="Serve the local single-page UI on 127.0.0.1 only (read-only store).",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind on 127.0.0.1 (default: 8765).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.group == "serve":
        from labelpath.serve import run_server

        return run_server(port=args.port, database=args.database)
    if args.group != "query" or not args.action:
        parser.print_help()
        return 2
    database = args.database
    as_json = args.as_json
    try:
        show_cypher = bool(getattr(args, "show_cypher", False))
        if args.action == "lookup":
            result = lookup(args.name, database=database)
            return _emit(result, as_json, format_lookup, show_cypher)
        if args.action == "path":
            result = paths_between(
                args.start,
                args.end,
                max_hops=args.max_hops,
                database=database,
                limit=args.limit,
                include_hubs=bool(getattr(args, "include_hubs", False)),
            )
            return _emit(result, as_json, format_paths, show_cypher)
        if args.action == "warnings":
            result = warnings(args.name, database=database)
            return _emit(result, as_json, format_warnings, show_cypher)
        if args.action == "neighbors":
            result = neighbors(args.name, database=database, limit=args.limit)
            return _emit(result, as_json, format_neighbors, show_cypher)
        if args.action == "med-list":
            result = med_list_check(args.names, database=database)
            return _emit(result, as_json, format_med_list, show_cypher)
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
