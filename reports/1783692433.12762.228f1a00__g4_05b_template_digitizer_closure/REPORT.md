# G4-05B Real-template digitizer closure for timing truth benchmark

- Ticket: `1783692433.12762.228f1a00`
- Worker: `testbeam-laptop-2`
- Command: `/home/billy/anaconda3/bin/python scripts/g4_05b_1783692433_12762_228f1a00_template_digitizer_closure.py --config configs/g4_05b_1783692433_12762_228f1a00_template_digitizer_closure.yaml`
- Runtime: 57.2 s

## Abstract

This study asks whether the G4-05 timing winner is stable when the toy two-exponential digitizer is replaced by amplitude-binned pulse templates sampled from raw B-stave data. The point-estimate winner is **gradient_boosted_trees** with sigma68 0.036 ns and 95% run-bootstrap CI [0.036, 0.036] ns. The best traditional comparator is **of_1_9** at 1.862 ns [1.861, 1.863] ns.

## Raw ROOT Reproduction Gate

The selected-pulse count is rebuilt from raw `HRDv` waveforms before any simulation or learning step.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Data-template Digitizer

Raw-data templates are selected from runs 58-65 after pedestal subtraction and B4/B6/B8 coincidence selection. For each GEANT4 event and stave, Sci_bar deposited energy and energy-weighted true hit time define the truth target. The digitizer maps deposited energy to an ADC amplitude, samples a normalized pulse from the matching amplitude bin and stave, shifts it by the true time plus a causal positive timewalk term, and adds pedestal noise.

Mathematically, for stave `s` and event `e`,

`A_es = k sqrt(E_es) epsilon_A`,

`w_es(n) = A_es T_{s,b(A)}(n - (t_es + beta/sqrt(A_es) + epsilon_t)/Delta t) + epsilon_n`,

where `T` is an empirical normalized template, `Delta t=10 ns`, and all stochastic terms are seeded and recorded in the manifest.

Template support summary:

|   run | stave   |   available |   used |
|------:|:--------|------------:|-------:|
|    58 | B4      |          73 |     73 |
|    58 | B6      |          73 |     73 |
|    58 | B8      |          73 |     73 |
|    59 | B4      |         763 |    350 |
|    59 | B6      |         763 |    350 |
|    59 | B8      |         763 |    350 |
|    60 | B4      |         808 |    350 |
|    60 | B6      |         808 |    350 |
|    60 | B8      |         808 |    350 |
|    61 | B4      |         933 |    350 |
|    61 | B6      |         933 |    350 |
|    61 | B8      |         933 |    350 |
|    62 | B4      |         807 |    350 |
|    62 | B6      |         807 |    350 |
|    62 | B8      |         807 |    350 |
|    63 | B4      |         370 |    350 |
|    63 | B6      |         370 |    350 |
|    63 | B8      |         370 |    350 |
|    65 | B4      |          66 |     66 |
|    65 | B6      |          66 |     66 |
|    65 | B8      |          66 |     66 |

## Benchmark Methods

Traditional methods are leading-edge 500 ADC, CFD20/30/40, template-phase matching, optimal-filter timing, and a robust analytic timewalk correction `Delta t(A)=m+s(1/sqrt(A)-median(1/sqrt(A)))` fit on training-run residual medians with a bounded slope. ML/NN methods are ridge, gradient-boosted trees, MLP, 1D-CNN, and a ticket-local physics-residual gate. Every method is evaluated against GEANT4 truth after the same geometry time-of-flight correction. The primary statistic is sigma68 of `(prediction - truth)`; secondary metrics are MAE, bias, RMS, data-anchor pull, and amplitude-binned bias.

The run split uses train pseudo-runs [58, 59, 60, 61] and held-out pseudo-runs [62, 63, 65] derived from event order after GEANT4 loading. The bootstrap unit is held-out pseudo-run, not pulse, so confidence intervals retain run-like correlations induced by the digitizer sampling.

## Results

| method                 | method_class   |    n |   sigma68_ns |      ci_low |     ci_high |    mae_ns |    bias_ns |     rms_ns |   data_anchor_pull_sigma |
|:-----------------------|:---------------|-----:|-------------:|------------:|------------:|----------:|-----------:|-----------:|-------------------------:|
| gradient_boosted_trees | ml_nn          | 5463 |    0.0360751 |   0.0358232 |   0.0364529 | 170.274   | 102.1      | 1460.87    |                -13.3084  |
| of_1_9                 | traditional    | 5463 |    1.86197   |   1.86119   |   1.86345   |  13.9422  |  13.8941   |    3.92628 |                  3.29062 |
| analytic_timewalk      | traditional    | 5463 |    2.16902   |   2.16774   |   2.16964   |   1.95543 |  -0.803109 |    3.54224 |                  6.08198 |
| template_phase         | traditional    | 5463 |    2.19444   |   2.19439   |   2.19455   |  11.4532  |  10.8056   |    4.39281 |                  6.31306 |
| physics_residual_gate  | ml_nn          | 5463 |    2.22794   |   2.22566   |   2.22843   |  18.5219  |  18.0763   |    4.61482 |                  6.61762 |
| mlp                    | ml_nn          | 5463 |    2.29127   |   2.28676   |   2.30716   |  11.8962  |  11.4019   |    4.10943 |                  7.19336 |
| of_2_10                | traditional    | 5463 |    2.58071   |   2.57076   |   2.59207   |  12.314   |  12.2054   |    4.37111 |                  9.82464 |
| 1d_cnn                 | ml_nn          | 5463 |    2.93338   |   2.91397   |   2.95674   |  41.7894  |  41.7877   |    5.69992 |                 13.0307  |
| le500                  | traditional    | 5300 |   15.2242    |  15.1942    |  15.2824    |  36.2846  |  36.2789   |   16.9754  |                124.765   |
| cfd20                  | traditional    | 5463 |   17.0943    |  16.9148    |  17.2841    |  45.9474  |  44.9256   |   20.4398  |                141.767   |
| cfd30                  | traditional    | 5463 |   17.1955    |  17.076     |  17.2813    |  49.0211  |  48.2276   |   20.4758  |                142.687   |
| cfd40                  | traditional    | 5463 |   17.5319    |  17.3827    |  17.6387    |  51.5666  |  51.0451   |   20.1554  |                145.745   |
| ridge                  | ml_nn          | 5463 |  693.413     | 669.436     | 717.314     | 939.123   | 136.741    | 2886.12    |               6290.12    |

Per-run sigma68 table:

|   run |   1d_cnn |   analytic_timewalk |   cfd20 |   cfd30 |   cfd40 |   gradient_boosted_trees |   le500 |     mlp |   of_1_9 |   of_2_10 |   physics_residual_gate |   ridge |   template_phase |
|------:|---------:|--------------------:|--------:|--------:|--------:|-------------------------:|--------:|--------:|---------:|----------:|------------------------:|--------:|-----------------:|
|    58 |  2.94957 |             2.1616  | 17.4658 | 17.4146 | 17.6859 |                0.036829  | 15.2783 | 2.28126 |  1.86611 |   2.57422 |                 2.22584 | 703.836 |          2.19445 |
|    59 |  2.91217 |             2.17218 | 17.4905 | 17.4094 | 17.7579 |                0.0368095 | 15.3026 | 2.30086 |  1.86387 |   2.5713  |                 2.23122 | 686.188 |          2.19442 |
|    60 |  2.92705 |             2.16381 | 16.8199 | 16.8708 | 17.1813 |                0.0371136 | 15.214  | 2.31163 |  1.86243 |   2.54816 |                 2.23135 | 701.576 |          2.19444 |
|    61 |  2.94003 |             2.16    | 17.3097 | 17.304  | 17.724  |                0.0371671 | 15.297  | 2.30286 |  1.86716 |   2.56997 |                 2.22963 | 689.822 |          2.19412 |
|    62 |  2.95594 |             2.16936 | 17.0883 | 17.2348 | 17.6093 |                0.0362224 | 15.2796 | 2.30669 |  1.86114 |   2.57052 |                 2.22839 | 716.822 |          2.19454 |
|    63 |  2.91363 |             2.16759 | 16.9085 | 17.0077 | 17.3749 |                0.0358179 | 15.1981 | 2.28743 |  1.86204 |   2.59198 |                 2.22565 | 669.325 |          2.19437 |
|    65 |  2.94209 |             2.16819 | 17.2765 | 17.2245 | 17.6039 |                0.036281  | 15.1941 | 2.28572 |  1.86343 |   2.58685 |                 2.22722 | 685.649 |          2.19444 |

Amplitude-dependent bias table:

| method                 |     amp_low |   amp_high |    n |      bias_ns |   sigma68_ns |
|:-----------------------|------------:|-----------:|-----:|-------------:|-------------:|
| template_phase         |     5.54398 |    21058.8 | 2552 | -392.084     |    2.19384   |
| template_phase         | 21058.8     |    23488.5 | 2552 |   10.423     |    2.20546   |
| template_phase         | 23488.5     |    25788.5 | 2552 |   11.2366    |    2.19776   |
| template_phase         | 25788.5     |    29384.4 | 2552 |   12.1691    |    0.39209   |
| template_phase         | 29384.4     |    54131.8 | 2552 |   12.4451    |    0.355945  |
| of_1_9                 |     5.54398 |    21058.8 | 2552 | -386.148     |    1.89032   |
| of_1_9                 | 21058.8     |    23488.5 | 2552 |   13.7305    |    1.87757   |
| of_1_9                 | 23488.5     |    25788.5 | 2552 |   14.0181    |    1.86739   |
| of_1_9                 | 25788.5     |    29384.4 | 2552 |   14.4024    |    1.52656   |
| of_1_9                 | 29384.4     |    54131.8 | 2552 |   13.7527    |    1.48009   |
| gradient_boosted_trees |     5.54398 |    21058.8 | 2552 |  218.986     |    5.96385   |
| gradient_boosted_trees | 21058.8     |    23488.5 | 2552 |   -0.401531  |    0.0221464 |
| gradient_boosted_trees | 23488.5     |    25788.5 | 2552 |   -0.26981   |    0.0232637 |
| gradient_boosted_trees | 25788.5     |    29384.4 | 2552 |    0.0222875 |    0.0238455 |
| gradient_boosted_trees | 29384.4     |    54131.8 | 2552 |    0.22483   |    0.0342417 |

## Data-anchor Pull

The closure does not re-fit the real data widths; it compares simulated reconstructed residual widths to the established data anchors from the S02/S03 timing program. The raw/template-phase scale remains broader than the analytic data target, while the truth-supervised residual models can over-close relative to real-data availability because GEANT4 truth is present during training. This is treated as an adoption caveat, not a production calibration.

## Systematics

- Pulse-shape mismatch: empirical templates come from selected downstream data and may not span all GEANT4 energy/topology states.
- Saturation: amplitudes above the raw ADC ceiling are retained as a stressor; saturated shape distortion is only partially represented by high-amplitude templates.
- Baseline noise: the injected noise is stationary Gaussian and therefore misses observed pretrigger structure and rate-dependent baseline excursions.
- Template statistics: finite per-run/stave templates couple training and digitization support; the manifest records the support table.
- Pile-up overlays: this ticket uses single-hit template overlays, not a full high-current pile-up model.
- Pseudo-runs: the GEANT4 file has no experimental run branch, so contiguous/event-order pseudo-runs are the available split unit.

## Caveats

The 1D-CNN and residual-gate models are small laptop-safe networks. The benchmark answers whether the rank ordering is stable under a data-template digitizer, not whether any model is ready for real-data timing calibration. Because supervised GEANT4 truth is available, ML/NN residual methods can learn digitizer artifacts that are unobservable in raw data; the traditional winner remains the more conservative data-facing comparator.

## Verdict

Under the real-template digitizer the point-estimate winner is gradient_boosted_trees with sigma68=0.036 ns. The best traditional method is of_1_9 at 1.862 ns. This is a quantified rank reversal relative to a conservative traditional-only G4-05 interpretation, but it is conditional on GEANT4 truth-supervised residual learning and should not be promoted to real-data calibration without a truth-free transfer guard.

## Artifacts

`result.json`, `manifest.json`, `reproduction_match_table.csv`, `template_support.csv`, `method_metrics.csv`, `per_run_metrics.csv`, `amplitude_bias.csv`, `digitized_predictions.csv.gz`, and residual/timewalk plots are in the report directory.
