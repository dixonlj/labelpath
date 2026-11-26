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

![LabelPath graph schema: Drug, Label, Section, Ingredient and Condition nodes joined by HAS_LABEL, HAS_SECTION, CONTAINS, INDICATED_FOR, CONTRAINDICATED_IN and LABELED_INTERACTION relationships. CONTAINS carries no snippet; the other three source-backed relationships carry source_kind, summary and source_set_id.](docs/img/labelpath-schema.png)

*The diagram was written as HTML/SVG (`docs/img/src/labelpath-schema.html`) and rendered with headless Google Chrome. Its labels, property names, and counts were checked against `scripts/ingest.py` and the committed store.*

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
| `LABELED_INTERACTION` | Drug to another snapshot drug or ingredient named in an interaction-related section (a label mention, not a confirmed clinical finding) |

Path queries walk `LABELED_INTERACTION`, `CONTAINS`, `INDICATED_FOR`, and `CONTRAINDICATED_IN`, at most three hops, shorter paths first. The UI defaults to 2 hops and can be raised to 3; the CLI defaults to 3. Each hop shows a section kind when the hop has one, a snippet when one exists, and a DailyMed link when a `set_id` exists. `CONTAINS` hops come from the structured ingredient list and have no section snippet. A path means label text mentions both names; it is not a pharmacological pathway or a clinical interaction finding.

## Files worth reading next

- `README.md` — pitch, setup, first result, versions
- `DATA.md` — source, attribution, field mapping, known limits
- `docs/MCP.md` — read-only MCP command and host snippets
- `MAC_SETUP.md` — macOS notes
