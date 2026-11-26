# Submission checklist — LabelPath

Draft only. **Publish, push, register, and submit nothing** until Liam gives a separate, explicit OK for each of those actions. Official Rules control if they conflict with the Devpost overview (Official Rules, Section 1). This list was checked against https://relate.devpost.com/rules as fetched on 25 November 2026 (America/New_York), including the 13 November 2026 topic-tag update and the 24 November 2026 updates to Section 5 (point values) and Section 8 (brand guidelines; do not modify the Relate logo or mascot).

**Deadline:** Friday, 11 December 2026, **9:00 PM ET** (America/New_York) / **6:00 PM PST**. That is the official Contest-page time. Submissions after that time will not be accepted. **Safe cutoff: 12:00 PM noon ET that same day**, so a missing GitHub topic, README typo, or video-link problem can still be fixed. Do not count on the rules’ “reasonable period” to add a missing `relate` topic after you submit.

Judging is 12–16 December 2026; winners are announced 17 December 2026. Official Rules Section 5 (as updated 24 November 2026, confirmed at https://relate.devpost.com/rules) scores each eligible entry out of 100 points: Relate and connected context (30 points), Functionality and completeness (25 points), Usefulness (20 points), Documentation and reproducibility (15 points), and Creativity (10 points).

---

## Official Rules and overview requirements

| Requirement | Source | Status |
| --- | --- | --- |
| New project started on or after 11 November 2026; do not submit a pre-existing repo. Reused code must be disclosed; only contest-period work is judged | Official Rules §3 | **Done** for the local repo (new project; first Mac commit 25 November 2026) and the public repo at https://github.com/dixonlj/labelpath. No pre-existing repo was reused as the entry |
| Original work; third-party libraries and data used with the right to use them | Official Rules §3 | **Done** for the code and public openFDA snapshot; disclose them in `STATEMENT.md` |
| Meaningful use of Relate (CLI, embedded use, MCP, and so on) | Official Rules §3 | **Done.** Embedded single-file store, Cypher via Python, read-only open, CLI, and official read-only MCP. Not only mentioned in the README |
| Public GitHub repository, tagged with topic `relate` (required), remains public with that tag through winner announcement; topic `relate-neo4j-hackathon` recommended | Official Rules §3–4; Devpost topic update 13 November 2026 | **Done.** Public at https://github.com/dixonlj/labelpath with topics `relate` and `relate-neo4j-hackathon` (also `fda`, `openfda`, `graph-database`, `cypher`, `mcp`). Confirm it appears at https://github.com/topics/relate (indexing can lag). Keep the repo public with the `relate` topic through the winner announcement |
| Open-source license encouraged (MIT or Apache-2.0) | Official Rules §3 | **Done.** Apache-2.0 `LICENSE`, copyright Liam Dixon 2026 (Liam may still switch to MIT before the public repo if he prefers) |
| Individual or team of 1–4; one identity; one entry per team; one prize per winning entry | Official Rules §3, §6 | **Done** as a planned individual entry, unless Liam later names teammates |
| Describe significant AI use in the submission | Official Rules §3–4 | **Done** as a draft in `STATEMENT.md` and `AI_USE.md`. Still a **LIAM STEP** to paste it into Devpost at submit time |
| Register on the Contest page and submit there by the deadline | Official Rules §4 | **LIAM STEP.** Use only the address Liam names, and only after an explicit OK |
| Project title and description of what it does and why it is useful | Official Rules §4 | **Done** as a draft in `DEVPOST.md`. **LIAM STEP** to paste into Devpost |
| Setup instructions so a judge can install and run the project | Official Rules §4; overview README template | **Done** in `README.md` (official template: use case; how it uses Relate, including single-file mode and why; setup and run; path to the store) |
| Demo: a video of up to 2 minutes *or* a working-demo link, plus screenshots if useful | Official Rules §4 | **LIAM STEP** to record and upload (script in `VIDEO_SCRIPT.md`). Screenshots are in `docs/img/` and `docs/screenshots/apixaban-aspirin.png`; a draft ElevenLabs voiceover MP3 exists outside the repo (disclose it as synthetic if used). Safest path: include a 1–2 minute video *and* the clone-and-run repo. Official Rules do not name YouTube; the video must be reachable **without a login or payment** |
| Video, if submitted, is original work (filming, editing, graphic design); third-party music and images only with permission; no modified Relate logo or mascot | Official Rules §4, §8 | **LIAM STEP** at recording time. Follow `VIDEO_SCRIPT.md` |
| Statement of Product capabilities, third-party tools, and AI tools | Official Rules §4 | **Done** as a draft in `STATEMENT.md`. **LIAM STEP** to include it on Devpost |
| Persistent Relate store (directory or single file) that judges can inspect; not in-memory only | Official Rules / overview | **Done.** Committed `data/labelpath.rl` (7,139,328 bytes; 2,023 nodes, 4,186 relationships) |
| Working code with Relate actually running; not prompts-only | Overview | **Done.** CLI, local UI, tests, and MCP smoke test |
| README answers: how are you using Relate, and why? | Overview template | **Done** in `README.md` |
| English-language UI, README, and Devpost text | Build rules | **Done** in the project and in these drafts |
| No secrets, no committed `.env`, no employer/patient/hospital data, no required paid services | Official Rules §4 (no purchase necessary), §8; build rules | **Done.** Public openFDA data only; no API key in the snapshot |
| Do not disclose or use confidential or proprietary information of an employer or other third party. If the work was done as part of a job, confirm the employer permits the entry | Official Rules §8 | **LIAM STEP** to confirm before submit. The project uses only public openFDA labels and no employer or patient records. The government-agency exclusion was already reviewed: Liam confirmed his employer is a private or nonprofit hospital, not a government agency |
| Age and location eligibility (18 or the age of majority if higher; not in a comprehensively sanctioned location; not on a restricted-party list). Neo4j employees and contest administrators (and their family/household) are ineligible | Official Rules §2 | **LIAM STEP** only as a final self-check at registration. The government-agency employment exclusion is resolved as noted above |
| You grant Neo4j a license to use submission *materials* (title, description, screenshots, demo video, and a repo link) for the contest and promotions; you keep the code, licensed under the repo license | Official Rules §8 | **LIAM STEP** at the moment of submit (this is part of entering) |
| Publicity permission described in Section 7, to the extent the law allows, by entering and by accepting a prize | Official Rules §7 | **LIAM STEP** to be aware of at submit / prize time |
| Repo must stay public with the `relate` topic through the end of judging and the winner announcement (announcement scheduled 17 December 2026) | Official Rules §3 | **Done** for the current public repo and topics; keep it that way through 17 December 2026 |

## Devpost form fields (paste from this pack)

| Field | Draft location | Status |
| --- | --- | --- |
| Title: LabelPath | `DEVPOST.md` | Draft done; **LIAM STEP** to paste |
| Tagline / short description (200 characters or fewer; current draft is 169) | `DEVPOST.md` | Draft done; **LIAM STEP** to paste |
| Inspiration, What it does, How we built it, Challenges, Accomplishments, What we learned, What's next | `DEVPOST.md` | Draft done; **LIAM STEP** to paste |
| Built with tags | `DEVPOST.md` | Draft done; **LIAM STEP** to select on Devpost |
| GitHub repo URL | https://github.com/dixonlj/labelpath | **Done.** **LIAM STEP** only to paste the URL into Devpost at submit time |
| Video link | `VIDEO_SCRIPT.md` | **LIAM STEP** after recording and upload |
| Screenshots, schema diagram, thumbnail | `docs/img/`, `docs/screenshots/` | Files ready; **LIAM STEP** to attach, without cropping the disclaimer |
| Capabilities / tools / AI statement | `STATEMENT.md` | Draft done; **LIAM STEP** to paste or attach |

## Suggested GitHub steps (later, only with explicit OK)

1. Create a **new** public repository (do not reuse an older private or public repo as the entry).
2. Add the local `labelpath` history, including `data/labelpath.rl`, `LICENSE`, and `README.md`. Push only after Liam’s OK.
3. In the GitHub About / Topics box, add `relate` (required) and `relate-neo4j-hackathon` (recommended). Save.
4. Open https://github.com/topics/relate and confirm the repo is listed.
5. Keep the repo public, with those topics, through the winner announcement.

## What is already done locally

- Judge-ready `README.md`, `ARCHITECTURE.md`, `DATA.md`, `docs/MCP.md`, Apache-2.0 `LICENSE`
- Committed inspectable store `data/labelpath.rl`
- CLI, 127.0.0.1 UI, read-only MCP docs and smoke test
- 34 tests passed on the Mac and in a clean-clone check (with the Relate CLI installed)
- This pack under `submission/`

## What is not done, on purpose

Nothing in this milestone was published, pushed, registered, or submitted. No Devpost account was created in this step. No video was recorded or uploaded. No GitHub remote was added.
