"""Read-only LabelPath queries. Compatible with Python 3.9."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from labelpath.paths import STORE_FILE
from labelpath.textutil import core_name, generic_matches_seed, normalize_name

DISCLAIMER = "Educational only, not medical advice."
DEFAULT_PATH_LIMIT = 20
DEFAULT_NEIGHBOR_LIMIT = 50
MAX_HOPS_CAP = 3
PATH_REL_TYPES = (
    "LABELED_INTERACTION",
    "CONTAINS",
    "INDICATED_FOR",
    "CONTRAINDICATED_IN",
)
# Sanitized integer hop bounds only (never raw user text) are interpolated below.
_PATH_REL_PATTERN = "|".join(PATH_REL_TYPES)

# Display-only labels. Graph/API keys stay in PATH_REL_TYPES and source.kind.
FRIENDLY_LABELS = {
    "LABELED_INTERACTION": "Mentions",
    "CONTAINS": "Contains",
    "INDICATED_FOR": "Indicated for",
    "CONTRAINDICATED_IN": "Contraindicated in",
    "drug_interactions": "Drug interactions",
    "boxed_warning": "Boxed warning",
    "warnings_and_cautions": "Warnings and cautions",
    "contraindications": "Contraindications",
    "indications_and_usage": "Indications and usage",
    "adverse_reactions": "Adverse reactions",
}

# Conditions linked by CONTRAINDICATED_IN to more than this many distinct
# drugs are treated as generic hubs and omitted from path search by default.
HUB_CONDITION_MIN_DRUGS = 10

# Retrieved date stored on the committed snapshot (data/raw/manifest.json).
SNAPSHOT_DATE = "19 November 2026"
SNAPSHOT_TZ = "America/New_York"
SNAPSHOT_DRUG_COUNT = 293  # verified against the store; also queried at runtime

NO_PATH_NOTE = (
    "No path in this snapshot does not mean the drugs are safe together. "
    "The snapshot covers %s drugs, matches exact names only, and misses "
    "class mentions such as 'anticoagulants'."
)

DAILYMED_LINK_NOTE = (
    "Label on DailyMed (current version may differ from the snapshot)"
)


def friendly_label(value) -> str:
    """Turn a raw relationship or section name into a short display label."""
    raw = "" if value is None else str(value)
    if not raw:
        return ""
    if raw in FRIENDLY_LABELS:
        return FRIENDLY_LABELS[raw]
    spaced = " ".join(raw.replace("_", " ").split())
    if not spaced:
        return ""
    return spaced[0].upper() + spaced[1:].lower()


def hop_display_label(rel_type, source_kind=None, source_kinds=None) -> str:
    """Arrow text: 'Mentions · Drug interactions'."""
    rel = friendly_label(rel_type)
    kinds = []
    if source_kinds:
        for kind in source_kinds:
            label = friendly_label(kind)
            if label and label not in kinds:
                kinds.append(label)
    elif source_kind:
        label = friendly_label(source_kind)
        if label:
            kinds.append(label)
    if kinds:
        return rel + " · " + " · ".join(kinds)
    return rel


def _cypher_payload(statement: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    return {"statement": statement, "parameters": parameters}


def hub_conditions(conn: Any) -> List[Dict[str, Any]]:
    """Condition nodes contraindicated in more than HUB_CONDITION_MIN_DRUGS drugs."""
    rows = conn.execute(
        "MATCH (d:Drug)-[:CONTRAINDICATED_IN]->(c:Condition) "
        "RETURN c.key AS key, c.name AS name, count(DISTINCT d) AS drug_count "
        "ORDER BY drug_count DESC, key ASC"
    ).fetchall()
    hubs = []
    for row in rows:
        count = int(row["drug_count"] or 0)
        if count > HUB_CONDITION_MIN_DRUGS:
            hubs.append(
                {
                    "key": row["key"],
                    "name": row["name"] or row["key"],
                    "drug_count": count,
                }
            )
    return hubs


def snapshot_stats(conn: Any) -> Dict[str, Any]:
    """Counts and mention-pair facts, all read from the store."""
    drug_count = conn.execute("MATCH (d:Drug) RETURN count(d) AS n").fetchone()["n"]
    directed = conn.execute(
        "MATCH (a:Drug)-[:LABELED_INTERACTION]->(b:Drug) "
        "RETURN DISTINCT a.key AS a, b.key AS b"
    ).fetchall()
    outgoing = {}
    undirected = set()
    for row in directed:
        a, b = row["a"], row["b"]
        outgoing.setdefault(a, set()).add(b)
        undirected.add(tuple(sorted((a, b))))
    mutual = [
        (a, b) for a, b in sorted(undirected) if b in outgoing.get(a, set()) and a in outgoing.get(b, set())
    ]
    top = conn.execute(
        "MATCH (a:Drug)-[:LABELED_INTERACTION]->(b:Drug) "
        "RETURN b.key AS key, b.generic_name AS name, count(DISTINCT a) AS n "
        "ORDER BY n DESC, key ASC "
        "LIMIT 5"
    ).fetchall()
    hubs = hub_conditions(conn)
    return {
        "disclaimer": DISCLAIMER,
        "snapshot_date": SNAPSHOT_DATE,
        "snapshot_timezone": SNAPSHOT_TZ,
        "drug_count": int(drug_count),
        "mention_linked_pairs": len(undirected),
        "mutual_mention_pairs": len(mutual),
        "one_sided_mention_pairs": len(undirected) - len(mutual),
        "directed_mention_pairs": len(directed),
        "most_mentioned": [
            {"key": row["key"], "name": row["name"], "named_by": int(row["n"])} for row in top
        ],
        "hub_condition_min_drugs": HUB_CONDITION_MIN_DRUGS,
        "hub_conditions": hubs,
        "dailymed_link_note": DAILYMED_LINK_NOTE,
        "no_path_note": NO_PATH_NOTE % int(drug_count),
    }

# CONTAINS edges come from the structured openFDA substance list, not a section.
CONTAINS_SOURCE_NOTE = (
    "Structured openFDA substance_name field on the source drug; "
    "no label-section snippet."
)


def open_store(database=None, conn=None):
    """Return (connection, close_when_done). Opens the store read-only."""
    if conn is not None:
        return conn, False
    import relate

    path = str(database or STORE_FILE)
    return relate.connect(path, read_only=True), True


def _display_name(row: Dict[str, Any]) -> str:
    return row.get("generic_name") or row.get("name") or row.get("key") or ""


def _score_name(query: str, key: str, official: str, brands: Optional[Sequence[str]] = None) -> int:
    qn = normalize_name(query)
    if not qn:
        return 0
    kn = normalize_name(key) if key else ""
    on = normalize_name(official) if official else ""
    if kn and kn == qn:
        return 100
    if on and on == qn:
        return 95
    if official and (
        generic_matches_seed(official, query) or generic_matches_seed(query, official)
    ):
        return 90
    if key and (generic_matches_seed(key, query) or generic_matches_seed(query, key)):
        return 88
    qc = core_name(query)
    oc = core_name(official or key or "")
    if qc and oc and qc == oc:
        return 86
    for brand in brands or []:
        bn = normalize_name(brand)
        if bn and bn == qn:
            return 80
    return 0


def _load_catalog(conn: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    drugs = [
        dict(row)
        for row in conn.execute(
            "MATCH (d:Drug) "
            "RETURN d.key AS key, d.generic_name AS generic_name, "
            "d.brand_names AS brand_names, d.application_numbers AS application_numbers "
            "ORDER BY d.key "
            "LIMIT 1000"
        ).fetchall()
    ]
    ingredients = [
        dict(row)
        for row in conn.execute(
            "MATCH (i:Ingredient) "
            "RETURN i.key AS key, i.name AS name "
            "ORDER BY i.key "
            "LIMIT 1000"
        ).fetchall()
    ]
    return drugs, ingredients


def _matches_from_catalog(
    query: str,
    drugs: Sequence[Dict[str, Any]],
    ingredients: Sequence[Dict[str, Any]],
    min_score: int = 80,
) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for drug in drugs:
        score = _score_name(
            query,
            drug.get("key") or "",
            drug.get("generic_name") or "",
            drug.get("brand_names") or [],
        )
        if score >= min_score:
            item = dict(drug)
            item["kind"] = "Drug"
            item["score"] = score
            hits.append(item)
    for ingredient in ingredients:
        score = _score_name(
            query,
            ingredient.get("key") or "",
            ingredient.get("name") or "",
            None,
        )
        if score >= min_score:
            item = dict(ingredient)
            item["kind"] = "Ingredient"
            item["score"] = score
            hits.append(item)
    hits.sort(key=lambda item: (-item["score"], item["kind"], item["key"]))
    return hits


def _best_unique(
    matches: Sequence[Dict[str, Any]], prefer_drug: bool = False
) -> Optional[Dict[str, Any]]:
    if not matches:
        return None
    if prefer_drug:
        drugs = [item for item in matches if item["kind"] == "Drug"]
        if drugs:
            top = drugs[0]["score"]
            best_drugs = [item for item in drugs if item["score"] == top]
            if len(best_drugs) == 1:
                return best_drugs[0]
            return None
    top = matches[0]["score"]
    best = [item for item in matches if item["score"] == top]
    if len(best) == 1:
        return best[0]
    drugs = [item for item in best if item["kind"] == "Drug"]
    ings = [item for item in best if item["kind"] == "Ingredient"]
    if len(drugs) == 1 and len(best) == len(drugs) + len(ings):
        return drugs[0]
    return None


def _label_map(conn: Any, set_ids: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    ids = []
    seen = set()
    for set_id in set_ids:
        if not set_id or set_id in seen:
            continue
        seen.add(set_id)
        ids.append(set_id)
    if not ids:
        return {}
    rows = conn.execute(
        "MATCH (l:Label) WHERE l.set_id IN $ids "
        "RETURN l.set_id AS set_id, l.source_url AS source_url, "
        "l.effective_time AS effective_time "
        "LIMIT 1000",
        {"ids": ids},
    ).fetchall()
    return {row["set_id"]: dict(row) for row in rows}


def _source_fields(
    source_kind: Optional[str],
    source_set_id: Optional[str],
    summary: Optional[str],
    labels: Dict[str, Dict[str, Any]],
    rel_type: str,
    matched_name: Optional[str] = None,
) -> Dict[str, Any]:
    info = labels.get(source_set_id or "", {})
    source = {
        "kind": source_kind,
        "set_id": source_set_id,
        "source_url": info.get("source_url"),
        "effective_time": info.get("effective_time"),
        "snippet": summary,
        "matched_name": matched_name,
    }
    if rel_type == "CONTAINS" and not source_kind and not summary:
        source["note"] = CONTAINS_SOURCE_NOTE
    return source


def lookup(name: str, conn: Any = None, database=None) -> Dict[str, Any]:
    """Find a drug or ingredient by name (case-insensitive, salt-tolerant)."""
    connection, close = open_store(database=database, conn=conn)
    try:
        drugs, ingredients = _load_catalog(connection)
        matches = _matches_from_catalog(name, drugs, ingredients)
        catalog_cypher = (
            "MATCH (d:Drug) "
            "RETURN d.key AS key, d.generic_name AS generic_name, "
            "d.brand_names AS brand_names, d.application_numbers AS application_numbers "
            "ORDER BY d.key "
            "LIMIT 1000"
        )
        return {
            "disclaimer": DISCLAIMER,
            "query": name,
            "matches": matches,
            "found": bool(matches),
            "cypher": _cypher_payload(catalog_cypher, {}),
        }
    finally:
        if close:
            connection.close()


def _resolve_required(
    name: str, conn: Any, role: str, prefer_drug: bool = True
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    drugs, ingredients = _load_catalog(conn)
    matches = _matches_from_catalog(name, drugs, ingredients)
    best = _best_unique(matches, prefer_drug=prefer_drug)
    if not matches:
        return None, matches, "No %s named %r was found in this snapshot." % (role, name)
    if best is None:
        return (
            None,
            matches,
            "The name %r is ambiguous in this snapshot; use a more specific generic name."
            % name,
        )
    return best, matches, None


def paths_between(
    a: str,
    b: str,
    max_hops: int = 3,
    conn: Any = None,
    database=None,
    limit: int = DEFAULT_PATH_LIMIT,
    include_hubs: bool = False,
) -> Dict[str, Any]:
    """Bounded labeled paths between two snapshot drugs or ingredients."""
    hops = int(max_hops)
    if hops < 1:
        hops = 1
    if hops > MAX_HOPS_CAP:
        hops = MAX_HOPS_CAP
    cap = int(limit)
    if cap < 1:
        cap = 1
    if cap > 100:
        cap = 100

    connection, close = open_store(database=database, conn=conn)
    try:
        start, start_matches, start_error = _resolve_required(a, connection, "start")
        end, end_matches, end_error = _resolve_required(b, connection, "end")
        drug_count = connection.execute("MATCH (d:Drug) RETURN count(d) AS n").fetchone()["n"]
        no_path_note = NO_PATH_NOTE % int(drug_count)
        hubs = [] if include_hubs else hub_conditions(connection)
        hub_keys = [item["key"] for item in hubs]
        result = {
            "disclaimer": DISCLAIMER,
            "start_query": a,
            "end_query": b,
            "max_hops": hops,
            "include_hubs": include_hubs,
            "excluded_hubs": hubs,
            "hub_condition_min_drugs": HUB_CONDITION_MIN_DRUGS,
            "start": start,
            "end": end,
            "paths": [],
            "found": False,
            "direct_mention_found": False,
            "no_path_note": no_path_note,
            "snapshot_date": SNAPSHOT_DATE,
            "snapshot_timezone": SNAPSHOT_TZ,
            "drug_count": int(drug_count),
        }
        if start_error:
            result["error"] = start_error
            result["start_matches"] = start_matches
            return result
        if end_error:
            result["error"] = end_error
            result["end_matches"] = end_matches
            return result
        assert start is not None and end is not None
        if start["kind"] == end["kind"] and start["key"] == end["key"]:
            result["error"] = "The start and end resolve to the same snapshot node."
            return result

        fetch_cap = cap * 8
        if fetch_cap < 80:
            fetch_cap = 80
        if fetch_cap > 200:
            fetch_cap = 200

        hub_clause = ""
        if hub_keys:
            hub_clause = (
                "AND ALL(n IN ns WHERE NOT (n:Condition AND n.key IN $hub_keys)) "
            )

        statement = (
            "MATCH (start {key: $start_key}), (finish {key: $end_key}) "
            "WHERE $start_label IN labels(start) AND $end_label IN labels(finish) "
            "MATCH p = (start)-[:%s*1..%d]-(finish) "
            "WITH p, nodes(p) AS ns "
            "WHERE ALL(n IN ns WHERE size([m IN ns WHERE m = n]) = 1) "
            "%s"
            "RETURN length(p) AS hops, "
            "[n IN nodes(p) | n.key] AS keys, "
            "[n IN nodes(p) | labels(n)[0]] AS node_kinds, "
            "[n IN nodes(p) | coalesce(n.generic_name, n.name, n.key)] AS names, "
            "[r IN relationships(p) | type(r)] AS rel_types, "
            "[r IN relationships(p) | r.summary] AS summaries, "
            "[r IN relationships(p) | r.source_kind] AS source_kinds, "
            "[r IN relationships(p) | r.source_set_id] AS source_set_ids, "
            "[r IN relationships(p) | r.matched_name] AS matched_names, "
            "[r IN relationships(p) | startNode(r).key] AS rel_starts, "
            "[r IN relationships(p) | endNode(r).key] AS rel_ends "
            "ORDER BY length(p) ASC "
            "LIMIT $fetch_limit"
        ) % (_PATH_REL_PATTERN, hops, hub_clause)

        parameters = {
            "start_key": start["key"],
            "end_key": end["key"],
            "start_label": start["kind"],
            "end_label": end["kind"],
            "fetch_limit": fetch_cap,
        }
        if hub_keys:
            parameters["hub_keys"] = hub_keys
        result["cypher"] = _cypher_payload(statement, parameters)

        rows = connection.execute(statement, parameters).fetchall()

        set_ids: List[str] = []
        for row in rows:
            set_ids.extend([item for item in (row["source_set_ids"] or []) if item])
        labels = _label_map(connection, set_ids)

        raw_paths = []
        for row in rows:
            steps = []
            rel_types = row["rel_types"] or []
            matched_names = row["matched_names"] or []
            for index, rel_type in enumerate(rel_types):
                source = _source_fields(
                    (row["source_kinds"] or [None])[index],
                    (row["source_set_ids"] or [None])[index],
                    (row["summaries"] or [None])[index],
                    labels,
                    rel_type,
                    matched_names[index] if index < len(matched_names) else None,
                )
                steps.append(
                    {
                        "from_key": (row["rel_starts"] or [None])[index],
                        "to_key": (row["rel_ends"] or [None])[index],
                        "rel_type": rel_type,
                        "source": source,
                    }
                )
            nodes = []
            keys = row["keys"] or []
            kinds = row["node_kinds"] or []
            names = row["names"] or []
            for index, key in enumerate(keys):
                nodes.append(
                    {
                        "key": key,
                        "kind": kinds[index] if index < len(kinds) else None,
                        "name": names[index] if index < len(names) else key,
                    }
                )
            raw_paths.append({"hops": row["hops"], "nodes": nodes, "steps": steps})

        paths, direct = _group_and_annotate_paths(raw_paths, cap)
        result["paths"] = paths
        result["found"] = bool(paths)
        result["direct_mention_found"] = direct
        if not paths:
            result["error"] = (
                "No labeled path of at most %s hop(s) was found between %s and %s "
                "in this snapshot. %s"
                % (hops, start["key"], end["key"], no_path_note)
            )
        return result
    finally:
        if close:
            connection.close()


def _source_signature(source: Optional[Dict[str, Any]]) -> Tuple:
    src = source or {}
    return (src.get("kind"), src.get("set_id"), src.get("snippet"), src.get("matched_name"))


def _group_and_annotate_paths(
    raw_paths: List[Dict[str, Any]], cap: int
) -> Tuple[List[Dict[str, Any]], bool]:
    """Collapse identical node routes; keep every distinct source snippet."""
    groups: Dict[Tuple[str, ...], Dict[str, Any]] = {}
    order: List[Tuple[str, ...]] = []
    for path in raw_paths:
        route = tuple(node["key"] for node in path["nodes"])
        if route not in groups:
            grouped_steps = []
            for step in path["steps"]:
                source = step.get("source")
                grouped_steps.append(
                    {
                        "from_key": step.get("from_key"),
                        "to_key": step.get("to_key"),
                        "rel_type": step.get("rel_type"),
                        "rel_types": [step.get("rel_type")],
                        "source": source,
                        "sources": [source] if source is not None else [],
                    }
                )
            groups[route] = {
                "hops": path["hops"],
                "nodes": path["nodes"],
                "steps": grouped_steps,
            }
            order.append(route)
            continue
        existing = groups[route]
        for index, step in enumerate(path["steps"]):
            if index >= len(existing["steps"]):
                break
            estep = existing["steps"][index]
            rel_type = step.get("rel_type")
            if rel_type and rel_type not in estep["rel_types"]:
                estep["rel_types"].append(rel_type)
            source = step.get("source")
            if source is None:
                continue
            sigs = [_source_signature(item) for item in estep["sources"]]
            if _source_signature(source) not in sigs:
                estep["sources"].append(source)
                if estep.get("source") is None:
                    estep["source"] = source

    has_direct = False
    annotated = []
    for route in order:
        path = groups[route]
        for step in path["steps"]:
            kinds = []
            for source in step["sources"]:
                kind = (source or {}).get("kind")
                if kind and kind not in kinds:
                    kinds.append(kind)
            step["source_kinds"] = kinds
            step["display_label"] = hop_display_label(
                step["rel_type"], source_kinds=kinds
            )
        intermediates = path["nodes"][1:-1]
        path["connected_through"] = [
            node.get("name") or node.get("key") for node in intermediates
        ]
        all_mentions = all(
            step.get("rel_type") == "LABELED_INTERACTION" for step in path["steps"]
        )
        path["all_mentions"] = all_mentions
        path["direct_mention"] = path["hops"] == 1 and all_mentions
        if path["direct_mention"]:
            has_direct = True
            path["headline"] = "Direct mention"
        elif path["connected_through"]:
            path["headline"] = "Connected through " + ", ".join(path["connected_through"])
        else:
            path["headline"] = ""
        annotated.append(path)

    for path in annotated:
        if path["direct_mention"]:
            path["neither_endpoint_mentions_the_other"] = False
        else:
            path["neither_endpoint_mentions_the_other"] = not has_direct
            if not has_direct:
                path["note"] = (
                    "Neither endpoint label mentions the other directly."
                )

    def rank(path: Dict[str, Any]) -> Tuple:
        if path.get("direct_mention"):
            cls = 0
        elif path.get("all_mentions"):
            cls = 1
        else:
            cls = 2
        keys = tuple(node["key"] for node in path["nodes"])
        return (cls, path["hops"], keys)

    annotated.sort(key=rank)
    return annotated[:cap], has_direct


def _drug_or_error(name: str, conn: Any) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    entity, matches, error = _resolve_required(name, conn, "drug")
    base = {
        "disclaimer": DISCLAIMER,
        "query": name,
        "matches": matches,
    }
    if error:
        base["found"] = False
        base["error"] = error
        return None, base
    assert entity is not None
    if entity["kind"] != "Drug":
        base["found"] = False
        base["error"] = (
            "%r resolved to an Ingredient (%s), not a Drug, in this snapshot."
            % (name, entity["key"])
        )
        return None, base
    base["drug"] = entity
    base["found"] = True
    return entity, base


def warnings(drug_name: str, conn: Any = None, database=None) -> Dict[str, Any]:
    """Boxed warning and contraindication sections, plus contraindicated conditions."""
    connection, close = open_store(database=database, conn=conn)
    try:
        drug, result = _drug_or_error(drug_name, connection)
        if drug is None:
            return result
        section_rows = connection.execute(
            "MATCH (d:Drug {key: $key})-[:HAS_LABEL]->(l:Label)-[:HAS_SECTION]->(s:Section) "
            "WHERE s.kind IN $kinds "
            "RETURN s.kind AS kind, s.text AS text, l.set_id AS set_id, "
            "l.source_url AS source_url, l.effective_time AS effective_time "
            "ORDER BY s.kind "
            "LIMIT 20",
            {
                "key": drug["key"],
                "kinds": ["boxed_warning", "contraindications"],
            },
        ).fetchall()
        condition_rows = connection.execute(
            "MATCH (d:Drug {key: $key})-[r:CONTRAINDICATED_IN]->(c:Condition) "
            "RETURN c.key AS key, c.name AS name, r.summary AS summary, "
            "r.source_kind AS source_kind, r.source_set_id AS source_set_id "
            "ORDER BY c.key "
            "LIMIT 100",
            {"key": drug["key"]},
        ).fetchall()
        labels = _label_map(
            connection,
            [row["source_set_id"] for row in condition_rows],
        )

        def clip(text: Optional[str], length: int = 400) -> Optional[str]:
            if not text:
                return text
            compact = " ".join(text.split())
            if len(compact) <= length:
                return compact
            return compact[: length - 3].rstrip() + "..."

        boxed = []
        contra_sections = []
        for row in section_rows:
            item = {
                "kind": row["kind"],
                "set_id": row["set_id"],
                "source_url": row["source_url"],
                "effective_time": row["effective_time"],
                "snippet": clip(row["text"]),
            }
            if row["kind"] == "boxed_warning":
                boxed.append(item)
            else:
                contra_sections.append(item)

        conditions = []
        for row in condition_rows:
            source = _source_fields(
                row["source_kind"],
                row["source_set_id"],
                row["summary"],
                labels,
                "CONTRAINDICATED_IN",
            )
            conditions.append(
                {
                    "key": row["key"],
                    "name": row["name"],
                    "rel_type": "CONTRAINDICATED_IN",
                    "source": source,
                }
            )
        result["boxed_warnings"] = boxed
        result["contraindication_sections"] = contra_sections
        result["contraindicated_in"] = conditions
        result["cypher"] = {
            "statement": (
                "MATCH (d:Drug {key: $key})-[:HAS_LABEL]->(l:Label)-[:HAS_SECTION]->(s:Section) "
                "WHERE s.kind IN $kinds "
                "RETURN s.kind AS kind, s.text AS text, l.set_id AS set_id, "
                "l.source_url AS source_url, l.effective_time AS effective_time "
                "ORDER BY s.kind "
                "LIMIT 20"
            ),
            "parameters": {
                "key": drug["key"],
                "kinds": ["boxed_warning", "contraindications"],
            },
            "queries": [
                {
                    "statement": (
                        "MATCH (d:Drug {key: $key})-[:HAS_LABEL]->(l:Label)-[:HAS_SECTION]->(s:Section) "
                        "WHERE s.kind IN $kinds "
                        "RETURN s.kind AS kind, s.text AS text, l.set_id AS set_id, "
                        "l.source_url AS source_url, l.effective_time AS effective_time "
                        "ORDER BY s.kind "
                        "LIMIT 20"
                    ),
                    "parameters": {
                        "key": drug["key"],
                        "kinds": ["boxed_warning", "contraindications"],
                    },
                },
                {
                    "statement": (
                        "MATCH (d:Drug {key: $key})-[r:CONTRAINDICATED_IN]->(c:Condition) "
                        "RETURN c.key AS key, c.name AS name, r.summary AS summary, "
                        "r.source_kind AS source_kind, r.source_set_id AS source_set_id "
                        "ORDER BY c.key "
                        "LIMIT 100"
                    ),
                    "parameters": {"key": drug["key"]},
                },
            ],
        }
        return result
    finally:
        if close:
            connection.close()


def neighbors(
    drug_name: str,
    conn: Any = None,
    database=None,
    limit: int = DEFAULT_NEIGHBOR_LIMIT,
) -> Dict[str, Any]:
    """Adjacent drugs, ingredients, and conditions, with source pointers."""
    cap = int(limit)
    if cap < 1:
        cap = 1
    if cap > 200:
        cap = 200
    connection, close = open_store(database=database, conn=conn)
    try:
        drug, result = _drug_or_error(drug_name, connection)
        if drug is None:
            return result
        neighbor_statement = (
            "MATCH (d:Drug {key: $key})-[r:%s]-(n) "
            "RETURN type(r) AS rel_type, startNode(r).key AS start_key, "
            "endNode(r).key AS end_key, labels(n)[0] AS neighbor_kind, "
            "n.key AS neighbor_key, coalesce(n.generic_name, n.name, n.key) AS neighbor_name, "
            "r.summary AS summary, r.source_kind AS source_kind, "
            "r.source_set_id AS source_set_id, r.matched_name AS matched_name "
            "ORDER BY type(r), n.key "
            "LIMIT $fetch_limit"
            % _PATH_REL_PATTERN
        )
        neighbor_params = {"key": drug["key"], "fetch_limit": cap}
        result["cypher"] = _cypher_payload(neighbor_statement, neighbor_params)
        rows = connection.execute(neighbor_statement, neighbor_params).fetchall()
        labels = _label_map(
            connection,
            [row["source_set_id"] for row in rows],
        )
        items = []
        for row in rows:
            outgoing = row["start_key"] == drug["key"]
            items.append(
                {
                    "direction": "outgoing" if outgoing else "incoming",
                    "rel_type": row["rel_type"],
                    "neighbor": {
                        "kind": row["neighbor_kind"],
                        "key": row["neighbor_key"],
                        "name": row["neighbor_name"],
                    },
                    "source": _source_fields(
                        row["source_kind"],
                        row["source_set_id"],
                        row["summary"],
                        labels,
                        row["rel_type"],
                        row["matched_name"],
                    ),
                    "display_label": hop_display_label(
                        row["rel_type"], source_kind=row["source_kind"]
                    ),
                }
            )
        items.sort(
            key=lambda item: (
                item["rel_type"],
                item["direction"],
                item["neighbor"]["kind"],
                item["neighbor"]["key"],
                (item["source"] or {}).get("kind") or "",
            )
        )
        result["neighbors"] = items[:cap]
        return result
    finally:
        if close:
            connection.close()


MED_LIST_MIN = 2
MED_LIST_MAX = 6
MED_LIST_STATEMENT = (
    "MATCH (a:Drug)-[r:LABELED_INTERACTION]->(b:Drug) "
    "WHERE a.key IN $keys AND b.key IN $keys AND a.key <> b.key "
    "RETURN a.key AS from_key, a.generic_name AS from_name, "
    "b.key AS to_key, b.generic_name AS to_name, "
    "r.source_kind AS source_kind, r.source_set_id AS source_set_id, "
    "r.summary AS summary, r.matched_name AS matched_name "
    "ORDER BY from_key, to_key, source_kind"
)


def med_list_check(
    names: Sequence[str], conn: Any = None, database=None
) -> Dict[str, Any]:
    """Every label mention among 2-6 resolved drugs, both directions, one query."""
    cleaned = [str(name).strip() for name in names if str(name).strip()]
    result: Dict[str, Any] = {
        "disclaimer": DISCLAIMER,
        "query": cleaned,
        "found": False,
        "mentions": [],
        "pairs": [],
        "drugs": [],
        "snapshot_date": SNAPSHOT_DATE,
        "snapshot_timezone": SNAPSHOT_TZ,
        "no_path_note": NO_PATH_NOTE % SNAPSHOT_DRUG_COUNT,
        "cypher": _cypher_payload(MED_LIST_STATEMENT, {"keys": []}),
    }
    if len(cleaned) < MED_LIST_MIN or len(cleaned) > MED_LIST_MAX:
        result["error"] = "Enter 2 to 6 drug names."
        return result

    connection, close = open_store(database=database, conn=conn)
    try:
        drug_count = connection.execute(
            "MATCH (d:Drug) RETURN count(d) AS n"
        ).fetchone()["n"]
        result["drug_count"] = int(drug_count)
        result["no_path_note"] = NO_PATH_NOTE % int(drug_count)

        resolved: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for name in cleaned:
            entity, matches, error = _resolve_required(
                name, connection, "drug", prefer_drug=True
            )
            if error:
                errors.append({"query": name, "error": error, "matches": matches})
                continue
            assert entity is not None
            if entity["kind"] != "Drug":
                errors.append(
                    {
                        "query": name,
                        "error": (
                            "%r resolved to an Ingredient (%s), not a Drug, in this snapshot."
                            % (name, entity["key"])
                        ),
                        "matches": matches,
                    }
                )
                continue
            resolved.append(
                {
                    "query": name,
                    "kind": entity["kind"],
                    "key": entity["key"],
                    "name": entity.get("name") or entity.get("generic_name") or entity["key"],
                }
            )

        result["resolved"] = resolved
        if errors:
            result["errors"] = errors
            result["error"] = "Every name must resolve to a drug in this snapshot."
            return result

        keys: List[str] = []
        drugs: List[Dict[str, Any]] = []
        seen = set()
        for item in resolved:
            if item["key"] in seen:
                continue
            seen.add(item["key"])
            keys.append(item["key"])
            drugs.append(item)
        result["drugs"] = drugs
        if len(keys) < MED_LIST_MIN:
            result["error"] = "Those names resolve to fewer than two distinct drugs."
            return result

        parameters = {"keys": keys}
        result["cypher"] = _cypher_payload(MED_LIST_STATEMENT, parameters)
        rows = connection.execute(MED_LIST_STATEMENT, parameters).fetchall()
        labels = _label_map(connection, [row["source_set_id"] for row in rows])

        mentions = []
        grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in rows:
            source = _source_fields(
                row["source_kind"],
                row["source_set_id"],
                row["summary"],
                labels,
                "LABELED_INTERACTION",
                row["matched_name"],
            )
            mention = {
                "from_key": row["from_key"],
                "from_name": row["from_name"] or row["from_key"],
                "to_key": row["to_key"],
                "to_name": row["to_name"] or row["to_key"],
                "rel_type": "LABELED_INTERACTION",
                "display_label": hop_display_label(
                    "LABELED_INTERACTION", source_kind=row["source_kind"]
                ),
                "source": source,
            }
            mentions.append(mention)
            pair_key = (row["from_key"], row["to_key"])
            if pair_key not in grouped:
                grouped[pair_key] = {
                    "from_key": mention["from_key"],
                    "from_name": mention["from_name"],
                    "to_key": mention["to_key"],
                    "to_name": mention["to_name"],
                    "display_label": mention["display_label"],
                    "sources": [],
                }
            grouped[pair_key]["sources"].append(source)

        by_key = {item["key"]: item for item in drugs}
        pairs = []
        for i, key_a in enumerate(keys):
            for key_b in keys[i + 1 :]:
                a_to_b = grouped.get((key_a, key_b))
                b_to_a = grouped.get((key_b, key_a))
                pairs.append(
                    {
                        "a": by_key[key_a],
                        "b": by_key[key_b],
                        "a_mentions_b": a_to_b,
                        "b_mentions_a": b_to_a,
                        "mutual": bool(a_to_b) and bool(b_to_a),
                        "one_sided": bool(a_to_b) != bool(b_to_a),
                        "none": not a_to_b and not b_to_a,
                    }
                )

        result["mentions"] = mentions
        result["grouped_mentions"] = list(grouped.values())
        result["pairs"] = pairs
        result["found"] = bool(mentions)
        if not mentions:
            result["error"] = (
                "No label mentions among these drugs were found in this snapshot. "
                + result["no_path_note"]
            )
        return result
    finally:
        if close:
            connection.close()
