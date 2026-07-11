# S17d: Optical and Electronics Parameter Scan for the Digitized GEANT4 Bridge

## Abstract

Ticket `1783791474.19875.088f6d63` scans the S17c digitizer's optical yield, shaping time, pedestal drift, and ADC clipping parameters against the S24a real residual strata. The raw ROOT reproduction gate is direct: `h101/HRDv` from `/home/billy/Desktop/test_beam/data/root/root` is baseline-subtracted and counted with the S00 B-stave threshold, reproducing **640,737** selected pulses against **640,737**. The best response-family match is **light_yield_scale=0.7** with log-res68 RMS distance **1.6421** to the S24a strata. On the selected digitizer, the benchmark winner written to `result.json` is **gradient_boosted_trees**, res68 **0.05026** with 95% run-bootstrap CI **[0.04719029142887861, 0.0551729681204654]**.

## Raw ROOT Reproduction

For each configured run, `HRDv` is reshaped to `(channel, sample)=(8,18)`. The per-channel median over samples 0--3 is subtracted. Even B-stave channels B2/B4/B6/B8 are selected when the corrected maximum exceeds 1000 ADC. This reproduces the ticket-scale number before any GEANT4, digitizer, or model step is run.

| expected_selected_pulses | reproduced_selected_pulses | delta | pass |
| --- | --- | --- | --- |
| 640737 | 640737 | 0 | True |

## Parameterized Digitizer

GEANT4 `Sci_bar_EDep` and `Sci_bar_TrackLength` are reduced to the mapped even B-stave layers. The baseline S17c charge model is

\[ Q_{ij}=\alpha E_{ij}(1+k_B(dE/dx)_{ij})^{-1}, \]

where `i` indexes events and `j` indexes B staves. The electronics response uses a normalized semi-Gaussian waveform with shaping time \(\tau\), pedestal offset \(p_r\), event common-mode noise \(c_i\), channel noise \(n_{ijt}\), afterpulse fraction \(f_a\), and clipping level \(C\):

\[ H_{ijt}=\operatorname{clip}\{p_r+c_i+n_{ijt}+A_{ij}g_\tau(t-t_{0,ij})+f_aA_{ij}g_\tau(t-t_{0,ij}-3),0,C\}. \]

The scan changes one family at a time relative to the S17c baseline: optical light yield \(\alpha\), shaping time \(\tau\), run pedestal drift width, and ADC clipping ceiling. Each candidate is scored by the RMS log-distance between simulated held-out Birks residual width and the S24a real in-stratum Birks residual width.

## S24a Residual Targets

| stratum | definition | n | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| adc_saturation_onset | any_saturated | 106217 | -0.040403 | 0.048498 | 1.2846 |
| pileup_or_multihit | multiplicity>=2 | 27765 | -0.019433 | 0.12595 | 3.1683 |
| pedestal_drift_proxy_high | charge/peak above heldout median | 166426 | -0.023258 | 0.033216 | 1.1235 |
| late_pulse_shape | deepest selected B stave index>=2 | 15256 | -0.017026 | 0.11667 | 3.0832 |

## Parameter Scan Results

| family | value | distance_log_res68_rms | mean_log_res68_delta_sim_minus_real | sim_saturation_event_fraction |
| --- | --- | --- | --- | --- |
| light_yield_scale | 0.7 | 1.6421 | 1.4793 | 0.98974 |
| light_yield_scale | 0.85 | 1.7071 | 1.5509 | 0.99118 |
| pedestal_run_drift_adc | 24 | 1.9088 | 1.7893 | 0.99232 |
| saturation_adc | 4095 | 1.9112 | 1.7921 | 0.99234 |
| light_yield_scale | 1 | 1.9123 | 1.7935 | 0.99234 |
| baseline | 1 | 1.9125 | 1.7935 | 0.99232 |
| pedestal_run_drift_adc | 12 | 1.9141 | 1.7948 | 0.99237 |
| pedestal_run_drift_adc | 0 | 1.9165 | 1.7971 | 0.99229 |
| pedestal_run_drift_adc | 6 | 1.9165 | 1.7976 | 0.99237 |
| shaping_tau_samples | 1.8 | 1.9172 | 1.7982 | 0.99345 |
| shaping_tau_samples | 2.15 | 1.9186 | 1.8 | 0.99232 |
| pedestal_run_drift_adc | 36 | 1.9226 | 1.8066 | 0.99237 |

The scan identifies which detector-response family moves the digitized simulation toward the real-data residual topology. The distance is not an absolute likelihood; it is a structured diagnostic over the S24a strata and is interpreted together with the supervised benchmark below.

## Supervised Benchmark

The selected digitizer is then benchmarked under the same pseudo-run split as S17c: pseudo-runs 1--7 train, 8--10 are held out. Bootstrap confidence intervals resample held-out pseudo-runs as blocks. The primary metric is

\[ \mathrm{res68}=Q_{0.68}\left(\left|\frac{\hat E-E}{E}\right|\right), \]

with signed median fractional bias and mean absolute error as secondary scores. Methods include the strong traditional digitized Birks inversion, ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN that learns a multiplicative waveform correction to Birks after tabular saturation/shape gating.

| method | family | n | bias_frac | res68_frac | res68_ci95 | mae_mev | mae_mev_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | ml_tree | 10814 | -0.0050239 | 0.050259 | [0.04719029142887861, 0.0551729681204654] | 2.754 | [2.581293054759755, 3.0245650984246395] |
| mlp | neural_tabular | 10814 | 0.014146 | 0.0833 | [0.0810677916166492, 0.08677154015466298] | 4.4791 | [4.445944041943911, 4.513004961279218] |
| gated_residual_cnn | neural_gated_residual_new | 10814 | -0.011376 | 0.099316 | [0.09821967144683327, 0.10046677264704777] | 5.3238 | [5.172050917528869, 5.562608910412357] |
| ridge | ml_linear | 10814 | 0.0096535 | 0.23011 | [0.22217989741610092, 0.2342031448944878] | 11.784 | [11.527109740117588, 11.914736379968577] |
| 1d_cnn | neural_waveform | 10814 | 0.0065051 | 0.23384 | [0.22941760025844624, 0.23839197565065706] | 12.187 | [11.92503130202816, 12.363813894710914] |
| truth_birks_lookup | traditional_digitized_birks | 10814 | -0.30807 | 0.53739 | [0.5357738431515904, 0.5398907028408899] | 25.707 | [25.600169266260888, 25.77344058108427] |

## Held-Out Pseudo-Run Breakdown

| pseudo_run | method | n | bias_frac | res68_frac | mae_mev |
| --- | --- | --- | --- | --- | --- |
| 8 | truth_birks_lookup | 3605 | -0.31254 | 0.5398 | 25.748 |
| 9 | truth_birks_lookup | 3605 | -0.30849 | 0.53569 | 25.773 |
| 10 | truth_birks_lookup | 3604 | -0.30473 | 0.53767 | 25.6 |
| 8 | gradient_boosted_trees | 3605 | 0.0078693 | 0.047178 | 2.5813 |
| 9 | gradient_boosted_trees | 3605 | -0.0033084 | 0.048903 | 2.6563 |
| 10 | gradient_boosted_trees | 3604 | -0.019563 | 0.055173 | 3.0246 |

## Sim-vs-Real Method Consistency

| method | sim_res68_frac | real_s24a_res68_frac | delta_sim_minus_real | interpretation |
| --- | --- | --- | --- | --- |
| gradient_boosted_trees | 0.050259 | 0.056685 | -0.0064255 | same method label after Birks-name normalization |
| mlp | 0.0833 | 0.69235 | -0.60905 | same method label after Birks-name normalization |
| ridge | 0.23011 | 0.096673 | 0.13344 | same method label after Birks-name normalization |
| 1d_cnn | 0.23384 | 0.2657 | -0.031863 | same method label after Birks-name normalization |
| truth_birks_lookup | 0.53739 | 0.040244 | 0.49715 | same method label after Birks-name normalization |

## Systematics

- The scan is one-factor-at-a-time. It isolates families but does not fit a full joint optical/electronics likelihood.
- GEANT4 and HRD events are not event-aligned; S24a comparison is stratum-level rather than row-level.
- Pseudo-runs are deterministic simulation blocks, so bootstrap intervals cover block composition but not true beam-condition drift.
- The optical-yield scan inherits the S24a Birks calibration and does not replace an optical photon simulation.
- Clipping and pedestal drift are applied after waveform synthesis; unmodeled baseline recovery and front-end nonlinearities can still dominate real saturation tails.

## Caveats

The selected light-yield response is the best member of the scanned one-factor families, not a globally optimized detector model. The S24a real-data targets are residual-shape constraints rather than labels for the same events used in simulation, so agreement in those strata should be read as consistency evidence rather than proof of a unique optical or electronics parameter. The bootstrap intervals quantify held-out pseudo-run variation for this simulation sample; they do not include uncertainty from the GEANT4 production, ROOT decoding assumptions, or the real-data Birks calibration inherited from S24a.

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. Across the four S24a residual strata, the closest one-factor digitizer family is light_yield_scale=0.7 (RMS log-res68 distance 1.6421). On that selected response model, gradient_boosted_trees wins the held-out pseudo-run benchmark with res68=0.05026; the conclusion is that light_yield_scale is the most plausible single missing detector-response handle among the scanned families, while real-data deployment remains bounded by the S24a non-event-aligned comparison.

## Artifacts and Reproducibility

Primary outputs are `result.json`, `REPORT.md`, `manifest.json`, `raw_reproduction_by_run.csv`, `digitizer_parameter_scan.csv`, `scan_strata_metrics.csv`, `selected_method_metrics.csv`, `selected_by_pseudorun.csv`, and `sim_vs_real_method_residuals.csv`.

```bash
/home/billy/anaconda3/bin/python scripts/s17d_1783791474_19875_088f6d63_digitizer_parameter_scan.py --config configs/s17d_1783791474_19875_088f6d63_digitizer_parameter_scan.yaml
```
