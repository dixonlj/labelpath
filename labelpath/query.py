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
) -> Dict[str, Any]:
    info = labels.get(source_set_id or "", {})
    source = {
        "kind": source_kind,
        "set_id": source_set_id,
        "source_url": info.get("source_url"),
        "effective_time": info.get("effective_time"),
        "snippet": summary,
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
        return {
            "disclaimer": DISCLAIMER,
            "query": name,
            "matches": matches,
            "found": bool(matches),
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
        result = {
            "disclaimer": DISCLAIMER,
            "start_query": a,
            "end_query": b,
            "max_hops": hops,
            "start": start,
            "end": end,
            "paths": [],
            "found": False,
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

        # Hop bound is a clamped integer, not raw user text.
        statement = (
            "MATCH (start {key: $start_key}), (finish {key: $end_key}) "
            "WHERE $start_label IN labels(start) AND $end_label IN labels(finish) "
            "MATCH p = (start)-[:%s*1..%d]-(finish) "
            "WITH p, nodes(p) AS ns "
            "WHERE ALL(n IN ns WHERE size([m IN ns WHERE m = n]) = 1) "
            "RETURN length(p) AS hops, "
            "[n IN nodes(p) | n.key] AS keys, "
            "[n IN nodes(p) | labels(n)[0]] AS node_kinds, "
            "[n IN nodes(p) | coalesce(n.generic_name, n.name, n.key)] AS names, "
            "[r IN relationships(p) | type(r)] AS rel_types, "
            "[r IN relationships(p) | r.summary] AS summaries, "
            "[r IN relationships(p) | r.source_kind] AS source_kinds, "
            "[r IN relationships(p) | r.source_set_id] AS source_set_ids, "
            "[r IN relationships(p) | startNode(r).key] AS rel_starts, "
            "[r IN relationships(p) | endNode(r).key] AS rel_ends "
            "ORDER BY length(p) ASC "
            "LIMIT $fetch_limit"
        ) % (_PATH_REL_PATTERN, hops)

        rows = connection.execute(
            statement,
            {
                "start_key": start["key"],
                "end_key": end["key"],
                "start_label": start["kind"],
                "end_label": end["kind"],
                "fetch_limit": cap,
            },
        ).fetchall()

        set_ids: List[str] = []
        for row in rows:
            set_ids.extend([item for item in (row["source_set_ids"] or []) if item])
        labels = _label_map(connection, set_ids)

        paths = []
        for row in rows:
            steps = []
            rel_types = row["rel_types"] or []
            for index, rel_type in enumerate(rel_types):
                source = _source_fields(
                    (row["source_kinds"] or [None])[index],
                    (row["source_set_ids"] or [None])[index],
                    (row["summaries"] or [None])[index],
                    labels,
                    rel_type,
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
            paths.append(
                {
                    "hops": row["hops"],
                    "nodes": nodes,
                    "steps": steps,
                }
            )

        def path_sort_key(path: Dict[str, Any]) -> Tuple:
            node_keys = tuple(node["key"] for node in path["nodes"])
            rels = tuple(step["rel_type"] for step in path["steps"])
            kinds = tuple((step["source"] or {}).get("kind") or "" for step in path["steps"])
            return (path["hops"], node_keys, rels, kinds)

        paths.sort(key=path_sort_key)
        paths = paths[:cap]
        result["paths"] = paths
        result["found"] = bool(paths)
        if not paths:
            result["error"] = (
                "No labeled path of at most %s hop(s) was found between %s and %s "
                "in this snapshot."
                % (hops, start["key"], end["key"])
            )
        return result
    finally:
        if close:
            connection.close()


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
        rows = connection.execute(
            "MATCH (d:Drug {key: $key})-[r:%s]-(n) "
            "RETURN type(r) AS rel_type, startNode(r).key AS start_key, "
            "endNode(r).key AS end_key, labels(n)[0] AS neighbor_kind, "
            "n.key AS neighbor_key, coalesce(n.generic_name, n.name, n.key) AS neighbor_name, "
            "r.summary AS summary, r.source_kind AS source_kind, "
            "r.source_set_id AS source_set_id "
            "ORDER BY type(r), n.key "
            "LIMIT $fetch_limit"
            % _PATH_REL_PATTERN,
            {"key": drug["key"], "fetch_limit": cap},
        ).fetchall()
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
