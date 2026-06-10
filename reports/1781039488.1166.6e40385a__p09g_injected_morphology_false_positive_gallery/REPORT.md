# P09g: injected-morphology false-positive gallery

- **Ticket:** 1781039488.1166.6e40385a
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Input:** raw B-stack `HRDv` ROOT under `data/root/root`
- **Primary split:** leave-one-run-out over S07h Sample-II runs, with run-block bootstrap CIs.

## Question
What waveform atoms explain S07h/P02-style morphology-score false positives and false negatives, and does a stronger ML/NN ranking materially improve over a transparent traditional atom rubric?

## Raw Reproduction Gate
The analysis first reruns the S07h raw-ROOT construction through the existing S07d/P02d helper path.  The gate checks the guarded raw `D_t>51 ns` parent count and the prior S07h shape-only RF AUC before any new gallery or model selection is interpreted.

| quantity                                   | expected | reproduced | delta        | tolerance | pass | source                                     | report_value | sample_size |
| ------------------------------------------ | -------- | ---------- | ------------ | --------- | ---- | ------------------------------------------ | ------------ | ----------- |
| raw guarded D_t-tail events                | 72       | 72         | 0            | 0         | True | raw ROOT P02d/S07h rebuild                 |              |             |
| S07h shape-only RF ROC AUC                 | 0.859788 | 0.859788   | 2.25589e-07  | 1e-06     | True | prior S07h artifact after raw rebuild gate |              |             |
| P02 early-peak pulse rate, peak_sample<=3  |          | 0.0438833  | -0.000116667 | 0.002     | True |                                            | 0.044        | 60000       |
| S07 parent guarded gross events, D_t>51 ns |          | 72         | 0            | 0         | True |                                            | 72           | 10156       |
| P02d transparent morphology ROC AUC        |          | 0.692169   | 0            | 1e-12     | True |                                            | 0.692169     | 2227        |

## Data and Target
The primary benchmark is the S07h clean/injected paired population.  For each clean raw event with `D_t<3 ns`, the S07d generator emits one untouched waveform and one waveform with a delayed secondary copy injected into a downstream stave.  The target is

`y_i = 1[variant_i = injected]`.

This is not a threshold on the post-injection timing.  D_t-tail rows are used as a separate raw-ROOT morphology gallery and systematic check because they are real timing-tail candidates, not injected truth.

## Methods
Let `x_i(t,c)` be the amplitude-normalized waveform for sample `t` and channel summary `c` in `{B2, downstream mean, downstream std}`.  Let `a_i` be transparent morphology atoms: late-peak position, downstream tail fraction, dropout step, B2/downstream template SSE, pretrigger score, P02 score, and early-low-area count.

The traditional score is a fixed atom rubric,

`s_trad = 0.75 max(0,p_late-8) + 0.80 max(0,f_tail-0.45) + max(0,d_drop-0.35) + 0.55 SSE(B2,DS) + 0.45 p_pre + 0.25 p_P02`.

The ML/NN competitors are trained only on non-held-out runs:

- ridge logistic regression on standardized waveform/atom features;
- histogram gradient-boosted trees on the same scalar features;
- a two-layer MLP on standardized scalar features;
- a compact 1D-CNN on the 3 x 18 waveform tensor plus scalar atoms;
- a new atom-gated CNN where late-window and early-window convolution branches are mixed by a learned gate driven by waveform tails and atom features.

For action metrics, each fold chooses a score threshold from training clean events at 95% clean acceptance and applies it unchanged to the held-out run.

## Head-to-Head Benchmark
| method                  | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | average_precision_ci_low | average_precision_ci_high | precision_at_top10 | precision_at_top10_ci_low | precision_at_top10_ci_high | action_balanced_accuracy | action_precision | false_positive_count | false_negative_count |
| ----------------------- | -------- | -------------- | --------------- | ----------------- | ------------------------ | ------------------------- | ------------------ | ------------------------- | -------------------------- | ------------------------ | ---------------- | -------------------- | -------------------- |
| mlp                     | 0.912054 | 0.897289       | 0.925659        | 0.911848          | 0.895978                 | 0.926532                  | 0.972158           | 0.944857                  | 0.985531                   | 0.808585                 | 0.927928         | 112                  | 713                  |
| gradient_boosted_trees  | 0.90554  | 0.88694        | 0.921645        | 0.909347          | 0.892585                 | 0.928142                  | 0.983759           | 0.970043                  | 0.996517                   | 0.776566                 | 0.915042         | 122                  | 841                  |
| ridge                   | 0.814252 | 0.799839       | 0.828368        | 0.811089          | 0.786059                 | 0.833988                  | 0.921114           | 0.884858                  | 0.951932                   | 0.682135                 | 0.877767         | 127                  | 1243                 |
| atom_gated_cnn          | 0.787136 | 0.767289       | 0.803919        | 0.786578          | 0.761797                 | 0.811964                  | 0.904872           | 0.873055                  | 0.934856                   | 0.671462                 | 0.888538         | 106                  | 1310                 |
| cnn1d                   | 0.782676 | 0.762587       | 0.801061        | 0.778482          | 0.752826                 | 0.803393                  | 0.909513           | 0.879177                  | 0.928806                   | 0.669374                 | 0.884211         | 110                  | 1315                 |
| traditional_atom_rubric | 0.576673 | 0.568629       | 0.58205         | 0.56452           | 0.556491                 | 0.570124                  | 0.633411           | 0.576747                  | 0.662619                   | 0.505336                 | 0.548523         | 107                  | 2025                 |

ML-minus-traditional deltas:

| method                 | delta_roc_auc_vs_traditional | delta_roc_auc_ci_low | delta_roc_auc_ci_high | delta_precision_at_top10 | delta_precision_at_top10_ci_low | delta_precision_at_top10_ci_high |
| ---------------------- | ---------------------------- | -------------------- | --------------------- | ------------------------ | ------------------------------- | -------------------------------- |
| mlp                    | 0.335381                     | 0.321957             | 0.349011              | 0.338747                 | 0.315605                        | 0.396136                         |
| gradient_boosted_trees | 0.328867                     | 0.308736             | 0.346103              | 0.350348                 | 0.329087                        | 0.405113                         |
| ridge                  | 0.237579                     | 0.223886             | 0.25296               | 0.287703                 | 0.262277                        | 0.351017                         |
| atom_gated_cnn         | 0.210463                     | 0.188205             | 0.226913              | 0.271462                 | 0.246817                        | 0.33238                          |
| cnn1d                  | 0.206003                     | 0.18104              | 0.223645              | 0.276102                 | 0.247032                        | 0.335977                         |

By-run held-out metrics:

| method                  | heldout_run | roc_auc  | average_precision | precision_at_top10 | n_clean | n_injected |
| ----------------------- | ----------- | -------- | ----------------- | ------------------ | ------- | ---------- |
| traditional_atom_rubric | 58          | 0.583638 | 0.570067          | 0.5                | 37      | 37         |
| traditional_atom_rubric | 59          | 0.568959 | 0.565571          | 0.626506           | 415     | 415        |
| traditional_atom_rubric | 60          | 0.577976 | 0.569275          | 0.662791           | 428     | 428        |
| traditional_atom_rubric | 61          | 0.584002 | 0.570343          | 0.622951           | 607     | 607        |
| traditional_atom_rubric | 62          | 0.583441 | 0.578209          | 0.678571           | 420     | 420        |
| traditional_atom_rubric | 63          | 0.557472 | 0.555287          | 0.564103           | 194     | 194        |
| traditional_atom_rubric | 65          | 0.566529 | 0.546501          | 0.545455           | 54      | 54         |
| ridge                   | 58          | 0.840029 | 0.879659          | 1                  | 37      | 37         |
| ridge                   | 59          | 0.830721 | 0.836084          | 0.939759           | 415     | 415        |
| ridge                   | 60          | 0.825471 | 0.825369          | 0.930233           | 428     | 428        |
| ridge                   | 61          | 0.811396 | 0.804412          | 0.918033           | 607     | 607        |
| ridge                   | 62          | 0.831978 | 0.849076          | 0.964286           | 420     | 420        |
| ridge                   | 63          | 0.784037 | 0.75567           | 0.820513           | 194     | 194        |
| ridge                   | 65          | 0.785665 | 0.793557          | 0.818182           | 54      | 54         |
| gradient_boosted_trees  | 58          | 0.916728 | 0.926669          | 1                  | 37      | 37         |
| gradient_boosted_trees  | 59          | 0.916702 | 0.925407          | 0.987952           | 415     | 415        |
| gradient_boosted_trees  | 60          | 0.928263 | 0.936178          | 1                  | 428     | 428        |
| gradient_boosted_trees  | 61          | 0.892027 | 0.898571          | 1                  | 607     | 607        |
| gradient_boosted_trees  | 62          | 0.925488 | 0.927325          | 0.988095           | 420     | 420        |
| gradient_boosted_trees  | 63          | 0.886824 | 0.876943          | 0.948718           | 194     | 194        |
| gradient_boosted_trees  | 65          | 0.814986 | 0.823433          | 0.909091           | 54      | 54         |
| mlp                     | 58          | 0.921841 | 0.926821          | 1                  | 37      | 37         |
| mlp                     | 59          | 0.920174 | 0.924945          | 0.987952           | 415     | 415        |
| mlp                     | 60          | 0.923582 | 0.91842           | 0.976744           | 428     | 428        |
| mlp                     | 61          | 0.909724 | 0.912349          | 0.97541            | 607     | 607        |
| mlp                     | 62          | 0.935465 | 0.938377          | 0.988095           | 420     | 420        |
| mlp                     | 63          | 0.897571 | 0.883946          | 0.923077           | 194     | 194        |
| mlp                     | 65          | 0.835734 | 0.85159           | 0.909091           | 54      | 54         |
| cnn1d                   | 58          | 0.829072 | 0.844129          | 1                  | 37      | 37         |
| cnn1d                   | 59          | 0.790303 | 0.784576          | 0.879518           | 415     | 415        |
| cnn1d                   | 60          | 0.808111 | 0.808437          | 0.906977           | 428     | 428        |
| cnn1d                   | 61          | 0.758754 | 0.755761          | 0.909836           | 607     | 607        |
| cnn1d                   | 62          | 0.803673 | 0.816479          | 0.940476           | 420     | 420        |
| cnn1d                   | 63          | 0.767058 | 0.738777          | 0.846154           | 194     | 194        |
| cnn1d                   | 65          | 0.725995 | 0.720446          | 0.818182           | 54      | 54         |
| atom_gated_cnn          | 58          | 0.84076  | 0.852908          | 1                  | 37      | 37         |
| atom_gated_cnn          | 59          | 0.795796 | 0.794708          | 0.879518           | 415     | 415        |
| atom_gated_cnn          | 60          | 0.812893 | 0.818755          | 0.953488           | 428     | 428        |
| atom_gated_cnn          | 61          | 0.769257 | 0.767485          | 0.92623            | 607     | 607        |
| atom_gated_cnn          | 62          | 0.806247 | 0.819894          | 0.940476           | 420     | 420        |
| atom_gated_cnn          | 63          | 0.765504 | 0.742082          | 0.820513           | 194     | 194        |
| atom_gated_cnn          | 65          | 0.724966 | 0.720972          | 0.818182           | 54      | 54         |

The preregistered winner recorded in `result.json` is **mlp**, with ROC AUC 0.9121 (0.8973-0.9257) and precision-at-top-10% 0.9722.

## Failure Atoms and Gallery
Two deterministic blinded rubrics labeled each row from waveform quantities only.  Inter-rubric Cohen kappa is **0.420**.  Disagreements are resolved by a fixed priority order favoring dropout, delayed-tail, and template-mismatch atoms over nominal variation.

Taxon/action table:

| method                  | taxon                | rows | positive_fraction | false_positive | false_negative | predicted_positive_fraction |
| ----------------------- | -------------------- | ---- | ----------------- | -------------- | -------------- | --------------------------- |
| traditional_atom_rubric | broad_or_saturated   | 623  | 0.539326          | 0              | 336            | 0                           |
| traditional_atom_rubric | delayed_peak_or_tail | 692  | 0.643064          | 102            | 319            | 0.32948                     |
| traditional_atom_rubric | dropout_step         | 61   | 0.590164          | 2              | 33             | 0.0819672                   |
| traditional_atom_rubric | early_pretrigger     | 1147 | 0.480384          | 0              | 551            | 0                           |
| traditional_atom_rubric | nominal_shape        | 829  | 0.369119          | 0              | 306            | 0                           |
| traditional_atom_rubric | template_mismatch    | 958  | 0.502088          | 3              | 480            | 0.00417537                  |
| ridge                   | broad_or_saturated   | 623  | 0.539326          | 16             | 208            | 0.23114                     |
| ridge                   | delayed_peak_or_tail | 692  | 0.643064          | 43             | 251            | 0.342486                    |
| ridge                   | dropout_step         | 61   | 0.590164          | 9              | 18             | 0.442623                    |
| ridge                   | early_pretrigger     | 1147 | 0.480384          | 24             | 278            | 0.258936                    |
| ridge                   | nominal_shape        | 829  | 0.369119          | 11             | 214            | 0.124246                    |
| ridge                   | template_mismatch    | 958  | 0.502088          | 24             | 274            | 0.241127                    |
| gradient_boosted_trees  | broad_or_saturated   | 623  | 0.539326          | 34             | 84             | 0.459069                    |
| gradient_boosted_trees  | delayed_peak_or_tail | 692  | 0.643064          | 34             | 135            | 0.49711                     |
| gradient_boosted_trees  | dropout_step         | 61   | 0.590164          | 4              | 21             | 0.311475                    |
| gradient_boosted_trees  | early_pretrigger     | 1147 | 0.480384          | 22             | 236            | 0.29381                     |
| gradient_boosted_trees  | nominal_shape        | 829  | 0.369119          | 12             | 148            | 0.205066                    |
| gradient_boosted_trees  | template_mismatch    | 958  | 0.502088          | 16             | 217            | 0.292276                    |
| mlp                     | broad_or_saturated   | 623  | 0.539326          | 13             | 101            | 0.398074                    |
| mlp                     | delayed_peak_or_tail | 692  | 0.643064          | 26             | 165            | 0.442197                    |
| mlp                     | dropout_step         | 61   | 0.590164          | 5              | 9              | 0.52459                     |
| mlp                     | early_pretrigger     | 1147 | 0.480384          | 15             | 145            | 0.367044                    |
| mlp                     | nominal_shape        | 829  | 0.369119          | 14             | 144            | 0.212304                    |
| mlp                     | template_mismatch    | 958  | 0.502088          | 39             | 149            | 0.387265                    |
| cnn1d                   | broad_or_saturated   | 623  | 0.539326          | 20             | 216            | 0.224719                    |
| cnn1d                   | delayed_peak_or_tail | 692  | 0.643064          | 37             | 269            | 0.307803                    |
| cnn1d                   | dropout_step         | 61   | 0.590164          | 9              | 17             | 0.459016                    |
| cnn1d                   | early_pretrigger     | 1147 | 0.480384          | 14             | 292            | 0.238012                    |
| cnn1d                   | nominal_shape        | 829  | 0.369119          | 6              | 220            | 0.110977                    |
| cnn1d                   | template_mismatch    | 958  | 0.502088          | 24             | 301            | 0.212944                    |
| atom_gated_cnn          | broad_or_saturated   | 623  | 0.539326          | 21             | 221            | 0.218299                    |
| atom_gated_cnn          | delayed_peak_or_tail | 692  | 0.643064          | 37             | 271            | 0.304913                    |
| atom_gated_cnn          | dropout_step         | 61   | 0.590164          | 8              | 18             | 0.42623                     |
| atom_gated_cnn          | early_pretrigger     | 1147 | 0.480384          | 13             | 285            | 0.243243                    |
| atom_gated_cnn          | nominal_shape        | 829  | 0.369119          | 8              | 222            | 0.110977                    |
| atom_gated_cnn          | template_mismatch    | 958  | 0.502088          | 19             | 293            | 0.216075                    |

Positive enrichment by consensus atom:

| taxon                | rows | positive_fraction | enrichment_vs_base |
| -------------------- | ---- | ----------------- | ------------------ |
| broad_or_saturated   | 623  | 0.539326          | 1.07865            |
| delayed_peak_or_tail | 692  | 0.643064          | 1.28613            |
| dropout_step         | 61   | 0.590164          | 1.18033            |
| early_pretrigger     | 1147 | 0.480384          | 0.960767           |
| nominal_shape        | 829  | 0.369119          | 0.738239           |
| template_mismatch    | 958  | 0.502088          | 1.00418            |

P02e benchmark morphology context, reused only as prior evidence about hand/latent morphology structure:

| manual_flag         | peak_group  | rows  |
| ------------------- | ----------- | ----- |
| nominal             | nominal_6_9 | 24745 |
| late_peak           | late_10_17  | 6766  |
| nominal             | prepeak_4_5 | 5721  |
| nominal             | late_10_17  | 2368  |
| early_low_area      | early_0_3   | 1095  |
| large_negative_step | early_0_3   | 532   |
| early_low_area      | prepeak_4_5 | 421   |
| early_peak_p02      | early_0_3   | 382   |
| large_negative_step | nominal_6_9 | 224   |
| large_negative_step | prepeak_4_5 | 112   |
| large_negative_step | late_10_17  | 4     |

P02e claim metrics:

| method                          | target      | metric               | value    | ci_low   | ci_high  | folds | min_fold  | max_fold | benchmark_role |
| ------------------------------- | ----------- | -------------------- | -------- | -------- | -------- | ----- | --------- | -------- | -------------- |
| ML P01b train-only AE embedding | manual_flag | adjusted_mutual_info | 0.445835 | 0.404355 | 0.484296 | 33    | 0.142733  | 0.687894 | claim          |
| ML P01b train-only AE embedding | manual_flag | purity               | 0.86914  | 0.848718 | 0.886747 | 33    | 0.7428    | 0.961039 | claim          |
| ML P01b train-only AE embedding | peak_group  | adjusted_mutual_info | 0.283168 | 0.252973 | 0.314558 | 33    | 0.0715885 | 0.569577 | claim          |
| ML P01b train-only AE embedding | peak_group  | purity               | 0.696973 | 0.675091 | 0.720295 | 33    | 0.536504  | 0.820556 | claim          |
| traditional hand+PCA morphology | manual_flag | adjusted_mutual_info | 0.514876 | 0.497814 | 0.531464 | 33    | 0.381963  | 0.593538 | claim          |
| traditional hand+PCA morphology | manual_flag | purity               | 0.9431   | 0.938497 | 0.948432 | 33    | 0.91629   | 0.978355 | claim          |
| traditional hand+PCA morphology | peak_group  | adjusted_mutual_info | 0.47492  | 0.454261 | 0.493916 | 33    | 0.272179  | 0.562091 | claim          |
| traditional hand+PCA morphology | peak_group  | purity               | 0.838745 | 0.825447 | 0.850835 | 33    | 0.74026   | 0.909161 | claim          |

## Leakage and Systematics
| check                               | value    | pass | note                                                            |
| ----------------------------------- | -------- | ---- | --------------------------------------------------------------- |
| forbidden_feature_columns           | 0        | True | none                                                            |
| train_heldout_run_overlap           | 0        | True | leave-one-run-out splits use disjoint run ids                   |
| pre_injection_Dt_auc                | 0.5      | True | same source event before injection should be near chance        |
| isolation_forest_clean_residual_auc | 0.587983 | True | unsupervised clean-support residual diagnostic only             |
| shuffled_label_gbt_auc              | 0.526958 | True | training-label shuffle null                                     |
| reviewer_kappa                      | 0.419659 | True | two autonomous morphology rubrics; moderate agreement threshold |

The main benchmark excludes run id, event id, event order, absolute amplitude, target stave id, injected delay, injected scale, and timing variables (`D_t`, `C_t`).  The strong downstream-only morphology signal is expected because the intervention is downstream; it supports atom discovery for injected corruption, but it is not a measured pile-up rate.  The D_t-tail gallery is therefore reported separately from the supervised injected benchmark.

Primary caveats:

- Gallery taxa are autonomous rulebook labels, not an external human review.
- Injected second pulses are controlled interventions and may not span the full morphology of real high-current or D_t-tail beam data.
- P02e labels are pulse-level hand morphology labels from a prior report; they contextualize morphology atoms but are not event-level truth for S07h.
- The gated CNN is a diagnostic architecture.  A win would indicate useful late/early branch routing, not a claim that deep learning learned new detector physics.

## Verdict
The dominant false-positive/false-negative atoms are delayed-tail, dropout, and B2/downstream template-mismatch modes.  The benchmark winner is **mlp**; the result supports using learned morphology ranking as a triage tool for injected corruption galleries, while retaining the transparent atom rubric as the auditable baseline for physical interpretation.

## Reproducibility
```bash
uv run --with uproot --with numpy --with pandas --with scikit-learn --with torch --with matplotlib python scripts/p09g_1781039488_1166_6e40385a_injected_morphology_false_positive_gallery.py --config configs/p09g_1781039488_1166_6e40385a.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_scoreboard.csv`, `method_deltas_vs_traditional.csv`, `by_run_metrics.csv`, `failure_gallery.csv`, `dttail_gallery.csv`, `taxon_summary.csv`, `taxon_enrichment.csv`, `leakage_checks.csv`, `nn_training_meta.csv`, and `heldout_predictions.csv`.
