# G4-04 Detector-response tuning

- **Ticket:** `1781212364.2054485.44255c27`
- **Worker:** `testbeam-laptop-2`
- **Question:** What detector-response parameters make GEANT4-derived response observables match raw HRD B-stack data before downstream truth use?

## Abstract

I reproduced the registered B-stave selected-pulse count directly from raw HRD ROOT files and then evaluated detector-response tuning methods on a strict run-held-out split. The raw gate gives 640,737 selected pulses, matching the expected count exactly. The benchmark compares a transparent traditional response scan, a GP/BO surrogate over the same response-card parameters, ridge regression, gradient-boosted trees, a multilayer perceptron, a 1D-CNN proxy, and a new residual-response forest. The best held-out method is `response_residual_forest`, with aggregate score 0.5825 and run-bootstrap 95% CI [0.5489, 0.6149]. Relative to the traditional response-card baseline, this is a 42.6% reduction, below the ticket's 50% success threshold; the result is therefore a useful response-card diagnostic rather than a full gate clearance for downstream truth-dependent G4 studies.

## Inputs and provenance

| input | role | checksum or count |
| --- | --- | --- |
| `data/root/root/hrdb_run_*.root` | raw HRD waveform reproduction | 33 analysis/calibration runs used |
| `reports/1781028640.1299.266407ae/s00_selected_b_pulses.csv.gz` | materialized selected-pulse table after raw-count audit | SHA256 `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f` |
| `reports/1781088387.1790.33b946cb__s14h_g4_energy_calibration_benchmark/result.json` | GEANT4 layer priors and previous calibration anchor | SHA256 `00561273fa72bf3d0131fe3535e689c8f9acd6ddfbd7e5d04128898d5949b652` |

The run split is by entire acquisition run, not by pulse. Training runs are 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, and 64. Held-out runs are 44 through 65 excluding no runs in that range except the naturally absent analysis run 66; concretely: 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, and 65.

## Raw ROOT reproduction

The selected-pulse gate was recomputed from `HRDv` in each raw ROOT file. For each event, `HRDv` is reshaped into 8 channels by 18 samples. The B-stave channels are B2, B4, B6, and B8 mapped to channels 0, 2, 4, and 6. For channel \(c\), the pedestal is

\[
b_c = \mathrm{median}(x_{c,0},x_{c,1},x_{c,2},x_{c,3}),
\]

and the pulse amplitude is

\[
A_c = \max_{0 \le t < 18} x_{c,t} - b_c.
\]

A pulse is selected when \(A_c > 1000\) ADC. The reproduction is deliberately simple and does not depend on the materialized CSV.

| quantity | value |
| --- | ---: |
| expected selected pulses | 640737 |
| reproduced selected pulses | 640737 |
| delta | 0 |
| raw reproduction status | pass |

The per-run counts are written to `raw_reproduction_counts_by_run.csv`; their sum is the table value above.

## Response model

The response-card methods map GEANT4 stave priors to predicted pulse-height distributions. For stave \(s\), layer index \(L_s\), deposited-energy prior \(E_s\), and stopping-power proxy \((dE/dx)_s\), a response parameter vector

\[
\theta = (k_B, m, g, \ell, a, \sigma)
\]

acts through

\[
R_s(\theta)=a\ell \,
\frac{\exp[-0.055(m-1)L_s]\,[1+0.045(g-1)(L_s-\bar L)]}
{1+k_B(dE/dx)_s}.
\]

The pulse-height calibration constant is fit only on training runs:

\[
\alpha_A = \mathrm{median}_{i \in train}\left(A_i/E_{s(i)}\right) = 303.789\ \mathrm{ADC/MeV}.
\]

The response prediction is then

\[
\hat A_i=\alpha_A E_{s(i)}R_{s(i)}(\theta)\,\epsilon_i(\sigma),
\]

where \(\epsilon_i\) is a deterministic event-number, peak-sample, and baseline-dependent smearing proxy. The held-out observed amplitude is never multiplied into the simulator prediction. This is the key leakage control separating this final result from the initial scratch benchmark.

## Methods

`traditional_response_scan` is a one-dimensional gain scan plus a grid over Birks \(k_B\), material scale, light-yield scale, and smearing. It is intentionally interpretable and forms the traditional baseline.

`gp_bo_surrogate_response` fits a Gaussian-process regressor with a Matern kernel to the response-card grid scores, then chooses the lowest surrogate-scored candidate from the same candidate family. It is a surrogate optimizer over response parameters, not a separate hidden simulator.

`ridge` predicts \(\log A\) from stave index, peak sample, baseline ADC, GEANT4 expected energy, \(dE/dx\), and truth hit fraction with standardized linear ridge regression.

`gradient_boosted_trees` uses histogram gradient-boosted regression on the same non-leaking features.

`mlp` uses a two-hidden-layer neural regressor on standardized features.

`1d_cnn_proxy` is a compact neural proxy for a stave-ordered 1D convolutional response learner. The available table does not contain full 18-sample waveforms, so the proxy uses ordered per-pulse scalar waveform summaries rather than raw waveform tensors.

`response_residual_forest` is the new architecture. It learns residual detector-response deformations after GEANT4 prior features are present in the feature vector, using a random-forest ensemble with large leaves to suppress pulse-level memorization.

The ML feature set explicitly excludes `amplitude_adc`, `log_amp`, `area_adc_samples`, and `log_area`. The target remains \(\log A\), and held-out scoring is done on reconstructed amplitudes \(\exp(\hat y)\).

## Scoring and uncertainty

For each held-out run \(r\), stave \(s\), data distribution \(D_{rs}\), and method prediction distribution \(M_{rs}\), the bin score is

\[
S_{rs}=D_{KS}(D_{rs},M_{rs})+
\frac{W_1(D_{rs},M_{rs})}{\mathrm{median}(D_{rs})}
+0.5\left|\frac{\mathrm{median}(M_{rs})-\mathrm{median}(D_{rs})}{\mathrm{median}(D_{rs})}\right|.
\]

The method score is the mean of \(S_{rs}\) over held-out run/stave bins. Confidence intervals resample held-out runs with replacement, preserving all stave-bin correlations within a sampled run:

\[
\widehat S^*_b = \frac{1}{|R|}\sum_{r \in R^*_b}\frac{1}{|S_r|}\sum_s S_{rs}.
\]

The reported interval is the 2.5th to 97.5th percentile over 2000 bootstrap replicates.

## Results

| method | score | score_ci95_low | score_ci95_high | KS | Wasserstein/median | median abs frac error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| response_residual_forest | 0.5825 | 0.5489 | 0.6149 | 0.3376 | 0.1971 | 0.0956 |
| ridge | 0.5879 | 0.5348 | 0.6469 | 0.3256 | 0.1909 | 0.1426 |
| gradient_boosted_trees | 0.5940 | 0.5612 | 0.6262 | 0.3458 | 0.2002 | 0.0960 |
| mlp | 0.5978 | 0.5676 | 0.6272 | 0.3452 | 0.2017 | 0.1019 |
| 1d_cnn_proxy | 0.6960 | 0.6597 | 0.7373 | 0.4239 | 0.2235 | 0.0970 |
| gp_bo_surrogate_response | 1.0144 | 0.9541 | 1.0726 | 0.5595 | 0.3431 | 0.2237 |
| traditional_response_scan | 1.0144 | 0.9541 | 1.0726 | 0.5595 | 0.3431 | 0.2237 |

The ranking is stable enough to identify the residual forest as the numerical winner, but the ridge CI overlaps it. The result should be interpreted as evidence that flexible residual response corrections help, not as evidence that the forest architecture is uniquely optimal.

## Tuned response card

Because the winning method is an ML residual mapper rather than a pure response-card scan, the exported response card records the best traditional card that anchors the residual result. The winner named in `result.json` remains the ML benchmark winner.

| parameter | value |
| --- | ---: |
| birks_kB_cm_per_MeV | 0 |
| material_scale | 1 |
| geometry_scale | 1 |
| light_yield_scale | 1 |
| adc_gain_scale | 0.6 |
| smear_frac | 0.12 |

The same parameters are exported in `tuned_params.json`.

## Systematics

The dominant systematic is the degeneracy between Birks quenching and light yield. In the response equation, increasing \(k_B\) suppresses \(R_s\), while increasing \(\ell\) or \(a\) restores the median scale. With only four B-stave amplitude distributions, the card is not a unique material measurement.

Material and geometry scales are effective response parameters, not survey-grade detector edits. They absorb optical collection, imperfect GEANT4 layer priors, and unmodeled stave-dependent readout effects.

The ML methods score on scalar pulse summaries from the S00 table, not on raw waveform tensors. The 1D-CNN entry is therefore a proxy architecture, and a true waveform CNN remains a future extension.

The bootstrap resamples runs, but all runs still come from the same campaign and reconstruction chain. It probes run-to-run stability within this dataset, not long-term detector aging, trigger-threshold drift, or independent beamline conditions.

The response-card scan remains coarse. The GP/BO surrogate selects from this scanned candidate family, so it cannot discover response regions absent from the grid.

## Caveats and gate interpretation

The traditional response-card baseline score is 1.0144. The winning score is 0.5825, corresponding to a 42.6% reduction. The claimed ticket's success threshold was at least 50% reduction without breaking other observables, so this pass does not clear the detector-response gate. It does, however, provide a documented response card, a leakage-controlled benchmark, and concrete evidence that residual response learning improves over the transparent scan.

Downstream G4-02/G4-03/G4-05 truth use should cite the exported card and preserve this caveat: the present tuning improves amplitude-distribution agreement but does not validate event-level waveforms, PID truth labels, timing, optical transport, or trigger efficiency.

## Reproducibility artifacts

| artifact | contents |
| --- | --- |
| `result.json` | top-level winner, raw-count pass, run split, checksums, success flag |
| `tuned_params.json` | exported response-card parameters |
| `method_summary.csv` | method scores and run-bootstrap CIs |
| `method_per_run_scores.csv` | per-run aggregate scores for bootstrap audit |
| `method_bins_by_run_stave.csv` | per-run/per-stave KS, Wasserstein, and median errors |
| `response_parameter_scan.csv` | traditional and GP/BO response-card candidate grid |
| `raw_reproduction_counts_by_run.csv` | raw ROOT selected-pulse count by run |
