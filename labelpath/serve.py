"""Local 127.0.0.1 UI for LabelPath. Standard library only. Python 3.9 compatible."""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from labelpath.paths import STORE_FILE
from labelpath.query import (
    DEFAULT_NEIGHBOR_LIMIT,
    DISCLAIMER,
    lookup,
    neighbors,
    paths_between,
    warnings,
)

BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
# The UI and /api/path default to 2 hops for a clearer first view (CLI path still defaults to 3).
DEFAULT_UI_MAX_HOPS = 2
DEFAULT_UI_PATH_LIMIT = 10
MAX_QUERY_LEN = 200
STATIC_DIR = Path(__file__).resolve().parent / "static"
ATTRIBUTION = (
    "Data provided by the U.S. Food and Drug Administration (https://open.fda.gov)."
)
OPENFDA_CAUTION = (
    "Do not rely on openFDA to make decisions regarding medical care."
)

_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def resolve_database(database=None) -> Path:
    path = Path(database) if database else STORE_FILE
    return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()


def _clip_query(value: Optional[str]) -> str:
    text = (value or "").strip()
    if len(text) > MAX_QUERY_LEN:
        return text[:MAX_QUERY_LEN]
    return text


def _error_payload(message: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {
        "disclaimer": DISCLAIMER,
        "attribution": ATTRIBUTION,
        "found": False,
        "error": message,
    }
    if extra:
        payload.update(extra)
    return payload


class LabelPathHandler(BaseHTTPRequestHandler):
    """Serves the single-page UI and read-only JSON query endpoints."""

    database = STORE_FILE
    quiet = False
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):  # noqa: A002 - required signature
        if not self.quiet:
            BaseHTTPRequestHandler.log_message(self, format, *args)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = unquote(parsed.path or "/")
        query = parse_qs(parsed.query, keep_blank_values=True)

        if route in ("/", "/index.html"):
            self._send_static(STATIC_DIR / "index.html")
            return
        if route.startswith("/static/"):
            self._send_static_route(route[len("/static/") :])
            return
        if route == "/api/meta":
            self._send_json(
                200,
                {
                    "disclaimer": DISCLAIMER,
                    "attribution": ATTRIBUTION,
                    "openfda_caution": OPENFDA_CAUTION,
                    "bind": BIND_HOST,
                    "default_max_hops": DEFAULT_UI_MAX_HOPS,
                },
            )
            return
        if route == "/api/lookup":
            self._api_lookup(query)
            return
        if route == "/api/path":
            self._api_path(query)
            return
        if route == "/api/warnings":
            self._api_warnings(query)
            return
        if route == "/api/neighbors":
            self._api_neighbors(query)
            return
        self._send_json(404, _error_payload("Not found."))

    def do_HEAD(self) -> None:
        # Used only so a probe can check the page is up without a body.
        parsed = urlparse(self.path)
        route = unquote(parsed.path or "/")
        if route in ("/", "/index.html"):
            target = STATIC_DIR / "index.html"
            if target.is_file():
                data = target.read_bytes()
                self._send_headers(200, "text/html; charset=utf-8", len(data))
                return
        self._send_headers(404, "application/json; charset=utf-8", 0)

    def _param(self, query: Dict[str, list], name: str) -> str:
        values = query.get(name) or []
        if not values:
            return ""
        return _clip_query(values[0])

    def _int_param(
        self, query: Dict[str, list], name: str, default: int, minimum: int, maximum: int
    ) -> Tuple[Optional[int], Optional[str]]:
        raw = self._param(query, name)
        if raw == "":
            return default, None
        try:
            value = int(raw)
        except ValueError:
            return None, "Parameter %r must be an integer." % name
        if value < minimum:
            value = minimum
        if value > maximum:
            value = maximum
        return value, None

    def _api_lookup(self, query: Dict[str, list]) -> None:
        name = self._param(query, "q")
        if not name:
            self._send_json(400, _error_payload("Type a drug or ingredient name to search."))
            return
        result = lookup(name, database=self.database)
        result["attribution"] = ATTRIBUTION
        self._send_json(200, result)

    def _api_path(self, query: Dict[str, list]) -> None:
        start = self._param(query, "start")
        end = self._param(query, "end")
        extra = {"start_query": start, "end_query": end}
        if not start or not end:
            self._send_json(
                400,
                _error_payload("Enter two drug or ingredient names to look for a labeled path.", extra),
            )
            return
        hops, error = self._int_param(query, "max_hops", DEFAULT_UI_MAX_HOPS, 1, 3)
        if error:
            self._send_json(400, _error_payload(error, extra))
            return
        limit, error = self._int_param(query, "limit", DEFAULT_UI_PATH_LIMIT, 1, 100)
        if error:
            self._send_json(400, _error_payload(error, extra))
            return
        assert hops is not None and limit is not None
        result = paths_between(
            start, end, max_hops=hops, database=self.database, limit=limit
        )
        result["attribution"] = ATTRIBUTION
        self._send_json(200, result)

    def _api_warnings(self, query: Dict[str, list]) -> None:
        name = self._param(query, "q")
        if not name:
            self._send_json(400, _error_payload("Type a drug name to list boxed warnings and contraindications."))
            return
        result = warnings(name, database=self.database)
        result["attribution"] = ATTRIBUTION
        self._send_json(200, result)

    def _api_neighbors(self, query: Dict[str, list]) -> None:
        name = self._param(query, "q")
        if not name:
            self._send_json(400, _error_payload("Type a drug name to list labeled neighbors."))
            return
        limit, error = self._int_param(query, "limit", DEFAULT_NEIGHBOR_LIMIT, 1, 200)
        if error:
            self._send_json(400, _error_payload(error, {"query": name}))
            return
        assert limit is not None
        result = neighbors(name, database=self.database, limit=limit)
        result["attribution"] = ATTRIBUTION
        self._send_json(200, result)

    def _send_static_route(self, relative: str) -> None:
        target = _safe_static_file(relative)
        if target is None:
            self._send_json(404, _error_payload("Not found."))
            return
        self._send_static(target)

    def _send_static(self, target: Path) -> None:
        if not target.is_file():
            self._send_json(404, _error_payload("Not found."))
            return
        data = target.read_bytes()
        mime = _MIME.get(target.suffix.lower(), "application/octet-stream")
        self._send_headers(200, mime, len(data))
        self.wfile.write(data)

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        self._send_headers(status, "application/json; charset=utf-8", len(body), cache=False)
        self.wfile.write(body)

    def _send_headers(self, status: int, content_type: str, length: int, cache: bool = True) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; form-action 'self'; "
            "base-uri 'self'; frame-ancestors 'none'",
        )
        if cache:
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()


def _safe_static_file(relative: str) -> Optional[Path]:
    if not relative or relative.startswith("."):
        return None
    # Reject any path that would escape STATIC_DIR (slashes, .., absolute paths).
    root = STATIC_DIR.resolve()
    candidate = (STATIC_DIR / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file() or not candidate.name or candidate.name.startswith("."):
        return None
    return candidate


def make_server(database=None, host: str = BIND_HOST, port: int = DEFAULT_PORT, quiet: bool = False):
    """Return a ThreadingHTTPServer bound only to a loopback address."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise ValueError("LabelPath binds only to loopback (127.0.0.1), not %r." % host)
    bind_host = "127.0.0.1" if host in ("127.0.0.1", "localhost") else host
    store = resolve_database(database)
    if not store.is_file():
        raise FileNotFoundError("Relate store not found: %s" % store)

    class BoundHandler(LabelPathHandler):
        pass

    BoundHandler.database = store
    BoundHandler.quiet = quiet
    server = ThreadingHTTPServer((bind_host, int(port)), BoundHandler)
    server.allow_reuse_address = True
    return server


def run_server(port: int = DEFAULT_PORT, database=None) -> int:
    """Start the UI server and block until interrupt. Returns a process exit code."""
    try:
        port_num = int(port)
    except (TypeError, ValueError):
        sys.stderr.write("Port must be an integer.\n")
        return 2
    if port_num < 0 or port_num > 65535:
        sys.stderr.write("Port must be between 0 and 65535.\n")
        return 2
    try:
        server = make_server(database=database, host=BIND_HOST, port=port_num, quiet=False)
    except FileNotFoundError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
    except OSError as exc:
        sys.stderr.write("Could not bind %s:%s: %s\n" % (BIND_HOST, port_num, exc))
        return 1

    host, bound_port = server.server_address[:2]
    sys.stdout.write(DISCLAIMER + "\n")
    sys.stdout.write(
        "LabelPath UI: http://%s:%s/  (bound to %s only; the store is opened read-only)\n"
        % (host, bound_port, BIND_HOST)
    )
    sys.stdout.write("Press Ctrl+C to stop.\n")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\nStopped.\n")
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_server())
