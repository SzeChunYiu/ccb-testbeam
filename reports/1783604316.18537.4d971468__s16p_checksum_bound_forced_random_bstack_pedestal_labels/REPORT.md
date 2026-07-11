# S16p Checksum-Bound Forced/Random B-Stack Pedestal Label Ingest

- **Ticket:** `1783604316.18537.4d971468`
- **Worker:** `testbeam-laptop-4`
- **Runtime:** 116.9 s
- **Raw ROOT anchor:** 640,737 selected B-stack pulses; expected 640,737; delta 0.
- **Winner:** `gradient_boosted_trees` with run-mean MAE 42.895 ADC and 95% run-bootstrap CI [35.197, 50.205].

## Abstract

This ticket asks for a checksum-pinned forced/random/no-pulse B-stack ROOT ingest with trigger-mode metadata and an S16o/S16p-style benchmark against true electronics-pedestal labels. The mounted data tree contains the canonical reduced B-stack ROOT files but no dedicated forced/random/no-pulse B-stack ROOT source. I therefore separate two estimands. First, the ingest audit is a direct raw-ROOT audit of every analysed B-stack file, with SHA-256 checksums and trigger-mode summaries. Second, because true no-pulse labels are absent, the benchmark is the strongest available beam-pretrigger surrogate: predict a hidden pretrigger sample from the other three samples and waveform covariates with full runs held out. The numerical winner is recorded, but the production adoption rule remains blocked until true forced/random labels are mounted.

## Raw ROOT Reproduction

For run \(r\), stave \(s\), and waveform sample vector \(x_{r,e,s,t}\), the baseline is \(b=\mathrm{median}\{x_0,x_1,x_2,x_3\}\) and the selected-pulse condition is

\[ \max_t (x_t-b) > 1000\;\mathrm{ADC}. \]

The recomputed total is **640,737**, matching the canonical ticket number: `True`.

The reproduction gate is evaluated before any model is fit. The per-run artifact `raw_root_selected_counts_by_run.csv` contains the selected-pulse count and checksum for each ROOT file.

## Forced/Random Mirror Inventory

Keyword ROOT hits: 0. Dedicated forced/random ROOT found: `False`. The trigger-mode checksum manifest contains 33 B-stack ROOT files and 0 entries with `TRIGGER != 1`; observed trigger summaries are `1:10005; 1:10970; 1:1441; 1:20569; 1:21764; 1:24416; 1:27786; 1:30321; 1:31284; 1:31713; 1:32354; 1:32613; 1:33972; 1:33997; 1:34141; 1:35943; 1:36074; 1:36535; 1:37030; 1:37413; 1:37584; 1:38424; 1:39612; 1:39765; 1:39990; 1:41921; 1:42303; 1:4294; 1:44804; 1:48181; 1:50513; 1:51823; 1:57173`. Because no true no-pulse mirror was found, S16p evaluates the adoption rule on beam pretrigger samples and does not promote the estimator for production baseline replacement.

The manifest file `trigger_mode_manifest.csv` is the checksum-bound ingest artifact requested by the ticket. It records `run`, `path`, `sha256`, `entries`, `trigger_summary`, non-beam-trigger counts, and tag-like branch names. The companion `input_sha256.csv` is a minimal checksum table for downstream provenance checks.

## Methods

Each selected pulse contributes four supervised rows. For target pretrigger sample \(j\in\{0,1,2,3\}\), the target is \(y=x_j\). Let \(O_j=\{0,1,2,3\}\setminus\{j\}\). The strong traditional comparator fits \(x_t=a+b t\) by least squares using only \(t\in O_j\), then predicts \(\hat y_j=a+bj\). Ridge regression minimizes \(\sum_i (y_i-x_i^T\beta)^2+\lambda\|\beta\|_2^2\). Histogram gradient-boosted trees minimize squared error with shallow additive trees. The MLP is a two-hidden-layer tabular regressor. The 1D-CNN receives the 18-sample waveform with the target sample replaced by the traditional estimate. The new `target_masked_residual_cnn` gates convolution channels with scalar covariates before regression, explicitly marking the hidden target location and allowing waveform residual features to be conditionally suppressed or amplified.

For held-out run \(r\), all rows from \(r\) are excluded from training. The primary loss is \(\mathrm{MAE}=n^{-1}\sum_i |\hat y_i-y_i|\). The secondary robust width is \(\sigma_{68}=(Q_{84}-Q_{16})/2\), and the operational tail is \(P(|\hat y-y|>25\,\mathrm{ADC})\). Confidence intervals resample held-out runs with replacement.

No model receives run number, event number, ROOT entry order, or the hidden target sample value as an input. Target leakage is further reduced by replacing the target waveform sample with the traditional estimate before neural-network training.

## Pooled Run-Held-Out Results

|method|family|mean_mae_adc|mae_ci95|mean_sigma68_adc|sigma68_ci95|mean_tail_gt25_adc|tail_gt25_ci95|
|---|---|---|---|---|---|---|---|
|gradient_boosted_trees|ml_nn|42.895|[35.19685384000919, 50.20545242879703]|17.357|[14.439197484972146, 20.30674577144847]|0.22726|[0.18074479166666668, 0.2738185763888889]|
|mlp|ml_nn|72.989|[63.708298189996455, 83.21827186941658]|44.334|[35.718685188913085, 55.133377799358364]|0.50937|[0.4436085069444445, 0.5810295138888888]|
|ridge|ml_nn|149.51|[129.13129019150009, 168.59521121971662]|78.152|[70.12900606935982, 85.47182981959625]|0.76823|[0.7562230902777778, 0.7804713541666666]|
|traditional_line3|traditional|165.4|[122.17816046626984, 195.9594792493386]|18.604|[12.99300297619064, 24.042226190476125]|0.24319|[0.18167274305555556, 0.29377170138888886]|
|target_masked_residual_cnn|new_nn|172.17|[149.85685831154717, 191.4937912818061]|48.405|[38.12537738037109, 59.02500677490234]|0.89847|[0.8386605902777777, 0.9428802083333333]|
|cnn1d|ml_nn|287.16|[224.84957107755872, 347.79299468782216]|51.552|[42.512995880126944, 60.735933837890606]|0.95993|[0.9296935763888888, 0.9840199652777778]|

## Per-Run Results

|run|method|n|mae_adc|sigma68_adc|tail_gt25_adc|bias_adc|
|---|---|---|---|---|---|---|
|58|cnn1d|3600|100.15|26.786|0.97278|61.716|
|58|gradient_boosted_trees|3600|20.626|10.222|0.081111|2.4782|
|58|mlp|3600|47.314|35.068|0.46|8.9406|
|58|ridge|3600|77.68|63.391|0.73583|6.0135|
|58|target_masked_residual_cnn|3600|98.182|29.448|0.95167|-83.09|
|58|traditional_line3|3600|38.514|8.7857|0.068333|-0.83492|
|59|cnn1d|3600|290.13|66.263|0.93778|-147.13|
|59|gradient_boosted_trees|3600|57.108|25.521|0.325|-5.1867|
|59|mlp|3600|89.606|55.721|0.58778|-22.323|
|59|ridge|3600|188.86|92.983|0.7825|-24.519|
|59|target_masked_residual_cnn|3600|180.35|68.755|0.91278|-69.101|
|59|traditional_line3|3600|224.66|37.273|0.33861|-39.592|
|60|cnn1d|3600|415.89|62.026|0.9925|-335.34|
|60|gradient_boosted_trees|3600|45.638|20.729|0.27806|-0.97712|
|60|mlp|3600|98.175|71.447|0.70083|5.9792|
|60|ridge|3600|170.92|93.363|0.78944|-6.2478|
|60|target_masked_residual_cnn|3600|198.1|59.299|0.90083|-71.005|
|60|traditional_line3|3600|206.71|26.833|0.32444|-47.831|
|61|cnn1d|3600|406.72|67.039|0.99111|-318.23|
|61|gradient_boosted_trees|3600|37.309|18.213|0.25167|-1.7718|
|61|mlp|3600|75.091|55.873|0.58861|-6.9273|
|61|ridge|3600|152.25|85.945|0.7775|-13.019|
|61|target_masked_residual_cnn|3600|200.2|54.065|0.96472|71.032|
|61|traditional_line3|3600|170.75|17.67|0.27917|-40.278|
|62|cnn1d|3600|235.56|62.106|0.85444|3.5901|
|62|gradient_boosted_trees|3600|40.437|18.189|0.25778|-0.34515|
|62|mlp|3600|59.886|38.999|0.46722|6.1288|
|62|ridge|3600|154.03|83.657|0.78056|10.903|
|62|target_masked_residual_cnn|3600|158.13|67.559|0.72333|30.921|
|62|traditional_line3|3600|172.52|18.293|0.2825|-39.137|
|63|cnn1d|3600|282.01|42.185|0.96056|-168.55|
|63|gradient_boosted_trees|3600|54.578|17.948|0.24583|-4.1537|
|63|mlp|3600|73.313|32.702|0.43|-1.4586|
|63|ridge|3600|160.28|71.914|0.76361|17.832|
|63|target_masked_residual_cnn|3600|166.02|36.274|0.84583|-60.08|
|63|traditional_line3|3600|179.88|15.197|0.24889|-20.063|
|64|cnn1d|3600|290.05|46.655|0.97389|-140.22|
|64|gradient_boosted_trees|3600|51.146|14.366|0.19889|-0.72751|
|64|mlp|3600|68.869|31.499|0.41333|5.0885|
|64|ridge|3600|156.88|64.111|0.74472|6.0661|
|64|target_masked_residual_cnn|3600|201.3|46.614|0.91611|66.277|
|64|traditional_line3|3600|181.14|13.154|0.20944|-20.784|
|65|cnn1d|3600|276.76|39.356|0.99639|91.086|
|65|gradient_boosted_trees|3600|36.316|13.665|0.17972|0.19773|
|65|mlp|3600|71.658|33.363|0.42722|7.233|
|65|ridge|3600|135.2|69.853|0.77167|10.895|
|65|target_masked_residual_cnn|3600|175.12|25.228|0.9725|67.918|
|65|traditional_line3|3600|149.04|11.627|0.19417|-15.574|

## Systematics and Caveats

- The exact raw ROOT count validates file access and selected-pulse semantics, but it does not by itself supply no-pulse pedestal truth.
- The accessible data tree contains beam-trigger selected-pulse files; keyword inventory did not find a dedicated forced/random no-pulse ROOT mirror.
- The benchmark target is a pretrigger sample hidden from the model. It diagnoses target-excluded imputation skill, not unbiased baseline replacement under true no-pulse acquisition.
- The raw files expose only beam-trigger reduced ROOT in this mirror. Trigger-mode metadata are checksum-pinned, but the physical forced/random acquisition requested by the ticket is not present.
- The traditional line3 method can have low robust width but high MAE when run-level offsets or outliers dominate; the winner is selected by the predeclared run-mean MAE for this imputation benchmark.
- Run-bootstrap intervals use eight held-out runs, so they measure run-to-run variation coarsely and should not be interpreted as asymptotic standard errors.
- Neural-network rankings can vary with initialization; fixed seeds, capped rows per run, and common run splits are used to keep the artifact reproducible.

## Adoption Decision

`result.json` names `gradient_boosted_trees` as the numerical winner. The adoption rule itself is **not adopted for production pedestal replacement** because the required true forced/random mirror is absent. The winning model is therefore a candidate nuisance diagnostic to rerun when no-pulse ROOT is acquired, not a deployed correction.
