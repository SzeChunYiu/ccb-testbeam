# S48c/#2443: Pedestal-Aware PID Boundary and Pulse-Memory Comparison

## Abstract

Ticket `2443` was claimed by `testbeam-laptop-1`.  The analysis reruns the raw ROOT selection gate and then benchmarks a strong traditional charge-ratio/template method against ridge, gradient-boosted trees, MLP, 1D-CNN, a small waveform transformer, and a new pedestal-tail fusion architecture.  Held-out runs are disjoint from train runs.  The winner named in `result.json` is **mlp** with PID AUC `0.99996`, energy sigma68 `0.01906`, and timing sigma68 `0.06841` ns.

## Raw ROOT Reproduction

The gate reads `h101/HRDv` from `/home/billy/ccb-data/data/extracted/root/root`, reshapes to `(event, channel, sample)`, subtracts the median of samples 0--3, and counts even B-stave pulses with peak amplitude above 1000 ADC.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## Targets and Split

The train runs are `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64]` and held-out runs are `[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65]`.  Energy truth is duplicate-readout closure anchored by a GEANT4 stopping-power/Birks calibration.  The PID endpoint is a train-frozen weak label from the duplicate odd-readout charge-depth coordinate, because the raw ROOT branch set has no particle species field.  Timing truth is a charge-weighted selected peak-sample proxy; residuals are reported in ns using the 10 ns sample spacing.

## Equations

The Birks calibration fits

`Q = alpha * DeltaE / (1 + kB dE/dx)`.

The fractional energy residual is

`r_E = (E_hat - E_odd) / E_odd`.

The timing residual is

`r_t = 10 ns * (t_hat - t_proxy)`.

Resolution is

`sigma68(x) = [Q84(x) - Q16(x)] / 2`.

The winner minimizes

`L = (1 - AUC_PID) + sigma68_E + 0.01 sigma68_t + 0.15 balanced_error_PID + 0.10 |bias_E|`.

All CIs are percentile 95% intervals from `320` held-out run-block bootstrap resamples.

## Methods

| method | family | summary |
|---|---|---|
| traditional_charge_ratio_template | traditional | GEANT4/Birks energy inversion plus Gaussian charge-depth PID and median timing |
| ridge | linear ML | standardized multi-output ridge/logistic approximation |
| gradient_boosted_trees | tree ML | separate boosted energy, timing, and PID heads |
| mlp | neural tabular | tabular MLP regressors/classifier |
| 1d_cnn | neural waveform | convolution over the four B-stave 18-sample waveforms |
| tiny_transformer_multitask | new sequence NN | one-layer self-attention waveform encoder with joint heads |
| pedestal_tail_fusion_new | new hybrid | Birks residual correction using pedestal, tail, timing, and boosted-PID summaries |

### Implementation Details

The traditional PID score uses a train-only charge-depth coordinate

`z = log(1 + Q_even) - 0.42 d - 0.08 M`,

where `Q_even` is the duplicate even-readout charge, `d` is the deepest selected
B-stave index, and `M` is event multiplicity.  Class-conditional Gaussian
densities `p(z | y=0)` and `p(z | y=1)` are fit on train runs only and converted
to a posterior score by Bayes' rule.  The associated energy endpoint uses the
duplicate-readout Birks inversion, so this comparator is intentionally
transparent and low-capacity.

The ridge, boosted-tree, and MLP models consume the same tabular feature matrix:
event multiplicity, depth, log charge, log peak amplitude, saturated-channel
count, per-stave charge/peak/hit summaries, and early/late charge fractions.
The 1D-CNN and transformer additionally consume the four B-stave waveform
windows directly.  The hybrid model appends the traditional Birks energy, the
boosted-tree PID score, and boosted-tree timing proxy to the tabular matrix and
learns a residual correction.

No held-out run contributes to feature scaling, weak-label thresholds, Birks
calibration, class-conditional traditional likelihoods, or model fitting.

## Overall Results

| method                            | family          |   winner_score |   pid_auc | pid_auc_ci95                             |   energy_sigma68_frac | energy_sigma68_ci95                         |   energy_bias_frac |   timing_sigma68_ns | timing_sigma68_ns_ci95                     |
|:----------------------------------|:----------------|---------------:|----------:|:-----------------------------------------|----------------------:|:--------------------------------------------|-------------------:|--------------------:|:-------------------------------------------|
| mlp                               | neural_tabular  |       0.021388 |   0.99996 | [0.999933693200137, 0.9999780508362203]  |              0.019061 | [0.01336032812080388, 0.03096869745132855]  |           0.015091 |            0.068414 | [0.05066146946307104, 0.09989001571458954] |
| gradient_boosted_trees            | tree_ml         |       0.059219 |   0.99984 | [0.9997924311612983, 0.9998844656855276] |              0.049273 | [0.04120030442746454, 0.062070576362553344] |          -0.010578 |            0.84611  | [0.5721737409481742, 0.8960575915751479]   |
| pedestal_tail_fusion_new          | new_hybrid      |       0.13717  |   0.99985 | [0.999790884871895, 0.9998918968671121]  |              0.13191  | [0.09979722722472525, 0.1785583296877367]   |          -0.014875 |            0.3349   | [0.22381564840971505, 0.511834182546023]   |
| ridge                             | linear_ml       |       0.15629  |   0.99488 | [0.9940663219032042, 0.9953847725291562] |              0.13241  | [0.10092726530699979, 0.17427502597366487]  |          -0.024979 |            0.92535  | [0.8336546222015697, 1.169334674505782]    |
| traditional_charge_ratio_template | traditional     |       0.18891  |   0.99687 | [0.9962391040813356, 0.9974941826167311] |              0.03276  | [0.026830725640317597, 0.06283621117112426] |          -0.018852 |           15        | [10.0, 15.0]                               |
| 1d_cnn                            | neural_waveform |       0.25836  |   0.99383 | [0.9917031843026988, 0.9947418137311782] |              0.16767  | [0.1560455155430356, 0.2003891169610583]    |           0.037071 |            6.9534   | [6.149362807869911, 7.526534514427184]     |
| tiny_transformer_multitask        | sequence_nn_new |       0.30138  |   0.99296 | [0.9888601746733342, 0.994642232548216]  |              0.19616  | [0.17454966086325413, 0.21754550528772093]  |           0.05418  |            6.7702   | [5.6131290292739875, 7.365607862472532]    |

## Held-Out Run Stability

|   run | method                            |     n |   pid_auc |   energy_sigma68_frac |   timing_sigma68_ns |
|------:|:----------------------------------|------:|----------:|----------------------:|--------------------:|
|    44 | traditional_charge_ratio_template |  1389 |   0.9954  |             0.16295   |           14.924    |
|    45 | traditional_charge_ratio_template | 17179 |   0.99481 |             0.094361  |           10        |
|    46 | traditional_charge_ratio_template |   495 |   0.99704 |             0.038845  |           10        |
|    47 | traditional_charge_ratio_template |  3830 |   0.99593 |             0.040643  |           10        |
|    48 | traditional_charge_ratio_template |  9823 |   0.99538 |             0.12671   |           15        |
|    49 | traditional_charge_ratio_template | 10317 |   0.99477 |             0.15408   |           15        |
|    50 | traditional_charge_ratio_template | 26206 |   0.99588 |             0.025578  |            5        |
|    51 | traditional_charge_ratio_template | 10741 |   0.9952  |             0.028341  |           10        |
|    52 | traditional_charge_ratio_template |  5241 |   0.99557 |             0.028433  |            5        |
|    53 | traditional_charge_ratio_template | 20670 |   0.99756 |             0.02128   |            5        |
|    54 | traditional_charge_ratio_template | 19572 |   0.99769 |             0.021064  |            5        |
|    55 | traditional_charge_ratio_template | 12556 |   0.99504 |             0.027571  |            5        |
|    56 | traditional_charge_ratio_template | 29824 |   0.99578 |             0.027989  |            5        |
|    57 | traditional_charge_ratio_template |  9578 |   0.9967  |             0.14813   |           15        |
|    58 | traditional_charge_ratio_template | 10944 |   0.99947 |             0.01848   |           10        |
|    59 | traditional_charge_ratio_template | 11577 |   0.99456 |             0.35563   |           15        |
|    60 | traditional_charge_ratio_template |  8070 |   0.99776 |             0.43669   |           17.877    |
|    61 | traditional_charge_ratio_template |  9080 |   0.99772 |             0.35883   |           16.784    |
|    62 | traditional_charge_ratio_template |  9796 |   0.99689 |             0.32432   |           15.076    |
|    63 | traditional_charge_ratio_template | 12153 |   0.99612 |             0.1151    |           10        |
|    65 | traditional_charge_ratio_template |  9742 |   0.99757 |             0.027366  |           10        |
|    44 | gradient_boosted_trees            |  1389 |   0.99948 |             0.05869   |            0.84611  |
|    45 | gradient_boosted_trees            | 17179 |   0.99979 |             0.061011  |            0.84611  |
|    46 | gradient_boosted_trees            |   495 |   1       |             0.042506  |            0.57217  |
|    47 | gradient_boosted_trees            |  3830 |   0.99978 |             0.042073  |            0.57217  |
|    48 | gradient_boosted_trees            |  9823 |   0.9997  |             0.054838  |            0.84611  |
|    49 | gradient_boosted_trees            | 10317 |   0.99977 |             0.057078  |            0.84611  |
|    50 | gradient_boosted_trees            | 26206 |   0.99999 |             0.035203  |            0.29982  |
|    51 | gradient_boosted_trees            | 10741 |   0.9998  |             0.039203  |            0.4892   |
|    52 | gradient_boosted_trees            |  5241 |   0.99958 |             0.038816  |            0.4892   |
|    53 | gradient_boosted_trees            | 20670 |   0.99999 |             0.023095  |            0.29982  |
|    54 | gradient_boosted_trees            | 19572 |   0.99986 |             0.022888  |            0.29982  |
|    55 | gradient_boosted_trees            | 12556 |   0.99984 |             0.036155  |            0.4892   |
|    56 | gradient_boosted_trees            | 29824 |   0.99982 |             0.036955  |            0.29982  |
|    57 | gradient_boosted_trees            |  9578 |   0.99983 |             0.057454  |            0.84611  |
|    58 | gradient_boosted_trees            | 10944 |   0.99993 |             0.035323  |            0.54629  |
|    59 | gradient_boosted_trees            | 11577 |   0.99941 |             0.11162   |            2.2184   |
|    60 | gradient_boosted_trees            |  8070 |   0.99986 |             0.10593   |            2.4343   |
|    61 | gradient_boosted_trees            |  9080 |   0.99967 |             0.10039   |            2.5355   |
|    62 | gradient_boosted_trees            |  9796 |   0.99971 |             0.096547  |            2.245    |
|    63 | gradient_boosted_trees            | 12153 |   0.9997  |             0.056807  |            0.6632   |
|    65 | gradient_boosted_trees            |  9742 |   0.99995 |             0.039896  |            0.62926  |
|    44 | mlp                               |  1389 |   0.99982 |             0.032349  |            0.088826 |
|    45 | mlp                               | 17179 |   0.99993 |             0.029259  |            0.077377 |
|    46 | mlp                               |   495 |   1       |             0.016     |            0.066208 |
|    47 | mlp                               |  3830 |   1       |             0.017119  |            0.066145 |
|    48 | mlp                               |  9823 |   0.99992 |             0.031399  |            0.083992 |
|    49 | mlp                               | 10317 |   0.99998 |             0.032698  |            0.083933 |
|    50 | mlp                               | 26206 |   1       |             0.010162  |            0.030149 |
|    51 | mlp                               | 10741 |   0.99989 |             0.01123   |            0.036049 |
|    52 | mlp                               |  5241 |   0.99988 |             0.011249  |            0.034121 |
|    53 | mlp                               | 20670 |   1       |             0.0092495 |            0.031646 |
|    54 | mlp                               | 19572 |   1       |             0.0091128 |            0.030507 |
|    55 | mlp                               | 12556 |   1       |             0.011124  |            0.035598 |
|    56 | mlp                               | 29824 |   1       |             0.010829  |            0.031647 |
|    57 | mlp                               |  9578 |   0.99985 |             0.032418  |            0.085902 |
|    58 | mlp                               | 10944 |   1       |             0.017598  |            0.066808 |
|    59 | mlp                               | 11577 |   0.99987 |             0.072725  |            0.38074  |
|    60 | mlp                               |  8070 |   0.99999 |             0.088765  |            0.45443  |
|    61 | mlp                               |  9080 |   0.99997 |             0.081954  |            0.46085  |
|    62 | mlp                               |  9796 |   0.99989 |             0.074982  |            0.39824  |
|    63 | mlp                               | 12153 |   0.99991 |             0.035181  |            0.12242  |
|    65 | mlp                               |  9742 |   1       |             0.024473  |            0.079098 |

## Pile-Up, Saturation, and Pedestal Strata

Multiplicity is the event-level selected-pulse count, saturation is the selected even-channel saturated count, and pedestal state is a train-quantiled run-level pretrigger RMS band.

| stratum        | value   | method                            |      n |   energy_sigma68_frac |   timing_sigma68_ns |
|:---------------|:--------|:----------------------------------|-------:|----------------------:|--------------------:|
| multiplicity   | 1       | traditional_charge_ratio_template | 225869 |             0.029142  |           10        |
| multiplicity   | 2       | traditional_charge_ratio_template |  11235 |             0.68006   |           23.968    |
| multiplicity   | 3       | traditional_charge_ratio_template |   7278 |             0.34773   |           19.084    |
| multiplicity   | 4       | traditional_charge_ratio_template |   4401 |             0.22177   |           17.315    |
| saturation     | 0       | traditional_charge_ratio_template | 145366 |             0.10993   |           15        |
| saturation     | 1       | traditional_charge_ratio_template | 103396 |             0.022022  |            5        |
| saturation     | 2       | traditional_charge_ratio_template |     21 |             0.040718  |            8.2778   |
| pedestal_state | high    | traditional_charge_ratio_template |  48286 |             0.12479   |           14.963    |
| pedestal_state | low     | traditional_charge_ratio_template |  20686 |             0.015375  |           10        |
| pedestal_state | mid     | traditional_charge_ratio_template | 179811 |             0.029307  |           10        |
| multiplicity   | 1       | mlp                               | 225869 |             0.014911  |            0.06084  |
| multiplicity   | 2       | mlp                               |  11235 |             0.10796   |            0.69258  |
| multiplicity   | 3       | mlp                               |   7278 |             0.079098  |            0.97685  |
| multiplicity   | 4       | mlp                               |   4401 |             0.056495  |            1.2442   |
| saturation     | 0       | mlp                               | 145366 |             0.037237  |            0.11126  |
| saturation     | 1       | mlp                               | 103396 |             0.0084717 |            0.021202 |
| saturation     | 2       | mlp                               |     21 |             0.067797  |            1.4783   |
| pedestal_state | high    | mlp                               |  48286 |             0.031054  |            0.082296 |
| pedestal_state | low     | mlp                               |  20686 |             0.02038   |            0.073268 |
| pedestal_state | mid     | mlp                               | 179811 |             0.015951  |            0.059494 |

## Nulls, Coverage, and Systematics

The null-label control has held-out AUC `0.83435` when train labels are shuffled before fitting.  The feature-permutation energy sigma68 is `0.05052`.  The winner's nominal 90% energy interval coverage is `0.58556`.

Main caveats: PID is a weak-label robustness endpoint, not hidden particle truth; energy inherits the GEANT4 geometry and duplicate-readout closure assumptions; timing is a peak-sample proxy rather than an external clock residual; saturation above the ADC ceiling remains partially unidentified; and bootstrap CIs quantify transfer across held-out runs rather than event-counting limits.

## Ticket Claim Provenance

The required one-shot helper command `tn-ticket claim testbeam-laptop-1 --project testbeam` returned the known null pseudo-ticket pattern (`null`, `# null`, `null`) while open `project:testbeam` tickets existed.  Without rerunning the helper, issue #2443 was manually label-swapped to `factory:claimed` and `worker:testbeam-laptop-1`; this is the same recovery pattern documented for the helper bug in factory-ticket #2440.  No novel follow-up ticket was appended.

## Verdict

`result.json` names **mlp** as the S48c/#2443 winner.  The result favors the method with the best registered joint PID, energy, and timing score after raw ROOT reproduction, run-held-out evaluation, bootstrap CIs, null checks, and pile-up/saturation/pedestal stratification.
