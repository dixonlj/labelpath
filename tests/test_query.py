from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from labelpath.query import (
    DISCLAIMER,
    HUB_CONDITION_MIN_DRUGS,
    format_cypher,
    hop_display_label,
    hub_conditions,
    lookup,
    med_list_check,
    neighbors,
    paths_between,
    snapshot_stats,
    warnings,
)

ROOT = Path(__file__).resolve().parents[1]


def test_lookup_is_case_insensitive_and_salt_tolerant(conn):
    lower = lookup("warfarin", conn=conn)
    upper = lookup("WARFARIN SODIUM", conn=conn)
    assert lower["found"] is True
    assert upper["found"] is True
    assert any(item["kind"] == "Drug" and item["key"] == "warfarin" for item in lower["matches"])
    assert any(item["kind"] == "Drug" and item["key"] == "warfarin" for item in upper["matches"])
    assert lower["disclaimer"] == DISCLAIMER


def test_lookup_not_found(conn):
    result = lookup("zyzyxyxyx-not-a-real-drug", conn=conn)
    assert result["found"] is False
    assert result["matches"] == []
    assert result["disclaimer"] == DISCLAIMER


def test_paths_between_apixaban_aspirin_via_warfarin(conn):
    result = paths_between("apixaban", "aspirin", max_hops=3, conn=conn, limit=20)
    assert result["disclaimer"] == DISCLAIMER
    if not result["found"]:
        # Fall back to the other documented snapshot pair.
        alt = paths_between("protamine", "heparin", max_hops=3, conn=conn, limit=20)
        if not alt["found"]:
            pytest.skip(
                "snapshot has neither an apixaban–aspirin path nor a protamine–heparin path"
            )
        _assert_path_has_snippets(alt)
        return
    _assert_path_has_snippets(result)
    via_warfarin = [
        path
        for path in result["paths"]
        if [node["key"] for node in path["nodes"]] == ["apixaban", "warfarin", "aspirin"]
    ]
    assert via_warfarin, (
        "expected a 2-hop path apixaban -> warfarin -> aspirin in this snapshot; "
        "paths were: %s"
        % [[node["key"] for node in path["nodes"]] for path in result["paths"]]
    )
    assert via_warfarin[0]["hops"] == 2
    assert all(step["rel_type"] for step in via_warfarin[0]["steps"])


def test_paths_between_not_found(conn):
    result = paths_between("zyzyxyxyx-not-a-real-drug", "warfarin", max_hops=3, conn=conn)
    assert result["found"] is False
    assert result["paths"] == []
    assert "not found" in (result.get("error") or "").lower() or "No start" in (result.get("error") or "")


def test_warnings_include_section_pointers(conn):
    result = warnings("warfarin", conn=conn)
    assert result["found"] is True
    assert result["disclaimer"] == DISCLAIMER
    # This snapshot's warfarin label has both a boxed warning and contraindications.
    assert result["boxed_warnings"], "expected a boxed_warning section on warfarin"
    boxed = result["boxed_warnings"][0]
    assert boxed["kind"] == "boxed_warning"
    assert boxed["snippet"]
    assert boxed["set_id"]
    assert boxed["source_url"]
    assert result["contraindication_sections"]
    contra = result["contraindication_sections"][0]
    assert contra["kind"] == "contraindications"
    assert contra["snippet"]
    assert contra["set_id"]


def test_neighbors_include_rel_type_and_source(conn):
    result = neighbors("warfarin", conn=conn, limit=50)
    assert result["found"] is True
    assert result["neighbors"]
    aspirin = [
        item
        for item in result["neighbors"]
        if item["neighbor"]["key"] == "aspirin" and item["rel_type"] == "LABELED_INTERACTION"
    ]
    assert aspirin, "expected a LABELED_INTERACTION neighbor from warfarin to aspirin"
    source = aspirin[0]["source"]
    assert source["snippet"]
    assert source["kind"]
    assert source["set_id"]


def _assert_path_has_snippets(result):
    assert result["paths"]
    for path in result["paths"]:
        assert path["steps"]
        for step in path["steps"]:
            assert step["rel_type"]
            source = step["source"]
            assert source is not None
            if step["rel_type"] == "CONTAINS":
                assert source.get("note") or source.get("snippet")
            else:
                assert source.get("snippet")
                assert source.get("kind")
                assert source.get("set_id")


def test_cli_path_and_disclaimer():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "labelpath",
            "query",
            "path",
            "apixaban",
            "aspirin",
            "--max-hops",
            "3",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert DISCLAIMER in proc.stdout
    assert "apixaban" in proc.stdout
    assert "aspirin" in proc.stdout
    assert "Snippet:" in proc.stdout
    assert "Section:" in proc.stdout


def test_cli_lookup_not_found_and_json():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "labelpath",
            "--json",
            "query",
            "lookup",
            "zyzyxyxyx-not-a-real-drug",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert DISCLAIMER in proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["found"] is False
    assert payload["matches"] == []


def test_warnings_accepts_salt_name(conn):
    result = warnings("warfarin sodium", conn=conn)
    assert result["found"] is True
    assert result["drug"]["key"] == "warfarin"
    assert result["boxed_warnings"]


def test_hub_conditions_derived_from_store(conn):
    hubs = hub_conditions(conn)
    keys = [item["key"] for item in hubs]
    assert HUB_CONDITION_MIN_DRUGS == 10
    assert keys == ["anaphylaxis", "angioedema", "asthma"]
    by_key = {item["key"]: item["drug_count"] for item in hubs}
    assert by_key["anaphylaxis"] == 44
    assert by_key["angioedema"] == 41
    assert by_key["asthma"] == 15


def test_paths_exclude_hubs_by_default(conn):
    filtered = paths_between(
        "clopidogrel", "methotrexate", max_hops=2, conn=conn, limit=20
    )
    assert filtered["found"] is True
    routes = [[node["key"] for node in path["nodes"]] for path in filtered["paths"]]
    assert all("anaphylaxis" not in route for route in routes)
    assert all("angioedema" not in route for route in routes)
    assert all("asthma" not in route for route in routes)
    assert ["clopidogrel", "omeprazole", "methotrexate"] in routes
    assert filtered["paths"][0]["nodes"][1]["key"] != "anaphylaxis"
    assert any(path.get("headline", "").startswith("Connected through") for path in filtered["paths"])
    assert filtered.get("direct_mention_found") is False
    assert any(
        path.get("note") == "Neither endpoint label mentions the other directly."
        for path in filtered["paths"]
    )
    assert filtered["cypher"]["statement"]
    assert "hub_keys" in filtered["cypher"]["parameters"]

    included = paths_between(
        "clopidogrel",
        "methotrexate",
        max_hops=2,
        conn=conn,
        limit=20,
        include_hubs=True,
    )
    included_routes = [[node["key"] for node in path["nodes"]] for path in included["paths"]]
    assert any("anaphylaxis" in route for route in included_routes)
    assert "hub_keys" not in included["cypher"]["parameters"]


def test_paths_group_duplicate_routes_and_list_sources(conn):
    result = paths_between("apixaban", "aspirin", max_hops=2, conn=conn, limit=20)
    routes = [tuple(node["key"] for node in path["nodes"]) for path in result["paths"]]
    assert len(routes) == len(set(routes))
    via = [
        path
        for path in result["paths"]
        if [node["key"] for node in path["nodes"]] == ["apixaban", "warfarin", "aspirin"]
    ]
    assert via
    hop = via[0]["steps"][0]
    assert hop.get("display_label", "").startswith("Mentions")
    assert hop.get("sources")
    assert hop["source"] in hop["sources"] or hop["source"] == hop["sources"][0]


def test_direct_mentions_are_listed_first(conn):
    result = paths_between("apixaban", "aspirin", max_hops=2, conn=conn, limit=20)
    if not any(path.get("direct_mention") for path in result["paths"]):
        pytest.skip("no direct mention in this snapshot pair")
    first_non_direct = next(
        (i for i, path in enumerate(result["paths"]) if not path.get("direct_mention")),
        len(result["paths"]),
    )
    assert all(path.get("direct_mention") for path in result["paths"][:first_non_direct])
    assert all(not path.get("direct_mention") for path in result["paths"][first_non_direct:])


def test_snapshot_stats_match_store(conn):
    stats = snapshot_stats(conn)
    assert stats["drug_count"] == 293
    assert stats["mention_linked_pairs"] == 1396
    assert stats["mutual_mention_pairs"] == 172
    assert stats["one_sided_mention_pairs"] == 1224
    assert stats["snapshot_date"] == "19 November 2026"
    top = {item["key"]: item["named_by"] for item in stats["most_mentioned"]}
    assert top["warfarin"] == 64
    assert top["phenytoin"] == 61
    assert top["rifampin"] == 53


def test_med_list_check_both_directions(conn):
    result = med_list_check(["apixaban", "aspirin", "warfarin"], conn=conn)
    assert result["found"] is True
    assert result["disclaimer"] == DISCLAIMER
    assert result["cypher"]["statement"].count("MATCH") == 1
    assert "LABELED_INTERACTION" in result["cypher"]["statement"]
    assert set(result["cypher"]["parameters"]["keys"]) == {
        "apixaban",
        "aspirin",
        "warfarin",
    }
    keys = {item["key"] for item in result["drugs"]}
    assert keys == {"apixaban", "aspirin", "warfarin"}

    def direction(src, dst):
        return [
            item
            for item in result["mentions"]
            if item["from_key"] == src and item["to_key"] == dst
        ]

    assert direction("warfarin", "aspirin")
    assert not direction("aspirin", "warfarin")
    assert direction("apixaban", "warfarin")
    assert not direction("warfarin", "apixaban")
    pairs = {
        tuple(sorted((pair["a"]["key"], pair["b"]["key"]))): pair
        for pair in result["pairs"]
    }
    wa = pairs[("aspirin", "warfarin")]
    assert wa["one_sided"] is True
    assert wa["mutual"] is False
    aw = pairs[("apixaban", "warfarin")]
    assert aw["one_sided"] is True
    source = direction("warfarin", "aspirin")[0]["source"]
    assert source["snippet"]
    assert source["kind"]
    assert "aspirin" in (source.get("matched_name") or source["snippet"]).lower()


def test_med_list_check_rejects_counts(conn):
    too_few = med_list_check(["warfarin"], conn=conn)
    assert too_few["found"] is False
    assert "2 to 6" in too_few["error"]
    too_many = med_list_check(
        ["a", "b", "c", "d", "e", "f", "g"], conn=conn
    )
    assert too_many["found"] is False
    assert "2 to 6" in too_many["error"]


def test_hop_display_label_mentions_section():
    assert hop_display_label("LABELED_INTERACTION", "warnings_and_cautions") == (
        "Mentions · Warnings and cautions"
    )


def test_cli_med_list_and_mentions_label():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "labelpath",
            "query",
            "path",
            "apixaban",
            "aspirin",
            "--max-hops",
            "2",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Mentions" in proc.stdout
    assert "LABELED_INTERACTION" not in proc.stdout
    med = subprocess.run(
        [
            sys.executable,
            "-m",
            "labelpath",
            "query",
            "mention-scan",
            "apixaban",
            "aspirin",
            "warfarin",
            "--show-cypher",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert med.returncode == 0, med.stderr
    assert DISCLAIMER in med.stdout
    assert "warfarin" in med.stdout
    assert "Cypher:" in med.stdout
    assert "LABELED_INTERACTION" in med.stdout


def test_mutual_mention_keeps_source_direction(conn):
    result = paths_between("clopidogrel", "omeprazole", max_hops=1, conn=conn, limit=20)
    assert result["found"] is True
    path = result["paths"][0]
    assert path["hops"] == 1
    assert path.get("mutual_mention") is True
    assert path.get("headline") == "Mutual mention"
    step = path["steps"][0]
    assert step.get("mutual") is True
    from_keys = {source["from_key"] for source in step["sources"]}
    to_keys = {source["to_key"] for source in step["sources"]}
    assert from_keys == {"clopidogrel", "omeprazole"}
    assert to_keys == {"clopidogrel", "omeprazole"}
    clo = [s for s in step["sources"] if s["from_key"] == "clopidogrel"]
    ome = [s for s in step["sources"] if s["from_key"] == "omeprazole"]
    assert clo and ome
    assert all((s.get("matched_name") or "").lower() == "omeprazole" or "omeprazole" in (s.get("snippet") or "").lower() for s in clo)
    assert all((s.get("matched_name") or "").lower() == "clopidogrel" or "clopidogrel" in (s.get("snippet") or "").lower() for s in ome)


def test_clopidogrel_methotrexate_preserves_mutual_hop(conn):
    result = paths_between("clopidogrel", "methotrexate", max_hops=2, conn=conn, limit=20)
    via = [
        path
        for path in result["paths"]
        if [node["key"] for node in path["nodes"]]
        == ["clopidogrel", "omeprazole", "methotrexate"]
    ]
    assert via
    hop = via[0]["steps"][0]
    assert hop.get("mutual") is True
    from_keys = {source["from_key"] for source in hop["sources"]}
    assert "clopidogrel" in from_keys and "omeprazole" in from_keys


def test_cli_mutual_mention_attribution():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "labelpath",
            "query",
            "path",
            "clopidogrel",
            "omeprazole",
            "--max-hops",
            "1",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    lower = proc.stdout.lower()
    assert "from clopidogrel" in lower and "label:" in lower
    assert "from omeprazole" in lower
    assert "Mutual mention" in proc.stdout


def test_med_list_display_label_includes_each_section(conn):
    result = med_list_check(["apixaban", "warfarin"], conn=conn)
    grouped = [
        item
        for item in result["grouped_mentions"]
        if item["from_key"] == "apixaban" and item["to_key"] == "warfarin"
    ]
    assert grouped
    kinds = {source["kind"] for source in grouped[0]["sources"]}
    assert "drug_interactions" in kinds
    assert "warnings_and_cautions" in kinds
    assert "Warnings and cautions" in grouped[0]["display_label"]
    assert "Drug interactions" in grouped[0]["display_label"]


def test_mention_scan_alias_and_bridges(conn):
    result = med_list_check(["clopidogrel", "methotrexate"], conn=conn)
    assert result["found"] is True
    keys = {(item["a"]["key"], item["b"]["key"], item["via"]["key"]) for item in result["bridges"]}
    assert ("clopidogrel", "methotrexate", "omeprazole") in keys
    alias = subprocess.run(
        [
            sys.executable,
            "-m",
            "labelpath",
            "query",
            "med-list",
            "clopidogrel",
            "omeprazole",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert alias.returncode == 0, alias.stderr
    assert "Multi-drug mention scan" in alias.stdout
    assert "mutual" in alias.stdout.lower() or "Mutual" in alias.stdout


def test_format_cypher_renders_all_queries_and_breaks_clauses(conn):
    result = warnings("warfarin", conn=conn)
    text = format_cypher(result["cypher"])
    assert "Query 1:" in text and "Query 2:" in text
    assert "\nWHERE " in "\n" + text.replace("\r", "")
    # inner WHERE inside ALL(...) or similar should not be the test; warnings WHERE is top-level
    assert "MATCH (d:Drug" in text
    lines = text.splitlines()
    assert any(line.startswith("WHERE") for line in lines)
    assert any(line.startswith("RETURN") for line in lines)
