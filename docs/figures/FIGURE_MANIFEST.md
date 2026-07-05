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
| `25_mv3_trigger_rootcause` | **(rebuilt 2026-07-05)** The real `Trig_bar` trigger moves the B2 fraction 45.9% → 99.7% (over-purifying past data 93.3%); the proxy χ²/ndf 625 is retired. | asymmetric B2-movement lollipop | n = 249,102 untriggered / 33,176 real-coincidence MC; exact fractions (no CIs) | `reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json` |
| `26_mv6b_c12_ruled_out` | C12 recoils cannot be the data's 4.4% early-peak class — 0/1,656 pass A>1000 quenched and MC early-peak fraction is 0.000% everywhere. | quantitative grid | counts (no CIs) | `reports/phase4_1783180742/REPORT.md`, `reports/mv6b_anomaly_quenching_1783180742/` |
| `27_mc_taueff_vs_data` | The first independent MC pile-up live-time honestly disagrees with data by +8% (134.99 vs 124.79 ns), replacing the retracted "MC confirms R_max". | quantitative grid | n_aligned 6,000/stave; bootstrap 95% CI (300 resamples); data band = S10 CI | `reports/mc03_overlay_1783180480/result.json` |
| `28_gain_honest_band` | There is no precision digitizer gain yet — both published values are retracted; the trigger-consistent band is ≈ 60–80 ADC/MeV. | schematic + scan inset | χ²/ndf point values (no CIs) | `reports/phase2_geometry_1783108797/mv3v4_grid.json` (retractions: External Review 2026-07-02) |
| `29_fdr_census` | **⚠ SUPERSEDED BY `44_fdr_census_refly`** (stale 1,948-claim / 11-of-17 census). Program-level multiplicity control is necessary but not sufficient — 11/17 wins survive BH, yet BH-surviving S03k was still falsified by leakage grids. | quantitative grid + callout | 1,948 claims / 152 studies; BH q=0.05 within family | `reports/stats01_program_fdr_20260703_220116/REPORT.md` |
| `30_twopulse_riskcoverage` | Two-pulse recovery is a split verdict — the template fit wins at matched 80% coverage, compact ML at full coverage. | quantitative grid | 600,000 overlays; bootstrap CIs on failure rates in artifact | `reports/mc03_overlay_1783180480/` (risk_coverage_curves.csv, result.json) |

## Post-review round 2 — real `Trig_bar` simulation + measured systematics (2026-07-05)

| File | Core conclusion (one sentence) | Archetype | n / error bars | Status | Source |
|---|---|---|---|---|---|
| `33_mv3_realtrigger` | **(round HERO)** A real GEANT4 two-arm-trigger simulation establishes the trigger (not missing material) as the MV3 mechanism (B2 45.9% → 99.7%) while over-purifying past the data (93.3%); the deep-proton veto (0.06% vs 31.1%, i.e. 99.94%) is the mechanism. Retires proxy χ²/ndf 625. | asymmetric hero (per-stave profiles + veto mechanism) | n = 249,102 untriggered / 33,176 real-coincidence MC; 233,184 data Sample I; exact fractions (no CIs) | new | `reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json` (mechanism fractions from its REPORT.md) |
| `34_gain_quenched_scan` | Quenched (Birks-on) trigger-consistent digitizer gain ≈ 65 ADC/MeV (band 60–70) — the χ² well (322 at 65) and the B2 amplitude scale (2,917 vs data 2,576 ADC) agree; 297 is a placeholder (7,752, ~24×). | quantitative grid (χ² scan + amplitude cross-check) | χ²/ndf point values (ndf 3, systematics-dominated — no sub-unit CI) | new | `reports/mv3_gain_quenched_1783240619/mv3_gain_quenched.json` |
| `35_covariance_timing` | A properly measured combined inter-stave timing σ₆₈ = 0.490 ns [0.470, 0.508] replaces the withdrawn 0.54–0.56; independence not rejected (p = 0.62); held-out confirmation blocked. | quantitative grid (covariance heatmap + per-stave/combined forest) | n = 3,820 events; 95% whole-event bootstrap CI (400 replicas) | new | `reports/s25_covariance_timing_1783241582/s25_summary.json` |
| `36_overlay_realism` | The traditional-fit two-pulse verdict is robust: it wins at matched 80% coverage across pinned / +phase-jitter / +cross-stave overlays (trad 0.0000 vs ML 0.0005–0.0010; σ₆₈ trad 0.33–0.41 vs ML 1.07–1.47 ns). | quantitative grid (failure@80% + Δt σ₆₈, three configs) | 30,000 overlays/config × 3 rates; means over rates; per-rate 95% CIs in report | new | `reports/s26_overlay_realism_1783241582/s26_summary.json` |
| `37_earlypeak_budget` | The early-peak class (3.41% of A>1000) leakage footprint per headline: timing +0.058 ns, τ_eff −13.2 ns (opposite sign to the MC–data +8% offset), pile-up/area −1.2%. | quantitative grid (per-observable forest) | n = 21,521 pairs; 95% bootstrap CI (timing); τ_eff/area point shifts | new | `reports/s27_earlypeak_budget_1783241582/s27_summary.json` |

## Audit-gap round — explain-the-data-point / provenance figures (2026-07-05)

| File | Core conclusion (one sentence) | Archetype | n / error bars | Status | Source |
|---|---|---|---|---|---|
| `38_enrichment_reconciliation` | The two enrichment headlines are NOT inconsistent: S23 data amplitude-tail ratio 3.45 [3.41, 3.50] and S21 MC-truth species-fraction ratio 1.519 [1.510, 1.528] measure DIFFERENT observables; the MC-anchored double ratio 0.738 [0.733, 0.742] (z = −99) is the reconciled cross-check, with the B-M6 run-set/beam-drift confound bounded ≤~29% (central ~3%). | quantitative grid (two ratio panels + reconciliation card) | S21/S23 per-stave 95% bootstrap CIs; run-clustered R CI [2.52, 4.64] | new | `reports/s21_sample12_trigger_truth_1783077969/s21_summary.json`, `reports/s23_sample12_data_mc_1783108675/s23_summary.json`, `reports/bm6_runset_confound_20260705_202638/bm6_summary.json` (29% is REPORT.md prose) |
| `39_new04_residual_waterfall` | The 6.4-pt MC-vs-data trigger over-purification residual is only PARTLY explained — accidentals ~2.0 [1.3, 2.6] + paddle/selection fidelity ~1.5 [0.5, 3.0] + ~2.9 pt genuinely unexplained (no forced closure); the S10 data current-excess anchor +1.03 pt [0.64, 1.42] independently brackets the accidentals. | waterfall / stacked contribution bars | first-principles ranges; ±2 pt B-M6 band; S10 anchor 95% CI | new | `reports/new04_trigger_residual_1783275727/new04_summary.json` |
| `40_mv3_closure_basis` | Basis-explicit MV3 stopping-depth closure — the untriggered B2 fraction is 45.9% (event basis) / 46.9% (track basis) / 47.2% (track incl) → real Trig_bar 99.7% → data Sample I 93.3%; fixes a basis-mix (45.9% quoted next to a track-basis χ²); proxy χ² ≈ 625 retired. | quantitative grid (basis-labelled ladder) | exact MC fractions (no CIs) | new | `reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json` |
| `41_b4_outlier_diagnostic` | B4 and B6 have ~equal median amplitude (2,368 vs 2,468 ADC) yet B4's timing σ₆₈ (1.52 ns) is 2.2× worse than B6 (0.68) — the excess is INTRINSIC (B4 is the most-upstream downstream stave), not a timewalk/amplitude effect. | quantitative grid (σ₆₈ forest + amplitude bars) | n = 3,820; σ₆₈ 95% bootstrap CI; amplitude medians on the same S25 selection | new | `reports/s25_covariance_timing_1783241582/s25_summary.json`; amplitudes from `reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz` (downstream triples, runs 58-63,65, A>1000; n=3,820 = S25 n_events) |
| `42_taueff_rmax_ladder` | The pile-up τ_eff → R_max ladder kills the retracted 90 ns / 4.22 MHz — every measured estimator (10%-cross 124.8, MC03 135.0, KM 151.6, IPCW 179.0) maps via R_max = 0.380/τ to R_max ≤ 3.05 MHz (≈2.1 MHz censoring-aware). | schematic-led composite (τ estimators + R_max) | S10g 10% + MC03 pooled 95% CIs; 90 ns / 4.22 MHz struck | new | `reports/1781028280.978.1e517fd7/result.json` (S10g), `reports/mc03_overlay_1783180480/result.json`, `reports/new04_trigger_residual_1783275727/new04_summary.json`; 90 ns/4.22 MHz retraction from `reports/mv5_pileup_1782678353/REPORT.md` |
| `43_fdr_delta_forest` | The certified traditional-fit ML-win deltas are auditable at a glance — every P04/P07 amplitude+charge Δ (0.018–0.240) excludes 0 and survives BH-FDR (z 23–166). | quantitative grid (delta-CI forest) | event-clustered 95% CIs (P04e run-block); z from CI SE; BH q=0.05 | new | `reports/bm3_p04p07_fdr_20260705_203249/stats02_delta_ci_summary.json` |
| `44_fdr_census_refly` | **SUPERSEDES `29_fdr_census`.** Refreshed program-level FDR census — 1,957 delta-CI claims / 157 studies, 1,375/1,444 nominal survive BH (amplitude-charge 432/471); of 15 scoreboard bold wins 14 survive BH, 0 fail, 1 prose-only. | quantitative grid (BH p-value plot + per-family census) | m = 1,957 claims; BH q=0.05 within family; p floored at 1e−30 for display | new | `reports/stats01_program_fdr_20260705_203905/claims.csv` (14/15 & prose-only headline from its REPORT.md) |

## Promoted figures (rebuilt to the shared style as curated wiki panels)

| File | Core conclusion | Archetype | n / error bars | Source |
|---|---|---|---|---|
| `31_s22_timing_vs_amplitude` | Pair-difference timing sharpens with amplitude along a 1/A timewalk law, σ(A) = √(c² + k²(1000/A)²). | quantitative grid | 200-bootstrap 95% CI per amplitude bin | `reports/s22_timing_vs_amplitude_1783108999/` (s22_curves.csv, s22_summary.json) |
| `32_s23_data_enrichment` | The trigger-driven Sample-I deuteron enrichment is confirmed in the data (B2 high-amp ratio 3.45) and MC under-predicts the between-sample contrast. | quantitative grid | 95% bootstrap CI; n = 640,737 data / 458,712 MC | `reports/s23_sample12_data_mc_1783108675/s23_summary.json` |
| `24_s21_denrichment` | Sample I (A·B coincidence) enriches deuterons in the upstream B staves at truth level (B2 ratio 1.519). | quantitative grid | 95% binomial / 16–84% quantile spans | `reports/s21_sample12_trigger_truth_1783077969/s21_summary.json` (kept from prior pass) |

## Rebuilt in place (filename kept so existing links resolve; content corrected)

| File | Change | Status | Source |
|---|---|---|---|
| `12_stopping_depth_failure` | **(rebuilt 2026-07-05)** The falsified "missing ~8–10 g/cm² material" root-cause card is replaced with the corrected mechanism (the two-arm trigger; ≤0.8 vs ≥10.5 g/cm² required) and a redirect to Fig 33/25; profile bars now show the real-trigger column. No retracted claim remains. Legacy `scripts/generate_all_figures.py` fig_12 text also corrected. | rebuilt | `reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json` |
| `25_mv3_trigger_rootcause` | **(rebuilt 2026-07-05)** Was a χ²/ndf ladder implying the proxy 625 as the achievement; now a B2-fraction-movement lollipop on the real-trigger result (45.9% → 99.7%, over-purifies past data 93.3%), proxy 625 shown struck/retired. | rebuilt | `reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json` |
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
  the S11a 0.295/0.168 table, the **proxy χ²/ndf ≈ 625 as MV3 closure**, and the **withdrawn
  0.54–0.56 ns combined timing** are all shown as retracted/struck or omitted. The MV3 hero
  (Fig 33) and the rebuilt Fig 25 / Fig 12 present the real `Trig_bar` result (B2 45.9% → 99.7%,
  over-purifying past data 93.3%) instead of the retired proxy 625.
