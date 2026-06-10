# P10f: template tail-shape saturation and current transfer

Ticket `1781021825.1891.293d03cc`. Raw B-stack ROOT under `data/root/root` was used directly; no Monte Carlo was used.

## Raw reproduction first

| quantity                            |   expected |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| S00/S01 selected B-stave pulses     |  640737    |    640737    |       0 |       0     | True   |
| analysis selected rows              |  377362    |    377362    |       0 |       0     | True   |
| S10b traditional template live10 ns |     124.79 |       124.79 |       0 |       1e-06 | True   |

## Methods

Evaluation is leave-one-run-out over analysis runs. For every held-out run, all empirical templates and ExtraTrees models are fit after excluding that run. CIs bootstrap held-out runs.

Traditional method: S01/P10 empirical median templates binned by stave, amplitude, current stratum, and saturation proxy, with stave-amplitude and stave fallbacks.

ML method: multi-output ExtraTrees conditional tail surrogate using log amplitude, stave, current stratum, and saturation/boundary flags. It predicts the aligned normalized template samples; run id, event id, and target residuals are excluded.

## Held-out summary

| method                         |   n_runs |   n_rows |   q_template_mse |   tail_mse |   live10_abs_error_ns |   live20_abs_error_ns |
|:-------------------------------|---------:|---------:|-----------------:|-----------:|----------------------:|----------------------:|
| ml_et_tail_surrogate           |       21 |    20962 |         0.137015 |   0.217524 |               25.6641 |               25.3172 |
| traditional_empirical_template |       21 |    20962 |         0.164729 |   0.25709  |               26.1153 |               21.4112 |

## ML minus traditional deltas

| comparison                                                | metric              |      delta | delta_ci95                                   |
|:----------------------------------------------------------|:--------------------|-----------:|:---------------------------------------------|
| ml_et_tail_surrogate minus traditional_empirical_template | q_template_mse      | -0.0277144 | [-0.03045337787083414, -0.02521630793092528] |
| ml_et_tail_surrogate minus traditional_empirical_template | tail_mse            | -0.039566  | [-0.04454995836695658, -0.03489757071592539] |
| ml_et_tail_surrogate minus traditional_empirical_template | live10_abs_error_ns | -0.451225  | [-0.7665909446077757, -0.1577398017819926]   |
| ml_et_tail_surrogate minus traditional_empirical_template | live20_abs_error_ns |  3.90594   | [3.536235478373989, 4.252802533304211]       |

## Current and saturation strata

| method                         | current_stratum   | saturation_bin   |    n |   n_runs |   tail_mse |   live10_abs_error_ns |   live20_abs_error_ns |
|:-------------------------------|:------------------|:-----------------|-----:|---------:|-----------:|----------------------:|----------------------:|
| ml_et_tail_surrogate           | high_20nA         | boundary         | 1383 |       12 |  0.0302685 |               6.78959 |               7.04989 |
| traditional_empirical_template | high_20nA         | boundary         | 1383 |       12 |  0.0414992 |              16.0882  |              16.3919  |
| ml_et_tail_surrogate           | high_20nA         | saturated_proxy  |  665 |       12 |  0.0361699 |               4.69173 |               4.69173 |
| traditional_empirical_template | high_20nA         | saturated_proxy  |  665 |       12 |  0.0502891 |              14.1654  |              14.1654  |
| ml_et_tail_surrogate           | high_20nA         | unsaturated      | 9505 |       12 |  0.32552   |              34.1684  |              33.3536  |
| traditional_empirical_template | high_20nA         | unsaturated      | 9505 |       12 |  0.380121  |              32.4138  |              26.2645  |
| ml_et_tail_surrogate           | low_2nA           | boundary         |  188 |        2 |  0.0322619 |               4.30851 |               4.30851 |
| traditional_empirical_template | low_2nA           | boundary         |  188 |        2 |  0.0421057 |              13.6702  |              13.6702  |
| ml_et_tail_surrogate           | low_2nA           | saturated_proxy  |   81 |        2 |  0.0244681 |               2.71605 |               2.71605 |
| traditional_empirical_template | low_2nA           | saturated_proxy  |   81 |        2 |  0.0313882 |               5.92593 |               5.92593 |
| ml_et_tail_surrogate           | low_2nA           | unsaturated      |  707 |        2 |  0.19416   |              19.6517  |              22.119   |
| traditional_empirical_template | low_2nA           | unsaturated      |  707 |        2 |  0.243882  |              18.6647  |              13.6284  |
| ml_et_tail_surrogate           | sample_ii         | boundary         |  960 |        7 |  0.0485877 |              13.4271  |              13.4167  |
| traditional_empirical_template | sample_ii         | boundary         |  960 |        7 |  0.0611254 |              21.1146  |              21.2083  |
| ml_et_tail_surrogate           | sample_ii         | saturated_proxy  |  344 |        7 |  0.0765166 |              10.7558  |              10.7558  |
| traditional_empirical_template | sample_ii         | saturated_proxy  |  344 |        7 |  0.0980213 |              19.9419  |              19.9419  |
| ml_et_tail_surrogate           | sample_ii         | unsaturated      | 7129 |        7 |  0.17313   |              25.5882  |              24.8484  |
| traditional_empirical_template | sample_ii         | unsaturated      | 7129 |        7 |  0.204077  |              24.6372  |              19.1213  |

## Leakage audit

- Held-out runs absent from train: `True`.
- Train/eval `(run,event,evt,stave)` overlap: `0`.
- Feature matrix excludes run id and event id: `True`.
- Real ML live10 absolute error on held-out rows: `26.18` ns.
- Shuffled live10 absolute error on held-out rows: `23.08` ns.
- Too-good trigger fired: `False`.

## Finding

The best held-out tail MSE is `ml_et_tail_surrogate` at `0.217524`. The ML-minus-traditional live10 absolute-error delta is `-0.4512` ns with run-bootstrap CI `[-0.7665909446077757, -0.1577398017819926]`, but the shuffled-live10 control is not worse than the real ML live10 prediction, so the live10 gain is not promoted as a trustworthy transfer claim. The stable result is narrower: ExtraTrees improves q/tail-shape MSE, while live-time and live20 transfer still need a better target/control.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10f_1781021825_1891_293d03cc_tail_shape_transfer.py --config configs/p10f_1781021825_1891_293d03cc_tail_shape_transfer.json
```
