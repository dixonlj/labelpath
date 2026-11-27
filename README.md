# LabelPath

A local Relate graph of public FDA drug labels, so you can follow labeled connections between drugs, ingredients, and conditions — with a source snippet when one exists on a hop.

**Educational only, not medical advice.** Not for clinical use, and not a substitute for the official label or a licensed clinician. This is a graph of public label text only. openFDA says: “Do not rely on openFDA to make decisions regarding medical care.” Always speak to your health provider about the risks and benefits of FDA-regulated products. Data provided by the U.S. Food and Drug Administration (https://open.fda.gov). See [DATA.md](DATA.md) for the official wording, terms, and attribution.

## How LabelPath works

![How LabelPath works: public FDA drug labels are turned into connected facts on your computer, then a question such as whether apixaban's label mentions aspirin is answered with a quote from the label and its source.](docs/img/labelpath-flow.png)

*From public FDA drug labels to a sourced answer. Public openFDA data - educational only, not medical advice.*

### Try it in 60 seconds

From a clean clone, in the project root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m labelpath serve --port 8765
```

Open http://127.0.0.1:8765/ and click **Try: apixaban → aspirin**. Full setup, tests, and CLI notes are below.

## Use case

LabelPath is for a person or an agent who wants to see *what the public label text actually says* about how two snapshot drugs are connected, or what boxed warnings and contraindication neighbors a drug has, without opening a hospital system or calling a remote database. It solves a documentation problem, not a clinical one: the interesting relationships are `LABELED_INTERACTION` edges (a label mention in an interaction-related section), ingredients a product contains, and conservatively phrase-matched indications and contraindications. `INDICATED_FOR`, `CONTRAINDICATED_IN`, and `LABELED_INTERACTION` point back to a source section and a snippet when those exist, and to a DailyMed page when a `set_id` exists; `CONTAINS` comes from the structured ingredient list and has no section snippet. A path means label text in this snapshot mentions both names; it is not a pharmacological pathway or a clinical interaction finding. A typical first result is the path from apixaban to aspirin, including a two-hop path via warfarin; on that documented demo path, each hop has a section name, a snippet, and a DailyMed link. A second checked example is clopidogrel → omeprazole → methotrexate (see below).

## How it uses Relate

LabelPath uses Relate as an **embedded, single-file graph store** that is written once during ingest and then opened **read-only** for every query surface.

- **Mode:** single file (`data/labelpath.rl`)
- **Why this mode:** one `.rl` file is easy to commit, copy, and inspect. Judges can query the committed store offline with the Python client or the Relate CLI. This is not an in-memory-only demo; the file remains after the process exits.
- **What the graph models:** public FDA label text for a curated snapshot of 293 drugs (294 seed names; one miss). Nodes are `Drug`, `Label`, `Section`, `Ingredient`, and `Condition`. Relationships are `HAS_LABEL`, `HAS_SECTION`, `CONTAINS`, `INDICATED_FOR`, `CONTRAINDICATED_IN`, and `LABELED_INTERACTION` (a label mention, not a confirmed clinical finding). A fuller map is in [ARCHITECTURE.md](ARCHITECTURE.md) and [DATA.md](DATA.md).

Relate capabilities this project actually uses, and where:

| Capability | Where it is used |
| --- | --- |
| Embedded Python client (`relate-db==1.1.0`, `import relate`) | `scripts/ingest.py` writes the store; `labelpath/query.py` and tests open it |
| Cypher via Python, with bound parameters | All lookups, path queries, warnings, and neighbors |
| Read-only open (`relate.connect(path, read_only=True)`) | The query library, CLI, local UI, and tests |
| Relate CLI | Optional documented one-liners, and MCP |
| MCP (`relate serve --mcp stdio --database ./data/labelpath.rl --read-only`) | Official Relate MCP server; listed tools are `read_cypher` and `get_schema` |

This project does **not** use vector search, Bolt, the HTTP Query API, WebAssembly, or a pull from Neo4j/Aura.

## Setup and run

Prerequisites:

- Python 3.9 or later (developed on Python 3.9.6; also checked on 3.9.25). The code avoids syntax newer than 3.9.
- A project virtualenv named `venv/` (this repo uses `venv/`, not `.venv`).
- The packages in `requirements.txt` (`relate-db==1.1.0` and `pytest==8.4.2`).
- Optional, for MCP and Relate CLI one-liners: the official Relate CLI. Install from https://relatedb.ai/docs/get-started/install/ :

```bash
curl -sSfL https://relatedb.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
relate --version
```

From a clean clone, in the project root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest
python -m labelpath serve --port 8765
```

`python -m pytest` should end with `34 passed`. If the Relate CLI is not installed, the MCP smoke test is skipped and the remaining tests still pass.

On Windows PowerShell, use `venv\Scripts\Activate.ps1` instead of `source`. This project is developed for macOS; macOS notes are in [MAC_SETUP.md](MAC_SETUP.md). The official CLI install command differs on Windows (see the install page above).

Open http://127.0.0.1:8765/ on the same machine and click **Try: apixaban → aspirin**, or add `?demo=1` to the URL. The UI binds to **127.0.0.1 only**, opens the store read-only, and always shows the educational disclaimer and openFDA attribution. The UI defaults to 2 hops and can be raised to 3. Stop the server with Ctrl+C.

CLI (venv active, from the project root). Every command prints `Educational only, not medical advice.` The CLI path command defaults to 3 hops.

```bash
python -m labelpath query lookup "warfarin sodium"
python -m labelpath query path apixaban aspirin --max-hops 3
python -m labelpath query warnings warfarin
python -m labelpath query neighbors protamine
```

`--json` writes one JSON object to stdout (the disclaimer is a field in that object, and the line is also printed to stderr). `--database PATH` selects a store; the default is `data/labelpath.rl`.

If the Relate CLI is on your `PATH`, you can query the same store directly. Bind values as parameters; do not paste user text into a statement:

```bash
relate --database ./data/labelpath.rl --read-only --mode table --param key=warfarin \
  "MATCH (d:Drug {key: $key})-[:HAS_LABEL]->(:Label)-[:HAS_SECTION]->(s:Section) RETURN s.kind AS kind LIMIT 10"
```

Read-only MCP, including host-config snippets and example questions, is documented in [docs/MCP.md](docs/MCP.md). Official MCP output carries no disclaimer, so hosts must add it. A stdlib smoke test is `python scripts/mcp_smoke.py` (skipped by pytest if the CLI is missing).

Current UI screenshots are in [docs/img/](docs/img/). An older Linux capture remains in `docs/screenshots/`.

### Second example: clopidogrel → omeprazole → methotrexate

Another path checked against the committed store with read-only queries (26 November 2026). In the UI, type `clopidogrel` and `methotrexate`, keep the default 2 hops, and click **Find paths**. Path 1 goes through a shared condition (`anaphylaxis`, from two contraindication sections). Path 2 is two `LABELED_INTERACTION` hops, each a label mention with a section name, a snippet, and a DailyMed `set_id`. In this snapshot there is no direct clopidogrel–methotrexate edge. Stored snippets are truncated, so they can start or end mid-word.

1. clopidogrel → omeprazole, section `drug_interactions`, label `set_id` `55731d95-0c99-ff61-e063-6394a90a1ab5`: “...sma concentrations of the active metabolite of clopidogrel and a reduction in platelet inhibition [ see Warnings and Precautions ( 5.1 ) ]. Omeprazole or Esomeprazole Avoid concomitant use of clopidogrel with omeprazole or esomeprazole. In clinical studies, omeprazole was shown to reduce s...”
2. omeprazole → methotrexate, section `drug_interactions`, label `set_id` `e235ef89-3592-4ca1-8c13-d7ce84b1001c`. The omeprazole label's section 7.7 notes reports of this, mostly at high methotrexate doses. The stored snippet is the label's highlights line that points to 7.7: “...CYP2C19 and 3A4 (e.g. voriconazole) may raise omeprazole levels (7.3) Tacrolimus: omeprazole may increase serum levels of tacrolimus (7.4) Methotrexate: Omeprazole may increase serum levels of methotrexate ( 7.7 ) 7.1 Interference with Antiretroviral Therapy Concomitant use of atazanavir an...”

As with the first example, a path means the label text mentions both names. It is not a pharmacological pathway or a clinical interaction finding. Educational only, not medical advice.

## Screenshots and diagram

Current screenshots of the local UI live in [docs/img/](docs/img/), captured on 27 November 2026 (America/New_York) on the maintainer's Mac against the read-only server on 127.0.0.1:8765. The disclaimer banner is visible in each. The UI can list the same route more than once when a hop has more than one source section (one edge per section). That is expected.

| | |
| --- | --- |
| ![LabelPath home page with the disclaimer banner](docs/img/01-home.png) | ![Apixaban to aspirin: Path 3, apixaban to warfarin to aspirin](docs/img/02-path-apixaban-aspirin.png) |
| ![Clopidogrel to methotrexate: Path 2 via omeprazole](docs/img/03-path-clopidogrel-methotrexate.png) | ![Boxed warning and contraindication snippets for warfarin](docs/img/04-warnings-warfarin.png) |

The flow diagram (`docs/img/labelpath-flow.png`), the schema diagram, and the 3:2 thumbnail (`docs/img/labelpath-schema.png`, `docs/img/labelpath-thumbnail.png`) were made as hand-written HTML/SVG rendered with headless Google Chrome; the sources are in `docs/img/src/`.

## Architecture

![LabelPath graph schema: Drug, Label, Section, Ingredient and Condition nodes joined by HAS_LABEL, HAS_SECTION, CONTAINS, INDICATED_FOR, CONTRAINDICATED_IN and LABELED_INTERACTION relationships. CONTAINS carries no snippet; the other three source-backed relationships carry source_kind, summary and source_set_id.](docs/img/labelpath-schema.png)

*Graph schema, checked against the live store (counts from the 19 November 2026 snapshot). A relationship named LABELED_INTERACTION is a label mention, not a clinical finding. Educational only, not medical advice.*

## Where the data lives

- **Persistent Relate store (committed, query this first):** `data/labelpath.rl`. On the Linux dry-run machine this file was 7,139,328 bytes after ingest. The snapshot it holds was built on 19 November 2026 (America/New_York) from 293 cached labels: **2,023 nodes** and **4,186 relationships**.
- **Offline source snapshot:** `data/raw/` (293 trimmed label JSON files, plus `manifest.json` and `missed.txt`). Ingest does not use the network:

```bash
python scripts/ingest.py
```

`scripts/ingest.py` deletes and rebuilds its target store, so it is safe to re-run, but it will replace `data/labelpath.rl` unless you pass another path:

```bash
python scripts/ingest.py --database /tmp/labelpath-rebuilt.rl
```

Do not run `scripts/milestone1_toy.py` against this project if you want to keep the real snapshot; that script would replace `data/labelpath.rl` with the toy graph.

Refreshing the snapshot (`python scripts/download_snapshot.py`) is optional, uses the network, and needs no API key. Already-cached seeds are skipped unless you pass `--force`. Details are in [DATA.md](DATA.md). The seed list is `data/seed_drugs.txt`.

## Known limitations and caveats

Extraction is conservative and does **not** use an LLM. Condition edges exist only when a phrase from `data/condition_phrases.txt` appears as a whole-phrase, word-boundary match. Longer phrases win over overlapping shorter ones (so “malignant hypertension” is not also stored as “hypertension”). This is not a medical ontology.

Observed gaps and quirks in this snapshot, also listed in [DATA.md](DATA.md):

- The warfarin label discusses “vitamin K,” not the generic name “phytonadione,” so there is no direct `LABELED_INTERACTION` between those two seeds.
- The heparin label in this snapshot did not name protamine in the scanned sections; the protamine boxed warning does name heparin.
- Phrase matches in contraindications can still fire inside an exception clause. On the warfarin label, “thromboembolism” appears in a sentence about pregnant women with mechanical heart valves who remain at high risk of thromboembolism, which is not a contraindication to warfarin for thromboembolism, so contraindication neighbors can be wrong.
- The most recent matching label can be a repackaged product. The warfarin snapshot record is a REMEDYREPACK ANDA label that still includes the boxed warning, indications, contraindications, interactions, and warnings-and-cautions sections.
- One seed was missed: **cholecalciferol**. Searches returned only combination products, which the matcher does not treat as a single-ingredient match. See `data/raw/missed.txt`.

## Data source and attribution

The graph is built from the public openFDA drug labeling API (https://open.fda.gov/apis/drug/label/). Data provided by the U.S. Food and Drug Administration (https://open.fda.gov). Field mapping, retrieval date, and the official “do not rely on this for medical care” quotations are in [DATA.md](DATA.md).

`Label.source_url` is not an openFDA field; it is constructed from `set_id` as the public DailyMed page.

## Versions

- Python package pin: `relate-db==1.1.0` in `requirements.txt` (the version used to write and query the committed store).
- Relate CLI: the maintainer’s Mac still has **v1.1.0**. The official installer (`curl -sSfL https://relatedb.ai/install.sh | bash`) installed **v1.3.0** on a Linux dry-run machine on 25 November 2026. If your `relate --version` is newer than a docs page was verified against, follow that version’s changelog: https://relatedb.ai/docs/reference/changelog/
- Compatibility check: the committed `data/labelpath.rl` (written with `relate-db==1.1.0`) opened **read-only** under Relate CLI v1.3.0 (`relate serve --mcp stdio --database … --read-only`, and a CLI count query). This project does not start a writable CLI 1.3.0 session against that store, and it does not claim write or migration compatibility that has not been tested.
- Tests: `pytest==8.4.2` (pytest 9 requires Python 3.10+).

## Third-party tools

- [Relate](https://relatedb.ai/) / `relate-db` and the Relate CLI (Apache License 2.0): the embedded store, Cypher, the official CLI, and the official MCP server.
- [pytest](https://pytest.org/) 8.4.2: the test runner.
- [openFDA](https://open.fda.gov/) drug-label records: the dataset. Attribution is in [DATA.md](DATA.md).
- The local UI and the MCP smoke test use the Python standard library only (no extra package, no CDN).
- [Inter](https://rsms.me/inter/) typeface (SIL Open Font License 1.1, license text in `labelpath/static/fonts/Inter-OFL.txt`): a Latin subset is bundled and served locally for the UI, so no font CDN is needed.
- Headless Google Chrome: rendered the hand-written HTML/SVG flow diagram, schema diagram, and thumbnail to PNG, and captured the UI screenshots.
- ElevenLabs text-to-speech: the draft demo voiceover audio (not committed).

There are no required paid services, no committed `.env`, and no API key in this snapshot.

## AI use

AI-assisted development was used for scaffolding and implementation. A draft demo voiceover was generated with ElevenLabs text-to-speech from my own script (the audio file is not in this repo). Graph extraction did not use an LLM. No patient, employer, or hospital data was used. The dated log is in [AI_USE.md](AI_USE.md).

## License

Copyright 2026 Liam Dixon. This project is licensed under the Apache License 2.0. See [LICENSE](LICENSE). Relate itself is also Apache-2.0.
