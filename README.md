# recipient-screening

Deterministic recipient verification for external multisig signing requests —
implements the screening mandate of the **External Multisig Signing Request
Checklist v1, item 9**:

> Before signing, the recipient address and (where identified) the recipient
> entity MUST be screened against applicable sanctions lists (OFAC SDN, UN,
> EU, UK) and available on-chain risk indicators (mixer proximity,
> hacked-funds flags, high-risk exposure). A positive hit or an inconclusive
> screen is a stop condition: the request pauses and escalates to the
> designated security contact rather than proceeding on the requester's
> assurances.

## Architecture

```
┌─ Any model (Claude / GPT / Gemini / local) ─────────────┐
│  adapters: MCP server · Claude SKILL.md · GPT function  │
│  spec · generic wrapper prompt                          │
└──────────────────────┬──────────────────────────────────┘
                       │ calls CLI / MCP tool
┌──────────────────────▼──────────────────────────────────┐
│  Deterministic engine (zero third-party deps, no model) │
│  • sanctions: OFAC SDN + Consolidated, UN, EU FSD, UK   │
│    OFSI — fetched from official URLs, cached with       │
│    SHA-256 provenance                                    │
│  • risk: known-mixer set; OpenSanctions (consolidated    │
│    sanctions cross-check); optional Chainabuse &         │
│    Etherscan-proximity adapters (free tiers)             │
│  • verdict: CLEAR / STOP_HIT / STOP_INCONCLUSIVE         │
└──────────────────────┬──────────────────────────────────┘
                       ▼
        Evidence report (markdown + JSON) with per-source
        provenance: URL, fetch time, SHA-256, verbatim hits
```

The model is a front door, never the judge. Verdicts are identical no matter
which model invokes the engine, and the engine runs fully offline once lists
are cached.

## Quick start (new contributor)

```bash
git clone <repo-url> && cd recipient-screening

# 1. Create your local config (never committed — holds your keys)
cp config.example.toml config.toml
$EDITOR config.toml   # set [agent] security_contact; add free API keys
                      # (Etherscan, OpenSanctions) or export the env vars

# 2. Fetch the sanctions lists
python3 -m recipient_screening update
#    EU FSD blocks scripts (403): in a browser open
#    https://webgate.ec.europa.eu/fsd/fsf → "Full list" → CSV v1.1, then
python3 -m recipient_screening ingest eu_fsd ~/Downloads/<file>.csv

# 3. Screen a recipient
python3 -m recipient_screening screen 0xADDRESS \
  --entity "Claimed Entity Ltd" --chain ethereum \
  --context "Safe 0x… nonce 42 / request link"

# 4. Verify the install (real OFAC-listed address, public record)
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest tests -q
python3 -m recipient_screening screen \
  0x098B716B8Aaf21512996dC57EB0615e2383E2f96 --entity "Lazarus Group"
#    expected: VERDICT: STOP_HIT, exit code 2
```

Python ≥3.11, zero runtime dependencies (stdlib only). Then pick an adapter
below: drop `adapters/claude-skill/SKILL.md` into your skills folder, register
the MCP server (`adapters/mcp/README.md`), or wire the GPT function.

Exit codes: `0` CLEAR · `2` STOP_HIT · `3` STOP_INCONCLUSIVE (both STOP
states pause the request and escalate).

## Verdict semantics

| Verdict | Meaning | Required action |
|---|---|---|
| `CLEAR` | All required checks ran, no hits | Record report (item 18); continue checklist — NOT a recommendation to sign |
| `STOP_HIT` | Exact address match, strong name match, or confirmed risk flag | Pause + escalate to security contact. Never proceed on requester assurances |
| `STOP_INCONCLUSIVE` | A required check failed/unavailable, or a name sits in the review band | Same as STOP_HIT |

Design consequences of the checklist text:

- A **stale cache with a failed refresh is still conclusive** — the screen
  runs against the last good copy and the report says so (provenance shows
  list age). No cache + failed fetch = inconclusive = STOP.
- A parser producing **0 entries** (publisher changed the schema) is
  inconclusive = STOP, never a silent clean screen.
- Entity-name matches have a **review band** (similarity 0.85–0.95): treated
  as inconclusive pending human disambiguation, per the checklist.

## Optional free risk providers

| Provider | Covers | Setup |
|---|---|---|
| `known_sets` (on by default) | Known Tornado Cash mixer contracts | none — offline |
| `opensanctions` | Cross-check against OpenSanctions' consolidated `sanctions` dataset (exact wallet match + scored name match); catches consolidation gaps the five direct lists miss | free key from opensanctions.org → `api_key` in config or env `OPENSANCTIONS_API_KEY`, set `enabled=true` |
| `chainabuse` | Hack/scam/phishing reports on the address | free key from chainabuse.com → env `CHAINABUSE_API_KEY`/`CHAINABUSE_API_SECRET`, set `enabled=true` |
| `etherscan_proximity` | Inbound funds from sanctioned/flagged addresses (mixer proximity; Etherscan V2 API) | free key from etherscan.io → `api_key` in config or env `ETHERSCAN_API_KEY`, set `enabled=true` |

Keys may be set inline in `config.toml` (`api_key`) or via the env vars
(inline wins; env is the fallback). `config.toml` is gitignored once keys
are in it. Set `required=true` on a provider to make its failure a stop
condition.

## Adapters

- `adapters/mcp/` — MCP server (`screen_recipient`, `sanctions_list_status`,
  `refresh_sanctions_lists`) for Claude Desktop/Cowork/Code subscriptions.
- `adapters/claude-skill/SKILL.md` — drop-in skill with stop-rule contract.
- `adapters/gpt/` — OpenAI function spec + executor code (works with any
  OpenAI-compatible API).
- `adapters/prompts/WRAPPER_PROMPT.md` — system prompt for any other model
  with shell access.

## Repo layout

```
recipient_screening/   engine package (stdlib only)
  lists/               official-list fetchers + namespace-agnostic parsers
  risk/                pluggable risk providers
tests/                 offline tests (file:// fixtures, no network)
adapters/              per-model integration wrappers
data/lists/            cached lists + provenance sidecars (gitignored)
reports/               screening evidence reports (gitignored)
config.toml            lists, thresholds, providers, security contact
```

## Honest limits (v0.1)

- Name matching is conservative string similarity, not entity resolution —
  review-band hits are escalations, not confirmations.
- Proximity analysis covers recent inbound txs on Ethereum mainnet only,
  and only against addresses already in the screened lists/known sets. A
  commercial graph provider (Chainalysis/TRM/Elliptic) can be added as a
  `risk/` adapter without changing the engine.
- The EU FSD endpoint blocks automated fetches; use browser download (CSV
  v1.1) + `ingest`. Provenance records manual ingests explicitly.
- OpenSanctions is a consolidator, not a primary source — its leg
  cross-confirms the five direct lists and surfaces member-list attribution
  (e.g. `us_ofac_sdn`, `jp_mof_sanctions`) in the hit evidence.
- The engine screens item 9 only. It does not decode calldata (item 8),
  simulate (item 10), or check request-to-Safe consistency (item 11).

Not legal advice. Verify screening results through your compliance process.
