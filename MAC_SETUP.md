# macOS setup

LabelPath is a local, read-only Relate graph of a public FDA-label snapshot. **Educational only, not medical advice.**

You need **Python 3.9 or later** (`python3 --version`) and, optionally, the official Relate CLI for MCP and CLI one-liners ([install guide](https://relatedb.ai/docs/get-started/install/)):

```bash
curl -sSfL https://relatedb.ai/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
relate --version
```

The installer does not edit your shell startup files. If `relate` is not found, add `~/.local/bin` to `PATH` yourself. Desktop apps often omit that directory from `PATH`, so an MCP `command` should be the absolute path of the `relate` binary.

From a clone, in the project root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m pytest
python -m labelpath serve --port 8765
```

Open http://127.0.0.1:8765/ on the same machine. The UI binds to **127.0.0.1 only** and opens `data/labelpath.rl` read-only.

CLI examples (venv active):

```bash
python -m labelpath query path apixaban aspirin --max-hops 2
python -m labelpath query mention-scan apixaban aspirin warfarin --show-cypher
```

Read-only MCP (`relate serve --mcp stdio --database ./data/labelpath.rl --read-only`) is documented in [docs/MCP.md](docs/MCP.md). Use the short system prompt in [docs/AGENT_PROMPT.md](docs/AGENT_PROMPT.md). Do not omit `--read-only`.

This project pins `relate-db==1.1.0`. If `relate --version` is newer, follow that version’s changelog: https://relatedb.ai/docs/reference/changelog/

These commands work in zsh or bash. On Windows PowerShell, use `venv\Scripts\Activate.ps1` instead of `source`; the official CLI install command also differs (see the install page above).
