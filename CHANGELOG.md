# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-29

First published version.

### Added

- Deterministic screening engine (stdlib-only Python, no model in the
  verdict path) implementing External Multisig Signing Request Checklist
  v1, item 9. Verdicts: `CLEAR` / `STOP_HIT` / `STOP_INCONCLUSIVE`; both
  STOP states pause the request and escalate to the designated security
  contact.
- Sanctions lists with SHA-256-pinned provenance and stale-cache fallback:
  OFAC SDN, OFAC Consolidated, UN Consolidated, EU FSD (CSV v1.1 via
  browser ingest — the FSD blocks scripted fetches), UK OFSI.
- Risk providers: offline known-mixer set (Tornado Cash contracts),
  OpenSanctions consolidated-`sanctions` cross-check (exact wallet match +
  scored name match), Etherscan V2 inbound-proximity scan, Chainabuse
  adapter (optional, key required).
- CLI (`update`, `check-lists`, `ingest`, `screen`) with verdict exit
  codes 0/2/3; per-screen evidence reports in markdown + JSON with
  per-source provenance.
- Model adapters: MCP server (SDK v2), Claude skill (`SKILL.md`), OpenAI
  function spec + reference executor, generic wrapper prompt.
- 38 offline tests (fixtures + stubbed HTTP, no network).

### Fixed during initial validation

- OFAC's default XML namespace caused silent "clean" parses — all parsers
  are namespace-agnostic, and a 0-entry parse is now always inconclusive.
- UK OFSI flat schema (`FinancialSanctionsTarget`, aliases via shared
  GroupID) correctly grouped (5,135 entries).
- Etherscan V1 API deprecation — provider migrated to V2 (`chainid=1`);
  zero-transaction addresses (string result shape) no longer crash the
  provider.
