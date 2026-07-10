# P09k: real reviewer locked-label replacement

Ticket: `1783600897.13505.593263a7`. Worker: `testbeam-laptop-3`.

## Abstract

P09k replaces the deterministic P09j reviewer proxy with the independent reviewer-label resources available in the repository and reruns the P09g frozen-method benchmark on the same run/stave/variant-balanced gallery. The analysis keeps the P09g parent raw-ROOT reproduction and all P09g model scores fixed, then evaluates the traditional atom rubric, ridge, gradient-boosted trees, MLP, 1D-CNN, and atom-gated CNN against the locked reviewer target using run-block bootstrap confidence intervals.

## Raw-ROOT Reproduction

The parent raw-ROOT inputs are the eight P09g files in `data/root/root`. `raw_root_input_verification.csv` recomputes SHA-256 hashes for every ROOT file listed in the P09g manifest. The reproduced selected-pulse denominator is copied to `reproduction_counts_by_run.csv` because P09k is a locked-label replacement on the exact P09g gallery, not a new event selection.

Verified ROOT inputs: **8** matched, **0** mismatched. Reproduced selected pulses: **160313** over **8** runs.

## Locked Reviewer Labels

The direct reviewer target is built from `independent_review_labels.csv` and `reviewer_calibrated_gallery.csv`. Rows join to P09g by `(run,eventno,evt)` where possible. Direct coverage is sparse; therefore the benchmark reports two quantities: direct human lock coverage and nearest-reviewed transfer coverage. The transfer is a nearest-neighbor assignment in frozen P09g score/morphology space and is included only because no full same-gallery human-label table is present in the repository. This limitation is a primary systematic, not an implementation detail.

| quantity                    | value    |
| --------------------------- | -------- |
| P09c_external_review        | 256      |
| P09i_locked_physical_review | 187      |
| p09g_rows                   | 4310     |
| direct_human_locked_rows    | 20       |
| transferred_locked_rows     | 4290     |
| locked_positive_rate        | 0.267749 |
| median_transfer_distance_z  | 2.17324  |

For row \(i\), the locked target is

\[ y_i = y_i^{direct} \quad \text{if an independent reviewer row joins, otherwise } y_{j(i)}^{direct}, \]

where \(j(i)\) is the nearest externally reviewed row after z-scoring the frozen score vector and timing morphology features on the directly joined subset. The transfer distance is recorded in `locked_reviewer_labels.csv`.

## Benchmark Methods

All methods are frozen from P09g. The traditional method is `traditional_atom_rubric`; ML/NN methods are `ridge`, `gradient_boosted_trees`, `mlp`, `cnn1d`, and the new architecture `atom_gated_cnn`. No method is retrained on reviewer labels. The primary metric is average precision:

\[ AP_m = \sum_n (R_n - R_{n-1}) P_n, \]

where predictions are ranked by the method score. We also report ROC AUC, action precision, and balanced accuracy for the frozen action threshold. For each metric \(S\), run-block bootstrap intervals sample the seven held-out runs with replacement:

\[ CI_{95}(S_m) = \left[Q_{0.025}\{S_m^{(b)}\}, Q_{0.975}\{S_m^{(b)}\}\right]. \]

## Main Results

| method                  | average_precision | average_precision_ci_low | average_precision_ci_high | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | action_precision | action_precision_ci_low | action_precision_ci_high | balanced_accuracy | balanced_accuracy_ci_low | balanced_accuracy_ci_high | positive_action_rate |
| ----------------------- | ----------------- | ------------------------ | ------------------------- | -------- | -------------- | --------------- | ---------------- | ----------------------- | ------------------------ | ----------------- | ------------------------ | ------------------------- | -------------------- |
| gradient_boosted_trees  | 0.508348          | 0.419199                 | 0.571321                  | 0.819178 | 0.802976       | 0.829752        | 0.552228         | 0.483504                | 0.584913                 | 0.741718          | 0.700654                 | 0.763572                  | 0.333179             |
| mlp                     | 0.427787          | 0.370478                 | 0.465931                  | 0.782689 | 0.764213       | 0.804359        | 0.504505         | 0.438452                | 0.542872                 | 0.717698          | 0.697994                 | 0.741772                  | 0.360557             |
| cnn1d                   | 0.422204          | 0.368833                 | 0.457022                  | 0.782951 | 0.769785       | 0.801853        | 0.461053         | 0.410891                | 0.493938                 | 0.608659          | 0.595715                 | 0.624496                  | 0.220418             |
| atom_gated_cnn          | 0.419921          | 0.368427                 | 0.454374                  | 0.78122  | 0.764411       | 0.803112        | 0.446898         | 0.4                     | 0.476611                 | 0.600809          | 0.575868                 | 0.63844                   | 0.22065              |
| ridge                   | 0.39486           | 0.332846                 | 0.430504                  | 0.748378 | 0.718623       | 0.784925        | 0.431184         | 0.346481                | 0.48345                  | 0.600476          | 0.567183                 | 0.625925                  | 0.241067             |
| traditional_atom_rubric | 0.264755          | 0.211943                 | 0.304743                  | 0.496667 | 0.465957       | 0.516384        | 0.021097         | 0                       | 0.0433589                | 0.465411          | 0.451924                 | 0.47299                   | 0.0549884            |

## Taxon-Stratified Check

| method                  | taxon                | n    | locked_positive_rate | average_precision | action_precision |
| ----------------------- | -------------------- | ---- | -------------------- | ----------------- | ---------------- |
| traditional_atom_rubric | broad_or_saturated   | 623  | 0.422151             | 0.515431          | 0                |
| traditional_atom_rubric | delayed_peak_or_tail | 692  | 0.319364             | 0.228757          | 0.0175439        |
| traditional_atom_rubric | dropout_step         | 61   | 0.196721             | 0.240377          | 0.2              |
| traditional_atom_rubric | early_pretrigger     | 1147 | 0.255449             | 0.209591          | 0                |
| traditional_atom_rubric | nominal_shape        | 829  | 0.199035             | 0.203453          | 0                |
| traditional_atom_rubric | template_mismatch    | 958  | 0.208768             | 0.199051          | 0                |
| ridge                   | broad_or_saturated   | 623  | 0.422151             | 0.602137          | 0.673611         |
| ridge                   | delayed_peak_or_tail | 692  | 0.319364             | 0.394039          | 0.43038          |
| ridge                   | dropout_step         | 61   | 0.196721             | 0.237076          | 0.222222         |
| ridge                   | early_pretrigger     | 1147 | 0.255449             | 0.391048          | 0.414141         |
| ridge                   | nominal_shape        | 829  | 0.199035             | 0.462609          | 0.514563         |
| ridge                   | template_mismatch    | 958  | 0.208768             | 0.281547          | 0.290043         |
| gradient_boosted_trees  | broad_or_saturated   | 623  | 0.422151             | 0.716789          | 0.744755         |
| gradient_boosted_trees  | delayed_peak_or_tail | 692  | 0.319364             | 0.667671          | 0.581395         |
| gradient_boosted_trees  | dropout_step         | 61   | 0.196721             | 0.252611          | 0.263158         |
| gradient_boosted_trees  | early_pretrigger     | 1147 | 0.255449             | 0.409154          | 0.474777         |
| gradient_boosted_trees  | nominal_shape        | 829  | 0.199035             | 0.558465          | 0.629412         |
| gradient_boosted_trees  | template_mismatch    | 958  | 0.208768             | 0.34095           | 0.385714         |
| mlp                     | broad_or_saturated   | 623  | 0.422151             | 0.647487          | 0.721774         |
| mlp                     | delayed_peak_or_tail | 692  | 0.319364             | 0.530319          | 0.581699         |
| mlp                     | dropout_step         | 61   | 0.196721             | 0.253569          | 0.28125          |
| mlp                     | early_pretrigger     | 1147 | 0.255449             | 0.381366          | 0.456057         |
| mlp                     | nominal_shape        | 829  | 0.199035             | 0.509846          | 0.522727         |
| mlp                     | template_mismatch    | 958  | 0.208768             | 0.302735          | 0.361186         |
| cnn1d                   | broad_or_saturated   | 623  | 0.422151             | 0.60843           | 0.671429         |
| cnn1d                   | delayed_peak_or_tail | 692  | 0.319364             | 0.399658          | 0.478873         |
| cnn1d                   | dropout_step         | 61   | 0.196721             | 0.228132          | 0.25             |
| cnn1d                   | early_pretrigger     | 1147 | 0.255449             | 0.408136          | 0.435897         |
| cnn1d                   | nominal_shape        | 829  | 0.199035             | 0.530853          | 0.554348         |
| cnn1d                   | template_mismatch    | 958  | 0.208768             | 0.314236          | 0.318627         |

## Winner

The winner named in `result.json` is **gradient_boosted_trees** by average precision with run-block bootstrap confidence intervals. The strongest traditional comparator is `traditional_atom_rubric`.

## Systematics and Caveats

- Direct human-label joins cover only the subset of P09g events that overlap older independent-review galleries; most P09g rows require nearest-reviewed transfer.
- The transferred target is suitable as an audit of consistency with available human labels, not as a substitute for a completed same-gallery review campaign.
- P09k inherits P09g's selected-pulse definition, raw-ROOT files, model scores, and thresholds.
- CIs capture run-to-run variation across held-out P09g runs; they do not include uncertainty from missing human labels.
- The atom-gated CNN is a frozen architecture inherited from P09g and was not retuned for the reviewer target.

## Artifacts

`result.json`, `REPORT.md`, `manifest.json`, `raw_root_input_verification.csv`, `reproduction_counts_by_run.csv`, `locked_reviewer_labels.csv`, `label_source_audit.csv`, `method_scoreboard.csv`, `per_run_metrics.csv`, `taxon_metrics.csv`, and `input_sha256.csv`.
