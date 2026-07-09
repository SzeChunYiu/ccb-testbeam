# S16p Target-Excluded Pedestal Adoption Rule

- **Ticket:** `1781135617.950.4da27974`
- **Worker:** `testbeam-laptop-2`
- **Runtime:** 118.5 s
- **Raw ROOT anchor:** 640,737 selected B-stack pulses; expected 640,737; delta 0.
- **Winner:** `gradient_boosted_trees` with run-mean MAE 42.646 ADC and 95% run-bootstrap CI [35.003, 50.039].

## Abstract

S16p tests whether the target-excluded pretrigger pedestal estimator can be adopted if a true forced/random B-stack no-pulse mirror has been acquired. The raw-data gate is an exact recount of selected B-stack pulses from `h101/HRDv`. The benchmark then uses real selected-pulse waveforms from held-out runs to predict each pretrigger sample from the other three samples and pulse-shape covariates. This is a surrogate for the desired no-pulse truth test; the acquisition inventory found no dedicated forced/random ROOT mirror in the accessible data tree, so the adoption decision is conservative.

## Raw ROOT Reproduction

For run \(r\), stave \(s\), and waveform sample vector \(x_{r,e,s,t}\), the baseline is \(b=\mathrm{median}\{x_0,x_1,x_2,x_3\}\) and the selected-pulse condition is

\[ \max_t (x_t-b) > 1000\;\mathrm{ADC}. \]

The recomputed total is **640,737**, matching the canonical ticket number: `True`.

## Forced/Random Mirror Inventory

Keyword ROOT hits: 0. Dedicated forced/random ROOT found: `False`. Because no true no-pulse mirror was found, S16p evaluates the adoption rule on beam pretrigger samples and does not promote the estimator for production baseline replacement.

## Methods

Each selected pulse contributes four supervised rows. For target pretrigger sample \(j\in\{0,1,2,3\}\), the target is \(y=x_j\). The traditional comparator is the three-point least-squares line extrapolation/interpolation \(\hat y_j=a+bj\) fitted only on the other three pretrigger samples. ML/NN methods receive the same scalar covariates: target index, stave index, amplitude, peak sample, pretrigger RMS/range, late integral, late maximum, and three-sample summaries. The 1D-CNN also sees the 18-sample waveform with the target sample replaced by the traditional estimate. The new `target_masked_residual_cnn` gates convolution channels with scalar covariates before regression.

For held-out run \(r\), all rows from \(r\) are excluded from training. The primary loss is \(\mathrm{MAE}=n^{-1}\sum_i |\hat y_i-y_i|\). The secondary robust width is \(\sigma_{68}=(Q_{84}-Q_{16})/2\), and the operational tail is \(P(|\hat y-y|>25\,\mathrm{ADC})\). Confidence intervals resample held-out runs with replacement.

## Pooled Run-Held-Out Results

|method|family|mean_mae_adc|mae_ci95|mean_sigma68_adc|sigma68_ci95|mean_tail_gt25_adc|tail_gt25_ci95|
|---|---|---|---|---|---|---|---|
|gradient_boosted_trees|ml_nn|42.646|[35.002944067924716, 50.03867502839424]|17.361|[14.387237221204048, 20.19870965646437]|0.22865|[0.17956510416666666, 0.2670486111111111]|
|mlp|ml_nn|80.455|[70.47795897165918, 90.71984970713392]|49.006|[40.885561565165574, 56.558696285287695]|0.55604|[0.4805902777777778, 0.6147951388888888]|
|ridge|ml_nn|149.51|[127.2186713529508, 169.1333037532649]|78.152|[69.8624992956459, 85.7081362381532]|0.76823|[0.7559869791666666, 0.7777960069444444]|
|traditional_line3|traditional|165.4|[120.21921750992064, 193.79240079365078]|18.604|[13.364842261904824, 25.353101190476135]|0.24319|[0.1798255208333333, 0.29346093749999996]|
|target_masked_residual_cnn|new_nn|178.2|[139.85112458377415, 213.13516699642605]|43.939|[33.87886761474609, 56.05051181030271]|0.80878|[0.6699001736111111, 0.9313854166666666]|
|cnn1d|ml_nn|313.49|[261.32545927259656, 371.6671376813253]|54.307|[43.8128881225586, 66.25164819335936]|0.94281|[0.8721328125, 0.9901875]|

## Per-Run Results

|run|method|n|mae_adc|sigma68_adc|tail_gt25_adc|bias_adc|
|---|---|---|---|---|---|---|
|58|cnn1d|3600|264.83|29.48|0.99611|-250.33|
|58|gradient_boosted_trees|3600|20.264|10.731|0.090556|3.4854|
|58|mlp|3600|51.333|38.097|0.52778|18.838|
|58|ridge|3600|77.68|63.391|0.73583|6.0135|
|58|target_masked_residual_cnn|3600|86.583|28.291|0.96083|-68.643|
|58|traditional_line3|3600|38.514|8.7857|0.068333|-0.83492|
|59|cnn1d|3600|435.35|68.749|0.99583|217.42|
|59|gradient_boosted_trees|3600|57.6|24.978|0.32167|-6.9428|
|59|mlp|3600|106.3|64.505|0.65194|-0.7926|
|59|ridge|3600|188.86|92.983|0.7825|-24.519|
|59|target_masked_residual_cnn|3600|240.17|70.95|0.95833|-93.453|
|59|traditional_line3|3600|224.66|37.273|0.33861|-39.592|
|60|cnn1d|3600|410.03|75.474|0.99028|-318.16|
|60|gradient_boosted_trees|3600|43.353|20.994|0.2825|-0.85469|
|60|mlp|3600|70.657|49.691|0.48917|-2.9307|
|60|ridge|3600|170.92|93.363|0.78944|-6.2478|
|60|target_masked_residual_cnn|3600|180.79|58.8|0.525|-28.752|
|60|traditional_line3|3600|206.71|26.833|0.32444|-47.831|
|61|cnn1d|3600|214.17|49.612|0.77944|-19.138|
|61|gradient_boosted_trees|3600|38.382|18.342|0.26278|-1.6662|
|61|mlp|3600|81.94|57.833|0.63806|-12.21|
|61|ridge|3600|152.25|85.945|0.7775|-13.019|
|61|target_masked_residual_cnn|3600|160.3|52.059|0.73333|-53.327|
|61|traditional_line3|3600|170.75|17.67|0.27917|-40.278|
|62|cnn1d|3600|228.15|56.932|0.82861|-11.754|
|62|gradient_boosted_trees|3600|38.799|18.04|0.25278|-1.6441|
|62|mlp|3600|79.204|58.086|0.65028|0.66376|
|62|ridge|3600|154.03|83.657|0.78056|10.903|
|62|target_masked_residual_cnn|3600|257.46|54.342|0.98694|-168.48|
|62|traditional_line3|3600|172.52|18.293|0.2825|-39.137|
|63|cnn1d|3600|310.64|73.103|0.97694|-149.21|
|63|gradient_boosted_trees|3600|53.781|17.103|0.24083|-4.7349|
|63|mlp|3600|95.236|52.795|0.61333|17.46|
|63|ridge|3600|160.28|71.914|0.76361|17.832|
|63|target_masked_residual_cnn|3600|143.29|28.098|0.8525|42.674|
|63|traditional_line3|3600|179.88|15.197|0.24889|-20.063|
|64|cnn1d|3600|372.18|39.473|0.98917|-266.55|
|64|gradient_boosted_trees|3600|51.264|14.36|0.19139|2.2744|
|64|mlp|3600|72.975|26.04|0.33722|18.888|
|64|ridge|3600|156.88|64.111|0.74472|6.0661|
|64|target_masked_residual_cnn|3600|155.33|24.758|0.46361|-25.002|
|64|traditional_line3|3600|181.14|13.154|0.20944|-20.784|
|65|cnn1d|3600|272.54|41.637|0.98611|-170.55|
|65|gradient_boosted_trees|3600|37.722|14.341|0.18667|0.33162|
|65|mlp|3600|85.993|45.004|0.54056|-1.394|
|65|ridge|3600|135.2|69.853|0.77167|10.895|
|65|target_masked_residual_cnn|3600|201.66|34.214|0.98972|-109.93|
|65|traditional_line3|3600|149.04|11.627|0.19417|-15.574|

## Systematics and Caveats

- The exact raw ROOT count validates file access and selected-pulse semantics, but it does not by itself supply no-pulse pedestal truth.
- The accessible data tree contains beam-trigger selected-pulse files; keyword inventory did not find a dedicated forced/random no-pulse ROOT mirror.
- The benchmark target is a pretrigger sample hidden from the model. It diagnoses target-excluded imputation skill, not unbiased baseline replacement under true no-pulse acquisition.
- Run-bootstrap intervals use eight held-out runs, so they measure run-to-run variation coarsely and should not be interpreted as asymptotic standard errors.
- Neural-network rankings can vary with initialization; fixed seeds, capped rows per run, and common run splits are used to keep the artifact reproducible.

## Adoption Decision

`result.json` names `gradient_boosted_trees` as the numerical winner. The adoption rule itself is **not adopted for production pedestal replacement** because the required true forced/random mirror is absent. The winning model is therefore a candidate nuisance diagnostic to rerun when no-pulse ROOT is acquired, not a deployed correction.
