#!/usr/bin/env python3
"""Read-only MCP smoke test for LabelPath. Standard library only. Python 3.9 compatible.

Talks JSON-RPC 2.0 over stdio to the official command:

    relate serve --mcp stdio --database ./data/labelpath.rl --read-only

The sequence is initialize, tools/list, one parameterized read (the documented
apixaban → warfarin → aspirin path), and one write attempt that must be refused.
Skips with exit code 77 if the Relate CLI is not installed.

This script never starts a writable server and never binds a port.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import threading
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from labelpath.paths import STORE_FILE
from labelpath.query import DISCLAIMER

# Official install.sh default (https://relatedb.ai/docs/get-started/install/).
OFFICIAL_USER_BIN = Path.home() / ".local" / "bin" / "relate"
SKIP_EXIT = 77
DEFAULT_TIMEOUT = 30

READ_STATEMENT = (
    "MATCH (a:Drug {key: $start})-[r1:LABELED_INTERACTION]->(mid:Drug)"
    "-[r2:LABELED_INTERACTION]->(b:Drug {key: $end}) "
    "RETURN a.key AS start, mid.key AS via, b.key AS end, "
    "r1.source_kind AS hop1_section, r1.source_set_id AS hop1_set_id, "
    "r2.source_kind AS hop2_section, r2.source_set_id AS hop2_set_id "
    "LIMIT 20"
)
WRITE_STATEMENT = "CREATE (n:Drug {key: $key}) RETURN n.key AS key"


class SkipMCP(Exception):
    """The Relate CLI is not available."""


class MCPError(Exception):
    """The smoke test failed."""


def find_relate_cli() -> Optional[str]:
    """Return the relate executable, or None if it is not installed."""
    env = os.environ.get("RELATE_CLI")
    if env:
        path = Path(env).expanduser()
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path.resolve())
        return None
    found = shutil.which("relate")
    if found:
        return found
    if OFFICIAL_USER_BIN.is_file() and os.access(str(OFFICIAL_USER_BIN), os.X_OK):
        return str(OFFICIAL_USER_BIN)
    return None


def file_fingerprint(path: Path) -> Tuple[int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return path.stat().st_size, digest.hexdigest()


def _send(
    proc: subprocess.Popen,
    message: Dict[str, Any],
    expect_response: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
) -> Optional[Dict[str, Any]]:
    if proc.stdin is None or proc.stdout is None:
        raise MCPError("MCP process has no stdio pipes.")
    line = json.dumps(message, separators=(",", ":"))
    proc.stdin.write(line + "\n")
    proc.stdin.flush()
    if not expect_response:
        return None
    ready, _, _ = select.select([proc.stdout], [], [], timeout)
    if not ready:
        raise MCPError(
            "Timed out waiting for a JSON-RPC response to method %r (id %r)."
            % (message.get("method"), message.get("id"))
        )
    raw = proc.stdout.readline()
    if not raw:
        raise MCPError("MCP server closed stdout before answering %r." % message.get("method"))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MCPError("MCP stdout was not JSON: %r (%s)" % (raw[:500], exc))


def _content_text(response: Dict[str, Any]) -> str:
    result = response.get("result") or {}
    chunks = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("text") is not None:
            chunks.append(str(item["text"]))
    return "\n".join(chunks)


def _parse_tool_envelope(response: Dict[str, Any]) -> Dict[str, Any]:
    text = _content_text(response)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def relate_version(cli: str) -> str:
    try:
        out = subprocess.check_output([cli, "--version"], text=True, timeout=10)
    except (OSError, subprocess.SubprocessError) as exc:
        raise MCPError("Could not run %s --version: %s" % (cli, exc))
    return " ".join(out.strip().split())


def run_smoke(
    database: Optional[str] = None,
    cli: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Run the stdio smoke test. Raises SkipMCP or MCPError."""
    relate = cli or find_relate_cli()
    if not relate:
        raise SkipMCP(
            "Relate CLI not found (looked at $RELATE_CLI, PATH, and %s). "
            "Install from https://relatedb.ai/docs/get-started/install/ and retry."
            % OFFICIAL_USER_BIN
        )
    store = Path(database) if database else STORE_FILE
    if not store.is_file():
        raise MCPError("Store not found: %s" % store)

    before = file_fingerprint(store)
    version = relate_version(relate)
    command = [
        relate,
        "serve",
        "--mcp",
        "stdio",
        "--database",
        str(store),
        "--read-only",
    ]
    # stderr to a pipe can deadlock if it fills; keep it in a temp-like buffer via PIPE
    # but drain after close because the session is short.
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stderr_text = ""
    try:
        init = _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "labelpath-mcp-smoke", "version": "0.0.0"},
                },
            },
            timeout=timeout,
        )
        assert init is not None
        if "error" in init:
            raise MCPError("initialize failed: %s" % init["error"])
        server_info = (init.get("result") or {}).get("serverInfo") or {}

        _send(
            proc,
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            expect_response=False,
            timeout=timeout,
        )

        listed = _send(
            proc,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            timeout=timeout,
        )
        assert listed is not None
        if "error" in listed:
            raise MCPError("tools/list failed: %s" % listed["error"])
        tools = (listed.get("result") or {}).get("tools") or []
        names = [item.get("name") for item in tools]
        if names != ["read_cypher", "get_schema"]:
            raise MCPError(
                "Expected read-only tools [read_cypher, get_schema], got %s" % names
            )

        read = _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "read_cypher",
                    "arguments": {
                        "statement": READ_STATEMENT,
                        "parameters": {"start": "apixaban", "end": "aspirin"},
                    },
                },
            },
            timeout=timeout,
        )
        assert read is not None
        if "error" in read:
            raise MCPError("read_cypher JSON-RPC error: %s" % read["error"])
        if (read.get("result") or {}).get("isError"):
            raise MCPError("read_cypher returned isError: %s" % _content_text(read))
        envelope = _parse_tool_envelope(read)
        rows = envelope.get("rows") or []
        via = [
            row
            for row in rows
            if row.get("start") == "apixaban"
            and row.get("via") == "warfarin"
            and row.get("end") == "aspirin"
        ]
        if not via:
            raise MCPError(
                "read_cypher did not return the apixaban → warfarin → aspirin path; rows=%s"
                % rows
            )
        stats = envelope.get("stats") or {}
        if any(int(stats.get(key) or 0) for key in (
            "nodes_created",
            "nodes_deleted",
            "relationships_created",
            "relationships_deleted",
            "properties_set",
        )):
            raise MCPError("read_cypher reported mutation stats: %s" % stats)

        write = _send(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "write_cypher",
                    "arguments": {
                        "statement": WRITE_STATEMENT,
                        "parameters": {"key": "should-not-be-created"},
                    },
                },
            },
            timeout=timeout,
        )
        assert write is not None
        write_text = _content_text(write)
        write_is_error = bool((write.get("result") or {}).get("isError"))
        # Official wording on a read-only server: unknown tool 'write_cypher'
        # (a tool result with isError true, not a JSON-RPC error).
        if not write_is_error or "unknown tool 'write_cypher'" not in write_text:
            raise MCPError(
                "write_cypher was not refused as unknown on the read-only server: %s"
                % json.dumps(write)[:1000]
            )
    finally:
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except OSError:
                pass
        stderr_chunks: List[str] = []

        def _drain_stderr():
            if proc.stderr is None:
                return
            try:
                data = proc.stderr.read()
            except OSError:
                return
            if data:
                stderr_chunks.append(data)

        drain = threading.Thread(target=_drain_stderr)
        drain.daemon = True
        drain.start()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
            drain.join(timeout=2)
            raise MCPError("MCP server did not exit after stdin was closed.")
        drain.join(timeout=2)
        stderr_text = "".join(stderr_chunks)

    if proc.returncode not in (0, None):
        raise MCPError(
            "relate serve exited %s. stderr:\n%s" % (proc.returncode, stderr_text)
        )

    after = file_fingerprint(store)
    if after != before:
        raise MCPError(
            "Store changed during the read-only MCP smoke test: %s -> %s" % (before, after)
        )

    return {
        "disclaimer": DISCLAIMER,
        "cli": relate,
        "version": version,
        "command": command,
        "server_info": server_info,
        "tools": names,
        "path_rows": via,
        "write_refusal": write_text,
        "store": str(store),
        "store_size": after[0],
        "store_sha256": after[1],
        "stderr": stderr_text.strip(),
        "exit_code": proc.returncode,
    }


def format_report(result: Dict[str, Any]) -> str:
    rows = result["path_rows"]
    sample = rows[0]
    lines = [
        result["disclaimer"],
        "Relate CLI: %s (%s)" % (result["cli"], result["version"]),
        "Command: %s" % " ".join(result["command"]),
        "MCP serverInfo: %s" % json.dumps(result["server_info"], sort_keys=True),
        "tools/list: %s" % ", ".join(result["tools"]),
        "read_cypher path rows: %s (showing first)" % len(rows),
        "  start=%s via=%s end=%s" % (sample.get("start"), sample.get("via"), sample.get("end")),
        "  hop1_section=%s hop1_set_id=%s" % (sample.get("hop1_section"), sample.get("hop1_set_id")),
        "  hop2_section=%s hop2_set_id=%s" % (sample.get("hop2_section"), sample.get("hop2_set_id")),
        "write_cypher refusal: %s" % result["write_refusal"],
        "store unchanged: %s bytes sha256=%s" % (result["store_size"], result["store_sha256"]),
        "relate serve exit: %s" % result["exit_code"],
    ]
    if result.get("stderr"):
        lines.append("stderr:")
        for line in str(result["stderr"]).splitlines():
            lines.append("  %s" % line)
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test read-only Relate MCP over stdio.")
    parser.add_argument(
        "--database",
        default=None,
        help="Path to the .rl store (default: data/labelpath.rl).",
    )
    parser.add_argument(
        "--cli",
        default=None,
        help="Path to the relate executable (default: $RELATE_CLI, PATH, or ~/.local/bin/relate).",
    )
    args = parser.parse_args(argv)
    try:
        result = run_smoke(database=args.database, cli=args.cli)
    except SkipMCP as exc:
        sys.stderr.write("SKIP: %s\n" % exc)
        return SKIP_EXIT
    except MCPError as exc:
        sys.stderr.write("FAIL: %s\n" % exc)
        return 1
    sys.stdout.write(format_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
