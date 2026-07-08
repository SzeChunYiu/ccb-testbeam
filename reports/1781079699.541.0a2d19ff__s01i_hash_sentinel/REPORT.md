# S01i selected-table byte-vs-content consumer sentinel

**Ticket:** `1781079699.541.0a2d19ff`  
**Worker:** `testbeam-laptop-4`  
**Command:** `/home/billy/anaconda3/bin/python scripts/s01i_1781079699_541_0a2d19ff_hash_sentinel.py --config configs/s01i_1781079699_541_0a2d19ff_hash_sentinel.json`  
**Git commit:** `7cb23646752e778d462a794c3538c761e648d0cd`

## Abstract

This study asks which sentinel protects downstream S01/S02/S04/P04 consumers of the S01 selected-pulse table: a byte-level gzip hash, a decompressed-content hash, or a deterministic replay of consumer summaries. The raw ROOT selection gate is reproduced first. Then the committed S01 `q_template_per_pulse.csv.gz` table is transformed into benign byte-only and deterministic reserialization controls, and into stale content controls that drop tail rows, shift Sample-II q-template residuals, round residual precision, shuffle q-template values, or swap run-stave labels. A strict traditional content-plus-replay sentinel is benchmarked against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a gated residual CNN.

## Reproduction From Raw ROOT

The raw B-stack ROOT files in `data/root/root` were scanned using the same S01 selection: channels B2/B4/B6/B8, baseline median over samples 0--3, and corrected amplitude greater than 1000 ADC. Let

`A_{e,s} = max_t (H_{e,s,t} - median_{u in B} H_{e,s,u})`,

where `B={0,1,2,3}`. A selected pulse is `A_{e,s} > 1000`.

Result: **640,737** selected pulses versus the S01 expected **640,737**, delta **0**. The raw-count reproduction therefore passes.

## Hash Variants

The byte hash is `sha256(gzip_bytes)`. The content hash is `sha256(gzip.decompress(gzip_bytes))`. The deterministic fresh replay serializes the same table rows with stable CSV formatting before gzip compression.

| variant                 | variant_kind     |   label_stale | source_byte_match   | source_content_match   | row_count_match   |
|:------------------------|:-----------------|--------------:|:--------------------|:-----------------------|:------------------|
| content_exact           | benign           |             0 | False               | True                   | True              |
| gzip_byte_repacked      | benign_byte_only |             0 | False               | True                   | True              |
| fresh_equivalent_rows   | benign_replay    |             0 | False               | False                  | True              |
| stale_tail_rows_dropped | stale_rows       |             1 | False               | False                  | False             |
| stale_sampleii_q_shift  | stale_content    |             1 | False               | False                  | True              |
| stale_rounded_qtemplate | stale_content    |             1 | False               | False                  | True              |
| shuffled_hash_control   | stale_content    |             1 | False               | False                  | True              |
| stale_run_stave_swap    | stale_join       |             1 | False               | False                  | True              |

The key control is `gzip_byte_repacked`: its gzip byte hash changes but its decompressed content hash and all consumer summaries remain identical. A byte-level sentinel therefore creates false alarms on harmless packaging changes.

## Consumer Replays

Compact deterministic consumers were replayed by run and stave:

- **S01 template consumer:** median and 95th percentile of `q_template_rmse`.
- **S02 timing proxy:** fraction in a high-q or late-peak timing-tail proxy.
- **S04 charge proxy:** median `area_adc_samples / amplitude_adc`.
- **P04 q-template consumer:** fraction above the run-stave q99 tail.

Mean deltas versus the exact table:

| variant                 | variant_kind     |   label_stale |   delta_n |   delta_s01_q_median |   delta_s02_timing_tail_proxy |   delta_s04_charge_proxy |   delta_p04_q_high_fraction |
|:------------------------|:-----------------|--------------:|----------:|---------------------:|------------------------------:|-------------------------:|----------------------------:|
| content_exact           | benign           |             0 |   0       |          0           |                    0          |               0          |                 0           |
| fresh_equivalent_rows   | benign_replay    |             0 |   0       |          0           |                    0          |               0          |                 0           |
| gzip_byte_repacked      | benign_byte_only |             0 |   0       |          0           |                    0          |               0          |                 0           |
| shuffled_hash_control   | stale_content    |             1 |   0       |         -1.17086e-06 |                   -0.0225951  |               0          |                 4.29653e-05 |
| stale_rounded_qtemplate | stale_content    |             1 |   0       |         -0.000765953 |                   -0.00431808 |               0          |                -0.000116314 |
| stale_run_stave_swap    | stale_join       |             1 |   0       |          0           |                    0          |               0          |                 0           |
| stale_sampleii_q_shift  | stale_content    |             1 |   0       |          0.00102747  |                    0          |               0          |                 0           |
| stale_tail_rows_dropped | stale_rows       |             1 |  -4.62879 |         -2.78601e-05 |                    1.8569e-05 |               0.00111503 |                 7.18999e-06 |

## Methods

### Traditional Sentinels

The byte sentinel is

`S_byte(x) = 1[H_byte(x) != H_byte(reference)]`.

The proposed strong traditional replay sentinel is

`S_content+replay(x) = 1[N(x) != N(reference) or max_j |C_j(x)-C_j(reference)| > 0]`,

where `N` is the row count and `C_j` are the deterministic run-stave consumer summaries above. The decompressed content hash is retained as provenance evidence, but the replay gate is intentionally consumer-facing: it accepts gzip repacks and exact deterministic row replays, while rejecting stale controls that perturb row support or downstream summaries.

### ML/NN Benchmark

Features are only hash mismatch flags plus consumer deltas and relative deltas. They do not include variant names. The benchmark compares ridge classification, histogram gradient-boosted trees, MLP, a 1D-CNN over the ordered feature vector, and a gated residual CNN:

`p(y=1 | x) = sigma(g(x) f_CNN(x))`, with `g(x)=sigma(w_g^T x+b_g)`.

The gated residual CNN is the new architecture. It is sensible here because stale-table detection is sparse: most rows are benign or exact-zero deltas, and a learned gate can suppress unconstrained residual corrections when hash/replay evidence is absent.

Train/test splits are stratified and repeated 2 times. Traditional sentinels are additionally evaluated with run-block bootstrap CIs over runs. The primary metrics are balanced accuracy, false alarm rate on benign packaging/replay controls, stale detection rate, ROC-AUC, and average precision.

## Results

| method                     |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |   balanced_accuracy |   balanced_accuracy_ci_low |   balanced_accuracy_ci_high |   false_alarm_rate |   false_alarm_rate_ci_low |   false_alarm_rate_ci_high |   stale_detection_rate |   stale_detection_rate_ci_low |   stale_detection_rate_ci_high |
|:---------------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|--------------------:|---------------------------:|----------------------------:|-------------------:|--------------------------:|---------------------------:|-----------------------:|------------------------------:|-------------------------------:|
| gradient_boosted_trees     |     0.947 |            0.940 |             0.955 |               0.946 |                      0.940 |                       0.953 |               0.849 |                      0.828 |                       0.869 |              0.302 |                     0.261 |                      0.343 |                  1.000 |                         1.000 |                          1.000 |
| mlp                        |     0.936 |            0.934 |             0.938 |               0.941 |                      0.939 |                       0.942 |               0.846 |                      0.828 |                       0.863 |              0.302 |                     0.261 |                      0.343 |                  0.994 |                         0.987 |                          1.000 |
| traditional_content_replay |     0.826 |            0.825 |             0.827 |               0.869 |                      0.868 |                       0.870 |               0.826 |                      0.825 |                       0.827 |              0.000 |                     0.000 |                      0.000 |                  0.652 |                         0.649 |                          0.654 |
| ridge                      |     0.918 |            0.914 |             0.922 |               0.927 |                      0.923 |                       0.932 |               0.568 |                      0.499 |                       0.637 |              0.500 |                     0.025 |                      0.975 |                  0.636 |                         0.299 |                          0.974 |
| gated_residual_cnn         |     0.756 |            0.584 |             0.927 |               0.870 |                      0.806 |                       0.934 |               0.500 |                      0.500 |                       0.500 |              1.000 |                     1.000 |                      1.000 |                  1.000 |                         1.000 |                          1.000 |
| 1d_cnn                     |     0.583 |            0.572 |             0.593 |               0.798 |                      0.796 |                       0.800 |               0.500 |                      0.500 |                       0.500 |              1.000 |                     1.000 |                      1.000 |                  1.000 |                         1.000 |                          1.000 |
| traditional_byte_hash      |     0.500 |            0.500 |             0.500 |               0.624 |                      0.624 |                       0.624 |               0.500 |                      0.500 |                       0.500 |              1.000 |                     1.000 |                      1.000 |                  1.000 |                         1.000 |                          1.000 |

Run-block bootstrap for the two traditional sentinels:

| method                     | metric               |   value |   ci_low |   ci_high | bootstrap_unit   |
|:---------------------------|:---------------------|--------:|---------:|----------:|:-----------------|
| traditional_byte_hash      | balanced_accuracy    |   0.500 |    0.500 |     0.500 | run              |
| traditional_byte_hash      | false_alarm_rate     |   1.000 |    1.000 |     1.000 | run              |
| traditional_byte_hash      | stale_detection_rate |   1.000 |    1.000 |     1.000 | run              |
| traditional_content_replay | balanced_accuracy    |   0.827 |    0.815 |     0.842 | run              |
| traditional_content_replay | false_alarm_rate     |   0.000 |    0.000 |     0.000 | run              |
| traditional_content_replay | stale_detection_rate |   0.655 |    0.624 |     0.685 | run              |

The winner recorded in `result.json` is **`gradient_boosted_trees`**. It has balanced accuracy 0.849, false alarm rate 0.302, and stale detection rate 1.000. The byte hash sentinel is intentionally strong for any packaging change but fails the physics-facing false-alarm requirement because it rejects `gzip_byte_repacked`.

## Systematics and Caveats

- **Raw ROOT reproduction:** this study reproduces the selected-pulse number, not every floating-point q-template residual from S01. The S01 table itself is treated as the downstream consumer input whose byte/content semantics are under test.
- **Consumer scope:** the S01/S02/S04/P04 consumers are compact deterministic proxies, chosen to represent timing, template, charge, and q-template sensitivities without rerunning every historical report.
- **Variant realism:** stale controls are deliberate perturbations. They test sentinel behavior under plausible failure modes but are not claims that these failures occurred in production.
- **ML limitations:** the ML classifiers have few unique variant families and many run-stave rows. Repeated splits and run bootstrap expose stability, but ML success here is not a reason to replace deterministic hash/replay gates.
- **Multiple comparisons:** the traditional sentinel is predeclared as the physics policy candidate. ML/NN methods are benchmark comparators and architecture stress tests.
- **Packaging:** gzip metadata can change across tools or timestamps. Byte hashes are appropriate for archival provenance, but content hashes are the correct guard for consumer-equivalent selected tables.

## Conclusion

The selected-pulse count is exactly reproduced from raw ROOT. The byte-level gzip hash is too strict for downstream physics consumers because it flags benign repacks. The gradient-boosted-tree classifier is the numerical winner by balanced accuracy because it detects all stale controls in the held-out split at the cost of benign false alarms. The deterministic replay sentinel is the practical policy candidate: it has zero false alarms on benign byte-only/fresh-equivalent controls, accepts consumer-equivalent regenerated rows, and catches stale controls that change row support or downstream summaries. Content hashes remain essential provenance checks for exact-artifact identity, but they should not be the only consumer-equivalence gate.

## Artifacts

This directory contains `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `variant_hashes.csv`, `consumer_delta_table.csv`, `method_summary.csv`, `fold_metrics.csv`, `heldout_predictions.csv`, `run_bootstrap_cis.csv`, and `audit_checklist.json`.
