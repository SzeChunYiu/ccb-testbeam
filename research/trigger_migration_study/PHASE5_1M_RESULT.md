# Phase 5 RESULT: 1M-event migration decision (#1045)

Executed 2026-08-17. Supersedes the 3506983 submission noted in
PHASE3_EXECUTION.md (that run used the BASE config: no T1/T2 detectors,
plain geometry -> 62 branches, no trigger data; quarantined as
`output_krakow_1M_wronggeom_3506983.root`). The corrected run is job
**3506988** with `krakow_phase2.config`
(`Detectors ...,T1_trigger_log,T2_trigger_log`) + the `*_T1T2` geometry —
the exact configuration family of the 10k validation sample. Output:
1,000,000 events, 96 branches (schema-identical to the 10k file).
Provenance: `ccb_1045_phase2_1M/provenance_1m_phase2_v2.txt`.

## Headline (reference config 1.0 MeV / 15 ns)

| Quantity | 10k (previous) | **1M (this run)** |
|---|---|---|
| Proxy two-arm coincidences | 4 | **554** |
| Hardware T1^T2 coincidences | 0 | **0** |
| Proxy efficiency (species-normalised) | 5.63% | **7.80%** |
| Hardware efficiency | 0.00% | **0.00% (all 20 grid configs)** |
| Migration loss | 100% (n=4, CP95 [0,0.60]) | **100% (n=554, CP95 upper 0.67%)** |

## Mechanism (three independent diagnostics on the 1M truth tree)

1. Counter populations: T1 hit by 1436 events, T2 by 986,
   **both counters: 0 events**. Expected overlap under independence
   ~1.4 (Poisson; P(0)~25%) -> the two-arm coincidence rate of the
   placed counters is O(1e-6)/beam-event vs the proxy sample's 5.5e-4.
2. The 554 proxy two-arm events hit **T1: 0, T2: 0, either: 0**. The
   sample the trigger must select passes the counters entirely.
3. Only 1 of ALL B-arm-entering events hits T1: the T1-hitting
   population (secondary protons near end of range, per the 10k study)
   is disjoint from even the single-arm entering population.

## Failure attribution (one stage) and verdict

NOT statistics (1M settles it), NOT threshold/window (0 across the full
0.5-5 MeV x 5-30 ns grid), NOT the proxy definition (reference by
construction). The failure is the **trigger volume placement**: T1/T2
sit 30 cm upstream of the scintillator stacks and intercept beam-line
secondaries, while the two-arm spectrometer particles bend into the
arms and miss both volumes.

Decision matrix: |M-1| = 1.00 > 0.20 -> **regeneration required**, but
re-running with the same placement is futile (deterministic ~0/554).
The regeneration that matters is a **Phase 2 geometry iteration**:
move T1/T2 onto the two-arm trajectories (arm-entrance faces / first
Sci layers of each arm), then repeat the Phase 2->5 ladder on the new
build. That iteration is the actionable output of this phase.

Artifacts: `phase3/hardware_scan_1m.json`,
`phase3/baseline_proxy_scan_1m.json`, `phase4/migration_matrix_1m.json`
(scan job 3506989).
