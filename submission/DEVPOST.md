# Devpost draft — LabelPath

**Status:** draft only. Do not publish, register, or submit until Liam gives an explicit OK.

**Title:** LabelPath

**Tagline** (169 characters, limit 200):

A local Relate graph of public FDA drug labels. Follow labeled paths between drugs, with a source snippet when one exists on a hop. Educational only, not medical advice.

## Built with

Suggested Devpost tags, limited to tools this project actually uses:

- Relate
- Python
- Cypher
- HTML
- CSS
- JavaScript
- pytest
- openFDA

Do not add Neo4j Aura, vector search, Bolt, WebAssembly, or a paid API. Those are not part of this project.

---

Paste the sections below into the Devpost project story. Keep the disclaimer in the first section so it is visible on the project page.

## Inspiration

I work as a blood-bank medical laboratory technician, and I have been teaching myself AI and software in the evenings. Outside of work, I have been curious about a documentation question only: what does the public label text say about how two drugs are connected, or which boxed warning sits on a drug in this snapshot?

I did not want to build a hospital graph, a pathway model, or anything that touched employer, patient, or production data. LabelPath is a local Relate graph of a snapshot of public FDA drug labels. It is educational only, not medical advice, not for clinical use, and not a substitute for the official label or a licensed clinician. openFDA says: “Do not rely on openFDA to make decisions regarding medical care.” Data provided by the U.S. Food and Drug Administration (https://open.fda.gov).

## What it does

LabelPath turns a curated, offline snapshot of public FDA labels into a persistent Relate single-file store, `data/labelpath.rl`. You can look up a drug or ingredient, find labeled paths of at most three hops between two names (shorter paths first; the UI defaults to 2 hops and can be raised to 3, and the CLI defaults to 3), list boxed warnings and contraindication neighbors, and list adjacent drugs, ingredients, and conditions. Every hop shows a section name, a source snippet when one exists, and a DailyMed link when a `set_id` is present.

The 19 November 2026 snapshot (America/New_York) covers 294 seed generic names and found 293 labels (one miss: cholecalciferol, because only combination products were returned). After ingest the store has 2,023 nodes and 4,186 relationships (293 Drug, 293 Label, 1,062 Section, 296 Ingredient, and 79 Condition nodes; 1,907 `LABELED_INTERACTION` edges, plus structural and condition edges). The committed store is 7,139,328 bytes.

A documented demo path in this snapshot is apixaban to aspirin, including a two-hop path via warfarin, with source `set_id` values `41a133ef-e461-48ad-8221-b735bdd0ec25` (apixaban) and `61ab23a7-bc67-4777-854a-bf43c788a69a` (warfarin). There is also a direct apixaban–aspirin labeled-interaction edge. You can run this from a local UI on 127.0.0.1, from `python -m labelpath query`, or through Relate’s official read-only MCP server. The CLI and UI always show the educational disclaimer; official MCP returns raw Cypher results, and the project docs ask every answer to keep the disclaimer line. Extraction is conservative and does not use an LLM.

## How we built it

The project is a new local repository started during the contest period, written for Python 3.9 (the version on my Mac). It uses Relate as an embedded single-file store because one `.rl` file is easy to commit, copy, and inspect.

1. A documented seed list (`data/seed_drugs.txt`) and a polite, unauthenticated download from the official openFDA drug-label API into `data/raw/`.
2. An offline ingest script that rebuilds `data/labelpath.rl` from that cache, with bound Cypher parameters. Condition and interaction edges are created only where a conservative phrase or name match is extractable from structured fields and kept label sections.
3. Read-only query functions and a `python -m labelpath query` CLI for lookup, path, warnings, and neighbors.
4. A local single-page UI served on 127.0.0.1 only (`python -m labelpath serve --port 8765`), using the Python standard library, with an inline SVG path diagram and a **Try: apixaban → aspirin** button.
5. Documentation and a stdio smoke test for Relate’s built-in read-only MCP: `relate serve --mcp stdio --database ./data/labelpath.rl --read-only`. That server lists `read_cypher` and `get_schema`; a `write_cypher` call is refused.

A fresh clone with a new `venv/`, `pip install -r requirements.txt`, `pytest`, a rebuild into a temporary store path, the UI, and the MCP smoke test were checked on a Linux dry-run machine. `pytest` currently reports 34 passed. The rebuilt store matched the committed counts: 2,023 nodes and 4,186 relationships.

## Challenges

The conservative matcher is honest, and that honesty shows up as gaps. The warfarin label in this snapshot talks about “vitamin K,” not the generic name “phytonadione,” so there is no direct `LABELED_INTERACTION` between those two seeds. The heparin label did not name protamine in the scanned sections; protamine’s boxed warning does name heparin. Phrase matches can still fire inside an exception clause: on the warfarin label, “thromboembolism” appears in a sentence about pregnant women with mechanical heart valves, which is not a contraindication to warfarin for thromboembolism. The most recent matching warfarin label is a REMEDYREPACK ANDA record. Salt names such as “warfarin sodium” had to resolve to the Drug node when a query needs a drug, not only the Ingredient.

I also stayed on official Relate docs and flags rather than inventing APIs, kept the code compatible with Python 3.9, and treated the store as read-only on every query surface.

## Accomplishments that I'm proud of

- A judge can clone the repo, install from `requirements.txt`, and get a first result from the committed store without a network call or a paid service.
- The same read-only graph is available from a CLI, a local UI, and official MCP. The CLI and UI always show the disclaimer; official MCP returns raw Cypher results, and the project docs ask every answer to keep the disclaimer line.
- Source-backed paths: the apixaban → warfarin → aspirin demo shows a section name, a snippet, and a DailyMed link on each hop.
- 34 tests passed on the maintainer’s Mac (Python 3.9.6) and in a clean-clone check (Python 3.9.25), including JSON UI endpoints and an MCP smoke test that refuses writes.
- The project uses only public openFDA data. No employer, patient, or hospital records were used.

## What I learned

I learned how to persist a real Relate single-file store, query it with bound Cypher parameters, and open it read-only for a UI and for MCP. I also learned that “the label said something nearby” is not the same as a clean structured relationship, which is why the limitations are documented in `DATA.md` instead of being smoothed over.

## What's next

This submission is meant to be a complete, cloneable graph demo, not a clinical product. If I keep going after the contest, I would use the documented read-only MCP from an agent host on my own machine, and I would only widen the snapshot or tighten matching where the current limits are explicit. I do not plan to turn LabelPath into a decision-support tool.

---

**Devpost field notes (for Liam):** paste the title and tagline into the corresponding fields. Paste the story sections into Inspiration through What's next. Add the Built with tags above. The GitHub repo is https://github.com/dixonlj/labelpath. Attach that link on Devpost, and attach the video only after that LIAM STEP is done. Include a screenshot from `docs/screenshots/` if useful, and do not crop out the disclaimer.
