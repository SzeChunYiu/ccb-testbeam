# Phase 3/4 EXECUTION on Phase 2 data (2026-08-17)

First real-data execution of the Phase 3 scan + Phase 4 matrix, on the
Phase 2 validated geometry sample `output_krakow_phase2_10k.root`
(10,000 events, binary `hibeam_g4_build_1045b` mtime 2026-08-17 00:15,
same build that passed the Phase 2 physics gate).

## Harness defect found and fixed

`scripts/trigger_threshold_scan.py` expected branches `T1_EDep/T1_Time/
T2_EDep/T2_Time`, but the Phase 2 SD writes `T1_trigger_log_EDep/_Time`
etc. — the scan had never been runnable on real data. Fixed in 55bcb099
(mapping applied at the uproot boundary; fixtures now use the real
schema). When `Sci_bar_*` HRD branches coexist with T1/T2 (they do in
the Phase 2 file), hardware mode now fills `species_breakdown` with the
proxy `enter_B` denominator, making Phase 4 quadrants exact.

## Results at 10k events (both modes, full 4x5 grid)

| Quantity | Value |
|---|---|
| T1 hit events | 14 / 10000 |
| T2 hit events | 15 / 10000 |
| Events hitting BOTH T1 and T2 (any time) | **0** |
| Proxy enter_B / enter_A / both-arms | 71 / 9 / 4 |
| Proxy coincidence pass (15 ns ref) | 4 / 10000 (= 4/71 species-normalised, 5.63%) |
| Hardware coincidence pass (ALL 20 configs) | **0 / 10000** |
| Quadrants (ref 1.0 MeV, 15 ns) | both=0, proxy-only=4, hw-only=0, neither=67 |

Artifacts: `phase3/baseline_proxy_scan_10k.json`,
`phase3/hardware_scan_10k.json`, `phase4/migration_matrix_10k.json`.

## Verdict: decision matrix NOT applicable at 10k

Migration loss reads 100% (0/4 proxy-fired events also fire hardware),
but with n=4 the 95% Clopper-Pearson interval on the conditional
hardware efficiency is [0.0, 0.60] — compatible with both "no migration"
and "total migration". The T1 and T2 hit populations are disjoint at
10k, so even the coincidence numerator cannot be estimated. Per the
failure-first rule this is INSUFFICIENT STATISTICS, not a measured
migration.

## Phase 5 submitted (job 3506983)

1M events, identical physics and binary to the 10k validation sample
(provenance: `ccb_1045_phase2_1M/provenance_1m_phase2.txt`). Expected
yield ~400 two-arm events, ~1400/1500 T1/T2 hit events -> conditional
hardware efficiency measurable to O(5%). Scan + matrix to be re-run on
the 1M output; the |M-1| decision matrix applies to THAT result.
