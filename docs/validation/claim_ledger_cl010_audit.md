# CL-010/CL-012 Rmax claim-ledger quarantine audit

## Scope

This unit reconstructs the two malformed pile-up-rate rows under the canonical 43-column claim-ledger schema and checks the exact repository evidence behind the reported `3.044–3.05 MHz` headline. It does not rerun beam data, the MV5 Monte Carlo, or a recovery study.

Policy: `QUARANTINE_CONFLICTED_RMAX_DEFINITION`.

## Confirmed source conflict

The tracked MV5 JSON records `tau_eff_new_ns = 124.8` and `duty = 0.38`. Its reported number is exactly

```text
(1 / 124.8 ns) × 0.38 = 3.0448717948717947 MHz.
```

The same JSON records `rmax_from_failure_ceiling_mhz = null`; the largest simulated recovery failure fraction is `0.03475`, below the recorded ceiling `0.17`. Thus the recovery curve never establishes a `3.044 MHz` crossing.

The academic chapter instead starts from `mu_max = 0.1`, obtains `0.801 MHz` per stave and `3.20 MHz` for four staves, then calls `3.05 MHz` a rounding. `3.05` is not a rounding of `3.20`. The chapter separately calls the recovery result `3.044 MHz`, contradicting the tracked MV5 JSON's null crossing.

The value `0.38` is explicitly named `DUTY` / beam duty factor in the source and summary. Treating it as a validated occupancy-quality threshold is unsupported by the reviewed repository evidence.

## Ledger correction

- `CL-010`: exact-width, `BLOCKED`, no accepted current value, truth type `derived_model_conflicted`, blocked by `S-STAT-003`.
- `CL-012`: exact-width, `SUPERSEDED`, no accepted current value, retained only as correction history.
- Both rows cite the tracked MV5 report, script, JSON, producing commit, and repaired `FIG-PU-003` record.

`FIG-PU-003` now points to the tracked JSON and six-panel PNG instead of nonexistent `results.json` and `docs/figures/rmax_comparison.png` paths. The figure is evidence for the historical calculation and failure curve, not an accepted Rmax measurement.

## Validation

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_cl010.py \
  tests/test_validate_claim_ledger_cl010.py

PYTHONPATH=. python -m pytest tests/test_validate_claim_ledger_cl010.py -q

6 passed in 0.04s
```

The focused suite covers corrected quarantine, attempted re-promotion to `VALIDATED`, attempted insertion of a canonical value, a future recovery-crossing change requiring review, stale figure paths, and controlled invalid UTF-8. The source-faithful validation fixture returned `VALIDATED` with zero issues. JSON and SVG parsing passed; changed Python lines are at most 92 characters.

A complete checkout was unavailable because the runtime could not resolve `github.com`. Exact repository facts were therefore inspected through authenticated GitHub blob reads; no claim is made that the entire repository validator suite or GitHub Actions ran.

## Cumulative schema state

- Ledger bytes: `10097`
- Ledger SHA-256: `809e03162f04f94235fe36612c0ec8a3ccf4ae054a5d87341bdd5e26ad3c57d6`
- Exact rows: `5/26` (`CL-001`, `CL-007`, `CL-010`, `CL-011`, `CL-012`)
- Width-mismatched rows: `21`
- Overall schema status: `FLAWED` by required fail-closed policy

## Scientific boundary

No accepted Rmax value or uncertainty remains in the canonical ledger. The public WIKI and academic chapter still contain conflicting `3.044–3.05 MHz` language and require a separate complete-file remediation after `S-STAT-003` defines the measurand, event/stave normalization, occupancy criterion, duty-factor use, uncertainty, and independent validation strategy.
