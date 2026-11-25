# LabelPath data notes

This file describes the public FDA label snapshot used to build `data/labelpath.rl`. It is not medical advice.

**Not medical advice, not for clinical use, and not a substitute for the official label or a licensed clinician.** LabelPath is a graph of public label text only.

## Source

- Dataset: openFDA drug labeling API
- Endpoint: https://api.fda.gov/drug/label.json
- Documentation: https://open.fda.gov/apis/drug/label/
- Field definitions: https://open.fda.gov/fields/druglabel.yaml
- Query parameters: https://open.fda.gov/apis/query-parameters/
- Authentication and rate limits: https://open.fda.gov/apis/authentication/
- Terms of service: https://open.fda.gov/terms/

No API key was used for this snapshot. The official authentication page lists unauthenticated limits of 240 requests per minute and 1,000 requests per day, per IP address. The downloader waits 0.5 seconds between requests and caches each seed’s chosen record under `data/raw/`.

## Attribution

From the openFDA terms of service (https://open.fda.gov/terms/), under “Attribution”:

> Data provided by the U.S. Food and Drug Administration (https://open.fda.gov)

The same terms page says that, unless otherwise noted, openFDA content is public domain with a Creative Commons CC0 1.0 Universal dedication, and that some third-party works may be limited. This project uses the public drug-label API records described above and attributes them anyway.

## Official “do not rely on this for medical care” wording

openFDA states this in more than one place. Both wordings below are quoted from official pages fetched on 19 November 2026 (America/New_York).

From the Drug Labeling overview, “Responsible use of the data” (https://open.fda.gov/apis/drug/label/):

> Do not rely on openFDA to make decisions regarding medical care. Always speak to your health provider about the risks and benefits of FDA-regulated products. We may limit or otherwise restrict your access to the API in line with our Terms of Service.

From every API response `meta.disclaimer`, which matches the example on https://open.fda.gov/apis/drug/label/understanding-the-api-results/:

> Do not rely on openFDA to make decisions regarding medical care. While we make every effort to ensure that data is accurate, you should assume all results are unvalidated. We may limit or otherwise restrict your access to the API in line with our Terms of Service.

The overview page also includes a longer “Disclaimer” about reformatted SPL content, OTC monograph products, and unapproved drugs. Read that page for the full text.

## Retrieval date

- Snapshot retrieved: **19 November 2026 (America/New_York)**
- Stored on each cached file as `retrieved_at`, and in `data/raw/manifest.json`
- The openFDA `meta.last_updated` value observed on those responses was `2026-11-19`

Re-running `scripts/download_snapshot.py` skips seeds that already have a cached file unless you pass `--force`.

## Seed list summary

The seed list is `data/seed_drugs.txt`. It is a seed list of generic names used as openFDA search terms, **not medical advice**, not a formulary, and not a complete drug list.

- 294 unique generic names
- 293 labels found and cached under `data/raw/`
- 1 missed: **cholecalciferol**. Searches returned only combination products (for example vitamins plus cholecalciferol, or alendronate sodium and cholecalciferol). The matcher rejects combination `generic_name` values that include `and`, so no standalone cholecalciferol label was kept. See `data/raw/missed.txt`.

The list includes a lab-relevant core (anticoagulants and DOACs, phytonadione, protamine, idarucizumab, antifibrinolytics, iron products, epoetin alfa and related supportive agents, and common antibiotics) plus everyday and chronic outpatient medicines so the graph has overlap.

## How one label was chosen per drug

For each seed, the downloader requested:

`https://api.fda.gov/drug/label.json?search=openfda.generic_name:"<seed>"&sort=effective_time:desc&limit=25`

It kept the most recent record (by `effective_time`, official format `YYYYmmdd`) whose `openfda.generic_name` matched the seed after conservative normalization (lowercase; trailing salt, ester, or dose-form tokens such as sodium, hydrochloride, tosylate, or acetonide; trailing biosimilar `-xxxx` suffixes). Combination products were not treated as a match for a single-ingredient seed.

If that newest match had none of the kept section fields, the newest match that did have at least one kept section was used instead. The most recent label can be a repackaged product; the warfarin snapshot record, for example, is a REMEDYREPACK ANDA label that still includes the boxed warning, indications, contraindications, interactions, and warnings-and-cautions sections.

Only a trimmed record is stored: `set_id`, `id`, `effective_time`, the kept sections, and `openfda.generic_name`, `openfda.brand_name`, `openfda.substance_name`, and `openfda.application_number`.

## Field mapping

Official field names and descriptions below come from https://open.fda.gov/fields/druglabel.yaml and from live API records. Section fields are arrays of strings in the API; ingest joins them into one `Section.text` value.

| Stored / graph field | openFDA field | Official description (abridged) |
| --- | --- | --- |
| `Label.set_id` | `set_id` | “The Set ID, A globally unique identifier (GUID) for the labeling, stable across all versions or revisions.” |
| (kept in raw JSON) | `id` | “The document ID, A globally unique identifier (GUID) for the particular revision of a labeling document.” |
| `Label.effective_time` | `effective_time` | “Date reference to the particular version of the labeling document.” Format `YYYYmmdd`. |
| `Drug.generic_name` | `openfda.generic_name` | “Generic name(s) of the drug product.” |
| `Drug.brand_names` | `openfda.brand_name` | “Brand or trade name of the drug product.” |
| `Ingredient.name` via `CONTAINS` | `openfda.substance_name` | “The list of active ingredients of a drug product.” |
| `Drug.application_numbers` | `openfda.application_number` | NDA, ANDA, or BLA number (or monograph citation) reported by the labeler. |
| `Section` kind `indications_and_usage` | `indications_and_usage` | A statement of the product’s indications for use; “This field may also describe any relevant limitations of use.” |
| `Section` kind `contraindications` | `contraindications` | Situations in which the product is contraindicated or should not be used because the risk clearly outweighs any possible benefit. |
| `Section` kind `boxed_warning` | `boxed_warning` | “Information about contraindications or serious warnings, particularly those that may lead to death or serious injury.” |
| `Section` kind `drug_interactions` | `drug_interactions` | Practical guidance on preventing clinically significant drug/drug and drug/food interactions. |
| `Section` kind `warnings_and_cautions` | `warnings_and_cautions` | Present on many prescription labels. The official YAML currently says “Documentation forthcoming.” |

`Label.source_url` is not an openFDA field. It is built from `set_id` as the public DailyMed page `https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={set_id}`, which was checked against the warfarin `set_id` in this snapshot.

## Graph construction (no LLM)

Ingest (`scripts/ingest.py`) reads only `data/raw/` and does not use the network. It deletes and rebuilds `data/labelpath.rl` in one Relate transaction, so re-running is safe.

- `(:Drug {key, generic_name, brand_names, application_numbers})` — one node per seed that has a cached label. `key` is the normalized seed name.
- `(:Label {set_id, effective_time, source_url})` and `(Drug)-[:HAS_LABEL]->(Label)-[:HAS_SECTION {kind}]->(:Section {kind, text})`.
- `(:Ingredient {key, name})` from `openfda.substance_name`, with `(Drug)-[:CONTAINS]->(Ingredient)`.
- `(:Condition {key, name})` only when a phrase from the documented list in `data/condition_phrases.txt` appears as a whole-phrase, word-boundary match. Longer phrases win over overlapping shorter ones (so “malignant hypertension” is not also stored as “hypertension”). `(Drug)-[:INDICATED_FOR {source_set_id, source_kind, summary}]->(Condition)` is created only from `indications_and_usage`. `(Drug)-[:CONTRAINDICATED_IN {source_set_id, source_kind, summary}]->(Condition)` is created only from `contraindications`. This is a conservative phrase list, not a medical ontology.
- `(Drug)-[:LABELED_INTERACTION {summary, source_set_id, source_kind, matched_name}]->(Drug|Ingredient)` only when an interaction-related section (`drug_interactions`, `contraindications`, `boxed_warning`, or `warnings_and_cautions`) names another snapshot drug or ingredient with a word-boundary match. A drug is not linked to itself, and is not linked to its own ingredients. The relationship properties point back to the source section.

Known limits of this conservative matching, observed in this snapshot:

- The warfarin label discusses “vitamin K,” not the generic name “phytonadione,” so no direct `LABELED_INTERACTION` was created between those two seeds.
- The heparin label in this snapshot did not name protamine in the scanned sections; the protamine boxed warning does name heparin.
- Phrase matches in contraindications can still fire inside an exception clause. On the warfarin label, “thromboembolism” appears in the sentence about pregnant women with mechanical heart valves who remain at high risk of thromboembolism, which is not a contraindication to warfarin for thromboembolism.

## Snapshot built on 19 November 2026 (America/New_York)

After ingest of the 293 cached labels:

| Nodes | Count | Relationships | Count |
| --- | ---: | --- | ---: |
| Drug | 293 | HAS_LABEL | 293 |
| Label | 293 | HAS_SECTION | 1062 |
| Section | 1062 | CONTAINS | 298 |
| Ingredient | 296 | INDICATED_FOR | 426 |
| Condition | 79 | CONTRAINDICATED_IN | 200 |
| **Total nodes** | **2023** | LABELED_INTERACTION | 1907 |
|  |  | **Total relationships** | **4186** |

Sizes on the Linux dry-run machine (a Mac may differ by a few bytes, but should be in the same range):

- `data/raw/` (293 trimmed label JSON files, plus `manifest.json` and `missed.txt`): 3,570,889 bytes (~3.4 MiB; `du -sh` reported 4.1M)
- `data/labelpath.rl` (Relate single-file store): 7,139,328 bytes (6.9M as reported by `du -sh`)

The single-file `.rl` layout is used because one file is easy to commit, copy, and inspect, and judges can query it offline with the Relate CLI or the Python client.
