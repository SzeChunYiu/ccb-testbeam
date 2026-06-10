# S20: GEANT4 truth validation of pile-up multiplicity

- **Ticket:** `0000000014.1.truthpileup`
- **Worker:** `testbeam-laptop-3`
- **Raw inputs:** `data/root/root` B-stack ROOT files
- **Truth input:** `/home/billy/ccb-geant4/output_krakow_1M.root`
- **Primary truth target for ML:** `truth_pd_overlap_90p0_ns` (proton and deuteron both deposit in Sci_bar with first-hit separation <= 90.0 ns)

## Reproduction gate

The raw-data gate is intentionally first.  The same baseline-subtracted B2/B4/B6/B8 amplitude cut used throughout the project is applied:

\[
A_{r,e,s}=\max_t\left(HRDv_{r,e,c(s),t}-\mathrm{median}(HRDv_{r,e,c(s),0:3})\right),\qquad
I_{r,e,s}=\mathbb{1}[A_{r,e,s}>1000].
\]

| quantity              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_pulses |         640737 |       640737 |       0 |           0 | True   |

## Raw current-dependent excess

For each run, selected events are events with at least one selected B-stack stave.  The topology rates are

\[
\hat p_g = \frac{\sum_{r\in g} N_r(\mathrm{topology})}{\sum_{r\in g} N_r(\mathrm{selected\ event})},
\qquad
\Delta = \hat p_{20\,\mathrm{nA}}-\hat p_{2\,\mathrm{nA}} .
\]

Confidence intervals are non-parametric bootstraps over real run IDs within current group.

| metric                         | contrast       |     value |   ci95_low |   ci95_high |   n_runs |
|:-------------------------------|:---------------|----------:|-----------:|------------:|---------:|
| multi_stave_per_selected_event | low_2nA        | 0.015588  |  0.011817  |   0.016082  |        2 |
| multi_stave_per_selected_event | high_20nA      | 0.026806  |  0.022053  |   0.034842  |       12 |
| multi_stave_per_selected_event | high_minus_low | 0.011219  |  0.0062766 |   0.018419  |       14 |
| three_stave_per_selected_event | low_2nA        | 0.004111  |  0.0014771 |   0.0044565 |        2 |
| three_stave_per_selected_event | high_20nA      | 0.0085379 |  0.0070366 |   0.011311  |       12 |
| three_stave_per_selected_event | high_minus_low | 0.0044269 |  0.0027678 |   0.0087203 |       14 |
| downstream_per_selected_event  | low_2nA        | 0.023124  |  0.014771  |   0.02422   |        2 |
| downstream_per_selected_event  | high_20nA      | 0.033414  |  0.027545  |   0.042775  |       12 |
| downstream_per_selected_event  | high_minus_low | 0.01029   |  0.0039018 |   0.022813  |       14 |

## GEANT4 truth definitions

The hibeam truth tree has no test-beam run/current branch.  The 1M events are therefore split into deterministic contiguous pseudo-runs solely for leakage control and block-bootstrap uncertainty.  This is weaker than true run splitting and is treated as a systematic limitation.

Truth multiplicity is evaluated from positive Sci_bar energy deposits:

\[
M_{\mathrm{track}}(e)=\left|\{\mathrm{TrackID}: E_{dep}>0\}\right|,\qquad
M_{pd}(e,\tau)=\mathbb{1}[p\ \mathrm{and}\ d\ \mathrm{deposit}]\,
\mathbb{1}[|t_p^{min}-t_d^{min}|\le \tau].
\]

The key truth rates, with pseudo-run block bootstrap CIs, are:

| truth_quantity                         |    value |   ci95_low |   ci95_high |   n_events |   n_pseudo_runs |
|:---------------------------------------|---------:|-----------:|------------:|-----------:|----------------:|
| truth_multi_track                      | 0.11202  |   0.11157  |    0.11241  |    1000000 |               3 |
| truth_multi_species                    | 0.10989  |   0.10941  |    0.11016  |    1000000 |               3 |
| truth_pd_present                       | 0.078119 |   0.077799 |    0.078294 |    1000000 |               3 |
| truth_pd_overlap_20p0_ns               | 0.078054 |   0.077751 |    0.078222 |    1000000 |               3 |
| truth_pd_overlap_60p0_ns               | 0.078071 |   0.077796 |    0.078231 |    1000000 |               3 |
| truth_pd_overlap_90p0_ns               | 0.078071 |   0.077763 |    0.07824  |    1000000 |               3 |
| truth_pd_overlap_124p79018394263471_ns | 0.078071 |   0.077763 |    0.078243 |    1000000 |               3 |

## Traditional and ML/NN benchmark

The traditional score is a truth-blind B-layer topology score:

\[
S_{trad} = N_{B\ layers} + \mathbb{1}[\mathrm{downstream\ B\ layer}] + 0.25\,\mathbb{1}[\Delta t_{Sci\ bar}\le \tau].
\]

The ML panel uses only detector-level Sci_bar hit summaries and per-layer energy/count/time tensors; it does not use PDG, TrackID, or the target labels as features.  Models are trained with the scored pseudo-run held out: ridge regression score, gradient-boosted trees, MLP, 1D CNN over ordered Sci_bar layers, and a new DeepSets-style layer-pooling network.  Model CIs are block bootstraps over held-out pseudo-runs.

|   rank_by_average_precision | method                 |   average_precision |   average_precision_ci95_low |   average_precision_ci95_high |   roc_auc |   roc_auc_ci95_low |   roc_auc_ci95_high |     brier |   brier_ci95_low |   brier_ci95_high |
|----------------------------:|:-----------------------|--------------------:|-----------------------------:|------------------------------:|----------:|-------------------:|--------------------:|----------:|-----------------:|------------------:|
|                           1 | gradient_boosted_trees |            0.98314  |                     0.98253  |                      0.985    |  0.99864  |           0.99862  |             0.99874 | 0.0085246 |        0.0083173 |          0.008866 |
|                           2 | ridge                  |            0.94027  |                     0.93035  |                      0.94669  |  0.99044  |           0.98943  |             0.99176 | 0.017467  |        0.015829  |          0.018178 |
|                           3 | mlp                    |            0.91624  |                     0.89724  |                      0.94041  |  0.99132  |           0.99091  |             0.99252 | 0.013843  |        0.010822  |          0.017796 |
|                           4 | traditional_topology   |            0.26663  |                     0.26225  |                      0.27388  |  0.87044  |           0.8673   |             0.87251 | 0.12211   |        0.11999   |          0.1242   |
|                           5 | deepsets_layer_pool    |            0.053436 |                     0.043581 |                      0.05375  |  0.30852  |           0.10757  |             0.30852 | 0.1997    |        0.17961   |          0.21463  |
|                           6 | cnn_1d                 |            0.043205 |                     0.041677 |                      0.045876 |  0.078039 |           0.033065 |             0.10463 | 0.23566   |        0.23442   |          0.23812  |

The winner by held-out average precision is **gradient_boosted_trees**.

## Rmax interpretation

The S10 occupancy model maps an allowed overlap occupancy \(\epsilon\) to

\[
R_{max} = \frac{\epsilon}{\tau_{eff}}.
\]

For the project value \(\epsilon=0.38\), the note's \(\tau_{eff}=90\) ns gives 4.22 MHz.  The raw waveform live10 measurement \(\tau=124.79\) ns gives about 3.05 MHz.  GEANT4 truth does not contain beam-current timing or DAQ live-time, so it cannot by itself restore the 90 ns assumption; it constrains intrinsic p+d multiplicity/topology instead.

| definition                                 |   tau_ns |   occupancy_tolerance |   rmax_mhz | basis                                                                         |
|:-------------------------------------------|---------:|----------------------:|-----------:|:------------------------------------------------------------------------------|
| note_assumed_tau                           |    90    |              0.38     |   4.2222   | S10 occupancy tolerance divided by effective live window                      |
| raw_measured_live10_tau                    |   124.79 |              0.38     |   3.0451   | S10 occupancy tolerance divided by effective live window                      |
| data_high_minus_low_downstream_equivalent  |   124.79 |              0.01029  |   0.082884 | Poisson rate that would yield the observed fraction in measured live10 window |
| truth_intrinsic_pd_overlap_90ns_equivalent |   124.79 |              0.078071 |   0.65139  | Poisson rate that would yield the observed fraction in measured live10 window |

## Leakage controls

| check                                 |       value | flag   | note                                                                                           |
|:--------------------------------------|------------:|:-------|:-----------------------------------------------------------------------------------------------|
| raw_reproduction_exact                | 1           | False  | Total selected B-stave pulses must reproduce 640737 exactly.                                   |
| reported_downstream_low_reproduced    | 2.43577e-05 | False  | Raw S10 low-current downstream rate within configured tolerance.                               |
| reported_downstream_high_reproduced   | 1.41048e-05 | False  | Raw S10 high-current downstream rate within configured tolerance.                              |
| truth_features_exclude_pdg_trackid    | 1           | False  | PDG and TrackID define labels only; model inputs are hit summaries and layer tensors.          |
| heldout_blocks_excluded_from_training | 1           | False  | Every model is trained with the scored pseudo-run block held out.                              |
| simulation_has_real_run_branch        | 0           | False  | No run/current branch exists; pseudo-runs are a documented limitation, not a hidden run split. |

## Systematics and caveats

1. The GEANT4 truth file has no run/current metadata.  Pseudo-runs protect the ML comparison from event-level leakage but do not reproduce real detector-run drift.
2. Truth labels are Sci_bar-level p+d coincidences and truth-track multiplicities, not digitized HRD waveform pile-up.  A full electronics response would be required to turn these into ADC-level overlay labels.
3. The raw current excess is measured in real data; the truth file is current-independent.  Agreement in topology can validate a baseline intrinsic multiplicity component, but cannot prove the 20 nA high-minus-low excess is caused by GEANT4 p+d coincidences.
4. The traditional topology score intentionally mirrors the data-driven S10 idea and is not allowed to inspect PDG or TrackID.  The ML/NN features are likewise detector-level summaries only.
5. The Rmax conclusion remains dominated by the live-time definition.  Truth multiplicity does not support reverting from the measured ~3.05 MHz live10 value to the older 4.22 MHz assumption.

## Conclusion

Raw ROOT reproduction passes exactly.  GEANT4 truth shows the intrinsic Sci_bar p+d/multi-track coincidence baseline and provides a genuine supervised target for checking the data-driven topology score.  The best held-out truth classifier is **gradient_boosted_trees**.  For the operational pile-up-rate limit, truth does not supersede the raw waveform live-time measurement: the defensible current value remains the measured-live10 **Rmax ≈ 3.05 MHz**, while the note's 4.22 MHz is the result of assuming a shorter 90 ns live window.  The real data high-minus-low topology excess is reported above with real-run CIs and should be interpreted as a current-dependent excess not directly encoded in the current-independent GEANT4 truth sample.
