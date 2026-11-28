# Demo video script — LabelPath

Official Rules (Section 4) allow a video of **up to 2 minutes** *or* a link to a working demo. The Devpost overview checklist asks for a 1–2 minute video. The voiceover below is **236 words**; the finished video length is **TBD** (it will be re-recorded) and must stay **under 2:00**.

The video must be your own work (filming, editing, and graphic design). Do not add unlicensed music or stock footage. The finished file must be accessible to judges **without a login or payment**. Official Rules do not name a required host (they do not mention YouTube). An unlisted YouTube link is a common option if the watch page opens without signing in; confirm that before you submit. Do not modify the Relate logo or mascot if you show them (Official Rules, Section 8).

Keep **Educational only, not medical advice.** visible on screen for the whole video (the UI banner does this during the UI shots; add a lower-third or title card for the CLI and MCP shots).

## Timed shot list (target 1:40 to 1:50)

| Time | Shot | What to show | What to say (short cue) |
| --- | --- | --- | --- |
| 0:00–0:12 | Title card, then the UI with the disclaimer banner already visible | Title “LabelPath”; browser at `http://127.0.0.1:8765/`; the dark banner with “Educational only, not medical advice.” and the openFDA attribution | Who you are, one-sentence problem, the disclaimer out loud |
| 0:12–0:22 | Stay on the UI, or a simple slide of the graph model | Drugs, labels, ingredients, conditions; edges: contains, labeled interaction, indicated for, contraindicated in | “It is a graph of public label text, not a hospital record.” |
| 0:22–0:46 | Live UI path demo | Click **Try: apixaban → aspirin** (UI default is 2 hops; it can be raised to 3). Scroll to Path 3: apixaban → warfarin → aspirin. On this demo path, both hops have a section name, a snippet, and a DailyMed link | Read one hop out loud, including the section name |
| 0:46–0:58 | Second example in the UI | Type `clopidogrel` and `methotrexate`, keep 2 hops, click **Find paths**. Path 1 goes through a shared condition (`anaphylaxis`, from two contraindication sections); scroll to Path 2: clopidogrel → omeprazole → methotrexate, two `drug_interactions` hops, each with a snippet and a DailyMed link | “Same hedges. The omeprazole label's section 7.7 notes reports of this, mostly at high methotrexate doses.” |
| 0:58–1:08 | UI warnings | In the Warnings box, type `warfarin`, click **Show warnings**. Show the boxed-warning snippet | “This is the boxed warning text from the snapshot label, not advice.” |
| 1:08–1:22 | Terminal CLI | From `~/Projects/labelpath` with `venv/` active: `python -m labelpath query path apixaban aspirin` (the CLI defaults to 3 hops). The first line must be the disclaimer | “Same graph from the command line.” |
| 1:22–1:36 | Terminal MCP smoke, or a prepared scrollback | `python scripts/mcp_smoke.py` (or a short, already-run output). Highlight `tools/list: read_cypher, get_schema` and `write_cypher refusal: unknown tool 'write_cypher'` | “Official MCP, opened read-only, returns raw Cypher results. A write is refused.” |
| 1:36–1:50 | Finder or `ls -l data/labelpath.rl`, then the README setup block | The committed `.rl` file in the repo; one-line clone-and-run (`pip install -r requirements.txt`, then `python -m labelpath serve --port 8765`); “built with Relate”; openFDA credit | Where the store lives, how a judge can run it, close on the disclaimer |

If you are running long, cut the graph-model beat (0:12–0:22) and keep the live path, DailyMed link, warnings, file, and disclaimer. If you are early, show neighbors for protamine after warnings, still narrating that this is snapshot label text.

## Voiceover (plain words, read this)

Hi, I'm Liam Dixon. I work as a medical lab professional, and in my spare time I build AI tools by directing coding assistants like Cursor and Claude. I built LabelPath outside of work.

It is a local graph of public FDA drug labels. Educational only, not medical advice, and not for clinical use. It uses no hospital or patient data.

Relate stores the snapshot in a single file in the repo. I click Try: apixaban to aspirin. The UI defaults to two hops, and you can raise that to three. Here is a two-hop path: apixaban, to warfarin, to aspirin. Each hop shows the label section, a snippet, and a DailyMed link. A path means the label text mentions both names. It is not a pharmacological pathway or a clinical finding.

A second example: clopidogrel, to omeprazole, to methotrexate — the omeprazole label's section 7.7 notes reports of this, mostly at high methotrexate doses. Same hedges.

Warnings for warfarin show the boxed warning from the label, not advice.

The command line prints the same results, disclaimer first, and defaults to three hops.

Agents can use Relate's official read-only MCP server. It lists read cypher and get schema, and a write is refused. MCP output carries no disclaimer, so the host must add it.

Clone the repo, install, and run it offline. Data provided by the U.S. Food and Drug Administration. Educational only, not medical advice.

(236 words; the finished video length is TBD and must stay well under 2:00. For the spoken text, `read_cypher` and `get_schema` are read as “read cypher” and “get schema”. Do a timed read-through before you record, and trim rather than speed up.)

An earlier ElevenLabs draft MP3 of a previous script (stock voice “Reid - E-Learning Instructor”, model `eleven_multilingual_v2`) was made on 26 November 2026. Re-record the voiceover for this script (finished video length TBD). It is **not committed** (`*.mp3` is git-ignored); if you use a synthetic voiceover, the video should say so.

## Recording tips (macOS)

1. Start the app first, in `~/Projects/labelpath`, with the project venv `venv/` active (not `.venv`):

   ```bash
   python -m labelpath serve --port 8765
   ```

   Open http://127.0.0.1:8765/ and confirm the disclaimer banner is visible. Leave this server running. Do not run `scripts/ingest.py` or `scripts/milestone1_toy.py`.

2. Open a second Terminal in the same project, venv already active, font large enough to read on a recording (16–18 pt). Have the CLI command and `python scripts/mcp_smoke.py` ready to paste. Optionally run the smoke test once before recording and keep the terminal scrollback, so you are not waiting on the process during the take.

3. Press **Command-Shift-5** (the official macOS screenshot toolbar). Choose **Record Selected Portion** so you can frame the browser and, later, the terminal. Or **Record Entire Screen** if you are doing one continuous take and will crop later. Click **Options** and pick a microphone, a save location, and a countdown. You do not need extra software.

4. Use a quiet room and your Mac’s built-in mic or a simple headset. Read the script once off-camera, then record. It is fine to do two or three short takes (UI, then terminal) and splice them in iMovie. Keep the disclaimer in every segment. Do not add a music bed unless you have permission to use that recording.

5. After you stop, check the duration in Finder (Get Info) or iMovie. If it is **2:00 or longer**, cut it before you upload. Watch the file all the way through: disclaimer visible, DailyMed link shown, write refusal shown, `.rl` file shown, no employer or patient information, no modified Relate logo or mascot.

6. Export a standard MP4. Upload only after you agree to do so, to a host judges can open without logging in or paying. Put the link into the Devpost form when you submit; do not treat this draft folder as a submission.
