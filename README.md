# LabelPath

A local, no-server app that turns a snapshot of public FDA drug labels into a Relate graph of labeled connections between drugs, ingredients, indications, contraindications, boxed warnings, and labeled interactions.

**Not medical advice, not for clinical use, and not a substitute for the official label or a licensed clinician.** This is a graph of public label text only. openFDA says: “Do not rely on openFDA to make decisions regarding medical care.” See `DATA.md` for the official wording, terms, and attribution.

Data provided by the U.S. Food and Drug Administration (https://open.fda.gov).

This repository is being built for the Relate by Neo4j hackathon. A curated, offline-queryable snapshot lives in a persistent Relate single-file store, `data/labelpath.rl`. A single `.rl` file is used because it is easy to commit, copy, and inspect. This is not an in-memory-only demo. Milestone 3 adds a read-only query CLI for lookups, bounded paths, warnings, and neighbors. Milestone 4 adds a local single-page UI, served only on 127.0.0.1, that reuses the same query functions.

## Requirements

- Python 3.9 or later (the maintainer’s Mac runs 3.9.6; this project avoids syntax newer than 3.9)
- A project virtualenv
- The official `relate-db==1.1.0` Python package (import `relate`)
- Optional, recommended for judges and agents: the Relate CLI 1.1.0. See `MAC_SETUP.md` for the official installer

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, use `venv\Scripts\Activate.ps1` instead of `source`. This project is developed for macOS, and the official CLI install command differs on Windows; see https://relatedb.ai/docs/get-started/install/.

## Build the graph (offline)

The raw snapshot is already under `data/raw/`. Ingest does not use the network:

```bash
python scripts/ingest.py
python -m pytest
```

`scripts/ingest.py` deletes and rebuilds `data/labelpath.rl`, so it is safe to re-run. It replaces the Milestone 1 toy store.

Success looks like printed node and relationship counts (293 Drug nodes in the 19 November 2026 snapshot), a `data/labelpath.rl` file that still exists after the process exits, and `pytest` passing.

## Refresh the snapshot (network, optional)

Only needed if you want a newer copy of the labels. No API key is used. Already-cached seeds are skipped unless you pass `--force`.

```bash
python scripts/download_snapshot.py
python scripts/ingest.py
```

Details, missed seeds, and field mapping are in `DATA.md`. The seed list is `data/seed_drugs.txt`.

## Query the store

The store is opened **read-only**. Every CLI output includes the line `Educational only, not medical advice.`

From the project root, with the venv active:

```bash
python -m labelpath query lookup "warfarin sodium"
python -m labelpath query path apixaban aspirin --max-hops 3
python -m labelpath query warnings warfarin
python -m labelpath query neighbors protamine
python -m labelpath --json query lookup warfarin
```

- `lookup` finds a drug or ingredient (case-insensitive, tolerant of salt names such as “warfarin sodium”).
- `path` finds labeled paths of at most 3 hops between two names (also `path a b --max-hops 2 --limit 10`). A documented demo path in this snapshot is apixaban to aspirin via warfarin, with a source snippet and section pointer on each hop. There is also a direct apixaban–aspirin edge, and a protamine–heparin edge from protamine’s boxed warning.
- `warnings` prints boxed-warning and contraindications sections for a drug.
- `neighbors` lists adjacent drugs, ingredients, and conditions.

`--json` writes one JSON object to stdout (the same disclaimer is a field in that object, and the disclaimer line is also printed to stderr). `--database PATH` selects a store; the default is `data/labelpath.rl`.

## Local UI

The UI is a single page served by the Python standard library (`http.server`). It binds to **127.0.0.1 only**, opens the store **read-only**, and reuses the same query functions as the CLI. There is no extra package to install.

From the project root, with the venv active:

```bash
python -m labelpath serve --port 8765
```

Then open http://127.0.0.1:8765/ in a browser on the same machine. The page always shows `Educational only, not medical advice.` and the openFDA attribution: “Data provided by the U.S. Food and Drug Administration (https://open.fda.gov).” It also quotes the openFDA caution: “Do not rely on openFDA to make decisions regarding medical care.”

The page has a lookup box, a two-drug path finder (default max 2 hops, shorter paths first, optional 1 or 3), and warnings and neighbors views. Each edge shows its section name, a source snippet, and a DailyMed link when a `set_id` is present. A **Try: apixaban → aspirin** button fills the demo pair and runs the path query. Paths also get a small inline SVG node-and-edge diagram (no CDN).

`?demo=1` on the URL runs that demo pair automatically. Press Ctrl+C in the terminal to stop the server.

The HTTP JSON endpoints are `/api/lookup?q=...`, `/api/path?start=...&end=...`, `/api/warnings?q=...`, `/api/neighbors?q=...`, and `/api/meta`. The path endpoint defaults to `max_hops=2` (the CLI `path` command still defaults to 3). Every JSON response includes the `disclaimer` field.

Do not run `scripts/milestone1_toy.py` against this project if you want to keep the real snapshot; that script would replace `data/labelpath.rl` with the toy graph.

If you have the Relate CLI on your `PATH` (`export PATH="$HOME/.local/bin:$PATH"` if needed), you can also query the same store directly. Bind values as parameters; do not paste user text into a statement:

```bash
relate --database ./data/labelpath.rl --read-only --mode table --param key=warfarin \
  "MATCH (d:Drug {key: $key})-[:HAS_LABEL]->(:Label)-[:HAS_SECTION]->(s:Section) RETURN s.kind AS kind LIMIT 10"
```

## Read-only MCP

Relate’s built-in MCP server can open the same committed store. The command this project documents and smoke-tests is:

```bash
relate serve --mcp stdio --database ./data/labelpath.rl --read-only
```

Opened `--read-only`, the server lists only `read_cypher` and `get_schema`. `write_cypher` is not listed; calling it is refused. Bind Cypher parameters and use `LIMIT`. Details, host-config snippets (a **LIAM STEP** to paste yourself; this repo does not edit Claude Desktop or Cursor config files), and example questions are in `docs/MCP.md`.

With the project venv `venv/` active (not `.venv`):

```bash
python scripts/mcp_smoke.py
```

The smoke test talks JSON-RPC over stdio (no extra Python package). It initializes, lists tools, runs a parameterized apixaban → warfarin → aspirin read, and checks that a write is refused and that `data/labelpath.rl` is unchanged. If the Relate CLI is missing, the script exits 77 and `pytest` skips that test.


## License

Apache-2.0 is planned unless a different encouraged license is chosen later. A license file is not in this milestone yet. Relate itself is Apache-2.0.
