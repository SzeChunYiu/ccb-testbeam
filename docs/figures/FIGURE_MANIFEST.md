# Figure Manifest — CCB Test-Beam Wiki

Post-external-review figure set. Every figure listed as **new / rebuilt / promoted** below is
reproducible end-to-end by:

```bash
/home/billy/anaconda3/envs/nnbar_env/bin/python scripts/generate_postreview_figures.py
```

which writes each figure as **PNG (600 dpi) + SVG + PDF** into `docs/figures/` (editable text,
shared `nature-figure` rcParams and palette). The earlier wiki figures (03–07, 09_systematic,
10_ml, 24) are produced by `scripts/generate_wiki_figures.py` (PNG at 200 dpi).

Style: sans-serif, editable SVG/PDF text, font.size 7, no top/right spines; one neutral (grey)
family + one signal (blue) family per figure, with green/red reserved for gains/drops and
struck-out (retracted) quantities. Colorblind-safe.

---

## New figures (this pass)

| File | Core conclusion (one sentence) | Archetype | n / error bars | Source |
|---|---|---|---|---|
| `25_mv3_trigger_rootcause` | The unsimulated A·B coincidence trigger — not missing material — is the root cause of the MV3 stopping-depth failure (χ²/ndf 68,269 → 555). | asymmetric hero + subordinate | n = 306,745 data / 1e6 MC; exact χ²/ndf & fractions (no CIs) | `reports/phase2_geometry_1783108797/mv3v4_grid.json` (+ MV3 ref 68,269) |
| `26_mv6b_c12_ruled_out` | C12 recoils cannot be the data's 4.4% early-peak class — 0/1,656 pass A>1000 quenched and MC early-peak fraction is 0.000% everywhere. | quantitative grid | counts (no CIs) | `reports/phase4_1783180742/REPORT.md`, `reports/mv6b_anomaly_quenching_1783180742/` |
| `27_mc_taueff_vs_data` | The first independent MC pile-up live-time honestly disagrees with data by +8% (134.99 vs 124.79 ns), replacing the retracted "MC confirms R_max". | quantitative grid | n_aligned 6,000/stave; bootstrap 95% CI (300 resamples); data band = S10 CI | `reports/mc03_overlay_1783180480/result.json` |
| `28_gain_honest_band` | There is no precision digitizer gain yet — both published values are retracted; the trigger-consistent band is ≈ 60–80 ADC/MeV. | schematic + scan inset | χ²/ndf point values (no CIs) | `reports/phase2_geometry_1783108797/mv3v4_grid.json` (retractions: External Review 2026-07-02) |
| `29_fdr_census` | Program-level multiplicity control is necessary but not sufficient — 11/17 wins survive BH, yet BH-surviving S03k was still falsified by leakage grids. | quantitative grid + callout | 1,948 claims / 152 studies; BH q=0.05 within family | `reports/stats01_program_fdr_20260703_220116/REPORT.md` |
| `30_twopulse_riskcoverage` | Two-pulse recovery is a split verdict — the template fit wins at matched 80% coverage, compact ML at full coverage. | quantitative grid | 600,000 overlays; bootstrap CIs on failure rates in artifact | `reports/mc03_overlay_1783180480/` (risk_coverage_curves.csv, result.json) |

## Promoted figures (rebuilt to the shared style as curated wiki panels)

| File | Core conclusion | Archetype | n / error bars | Source |
|---|---|---|---|---|
| `31_s22_timing_vs_amplitude` | Pair-difference timing sharpens with amplitude along a 1/A timewalk law, σ(A) = √(c² + k²(1000/A)²). | quantitative grid | 200-bootstrap 95% CI per amplitude bin | `reports/s22_timing_vs_amplitude_1783108999/` (s22_curves.csv, s22_summary.json) |
| `32_s23_data_enrichment` | The trigger-driven Sample-I deuteron enrichment is confirmed in the data (B2 high-amp ratio 3.45) and MC under-predicts the between-sample contrast. | quantitative grid | 95% bootstrap CI; n = 640,737 data / 458,712 MC | `reports/s23_sample12_data_mc_1783108675/s23_summary.json` |
| `24_s21_denrichment` | Sample I (A·B coincidence) enriches deuterons in the upstream B staves at truth level (B2 ratio 1.519). | quantitative grid | 95% binomial / 16–84% quantile spans | `reports/s21_sample12_trigger_truth_1783077969/s21_summary.json` (kept from prior pass) |

## Rebuilt in place (filename kept so existing links resolve; content corrected)

| File | Change | Status | Source |
|---|---|---|---|
| `08_c12_anomaly` | Now carries the MV6b "C12 ruled out" content (identical to `26_mv6b_c12_ruled_out`); the wiki points to fig 26. | rebuilt | `reports/phase4_1783180742/REPORT.md` |
| `18_gain_calibration` | Now the honest 60–80 gain band (identical to `28_gain_honest_band`); wiki points to fig 28. | rebuilt | `reports/phase2_geometry_1783108797/mv3v4_grid.json` |
| `09_rmax_correction` | Reframed: 4.22 MHz retracted-as-a-value → R_max ≤ 3.05 MHz one-sided bound; censoring-aware τ implies ≈2.1 MHz; MV5 retracted. | rebuilt | S10 τ estimators; `reports/mc03_overlay_1783180480/` (MC τ_eff) |
| `19_pedestal_comparison` | Real MV7 zero-signal MC numbers: adaptive MAE 3.48 vs learned 1.50 ADC (lower bounds). | rebuilt | `reports/mc02_pulse_table_1783107862/mv7_pedestal_validation.json` |

## Retired (files left on disk; **no longer referenced by WIKI.md**)

These assert claims retracted by the 2026-07-02 external review. They are not deleted (to avoid
breaking any external deep links) but the wiki no longer references them; do not cite them.

| File | Why retired |
|---|---|
| `10_c12_discovery_story` | C12 "discovery" narrative — species attribution retracted (see fig 26). |
| `12_stopping_depth_failure` | Superseded by the trigger-root-cause hero (fig 25); the "missing material" framing was falsified. |
| `07_b2_covariance` | B2 covariance validation withdrawn 2026-07-03. |
| `21_twopulse_recovery` | Built on the rigged S11a table (0.295/0.168); superseded by the honest benchmark (fig 30). |
| `13_timing_mc_vs_data` | Pre-review MV4 timing comparison; superseded by the honest rerun (fig 04) and S22 (fig 31). |

## QA (nature-figure qa-contract)

- Every quantitative panel has axis labels with units; error-bar definitions are stated in each
  wiki caption and in this manifest (bootstrap 95% CI, binomial CI, or "counts/point values — no
  CI" where the artifact provides none).
- One restrained palette per figure; green/red used only for gains/drops/retracted; grayscale-safe.
- Editable text in SVG/PDF (`svg.fonttype=none`, `pdf.fonttype=42`); legible at print size (7 pt).
- No figure asserts a retracted claim: MV5 "MC confirms R_max", MV6 "C12", the MV0 gain values,
  and the S11a 0.295/0.168 table are all shown as retracted/struck or omitted.
