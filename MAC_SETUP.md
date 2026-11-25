# Milestone 1 setup on a Mac

These are the copy-paste steps to repeat the Milestone 1 dry run on a MacBook Air (Apple Silicon, arm64). They follow the official install page (https://relatedb.ai/docs/get-started/install/) and the official Python client page (https://relatedb.ai/docs/guides/embed/python/).

A Linux dry run already succeeded on 19 November 2026 (America/New_York) with Relate CLI **v1.1.0** and Python package **relate-db 1.1.0**. Official docs and `llms.txt` were also verified against 1.1.0. If `relate --version` on your Mac prints a newer version, follow that version’s changelog: https://relatedb.ai/docs/reference/changelog/#since-1.1.0

Do not create a public GitHub repo, do not push, do not register on Devpost, and do not spend money in this milestone.

## What was different on Linux

The dry run ran on Linux **x86_64 (amd64)**, not macOS arm64. These things still apply to your Mac, with the differences below:

- The official installer supports macOS and Linux on amd64 and arm64. On Linux it installed `relate v1.1.0 (linux/amd64)` to `~/.local/bin` after checking the release signature and SHA-256.
- On a Mac the same install command should install a `darwin/arm64` binary to the same place, `~/.local/bin`.
- `pip install relate-db` on Linux installed the wheel `relate_db-1.1.0-cp39-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.whl`. PyPI also publishes `relate_db-1.1.0-cp39-abi3-macosx_11_0_arm64.whl` for Apple Silicon, and the package requires Python 3.9 or later.
- The Linux box already had `~/.local/bin` on the PATH of login shells (via a pre-existing `~/.profile` snippet, not via the Relate installer). The installer does **not** edit your shell startup files. If `relate` is not found after install, it prints a NOTE and you add `~/.local/bin` to PATH yourself (see below).
- The dry run used **Python 3.13.5**. Any 3.9+ should work. Check yours with `python3 --version`.
- macOS terminals usually use **zsh**. The commands below work in zsh or bash.

## 0. Prerequisites

In Terminal:

```bash
python3 --version
command -v curl
command -v ssh-keygen
```

You need:

- Python 3.9 or later, with `python3 -m venv` working
- `curl` and `ssh-keygen` (OpenSSH), which the official installer uses to verify the release

If `python3` is missing or older than 3.9, install a current Python 3 first, then come back. This file does not pick an installer for you.

## 1. Create the project folder

If you already have the `labelpath` folder from the dry run (README, scripts, `.gitignore`, `requirements.txt`), `cd` into it and skip the `mkdir` / `git init` lines. Otherwise, start a new folder. Change the parent path if you keep projects somewhere else:

```bash
mkdir -p ~/Projects/labelpath
cd ~/Projects/labelpath
python3 -m venv venv
source venv/bin/activate
git init
```

`git init` is only a local repo. Do not add a remote and do not push.

If you are creating the folder from scratch, also add a `.gitignore` that ignores `venv/`, `.venv/`, `.env`, `__pycache__/`, cache directories, `.DS_Store`, and auth-token files, plus a short README. Those files already exist in the dry-run copy.

## 2. Install the official Relate CLI

This is the vendor-signed installer from the official docs. It checks the signature on the release `SHA256SUMS` and the binary’s SHA-256, then installs `relate` to `~/.local/bin`. If a check fails, it installs nothing.

```bash
curl -sSfL https://relatedb.ai/install.sh | bash
```

If you would rather not pipe a script to bash, skip this step and use only the Python package in step 3. The CLI is still recommended so judges and agents can query the store.

If the install succeeds but `relate` is not found, the installer itself tells you to add `~/.local/bin` to PATH. Run this in the same terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

To make that permanent on a Mac (zsh), add the same `export` line to `~/.zprofile` (or `~/.zshrc`), then open a new terminal. The official installer does not add that line for you.

Check the CLI:

```bash
relate --version
```

Success looks like this (the license line is expected):

```text
Relate v1.1.0
License: Apache 2.0 (binary)
```

If you see a newer version, record it and use that version’s docs.

The first time you run a query, the CLI may also print that it collects anonymous usage metrics and that you can disable them with `relate telemetry off`. That appeared on the Linux dry run. Leave it as-is unless you decide to turn it off.

## 3. Install the Python package in the venv

Make sure the venv is active (`source venv/bin/activate`; your prompt usually shows `(venv)`).

If this folder already has `requirements.txt` from the dry run:

```bash
pip install -r requirements.txt
```

Otherwise:

```bash
pip install relate-db
```

The package name is `relate-db`; the import is `import relate`. Record both versions:

```bash
python -c "import relate; print(getattr(relate, '__version__', 'ok'))"
pip show relate-db
relate --version
```

On the Linux dry run those printed `1.1.0` for the import, `Version: 1.1.0` for `pip show`, and `Relate v1.1.0` for the CLI. On a Mac, `pip` should pull the macOS arm64 wheel, not the Linux one.

## 4. Run the toy script

You need `scripts/milestone1_toy.py` from this repo. From the project root, with the venv active:

```bash
python scripts/milestone1_toy.py
```

The script creates `data/labelpath.rl`, writes three toy `Drug` nodes (`toy-drug-a`, `toy-drug-b`, `toy-drug-c`), one `LABELED_INTERACTION` relationship, and one `Section` node linked to a drug, then closes the store and reopens it read-only.

Success looks like this (the path will match your Mac folder):

```text
wrote .../data/labelpath.rl exists= True
drugs: [{'key': 'toy-drug-a'}, {'key': 'toy-drug-b'}, {'key': 'toy-drug-c'}]
interaction: {'from_key': 'toy-drug-a', 'to_key': 'toy-drug-b', 'summary': 'toy placeholder interaction'}
section: {'drug_key': 'toy-drug-a', 'kind': 'interactions', 'text': 'Placeholder text only: toy-drug-a mentions toy-drug-b.'}
nodes: 4
```

Those names are fake placeholders, not medical claims.

If you run the script again, it will add another copy of the same toy graph. To start clean, delete the store first:

```bash
rm data/labelpath.rl
python scripts/milestone1_toy.py
```

## 5. Acceptance checks

Confirm the file is still there after the script has exited:

```bash
ls -l data/labelpath.rl
```

On Linux the toy store was 36864 bytes. The size on a Mac may differ; the important part is that the file exists and the data reads back.

Read it back in a **new** Python process (still in the project root, venv active):

```bash
python -c '
from pathlib import Path
import relate
store = Path("data/labelpath.rl")
print("exists=", store.is_file(), "size=", store.stat().st_size)
reader = relate.connect(str(store), read_only=True)
print("drugs=", reader.execute("MATCH (d:Drug) RETURN d.key AS key ORDER BY d.key").fetchall())
print("nodes=", reader.execute("MATCH (n) RETURN count(n) AS n").single()["n"])
reader.close()
'
```

Success: `exists= True`, the three `toy-drug-*` keys, and `nodes= 4`.

If the CLI is installed, also query with the documented read-only flags (`--mode table` is valid in 1.1.0; it is the default only when output goes to a terminal, so passing it explicitly is safer):

```bash
relate --database ./data/labelpath.rl --read-only --mode table "MATCH (d:Drug) RETURN d.key AS key ORDER BY d.key"
```

Success looks like:

```text
+--------------+
| key          |
+--------------+
| "toy-drug-a" |
| "toy-drug-b" |
| "toy-drug-c" |
+--------------+
```

Optional extra query used in the dry run:

```bash
relate --database ./data/labelpath.rl --read-only --mode table "MATCH (a:Drug)-[r:LABELED_INTERACTION]->(b:Drug) OPTIONAL MATCH (a)-[:HAS_SECTION]->(s:Section) RETURN a.key AS from_key, b.key AS to_key, r.summary AS summary, s.kind AS section_kind, s.text AS section_text"
```

## Optional: Cursor skill

The official install page also documents `relate skill install --agent cursor`. This was not run in the Linux dry run. You can do it later if you want the skill in Cursor.

## If something fails

- `relate: command not found` — run `export PATH="$HOME/.local/bin:$PATH"` and try `relate --version` again.
- The installer stopped and installed nothing — read its error; a failed signature or SHA-256 check is intentional. Do not skip verification.
- `storage error: database not found` on a read-only open — the `.rl` file is missing or the path is wrong. Run the script from the project root first, or use the script’s absolute path under `data/`.
- Wrong or unexpected API — do not guess. Open https://relatedb.ai/docs/guides/embed/python/ and https://relatedb.ai/docs/llms.txt for the installed version.


## Milestone 2 on a Mac

Milestone 1 only proved the Relate install. For the openFDA snapshot and ingest, use the commands in `README.md` (`pip install -r requirements.txt`, then `python scripts/ingest.py`, then `python -m pytest`). Ingest is offline and uses the files already under `data/raw/`.

This project is written for Python 3.9 or later. If `python3 --version` is 3.9.6, that is enough. Copy or sync the updated `labelpath` folder (including `data/raw/` and `data/labelpath.rl` if you do not want to re-ingest) onto the Mac, create a fresh venv there, and install from `requirements.txt`. Do not re-run `scripts/milestone1_toy.py` unless you intend to replace the real store with the toy graph; `scripts/ingest.py` rebuilds the real store from `data/raw/`.

Downloading a newer snapshot (`python scripts/download_snapshot.py`) needs network access and is optional. No API key is required. See `DATA.md`.


## Milestone 3 on a Mac

The query CLI is documented in `README.md`. After the venv is active in `~/Projects/labelpath`:

```bash
python -m pytest
python -m labelpath query lookup "warfarin sodium"
python -m labelpath query path apixaban aspirin --max-hops 3
python -m labelpath query warnings warfarin
```

Every command prints `Educational only, not medical advice.` The store is opened read-only. Do **not** run `python scripts/ingest.py` or `python scripts/milestone1_toy.py` just to try queries: both would replace `data/labelpath.rl`. Ingest is only needed if you are rebuilding the store from `data/raw/` on purpose.


## Milestone 4 on a Mac

The local UI is documented in `README.md`. After the venv is active in `~/Projects/labelpath`:

```bash
python -m pytest
python -m labelpath serve --port 8765
```

Leave that process running and, in another terminal (or a browser on this Mac), open http://127.0.0.1:8765/ or use:

```bash
curl -sS http://127.0.0.1:8765/ | head
curl -sS "http://127.0.0.1:8765/api/path?start=apixaban&end=aspirin"
```

The server binds to 127.0.0.1 only and opens the store read-only. The page always shows `Educational only, not medical advice.` Click **Try: apixaban → aspirin** for the demo pair (default max 2 hops). Stop the server with Ctrl+C.

Do **not** run `python scripts/ingest.py` or `python scripts/milestone1_toy.py` just to try the UI: both would replace `data/labelpath.rl`.


## Milestone 5 on a Mac

Read-only MCP is documented in `docs/MCP.md` and `README.md`. After the project venv `venv/` is active in `~/Projects/labelpath` (this repo uses `venv/`, not `.venv`):

```bash
export PATH="$HOME/.local/bin:$PATH"
relate --version
python -m pytest
python scripts/mcp_smoke.py
```

The smoke test starts `relate serve --mcp stdio --database ./data/labelpath.rl --read-only` itself, talks JSON-RPC on that process, and then lets it exit. It does not bind a port. Leave a LabelPath UI server on port 8765 alone if one is already running.

Do **not** run `python scripts/ingest.py` or `python scripts/milestone1_toy.py` just to try MCP: both would replace `data/labelpath.rl`. Do **not** start MCP without `--read-only`. Do **not** edit Claude Desktop or Cursor config files unless you choose to paste a snippet from `docs/MCP.md` yourself (a LIAM STEP).


## Milestone 6 on a Mac

The judge-ready README, `LICENSE` (Apache-2.0), `ARCHITECTURE.md`, and `CITATION.cff` are in the project root. After the project venv `venv/` is active in `~/Projects/labelpath` (this repo uses `venv/`, not `.venv`):

```bash
python -m pytest
```

Do **not** run `python scripts/ingest.py` or `python scripts/milestone1_toy.py` just to re-read the docs: both would replace `data/labelpath.rl`. Leave a LabelPath UI server on port 8765 alone if one is already running. A public GitHub repo is not created in this milestone.

