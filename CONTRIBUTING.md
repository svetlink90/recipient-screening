# Contributing

Contributions are welcome. This is a
deterministic compliance tool — correctness and auditability beat
convenience. Read the hard rules before changing anything.

## Ground rules (non-negotiable)

1. **The verdict is computed by `recipient_screening/verdict.py` only.**
   Never let a model, adapter, or wrapper prompt adjust, soften, or
   override a verdict.
2. **STOP_HIT and STOP_INCONCLUSIVE both pause + escalate.** There is no
   "proceed anyway" code path. A user's decision to proceed is recorded
   as a deviation note in their request record — never as a re-screen.
3. **Every parser stays namespace-agnostic** (`lists/xmlutil.py`). A parse
   producing 0 entries is inconclusive, never a silent clean screen.
4. **Provenance is mandatory** for every external input: URL, fetch time,
   SHA-256. Manual ingests are marked as such.
5. **Tests are offline.** Fixtures use `file://` URLs and stubbed HTTP.
   Never add a network-dependent test.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install pytest   # that's it — runtime is stdlib-only
.venv/bin/python -m pytest tests -q
```

## Verify before every commit

```bash
.venv/bin/python -m pytest tests -q
# Live check against the real lists (public OFAC-listed address):
python3 -m recipient_screening screen \
  0x098B716B8Aaf21512996dC57EB0615e2383E2f96 --entity "Lazarus Group"
# expected: VERDICT: STOP_HIT, exit code 2
```

## Adding a sanctions list

1. Write `lists/<source>.py` exposing `parse(path, list_id) -> list[ListEntry]`.
2. Register its format in `lists/registry.py`.
3. Add a `[[lists]]` block to `config.toml` and `config.example.toml`
   (`required = true` only for lists item 9 mandates).
4. Add a small fixture under `tests/fixtures/` and a parser test.

## Adding a risk provider

1. Write `risk/<provider>.py` implementing the `RiskProvider` protocol
   (`assess(request, sanctioned_addresses) -> CheckResult`).
2. Wire it in `engine.py:_risk_providers()` behind a `[risk.<id>]` config
   section. Default to `enabled = false`, `required = false`.
3. Any network/auth/parse failure must return `ok=False` with an
   `inconclusive_reason` — never raise through `assess()`.
4. Add stubbed-HTTP tests in `tests/test_risk_providers.py`.

## Style

- Stdlib only at runtime. New dependencies need a very good reason.
- Plain dataclasses in `models.py`; no framework magic.
- Keep adapters thin: extraction and relay only, no judgment.
