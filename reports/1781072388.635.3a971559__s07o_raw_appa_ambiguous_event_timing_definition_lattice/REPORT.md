# S07o: raw App.A ambiguous-event timing-definition lattice

- **Ticket:** `1781072388.635.3a971559`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Input:** raw B-stack `HRDv` ROOT under `data/root/root` plus S01 `q_template`
- **Split:** grouped by run; no event appears in both train and test in any fold
- **Bootstrap:** run-block bootstrap with `300` resamples

## 1. Preregistered question

The App.A downstream timing labels are internally inconsistent across reports: a documented weak-label tuple has 12,147 labelled events (10,636 clean and 1,511 violating), while the reproducible raw CFD20/App.A gate has 9,897 labelled events and leaves 5,457 downstream-ge2 events in a gray zone. This study asks whether that gray zone contains a reproducible timing-definition boundary that can recover the documented tuple, or whether it must be carried as an unrecoverable systematic.

The fixed raw App.A definition is: downstream multiplicity at least two among B4/B6/B8; CFD20 times; clean if downstream span < 5 ns and all-hit span < 10 ns; violating if downstream span > 10 ns or B2 displacement from the downstream median > 20 ns; ambiguous otherwise. Baselines are the median of samples 0-3 and pulse selection is peak amplitude above 1000 ADC.

## 2. Raw-ROOT reproduction gate

The selected-pulse S00 counts are rebuilt directly from raw `h101/HRDv` before any model is trained:

| quantity              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_pulses |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib        |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis     |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib       |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis    |         125096 |       125096 |       0 |           0 | True   |

The claimed App.A raw numbers are also rebuilt from raw `HRDv`:

| quantity                             |   report_value |   reproduced |   delta | pass   |
|:-------------------------------------|---------------:|-------------:|--------:|:-------|
| raw_cfd20_labelled_events            |           9897 |         9897 |       0 | True   |
| raw_cfd20_clean                      |            nan |         7583 |     nan | True   |
| raw_cfd20_violating                  |            nan |         2314 |     nan | True   |
| ambiguous_downstream_ge2_events      |           5457 |         5457 |       0 | True   |
| raw_cfd20_base_downstream_ge2_events |            nan |        15354 |     nan | True   |

The reproduced raw CFD20/App.A core has 9897 labelled events and 5457 ambiguous downstream-ge2 events.

## 3. Estimands and equations

For event `e`, stave `s`, and CFD fraction `f`, the baseline-subtracted waveform is

`x_{e,s,k} = HRDv_{e,s,k} - median(HRDv_{e,s,0:3})`.

The selected-pulse amplitude is `A_{e,s} = max_k x_{e,s,k}`; a hit satisfies `A_{e,s} > 1000 ADC`. The CFD time is obtained by linear interpolation at `f A_{e,s}`.

For the raw App.A CFD20 gate,

`D_e = max(t_B4,t_B6,t_B8) - min(t_B4,t_B6,t_B8)`,

`H_e = max_s t_s - min_s t_s`,

and, if B2 is present,

`B_e = |t_B2 - median(t_B4,t_B6,t_B8)|`.

Clean core labels satisfy `D_e < 5 ns` and `H_e < 10 ns`; violating core labels satisfy `D_e > 10 ns` or `B_e > 20 ns`; all remaining downstream-ge2 events are ambiguous. The supervised benchmark uses only the core labels and reports held-out ROC AUC, average precision, Brier score, and violating-event rejection at 90% clean efficiency.

As an external-to-App.A diagnostic, the same out-of-fold scores are also evaluated against a q-template non-tail proxy, `q_downstream_max <= 0.06`. This proxy is not an independent truth label because q-template atoms are allowed in the feature matrix, but it tests whether the score ranking aligns with a non-timing-span quality axis.

## 4. Timing-definition lattice

The transparent lattice varied CFD fraction (`0.15`, `0.20`, `0.25`), downstream multiplicity (`>=2`, `>=3`), strict/App.A/loose span thresholds, optional `q_downstream_max <= 0.06`, and ambiguity handling. The closest count rows are:

| definition_id                          |   labelled_events |   clean |   violating |   ambiguous_promoted |   labelled_delta_to_12147 |   clean_delta_to_10636 |   violating_delta_to_1511 |
|:---------------------------------------|------------------:|--------:|------------:|---------------------:|--------------------------:|-----------------------:|--------------------------:|
| cfd15_ds2_loose_qnone_ambexclude       |             12002 |    9816 |        2186 |                    0 |                      -145 |                   -820 |                       675 |
| cfd20_ds2_loose_qnone_ambexclude       |             12307 |   10153 |        2154 |                    0 |                       160 |                   -483 |                       643 |
| cfd25_ds2_loose_qnone_ambexclude       |             12490 |   10368 |        2122 |                    0 |                       343 |                   -268 |                       611 |
| cfd25_ds2_app_a_qnone_ambexclude       |              9951 |    7661 |        2290 |                    0 |                     -2196 |                  -2975 |                       779 |
| cfd20_ds2_app_a_qnone_ambexclude       |              9897 |    7583 |        2314 |                    0 |                     -2250 |                  -3053 |                       803 |
| cfd15_ds2_app_a_qnone_ambexclude       |              9739 |    7386 |        2353 |                    0 |                     -2408 |                  -3250 |                       842 |
| cfd20_ds2_strict_qnone_ambas_violating |             15354 |    4854 |       10500 |                 7848 |                      3207 |                  -5782 |                      8989 |
| cfd15_ds2_strict_qnone_ambas_violating |             15354 |    5101 |       10253 |                 7524 |                      3207 |                  -5535 |                      8742 |
| cfd20_ds2_app_a_qnone_ambas_violating  |             15354 |    7583 |        7771 |                 5457 |                      3207 |                  -3053 |                      6260 |
| cfd15_ds2_app_a_qnone_ambas_violating  |             15354 |    7386 |        7968 |                 5615 |                      3207 |                  -3250 |                      6457 |
| cfd25_ds2_loose_qnone_ambas_violating  |             15354 |   10368 |        4986 |                 2864 |                      3207 |                   -268 |                      3475 |
| cfd15_ds2_loose_qnone_ambas_violating  |             15354 |    9816 |        5538 |                 3352 |                      3207 |                   -820 |                      4027 |
| cfd20_ds2_loose_qnone_ambas_violating  |             15354 |   10153 |        5201 |                 3047 |                      3207 |                   -483 |                      3690 |
| cfd25_ds2_app_a_qnone_ambas_violating  |             15354 |    7661 |        7693 |                 5403 |                      3207 |                  -2975 |                      6182 |
| cfd25_ds2_strict_qnone_ambas_violating |             15354 |    4778 |       10576 |                 7906 |                      3207 |                  -5858 |                      9065 |
| cfd20_ds2_app_a_qtight_ambas_violating |              8750 |    3471 |        5279 |                 3573 |                     -3397 |                  -7165 |                      3768 |
| cfd20_ds2_loose_qtight_ambas_violating |              8750 |    5116 |        3634 |                 2015 |                     -3397 |                  -5520 |                      2123 |
| cfd25_ds2_app_a_qtight_ambas_violating |              8750 |    3577 |        5173 |                 3485 |                     -3397 |                  -7059 |                      3662 |

No lattice row is accepted unless it reproduces the full 12,147 / 10,636 / 1,511 tuple, not merely the total labelled count.

## 5. Model panel

The strong traditional comparator is a transparent span/q score selected inside each training fold from span margins, tail margins, and q-template quality. It intentionally uses the same timing quantities that define the weak labels and is therefore a best-case transparent boundary, not an independent detector classifier.

The ML/NN panel uses only same-event topology, amplitudes, q-template summaries, and raw waveform moment summaries. It excludes run, event identifiers, event order, and active timing-span/displacement columns. Ridge uses standardized linear regression scores; gradient-boosted trees use `HistGradientBoostingClassifier`; MLP is a one-hidden-layer classifier with early stopping; the 1D-CNN treats the four staves as an ordered event sequence with per-stave raw-HRDv summary channels; the new architecture is a gated dilated 1D-CNN over the same four-stave sequence. A shuffled-label HGB sentinel is included.

Model fit audit:

|   fold | method                 | selected                        |   n_features |   n_train |   n_parameters |   last_loss |   train_seconds |
|-------:|:-----------------------|:--------------------------------|-------------:|----------:|---------------:|------------:|----------------:|
|      1 | ridge                  | alpha=10.0                      |           47 |      7920 |            nan | nan         |      nan        |
|      1 | gradient_boosted_trees | HistGradientBoostingClassifier  |           47 |      7920 |            nan | nan         |      nan        |
|      1 | mlp                    | one_hidden_layer_early_stopping |           47 |      7920 |            nan | nan         |      nan        |
|      1 | cnn1d                  | four_stave_sequence             |           36 |      7920 |           2257 |   0.149117  |        0.308    |
|      1 | gated_dilated_cnn      | four_stave_sequence             |           36 |      7920 |           4969 |   0.0681271 |        0.486259 |
|      2 | ridge                  | alpha=1.0                       |           47 |      7914 |            nan | nan         |      nan        |
|      2 | gradient_boosted_trees | HistGradientBoostingClassifier  |           47 |      7914 |            nan | nan         |      nan        |
|      2 | mlp                    | one_hidden_layer_early_stopping |           47 |      7914 |            nan | nan         |      nan        |
|      2 | cnn1d                  | four_stave_sequence             |           36 |      7914 |           2257 |   0.173523  |        0.272415 |
|      2 | gated_dilated_cnn      | four_stave_sequence             |           36 |      7914 |           4969 |   0.0911985 |        0.462279 |
|      3 | ridge                  | alpha=10.0                      |           47 |      7910 |            nan | nan         |      nan        |
|      3 | gradient_boosted_trees | HistGradientBoostingClassifier  |           47 |      7910 |            nan | nan         |      nan        |
|      3 | mlp                    | one_hidden_layer_early_stopping |           47 |      7910 |            nan | nan         |      nan        |
|      3 | cnn1d                  | four_stave_sequence             |           36 |      7910 |           2257 |   0.138279  |        0.277763 |
|      3 | gated_dilated_cnn      | four_stave_sequence             |           36 |      7910 |           4969 |   0.0523474 |        0.471115 |
|      4 | ridge                  | alpha=10.0                      |           47 |      7922 |            nan | nan         |      nan        |
|      4 | gradient_boosted_trees | HistGradientBoostingClassifier  |           47 |      7922 |            nan | nan         |      nan        |
|      4 | mlp                    | one_hidden_layer_early_stopping |           47 |      7922 |            nan | nan         |      nan        |
|      4 | cnn1d                  | four_stave_sequence             |           36 |      7922 |           2257 |   0.0745961 |        0.279557 |
|      4 | gated_dilated_cnn      | four_stave_sequence             |           36 |      7922 |           4969 |   0.100861  |        0.45527  |
|      5 | ridge                  | alpha=10.0                      |           47 |      7922 |            nan | nan         |      nan        |
|      5 | gradient_boosted_trees | HistGradientBoostingClassifier  |           47 |      7922 |            nan | nan         |      nan        |
|      5 | mlp                    | one_hidden_layer_early_stopping |           47 |      7922 |            nan | nan         |      nan        |
|      5 | cnn1d                  | four_stave_sequence             |           36 |      7922 |           2257 |   0.135829  |        0.26762  |
|      5 | gated_dilated_cnn      | four_stave_sequence             |           36 |      7922 |           4969 |   0.0544257 |        0.474025 |

Run-held-out folds:

|   fold | test_runs               |   train_n |   test_n |   test_clean |   test_violating | traditional_selected_columns   |
|-------:|:------------------------|----------:|---------:|-------------:|-----------------:|:-------------------------------|
|      1 | 31,44,52,58,61          |      7920 |     1977 |         1751 |              226 | span_margin_ns                 |
|      2 | 32,35,49,50,53,59       |      7914 |     1983 |         1425 |              558 | span_margin_ns                 |
|      3 | 34,39,42,47,51,62,65    |      7910 |     1987 |         1551 |              436 | span_margin_ns                 |
|      4 | 36,40,41,45,54,60       |      7922 |     1975 |         1603 |              372 | span_margin_ns                 |
|      5 | 33,37,48,55,56,57,63,64 |      7922 |     1975 |         1253 |              722 | span_margin_ns                 |

## 6. Head-to-head results with run-bootstrap CIs

| method                 |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |       brier |   brier_ci_low |   brier_ci_high |   violating_rejection_at_90pct_clean_eff |   violating_rejection_ci_low |   violating_rejection_ci_high | uses_label_defining_timing   | is_sentinel   |
|:-----------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|------------:|---------------:|----------------:|-----------------------------------------:|-----------------------------:|------------------------------:|:-----------------------------|:--------------|
| traditional_span_q     |  1        |         1        |          1        |            1        |                   1        |                    1        | 7.90397e-08 |      0         |     2.43757e-07 |                                 1        |                    1         |                      1        | True                         | False         |
| gradient_boosted_trees |  0.993024 |         0.990133 |          0.995253 |            0.996716 |                   0.994241 |                    0.998265 | 0.0167826   |      0.0145555 |     0.0202297   |                                 0.987468 |                    0.981881  |                      0.992102 | False                        | False         |
| mlp                    |  0.990127 |         0.986458 |          0.993527 |            0.992887 |                   0.987282 |                    0.995684 | 0.0154233   |      0.0120796 |     0.0208141   |                                 0.983578 |                    0.978025  |                      0.98921  | False                        | False         |
| gated_dilated_cnn      |  0.973423 |         0.966518 |          0.97874  |            0.98474  |                   0.97672  |                    0.988862 | 0.0337342   |      0.0297167 |     0.0385102   |                                 0.95981  |                    0.94715   |                      0.971762 | False                        | False         |
| ridge                  |  0.970183 |         0.961564 |          0.975878 |            0.973787 |                   0.960375 |                    0.983315 | 0.0382358   |      0.0321324 |     0.0468786   |                                 0.952895 |                    0.939451  |                      0.964477 | False                        | False         |
| cnn1d                  |  0.953075 |         0.938243 |          0.968154 |            0.981203 |                   0.970341 |                    0.987712 | 0.0863192   |      0.0703125 |     0.106242    |                                 0.844857 |                    0.774625  |                      0.923028 | False                        | False         |
| shuffled_hgb_control   |  0.423113 |         0.366187 |          0.497736 |            0.712274 |                   0.608379 |                    0.778977 | 0.186558    |      0.152242  |     0.255831    |                                 0.100259 |                    0.0883094 |                      0.115079 | False                        | True          |

The primary winner is selected among non-sentinel methods by highest held-out ROC AUC, with Brier and rejection rates shown as calibration and operating-point diagnostics. The named winner in `result.json` is **traditional_span_q** with ROC AUC 1.000 [1.000, 1.000].

External non-tail proxy ROC/AP:

| method                 | proxy_label                       |   positive_events |   total_events |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high | interpretation                                                                            |
|:-----------------------|:----------------------------------|------------------:|---------------:|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|:------------------------------------------------------------------------------------------|
| shuffled_hgb_control   | q_downstream_max_le_0p06_non_tail |              5177 |           9897 |  0.531326 |         0.494099 |          0.565637 |            0.552549 |                   0.512641 |                    0.617479 | support diagnostic; q_template is external to App.A span labels but not independent truth |
| gradient_boosted_trees | q_downstream_max_le_0p06_non_tail |              5177 |           9897 |  0.453604 |         0.380922 |          0.508164 |            0.560889 |                   0.54637  |                    0.583737 | support diagnostic; q_template is external to App.A span labels but not independent truth |
| mlp                    | q_downstream_max_le_0p06_non_tail |              5177 |           9897 |  0.448346 |         0.37377  |          0.496315 |            0.513578 |                   0.47872  |                    0.559526 | support diagnostic; q_template is external to App.A span labels but not independent truth |
| ridge                  | q_downstream_max_le_0p06_non_tail |              5177 |           9897 |  0.348636 |         0.295308 |          0.383101 |            0.426282 |                   0.405167 |                    0.462292 | support diagnostic; q_template is external to App.A span labels but not independent truth |
| gated_dilated_cnn      | q_downstream_max_le_0p06_non_tail |              5177 |           9897 |  0.335402 |         0.302566 |          0.361911 |            0.411282 |                   0.382133 |                    0.46843  | support diagnostic; q_template is external to App.A span labels but not independent truth |
| cnn1d                  | q_downstream_max_le_0p06_non_tail |              5177 |           9897 |  0.282943 |         0.259664 |          0.304596 |            0.388456 |                   0.362847 |                    0.439814 | support diagnostic; q_template is external to App.A span labels but not independent truth |
| traditional_span_q     | q_downstream_max_le_0p06_non_tail |              5177 |           9897 |  0.279036 |         0.252825 |          0.307071 |            0.387707 |                   0.358661 |                    0.443003 | support diagnostic; q_template is external to App.A span labels but not independent truth |

## 7. Gray-zone adoption test

After core-label training, each method scores the 5,457 ambiguous events. A gray-zone event is promoted to clean if its score is inside the central 90% clean-core acceptance region, promoted to violating if it is inside the central 90% violating-core rejection region, and left gray otherwise. This is deliberately conservative and does not tune thresholds to the documented count.

| method                 |   ambiguous_promoted |   ambiguous_promoted_clean |   ambiguous_promoted_violating |   labelled_events |   clean |   violating |   labelled_delta_to_12147 |   clean_delta_to_10636 |   violating_delta_to_1511 |   tuple_l1_error |
|:-----------------------|---------------------:|---------------------------:|-------------------------------:|------------------:|--------:|------------:|--------------------------:|-----------------------:|--------------------------:|-----------------:|
| traditional_span_q     |                 2341 |                       2341 |                              0 |             12238 |    9924 |        2314 |                        91 |                   -712 |                       803 |             1606 |
| mlp                    |                 4115 |                       4061 |                             54 |             14012 |   11644 |        2368 |                      1865 |                   1008 |                       857 |             3730 |
| gradient_boosted_trees |                 4277 |                       4217 |                             60 |             14174 |   11800 |        2374 |                      2027 |                   1164 |                       863 |             4054 |
| gated_dilated_cnn      |                 4413 |                       4267 |                            146 |             14310 |   11850 |        2460 |                      2163 |                   1214 |                       949 |             4326 |
| ridge                  |                 4468 |                       4275 |                            193 |             14365 |   11858 |        2507 |                      2218 |                   1222 |                       996 |             4436 |
| cnn1d                  |                 4580 |                       4338 |                            242 |             14477 |   11921 |        2556 |                      2330 |                   1285 |                      1045 |             4660 |

The tuple error is the L1 distance to `(labelled, clean, violating) = (12147, 10636, 1511)`. A successful rescue would require small total error and physically credible clean/violating composition. None of the learned boundaries reproduces the tuple; many increase the already-too-large raw violating count.

## 8. Systematics and caveats

The largest systematic is label circularity: the core labels are derived from timing spans, so high AUC against those labels is not evidence that App.A is externally true. The traditional score is intentionally timing-overlapping; ML scores are less direct but still inherit weak-label bias through supervised training. The run-block bootstrap reflects between-run transfer but has only the available run groups, so CI granularity is limited. The 1D-CNN and gated dilated CNN operate on raw-HRDv-derived four-stave summary sequences rather than all 18 samples per stave; this is appropriate for an event-boundary audit but weaker than a full waveform classifier. q-template values come from the previously reproduced S01 table and missing q rows are median-imputed with a missingness flag.

The decision rule is intentionally stricter than AUC ranking: no method is adopted unless it reproduces the full documented count tuple and does not fail leakage/sentinel checks. The shuffled-label sentinel remains a lower-bound leakage check only; passing it does not validate the weak labels.

## 9. Verdict

**Winner for supervised core-label discrimination:** `traditional_span_q`.

**Adoption verdict:** `no_adoptable_boundary_documented_tuple_not_reproduced`.

The raw HRDv evidence supports the 9,897 labelled / 5,457 ambiguous App.A reproduction, not the documented 12,147 weak-label tuple. The ambiguous pool should remain a bounded gray-zone systematic for downstream timing-tail, pile-up, and morphology consumers.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.py --config configs/s07o_1781072388_635_3a971559_raw_appa_ambiguous_lattice.json
```

Artifacts: `raw_s00_reproduction.csv`, `raw_candidate_counts_by_run.csv`, `raw_candidate_event_universe.csv.gz`, `appa_reproduction_counts.csv`, `label_definition_lattice_counts.csv`, `method_metrics.csv`, `external_non_tail_proxy_metrics.csv`, `run_heldout_folds.csv`, `heldout_scores.csv`, `model_fit_audit.csv`, `ambiguous_adoption_decisions.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and this report.
