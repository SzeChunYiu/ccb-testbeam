# Cluster A — ΔE-E / PID / stopping-depth diagnostic study (Krakow 1M-event MC)

**Source script:** `scripts/studies/clusterA_dE_PID_stopping.py`
(run: `PYTHONPATH=src:$PYTHONPATH MPLCONFIGDIR=… ccb-py/bin/python scripts/studies/clusterA_dE_PID_stopping.py`)
**Input:** `geant4/data/output_krakow_1M.root` (tree `hibeam`, 1,000,000 events)
**Quantities JSON:** `reports/studies/clusterA/counts.json`

## Headline physics (proves the chain works)

- **Beam = pure protons** (`PrimaryPDG==2212` for every primary) on the CD2 target. CD2
  breakup feeds **recoil deuterons** (24.6 % of `Sci_bar` steps, present in ≈14.5 % of
  events), alphas (4.0 %) and heavier ions into the B-arm bars. The **dE-E band identity
  is therefore the energy-weighted dominant depositing species per event**, not the beam
  particle — this is what the PID task targets.
- **dE-E selected:** 131,198 events with ΔE>0 and E>0 (of 237,449 events that produced a
  charged B-arm track). Weighted medians: ΔE = 24.13 MeV, E = 101.03 MeV,
  **corr(ΔE,E) = −0.533** — the expected anti-correlation (Bragg stopping signature).
- **PID (proton vs deuteron), out-of-fold:** full AUC = **0.898**, 5-fold run-disjoint-proxy
  mean = **0.898** ± 0.01, AP = 0.47 vs weighted prevalence 0.029, Brier = 0.017. Operating
  point (max weighted-F1) at threshold 0.34. **The discrimination is real.**
- **Stopping / censoring (TRU-003 honored):** of the ΔE-E-selected sample, **stop 2,964
  (2.3 %), escape 28,806 (22 %), censored 99,428 (76 %)**. The deepest observed layer is
  **never** labelled a stop without truth — a track is `stop` only when its residual KE at
  the last observed hit is ≤ 1.0 MeV; the large *censored* fraction (exited the active
  volume with KE>1 MeV before the outermost layer) is the honest residue.

## Plots (each carries its counts + units; all rendered from the run above)

| ID | File | What it shows |
|----|------|---------------|
| VIS-DE-001  | `VIS-DE-001_dE_E_density_quantiles.png`  | MC ΔE-E PrimaryWeighted hexbin (Σ weight, log) + conditional 10/25/50/75/90 %ile quantiles of ΔE vs E. N, weighted-N, medians, corr, composite-key-uniqueness annotated. |
| VIS-DE-002  | `VIS-DE-002_species_bands.png`           | ΔE-E (log-log) coloured by dominant species (p / d / α / other), PrimaryWeighted, with per-band weighted-median ΔE + counts; side panel = band-assignment purity proxy (dominant-track edep / event-total edep). |
| VIS-PID-001 | `VIS-PID-001_roc_pr.png`                 | ROC (AUC + 95 % grouped-bootstrap CI, block=500 events) + precision-recall (AP) for p-vs-d logistic PID; run-disjoint 5-fold fold AUCs; max-wF1 operating point with weighted confusion matrix. |
| VIS-PID-002 | `VIS-PID-002_calibration.png`            | Reliability diagram (decile bins, Wilson err-bars) + weighted score distributions (p vs d) + purity/efficiency vs threshold. |
| VIS-PID-003 | `VIS-PID-003_robustness.png`             | Slice AUC by entry-KE, by last-observed-layer, by ΔE (saturation proxy) — **worst slice reported, not only the global AUC**. Global + 5-fold + op-point summarised. |
| VIS-STOP-001| `VIS-STOP-001_geometry_material.png`     | B-arm cross-section sketch (B2/B4/B6/B8 @ 0/4/8/12 cm, 2 cm BC-408, ρ=1.03 g/cm³) with cumulative areal-density ladder, PSTAR proton range markers (20–190 MeV; R(190 MeV)=20.8 cm > 12 cm → punch-through), and the observed last-observed-layer occupancy. |
| VIS-STOP-002| `VIS-STOP-002_stopping_censoring.png`    | Termination category (stop/escape/censored) stacked by species + last-observed-layer violin by species. TRU-003 rule and category counts annotated on the figure. |

## Carried fixes (from origin/main)

GeV→MeV (`kinetic_energy_from_branch_momentum`, reaudit #864) · PrimaryWeight propagation
(issue #880) · stop-vs-escape censoring (TRU-003, STOP_KE = 1.0 MeV) · canonical GEO-001
pair_merge readout (`GeometryRegistry`: layers (0,1)→B2, (2,3)→B4, (4,5)→B6, (6,7)→B8) ·
per-layer edep from canonical `build_track_records`. Pure numpy/matplotlib (no pandas/sklearn).

## Known limitations / honest residues

1. **No raw beam data on LUNARC.** Only the Krakow 1M-event MC is staged here. The raw
   `hrdb_run_*.root` files are **not on LUNARC**, so the data-side ΔE-E overlay (ADC,
   `deltaE_a002`), the data-side composite-key join (`source_file_id`+`run`+`evt`, see
   `de_run.txt`), and PID-on-data are deferred until those files are transferred. On the MC
   the per-event key is `event_index` (verified unique: 237,449 / 237,449).
2. **Worst PID slices are poor (AUC ≈ 0.03–0.07 in the saturated-ΔE / deepest-layer
   slices).** These slices are small and heavily proton-dominated; the global AUC (0.898)
   hides the degradation there. This is reported explicitly (VIS-PID-003) rather than
   averaged away, and is the honest worst-case behaviour of a global linear score.
3. **Depth axis is the documented nominal B-arm pitch**, not `Sci_bar_GlobalPosition_Z`
   (which is a non-monotonic tilted-arm projection, layer-5 median < layer-3; recorded in
   `counts.json` for audit but not used as the depth coordinate).
4. **PID "run-disjoint" split is a pseudo-run proxy** (contiguous 2000-event blocks, 5-fold):
   the MC has no `run` column. The real run-disjoint test belongs on the data side.
