from __future__ import annotations

import pytest


def test_graph_counts_are_positive(conn):
    nodes = conn.execute("MATCH (n) RETURN count(n) AS n").single()["n"]
    rels = conn.execute("MATCH ()-[r]->() RETURN count(r) AS n").single()["n"]
    drugs = conn.execute("MATCH (d:Drug) RETURN count(d) AS n").single()["n"]
    sections = conn.execute("MATCH (s:Section) RETURN count(s) AS n").single()["n"]
    labels = conn.execute("MATCH (l:Label) RETURN count(l) AS n").single()["n"]
    assert nodes > 0
    assert rels > 0
    assert drugs > 0
    assert sections > 0
    assert labels > 0


def test_warfarin_exists_with_a_section(conn):
    row = conn.execute(
        "MATCH (d:Drug {key: $key})-[:HAS_LABEL]->(:Label)-[:HAS_SECTION]->(s:Section) "
        "RETURN d.key AS key, count(s) AS sections",
        {"key": "warfarin"},
    ).single()
    assert row is not None
    assert row["sections"] >= 1


# Candidate public-label pairs to look for. The first pair that exists in this
# snapshot is the documented "known path". If none exist, the test is skipped.
KNOWN_PATH_CANDIDATES = (
    ("warfarin", "aspirin"),
    ("warfarin", "amiodarone"),
    ("warfarin", "rifampin"),
    ("warfarin", "fluconazole"),
    ("warfarin", "phytonadione"),
    ("heparin", "protamine"),
    ("warfarin", "ibuprofen"),
    ("warfarin", "naproxen"),
)


def _path_row(conn, src, dst):
    return conn.execute(
        "MATCH (a:Drug {key: $src})-[r:LABELED_INTERACTION]->(b {key: $dst}) "
        "RETURN a.key AS from_key, b.key AS to_key, r.summary AS summary, "
        "r.source_kind AS source_kind, r.source_set_id AS source_set_id "
        "LIMIT 5",
        {"src": src, "dst": dst},
    ).fetchall()


def test_known_labeled_interaction_path_or_skip(conn):
    found = None
    for src, dst in KNOWN_PATH_CANDIDATES:
        rows = _path_row(conn, src, dst)
        if rows:
            found = (src, dst, rows[0])
            break
    if found is None:
        pytest.skip(
            "snapshot has no LABELED_INTERACTION for any candidate pair "
            "(warfarin–aspirin, warfarin–amiodarone, warfarin–rifampin, "
            "warfarin–fluconazole, warfarin–phytonadione, heparin–protamine, "
            "warfarin–ibuprofen, warfarin–naproxen); inspect the store before adding a new pair"
        )
    src, dst, row = found
    assert row["from_key"] == src
    assert row["summary"]
    assert row["source_kind"]
    assert row["source_set_id"]
