# Read-only MCP for LabelPath

**Educational only, not medical advice.** This is a graph of public FDA label text, not a clinical decision tool. openFDA says: “Do not rely on openFDA to make decisions regarding medical care.” Data provided by the U.S. Food and Drug Administration (https://open.fda.gov).

This page documents how to query the committed LabelPath store through Relate’s built-in MCP server. It does not add a second server of our own. The official guides are [Serve a store over MCP](https://relatedb.ai/docs/guides/serve/mcp/) and [Connect over MCP](https://relatedb.ai/docs/guides/agents/connect-over-mcp/). If your `relate --version` is newer than the version those pages were verified against, follow that version’s [changelog](https://relatedb.ai/docs/reference/changelog/).

## What it is

`relate serve --mcp stdio` starts Relate’s MCP server as a child process of an agent host. The host speaks newline-delimited JSON-RPC 2.0 on stdin and stdout. Startup lines go to stderr; stdout is only JSON-RPC. There is no network listener and no authentication challenge on stdio (the host spawned the process).

From the project root, with the official CLI on your `PATH` (`export PATH="$HOME/.local/bin:$PATH"` if you used the official installer):

```bash
relate serve --mcp stdio --database ./data/labelpath.rl --read-only
```

A relative `--database` path is resolved against the directory the server starts in. Desktop hosts often start the process somewhere other than this project, so the configuration snippets below use an absolute path.

This project does **not** start MCP over HTTP by default, and it does not start a writable MCP server by default. The HTTP transport (`relate serve --mcp PORT`) binds `127.0.0.1` unless you pass `--host`; this repo does not document turning that on for LabelPath.

## Read-only guarantee

The guarantee comes from how the store is opened, not from the agent host’s settings. With `--read-only`, official Relate behavior (confirmed against the CLI on the dry-run box, Relate v1.3.0, and matching the official MCP guide) is:

- The server takes no writer lease and never creates the store. Every write fails.
- `tools/list` returns exactly two tools: `read_cypher` and `get_schema`. `write_cypher` is not listed.
- A `tools/call` of `write_cypher` is refused with the tool result `unknown tool 'write_cypher'` and `isError: true`.
- A write or schema statement sent to `read_cypher` is refused with `Only MATCH queries are allowed for read-query`; the store is unchanged. (The message mentions `MATCH` for compatibility; official docs say any pure read is accepted, including `OPTIONAL MATCH` and `RETURN` without `MATCH`.)

`read_cypher` takes `statement` (required) and `parameters` (object, default `{}`). `get_schema` takes an optional integer `sample_size` (`-1` examines all). Bind values as parameters; do not paste user text into a statement. Use `LIMIT` on reads.

## Smoke test

A stdlib JSON-RPC client lives at `scripts/mcp_smoke.py`. It initializes the session, lists tools, runs the parameterized apixaban → warfarin → aspirin read below, and checks that `write_cypher` is refused. It also checks that `data/labelpath.rl` is unchanged. If the Relate CLI is missing, the script exits 77 and the pytest wrapper skips.

From the project root, with the project venv `venv/` active (this repo uses `venv/`, not `.venv`):

```bash
python scripts/mcp_smoke.py
python -m pytest
```

The script looks for `relate` in `$RELATE_CLI`, then `PATH`, then the official installer location `~/.local/bin/relate`.

## Agent prompt

Official MCP output carries no disclaimer. Before a host answers questions about this snapshot, give it the short system prompt in [AGENT_PROMPT.md](AGENT_PROMPT.md): quote the section and snippet, include **Educational only, not medical advice.**, and never treat a mention as a clinical interaction.

## Host configuration

Do **not** have an agent edit Claude Desktop or Cursor config files for you. If you want a host to start the read-only server, paste a snippet yourself and restart the host. The official blocks are in [Connect over MCP](https://relatedb.ai/docs/guides/agents/connect-over-mcp/) (that page notes host formats as of 2026-11-07). Official docs also say desktop apps often do not include `~/.local/bin` on `PATH`, so `command` should be the absolute path of the `relate` binary.

Placeholder (replace the two absolute paths):

```json
{
  "mcpServers": {
    "relate": {
      "command": "<absolute-path-to-relate>",
      "args": [
        "serve",
        "--mcp",
        "stdio",
        "--database",
        "<absolute-path-to-labelpath>/data/labelpath.rl",
        "--read-only"
      ]
    }
  }
}
```

Do not remove `"--read-only"` from the args.

Where to put it, from the official host guide:

- **Claude Desktop:** `claude_desktop_config.json`, at `~/Library/Application Support/Claude/` on macOS. Settings → Developer → Edit Config opens it. Quit and restart Claude Desktop after saving.
- **Cursor:** `.cursor/mcp.json` in the project, or `~/.cursor/mcp.json` for every project.

## Example questions

Ask these only as questions about **this public-label snapshot**. Official MCP output carries no disclaimer, so the host must add it. Every answer should include the line **Educational only, not medical advice.**

**1. Is there a labeled path from apixaban to aspirin via warfarin?**

```cypher
MATCH (a:Drug {key: $start})-[r1:LABELED_INTERACTION]->(mid:Drug)-[r2:LABELED_INTERACTION]->(b:Drug {key: $end})
RETURN a.key AS start, mid.key AS via, b.key AS end,
       r1.source_kind AS hop1_section, r1.source_set_id AS hop1_set_id,
       r2.source_kind AS hop2_section, r2.source_set_id AS hop2_set_id
LIMIT 20
```

Parameters: `{"start": "apixaban", "end": "aspirin"}`. In this snapshot this returns two rows, both `apixaban → warfarin → aspirin`, with source `set_id` values `41a133ef-e461-48ad-8221-b735bdd0ec25` (apixaban) and `61ab23a7-bc67-4777-854a-bf43c788a69a` (warfarin).

**2. What boxed-warning and contraindications sections does this snapshot store for warfarin?**

```cypher
MATCH (d:Drug {key: $key})-[:HAS_LABEL]->(l:Label)-[:HAS_SECTION]->(s:Section)
WHERE s.kind IN $kinds
RETURN s.kind AS section, l.set_id AS set_id, l.source_url AS source_url, s.text AS text
LIMIT 10
```

Parameters: `{"key": "warfarin", "kinds": ["boxed_warning", "contraindications"]}`.

**3. Which labeled-interaction neighbors does this snapshot store for protamine?**

```cypher
MATCH (d:Drug {key: $key})-[r:LABELED_INTERACTION]-(n)
RETURN type(r) AS rel_type, labels(n)[0] AS neighbor_kind,
       n.key AS neighbor_key, r.source_kind AS section, r.summary AS snippet
LIMIT 20
```

Parameters: `{"key": "protamine"}`. In this snapshot, protamine’s boxed warning names heparin.

**4. What labels and relationship types are in the store?**

Call `get_schema` (optional argument `sample_size`). That is a tool call, not a Cypher statement. Official `read_cypher` / `get_schema` request shapes are in the [MCP guide](https://relatedb.ai/docs/guides/serve/mcp/).
