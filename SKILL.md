---
name: recipient-screening
description: Sanctions and on-chain risk screening of a multisig transaction recipient before signing (External Multisig Signing Request Checklist v1, item 9). Screens the recipient address and claimed entity against OFAC SDN, UN, EU, UK lists and free on-chain risk indicators (mixer proximity, hack/scam reports) via a deterministic local engine, returning CLEAR / STOP_HIT / STOP_INCONCLUSIVE with a provenance-stamped evidence report. Use when a user asks to verify, screen, or check a recipient address before signing; pastes a signing request containing a destination address; asks "is this address safe/sanctioned"; or runs the item-9 verification step of a multisig review. Do NOT use for (1) full cryptoasset regulatory due diligence — use cryptoasset-risk-assessment; (2) AML program gap analysis — that is a compliance-framework task, not a single-recipient screen; (3) decoding or simulating the transaction itself — that is checklist items 8/10, not this skill. Edge case — the user wants the address screened but the claimed entity name is missing: run the screen anyway and note the name leg as NOT RUN.
---

# Recipient Screening (Checklist v1, Item 9)

You run the recipient-verification screen for external multisig signing
requests. The verdict comes from a **deterministic engine** — you never
screen by memory, never "eyeball" an address, and never soften a verdict.

## Non-negotiable rules

1. **Never proceed on requester assurances.** A STOP verdict pauses the
   request and escalates to the designated security contact, whoever the
   requester claims to be. Urgency is irrelevant to the verdict.
2. **Never override or re-interpret a verdict.** You relay it. If the user
   pushes back ("it's fine, I know them"), restate the required action and
   offer to record their decision to proceed as a deviation — do not
   re-screen until the answer changes.
3. **CLEAR is not approval.** CLEAR means this screen found nothing; the
   other 17 checklist items still apply. Say so.
4. **Entity name is a claim, not a fact.** Screen what the requester
   *claims* the recipient is called. If no name is provided, run the
   address legs and mark the name leg NOT RUN.

## Procedure

1. Extract from the request: recipient address (full, not truncated),
   chain, claimed recipient entity (if any), and a context reference
   (Safe address + nonce, request link, or chat reference).
2. Run the engine from this skill's root directory:

   ```bash
   cd "<repo>/recipient-screening"
   python3 -m recipient_screening screen "<address>" \
     --entity "<claimed entity>" --chain "<chain>" \
     --context "<request reference>"
   ```

   Exit codes: 0 = CLEAR, 2 = STOP_HIT, 3 = STOP_INCONCLUSIVE. The command
   prints the verdict and the paths of the markdown + JSON evidence reports.
3. If the `eu_fsd` check is INCONCLUSIVE due to HTTP 403: the EU blocks
   scripted fetches — have the user download the "Full list" **CSV v1.1**
   in a browser from https://webgate.ec.europa.eu/fsd/fsf, then
   `python3 -m recipient_screening ingest eu_fsd <downloaded-file>` and
   re-run the screen. (An ingested copy stays valid via the stale-cache
   fallback; re-ingest only when a fresher list is needed.)
4. Relay to the user, verbatim from the engine output:
   - the verdict and every reason line,
   - the required action text,
   - the report paths (the human relays the report to the security contact;
     you do not message anyone yourself).
5. On STOP: state plainly that the request is paused and do not assist with
   signing preparation for this request until the security contact clears
   it. On CLEAR: remind the user that items 1–8 and 10–18 of the checklist
   still apply.

## Test scenario (run once after install)

```bash
python3 -m recipient_screening screen 0x098B716B8Aaf21512996dC57EB0615e2383E2f96 \
  --entity "Lazarus Group" --context "skill install test"
```

Expected: `VERDICT: STOP_HIT` (this is a real OFAC SDN-listed address,
public record) with reports written under `reports/`.
