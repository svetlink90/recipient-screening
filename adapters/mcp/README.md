# MCP adapter — setup

Exposes the screening engine as three tools: `screen_recipient`,
`sanctions_list_status`, `refresh_sanctions_lists`.

## Install

```bash
python3 -m venv .venv        # if not already present
.venv/bin/pip install mcp    # v2 SDK
```

## Claude Desktop / Cowork (`claude_desktop_config.json`)

`<REPO>` = absolute path of this folder on the contributor's machine.

```json
{
  "mcpServers": {
    "recipient-screening": {
      "command": "<REPO>/.venv/bin/python",
      "args": ["<REPO>/adapters/mcp/server.py"],
      "env": {
        "ETHERSCAN_API_KEY": "optional if set inline in config.toml",
        "OPENSANCTIONS_API_KEY": "optional if set inline in config.toml",
        "CHAINABUSE_API_KEY": "optional",
        "CHAINABUSE_API_SECRET": "optional"
      }
    }
  }
}
```

Restart Claude Desktop after saving. Verify: ask "what recipient-screening
tools are available?" — expect `screen_recipient`, `sanctions_list_status`,
`refresh_sanctions_lists`.

## Claude Code / Cowork CLI

```bash
claude mcp add recipient-screening -- \
  "<REPO>/.venv/bin/python" "<REPO>/adapters/mcp/server.py"
```

The tools work with a Claude subscription (Desktop/Cowork/Code) — no API key
needed. The engine itself never calls a model; screening results are
identical regardless of which client invokes them.

## EU FSD note

`webgate.ec.europa.eu` blocks automated fetches (403). Download the "Full
list" **CSV v1.1** in a browser from https://webgate.ec.europa.eu/fsd/fsf,
then:

```bash
python3 -m recipient_screening ingest eu_fsd ~/Downloads/<file>.csv
```

A copy is already ingested in this install; without one, every screen
correctly returns STOP_INCONCLUSIVE.
