# Cluster A — ΔE-E / PID / stopping-depth diagnostic study (Krakow MC + real-beam data side)

**Scripts:** `scripts/studies/clusterA_dE_PID_stopping.py` (MC) ·
`scripts/studies/clusterA_data_side.py` (data side, ADC + composite-key validation)
**Inputs:** `geant4/data/output_krakow_1M.root` (MC, 1,000,000 events) ·
`/projects/hep/fs10/shared/nnbar/billy/ccb_deltae_rerun/deltaE_E_events_data.csv` (data side,
632,939 rows, derived from `reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz`)
**Quantities:** `reports/studies/clusterA/counts.json`

## Headline physics (the chain works — MC and data side)

- **Beam = pure protons** (`PrimaryPDG==2212` for every primary) on CD2. CD2 breakup feeds
  **recoil deuterons** (24.6 % of `Sci_bar` steps, ≈14.5 % of events), alphas (4.0 %) and
  heavier ions into the B-arm bars. The **dE-E band identity is the energy-weighted dominant
  depositing species per event** (proton vs deuteron) — this is what the PID targets.
- **MC dE-E** (canonical GEO-001 pair_merge, ΔE=edep(B2), E=edep(B4+B6+B8)): 131,198 selected;
  weighted medians ΔE=24.13 MeV, E=101.03 MeV, **corr(ΔE,E)=−0.533** (Bragg signature).
- **PID (p vs d), out-of-fold:** full AUC = **0.898**, 5-fold run-disjoint-proxy mean 0.898,
  AP=0.47 vs weighted prevalence 0.029, Brier=0.017; grouped-bootstrap CI; max-wF1 op-point.
  **Worst-slice AUC reported** (≈0.03–0.07 in saturated-ΔE / deepest-layer slices).
- **Stopping/censoring (TRU-003):** stop 2.3 % / escape 22 % / censored 76 %. The deepest
  observed layer is **never** labelled a stop without truth (residual-KE ≤ 1.0 MeV rule).
- **Data side delivered (ADC):** the real-beam dE-E is built from the derived event table and
  **reproduces `de_run.txt` exactly** — 632,939 rows → **385,984 unique composite keys**
  (`source_file_id`,`run`,`evt`); eventno-only join corrupts **73,098** rows; data
  stopping-layer B2=567,925 (89.9 %), B4=26,978, B6=14,586, B8=8,575, none=14,875. Data
  corr(ΔE,E)=**+0.18** vs MC −0.53 — the genuine MC-vs-data topology gap (data is B2-dominated;
  matches the known MV3 material-budget discrepancy, `mv3b_material_budget.py`).

## Plots (each carries counts + units; all rendered from the runs above)

| ID | File | What it shows |
|----|------|---------------|
| VIS-DE-001     | `VIS-DE-001_dE_E_density_quantiles.png`     | MC ΔE-E PrimaryWeighted hexbin + conditional 10/25/50/75/90 %iles; N, medians, corr, key-uniqueness. |
| VIS-DE-001-DATA| `VIS-DE-001-DATA_deltaE_E_adc.png`          | Real-beam ΔE-E hexbin (ADC) + quantiles; composite-key validation (385,984 unique / 632,939 rows; reproduces de_run.txt). |
| VIS-DE-002     | `VIS-DE-002_species_bands.png`              | ΔE-E (log-log) by dominant species (p/d/α/other) + band-assignment purity proxy. |
| VIS-DE-003     | `VIS-DE-003_mc_vs_data.png`                 | MC (MeV) vs DATA (ADC) ΔE-E side-by-side — topology comparison (different units). |
| VIS-PID-001    | `VIS-PID-001_roc_pr.png`                    | ROC (AUC + 95 % grouped-bootstrap CI) + PR (AP); 5-fold; max-wF1 op-point + confusion. |
| VIS-PID-002    | `VIS-PID-002_calibration.png`               | Reliability diagram + score distributions + purity/efficiency vs threshold. |
| VIS-PID-003    | `VIS-PID-003_robustness.png`                | Slice AUC by entry-KE / last-layer / ΔE — **worst slice reported, not only global**. |
| VIS-STOP-001   | `VIS-STOP-001_geometry_material.png`        | B-arm sketch (B2/B4/B6/B8 @ 0/4/8/12 cm) + areal-density ladder + PSTAR range markers + last-layer occupancy. |
| VIS-STOP-002   | `VIS-STOP-002_stopping_censoring.png`       | Termination category (stop/escape/censored) by species + last-layer violin. |

## Carried fixes (from origin/main)

GeV→MeV (`kinetic_energy_from_branch_momentum`, reaudit #864) · PrimaryWeight propagation
(#880) · stop-vs-escape censoring (TRU-003, STOP_KE=1.0 MeV) · canonical GEO-001 pair_merge
readout (`GeometryRegistry`: (0,1)→B2, (2,3)→B4, (4,5)→B6, (6,7)→B8) · per-layer edep from
canonical `build_track_records` · data-side composite key (`source_file_id`+`run`+`evt`,
`deltaE_E.py` KEY_COLS). Pure numpy/matplotlib/uproot/csv (no pandas/sklearn — shared venv
not mutated; the system PyPI bundle is kept on the path by prepending rather than replacing
`PYTHONPATH`).

## Honest limitations / residues

1. **Raw `hrdb_run_*.root` still absent on LUNARC** — but the **derived data event table IS
   staged**, so the data-side ΔE-E (ADC), stopping-layer, and composite-key validation are
   delivered here (VIS-DE-001-DATA, VIS-DE-003). The raw hrdb files are only needed to
   *re-derive* the table or extend the data PID; the existing taxonomy table covers this run.
2. **Data table is multi-row per event** (632,939 rows / 385,984 keys). Row-level ΔE-E is
   shown (consistent with `de_run.txt`'s stopping_distribution); one-row-per-event aggregation
   for data PID needs the canonical `composite_merge` (`deltaE_E.py`) — not re-implemented here.
3. **Worst PID slices are poor (AUC ≈ 0.03–0.07)** in the saturated-ΔE / deepest-layer slices
   (small, proton-dominated). Reported explicitly (VIS-PID-003), not averaged away.
4. **Depth axis is the nominal B-arm pitch**, not `Sci_bar_GlobalPosition_Z` (a non-monotonic
   tilted-arm projection; recorded in `counts.json` for audit).
5. **PID "run-disjoint" split is a pseudo-run proxy** (contiguous 2000-event blocks, 5-fold):
   the MC has no `run` column. The true run-disjoint test belongs on the data side.
