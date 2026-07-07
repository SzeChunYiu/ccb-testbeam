# S03s: Upstream q-template curvature leakage gate

**Ticket:** `1781075115.415.5d145e93`  
**Worker:** `testbeam-laptop-3`  
**Raw data:** `data/root/root` (`hrdb_run_0031.root` through `hrdb_run_0065.root`, configured subset)  
**Primary split:** leave-one-run-out over Sample-II analysis runs [58, 59, 60, 61, 62, 63, 65] with run-bootstrap 95% confidence intervals.

## Abstract

This study asks whether an upstream-only q-template atom can predict the all-three downstream curvature-tail label after excluding the downstream waveform provenance that defines the tail. The target is a rare binary endpoint on all-three downstream events: clean events satisfy `|C_t| < 3 ns`, tail events satisfy `|C_t| > 51 ns`, where

`C_t = t_B8 - 2 t_B6 + t_B4`.

The central result is that the winner is **ridge** with ROC AUC 0.814 [0.716, 0.894] and AP 0.146 [0.080, 0.246]. Because the target is rare and downstream-defined, this is a leakage gate rather than a claim of independent timing truth.

## Raw ROOT Reproduction

The analysis first re-runs the S03e/S00 raw ROOT scan before fitting any model. The gate reads `HRDv` from `h101`, subtracts the median baseline from samples 0-3, selects B2/B4/B6/B8 pulses with amplitude greater than 1000 ADC, and reconstructs CFD20 timing. The predeclared reproduction numbers are copied from the earlier S03e gate and must match exactly.

| quantity                                             | report_value | reproduced | delta | tolerance | pass |
| ---------------------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses                        | 640737       | 640737     | 0     | 0         | True |
| sample_i_calib selected pulses                       | 248745       | 248745     | 0     | 0         | True |
| sample_i_analysis selected pulses                    | 252266       | 252266     | 0     | 0         | True |
| sample_ii_calib selected pulses                      | 14630        | 14630      | 0     | 0         | True |
| sample_ii_analysis selected pulses                   | 125096       | 125096     | 0     | 0         | True |
| S07 parent guarded gross events, D_t>51 ns           | 72           | 72         | 0     | 0         | True |
| all-three downstream control events                  | 3774         | 3774       | 0     | 0         | True |
| all-three downstream guarded gross events, D_t>51 ns | 22           | 22         | 0     | 0         | True |

Benchmark run counts:

| run | selected_pulses | all_three_control_events | all_three_gross_dt_gt51 |
| --- | --------------- | ------------------------ | ----------------------- |
| 58  | 16781           | 72                       | 0                       |
| 59  | 21377           | 749                      | 5                       |
| 60  | 17029           | 802                      | 6                       |
| 61  | 18965           | 925                      | 8                       |
| 62  | 19089           | 798                      | 1                       |
| 63  | 18817           | 365                      | 2                       |
| 65  | 13038           | 63                       | 0                       |

## Statistical Design

For each held-out run `r`, all preprocessing choices that can depend on the endpoint are made using the remaining runs only. The score vector `s_m` for method `m` is evaluated out of fold. ROC AUC is

`AUC_m = P(s_m(x_tail) > s_m(x_clean)) + 0.5 P(s_m(x_tail) = s_m(x_clean))`.

Average precision is computed from the same held-out scores. Confidence intervals sample the seven held-out runs with replacement and recompute the metric on the concatenated sampled runs. This preserves within-run correlation and makes run-to-run instability visible.

## Features and Leakage Controls

The primary matrix is upstream-only plus nuisance terms: `q_b2, amp_b2, log_amp_b2, q_b2_amp_resid, q_b2_amp_z, run_family_code`. Downstream q-template columns are not allowed in primary models: `q_b4, q_b6, q_b8, q_ds_max, q_ds_mean, q_ds_span, q_ds_std`. The nuisance terms are B2 amplitude, log amplitude, an amplitude-residualized B2 q-template score, an amplitude-z-scored B2 score, and a coarse run-family code for the run-64/65 acquisition family. No `D_t`, `C_t`, App.A label, event id, downstream q-template, selected-downstream flag, or waveform sample enters the primary benchmark.

Dataset:

| quantity                  | value     |
| ------------------------- | --------- |
| all-three control events  | 3774      |
| clean events \|C_t\|<3 ns | 728       |
| tail events \|C_t\|>51 ns | 23        |
| benchmark events          | 751       |
| tail fraction             | 0.0306258 |

Leakage and sentinel checks:

| probe                    | roc_auc  | average_precision | notes                                                                  |
| ------------------------ | -------- | ----------------- | ---------------------------------------------------------------------- |
| b2_only_ridge            | 0.647934 | 0.0470081         | Strict upstream shape-only lower-capacity sentinel.                    |
| downstream_forbidden_gbt | 0.810171 | 0.361428          | Forbidden provenance ceiling using downstream q-template columns.      |
| amplitude_only_gbt       | 0.561544 | 0.107048          | Nuisance-only amplitude sentinel.                                      |
| leaky_abs_ct_ceiling     | 1        | 1                 | Label-defining oracle; must be 1.0 if target construction is coherent. |

## Methods

The traditional method is a training-run-selected scalar upstream score over `q_b2`, `q_b2_amp_resid`, and `q_b2_amp_z`, with sign selected inside the training runs. Ridge is L2 logistic regression. Gradient-boosted trees use histogram gradient boosting. MLP is a two-hidden-layer neural network. The 1D-CNN entry uses fixed local convolutional filters on the ordered upstream/nuisance vector followed by ridge logistic readout, providing a small convolutional inductive bias without downstream samples. The new architecture, `amplitude_residual_stack`, is a residual MLP over the same upstream nuisance feature set, designed to test whether a deeper residualized upstream score adds information beyond amplitude correction.

## Results

| method                   | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high |
| ------------------------ | -------- | -------------- | --------------- | ----------------- | --------- | ---------- |
| ridge                    | 0.814441 | 0.715654       | 0.894414        | 0.146427          | 0.0803384 | 0.245516   |
| one_dimensional_cnn      | 0.778249 | 0.588221       | 0.871047        | 0.154785          | 0.0937944 | 0.243594   |
| gradient_boosted_trees   | 0.753106 | 0.653386       | 0.875028        | 0.133631          | 0.0673218 | 0.274874   |
| traditional_upstream_q   | 0.712039 | 0.641926       | 0.837593        | 0.0520189         | 0.046521  | 0.0800382  |
| mlp                      | 0.590779 | 0.313174       | 0.760372        | 0.042756          | 0.015496  | 0.127633   |
| amplitude_residual_stack | 0.492774 | 0.293305       | 0.612336        | 0.0335532         | 0.0169776 | 0.0412238  |

At 95% clean acceptance, the held-out tail rejection summary is:

| method                   | clean_efficiency | tail_rejection | n_tail |
| ------------------------ | ---------------- | -------------- | ------ |
| amplitude_residual_stack | 0.857143         | 0.2            | 23     |
| gradient_boosted_trees   | 0.937702         | 0.262222       | 23     |
| mlp                      | 0.92332          | 0.0333333      | 23     |
| one_dimensional_cnn      | 0.950506         | 0.42           | 23     |
| ridge                    | 0.924223         | 0.364444       | 23     |
| traditional_upstream_q   | 0.956778         | 0              | 23     |

Per-run metrics:

| method                   | heldout_run | n_clean | n_tail | roc_auc    | average_precision |
| ------------------------ | ----------- | ------- | ------ | ---------- | ----------------- |
| traditional_upstream_q   | 58          | 16      | 0      |            |                   |
| traditional_upstream_q   | 59          | 127     | 5      | 0.669291   | 0.0653621         |
| traditional_upstream_q   | 60          | 154     | 6      | 0.706972   | 0.0678385         |
| traditional_upstream_q   | 61          | 220     | 9      | 0.658586   | 0.0641133         |
| traditional_upstream_q   | 62          | 129     | 1      | 0.992248   | 0.5               |
| traditional_upstream_q   | 63          | 67      | 2      | 0.589552   | 0.0527778         |
| traditional_upstream_q   | 65          | 15      | 0      |            |                   |
| ridge                    | 58          | 16      | 0      |            |                   |
| ridge                    | 59          | 127     | 5      | 0.774803   | 0.150248          |
| ridge                    | 60          | 154     | 6      | 0.953463   | 0.313956          |
| ridge                    | 61          | 220     | 9      | 0.810101   | 0.290109          |
| ridge                    | 62          | 129     | 1      | 0.379845   | 0.0123457         |
| ridge                    | 63          | 67      | 2      | 0.865672   | 0.183824          |
| ridge                    | 65          | 15      | 0      |            |                   |
| gradient_boosted_trees   | 58          | 16      | 0      |            |                   |
| gradient_boosted_trees   | 59          | 127     | 5      | 0.762992   | 0.158151          |
| gradient_boosted_trees   | 60          | 154     | 6      | 0.886364   | 0.37844           |
| gradient_boosted_trees   | 61          | 220     | 9      | 0.690152   | 0.108977          |
| gradient_boosted_trees   | 62          | 129     | 1      | 0.325581   | 0.011236          |
| gradient_boosted_trees   | 63          | 67      | 2      | 0.955224   | 0.333333          |
| gradient_boosted_trees   | 65          | 15      | 0      |            |                   |
| mlp                      | 58          | 16      | 0      |            |                   |
| mlp                      | 59          | 127     | 5      | 0.612598   | 0.0621803         |
| mlp                      | 60          | 154     | 6      | 0.830087   | 0.217914          |
| mlp                      | 61          | 220     | 9      | 0.530808   | 0.209158          |
| mlp                      | 62          | 129     | 1      | 0          | 0.00769231        |
| mlp                      | 63          | 67      | 2      | 0.544776   | 0.266129          |
| mlp                      | 65          | 15      | 0      |            |                   |
| one_dimensional_cnn      | 58          | 16      | 0      |            |                   |
| one_dimensional_cnn      | 59          | 127     | 5      | 0.754331   | 0.152661          |
| one_dimensional_cnn      | 60          | 154     | 6      | 0.958874   | 0.347936          |
| one_dimensional_cnn      | 61          | 220     | 9      | 0.788889   | 0.225707          |
| one_dimensional_cnn      | 62          | 129     | 1      | 0.00775194 | 0.00775194        |
| one_dimensional_cnn      | 63          | 67      | 2      | 0.738806   | 0.195238          |
| one_dimensional_cnn      | 65          | 15      | 0      |            |                   |
| amplitude_residual_stack | 58          | 16      | 0      |            |                   |
| amplitude_residual_stack | 59          | 127     | 5      | 0.497638   | 0.0445478         |
| amplitude_residual_stack | 60          | 154     | 6      | 0.117965   | 0.0238486         |
| amplitude_residual_stack | 61          | 220     | 9      | 0.369697   | 0.0324911         |
| amplitude_residual_stack | 62          | 129     | 1      | 0          | 0.00769231        |
| amplitude_residual_stack | 63          | 67      | 2      | 0.238806   | 0.0283224         |
| amplitude_residual_stack | 65          | 15      | 0      |            |                   |

## Systematics and Caveats

The positive class has only 23 tail events after the clean/tail endpoint is applied, so AP and fixed-efficiency tail rejection are sensitive to individual runs. The bootstrap interval is therefore the decision object, not the point estimate alone. The endpoint is defined from downstream times; even when downstream q-template features are excluded, any upstream correlation may reflect event-level beam or electronics conditions rather than a causal B2 shape mechanism. Run-family coding is retained as a nuisance because run 64/65 acquisition conditions are known to differ, but it can also absorb genuine run-specific physics. The CNN entry is deliberately small; it tests a local-filter inductive bias on the tabular upstream sequence and is not a high-capacity waveform CNN.

## Verdict

The raw ROOT reproduction gate passes exactly. The winner written to `result.json` is **ridge**. The gate does not justify adopting downstream q-template features as independent truth; it supports using the upstream-only signal as a conservative diagnostic with explicit run-level uncertainty.

## Reproduction Command

```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn python scripts/s03s_1781075115_415_5d145e93_upstream_qtemplate_curvature_leakage_gate.py --config configs/s03s_1781075115_415_5d145e93_upstream_qtemplate_curvature_leakage_gate.json
```
