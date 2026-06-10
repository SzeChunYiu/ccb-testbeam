# Study report: S07 - ML rigour pass, current/topology proxy scoreboard

- **Study ID:** S07
- **Ticket:** 1780997954.15217.702122ea
- **Author (worker label):** testbeam-laptop-4
- **Date:** 2026-06-09
- **Depends on:** S00
- **Input checksums:** `input_sha256.csv` records all 33 B-stack raw ROOT files used for the S00 reproduction. First pinned file: `data/root/root/hrdb_run_0031.root`, sha256 `9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7`.
- **Git commit:** `696daf4c4b7df48eae2ff23b7f6a08be4e0dcc1b`
- **Config:** `configs/s07_ml_rigour_scoreboard.yaml`

## 0. Question
Can an App.H-like waveform-shape classifier distinguish 2 nA low-current runs from 20 nA high-current Sample-I analysis runs under S07 rigour rules: raw-ROOT reproduction first, run-held-out folds, no run/stave/amplitude label leakage, hyperparameter scan, calibration, bootstrap CIs, and a fair traditional baseline?

This is an atomic S07 scoreboard slice for the current/topology proxy. Timing-control labels such as `D_t` and `q_template` are not present in raw `HRDv`; follow-up tickets below should cover those derived-label classifiers from their derived tables.

## 1. Reproduction
The script first re-scans raw B-stack `HRDv` waveforms using the S00 rule: even physical channels B2/B4/B6/B8, baseline median samples 0-3, amplitude `A=max(w-baseline)`, and `A>1000` ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_i_calib selected pulses | 248745 | 248745 | 0 | 0 | yes |
| sample_i_analysis selected pulses | 252266 | 252266 | 0 | 0 | yes |
| sample_ii_calib selected pulses | 14630 | 14630 | 0 | 0 | yes |
| sample_ii_analysis selected pulses | 125096 | 125096 | 0 | 0 | yes |

Full run counts are in `reproduction_counts_by_run.csv`; the match table is `reproduction_match_table.csv`.

## 2. Traditional method
The traditional comparator is the best one-dimensional waveform-shape score selected inside each training fold from pre-registered candidates: `tail_fraction`, `late_fraction`, `area_over_peak`, `peak_sample`, `max_down_step`, and `final_fraction`, with both signs tested. The selected scores were `-late_fraction` in fold 1 and `-peak_sample` in fold 2.

It is intentionally stronger than a fixed arbitrary cut, but still interpretable and non-ML. No parametric distribution fit is used, so chi2/ndf is not applicable. Full score distributions are represented by the ROC/PR curves in `fig_roc_pr.png` and calibration bins in `fig_reliability.png`.

Result: ROC AUC `0.504` with bootstrap 95% CI `[0.491, 0.517]`; AP `0.195` with CI `[0.186, 0.204]`; cross-fold isotonic Brier `0.203`.

## 3. ML method
The ML method is a random forest on waveform-shape features only: 18 amplitude-normalised samples plus the six hand-built shape features above. It excludes run id, current, stave id, absolute amplitude, hit multiplicity, and any timing-derived label feature.

Split is by run. Fold 1 holds out low-current run 46 plus high-current runs 44,45,48-51; fold 2 holds out low-current run 47 plus high-current runs 52-57. Hyperparameters scanned:

| n_estimators | max_depth | min_samples_leaf | ROC AUC |
|---:|---:|---:|---:|
| 250 | 7 | 20 | 0.768 |
| 150 | 5 | 30 | 0.764 |
| 250 | 5 | 30 | 0.763 |
| 150 | 3 | 50 | 0.756 |

Best model: 250 trees, max depth 7, min leaf 20. Probabilities are calibrated with isotonic calibration across the held-out folds rather than on the same fold being evaluated. Bootstrap CIs use 800 resamples.

Result: ROC AUC `0.768` with bootstrap 95% CI `[0.758, 0.778]`; AP `0.390` with CI `[0.371, 0.411]`; cross-fold isotonic Brier `0.145`.

## 4. Head-to-head benchmark
Both methods are evaluated on the same held-out run folds with the same positive class: a selected pulse from a 2 nA low-current run.

| Method | Metric | Value +/- CI | Notes |
|---|---|---|---|
| Traditional single-shape-variable score | ROC AUC | 0.504 [0.491, 0.517] | Best fold-local one-dimensional shape score |
| Calibrated RF waveform-shape model | ROC AUC | 0.768 [0.758, 0.778] | Best scanned RF, run-held-out OOF |

Verdict: ML beats the traditional score by AUC `+0.264`, bootstrap CI `[0.250, 0.280]`. This is useful as a current/topology proxy ranking, not a calibrated beam-pile-up probability or truth label.

## 5. Falsification
- **Pre-registration:** before outcome inspection, the metric was run-held-out low-current ROC AUC on the fold plan in `configs/s07_ml_rigour_scoreboard.yaml`. Positive label is 2 nA current. Features exclude run, stave id, absolute amplitude, and timing-derived label variables. The RF grid and traditional candidate scores are fixed in the config.
- **Falsification test:** if the paired bootstrap CI for ML minus traditional AUC crossed zero, or the Bonferroni-corrected one-sided p-value exceeded 0.05, the ML advantage claim would fail.
- **Result:** ML minus traditional AUC `+0.264`, CI `[0.250, 0.280]`; one-sided bootstrap p `0.00125`, Bonferroni corrected over 16 tries p `0.01998`.

## 6. Threats to validity
- **Benchmark/selection:** the baseline is not a strawman, but it is limited to one-dimensional shape scores. A stronger analytic multi-cut baseline may narrow the gap.
- **Data leakage:** split is by run. No run id, current, stave id, absolute amplitude, hit multiplicity, or label-defining timing variables are features. Calibration is cross-fold.
- **Metric misuse:** ROC AUC and AP are ranking metrics for a weak current label. The result must not be read as a pile-up probability. Brier and reliability are reported only for calibrated low-current probability.
- **Post-hoc selection:** candidates and RF grid are in the config. The p-value is corrected for 12 traditional feature/sign tries plus 4 RF hyperparameter tries.
- **Statistics:** only two 2 nA runs exist. Low-current downstream staves are sparse, especially run 46, so this result is best treated as a reusable S07 method and current-proxy result, not a final detector conclusion.

## 7. Provenance manifest
`manifest.json` contains the command, seed, input hashes, output hashes, and git commit. The command is:

```bash
python scripts/s07_ml_rigour_scoreboard.py --config configs/s07_ml_rigour_scoreboard.yaml
```

## 8. Findings and next steps
The S00 reproduction agrees with the fleet summary exactly, so there is no conflict with the current scoreboard. The new result adds an S07 row: waveform-shape RFs can separate low-current from high-current Sample-I pulses substantially better than a single hand-built shape score, but the positive class is a weak current proxy. The hypothesis is that low-current and high-current Sample-I pulses differ through a mixture of genuine beam pile-up excess and current-independent topology/pathology differences; the RF is detecting that mixture, not isolating the beam-pile-up component.

Proposed next experiments:
- **S07b: timing-control classifier calibration with `D_t` labels and bootstrap CIs.** Question: does the App.I waveform classifier still beat a direct `D_t`/curvature baseline once the 72-event positive class is bootstrapped and calibrated? Expected information gain: resolves the highest-risk small-positive-class ML claim.
- **S07c: event-level clean-timing RF vs `q_template`/downstream-span baseline.** Question: does the App.A clean-timing RF add information beyond strong conventional timing/template cuts without label leakage? Expected information gain: determines whether S03/S04/S09 should consume RF clean-timing scores or stay with analytic cuts.

## 9. Reproducibility
Artifacts written:

- `reproduction_match_table.csv`, `reproduction_counts_by_run.csv`, `reproduction_counts_by_group.csv`
- `dataset_counts.csv`, `traditional_baseline_choices.csv`, `rf_cv_scan.csv`, `scoreboard.csv`
- `fig_roc_pr.png`, `fig_reliability.png`
- `input_sha256.csv`, `manifest.json`, `result.json`

Regenerate all numbers and figures with:

```bash
python scripts/s07_ml_rigour_scoreboard.py --config configs/s07_ml_rigour_scoreboard.yaml
```
