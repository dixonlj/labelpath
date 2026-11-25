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
