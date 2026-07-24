# Active Task

- **Task ID:** AUD-LEDGER-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T081929Z
- **Initial remote main SHA for this unit:** `251353ffb0e200bd3c495b92c854f60593f44279`
- **Scope completed in this unit:** reconstructed malformed claim-ledger row `CL-015` from the exact P04p duplicate-readout report, result, manifest, script, config, and source commit; audited whether the reported model winner is robust to uncertainty at its hard accepted-coverage gate; added fail-closed audit tooling, focused tests, machine-readable evidence, and an accessible SVG.
- **Implemented files:** `tools/audit/audit_p04p_winner_robustness.py` v1.0.0; `tests/test_audit_p04p_winner_robustness.py`; `tests/test_claim_ledger_p04p_row.py`; `docs/validation/p04p_winner_robustness_{audit.md,fixture.json,validation.json,svg}`.
- **Validation:** `py_compile` passed; focused pytest returned `6 passed in 1.14s`; the source-faithful current-like fixture returned `FLAWED` with two findings; a corrected synthetic preregistered contract returned `VALIDATED`; JSON and SVG parsed; changed Python lines were at most 100 characters; committed code blobs match the locally validated bytes.
- **Measured current state:** the reported GBT has accepted coverage `0.501643` with run-bootstrap 95% interval `[0.478103,0.538255]`, only `0.001643` above the hard 0.50 point gate. The result does not declare how uncertainty controls eligibility. A lower-95%-bound sensitivity gate excludes GBT and makes MLP the first eligible method; this sensitivity result is not promoted to a canonical winner.
- **Ledger progress:** `CL-015` is now exactly 43 fields, status `GATED`, truth type `data_external_duplicate_readout`, with source-backed central value, interval, event/run counts, baseline, delta, exact paths, source commit, and blocker `BLK-P04P-001`. Ledger progress is 6/26 exact-width rows; 20 remain withheld.
- **Scientific boundary:** no raw ROOT file, waveform, model fit, bootstrap ensemble, cross-stave transfer sample, or detector result was generated. The committed P04p metrics are repository facts; model-selection acceptance remains blocked.
- **Remaining work:** preregister an uncertainty-aware coverage gate and multiplicity policy, reserve independent runs or cross-stave transfer data for final selection, execute P04q/new-run validation, and only then designate a production model. Continue source-backed reconstruction of the 20 malformed ledger rows.
- **Status:** PARTIAL.
