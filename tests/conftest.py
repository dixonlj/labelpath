from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STORE = ROOT / "data" / "labelpath.rl"


@pytest.fixture(scope="session")
def store_path():
    if not STORE.is_file():
        pytest.skip("data/labelpath.rl is missing; run python scripts/ingest.py first")
    return STORE


@pytest.fixture(scope="session")
def conn(store_path):
    import relate

    connection = relate.connect(str(store_path), read_only=True)
    yield connection
    connection.close()
