# MV6b — anomaly taxonomy with Birks quenching (honest MV6 redo)

Generated 2026-07-04T16:01:26+00:00. Inputs: quenched `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mc02_pulse_table_birks_1783180742/mc02_pulse_table.csv.gz`, unquenched twin `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mc02_pulse_table_1783107862/mc02_pulse_table.csv.gz`.

Question (review F6.2): can C12 recoils be the data's ~4.4% early-peak class once light quenching is included? The retracted MV6 ran unquenched (C12 light overstated ~10x) with no amplitude threshold.

## Primary result (gain 60 = Phase-2 preferred, sample_II trigger proxy)

| quantity | quenched (Birks ON) | unquenched (legacy twin) | data |
|---|---|---|---|
| A>1000 rows | 0 | 312 | — |
| early-peak (peak_sample<=3) fraction | 0.000% [0.000%, 100.000%] | 0.000% [0.000%, 1.216%] | 4.400% |
| C12 rows in population | 1656 | 1656 | — |
| C12 rows passing A>1000 | 0 | 0 | — |
| heavy-ion fraction of A>1000 | 0.000% | 13.782% | — |

## Species composition of the A>1000 selection (primary config)

| species | quenched n (frac, med amp) | unquenched n (frac, med amp) |
|---|---|---|
| He3 | 0 | 10 (3.205%, 5761) |
| alpha | 0 | 27 (8.654%, 5302) |
| d | 0 | 111 (35.577%, 5146) |
| other_ion | 0 | 2 (0.641%, 5409) |
| p | 0 | 158 (50.641%, 5220) |
| t | 0 | 4 (1.282%, 5230) |

## Early-peak species composition (primary config)

| species | quenched | unquenched |
|---|---|---|
| (no early-peak rows in either table) | 0 | 0 |

## Sensitivity grid (all gain x population configs)

| config | quenched: n sel / early frac / C12 sel | unquenched: n sel / early frac / C12 sel |
|---|---|---|
| gain60_sample_II | 0 / 0.000% / 0 | 312 / 0.000% / 0 |
| gain60_all | 0 / 0.000% / 0 | 312 / 0.000% / 0 |
| gain60_sample_I | 0 / 0.000% / 0 | 16 / 0.000% / 0 |
| gain297_sample_II | 415400 / 0.000% / 0 | 458651 / 0.000% / 3 |
| gain297_all | 415416 / 0.000% / 0 | 458712 / 0.000% / 3 |
| gain297_sample_I | 74027 / 0.000% / 0 | 79447 / 0.000% / 1 |

## Caveats

- MC pulses have a construction-pinned peak phase (trigger offset 50 ns, no trigger-phase jitter), so MC early-peak can only arise from noise/baseline pathologies — the decisive quench observable is C12/ion survival of the A>1000 selection, not the raw early-peak fraction
- gain is a placeholder either way; both hypotheses (60 preferred, 297) reported
- occupancy weights inherit the unsimulated-trigger defect (Phase 2)

## Reproduce

```
python3 scripts/mv6b_anomaly_with_quenching.py \
    --quenched /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mc02_pulse_table_birks_1783180742 --unquenched /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mc02_pulse_table_1783107862 --out /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mv6b_anomaly_quenching_1783180742
```
