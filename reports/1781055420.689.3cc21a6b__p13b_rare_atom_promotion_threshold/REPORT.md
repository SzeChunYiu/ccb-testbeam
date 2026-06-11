# P13b: rare-atom bootstrap promotion threshold

**Ticket:** `1781055420.689.3cc21a6b`  
**Worker:** `testbeam-laptop-4`  
**Date:** 2026-06-11  
**Depends on:** S00, P09a, P04/P07/P12 rare-atom consumers  
**Config:** `configs/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.json`  
**Git commit:** `14ef681a9593cf98df78b91002b31c5dd2bc1054`

## 0. Question
What minimum support, run stability, and control-passing criteria are needed before rare waveform atoms should be promoted from diagnostics to steering variables, and does a learned support/risk model choose more stable atoms than a transparent exact-count rule?

## 1. Reproduction
The analysis starts from raw B-stack ROOT files in `data/root/root`. The S00 gate is reproduced using even channels B2/B4/B6/B8, median baseline from samples 0--3, and a baseline-subtracted amplitude threshold of 1000 ADC.

| quantity                    |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulses |         640737 |       640737 |       0 |           0 | True   |

The reproduced total is the required 640,737 selected B-stave pulses. No sorted ROOT table or previous CSV is used for the gate.

## 2. Traditional Method
An atom is the tuple \(a=(\mathrm{taxon},\mathrm{stave},\mathrm{amplitude\ bin})\). Taxa are the fold-local P09a transparent classes: saturation, dropout, baseline excursion, pile-up/long-tail, early pretrigger, delayed peak, undershoot recovery, broad/template mismatch, and timing-tail-only.

For each atom and support stratum \(s=(\mathrm{stave},\mathrm{amplitude\ bin})\), the train-run rate is

\[\hat p_a = \frac{n_a}{N_s}.\]

The 95% Wilson interval is

\[\frac{\hat p+z^2/(2N) \pm z\sqrt{\hat p(1-\hat p)/N+z^2/(4N^2)}}{1+z^2/N}, \quad z=1.96.\]

Run concentration is summarized by an effective sample size

\[n_{\rm eff}=\frac{(\sum_r n_{a,r})^2}{\sum_r n_{a,r}^2}.\]

The preregistered promotion gate is: train count >= 24, effective count >= 18.0, at least 4 train runs, max single-run share <= 0.55, and train Wilson CI width <= 0.035. A promoted atom is counted stable on held-out runs if the held-out Wilson interval overlaps the train interval within 0.005 and has at least 3 held-out pulses.

Highest traditional support-score atoms:

| atom_id                                    |   train_count |   train_effective_n |   train_max_run_share |   train_rate_ci_width |   heldout_count | stable_on_heldout   | promote_traditional_support_exact   |
|:-------------------------------------------|--------------:|--------------------:|----------------------:|----------------------:|----------------:|:--------------------|:------------------------------------|
| novel_early_pretrigger|B2|1000_1500        |          5867 |             19.8642 |             0.0913584 |           0.0114381   |             991 | False               | True                                |
| novel_delayed_peak|B4|2500_4000            |          1937 |             23.4725 |             0.0598864 |           0.00984794  |             260 | True                | True                                |
| novel_early_pretrigger|B2|1500_2500        |          4773 |             19.817  |             0.0917662 |           0.00653728  |             782 | False               | True                                |
| novel_delayed_peak|B2|2500_4000            |          1746 |             19.2505 |             0.0864834 |           0.00185411  |             310 | True                | True                                |
| novel_delayed_peak|B4|1500_2500            |           894 |             23.2174 |             0.0626398 |           0.0149843   |             132 | True                | True                                |
| baseline_excursion|B2|2500_4000            |          1335 |             19.4119 |             0.0966292 |           0.00162529  |             279 | True                | True                                |
| novel_delayed_peak|B2|4000_7000            |          1156 |             21.305  |             0.0709343 |           0.000658272 |             217 | False               | True                                |
| baseline_excursion|B2|4000_7000            |          1362 |             18.0554 |             0.103524  |           0.00071411  |             240 | False               | True                                |
| novel_early_pretrigger|B2|2500_4000        |          1420 |             19.2968 |             0.0957746 |           0.00167537  |             301 | True                | True                                |
| novel_delayed_peak|B4|4000_7000            |           528 |             22.2032 |             0.0662879 |           0.0156701   |              70 | True                | True                                |
| novel_broad_template_mismatch|B2|4000_7000 |          1567 |             17.6823 |             0.116784  |           0.000765542 |             141 | True                | False                               |
| novel_delayed_peak|B6|2500_4000            |           749 |             22.2029 |             0.0774366 |           0.0124496   |              94 | True                | True                                |

No chi-square fit is used in the traditional gate; uncertainty is exact-count/binomial and run-block bootstrap. The full distribution of support is reported in `atom_promotion_table.csv` rather than only the top rows.

## 3. ML/NN Methods
All learned methods train only on non-held-out runs and predict the binary fold-local rare-atom label for pulses. Features exclude run id, event id, and held-out labels. Tabular methods use normalized waveform summaries, q-template residual, duplicate-channel timing span, baseline and saturation summaries, and stave one-hot indicators. CNN methods see the normalized 18-sample waveform plus the same scalar summaries.

The panel is ridge classification, gradient-boosted trees, MLP, a small 1D-CNN, and a new gated CNN whose scalar support features multiplicatively gate the convolutional waveform embedding. Per-method score thresholds are chosen on train runs to target 90% rare-label precision with at least 1% recall; atom promotion then requires loose train support plus a train atom mean score above that threshold.

| method                 |   score_threshold |   train_precision |   train_recall |   train_predicted_positive |
|:-----------------------|------------------:|------------------:|---------------:|---------------------------:|
| ridge                  |          0.675276 |          0.900009 |       0.589323 |                      21292 |
| gradient_boosted_trees |          0.12897  |          0.905162 |       0.999723 |                      35914 |
| mlp                    |          0.810959 |          0.900006 |       0.971553 |                      35102 |
| cnn_1d                 |          0.666522 |          0.900035 |       0.557647 |                      20147 |
| gated_cnn_new          |          0.733447 |          0.900013 |       0.424363 |                      15332 |

Held-out pulse-level classifier diagnostics:

| method                 |   heldout_auc |   heldout_average_precision |   heldout_brier |   heldout_ece |
|:-----------------------|--------------:|----------------------------:|----------------:|--------------:|
| ridge                  |      0.990369 |                    0.899958 |      0.114881   |     0.28962   |
| gradient_boosted_trees |      0.999973 |                    0.999743 |      0.00240603 |     0.0187282 |
| mlp                    |      0.999238 |                    0.991907 |      0.0151829  |     0.0280866 |
| cnn_1d                 |      0.961103 |                    0.847141 |      0.120038   |     0.296094  |
| gated_cnn_new          |      0.959625 |                    0.822723 |      0.180579   |     0.3733    |

The classifier scores are support/risk diagnostics, not truth labels. They only become promotion proposals after aggregation to the atom table.

## 4. Head-to-head Benchmark
All methods are evaluated on the same four held-out runs (42, 57, 64, 65). The primary metric is promotion utility: stable-promotion rate plus a small coverage reward minus false-promotion penalty and excessive train-CI width penalty. CIs are 400 run-block bootstrap resamples of held-out runs.

| method                    |   promoted_atoms |   stable_promotion_rate | stable_promotion_rate_ci   |   false_promotion_rate | false_promotion_rate_ci   |   heldout_rare_pulse_coverage | heldout_rare_pulse_coverage_ci   |   promotion_utility | promotion_utility_ci   |
|:--------------------------|-----------------:|------------------------:|:---------------------------|-----------------------:|:--------------------------|------------------------------:|:---------------------------------|--------------------:|:-----------------------|
| traditional_support_exact |               23 |                0.782609 | [0.521, 0.871]             |               0.217391 | [0.129, 0.479]            |                      0.841345 | [0.803, 0.862]                   |            0.745767 | [0.278, 0.901]         |
| ridge                     |               30 |                0.833333 | [0.500, 0.867]             |               0.166667 | [0.133, 0.500]            |                      0.727399 | [0.682, 0.764]                   |            0.817443 | [0.241, 0.874]         |
| gradient_boosted_trees    |               58 |                0.758621 | [0.534, 0.776]             |               0.241379 | [0.224, 0.466]            |                      0.997626 | [0.995, 0.999]                   |            0.72723  | [0.335, 0.758]         |
| mlp                       |               57 |                0.77193  | [0.544, 0.772]             |               0.22807  | [0.228, 0.456]            |                      0.99723  | [0.995, 0.999]                   |            0.750462 | [0.352, 0.751]         |
| cnn_1d                    |               20 |                0.75     | [0.450, 0.800]             |               0.25     | [0.200, 0.550]            |                      0.555094 | [0.481, 0.609]                   |            0.645764 | [0.116, 0.738]         |
| gated_cnn_new             |               13 |                0.692308 | [0.462, 0.923]             |               0.307692 | [0.077, 0.538]            |                      0.495747 | [0.416, 0.553]                   |            0.5359   | [0.120, 0.944]         |

**Winner:** `ridge`. It promotes 30 atoms with stable-promotion rate 0.833, false-promotion rate 0.167, held-out rare-pulse coverage 0.727, and utility 0.817.

## 5. Falsification
Pre-registration came from the ticket: require minimum support, bootstrap stability, control-passing diagnostics, split by run, and ML-minus-traditional deltas with stratified run-block bootstrap 95% CIs. The falsification test is direct: a method claiming promotion superiority must have lower false-promotion rate and higher utility than the traditional support rule on the same held-out runs. Six methods were compared; the report treats the utility ranking as a model-selection panel, not a single uncorrected p-value.

## 6. Threats to Validity
- **Benchmark/selection:** the traditional baseline is deliberately strong: exact support, effective count, run concentration, and binomial width. ML is not compared against a weak threshold.
- **Data leakage:** runs 42, 57, 64, and 65 are held out. Run and event identifiers are excluded from model features. The taxonomy thresholds and q-template templates are fit on train runs.
- **Metric misuse:** rare-atom promotion is a support/stability decision; the report therefore emphasizes false-promotion rate, CI width, and coverage, not only classifier AUC.
- **Post-hoc selection:** thresholds are fixed in the JSON config before execution. The new architecture is included because gated waveform/support interactions are exactly the scientific object of this ticket.

## 7. Provenance Manifest
`manifest.json` records raw ROOT SHA256 hashes, code/config hashes, output hashes, environment, random seeds, and the exact command.

## 8. Findings and Next Steps
The conservative threshold implied by this study is: do not promote a rare atom unless it has at least 24 train pulses, effective run-balanced count at least 18, at least four train runs, no run contributing more than 55%, and a train-rate Wilson width below 0.035. Atoms below this support can still be useful for gallery review or diagnostics, but they should not steer timing, pile-up, charge, PID, or energy decisions without a consumer-level dry run.

Hypothesis: rare atoms that fail this gate are dominated by run-family composition and threshold jitter rather than reusable detector states. The proposed next ticket is `P13c rare-atom external steering dry run` because it directly tests whether the P13b support gate remains conservative when plugged into real consumers without retuning.

## 9. Reproducibility
Run:

```bash
/home/billy/anaconda3/bin/python scripts/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.py --config configs/p13b_1781055420_689_3cc21a6b_rare_atom_promotion_threshold.json
```

Runtime in this execution was 106.7 s. Output artifacts are in `reports/1781055420.689.3cc21a6b__p13b_rare_atom_promotion_threshold`.

## Systematics and Caveats
The held-out panel has only four runs, so bootstrap CIs quantify run sensitivity but cannot prove long-term detector stability. P09a taxonomy labels are transparent detector hypotheses, not hand truth; therefore the ML methods are support/risk scorers. The gate is intentionally conservative and may defer real but low-count phenomena such as the 54-event S03f topology until an external consumer-level dry run validates them.
