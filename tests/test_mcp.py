"""Read-only MCP smoke tests. Skipped if the Relate CLI is not installed."""
from __future__ import annotations

import importlib.util
from pathlib import Path

from labelpath.query import DISCLAIMER

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "labelpath_mcp_smoke", ROOT / "scripts" / "mcp_smoke.py"
)
assert _SPEC is not None and _SPEC.loader is not None
mcp_smoke = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mcp_smoke)


def test_mcp_initialize_list_path_and_refuse_write(store_path):
    if mcp_smoke.find_relate_cli() is None:
        import pytest

        pytest.skip("Relate CLI is not installed; MCP smoke test skipped.")
    try:
        result = mcp_smoke.run_smoke(database=str(store_path))
    except mcp_smoke.SkipMCP as exc:
        import pytest

        pytest.skip(str(exc))
    except mcp_smoke.MCPError as exc:
        raise AssertionError(str(exc))

    assert result["disclaimer"] == DISCLAIMER
    assert result["tools"] == ["read_cypher", "get_schema"]
    assert "write_cypher" not in result["tools"]
    assert result["server_info"].get("name") == "relate-mcp"
    assert result["path_rows"]
    assert all(
        row["start"] == "apixaban" and row["via"] == "warfarin" and row["end"] == "aspirin"
        for row in result["path_rows"]
    )
    assert "unknown tool 'write_cypher'" in result["write_refusal"]
    assert result["exit_code"] == 0
