"""Project paths. Compatible with Python 3.9."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SEED_FILE = DATA_DIR / "seed_drugs.txt"
CONDITION_FILE = DATA_DIR / "condition_phrases.txt"
STORE_FILE = DATA_DIR / "labelpath.rl"
MANIFEST_FILE = RAW_DIR / "manifest.json"
MISSED_FILE = RAW_DIR / "missed.txt"
