"""HTTP tests for the local LabelPath UI. The store is opened read-only."""
from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from labelpath.query import DISCLAIMER
from labelpath.serve import ATTRIBUTION, BIND_HOST, make_server

try:
    from http.client import RemoteDisconnected
except ImportError:  # pragma: no cover
    RemoteDisconnected = ConnectionError


@pytest.fixture(scope="module")
def httpd(store_path):
    server = make_server(database=str(store_path), host="127.0.0.1", port=0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield "http://%s:%s" % (host, port), server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _request(base, path, method="GET"):
    url = base + path
    req = Request(url, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read()
            return resp.status, resp.headers, body
    except HTTPError as exc:
        body = exc.read()
        return exc.code, exc.headers, body


def _json(base, path):
    status, headers, body = _request(base, path)
    payload = json.loads(body.decode("utf-8"))
    return status, headers, payload


def test_server_binds_loopback_only(httpd):
    base, server = httpd
    host, _port = server.server_address[:2]
    assert host == BIND_HOST == "127.0.0.1"
    assert base.startswith("http://127.0.0.1:")


def test_index_contains_disclaimer_and_attribution(httpd):
    base, _server = httpd
    status, headers, body = _request(base, "/")
    text = body.decode("utf-8")
    assert status == 200
    ctype = headers.get("Content-Type") or ""
    assert "text/html" in ctype
    assert DISCLAIMER in text
    assert "Data provided by the U.S. Food and Drug Administration" in text
    assert "https://open.fda.gov" in text
    assert "Do not rely on openFDA to make decisions regarding medical care." in text
    assert "Try: apixaban → aspirin" in text
    assert "Multi-drug mention scan" in text
    assert "Scan mentions" in text
    assert "Why a graph" in text
    assert "exact FDA label" not in text
    assert "label on DailyMed (current version may differ from the snapshot)" in text
    # The disclaimer is in the HTML itself, not only injected by JavaScript.
    assert text.index(DISCLAIMER) < text.index('src="/static/app.js"')


def test_api_meta_includes_disclaimer(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/meta")
    assert status == 200
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["attribution"] == ATTRIBUTION
    assert payload["bind"] == "127.0.0.1"
    assert payload["default_max_hops"] == 2


def test_lookup_json_ok(httpd):
    base, _server = httpd
    status, headers, payload = _json(base, "/api/lookup?q=warfarin%20sodium")
    assert status == 200
    assert "application/json" in (headers.get("Content-Type") or "")
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["found"] is True
    assert any(item["kind"] == "Drug" and item["key"] == "warfarin" for item in payload["matches"])


def test_lookup_not_found_includes_disclaimer(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/lookup?q=zyzyxyxyx-not-a-real-drug")
    assert status == 200
    assert payload["found"] is False
    assert payload["matches"] == []
    assert payload["disclaimer"] == DISCLAIMER


def test_lookup_empty_query_is_error_with_disclaimer(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/lookup?q=")
    assert status == 400
    assert payload["found"] is False
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["error"]


def test_path_apixaban_aspirin_defaults_to_two_hops(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/path?start=apixaban&end=aspirin")
    assert status == 200
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["max_hops"] == 2
    assert payload["found"] is True
    hops = [path["hops"] for path in payload["paths"]]
    assert hops, "expected at least one path"
    assert hops == sorted(hops)
    assert hops[0] == 1
    assert all(item <= 2 for item in hops)
    # A 2-hop apixaban → warfarin → aspirin path should still appear at max_hops=2.
    via = [
        path
        for path in payload["paths"]
        if path["hops"] == 2
        and [node["key"] for node in path["nodes"]] == ["apixaban", "warfarin", "aspirin"]
    ]
    assert via, "expected the documented 2-hop path via warfarin"
    step = via[0]["steps"][0]
    source = step["source"]
    assert source.get("kind")
    assert source.get("snippet")
    assert source.get("source_url")
    assert "dailymed.nlm.nih.gov" in source["source_url"]


def test_path_missing_names_is_error_with_disclaimer(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/path?start=apixaban")
    assert status == 400
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["found"] is False


def test_path_no_match_includes_disclaimer(httpd):
    base, _server = httpd
    status, _headers, payload = _json(
        base, "/api/path?start=zyzyxyxyx-not-a-real-drug&end=aspirin"
    )
    assert status == 200
    assert payload["found"] is False
    assert payload["disclaimer"] == DISCLAIMER
    assert payload.get("error")


def test_warnings_warfarin(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/warnings?q=warfarin")
    assert status == 200
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["found"] is True
    assert payload["boxed_warnings"]
    boxed = payload["boxed_warnings"][0]
    assert boxed.get("snippet")
    assert boxed.get("kind") == "boxed_warning"
    assert boxed.get("source_url")
    assert "dailymed.nlm.nih.gov" in boxed["source_url"]


def test_neighbors_protamine(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/neighbors?q=protamine")
    assert status == 200
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["found"] is True
    assert payload["neighbors"]
    heparin = [
        item
        for item in payload["neighbors"]
        if item["neighbor"]["key"] == "heparin"
        and item["rel_type"] == "LABELED_INTERACTION"
    ]
    assert heparin
    source = heparin[0]["source"]
    assert source.get("kind")
    assert source.get("snippet")
    assert source.get("source_url")


def test_static_css_and_js(httpd):
    base, _server = httpd
    css_status, css_headers, css = _request(base, "/static/styles.css")
    js_status, js_headers, js = _request(base, "/static/app.js")
    assert css_status == 200
    assert js_status == 200
    assert "text/css" in (css_headers.get("Content-Type") or "")
    assert "javascript" in (js_headers.get("Content-Type") or "")
    assert b"banner" in css
    assert b"Try" not in js or b"apixaban" in js
    font_status, font_headers, font = _request(base, "/static/fonts/inter-latin-var.woff2")
    assert font_status == 200
    assert "font/woff2" in (font_headers.get("Content-Type") or "")
    assert font[:4] == b"wOF2"
    img_status, img_headers, img = _request(base, "/static/how-labelpath-works.png")
    assert img_status == 200
    assert "image/png" in (img_headers.get("Content-Type") or "")
    assert img[:8] == b"\x89PNG\r\n\x1a\n"
    logo_status, logo_headers, logo = _request(base, "/static/logo.svg")
    assert logo_status == 200
    assert "svg" in (logo_headers.get("Content-Type") or "")
    assert b"LabelPath" in logo
    fav_status, fav_headers, fav = _request(base, "/favicon.ico")
    assert fav_status == 200
    assert "image/x-icon" in (fav_headers.get("Content-Type") or "")
    assert len(fav) > 16


def test_static_path_traversal_is_rejected(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/static/../../data/labelpath.rl")
    assert status == 404
    assert payload["disclaimer"] == DISCLAIMER
    # A raw store file must not be served as a static asset.
    assert _headers is None or "application/octet-stream" not in (
        (_headers.get("Content-Type") or "") if _headers else ""
    )


def test_unknown_route_is_404_with_disclaimer(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/does-not-exist")
    assert status == 404
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["found"] is False


def test_make_server_rejects_non_loopback(store_path):
    with pytest.raises(ValueError, match="loopback"):
        make_server(database=str(store_path), host="0.0.0.0", port=0, quiet=True)


def test_api_meta_includes_snapshot_facts(httpd):
    base, _server = httpd
    status, _headers, payload = _json(base, "/api/meta")
    assert status == 200
    assert payload["drug_count"] == 293
    assert payload["mention_linked_pairs"] == 1396
    assert payload["mutual_mention_pairs"] == 172
    assert payload["snapshot_date"] == "19 November 2026"
    keys = [item["key"] for item in payload["hub_conditions"]]
    assert keys == ["anaphylaxis", "angioedema", "asthma"]


def test_api_path_hub_toggle_and_cypher(httpd):
    base, _server = httpd
    status, _headers, payload = _json(
        base, "/api/path?start=clopidogrel&end=methotrexate&max_hops=2"
    )
    assert status == 200
    routes = [[node["key"] for node in path["nodes"]] for path in payload["paths"]]
    assert all("anaphylaxis" not in route for route in routes)
    assert payload["cypher"]["statement"]
    status, _headers, included = _json(
        base,
        "/api/path?start=clopidogrel&end=methotrexate&max_hops=2&include_hubs=1",
    )
    assert status == 200
    included_routes = [
        [node["key"] for node in path["nodes"]] for path in included["paths"]
    ]
    assert any("anaphylaxis" in route for route in included_routes)


def test_api_med_list(httpd):
    base, _server = httpd
    status, _headers, payload = _json(
        base, "/api/med-list?q=apixaban,aspirin,warfarin"
    )
    assert status == 200
    assert payload["disclaimer"] == DISCLAIMER
    assert payload["found"] is True
    assert payload["cypher"]["statement"].count("MATCH") == 1
    assert any(
        item["from_key"] == "warfarin" and item["to_key"] == "aspirin"
        for item in payload["mentions"]
    )


def test_api_mention_scan_alias(httpd):
    base, _server = httpd
    status, _headers, payload = _json(
        base, "/api/mention-scan?q=clopidogrel,omeprazole"
    )
    assert status == 200
    assert payload["found"] is True
    assert any(pair.get("mutual") for pair in payload["pairs"])
    assert payload["cypher"]["queries"] and len(payload["cypher"]["queries"]) == 2
