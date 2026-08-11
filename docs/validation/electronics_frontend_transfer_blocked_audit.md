# Electronics front-end transfer BLOCKED audit (issue #1010)

Status: **BLOCKED** — no invented transfer function.

## Evidence

- Pinned `ccb-sipm-core` defaults to `ASSUMPTION_GENERIC_CRRC_NOT_MEASURED`.
- Geant4 / MV0 integration does not supply a CCB bench-measured or held-out
  `DATA_FIT` impulse digest.
- Children #1067/#1068 require fail-closed measured-impulse handling and
  charge-vs-peak unit contracts before a bound impulse can authorize claims.

## Gate

`ccb_mc_validation.digitizer.electronics_response_authority.assert_detector_claim_authorized`
raises unless provenance is `BENCH_MEASURED` or `DATA_FIT` with a non-empty
`impulse_digest`.

See `docs/mc_validation/ADR-0010-ccb-frontend-transfer-blocked.md`.
