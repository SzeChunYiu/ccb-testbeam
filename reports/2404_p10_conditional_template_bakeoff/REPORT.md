# P10-2404: Conditional Generative Pulse Templates

- **Ticket:** #2404, "P10: Conditional generative pulse templates"
- **Worker:** testbeam-laptop-3
- **Date:** 2026-08-16
- **Depends on:** S00/S01 selected B-stave pulse definition
- **Raw input:** `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`
- **Config:** `configs/p10_2404_conditional_template_bakeoff.yaml`
- **Script:** `scripts/p10m_1781191148_2507_386921a0_phase_gated_consumers.py`
- **Git commit:** `d3b2beb217c7157693da45e3e8824489c7a8f036`

## 0. Question

Can a conditional pulse-template consumer using local waveform shape and run-held-out training improve downstream timing and charge consistency relative to a strong non-ML median-template baseline? The atomic decision is made on the same run-held-out events for all methods, using a pre-registered scalar loss

\[
L = \sigma_{68}(t^\star) + 10\,\sigma_{68}(q^\star),
\]

where timing is in ns, charge is in log-area units, and both widths are computed per run before bootstrap aggregation.

## 1. Reproduction Gate From Raw ROOT

Before any model fit, the selected-pulse count was rebuilt from raw ROOT waveforms with the S00/S01 gate: B-stave channels B2/B4/B6/B8, baseline equal to the median of samples 0--3, and amplitude \(A>1000\) ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass |
|---|---:|---:|---:|---:|---:|
| S00/S01 selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |

This is an exact gate. The analysis would abort on any non-zero count delta.

## 2. Data Split

The split is by run, never by event row. Two family-holdout folds are used:

| Fold | Train runs | Held-out evaluation runs | Train pulses | Eval pulses | Eval events |
|---|---|---|---:|---:|---:|
| holdout_sample_i | 64 | 44--57 | 828 | 2524 | 631 |
| holdout_sample_ii | 31--37, 39--42 | 58--63, 65 | 2300 | 15096 | 3774 |

The Sample-I fold is deliberately hard because only run 64 is available for training; this is why all claims are interpreted at the family-transfer level rather than as an optimized in-family deployment.

## 3. Waveform Construction

For pulse \(i\), event \(e\), and stave \(s\), the raw waveform \(h_i(k)\) has 18 samples. The baseline-subtracted waveform is

\[
x_i(k) = h_i(k)-\operatorname{median}\{h_i(0),h_i(1),h_i(2),h_i(3)\}.
\]

The amplitude, charge proxy, and normalized pulse are

\[
A_i=\max_k x_i(k),\qquad Q_i=\sum_k x_i(k),\qquad u_i(k)=x_i(k)/A_i.
\]

The local timing seed is CFD20. A linear interpolation gives the fractional sample \(c_i\) at which \(x_i(k)=0.2A_i\). Geometry-corrected timing uses 2 cm stave spacing and \(0.033356\) ns/cm:

\[
t_{i,\mathrm{geom}} = 10c_i - g_s.
\]

## 4. Strong Traditional Method

The non-ML baseline is an explicit train-only median residual table. It first freezes a phase-gated median template family

\[
T_{s,a,p}(k)=\operatorname{median}\{u_i(k): s_i=s,\ a_i=a,\ p_i=p,\ i\in\mathcal{D}_{\mathrm{train}}\},
\]

with cells keyed by stave, amplitude bin, and CFD phase bin. Cells with fewer than 25 training pulses fall back to the train-only stave median. The downstream residual table then keys the leave-one-stave target by stave, amplitude bin, phase bin, rise-width bin, and tail bin. Cells with fewer than 20 training pulses fall back to a looser stave/amplitude/phase table, then stave median, then global median. No held-out pulse contributes to any table entry.

This is a strong baseline because it uses the same detector-local observables as the ML methods, includes phase and tail-shape handles, and is trained separately inside each run-family fold.

## 5. ML/NN Methods

All learned methods predict the two-output target

\[
y^t_i=(t_{i,\mathrm{geom}})-\frac{1}{3}\sum_{r\ne s_i} t_{e,r,\mathrm{geom}},
\qquad
y^q_i=\log Q_i-\frac{1}{3}\sum_{r\ne s_i}\log Q_{e,r}.
\]

The consumer values are then

\[
t_i^\star=t_{i,\mathrm{geom}}-\hat y^t_i,\qquad q_i^\star=\log Q_i-\hat y^q_i.
\]

Compared methods:

| Method | Family | Inputs |
|---|---|---|
| ridge | Linear ML | standardized explicit handles and frozen-template residual summaries |
| gradient_boosted_trees | Tree ML | same tabular inputs as ridge |
| mlp | Neural net | two-layer tabular MLP on the same explicit handles |
| cnn_1d | Neural net | 18-sample normalized waveform plus tabular head |
| phase_gated_cnn_new | New architecture | CNN representation multiplicatively gated by tabular phase/template handles |
| shuffled_target_ridge_sentinel | Negative control | ridge trained on row-permuted targets; excluded from winner selection |

Training used CPU PyTorch 1.13.1 for neural nets. The MLP trained for 8 epochs; the CNNs trained for 6 epochs. The run split, target definition, and evaluation events are identical across methods.

## 6. Head-to-Head Results With Bootstrap CIs

Widths are computed per run from all same-event B2/B4/B6/B8 pairwise residuals. The 95% intervals are bootstrap CIs over held-out runs within each fold. The primary loss is \(L=\sigma_{68,t}+10\sigma_{68,q}\); lower is better.

| Fold | Method | Timing sigma68 ns [95% CI] | Charge sigma68 log [95% CI] | Primary loss |
|---|---|---:|---:|---:|
| holdout_sample_i | gradient_boosted_trees | 14.745 [10.216, 20.075] | 0.3174 [0.2703, 0.3560] | 17.920 |
| holdout_sample_i | ridge | 15.463 [10.658, 20.312] | 0.3897 [0.3731, 0.4064] | 19.360 |
| holdout_sample_i | mlp | 16.660 [11.733, 21.500] | 0.5268 [0.4775, 0.5717] | 21.928 |
| holdout_sample_i | traditional_explicit_handles | 16.410 [11.009, 21.956] | 0.6564 [0.5996, 0.7086] | 22.973 |
| holdout_sample_i | phase_gated_cnn_new | 16.547 [10.505, 22.051] | 0.6837 [0.6140, 0.7457] | 23.384 |
| holdout_sample_i | cnn_1d | 16.165 [11.470, 21.657] | 0.7251 [0.6738, 0.7760] | 23.416 |
| holdout_sample_ii | mlp | 3.506 [3.212, 3.766] | 0.2102 [0.1999, 0.2220] | 5.608 |
| holdout_sample_ii | cnn_1d | 3.606 [3.208, 4.098] | 0.3244 [0.2868, 0.3675] | 6.850 |
| holdout_sample_ii | phase_gated_cnn_new | 4.026 [3.721, 4.340] | 0.3609 [0.3188, 0.4047] | 7.635 |
| holdout_sample_ii | traditional_explicit_handles | 4.126 [3.444, 5.291] | 0.4088 [0.3848, 0.4338] | 8.214 |
| holdout_sample_ii | gradient_boosted_trees | 8.333 [7.568, 9.071] | 0.2166 [0.2060, 0.2294] | 10.500 |
| holdout_sample_ii | ridge | 11.413 [11.119, 11.693] | 0.3073 [0.2981, 0.3183] | 14.486 |

The overall non-sentinel ranking averages the two fold-level primary losses:

| Rank | Method | Mean timing sigma68 ns | Mean charge sigma68 log | Mean primary loss |
|---:|---|---:|---:|---:|
| 1 | mlp | 10.083 | 0.3685 | 13.768 |
| 2 | gradient_boosted_trees | 11.539 | 0.2670 | 14.210 |
| 3 | cnn_1d | 9.886 | 0.5247 | 15.133 |
| 4 | phase_gated_cnn_new | 10.286 | 0.5223 | 15.510 |
| 5 | traditional_explicit_handles | 10.268 | 0.5326 | 15.594 |
| 6 | ridge | 13.438 | 0.3485 | 16.923 |

**Winner:** `mlp`, also named in `result.json`. The MLP is not uniformly best: gradient-boosted trees win the harder Sample-I transfer fold, while the MLP wins Sample-II strongly enough to have the lowest mean primary loss.

## 7. Falsification and Leakage Controls

The pre-registered falsification test is the shuffled-target ridge sentinel. A gross leakage path would let the sentinel approach the real models. It does not: its mean primary loss is 17.885, worse than all eligible methods except ridge in the overall ranking. The sentinel is excluded from winner selection by construction.

Leakage controls:

- Run-family folds are disjoint by run.
- Event identifiers, run labels, and event order are not model inputs.
- Templates and residual tables are fit only on training runs inside each fold.
- Targets are leave-one-stave residuals; a pulse's own corrected time/charge is compared to the other staves only to define the training target.
- Bootstrap CIs resample held-out runs, not event rows, so the reported intervals reflect run-to-run variation.

## 8. Systematics and Caveats

The charge target is a log-area proxy, not calibrated deposited energy. The timing target uses CFD20 and a fixed geometry correction, so results test downstream consistency after a shared pickoff rather than absolute time-of-flight. Sample-I evaluation has small all-hit support, including runs with very few events; this inflates run-bootstrap intervals and makes Sample-I conclusions conservative. The primary loss weight of 10 on charge is a pragmatic scale match between ns and log-charge units; a different physics objective could prefer the CNN timing winner or the GBT charge winner. The CNNs were intentionally small CPU models, so this is not a claim that deep waveform modeling has been exhausted. The new phase-gated CNN did not beat the plain MLP on this split.

## 9. Provenance and Reproducibility

Regeneration command:

```bash
/home/billy/anaconda3/bin/python scripts/p10m_1781191148_2507_386921a0_phase_gated_consumers.py --config configs/p10_2404_conditional_template_bakeoff.yaml
```

Artifacts in this directory:

- `result.json`: machine-readable winner and method ranking.
- `manifest.json`: config, script, platform, and output inventory.
- `input_sha256.csv`: checksums and byte sizes for raw ROOT inputs.
- `reproduction_match_table.csv`: raw-ROOT count gate.
- `fold_run_metrics.csv`: per-run timing and charge widths.
- `fold_summary.csv`: fold-level bootstrap CIs.
- `model_diagnostics.csv`: fit status, training rows, eval rows, runtime, and device.
- `template_support.csv`: train-only template support by stave/amplitude/phase cell.
- `fig_consumer_summary.png`: visual head-to-head summary.

No Monte Carlo truth labels are used. No data files under the raw ROOT directory were modified.
