# Active Task

- **Task ID:** AUD-LEDGER-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T084518Z
- **Initial remote main SHA for this unit:** `71907c86124f2ac0e5c4ee9fd4acc05967a02268`
- **Scope completed in this unit:** reconstructed malformed claim-ledger row `CL-016` from the exact P07e duplicate-readout saturation report, result, manifest, producer script, configuration, and repository history; separated synthetic pseudo-saturation closure from external held-out duplicate-channel validation; added a fail-closed source-chain audit, focused tests, machine-readable evidence, and an accessible SVG.
- **Implemented files:** `tools/audit/audit_p07e_saturation_claim.py` v1.0.0; `tests/test_audit_p07e_saturation_claim.py`; `docs/validation/p07e_saturation_claim_{audit.md,validation.json,svg}`; reconstructed `docs/claim_ledger.csv` row `CL-016`; refreshed claim-ledger schema JSON/SVG.
- **Validation:** `py_compile` passed; focused pytest returned `4 passed in 0.62s`; JSON and SVG parsed; changed Python lines are at most 100 characters; the ledger is exactly 43 columns for `CL-016`; the committed ledger blob matches the locally validated bytes.
- **Measured current state:** pseudo-saturation ML charge res68 is `0.03669062665507541`, but external held-out duplicate closure gives ML `0.1763577793605039` with run-block 95% interval `[0.17304334869529975,0.18060166173702746]`, versus raw `0.12079374117700271` with `[0.11700387021774719,0.12536373643016782]`. The signed degradation is `+0.05556403818350119`; the intervals do not overlap.
- **Scientific decision:** `WITHHOLD_ML_CORRECTION` under `P07E_EXTERNAL_DUPLICATE_CLOSURE_OVERRIDES_PSEUDO_SATURATION`.
- **Provenance blocker:** the manifest execution commit `f20e1b0bceac4eeae4532c9e871a363d6dce08d7` predates the P07e producer path, and the manifest records neither producer SHA-256 nor worktree cleanliness. `BLK-P07E-001` remains open.
- **Ledger progress:** `CL-016` is now exactly 43 fields, status `GATED`, truth type `data_external_duplicate_readout`, with source-backed metric, interval, event/run counts, baseline, delta, exact paths, and explicit provenance blocker. Ledger progress is 7/26 exact-width rows; 19 remain withheld.
- **Scientific boundary:** no raw ROOT file, waveform extraction, model refit, bootstrap rerun, cross-stave transfer sample, new-run validation, calibration, or detector-performance result was generated.
- **Remaining work:** recover or reproduce content-addressed producer bytes and clean worktree provenance; preregister and execute cross-stave/new-run saturation validation before production use; continue source-backed reconstruction of the 19 malformed ledger rows.
- **Status:** PARTIAL.
