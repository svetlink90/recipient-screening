# recipient-screening — Claude Instructions

## What this folder is
Deterministic sanctions + on-chain risk screening engine for external
multisig signing requests (Checklist v1, item 9), with thin per-model
adapters (MCP, Claude skill, GPT function, generic prompt). The engine is
stdlib-only Python; models are front doors, never the judge.

## Hard rules
- The verdict is computed by `verdict.py` only. Never let a model adjust,
  soften, or override a verdict in an adapter or wrapper prompt.
- STOP_HIT and STOP_INCONCLUSIVE both pause + escalate. If a user asks for
  a "proceed anyway" path, it must be recorded as a deviation note in the
  request record — never as a re-screen.
- Every parser must stay namespace-agnostic (`lists/xmlutil.py`). A parse
  producing 0 entries is inconclusive, never clean.
- Provenance (URL, fetched_at, SHA-256) is mandatory for every external
  input. Manual ingests are marked as such.
- Tests are offline (file:// fixtures). Never add network-dependent tests.

## Verify after any change
```bash
python3 -m pytest tests -q
python3 -m recipient_screening screen \
  0x098B716B8Aaf21512996dC57EB0615e2383E2f96 --entity "Lazarus Group"
# expected: VERDICT: STOP_HIT, exit 2
```

## Notes
- EU FSD blocks scripts (403) → browser download of the "Full list" **CSV
  v1.1** + `ingest eu_fsd <file>` (parser: `lists/eu_fsd_csv.py`; the v1.0
  CSV is the same rows in a legacy layout and is not parsed).
- Etherscan provider uses the V2 API (`/v2/api`, chainid=1) — V1 is dead.
- `config.toml` holds inline API keys (Etherscan, OpenSanctions) for this
  local install and is gitignored; env-var fallback stays supported.
- OpenSanctions (`risk/opensanctions.py`) is a supplementary cross-check leg
  against their consolidated `sanctions` dataset — never `required=true`
  unless the API contract is re-pinned; the five direct lists stay
  authoritative.
- Escalation pathway: STOP_HIT / STOP_INCONCLUSIVE escalate to the
  designated security contact configured in `config.toml [agent]
  security_contact`.
