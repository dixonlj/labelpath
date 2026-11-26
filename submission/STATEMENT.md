# Statement of Relate capabilities, third-party tools, and AI use

**Status:** draft only. This is the statement Official Rules Section 4 require: “which Product capabilities, third-party tools, and AI tools the project uses.” Paste or attach it on the Devpost submission. Do not submit until Liam gives an explicit OK.

**Educational only, not medical advice.** LabelPath is not for clinical use and is not a substitute for the official label or a licensed clinician.

## Relate capabilities used

LabelPath makes meaningful use of Relate as an embedded, persistent graph, not only as a mention in the README.

- **Embedded Python client** (`relate-db==1.1.0`, `import relate`): `scripts/ingest.py` writes the store; `labelpath/query.py` and the tests open it.
- **Single-file store mode:** the committed persistent store is `data/labelpath.rl` (7,139,328 bytes after the 19 November 2026 ingest). A single file was chosen because it is easy to commit, copy, and inspect. This is not an in-memory-only demo.
- **Cypher via Python, with bound parameters:** lookups, bounded path queries, warnings, and neighbors all run as parameterized Cypher. User text is not interpolated into statements. Path queries are at most three hops, shorter first. The UI defaults to 2 hops and can be raised to 3; the CLI defaults to 3. A path means label text mentions both names; it is not a pharmacological pathway or a clinical interaction finding. In prose, a `LABELED_INTERACTION` is a label mention, not a confirmed clinical finding.
- **Read-only open:** every query surface uses `relate.connect(path, read_only=True)` or `relate serve … --read-only`.
- **Relate CLI (optional for judges):** documented one-liners against `data/labelpath.rl`, and the MCP command below. The maintainer’s Mac has Relate CLI v1.1.0. The official installer installed CLI v1.3.0 on a Linux dry-run machine on 25 November 2026. The committed store, written with `relate-db==1.1.0`, opened read-only under CLI v1.3.0. Write or migration compatibility with CLI v1.3.0 was not tested.
- **MCP:** the official server, started as `relate serve --mcp stdio --database ./data/labelpath.rl --read-only`. Opened read-only, `tools/list` returns `read_cypher` and `get_schema`. A `write_cypher` call is refused with `unknown tool 'write_cypher'`. This project does not start a writable MCP server and does not start MCP over HTTP. Official MCP output carries no disclaimer, so hosts must add it. The CLI and UI always show the disclaimer.

This project does **not** use vector search, Bolt, the HTTP Query API, WebAssembly, or a connection to Neo4j or Aura.

## Third-party tools and data

- **Relate** / `relate-db` and the Relate CLI (Apache License 2.0): the embedded store, Cypher, the official CLI, and the official MCP server. Relate itself is not a paid service and needs no account.
- **pytest 8.4.2:** the test runner (34 tests passed on the maintainer’s Mac and in a clean-clone check, with the Relate CLI installed). Without the CLI, the MCP smoke test in `tests/test_mcp.py` is skipped.
- **Python 3.9** and the Python standard library: the local UI (`http.server`, HTML, CSS, and JavaScript with no CDN) and the MCP stdio smoke test. No extra UI package is required.
- **Headless Google Chrome:** rendered the graph-schema diagram and the 3:2 thumbnail from hand-written HTML/SVG (sources in `docs/img/src/`), and captured the UI screenshots in `docs/img/`.
- **ElevenLabs text-to-speech:** generated a draft demo voiceover (stock voice “Reid - E-Learning Instructor”, model `eleven_multilingual_v2`, 90.6 seconds) from my own video script, on 26 November 2026, under my existing ElevenLabs plan. The audio file is not committed to the repo. If it is used in the video, the voiceover is synthetic.
- **openFDA drug labeling API** (https://open.fda.gov/apis/drug/label/): the dataset. The committed snapshot was retrieved on 19 November 2026 (America/New_York) with no API key, under the official unauthenticated limits. Field mapping and limitations are in `DATA.md`.

**Attribution**, from the openFDA terms of service (https://open.fda.gov/terms/): “Data provided by the U.S. Food and Drug Administration (https://open.fda.gov).” Those terms also say that, unless otherwise noted, openFDA content is public domain with a Creative Commons CC0 1.0 Universal dedication, and that some third-party works may be limited. This project uses the public drug-label records described in `DATA.md` and attributes them anyway.

openFDA also states: “Do not rely on openFDA to make decisions regarding medical care.” The constructed DailyMed `source_url` on each label is not an openFDA field; it is built from `set_id`.

There are no required paid services, no committed `.env`, and no employer, patient, or hospital data in the project.

## Significant AI use

AI-assisted development was used, in Cursor, to scaffold and implement the project: the local layout and Relate install dry run, the snapshot and ingest scripts, the query CLI, the local UI, the MCP documentation and smoke test, the judge-ready README, and this submission pack. I remain responsible for the result, including originality and license compliance.

The demo voiceover audio was generated with ElevenLabs text-to-speech from my script; the schema diagram and thumbnail were made as hand-written HTML/SVG rendered with headless Google Chrome. Graph extraction did **not** use an LLM. Edges come from structured openFDA fields and conservative, deterministic phrase and name matching. The dated log is in `AI_USE.md`. No patient, employer, or hospital data was used in any AI-assisted step.
