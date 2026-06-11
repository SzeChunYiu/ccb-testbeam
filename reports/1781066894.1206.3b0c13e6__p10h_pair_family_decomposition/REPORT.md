# P10h: Pair-family decomposition of B2-included explicit closure

- **Ticket:** `1781066894.1206.3b0c13e6`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Monte Carlo:** none
- **Git commit:** `740dab6d337aa045931cd8cfada0b054c3b53dfc`
- **Winner:** `event_token_attention` on the B2-included all-six-pair held-out metric.

## Abstract

This study re-runs the B2-included explicit timing-closure analysis from raw ROOT and decomposes the held-out closure into B2-containing pairs and downstream-only pairs. The original P10e result pooled these pair families; P10h asks whether the apparent improvement is specific to B2-containing residuals, whether downstream-only pairs are harmed, and whether a modern learned correction beats the strong traditional amplitude-bin residual correction under the same run split.

## Fleet Synthesis Context

The current fleet synthesis says analytic/transparent timewalk corrections usually beat or tie ML on primary timing tasks, while ML is useful when the target is independent and the signal is genuinely in waveform shape. P10h is consistent with that caution: the event-token attention model has the best B2-included all-six point estimate, but its CI overlaps the strong traditional correction, so this is a diagnostic point win rather than a production replacement claim. The result refines the P10 synthesis by showing that B2 pair-family structure remains the dominant limitation even after B2 is included in the fit.

## Raw Reproduction

The selected B-stave pulse table was rebuilt directly from `h101/HRDv` in the raw ROOT files before any timing fit. No sorted-table or Monte Carlo input is used.

| quantity                                             |   expected |   reproduced |   delta | pass   |
|:-----------------------------------------------------|-----------:|-------------:|--------:|:-------|
| S00/P10 selected B-stave pulses                      |     640737 |       640737 |       0 | True   |
| Sample-II analysis selected B-stave pulses           |     125096 |       125096 |       0 | True   |
| Sample-II calibration run 64 selected B-stave pulses |      14630 |        14630 |       0 | True   |

The all-hit B2/B4/B6/B8 timing population was also rebuilt from raw ROOT:

|   run |   n_events |   selected_pulses |   all_hit_b2_b4_b6_b8_events | used_for_external_timing   |
|------:|-----------:|------------------:|-----------------------------:|:---------------------------|
|    58 |      34141 |             16781 |                           72 | True                       |
|    59 |      42303 |             21377 |                          749 | True                       |
|    60 |      36074 |             17029 |                          802 | True                       |
|    61 |      36535 |             18965 |                          925 | True                       |
|    62 |      37584 |             19089 |                          798 | True                       |
|    63 |      37030 |             18817 |                          365 | True                       |
|    64 |      35943 |             14630 |                          207 | True                       |
|    65 |      38424 |             13038 |                           63 | True                       |

## Split and Target

Training is restricted to run 64. Evaluation uses held-out Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65. Confidence intervals are nonparametric run bootstraps over those held-out runs.

For event `e`, stave `s`, geometry position `x_s`, and method `m`, the geometry-corrected time is

```text
tau_{e,s}^{(m)} = t_{e,s}^{(m)} - x_s * v_TOF,  with v_TOF = 0.078 ns/cm.
```

The explicit correction target in the training run is the fold-local residual

```text
y_{e,s} = tau_{e,s}^{(base)} - mean_{u in T, u != s} tau_{e,u}^{(base)}.
```

The B2-held-out mode sets `T={B4,B6,B8}` and leaves B2 unfit. The B2-included mode sets `T={B2,B4,B6,B8}`. All learned methods predict `f_m(z_{e,s})` and use `t_{e,s}^{(m)} = t_{e,s}^{(base)} - f_m(z_{e,s})`.

## Methods

Base phase templates are run-64 empirical normalized waveform templates binned by stave and amplitude. The strong traditional method is the P10e amplitude-bin residual correction: median `y_{e,s}` in each stave/amplitude bin, with a stave fallback when the bin has fewer than the configured minimum training pulses.

The learned panel is deliberately heterogeneous: ridge regression, histogram gradient-boosted trees, a tabular MLP, a 1D-CNN over the normalized raw waveform plus tabular pulse features, and a new event-token attention architecture. The event-token model is sensible for this ticket because the target is explicitly event-relative; it embeds the B2/B4/B6/B8 pulses as four tokens, applies self-attention inside the event, and predicts the requested stave token's residual without using run id, event id, event order, or held-out residuals.

B2-held-out train target pulses: `621`; B2-included train target pulses: `828` including `207` B2 pulses.

The score for pair family `F` in run `r` is

```text
sigma68_{r,F,m} = (Q84({tau_a - tau_b : (a,b) in F}) - Q16(...)) / 2.
```

Reported point estimates are the mean of `sigma68_{r,F,m}` over held-out runs; CIs resample held-out runs with replacement.

## Main Held-out Results

### B2-held-out all-six closure

| method                 | sigma68_ns_95ci            |   n_pair_residuals |
|:-----------------------|:---------------------------|-------------------:|
| base                   | 3.27235 [3.05229, 3.50074] |              22644 |
| traditional            | 3.65126 [3.43001, 3.85352] |              22644 |
| ridge                  | 3.63616 [3.42077, 3.85497] |              22644 |
| gradient_boosted_trees | 3.87432 [3.58791, 4.24329] |              22644 |
| mlp                    | 3.74389 [3.5322, 4.00037]  |              22644 |
| cnn1d                  | 2.94685 [2.7386, 3.14621]  |              22644 |
| event_token_attention  | 2.96069 [2.71466, 3.19889] |              22644 |

### B2-included all-six closure

| method                 | sigma68_ns_95ci            |   n_pair_residuals |
|:-----------------------|:---------------------------|-------------------:|
| base                   | 3.27235 [3.05218, 3.50092] |              22644 |
| traditional            | 2.35239 [2.17419, 2.53544] |              22644 |
| ridge                  | 2.60598 [2.41407, 2.81512] |              22644 |
| gradient_boosted_trees | 2.79577 [2.65452, 2.93841] |              22644 |
| mlp                    | 2.87753 [2.698, 3.08752]   |              22644 |
| cnn1d                  | 2.415 [2.2235, 2.6342]     |              22644 |
| event_token_attention  | 2.27945 [2.0494, 2.52543]  |              22644 |

### B2-included B2-containing pairs

| method                 | sigma68_ns_95ci            |   n_pair_residuals |
|:-----------------------|:---------------------------|-------------------:|
| base                   | 4.32871 [3.18896, 5.6367]  |              11322 |
| traditional            | 3.77465 [2.60909, 5.07321] |              11322 |
| ridge                  | 3.8086 [2.79831, 5.01487]  |              11322 |
| gradient_boosted_trees | 3.2469 [2.80892, 3.69475]  |              11322 |
| mlp                    | 4.02909 [3.37451, 4.75583] |              11322 |
| cnn1d                  | 3.4399 [2.39614, 4.65517]  |              11322 |
| event_token_attention  | 3.35284 [2.38207, 4.39212] |              11322 |

### B2-included downstream-only pairs

| method                 | sigma68_ns_95ci            |   n_pair_residuals |
|:-----------------------|:---------------------------|-------------------:|
| base                   | 2.78724 [2.69222, 2.88776] |              11322 |
| traditional            | 1.95893 [1.82704, 2.15975] |              11322 |
| ridge                  | 1.75303 [1.66849, 1.85419] |              11322 |
| gradient_boosted_trees | 2.30243 [2.21403, 2.39406] |              11322 |
| mlp                    | 2.15593 [2.03028, 2.31002] |              11322 |
| cnn1d                  | 2.07175 [2.02242, 2.12684] |              11322 |
| event_token_attention  | 1.82558 [1.80133, 1.85738] |              11322 |

## Paired Deltas

Negative values favor the first term in each contrast when the contrast is `included - heldout`; positive values in `B2-containing - downstream-only` indicate broader B2-containing residuals.

| family          | method                 | delta_ns_95ci                     |
|:----------------|:-----------------------|:----------------------------------|
| all_six         | base                   | 0 [0, 0]                          |
| all_six         | traditional            | -1.29888 [-1.48991, -1.12465]     |
| all_six         | ridge                  | -1.03018 [-1.21749, -0.86963]     |
| all_six         | gradient_boosted_trees | -1.07855 [-1.39778, -0.892449]    |
| all_six         | mlp                    | -0.866363 [-0.955276, -0.775089]  |
| all_six         | cnn1d                  | -0.531855 [-0.703127, -0.392444]  |
| all_six         | event_token_attention  | -0.681237 [-0.877833, -0.503901]  |
| b2_containing   | base                   | 0 [0, 0]                          |
| b2_containing   | traditional            | -0.171878 [-0.312759, -0.0356633] |
| b2_containing   | ridge                  | -0.231662 [-0.591144, 0.0981045]  |
| b2_containing   | gradient_boosted_trees | -0.727116 [-1.55941, 0.073927]    |
| b2_containing   | mlp                    | 0.191325 [-0.545628, 0.809611]    |
| b2_containing   | cnn1d                  | -0.288288 [-0.629972, 0.0184786]  |
| b2_containing   | event_token_attention  | -0.264426 [-0.606788, 0.0518972]  |
| downstream_only | base                   | 0 [0, 0]                          |
| downstream_only | traditional            | -0.0489247 [-0.103568, 0.006655]  |
| downstream_only | ridge                  | -0.214559 [-0.260218, -0.174535]  |
| downstream_only | gradient_boosted_trees | 0.17282 [0.100019, 0.247133]      |
| downstream_only | mlp                    | 0.154971 [0.0954503, 0.215751]    |
| downstream_only | cnn1d                  | 0.246941 [0.107252, 0.38991]      |
| downstream_only | event_token_attention  | -0.00941071 [-0.118951, 0.11657]  |

| mode        | method                 | delta_ns_95ci                |
|:------------|:-----------------------|:-----------------------------|
| b2_heldout  | base                   | 1.54146 [0.392479, 2.84651]  |
| b2_heldout  | traditional            | 1.93867 [0.538662, 3.4606]   |
| b2_heldout  | ridge                  | 2.07267 [0.858004, 3.44649]  |
| b2_heldout  | gradient_boosted_trees | 1.8444 [0.65509, 3.14391]    |
| b2_heldout  | mlp                    | 1.83681 [0.683916, 3.16846]  |
| b2_heldout  | cnn1d                  | 1.90337 [0.622145, 3.42256]  |
| b2_heldout  | event_token_attention  | 1.78228 [0.531663, 3.22582]  |
| b2_included | base                   | 1.54146 [0.392479, 2.7828]   |
| b2_included | traditional            | 1.81572 [0.545174, 3.30012]  |
| b2_included | ridge                  | 2.05557 [1.05041, 3.19906]   |
| b2_included | gradient_boosted_trees | 0.944467 [0.473148, 1.41365] |
| b2_included | mlp                    | 1.87316 [1.22979, 2.54185]   |
| b2_included | cnn1d                  | 1.36814 [0.283549, 2.642]    |
| b2_included | event_token_attention  | 1.52726 [0.578596, 2.57522]  |

## Shuffled-target Controls

Each learned method was re-trained after shuffling the run-64 residual target within the training rows. Positive shuffled-minus-real deltas mean the real target fit improves over its shuffled control.

| mode        | family          | contrast                                   | delta_ns_95ci                    |
|:------------|:----------------|:-------------------------------------------|:---------------------------------|
| b2_heldout  | all_six         | ridge_shuffled_minus_real                  | -0.298043 [-0.52943, -0.0775774] |
| b2_heldout  | all_six         | gradient_boosted_trees_shuffled_minus_real | 0.0334999 [-0.217042, 0.295996]  |
| b2_heldout  | all_six         | mlp_shuffled_minus_real                    | 0.404471 [0.196609, 0.599609]    |
| b2_heldout  | all_six         | cnn1d_shuffled_minus_real                  | 0.299189 [0.13056, 0.446527]     |
| b2_heldout  | all_six         | event_token_attention_shuffled_minus_real  | 0.535123 [0.328696, 0.707286]    |
| b2_heldout  | b2_containing   | ridge_shuffled_minus_real                  | 0.473273 [0.337267, 0.615956]    |
| b2_heldout  | b2_containing   | gradient_boosted_trees_shuffled_minus_real | 0.721815 [0.384578, 0.947633]    |
| b2_heldout  | b2_containing   | mlp_shuffled_minus_real                    | 1.42246 [1.05356, 1.90136]       |
| b2_heldout  | b2_containing   | cnn1d_shuffled_minus_real                  | 0.635244 [0.386382, 0.89136]     |
| b2_heldout  | b2_containing   | event_token_attention_shuffled_minus_real  | 1.03311 [0.696256, 1.34836]      |
| b2_heldout  | downstream_only | ridge_shuffled_minus_real                  | 1.09395 [0.840927, 1.30687]      |
| b2_heldout  | downstream_only | gradient_boosted_trees_shuffled_minus_real | 1.54483 [1.41574, 1.67953]       |
| b2_heldout  | downstream_only | mlp_shuffled_minus_real                    | 1.75922 [1.58289, 1.93753]       |
| b2_heldout  | downstream_only | cnn1d_shuffled_minus_real                  | 1.03156 [0.905286, 1.16423]      |
| b2_heldout  | downstream_only | event_token_attention_shuffled_minus_real  | 1.02474 [0.847944, 1.1871]       |
| b2_included | all_six         | ridge_shuffled_minus_real                  | 1.23859 [1.0836, 1.36495]        |
| b2_included | all_six         | gradient_boosted_trees_shuffled_minus_real | 1.83816 [1.62751, 2.06843]       |
| b2_included | all_six         | mlp_shuffled_minus_real                    | 1.40081 [1.15286, 1.65469]       |
| b2_included | all_six         | cnn1d_shuffled_minus_real                  | 0.832107 [0.722433, 0.928521]    |
| b2_included | all_six         | event_token_attention_shuffled_minus_real  | 0.834817 [0.777419, 0.890436]    |
| b2_included | b2_containing   | ridge_shuffled_minus_real                  | 1.04696 [0.638485, 1.42365]      |
| b2_included | b2_containing   | gradient_boosted_trees_shuffled_minus_real | 2.21839 [1.56744, 2.92041]       |
| b2_included | b2_containing   | mlp_shuffled_minus_real                    | 1.14697 [0.72921, 1.56932]       |
| b2_included | b2_containing   | cnn1d_shuffled_minus_real                  | 0.830762 [0.663819, 1.00612]     |
| b2_included | b2_containing   | event_token_attention_shuffled_minus_real  | 0.787582 [0.622054, 0.984809]    |
| b2_included | downstream_only | ridge_shuffled_minus_real                  | 1.60079 [1.37346, 1.81478]       |
| b2_included | downstream_only | gradient_boosted_trees_shuffled_minus_real | 1.93048 [1.72292, 2.12839]       |
| b2_included | downstream_only | mlp_shuffled_minus_real                    | 1.75044 [1.58829, 1.92052]       |
| b2_included | downstream_only | cnn1d_shuffled_minus_real                  | 0.775021 [0.627209, 0.899916]    |
| b2_included | downstream_only | event_token_attention_shuffled_minus_real  | 0.998282 [0.916259, 1.07411]     |

## Leakage and Reproduction Checks

| check                                          |          value | pass   |
|:-----------------------------------------------|---------------:|:-------|
| selected_pulse_reproduction_passed             |    1           | True   |
| run64_all_hit_events                           |  207           | True   |
| heldout_all_hit_events                         | 3774           | True   |
| train_heldout_run_overlap                      |    0           | True   |
| train_heldout_event_overlap                    |    0           | True   |
| b2_heldout_b2_rows_used_in_target_fit          |    0           | True   |
| b2_included_b2_rows_used_in_target_fit         |  207           | True   |
| p10e_b2_heldout_traditional_abs_delta_ns       |    0           | True   |
| p10e_b2_heldout_ridge_abs_delta_ns             |    2.26485e-14 | True   |
| p10e_b2_included_traditional_abs_delta_ns      |    0           | True   |
| p10e_b2_included_ridge_abs_delta_ns            |    1.37668e-14 | True   |
| all_included_shuffled_controls_worse_than_real |    5           | True   |
| too_good_external_sigma68_lt_1ns               |    0           | True   |

The P10e all-six traditional and ridge reproductions are checked numerically against the parent result. Run id, event id, event order, cross-stave held-out timing, and residual labels are not model features. The only run membership used by models is the hard split gate: run 64 for fitting and Sample-II analysis runs for scoring.

## Systematics and Caveats

- The training set for explicit residuals is small: 207 all-hit run-64 events, or 828 target pulses in the B2-included mode. Neural models are therefore regularized and judged against shuffled-target controls, but they are still variance-limited.
- The metric is pairwise timing closure, not absolute time resolution. A correction that removes common event structure can improve pair closure without proving improved absolute timing.
- All uncertainty intervals bootstrap seven held-out runs. They capture run-to-run variability in this split, not all possible detector states or future beam configurations.
- The B2-held-out mode intentionally leaves B2 unfit; its B2-containing residuals therefore test transfer from downstream staves rather than a best possible B2 calibration.
- Pair families share events, so family comparisons are paired diagnostics rather than independent experiments.

## Finding

The B2-included all-six winner is event_token_attention with sigma68=2.2795 ns [2.0494, 2.5254]. The strong traditional correction is 2.3524 ns [2.1742, 2.5354], so the winner-minus-traditional point delta is -0.0729 ns. Pair-family tables show whether that gain is driven by B2-containing or downstream-only pairs.

## Hypothesis and Next Test

Hypothesis: the residual B2-containing/downstream-only gap is not only amplitude timewalk; it is partly a raw waveform quality or topology covariate that event-token attention can exploit weakly through event context. A confirming test would apply a strictly external, pre-timing quality veto or abstention rule and show that it narrows the B2-containing family without degrading downstream-only closure. A falsifying test would show that the event-token point win vanishes under external quality labels or transfers only through residual-derived information.

Queued follow-up in `result.json`: `P10i: external non-timewalk covariate veto for B2 pair-family closure`.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10h_1781066894_1206_3b0c13e6_pair_family_decomposition.py --config configs/p10h_1781066894_1206_3b0c13e6_pair_family_decomposition.json
```
