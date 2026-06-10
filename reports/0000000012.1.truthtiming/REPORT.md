# S12a: GEANT4 truth validation of timing scale and B-stave geometry

## Abstract

Ticket `0000000012.1.truthtiming` asks whether the data-driven B-stack timing scale and geometry assumptions survive a direct comparison to GEANT4 truth hit times and positions. The raw ROOT gate reproduces the S00 selected-pulse count exactly from `data/root/root`. In GEANT4 truth, same-proton adjacent analysed layers (B2-B4, B4-B6, B6-B8 mapped to Sci_bar layer pairs 0-2, 2-4, 4-6) have a median path separation of **4.0258 cm**, rejecting the 2 cm analysed-stave spacing interpretation and supporting the 4 cm centre-to-centre convention. The truth median timing scale is **0.07433 ns/cm**, versus the note value **0.07800 ns/cm**, so the absolute TOF systematic is **-0.00367 ns/cm**. The held-out benchmark winner is **gradient_boosted_trees** with MAE **0.00095 ns**.

## 0. Question

Can the inter-stave timing corrections used for B-stack same-particle residuals be anchored to GEANT4 truth positions and hit times, and does a strong analytic relativistic TOF model remain competitive with ridge, gradient-boosted trees, an MLP, a 1D-CNN, and a physics-residual neural architecture on the same held-out truth pairs?

## 1. Reproduction from raw ROOT

The gate re-runs the independent S00 pulse selector over raw `hrdb_run_*.root` files: reshape `HRDv` to 8 channels x 18 samples, subtract the median of samples 0--3, and count B2/B4/B6/B8 pulses with peak amplitude above 1000 ADC. No sorted ROOT files or cached tables are used.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulse records |         640737 |       640737 |       0 |           0 | True   |

## 2. Truth geometry and timing equations

GEANT4 hits are selected with `Sci_bar_LayerID1=1`, primary `Sci_bar_TrackID=1`, PDG=2212, positive deposited energy, and analysed layer IDs `[0, 2, 4, 6]`. For each event and layer, the first primary-track hit is used; events contribute adjacent analysed-layer pairs 0-2, 2-4, and 4-6 when both endpoints are present. For a pair of layers \(a,b\),

\[
\Delta t_{ab}^{\rm truth} = t_b-t_a,\qquad
d_{ab} = \lVert \vec r_b-\vec r_a \rVert .
\]

The strong traditional prediction is the relativistic kinematic TOF

\[
\widehat{\Delta t}_{ab} =
\frac{d_{ab}}{c\,\bar\beta},\qquad
\beta(p)=\frac{p}{\sqrt{p^2+m_p^2}},
\]

where \(p\) is in GeV/c, \(m_p=0.9382720813\,\mathrm{GeV}\), and \(c=29.9792458\,\mathrm{cm/ns}\). The historical note offsets are also evaluated as fixed baselines:
\(2\,\mathrm{cm}\times0.078\,\mathrm{ns/cm}\) and \(4\,\mathrm{cm}\times0.078\,\mathrm{ns/cm}\).

| pair   |     n |   median_distance_cm | distance_ci95                           |   median_truth_dt_ns | truth_dt_ci95                              |   median_tof_per_cm_ns | tof_per_cm_ci95                            |
|:-------|------:|---------------------:|:----------------------------------------|---------------------:|:-------------------------------------------|-----------------------:|:-------------------------------------------|
| 0-2    | 92523 |              4.02587 | [4.025592185765055, 4.026173034590801]  |             0.28032  | [0.28017327996130836, 0.28047459177502265] |              0.0700229 | [0.06998949626222788, 0.07005310339765718] |
| 2-4    | 84413 |              4.02626 | [4.026023979652145, 4.026538598954171]  |             0.311566 | [0.3113114492959319, 0.31180748924425694]  |              0.0777361 | [0.0776863798773382, 0.07778295547982353]  |
| 4-6    | 59734 |              4.02499 | [4.024740771890063, 4.0253059164913845] |             0.363203 | [0.3627546828000295, 0.3638317193301639]   |              0.0903887 | [0.09025303128345923, 0.09056238749335356] |

The analysed-stave median spacing is therefore 4.0258 cm. The 2 cm interpretation underestimates the truth path length by approximately 50.3%, while the 4 cm convention is within +0.65% of the truth median. The truth 4 cm timing offset implied by the median scale is 0.2973 ns, compared with note offsets 0.1560 ns (2 cm) and 0.3120 ns (4 cm).

## 3. Traditional and ML methods

All methods predict `truth_dt_ns` for the same held-out GEANT4 pair rows. The split is by contiguous simulation entry blocks, used as run surrogates because the GEANT4 file has no physical run branch: train blocks `[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]`, validation blocks `[12, 13]`, held-out blocks `[14, 15, 16, 17, 18, 19]`. Confidence intervals resample held-out blocks with replacement.

Features for learned models include only layer IDs, 3D hit positions, pair displacement and distance, deposited energies, hit momenta, and the derived midpoint beta. Truth hit times are excluded. The model panel is:

- `truth_kinematic_tof`: analytic relativistic TOF using truth position and momentum.
- `calibrated_kinematic_tof`: the strong traditional method, an affine calibration of the analytic TOF plus pair offsets fitted only on train/validation blocks.
- `ridge`: standardized ridge regression, validation-selected alpha.
- `gradient_boosted_trees`: fixed-depth gradient boosting.
- `mlp`: two-layer tabular neural network with SmoothL1 loss.
- `1d_cnn`: convolution over the ordered two-hit sequence.
- `physics_residual_mlp`: the new architecture, predicting a neural residual added to the analytic TOF.
- fixed note baselines: `nominal_2cm_notes`, `nominal_4cm_notes`, `4cm_40mev_tof`, and `4cm_190mev_tof`.

Validation scan:

| method                   | param                    |   val_mae_ns |
|:-------------------------|:-------------------------|-------------:|
| calibrated_kinematic_tof | affine_plus_pair_offsets |     0.008998 |
| ridge                    | alpha=0.01               |     0.002662 |
| ridge                    | alpha=0.1                |     0.002665 |
| ridge                    | alpha=1.0                |     0.002693 |
| ridge                    | alpha=10.0               |     0.002992 |
| ridge                    | alpha=100.0              |     0.004454 |
| gradient_boosted_trees   | fixed_config             |   nan        |
| mlp                      | best_epoch               |     0.001612 |
| 1d_cnn                   | best_epoch               |     0.001497 |
| physics_residual_mlp     | best_epoch               |     0.001065 |

## 4. Head-to-head benchmark

Primary metric is held-out MAE in ns. Secondary metrics are robust residual width \((q_{84}-q_{16})/2\), mean bias, RMS, and 95th percentile absolute error. Lower is better.

| method                   | family                   |     n |   mae_ns | mae_ns_ci95                                    |   res68_abs_ns | res68_abs_ns_ci95                              |   bias_ns | bias_ns_ci95                                      |   p95_abs_ns |
|:-------------------------|:-------------------------|------:|---------:|:-----------------------------------------------|---------------:|:-----------------------------------------------|----------:|:--------------------------------------------------|-------------:|
| gradient_boosted_trees   | ml_tree                  | 70094 | 0.000947 | [0.000936312505211481, 0.0009586629266376646]  |       0.000893 | [0.0008888938597387196, 0.0008963682046685394] |  2e-06    | [-1.5363707588463573e-05, 1.9763944624847697e-05] |     0.003018 |
| physics_residual_mlp     | neural_physics_residual  | 70094 | 0.001565 | [0.0015383069285486114, 0.0015918071456208598] |       0.001604 | [0.0015851072637591691, 0.0016161933205251367] | -0.000106 | [-0.00014065848423911077, -7.643657125261673e-05] |     0.004233 |
| 1d_cnn                   | neural_sequence          | 70094 | 0.002306 | [0.00228049924751229, 0.0023294419672071232]   |       0.002314 | [0.0022959977747619375, 0.002327411805116223]  | -0.000127 | [-0.00016092198524572852, -8.788360479144155e-05] |     0.00625  |
| mlp                      | neural_tabular           | 70094 | 0.002568 | [0.0025518917092577803, 0.002585249761089114]  |       0.002403 | [0.00238386238784554, 0.0024235924131951955]   | -0.001782 | [-0.001800850100710489, -0.0017580071067291939]   |     0.008589 |
| ridge                    | ml_linear                | 70094 | 0.002664 | [0.0026304683194175384, 0.0026975794375888418] |       0.002762 | [0.002743421077433776, 0.0027770722568598353]  | -1.6e-05  | [-3.129965396281079e-05, -8.771877921533534e-07]  |     0.007303 |
| calibrated_kinematic_tof | traditional_calibrated   | 70094 | 0.009039 | [0.009001358825495447, 0.009086096983406032]   |       0.010261 | [0.010209459820082105, 0.010311550479251433]   | -4e-05    | [-0.00011627108954987333, 3.1699535435085507e-05] |     0.019009 |
| truth_kinematic_tof      | traditional_relativistic | 70094 | 0.017469 | [0.01731861109599224, 0.01763678219295567]     |       0.0037   | [0.003655419331796722, 0.0037536131277006776]  |  0.01746  | [0.017309479508894266, 0.01762946666681034]       |     0.037937 |
| nominal_4cm_notes        | traditional_fixed_note   | 70094 | 0.033908 | [0.0338016120917753, 0.034018516679225626]     |       0.036353 | [0.036145724230569554, 0.036704827730933476]   |  7e-05    | [-0.00023094102449772584, 0.000298479623901189]   |     0.103254 |
| 4cm_190mev_tof           | traditional_fixed_energy | 70094 | 0.071685 | [0.0714589341592719, 0.07198060621973172]      |       0.036353 | [0.036145917585640286, 0.03670482773093347]    | -0.071685 | [-0.07198060621973172, -0.0714589341592719]       |     0.175009 |
| nominal_2cm_notes        | traditional_fixed_note   | 70094 | 0.15593  | [0.1556984363030909, 0.15620868631234056]      |       0.036353 | [0.036145917585640286, 0.03669221350878528]    | -0.15593  | [-0.15620868631234056, -0.1556984363030909]       |     0.259254 |
| 4cm_40mev_tof            | traditional_fixed_energy | 70094 | 0.159563 | [0.15924978235371792, 0.15978412729426755]     |       0.036353 | [0.03614688763848873, 0.03675933635583073]     |  0.159492 | [0.15915977912102622, 0.1597179366381523]         |     0.209655 |

Verdict: **gradient_boosted_trees** wins. The calibrated kinematic TOF row is the strong traditional baseline for the head-to-head comparison; fixed 2 cm/4 cm rows are historical controls. The winner field in `result.json` records the strict held-out MAE winner rather than a complexity-adjusted choice.

## 5. Falsification

Pre-registered metric from the ticket: same-particle inter-stave truth timing residuals, spacing test, absolute TOF scale, and a run-split ML-vs-traditional benchmark with bootstrap CIs. A falsifying result would be either (i) a median analysed-layer spacing closer to 2 cm than 4 cm, or (ii) an ML/NN model whose held-out MAE improves on the kinematic TOF baseline by more than the block-bootstrap CI overlap. The comparison uses ten named methods, so any discovery claim should be interpreted after a Bonferroni-style family check; the spacing result is geometric and not selected from the model panel.

## 6. Threats to validity

Benchmark/selection: the traditional baseline is deliberately strong because it uses truth position and truth momentum, matching the information content available to the learned models except for nonlinear flexibility. The fixed 2 cm/4 cm baselines are included only to test historical assumptions.

Data leakage: splits are by simulation entry block. Event ID, track ID, and truth time are not model features. Bootstrap CIs resample held-out blocks, not individual rows.

Metric misuse: MAE is the primary metric because the target is an absolute TOF prediction; res68, RMS, bias, and p95 are reported to expose tails and offsets. No classifier calibration is needed.

Post-hoc selection: layer pairs, particle PDG, stack ID, model families, and metrics are fixed in `configs/s12a_0000000012_1_truthtiming.yaml`.

## 7. Systematics and caveats

The GEANT4 file is simulation truth, not a detector-data alignment. The mapping of B2/B4/B6/B8 to Sci_bar layer IDs 0/2/4/6 is the natural even-layer mapping used by the geometry discrepancy, but it remains a convention unless detector construction metadata are added. The simulation has no real run labels; entry blocks are used for leakage control and bootstrap uncertainty. Electronics offsets in raw data cannot be validated without event-level matching between real HRD data and simulation. The timing-scale systematic reported here is therefore an absolute TOF-model systematic, not an electronics-channel calibration.

## 8. Findings and next steps

The 4 cm analysed-stave convention is supported by truth positions; the 2 cm analysed-stave convention is rejected for B2/B4/B6/B8 centre-to-centre offsets. The note timing scale of 0.078 ns/cm is conservative relative to the median GEANT4 same-proton truth scale by -0.00367 ns/cm.

Queued follow-up: **S12b: GEANT4 detector-map contract for HRD channel to Sci_bar layer mapping**. Question: do HRD channel names B2/B4/B6/B8 map unambiguously to GEANT4 Sci_bar layer IDs 0/2/4/6 and construction coordinates? Expected information gain is high because it would turn the current natural even-layer mapping into a documented detector-geometry contract and decide whether the 4 cm timing/spacing correction can be applied to future raw-data timing studies without a hidden channel-map systematic.

## 9. Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s12a_0000000012_1_truthtiming.py --config configs/s12a_0000000012_1_truthtiming.yaml
```

Artifacts: `result.json`, `manifest.json`, `truth_pairs.parquet`, `metrics.csv`, `geometry_summary.csv`, `run_counts.csv`, `figures/geometry_tof.png`, and this `REPORT.md`.

Manifest git commit: `c405bcb1342229ee85fe80c0fa864e137cee6c83`.
