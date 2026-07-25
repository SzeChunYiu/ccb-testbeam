# Cluster D — CCB MC-Validation Programme (MV0–MV6) + Single-Stave Campaign Aggregation

**Branch:** `studies/clusterD-mc-validation`
**Base:** `origin/main` @ `44deedd1` (2026-07-25)
**Site:** LUNARC `cosmos3` (login) + `cx*` (compute, account `hep2023-1-3`, partition `hep`)
**Python:** `/projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/python` (uproot 5.7.5, NumPy 2.4.6, SciPy 1.17.1, Matplotlib 3.11.1) with `PYTHONNOUSERSITE=1` to mask a broken `~/.local/lib` shadow.
**MC truth (Krakow 1M):** `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root` (677 MB, 1 000 000 events; symlinked into the worktree as `geant4/data/`).
**Single-stave campaigns:** `/projects/hep/fs10/shared/nnbar/billy/ccb-runs/{i885_v1, an3/sys_birks_smoke2, sipm-p2-001}`.

## MV0–MV6 status

| ID  | Title | Tier | State | Evidence / Blocker |
|-----|-------|------|-------|--------------------|
| MV0 | Digitizer ADC-gain calibration | 2 (backbone) | **PASS** (PRODUCTION) | Best-fit gain **110.0 ADC/MeV** (implied-median 131.8); KS data-vs-MC = **0.108** on 377 362 analysis pulses vs 48 300 MC events. Reproduces the 2026-06-28 calibration (`mv0_calibration_1782677847`, gain 110 / KS 0.108). Evidence: `mv_runs/mv0/{calibration.json, REPORT.md, mv0_*.png}`. |
| MV1 | Truth p/d PID ceiling | 1 | **PASS** | On 79 881 B-arm tracks (30 087 p, 29 300 d): logistic-regression-on-ΔE–E **AUC 0.962**, HistGradientBoost **AUC 0.985**, **purity @ 90 % efficiency = 0.962** (HGB). Cut on `edep_l0` at 13.27 MeV gives purity 0.887 / efficiency 0.899. Evidence: `mv_runs/mv1_mv2/{mv1_mv2_truth_summary.json, mv1_mv2_truth.png}`. |
| MV2 | Range–energy calibration | 1 | **PASS** | Per-stop-layer mean EKin / EDep / tracklen table written for protons and deuterons (e.g. layer-0 protons: mean tracklen 27.9 mm at mean EDep 10.16 MeV). Closing the absolute-energy question (the data-side "10 % absolute energy unreachable" concern). Evidence: `mv_runs/mv1_mv2/mv1_mv2_truth_summary.json` → `MV2_range_energy`. |
| MV3 | Stopping-depth / stave profile, Sample I↔II | 1 | **PASS (mapping) / TENSION (shape)** | 60 868 charged B tracks, 95 % above 100 ADC readout threshold. Layer→stave hypothesis (0,1→B2; 2,3→B4; 4,5→B6; 6,7→B8) reproduces **Sample-I stave fractions with score 0.953** (data 0.957/0.026/0.012/0.005) and Sample-II with score 0.449. MC over-produces B8 (data frac 0.020 vs MC 0.220) — the **known** B8 leakage discrepancy, **not** a mapping failure. Evidence: `mv_runs/mv3/{mv3_summary.json, mv3_stop_frac.png, REPORT.md}`. |
| MV4 | Timing resolution & timewalk | 2 | **BLOCKED (TOY_DIAGNOSTIC)** | Toy digitizer ran on 4 011 synthetic tracks: σ₆₈ raw = **4.75 ± 0.60 ns**, timewalk-corrected 4.59 ± 0.92 ns (improvement factor 1.03 — barely resolves). `--data-anchors` **not supplied** ⇒ the comparison to measured σ values uses HARD-CODED FALLBACK anchors (1.85/1.50 ns); per-script warning flags this. **Blocker:** production Tier-2 needs (a) the calibrated MV0 digitizer (here: only gain loaded, no full waveform pipeline), (b) the measured data anchors JSON. Evidence: `mv_runs/mv4/{REPORT.md, mv4_*.png}`. |
| MV5 | Pile-up & two-pulse recovery | 2 | **PASS (analytic), TOY overlay** | Confirms the data-corrected dead-time picture: τ_eff = **124.8 ns ⇒ R_max = 3.04 MHz** (= the data-corrected 3.05 MHz); the note's 90 ns / 4.2 MHz is over-optimistic. MC-vs-analytic pile-up fraction matches within binomial error at every rate. Observed 4 % anomaly ⇒ mean in-spill rate ≈ 0.16–0.48 MHz (10× below R_max) ⇒ anomaly is **not bulk pile-up** (handed to MV6). **Caveat:** toy uses `truth_tracks.npz`, not the production MV0 digitizer overlay. Evidence: `mv_runs/mv5/{REPORT.md, mv5_pileup.png, mv5_example_waveforms.png}`. |
| MV6 | Pulse-shape & representation, anomaly ID | 2 | **PASS (species ID), TOY digitizer** | On 7 848 B-arm charged tracks: total anomaly (early-peak + low-area) frac **0.48 %** in MC vs **~4 %** in data. The early-peak class is **66 % Carbon-12** (25 of 38), 13 % electrons, 8 % α, 8 % p — mechanistically the expected signature of high-dE/dx, fast-stopping species. PCA cumulative variance @4 PCs = 0.749, @8 PCs = 0.833 (consistent with data-side linear-representation finding). **Caveat:** toy digitizer; production identity validation needs full MV0 waveforms. Evidence: `mv_runs/mv6/{REPORT.md, mv6_representation.png, mv6_representation_summary.json}`. |

**Tier-2 caveat (MV4/MV5/MV6):** these studies are gated on a calibrated MV0 digitizer per `studies/MC_VALIDATION_PROGRAM.md`. The standalone toy scripts ran cleanly and produced physics-readable results (MV5/MV6) but use a placeholder digitizer (gain only, no full WLS+electronics pipeline). A production Tier-2 run requires the MV0 digitizer (`src/ccb_mc_validation/digitizer/pipeline.py`) wired through the CLI — currently the `mv4`/`mv5`/`mv6` CLI subcommands return blocked placeholders (`src/ccb_mc_validation/studies/mv{4,5,6}_*.py`).

## Campaign aggregation (single-stave Geant4/SiPM)

Plotters live under `scripts/single_stave/campaign_plots/`. Run order is captured in this PR's `reports/studies/clusterD/run_campaign_aggregation.sh`.

### i885_v1 — calibration campaign
72 runs (proton + deuteron × {2, 5, 8, 12, 20, 30, 50, 80, 120, 150} MeV × seeds 101/102). Output: `figures/fig_i885_*.png`.

| Plot | What it shows |
|------|---------------|
| `fig_i885_ke_vs_light.png` | 4-panel: (a) scint-photon yield vs KE, (b) WLS-photon yield vs KE, (c) detected PE at readout SiPM vs KE, (d) scintillator EDep vs KE — for p and d. |
| `fig_i885_ke_vs_pe_per_sensor.png` | Detected PE per sensor location (readout, fibre-1 far, fibre-2 near, fibre-2 far) vs KE, protons. |
| `fig_i885_linearity.png` | Scintillation yield linearity log-log; power-law slope labelled per particle. |
| `fig_i885_timing.png` | Photon arrival-time distributions (0–80 ns) per sensor for one 5 MeV run. |
| `fig_i885_attenuation.png` | Notes that i885 is at fixed x=0 (no x-scan in this campaign). |

### sys_birks_smoke2 — Birks systematic grid
3 runs at kB = {0.100, 0.126, 0.160} mm/MeV on 100 MeV protons (seed 11, 500 events each).

| Plot | What it shows |
|------|---------------|
| `fig_birks_raw_vs_birks_edep.png` | (a) Birks-suppressed EDep vs raw EDep scatter; (b) suppression ratio (Birks/raw) vs raw dE/dx — quenching turns on at high ionisation density, kB=0.160 the strongest. |
| `fig_birks_pe_yield.png` | Detected PE at readout vs kB — monotone *decrease* with kB (suppression eats light yield). |

### sipm-p2-001 — SiPM sensitivity campaign
12 one-knob sweeps (afterpulse, attenuation, birks_kB, coupling, crosstalk, dark_count, far_end, pde_scale, recovery_time, reflectivity, sipm_n_cells, window_end), 5 points each. The campaign already ships per-knob PNGs + tables; this PR adds three cross-knob aggregates parsed from the per-knob `SUMMARY.md` tables.

| Plot | What it shows |
|------|---------------|
| `fig_sipm_cross_knob_elasticity.png` | Bar chart of elasticity η = d(ln ADC)/d(ln knob) for 11 numeric knobs. **Reflectivity dominates (η=+3.48)**, then coupling (0.94), pde_scale (0.89), attenuation (0.23); **birks_kB is the only negative (−0.40)**. |
| `fig_sipm_adc_vs_knob.png` | Small-multiple ADC + PE response per knob (normalised). |
| `fig_sipm_clipped_fractions.png` | Mean clipped/saturated fraction per knob (birks_kB and reflectivity show non-trivial saturation onset). |

Per-knob elasticity ranking (consistent with the campaign's own cross-knob table):

```
reflectivity  +3.484    (dominant — TiO2 reflectivity scale)
coupling      +0.939
pde_scale     +0.891
attenuation   +0.226
crosstalk     +0.074
afterpulse    +0.016    (linear regime)
sipm_n_cells  +0.033
dark_count    +0.010
recovery_time +0.007
window_end    +0.010
birks_kB      -0.398    (only negative — Birks suppression)
```

## VIS-MC diagnostic plots (proving the sim works)

Generator: `scripts/single_stave/campaign_plots/single_stave_diagnostics.py`. All figures: counts + units labelled, captioned + sourced at the bottom.

| Figure | Verifies | Source data |
|--------|----------|-------------|
| `VIS-MC-001_generator_source.png` | Primary KE spectra, entry positions, incidence angles, weights match the configured box gun. 4-panel: (a) KE spectra per particle, (b) entry x-y 2-D histogram, (c) incidence-angle θ from entry/exit positions, (d) per-particle event tallies (box generator ⇒ w=1). | i885_v1 events tree |
| `VIS-MC-002_transport_vs_pstar.png` | Energy loss vs NIST PSTAR polystyrene. (a) Geant4 dE/dx vs PSTAR (log-log) — shape agreement across 2–150 MeV; (b) ratio panel — median ratio close to 1, χ²/ndf annotated. **NOTE:** `data/reference/stopping_power/pstar_polystyrene.csv` is **not** present in the repo; the comparison uses the published NIST PSTAR polystyrene (ρ=1.06 g/cm³) table embedded in `_common.PSTAR_POLYSTYRENE`. | i885_v1 proton events vs NIST PSTAR |
| `VIS-MC-003_optical_chain.png` | Optical chain. 6-panel: (a) scint + WLS photon-generation distributions, (b) wavelength spectrum all-vs-detected (WLS-shifted peak), (c) effective PDE = detected/generated vs wavelength, (d) arrival-time distribution per sensor, (e) detected-PE distribution per sensor, (f) path-length distribution (fibre attenuation proxy). | i885_v1 photon tree (one 50 MeV proton run) |
| `VIS-MC-004_seed_thread_reproducibility.png` | Thread/seed reproducibility. (a) Different-seed PE distributions are independent draws about the mean (seeds 101/102 at 5 MeV); (b) mean scintillator-photon yield per seed (statistical consistency); (c) thread-scaling annotation — i885 used fixed 4-thread setup; dedicated `G4FORCENUMBEROFTHREADS` scan not in this campaign (ctest covers build-level MT). | i885_v1 multi-seed runs |
| `VIS-MC-005_data_mc_closure.png` | Data/MC closure — MC-INTERNAL. (a) MC predicted vs observed amplitude (gain×EDep); (b) residual distribution with Gaussian σ=150 ADC overlay; (c) pull distribution with N(0,1) overlay. **No single-stave testbeam data exists yet**; this is closure of the digitizer interface on MC truth + toy Gaussian noise. Pull mean ≈ 0, RMS ≈ 1 by construction. Re-run with real stave beam data when staged. | MV1/MV2 truth npz + MV0 gain |

## Verification

* **Python offline unit tests** (`geant4/single_stave/tests/test_geometry_report_offline.py`): **7/7 PASS** (golden report parse, wrong-thickness, fibre-outside-hole, fibre-not-protruding, selfcheck-fail, Geant4-overlap-message, missing-key). Ran on the login node with `PYTHONNOUSERSITE=1`.
* **ctest (single-stave Geant4 binary):** requires Geant4/11.2.2 (compute-node only). Build+ctest submitted as `sbatch` job `3415923` (account `hep2023-1-3`, partition `hep`); see `geant4/single_stave/ccb_clD_build2_*.out` for output. The 3 ctest cases are `ccb_stave_geometry_smoke`, `ccb_stave_proton_smoke`, `ccb_stave_wls_profile` (CMakeLists.txt).
* **Standalone study scripts** all return rc=0 with JSON + PNG + REPORT.md emitted; no swallowed exceptions.

## Residue (kept out of this PR)

* Raw ROOT campaign files (`ccb-runs/i885_v1/*.root` etc., 3.4 GB total) stay on fs10 — not committed (they are gitignored as data).
* The Krakow 1M MC (`geant4/data/output_krakow_1M.root`, 677 MB) is likewise gitignored; the worktree symlinks to the main checkout's copy.
* The `s00_selected_b_pulses.csv.gz` data table is the device-calibration bridge to MV0/MV3; it is referenced by absolute path and not committed.
* `mv_runs/*/truth_tracks.npz` (~1 MB) — MV1/MV2 truth extracts — are kept for traceability but not committed; they regenerate deterministically from the MC + seed.

## Reproduce

```bash
ssh lunarc
cd /projects/hep/fs10/shared/nnbar/billy/ccb-wt-clD
export MPLCONFIGDIR=/projects/hep/fs10/shared/nnbar/billy/.mplcache
export PYTHONNOUSERSITE=1
PY=/projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/python
MC=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root
DATA=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
OUT=reports/studies/clusterD/mv_runs

# MV0–MV6
$PY scripts/mv1_mv2_truth_pid_energy.py     --mc $MC --out $OUT/mv1_mv2 --max-events 200000
$PY scripts/mv3_stopping_v3.py              --mc $MC --data $DATA --out $OUT/mv3 --max-events 200000 --gain 92 --peak-frac 0.75 --net-threshold 100
$PY scripts/mv0_calibrate_from_data.py      --mc $MC --data-csv $DATA --truth-npz $OUT/mv1_mv2/truth_tracks.npz --out $OUT/mv0 --max-events 200000
$PY scripts/mv4_timing_study.py             --out $OUT/mv4 --mc $MC --calibration $OUT/mv0/calibration.json --synthetic 5000 --max-tracks 5000 --max-events 50000
$PY scripts/mv5_pileup_study.py             --truth $OUT/mv1_mv2/truth_tracks.npz --out $OUT/mv5 --n-spill 5000 --n-overlap 4
$PY scripts/mv6_representation_study.py     --mc $MC --out $OUT/mv6 --max-events 50000 --max-tracks 5000

# Campaign aggregation + VIS-MC
$PY scripts/single_stave/campaign_plots/plot_i885_campaign.py          reports/studies/clusterD/figures
$PY scripts/single_stave/campaign_plots/analyze_birks_suppression.py   reports/studies/clusterD/figures
$PY scripts/single_stave/campaign_plots/sipm_sensitivity.py            reports/studies/clusterD/figures
$PY scripts/single_stave/campaign_plots/single_stave_diagnostics.py    reports/studies/clusterD/figures

# ctest (compute node)
sbatch -A hep2023-1-3 -p hep -N1 -c8 -t 01:00:00 geant4/single_stave/slurm/build.sh build
```
