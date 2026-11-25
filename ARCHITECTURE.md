# LabelPath architecture

A short map of the local app. The run steps, disclaimer, and data caveats live in `README.md` and `DATA.md`.

## Layout

```
data/raw/*.json          offline openFDA snapshot (293 labels)
        │
        ▼
scripts/ingest.py        writes (or replaces) a Relate single-file store
        │
        ▼
data/labelpath.rl        committed persistent store (default path)
        │
        ▼
labelpath/query.py       read-only Cypher helpers (lookup, paths, warnings, neighbors)
        │
        ├── python -m labelpath query …     CLI
        ├── python -m labelpath serve …     local UI on 127.0.0.1
        └── relate serve --mcp stdio …      official read-only MCP server
```

Ingest is the only writer in this project. It opens the target `.rl` file for writing, builds the graph in one transaction, and closes it. Every later surface calls `relate.connect(path, read_only=True)` or `relate serve … --read-only`. Queries bind Cypher parameters; they do not interpolate user text into statements.

The UI (`labelpath/serve.py`) is a standard-library HTTP server that binds 127.0.0.1 only and reuses `labelpath.query`. MCP is not a second implementation: the host starts the official Relate command documented in `docs/MCP.md`.

## Graph model

From the 19 November 2026 snapshot (2,023 nodes, 4,186 relationships):

| Nodes | What they represent |
| --- | --- |
| `Drug` | One node per seed that has a cached label (`key` is the normalized seed name) |
| `Label` | The chosen openFDA record (`set_id`, `effective_time`, constructed DailyMed `source_url`) |
| `Section` | Joined text of a kept label section (`kind`, `text`) |
| `Ingredient` | An `openfda.substance_name` value |
| `Condition` | A phrase from `data/condition_phrases.txt` that matched conservatively |

| Relationships | Meaning |
| --- | --- |
| `HAS_LABEL` | Drug to its snapshot label |
| `HAS_SECTION` | Label to a section |
| `CONTAINS` | Drug to an ingredient from the structured substance list |
| `INDICATED_FOR` | Drug to a condition phrase found in `indications_and_usage` |
| `CONTRAINDICATED_IN` | Drug to a condition phrase found in `contraindications` |
| `LABELED_INTERACTION` | Drug to another snapshot drug or ingredient named in an interaction-related section |

Path queries walk `LABELED_INTERACTION`, `CONTAINS`, `INDICATED_FOR`, and `CONTRAINDICATED_IN`, at most three hops, shorter paths first. Each hop carries a section kind, a snippet when one exists, and a DailyMed link when a `set_id` is present.

## Files worth reading next

- `README.md` — pitch, setup, first result, versions
- `DATA.md` — source, attribution, field mapping, known limits
- `docs/MCP.md` — read-only MCP command and host snippets
- `MAC_SETUP.md` — macOS notes
