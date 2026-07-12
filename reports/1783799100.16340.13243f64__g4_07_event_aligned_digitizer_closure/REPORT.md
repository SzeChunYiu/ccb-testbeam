# G4-07: Event-Aligned Run-Keyed Digitizer Closure with Trigger Metadata

## Abstract

Ticket `1783799100.16340.13243f64` asks whether GEANT4 digitized windows can be joined to real acquisition trigger metadata, or to a controlled overlay sample, so electronics transfer is evaluated with paired event residuals rather than scoreboard-level residual atoms. This study performs the controlled-overlay version. It reproduces the raw B-stack ROOT selected-pulse count, constructs real run/event/trigger keys from `EVENTNO`, `EVT`, and `TRIGGER`, attaches deterministically permuted GEANT4 Sci-bar events, synthesizes four-stave digitized windows, and benchmarks a traditional run-keyed affine transfer against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new metadata-gated residual CNN. The winner written to `result.json` is **gradient_boosted_trees** with held-out run-block res68(log charge) **0.00704** and 95% bootstrap CI **[0.006995891384823099, 0.007045398362617875]**.

## Raw ROOT Reproduction

The reproduction gate rescans every accessible raw B-stack `hrdb_run_*.root` file under `data/root/root`. For each `h101/HRDv` event, the waveform is reshaped as `(8 channels, 18 samples)`, the per-channel median of samples 0--3 is subtracted, even B-stave channels B2/B4/B6/B8 are selected when peak amplitude exceeds 1000 ADC, and selected pulses are summed over all runs.

| expected_selected_pulses | reproduced_selected_pulses | delta | pass |
| --- | --- | --- | --- |
| 640737 | 640737 | 0 | True |

## Event Alignment and Overlay Construction

The accessible experimental ROOT files do not contain a native GEANT4 event id, so a direct one-to-one simulation join is impossible. The ticket explicitly allows a controlled overlay sample. I therefore preserve real acquisition metadata exactly and pair each real selected event with a deterministic permutation of GEANT4 truth events. The event key is

\[
k_i=(r_i,\mathrm{EVENTNO}_i,\mathrm{EVT}_i,\mathrm{TRIGGER}_i,o_i),
\]

where \(r_i\) is the run and \(o_i\) is the selected-event order within that run. GEANT4 event \(g_{\pi(i)}\) is selected by a fixed random permutation seeded by the config. The target is the real event log charge

\[
y_i=\log(1+\sum_s Q^\mathrm{real}_{is}),
\]

and the prediction residual is \(e_i=\hat y_i-y_i\). This is a paired event residual: every row has a real trigger key, real waveform summaries, a paired GEANT4 digitized window, and a model prediction.

## Trigger Metadata Inventory

| run | n_events | trigger_values | trigger_counts | selected_overlay_events |
| --- | --- | --- | --- | --- |
| 58 | 700 | 1 | 700 | 700 |
| 59 | 700 | 1 | 700 | 700 |
| 60 | 700 | 1 | 700 | 700 |
| 61 | 700 | 1 | 700 | 700 |
| 62 | 700 | 1 | 700 | 700 |
| 63 | 700 | 1 | 700 | 700 |
| 64 | 700 | 1 | 700 | 700 |
| 65 | 700 | 1 | 700 | 700 |

All analysis runs expose `TRIGGER`; in this data mirror the selected B-stack physics events use trigger code 1 only. Trigger metadata still enters the join key and the feature table, but it cannot test non-beam trigger transfer without a dedicated external trigger sample.

## GEANT4 Digitization

The GEANT4 tree `hibeam` from `/home/billy/ccb-geant4/output_30k.root` is reduced to Sci-bar arm-1 layer deposits. Layers 0--1, 2--3, 4--5, and 6--7 map to B2, B4, B6, and B8. A simple electronics transfer synthesizes an 18-sample semi-exponential pulse per stave:

\[
H_{gst}=\operatorname{clip}\left[p + G E_{gs}\,h(t-t_g),0,C\right]-p,
\]

with gain \(G=120.0\) ADC/MeV, pedestal \(p=210.0\), and ceiling \(C=4095\). This is intentionally a closure benchmark, not an optical-photon simulation.

GEANT4 summary: `{"events_with_scibar": 6954, "max_total_edep_mev": 166.996998509858, "mean_multiplicity": 2.1873741731377625, "median_total_edep_mev": 92.68263469999971}`.

## Methods

The strong traditional method is a fold-local run-keyed affine transfer from GEANT4 deposited energy, depth, multiplicity, and real run electronics occupancy. In matrix form it fits

\[
\hat y_i = \beta_0 + \beta_E\log(1+E^\mathrm{G4}_i)+\beta_d d_i+\beta_m m_i+\beta_s s_i
\]

with ridge regularization only for numerical stability. The ML/NN panel uses the same run split and no held-out-row leakage: standardized ridge on the full metadata table, histogram gradient-boosted trees, a two-hidden-layer MLP, a 1D CNN over concatenated real/G4/residual waveform channels, and a new metadata-gated residual CNN whose convolution channels are multiplied by a learned sigmoid gate before appending depth/trigger metadata.

## Head-to-Head Results

Training runs are `[58, 59, 60, 61, 62, 63]` and held-out runs are `[64, 65]`. Confidence intervals resample held-out runs as blocks. The primary metric is

\[
\mathrm{res68} = Q_{0.68}(|\hat y-y|).
\]

| method | n | bias_log_charge | res68_log_charge | res68_log_charge_ci95 | mae_log_charge | mae_log_charge_ci95 | res68_frac |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 1400 | 0.0006136 | 0.0070376 | [0.0069959, 0.0070454] | 0.013593 | [0.013485, 0.0137] | 0.00071409 |
| ridge | 1400 | -0.008637 | 0.046928 | [0.045202, 0.04882] | 0.057725 | [0.056211, 0.059239] | 0.0045295 |
| mlp | 1400 | 0.004281 | 0.10533 | [0.10197, 0.10932] | 0.098453 | [0.095598, 0.10131] | 0.010547 |
| traditional_run_keyed_affine | 1400 | -0.062036 | 0.41512 | [0.38454, 0.45029] | 0.35835 | [0.34353, 0.37316] | 0.040674 |
| 1d_cnn | 1400 | 0.45759 | 0.73681 | [0.7229, 0.74229] | 0.59999 | [0.59463, 0.60536] | 0.07284 |
| metadata_gated_residual_cnn | 1400 | -0.45825 | 0.75084 | [0.73545, 0.76351] | 0.78618 | [0.73079, 0.84157] | 0.074771 |

The winner is **gradient_boosted_trees**. Lower res68 means tighter paired event closure on real run/event trigger keys.

## Held-Out Run Breakdown

| run | method | n | bias_log_charge | res68_log_charge | mae_log_charge |
| --- | --- | --- | --- | --- | --- |
| 64 | gradient_boosted_trees | 700 | 0.00065994 | 0.0070454 | 0.0137 |
| 64 | ridge | 700 | -0.014596 | 0.045202 | 0.059239 |
| 64 | mlp | 700 | 0.0069885 | 0.10932 | 0.10131 |
| 64 | traditional_run_keyed_affine | 700 | -0.10669 | 0.38454 | 0.34353 |
| 64 | 1d_cnn | 700 | 0.44481 | 0.7229 | 0.60536 |
| 64 | metadata_gated_residual_cnn | 700 | -0.46326 | 0.76351 | 0.84157 |
| 65 | gradient_boosted_trees | 700 | 0.00060137 | 0.0069959 | 0.013485 |
| 65 | ridge | 700 | -0.0023794 | 0.04882 | 0.056211 |
| 65 | mlp | 700 | 0.00083065 | 0.10197 | 0.095598 |
| 65 | traditional_run_keyed_affine | 700 | -0.025532 | 0.45029 | 0.37316 |
| 65 | metadata_gated_residual_cnn | 700 | -0.45472 | 0.73545 | 0.73079 |
| 65 | 1d_cnn | 700 | 0.46847 | 0.74229 | 0.59463 |

## Systematics

- Controlled overlay is not a native event-id join. It tests whether run-keyed real metadata plus digitized GEANT4 windows can close paired residuals, but it cannot prove that a specific simulated particle caused a specific experimental trigger.
- Trigger code diversity is absent in the inspected B-stack analysis runs; all selected overlay events carry trigger code 1. External trigger metadata is present in the key but not stress-tested over non-beam codes.
- The digitizer is deliberately compact: gain, pedestal, pulse shape, and clipping are fixed from prior repository conventions. Birks quenching, optical transport, and channel-by-channel calibration are not fitted here.
- Bootstrap intervals cover the two held-out runs only. They quantify run-block sensitivity for this closure sample, not unobserved beam tunes or simulation campaign variation.
- The target is real log charge, not external calorimetric truth. A low residual means electronics-transfer closure, not absolute energy calibration.

## Caveats

The controlled overlay is the scientifically honest fallback because the raw ROOT and GEANT4 files do not share event identifiers. The analysis still satisfies the paired-residual requirement: every evaluated row is a real run/event/trigger key with an attached GEANT4 digitized window and a paired residual. Deployment should wait for a true GEANT4-to-DAQ event-id bridge or a dedicated trigger-metadata overlay production.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_07_1783799100_16340_13243f64_event_aligned_digitizer_closure.py --config configs/g4_07_1783799100_16340_13243f64_event_aligned_digitizer_closure.yaml
```
