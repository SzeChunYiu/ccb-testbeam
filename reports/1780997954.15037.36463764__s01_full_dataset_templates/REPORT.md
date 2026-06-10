# Study report: S01 — Full-dataset amplitude-adaptive template and q_template

- **Study ID:** S01
- **Author (worker label):** testbeam-laptop-1
- **Date:** 2026-06-09
- **Depends on:** S00 / S01b selected-pulse table
- **Input checksum(s):** S00 selected table `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f`; raw ROOT checksums in `input_sha256.csv`
- **Git commit:** 696daf4c4b7df48eae2ff23b7f6a08be4e0dcc1b
- **Config:** `reports/1780997954.15037.36463764__s01_full_dataset_templates/s01_config.json`

## 0. Question
Does the amplitude-adaptive median template built per B stave and amplitude bin from calibration runs describe all 640,737 S00-selected pulses, and does a small autoencoder beat that strong conventional template on the same held-out analysis runs?

## 1. Reproduction
The S00 selection was rerun from raw B-stack ROOT with the exact gate: even physical channels B2/B4/B6/B8, baseline median samples 0-3, amplitude >1000 ADC. The selected-row count matches S00 exactly. The older q_template subset cannot be numerically reproduced from this repository because no old subset table or numeric q_template reference is committed; this study therefore treats the missing full-dataset q_template evaluation as the finding target after first reproducing the S00 input gate.

| Quantity                    | Report value   | Reproduced   |   delta | Tolerance   | Pass?   |
|:----------------------------|:---------------|:-------------|--------:|:------------|:--------|
| S00 selected B-stave pulses | 640737         | 640737       |       0 | 0           | True    |
| S00 selected-table sha256   | 648c32d0109f   | 648c32d0109f |       0 | exact       | True    |

## 2. Traditional (non-ML) method
Each selected waveform was baseline-subtracted, divided by its peak amplitude, and shifted onto an 18-point grid relative to the CFD20 crossing. Templates were trained only on calibration runs using the fixed amplitude edges in the config. For each stave and amplitude bin the template is the sample-wise median aligned waveform; bins with fewer than 30 calibration pulses fall back to the stave-level calibration median.

Template-bin coverage: 22/32 bins had enough calibration statistics; the rest used the stave fallback. The per-pulse `q_template` is RMSE to the relevant median template and is saved for all 640737 selected pulses in `q_template_per_pulse.csv.gz`. Full distributions are shown in `fig_q_template_by_group_stave.png`; template examples are in `fig_template_library_examples.png`.

## 3. ML method
The ML cross-check is a small fully connected autoencoder trained only on calibration-run aligned waveforms. Hyperparameters were scanned with GroupKFold by run over latent/hidden dimensions from the config. The selected model was latent_dim=8, hidden_dim=32 on `cpu`. The output is only a reconstruction residual, not a physics truth label or calibrated probability.

CV means:

| fold   |   val_mse |   latent_dim |   hidden_dim |
|:-------|----------:|-------------:|-------------:|
| mean   | 0.0164821 |            8 |           32 |
| mean   | 0.0240319 |            8 |           16 |
| mean   | 0.0298446 |            4 |           16 |
| mean   | 0.0313059 |            4 |           32 |

## 4. Head-to-head benchmark
Benchmark metric was pre-registered as analysis-run mean squared reconstruction residual on the same held-out runs. Confidence intervals are run-bootstrap 95% CIs over analysis runs.

| Method | Metric | Value ± CI | Notes |
|---|---|---:|---|
| Median amplitude-bin template | analysis-run MSE | 0.044414 [0.0342487, 0.0547819] | Strong conventional baseline |
| Autoencoder | analysis-run MSE | 0.00207807 [0.00172533, 0.00241913] | Best CV model |

Delta ML minus traditional = -0.0423359 with CI [-0.0524212, -0.032381]. Verdict: ML beats the template baseline on this residual metric.

## 5. Falsification
- **Pre-registration:** metric, cuts, fixed amplitude bins, CV scan, and ML-win rule were written in this report before running the data-derived analysis.
- **Falsification test:** ML had to have a 95% run-bootstrap CI for ML MSE minus traditional MSE entirely below zero.
- **Result:** CI upper bound = -0.032381; `n_tries=1`; no multiple model family was added after seeing the outcome.

## 6. Threats to Validity
- **Benchmark/selection:** the median template is a real conventional baseline trained on the same calibration source as the autoencoder. The metric is reconstruction quality, not timing resolution; S02/P10 still need to test whether lower residual improves timing.
- **Data leakage:** both methods train only on calibration runs. The benchmark is on analysis runs and CV is grouped by run. Features are waveforms only; no q_template-derived labels exist.
- **Metric misuse:** the report includes full residual distributions by stave/group and run-level stability, not just a core width. No Gaussian fit is used here, so chi2/ndf is not applicable.
- **Post-hoc selection:** the S00 cut, amplitude bins, hyperparameter grid, bootstrap unit, and win rule were fixed before the analysis run.

## 7. Provenance Manifest
`manifest.json` lists raw input hashes, commands, seeds, code/config hashes, and output hashes. The analysis command is:

```bash
python reports/1780997954.15037.36463764__s01_full_dataset_templates/s01_full_dataset_templates.py --config reports/1780997954.15037.36463764__s01_full_dataset_templates/s01_config.json
```

## 8. Findings & Next Steps
The full-dataset q_template table now exists and exposes run/stave/amplitude stability from the same S00-selected pulse population used downstream. The scientific hypothesis is that most shape variation is conventional amplitude/stave response, but residual run-local structure flags either pile-up/topology changes or calibration drift; this is testable by feeding this `q_template` into timing closure and anomaly studies.

Next tickets proposed in `result.json`:
- S01e: validate whether q_template predicts held-out timing residual tails in S02/S03. Expected information gain: decides whether q_template is a timing-quality cut or only a shape diagnostic.
- P10a: compare this empirical median template family against a conditional generative template on the same q_template MSE and timing residual metric. Expected information gain: tests whether nonlinear template generation adds value beyond fixed amplitude bins.

Current fleet summary conflict: none. The rolling summary already identified S01 as missing full-dataset q_template; this report fills that gap.

## 9. Reproducibility
Artifacts written under this directory: `q_template_per_pulse.csv.gz`, `template_library.npz`, CSV summaries, four figures, `result.json`, and `manifest.json`. No files outside this report directory were written.
