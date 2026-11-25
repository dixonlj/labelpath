#!/usr/bin/env python3
"""Build data/labelpath.rl from the cached openFDA snapshot in data/raw/.

Offline. Replaces the store on each run so ingest is safe to repeat.
Python 3.9 compatible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import relate

from labelpath.paths import CONDITION_FILE, RAW_DIR, SEED_FILE, STORE_FILE
from labelpath.textutil import (
    alias_is_usable,
    core_name,
    find_mentions,
    first_mention_snippet,
    join_field,
    load_name_list,
    nonoverlapping_phrase_hits,
    normalize_name,
    unique_strings,
)

# Scan these sections for drug/ingredient mentions. indications_and_usage is
# used only for conservative INDICATED_FOR condition phrases, not interactions.
INTERACTION_KINDS = (
    "drug_interactions",
    "contraindications",
    "boxed_warning",
    "warnings_and_cautions",
)
SECTION_KINDS = INTERACTION_KINDS + ("indications_and_usage",)
DAILYMED_URL = "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}"


def load_snapshot() -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not RAW_DIR.is_dir():
        return items
    for path in sorted(RAW_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        record = data.get("record") if isinstance(data, dict) else None
        seed = data.get("seed") if isinstance(data, dict) else None
        if not record or not seed:
            print("Skipping %s (missing seed or record)" % path.name, file=sys.stderr)
            continue
        items.append({"seed": seed, "record": record, "file": path.name})
    return items


def source_url(set_id: Optional[str]) -> Optional[str]:
    if not set_id:
        return None
    return DAILYMED_URL.format(set_id=set_id)


def section_texts(record: Dict[str, Any]) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, str]] = []
    for kind in SECTION_KINDS:
        text = join_field(record.get(kind))
        if text:
            sections.append((kind, text))
    return sections


def drug_aliases(seed: str, record: Dict[str, Any]) -> List[str]:
    openfda = record.get("openfda") or {}
    aliases: List[str] = []
    for name in [seed] + unique_strings(openfda.get("generic_name") or []):
        aliases.append(name)
        core = core_name(name)
        if core and core != normalize_name(name):
            aliases.append(core)
    aliases.extend(unique_strings(openfda.get("brand_name") or []))
    usable = []
    seen = set()
    for name in aliases:
        if not alias_is_usable(name):
            continue
        key = normalize_name(name)
        if key in seen:
            continue
        seen.add(key)
        usable.append(name)
    # Longer aliases first so "warfarin sodium" wins over "warfarin" overlaps
    # at the mention-filter stage.
    usable.sort(key=lambda name: len(normalize_name(name)), reverse=True)
    return usable


def add_count(counter: Dict[str, int], key: str, amount: int = 1) -> None:
    counter[key] = counter.get(key, 0) + amount


def execute(conn: Any, statement: str, params: Optional[Dict[str, Any]] = None) -> None:
    conn.execute(statement, params or {})


def ingest(snapshot: Sequence[Dict[str, Any]], condition_phrases: Sequence[str]) -> Dict[str, Dict[str, int]]:
    if STORE_FILE.exists():
        STORE_FILE.unlink()
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)

    node_counts: Dict[str, int] = {}
    rel_counts: Dict[str, int] = {}
    created_drugs: Set[str] = set()
    created_ingredients: Set[str] = set()
    created_conditions: Set[str] = set()
    created_labels: Set[str] = set()
    # (from_key, to_kind, to_key, source_set_id, kind)
    created_interactions: Set[Tuple[str, str, str, str, str]] = set()
    created_indicated: Set[Tuple[str, str]] = set()
    created_contraindicated: Set[Tuple[str, str]] = set()
    contains_pairs: Set[Tuple[str, str]] = set()

    # Catalog for mention matching: drugs and ingredients in this snapshot only.
    drug_catalog: List[Dict[str, Any]] = []
    ingredient_catalog: List[Dict[str, Any]] = []
    drug_own_ingredients: Dict[str, Set[str]] = {}

    prepared: List[Dict[str, Any]] = []
    for item in snapshot:
        seed = item["seed"]
        record = item["record"]
        drug_key = normalize_name(seed)
        if not drug_key:
            continue
        openfda = record.get("openfda") or {}
        generics = unique_strings(openfda.get("generic_name") or [])
        brands = unique_strings(openfda.get("brand_name") or [])
        substances = unique_strings(openfda.get("substance_name") or [])
        applications = unique_strings(openfda.get("application_number") or [])
        generic_name = generics[0] if generics else seed
        set_id = record.get("set_id")
        if not set_id:
            print("Skipping %s: no set_id" % seed, file=sys.stderr)
            continue
        own_ing: Set[str] = set()
        for substance in substances:
            ing_key = normalize_name(substance)
            if not ing_key or not alias_is_usable(substance):
                # Still store the ingredient node if the name is specific enough
                # after normalize, even if we will not use it as a matcher.
                if not ing_key:
                    continue
            own_ing.add(ing_key)
            ingredient_catalog.append(
                {
                    "key": ing_key,
                    "name": substance,
                    "aliases": [substance] if alias_is_usable(substance) else [],
                }
            )
        drug_own_ingredients[drug_key] = own_ing
        drug_catalog.append(
            {
                "key": drug_key,
                "aliases": drug_aliases(seed, record),
            }
        )
        prepared.append(
            {
                "seed": seed,
                "drug_key": drug_key,
                "generic_name": generic_name,
                "brand_names": brands,
                "application_numbers": applications,
                "substances": substances,
                "set_id": set_id,
                "effective_time": record.get("effective_time") or "",
                "source_url": source_url(set_id),
                "sections": section_texts(record),
            }
        )

    conn = relate.connect(str(STORE_FILE))
    try:
        conn.autocommit = False
        for row in prepared:
            if row["drug_key"] not in created_drugs:
                execute(
                    conn,
                    "CREATE (d:Drug {key: $key, generic_name: $generic_name, "
                    "brand_names: $brand_names, application_numbers: $application_numbers})",
                    {
                        "key": row["drug_key"],
                        "generic_name": row["generic_name"],
                        "brand_names": row["brand_names"],
                        "application_numbers": row["application_numbers"],
                    },
                )
                created_drugs.add(row["drug_key"])
                add_count(node_counts, "Drug")
            if row["set_id"] not in created_labels:
                execute(
                    conn,
                    "CREATE (l:Label {set_id: $set_id, effective_time: $effective_time, "
                    "source_url: $source_url})",
                    {
                        "set_id": row["set_id"],
                        "effective_time": row["effective_time"],
                        "source_url": row["source_url"],
                    },
                )
                created_labels.add(row["set_id"])
                add_count(node_counts, "Label")
            execute(
                conn,
                "MATCH (d:Drug {key: $key}), (l:Label {set_id: $set_id}) "
                "CREATE (d)-[:HAS_LABEL]->(l)",
                {"key": row["drug_key"], "set_id": row["set_id"]},
            )
            add_count(rel_counts, "HAS_LABEL")
            for kind, text in row["sections"]:
                execute(
                    conn,
                    "MATCH (l:Label {set_id: $set_id}) "
                    "CREATE (l)-[:HAS_SECTION {kind: $kind}]->"
                    "(:Section {kind: $kind, text: $text})",
                    {"set_id": row["set_id"], "kind": kind, "text": text},
                )
                add_count(node_counts, "Section")
                add_count(rel_counts, "HAS_SECTION")
            for substance in row["substances"]:
                ing_key = normalize_name(substance)
                if not ing_key:
                    continue
                if ing_key not in created_ingredients:
                    execute(
                        conn,
                        "CREATE (i:Ingredient {key: $key, name: $name})",
                        {"key": ing_key, "name": substance},
                    )
                    created_ingredients.add(ing_key)
                    add_count(node_counts, "Ingredient")
                pair = (row["drug_key"], ing_key)
                if pair not in contains_pairs:
                    execute(
                        conn,
                        "MATCH (d:Drug {key: $drug}), (i:Ingredient {key: $ing}) "
                        "CREATE (d)-[:CONTAINS]->(i)",
                        {"drug": row["drug_key"], "ing": ing_key},
                    )
                    contains_pairs.add(pair)
                    add_count(rel_counts, "CONTAINS")

        # Build mention index: unique drugs by key, ingredients by key.
        drugs_by_key: Dict[str, Dict[str, Any]] = {}
        for entry in drug_catalog:
            drugs_by_key.setdefault(entry["key"], entry)
        ings_by_key: Dict[str, Dict[str, Any]] = {}
        for entry in ingredient_catalog:
            ings_by_key.setdefault(entry["key"], entry)

        mention_targets: List[Tuple[str, str, str, List[str]]] = []
        for key, entry in drugs_by_key.items():
            mention_targets.append(("Drug", key, key, entry["aliases"]))
        for key, entry in ings_by_key.items():
            aliases = entry["aliases"]
            if aliases:
                mention_targets.append(("Ingredient", key, entry["name"], aliases))

        def mention_hits(text: str) -> List[Tuple[str, str, str, str]]:
            """Return non-overlapping (kind, key, matched_alias, snippet) hits."""
            scored: List[Tuple[int, int, int, str, str, str, str]] = []
            for kind, key, _label, aliases in mention_targets:
                for alias in aliases:
                    snippet = first_mention_snippet(text, alias)
                    if snippet is None:
                        continue
                    spans = find_mentions(text, alias)
                    if not spans:
                        continue
                    start, end = spans[0]
                    scored.append((start, -(end - start), end, kind, key, alias, snippet))
                    break
            scored.sort()
            used_ranges: List[Tuple[int, int]] = []
            hits: List[Tuple[str, str, str, str]] = []
            for start, neg_len, end, kind, key, alias, snippet in scored:
                if any(not (end <= lo or start >= hi) for lo, hi in used_ranges):
                    continue
                used_ranges.append((start, end))
                hits.append((kind, key, alias, snippet))
            return hits

        for row in prepared:
            for kind, text in row["sections"]:
                if kind == "indications_and_usage":
                    for phrase, snippet in nonoverlapping_phrase_hits(text, condition_phrases):
                        cond_key = normalize_name(phrase)
                        if cond_key not in created_conditions:
                            execute(
                                conn,
                                "CREATE (c:Condition {key: $key, name: $name})",
                                {"key": cond_key, "name": phrase},
                            )
                            created_conditions.add(cond_key)
                            add_count(node_counts, "Condition")
                        pair = (row["drug_key"], cond_key)
                        if pair in created_indicated:
                            continue
                        execute(
                            conn,
                            "MATCH (d:Drug {key: $drug}), (c:Condition {key: $cond}) "
                            "CREATE (d)-[:INDICATED_FOR {source_set_id: $set_id, "
                            "source_kind: $kind, summary: $summary}]->(c)",
                            {
                                "drug": row["drug_key"],
                                "cond": cond_key,
                                "set_id": row["set_id"],
                                "kind": kind,
                                "summary": snippet,
                            },
                        )
                        created_indicated.add(pair)
                        add_count(rel_counts, "INDICATED_FOR")
                    continue

                if kind == "contraindications":
                    for phrase, snippet in nonoverlapping_phrase_hits(text, condition_phrases):
                        cond_key = normalize_name(phrase)
                        if cond_key not in created_conditions:
                            execute(
                                conn,
                                "CREATE (c:Condition {key: $key, name: $name})",
                                {"key": cond_key, "name": phrase},
                            )
                            created_conditions.add(cond_key)
                            add_count(node_counts, "Condition")
                        pair = (row["drug_key"], cond_key)
                        if pair in created_contraindicated:
                            continue
                        execute(
                            conn,
                            "MATCH (d:Drug {key: $drug}), (c:Condition {key: $cond}) "
                            "CREATE (d)-[:CONTRAINDICATED_IN {source_set_id: $set_id, "
                            "source_kind: $kind, summary: $summary}]->(c)",
                            {
                                "drug": row["drug_key"],
                                "cond": cond_key,
                                "set_id": row["set_id"],
                                "kind": kind,
                                "summary": snippet,
                            },
                        )
                        created_contraindicated.add(pair)
                        add_count(rel_counts, "CONTRAINDICATED_IN")

                if kind not in INTERACTION_KINDS:
                    continue
                for target_kind, target_key, alias, snippet in mention_hits(text):
                    if target_kind == "Drug" and target_key == row["drug_key"]:
                        continue
                    if target_kind == "Ingredient" and target_key in drug_own_ingredients.get(
                        row["drug_key"], set()
                    ):
                        continue
                    stamp = (row["drug_key"], target_kind, target_key, row["set_id"], kind)
                    if stamp in created_interactions:
                        continue
                    if target_kind == "Drug":
                        execute(
                            conn,
                            "MATCH (a:Drug {key: $src}), (b:Drug {key: $dst}) "
                            "CREATE (a)-[:LABELED_INTERACTION {summary: $summary, "
                            "source_set_id: $set_id, source_kind: $kind, "
                            "matched_name: $matched}]->(b)",
                            {
                                "src": row["drug_key"],
                                "dst": target_key,
                                "summary": snippet,
                                "set_id": row["set_id"],
                                "kind": kind,
                                "matched": alias,
                            },
                        )
                    else:
                        execute(
                            conn,
                            "MATCH (a:Drug {key: $src}), (b:Ingredient {key: $dst}) "
                            "CREATE (a)-[:LABELED_INTERACTION {summary: $summary, "
                            "source_set_id: $set_id, source_kind: $kind, "
                            "matched_name: $matched}]->(b)",
                            {
                                "src": row["drug_key"],
                                "dst": target_key,
                                "summary": snippet,
                                "set_id": row["set_id"],
                                "kind": kind,
                                "matched": alias,
                            },
                        )
                    created_interactions.add(stamp)
                    add_count(rel_counts, "LABELED_INTERACTION")

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return {"nodes": node_counts, "relationships": rel_counts}


def print_counts(counts: Dict[str, Dict[str, int]]) -> None:
    print("Node counts:")
    for key in sorted(counts["nodes"]):
        print("  %s: %s" % (key, counts["nodes"][key]))
    print("Relationship counts:")
    for key in sorted(counts["relationships"]):
        print("  %s: %s" % (key, counts["relationships"][key]))
    print("  nodes_total: %s" % sum(counts["nodes"].values()))
    print("  relationships_total: %s" % sum(counts["relationships"].values()))


def verify_with_read() -> None:
    reader = relate.connect(str(STORE_FILE), read_only=True)
    try:
        for label, prop in (
            ("Drug", "key"),
            ("Ingredient", "key"),
            ("Condition", "key"),
            ("Label", "set_id"),
            ("Section", "kind"),
        ):
            n = reader.execute(
                "MATCH (n:%s) RETURN count(n) AS n" % label
            ).single()["n"]
            print("store %s: %s" % (label, n))
        for rel in (
            "HAS_LABEL",
            "HAS_SECTION",
            "CONTAINS",
            "INDICATED_FOR",
            "CONTRAINDICATED_IN",
            "LABELED_INTERACTION",
        ):
            n = reader.execute(
                "MATCH ()-[r:%s]->() RETURN count(r) AS n" % rel
            ).single()["n"]
            print("store %s: %s" % (rel, n))
    finally:
        reader.close()


def main() -> int:
    seeds = load_name_list(SEED_FILE)
    snapshot = load_snapshot()
    condition_phrases = load_name_list(CONDITION_FILE)
    if not snapshot:
        print("No cached labels in %s. Run scripts/download_snapshot.py first." % RAW_DIR, file=sys.stderr)
        return 1
    print(
        "Ingesting %s cached labels (%s seeds listed) into %s"
        % (len(snapshot), len(seeds), STORE_FILE)
    )
    counts = ingest(snapshot, condition_phrases)
    print_counts(counts)
    print("Verifying read-only reopen...")
    verify_with_read()
    size = STORE_FILE.stat().st_size if STORE_FILE.is_file() else 0
    print("Store written: %s (%s bytes)" % (STORE_FILE, size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
