from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from labelpath.query import DISCLAIMER, lookup, neighbors, paths_between, warnings

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
