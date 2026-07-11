# S24a Pulse-Shape Pedestal Disentanglement Benchmark

Ticket: `1783754154.7824.22ac6254`  
Worker: `testbeam-laptop-2`  
Claimed command: `tn-ticket claim testbeam-laptop-2 --project testbeam`  
Raw ROOT input: `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`

## Abstract

This study tests whether apparent timing, pile-up, energy, saturation, and PID-proxy residuals in the B-stave pulse sample are driven mainly by pedestal drift or by genuine pulse-shape variation. The analysis uses raw-ROOT-derived evidence from the repository's S24a energy/saturation benchmark and S24b pedestal-shape invariance benchmark, both gated by the same raw ROOT pulse-count reproduction check. The reproduced raw ROOT selected-pulse count is exactly 640,737, matching the expected reference count with zero difference.

The primary disentanglement endpoint is held-out-run classification of high pedestal drift from engineered and waveform features, with run-block bootstrap 95% confidence intervals. A gradient-boosted tree model is the primary winner: ROC AUC = 0.9484 with 95% CI [0.9248, 0.9644], outperforming the traditional Fisher-Gatti engineered-feature baseline and the tested ridge, MLP, 1D-CNN, and residual squeeze CNN. The result means pedestal state is highly recoverable from the same feature families used in timing, energy, and PID proxies. Endpoint-specific exceptions matter: the best inclusive energy closure remains the traditional GEANT4/Birks lookup, with fractional sigma68 = 0.04024 [0.03886, 0.04161], while the physics-residual MLP is best in the saturation-onset energy stratum.

## Reproduction Gate

The raw ROOT reproduction gate uses `h101/HRDv` records, B-stave channels `{2,4,6,8}`, a per-pulse pedestal estimated from the median of the first four ADC samples, and a selected-pulse requirement that the pedestal-subtracted maximum amplitude exceed 1000 ADC counts. The reproduction table copied into this ticket artifact records exact agreement:

| Quantity | Value |
| --- | ---: |
| Raw ROOT glob | `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root` |
| Expected selected B-stave pulses | 640,737 |
| Reproduced selected B-stave pulses | 640,737 |
| Difference | 0 |
| Evidence | `reproduction_match_table.csv` |

This gate is the first acceptance criterion for all downstream benchmarks: any method comparison is interpreted only after the raw pulse selection has been shown to reproduce the expected sample size.

## Scientific Model

Let `x_i(t)` be the waveform for pulse `i` and channel `c_i` in run `r_i`. The pedestal estimate is

```text
p_i = median{x_i(t): t in {0,1,2,3}}
```

and the baseline-subtracted waveform is

```text
z_i(t) = x_i(t) - p_i.
```

Pulse amplitude is `A_i = max_t z_i(t)`. The selected analysis sample satisfies `A_i > 1000 ADC` for B-stave channels. The study separates two mechanisms:

```text
observed residual = genuine pulse-shape term + pedestal-drift term + run/domain term + noise.
```

The pedestal term is operationalized with a run-block weak label, `y_i = 1` for high-drift blocks and `0` for low-drift blocks. The pulse-shape term is represented through normalized waveform descriptors, Fisher-Gatti-like projections, width/asymmetry metrics, saturation flags, and energy/timing proxies. Successful prediction of `y_i` from these representations, under held-out runs, shows that pedestal drift is not an ignorable nuisance: it is entangled with shape, timing, energy, and PID proxies in a run-stable way.

## Metrics

For binary pedestal-drift classification, the primary metric is ROC AUC, with average precision as an imbalance-sensitive secondary metric. For energy closure the primary robust resolution metric is fractional sigma68:

```text
res68_frac = 0.5 * (Q84(delta_E / E) - Q16(delta_E / E)).
```

Bias is the mean fractional residual,

```text
bias_frac = mean(delta_E / E),
```

and MAE is reported in MeV where available. For pedestal-induced proxy shifts, the reported high-minus-low drift effect is

```text
Delta_m = mean(m | high drift) - mean(m | low drift),
```

where `m` is a shape-distance, timing, energy, or PID proxy. All uncertainty intervals are percentile 95% confidence intervals from run-block bootstrap resampling. Runs, not events, are the bootstrap units to avoid overstating precision from correlated pulses in the same detector state.

## Evaluation Design

The evaluation deliberately avoids event-level random splits. Pedestal classification uses held-out runs `[42, 50, 57, 58, 60, 62, 64, 65]` and 500 run-block bootstrap replicas. The energy study uses held-out-run summaries and run-block bootstrap intervals from `energy_run_heldout_summary.csv` and `energy_method_metrics.csv`. This design asks whether a method generalizes across run conditions rather than whether it interpolates within a single run.

The benchmark includes:

| Family | Methods |
| --- | --- |
| Traditional pedestal/shape | `traditional_fisher_gatti_all_features` |
| Traditional energy | `geant4_birks_lookup`, `old_power_law` |
| Linear ML | `ML_ridge_classifier`, `ridge` |
| Tree ML | `ML_gradient_boosted_trees`, `gradient_boosted_trees` |
| Tabular neural | `ML_mlp`, `mlp`, `physics_residual_mlp` |
| Waveform neural | `NN_1d_cnn`, `1d_cnn` |
| New architectures | `NN_residual_squeeze_cnn_new`, `physics_residual_mlp`, `transformer` |

The traditional Fisher-Gatti-like comparator is a strong analytic baseline because it projects waveforms onto engineered pulse-shape and pedestal-sideband summaries. The energy traditional comparator uses a detector-physics GEANT4/Birks lookup, and the empirical power law is retained as a weaker historical baseline. The neural additions test whether waveform-local convolution, attention, or physics-residual learning can improve over these strong baselines.

## Primary Pedestal-Disentanglement Results

The primary result is the held-out-run pedestal-drift classification table:

| Method | N | Positives | ROC AUC | 95% CI | Average precision | Role |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| `ML_gradient_boosted_trees` | 9,745 | 2,060 | 0.9484 | [0.9248, 0.9644] | 0.9204 | ML panel |
| `ML_mlp` | 9,745 | 2,060 | 0.9181 | [0.8908, 0.9379] | 0.8813 | ML panel |
| `NN_residual_squeeze_cnn_new` | 9,745 | 2,060 | 0.9062 | [0.8795, 0.9233] | 0.8632 | New NN architecture |
| `ML_ridge_classifier` | 9,745 | 2,060 | 0.8926 | [0.8686, 0.9107] | 0.8427 | Linear ML |
| `traditional_fisher_gatti_all_features` | 9,745 | 2,060 | 0.8878 | [0.8585, 0.9070] | 0.8437 | Traditional |
| `NN_1d_cnn` | 9,745 | 2,060 | 0.7071 | [0.6771, 0.7338] | 0.5702 | Waveform NN |

The gradient-boosted tree is the primary winner. Its AUC interval is separated from the 1D-CNN and remains above the Fisher-Gatti baseline. The MLP and residual squeeze CNN are competitive but do not overtake the tree. Ridge is close to the traditional engineered-feature baseline, indicating that much of the pedestal signature is linearly visible, but the nonlinear tree extracts additional interaction structure.

The poor 1D-CNN result is informative rather than merely negative. It suggests that raw local waveform texture alone is insufficient under this split unless the architecture is constrained or augmented with explicit pedestal-sideband and run-stable summary variables. The new residual squeeze CNN improves strongly over the plain 1D-CNN, supporting the value of compact residual channel mixing for this detector regime.

## Proxy Shifts: Shape, Timing, Energy, and PID

The bootstrap high-minus-low pedestal-drift shifts are:

| Proxy | Interpretation | Shift | 95% CI |
| --- | --- | ---: | --- |
| `shape_distance_nominal_chi2` | Shape-distance stability | 0.1171 | [0.1034, 0.1272] |
| `timing_residual_mean_time_sample` | Timing residual | -3.2409 | [-3.5574, -2.8710] |
| `energy_residual_log10_amplitude` | Energy calibration proxy | -0.0903 | [-0.1007, -0.0798] |
| `pid_residual_odd_negative_adc` | PID score proxy | -1545.6250 | [-1645.3813, -1424.0313] |

All intervals exclude zero by a wide margin. The sign and magnitude pattern implies that pedestal drift is not confined to a baseline offset; it co-moves with pulse shape, timing, energy scale, and PID-proxy residuals. The timing shift of roughly -3.24 mean-time samples is especially large relative to a pure nuisance expectation. The PID proxy shift is also large, warning that PID-like variables built from signed ADC summaries can absorb detector-state changes.

## Energy Benchmark Results

The inclusive S24a energy benchmark gives a complementary result: the strongest traditional detector-physics method wins the energy endpoint even though the gradient-boosted tree wins the pedestal-disentanglement endpoint.

| Method | Family | N | Bias frac | Res68 frac | 95% CI for res68 | MAE MeV | 95% CI for MAE |
| --- | --- | ---: | ---: | ---: | --- | ---: | --- |
| `geant4_birks_lookup` | traditional GEANT4/Birks | 332,852 | -0.0231 | 0.0402 | [0.0389, 0.0416] | 1.0824 | [0.9582, 1.2490] |
| `gradient_boosted_trees` | ML tree | 332,852 | -0.0167 | 0.0567 | [0.0488, 0.0672] | 1.0029 | [0.8835, 1.1522] |
| `physics_residual_mlp` | neural physics residual | 332,852 | -0.0146 | 0.0587 | [0.0490, 0.0779] | 1.0515 | [0.9152, 1.2831] |
| `ridge` | ML linear | 332,852 | -0.0236 | 0.0967 | [0.0887, 0.1172] | 1.4114 | [1.2981, 1.5619] |
| `transformer` | neural waveform attention | 332,852 | 0.0326 | 0.1264 | [0.1204, 0.1440] | 1.9291 | [1.8156, 2.0287] |
| `1d_cnn` | neural waveform | 332,852 | -0.1777 | 0.2657 | [0.2493, 0.2891] | 3.8621 | [3.5557, 4.0799] |
| `old_power_law` | traditional empirical | 332,852 | -0.2976 | 0.4624 | [0.4443, 0.5644] | 7.8628 | [7.4234, 8.2452] |
| `mlp` | neural tabular | 332,852 | -0.5827 | 0.6923 | [0.6842, 0.6996] | 10.6163 | [9.3753, 11.5247] |

The energy table argues against a simplistic "ML always wins" interpretation. The detector-physics lookup has the best robust fractional resolution, while the tree and physics-residual MLP reduce absolute-error summaries but have broader sigma68. For the ticket question, this means the winner must be named by endpoint: gradient-boosted trees for pedestal disentanglement, GEANT4/Birks for inclusive energy closure.

## Saturation and Pulse-Shape Strata

The copied saturation/shape stratum table shows an endpoint-specific neural advantage at the ADC saturation onset. In that stratum, `physics_residual_mlp` reaches fractional sigma68 = 0.03877 with CI [0.03589, 0.04471], better than the inclusive tree and neural waveform models in the same stress regime. This supports a physically sensible division of labor: analytic detector corrections dominate the inclusive response, while a constrained residual neural model can help where the analytic response is locally stressed by saturation.

This result should not be generalized to all neural architectures. The plain 1D-CNN is weak in both pedestal classification and energy closure, and the transformer energy result is below the GEANT4/Birks lookup. The useful neural model is the one that encodes the residual problem around a physics prior rather than replacing the full response model.

## Interpretation

The benchmark supports three conclusions.

First, pedestal drift is a dominant, learnable run-block effect. The gradient-boosted tree's AUC near 0.95 under held-out-run evaluation shows that high-drift states leave a reproducible signature in the same variables that feed timing, energy, and PID proxies.

Second, genuine pulse-shape information remains present, but pedestal-sideband information must be modeled explicitly. Ridge and Fisher-Gatti methods perform respectably, which means engineered projections already contain much of the signal. The tree improves because it captures interactions among pedestal windows, shape distances, amplitudes, and saturation descriptors.

Third, endpoint winners are not identical. If the objective is pedestal-versus-shape disentanglement, `ML_gradient_boosted_trees` is the winner. If the objective is inclusive energy reconstruction, `geant4_birks_lookup` is the winner. If the objective is saturation-onset energy stress, `physics_residual_mlp` is the most promising architecture.

## Systematic Uncertainties

Several systematics can affect the interpretation:

| Source | Risk | Mitigation in this artifact | Residual caveat |
| --- | --- | --- | --- |
| Run correlation | Event-level splits overstate precision | Held-out-run splits and run-block bootstrap CIs | Small number of held-out runs limits tail precision |
| Weak pedestal labels | High/low labels may mix detector states | Labels are used as disentanglement probes, not ground truth | A dedicated calibration label would be stronger |
| Pedestal estimator | Median of samples 0:3 can include early pickup | Same estimator used in reproduction and benchmarks | Alternative sideband windows should be tested |
| Saturation | Clipping changes waveform shape and energy response | Saturation/shape strata are reported separately | Sparse extreme strata can broaden CIs |
| Architecture tuning | NN models may be under- or over-tuned | Multiple NN families are shown with held-out runs | Better regularized waveform models may improve |
| Source synthesis | This ticket uses existing raw-ROOT-derived benchmark artifacts | All copied tables are included with provenance in `manifest.json` | A single monolithic rerun would be cleaner but costly |

## Caveats

The primary caveat is that this ticket is a synthesis over already materialized raw-ROOT-derived analyses rather than a fresh rerun of every model inside the current default Python environment. The source analyses were produced from the raw ROOT files, and the exact selected-pulse reproduction table is included here. The practical benefit is that this ticket can compare all requested model families without rerunning long neural training jobs; the cost is that provenance must be read through the copied tables and manifest.

The second caveat is interpretive. A classifier that separates high- and low-pedestal drift does not prove that pedestal drift alone causes every timing, energy, or PID residual. It proves that pedestal drift is statistically entangled with those observables under run-held-out evaluation. The proxy shift table then shows that the entanglement is large enough to matter for timing, energy, and PID-like variables.

## Winner

The winner named in `result.json` is:

```text
ML_gradient_boosted_trees
```

It is the primary winner for the claimed ticket because the ticket asks for pedestal-versus-genuine-pulse-shape disentanglement. It has the best held-out-run pedestal-drift ROC AUC, 0.9484 [0.9248, 0.9644]. The report also records endpoint-specific winners so that this conclusion is not confused with the inclusive energy result, where `geant4_birks_lookup` remains best.

## Reproducibility Inventory

| File | Purpose |
| --- | --- |
| `claimed_ticket.txt` | Ticket id and title claimed by this worker |
| `result.json` | Machine-readable result and named winner |
| `manifest.json` | Source-artifact provenance and ticket append accounting |
| `reproduction_match_table.csv` | Raw ROOT reproduction gate |
| `pedestal_primary_method_summary.csv` | Primary pedestal-disentanglement model table |
| `pedestal_traditional_method_summary.csv` | Traditional pedestal comparator details |
| `proxy_shift_bootstrap_cis.csv` | Shape/timing/energy/PID proxy shifts with CIs |
| `energy_method_metrics.csv` | Inclusive energy benchmark with CIs |
| `energy_run_heldout_summary.csv` | Held-out-run energy split summary |
| `saturation_shape_strata_metrics.csv` | Saturation and shape stratum results |
| `pedestal_drift_by_run.csv` | Run-level pedestal strata |
| `pedestal_drift_time_blocks.csv` | Time-block pedestal drift evidence |

No novel ticket was appended from this artifact. The objective allowed at most one; zero were appended because the next most useful follow-up is already explicit in the caveats: a monolithic rerun with alternate pedestal sideband windows and dedicated calibration labels.
