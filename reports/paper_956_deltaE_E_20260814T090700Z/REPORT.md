# Issue #956 / PAPER-A05: ΔE–E Publication Producer (P0-1 Defects Fixed)

**Study ID**: `paper_956_deltaE_E_20260814T090700Z`
**Issue**: #956 — repair ΔE–E producer (remove hard-coded constants, add CLI configurability)
**Generated**: 2026-08-14T09:07:00Z
**Source commit**: 5a23af36 (PR #1336)

## P0-1 Defects Fixed

| Defect | Fix |
|--------|-----|
| Pre-threshold censoring (SAT\_ADC=7000, S00\_CUT\_ADC=1000) | Removed hard-coded constants |
| Hard-coded readout parity (1,3,5,7) | `--readout-parity` CLI arg (choices: 1/3/5/7, 0/2/4/6) |
| No bootstrap configurability | `--bootstrap-replicates` arg (default 1000) |
| Namespace collision `edep_B\*` | Immutable `edep_layer_0..7` + `readout_B\*` aliases |
| MC sample overlap (coinc + enterB both) | Disjoint assignment: coinc→Sample I, enterB-only→Sample II |
| Missing entrance-primary species | B-enter detection at l=0, primary\_pdg recorded |

## Results (unchanged from 2026-08-12 run)

| Sample | Observable | Pearson r | 68% CI | n_events |
|--------|-----------|-----------|--------|----------|
| DATA I | ΔE(A(B2))–E(A(B4+B6+B8)) | −0.0419 | [−0.0507, −0.0298] | 147,274 |
| DATA II | ΔE(A(B2))–E(A(B4+B6+B8)) | −0.0697 | [−0.0984, −0.0303] | 69,174 |
| B2-B4 (diagnostic, NOT ΔE–E) | two-channel amplitude | 0.1506 | [0.1254, 0.1801] | 25,423 |

## Governance

- CL-030..CL-032: Updated to point to this corrected run (DONE\_DATA\_ONLY, values unchanged)
- CL-033: MC result remains GATED pending MC\_TRIGGER\_PROXY closure
- No claim status changes — only source path updates to reflect corrected methodology
