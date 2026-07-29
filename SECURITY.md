# Security

## Reporting a vulnerability

This tool is a control in a financial signing process — if you find a way
to make it produce a wrong verdict (a bypass, a parser blind spot, a
provenance gap), treat it as a security issue, not a bug ticket.

- **Do not** open a public issue with exploit details.
- Report privately to the repository maintainer using the contact configured
  in `config.example.toml`, or via the repository's private security channel.
- Include: affected version/commit, a minimal repro (address/entity/list
  fixture), expected vs actual verdict.

## Operational security model

- **Secrets:** `config.toml` holds API keys and is gitignored. Only
  `config.example.toml` (placeholders) is committed. Env vars are
  supported for every key — prefer those on shared machines.
- **Evidence:** `reports/` and `data/lists/` are gitignored. Screening
  reports are case evidence — they name counterparties and must not be
  committed or posted publicly.
- **Integrity:** every external input is SHA-256-pinned at fetch time and
  the hash is printed into the report. Verify download origins for manual
  ingests (the ingest detail tells you to).
- **Supply chain:** the runtime engine is stdlib-only by design — there is
  no dependency tree to poison. Optional extras (`mcp`, `pytest`) are for
  adapters/tests only and never run inside the verdict path.
- **Model isolation:** models invoke the engine; they never compute or
  modify verdicts. If you find an adapter that lets a model influence the
  verdict path, that is a reportable issue.
