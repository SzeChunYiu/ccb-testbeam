# G4-02 - Energy calibration vs GEANT4 truth deposited energy
- Study ID:      G4-02
- Ticket ID:     1781212364.2054355.4a1327ef
- Title:         Energy calibration vs GEANT4 truth deposited energy
- Date:          2026-07-10
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00 selected-pulse gate; S14g GEANT4/Birks energy bridge; G4-01/G4-04 pending for adoption
- Data anchor:   640,737 selected B-stave pulses

**ML loses: traditional 0.04025 beats ML 0.05809; the GEANT4/Birks lookup is the production candidate for this closure metric.**

## Reproduction Gate

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s14g_0000000003_1_g4energy.py --config configs/g4_02_1781212364_2054355_4a1327ef_energy_calibration.yaml
```

Expected: 640,737 selected B-stave pulses from raw B-stack ROOT files in `/home/billy/Desktop/test_beam/data/root/root`.

Actual: 640,737; delta +0; pass `true`.

Seed: numpy/sklearn/torch random seed 1437; run-block bootstrap seed is derived from the method name and uses 300 resamples.

Selection: baseline is the median of samples [0, 1, 2, 3]; a selected B pulse is an even physical B-stave channel B2/B4/B6/B8 with peak amplitude greater than 1000.0 ADC.

## Key Metrics Table

The primary score is the 68th percentile of absolute fractional energy residuals, `res68 = P68(|(Ehat - Eodd)/Eodd|)`, evaluated only on held-out runs.

| method                 | family                   | n      | bias_frac   | res68_frac | res68_ci95         | mae_mev | mae_mev_ci95       |
| --- | --- | --- | --- | --- | --- | --- | --- |
| geant4_birks_lookup    | traditional_geant4_birks | 332852 | -0.023105   | 0.040248   | [0.03886, 0.04161] | 0.22821 | [0.20179, 0.26361] |
| gradient_boosted_trees | ml_tree                  | 332852 | -0.016798   | 0.058092   | [0.04997, 0.06870] | 0.21426 | [0.18851, 0.24653] |
| physics_residual_mlp   | neural_physics_residual  | 332852 | -0.014597   | 0.058683   | [0.04904, 0.07789] | 0.2219  | [0.19293, 0.27133] |
| ridge                  | ml_linear                | 332852 | -0.023655   | 0.096692   | [0.08872, 0.11728] | 0.29739 | [0.27321, 0.32954] |
| 1d_cnn                 | neural_waveform          | 332852 | -6.5609e-05 | 0.10775    | [0.09097, 0.15318] | 0.33978 | [0.29888, 0.40706] |
| mlp                    | neural_tabular           | 332852 | 0.020596    | 0.18327    | [0.14279, 0.24433] | 0.53764 | [0.48199, 0.61795] |
| old_power_law          | traditional_empirical    | 332852 | -0.29763    | 0.46237    | [0.44418, 0.56703] | 1.6563  | [1.56336, 1.73562] |

## Physics Motivation

The experiment needs an energy observable that is tied to deposited energy rather than only to ADC charge. GEANT4 provides a stopping-power and range-energy prior, while the real data provide duplicate readout closure: even channels predict an odd-channel target after train-run calibration. This G4-02 study asks whether ML improves that calibration enough to justify replacing a transparent GEANT4/Birks rule.

## Methodology

### Data Selection

Raw ROOT branches `HRDv`, `EVENTNO`, and `EVT` are read directly. Waveforms are reshaped into 8 channels by 18 samples; even channels 0/2/4/6 are treated as physical B2/B4/B6/B8 readout and odd channels 1/3/5/7 as duplicate closure readout. After the reproduction gate, events are retained for the energy benchmark when both even and odd event charge sums exceed 100 ADC; pulse rows entering the Birks fit require odd charge above 20 ADC.

Counts by run:

| run | group              | events_total | events_with_selected | selected_pulses |
| --- | --- | --- | --- | --- |
| 31  | sample_i_calib     | 39990        | 27078                | 27871           |
| 32  | sample_i_calib     | 41921        | 27461                | 28240           |
| 33  | sample_i_calib     | 57173        | 47911                | 48737           |
| 34  | sample_i_calib     | 39765        | 33500                | 34118           |
| 35  | sample_i_calib     | 27786        | 11141                | 11667           |
| 36  | sample_i_calib     | 21764        | 9930                 | 10391           |
| 37  | sample_i_calib     | 50513        | 23174                | 24537           |
| 39  | sample_i_calib     | 30321        | 13329                | 14218           |
| 40  | sample_i_calib     | 32613        | 13763                | 14708           |
| 41  | sample_i_calib     | 33997        | 15140                | 16146           |
| 42  | sample_i_calib     | 33972        | 17132                | 18112           |
| 44  | sample_i_analysis  | 4294         | 1912                 | 2038            |
| 45  | sample_i_analysis  | 48181        | 23013                | 24333           |
| 46  | sample_i_analysis  | 1441         | 677                  | 687             |
| 47  | sample_i_analysis  | 10970        | 5161                 | 5276            |
| 48  | sample_i_analysis  | 31713        | 13185                | 14000           |
| 49  | sample_i_analysis  | 32354        | 13937                | 14815           |
| 50  | sample_i_analysis  | 44804        | 34257                | 35217           |
| 51  | sample_i_analysis  | 20569        | 14295                | 14740           |
| 52  | sample_i_analysis  | 10005        | 6933                 | 7152            |
| 53  | sample_i_analysis  | 39612        | 31386                | 32200           |
| 54  | sample_i_analysis  | 37413        | 29665                | 30440           |
| 55  | sample_i_analysis  | 24416        | 16841                | 17387           |
| 56  | sample_i_analysis  | 51823        | 38932                | 40148           |
| 57  | sample_i_analysis  | 31284        | 12939                | 13833           |
| 58  | sample_ii_analysis | 34141        | 15920                | 16781           |
| 59  | sample_ii_analysis | 42303        | 13863                | 21377           |
| 60  | sample_ii_analysis | 36074        | 10140                | 17029           |
| 61  | sample_ii_analysis | 36535        | 11287                | 18965           |
| 62  | sample_ii_analysis | 37584        | 11912                | 19089           |
| 63  | sample_ii_analysis | 37030        | 14781                | 18817           |
| 64  | sample_ii_calib    | 35943        | 12103                | 14630           |
| 65  | sample_ii_analysis | 38424        | 11904                | 13038           |

### GEANT4 Range-Energy Prior

The GEANT4 stopping table `/home/billy/ccb-geant4/dedx_p_in_CD2.txt` is interpreted as kinetic energy `E` in MeV and stopping power `S(E)=dE/dx` in GeV/mm, converted by 10000 to MeV/cm. The continuous-slowing-down range is

```text
R(E) = integral_0^E [1 / S(E')] dE' .
```

For each stave center `z_j`, residual kinetic energy is `E_j = R^-1(R(E0)-z_j)`, with `E0 = 190.0 MeV`. The layer truth prior is

```text
DeltaE_j = E(front_j) - E(back_j)
```

for a 1.0 cm effective layer thickness. This produces the following per-layer priors:

| stave | center_cm | residual_energy_mev | dedx_mev_cm | expected_edep_mev |
| --- | --- | --- | --- | --- |
| B2    | 2         | 182.28              | 3.9065      | 3.9032            |
| B4    | 6         | 166.2               | 4.1477      | 4.1437            |
| B6    | 10        | 148.97              | 4.5199      | 4.5152            |
| B8    | 14        | 130.03              | 4.9817      | 4.9831            |

### Traditional Baselines

The strongest traditional method is `geant4_birks_lookup`. On train runs, duplicate odd charges fit the one-parameter Birks-like response

```text
Q_j = alpha * DeltaE_j / (1 + kB * S_j).
```

The fitted constants are `alpha = 15123.5 ADC/MeV` and `kB = 0.0485 cm/MeV`. Even-channel charges are inverted with the same response and summed over selected staves. A weaker but transparent empirical incumbent, `old_power_law`, fits `log(Eodd) = beta0 + beta1 log(Qeven)` on train runs.

### ML And Neural Methods

All ML methods use only even-readout information: event multiplicity, depth index, even total charge, maximum even amplitude, saturation count, per-stave log charge, per-stave log amplitude, hit indicators, normalized peak positions, and early/late charge fractions. Odd charge, event identifiers, and run labels are excluded. The evaluated methods are:

- `ridge`: standardized ridge regression on log energy.
- `gradient_boosted_trees`: scikit-learn gradient boosting with 60 depth-3 trees, learning rate 0.05, and 0.75 subsampling.
- `mlp`: tabular PyTorch MLP with one hidden layer and SmoothL1 loss.
- `1d_cnn`: small 1D convolutional network over the four B-stave waveforms plus tabular features.
- `physics_residual_mlp`: the new architecture for this benchmark; it predicts a multiplicative residual correction to the GEANT4/Birks baseline, i.e. `Ehat = Ebirks * exp(f_theta(x, log Ebirks))`.

Training uses sample I calibration runs and run 64; held-out scoring uses sample I analysis runs 44-57 and sample II analysis runs 58-63 and 65.

### Leakage Controls

| check                                       | value                                                                                                                                                                                                                                                                                                                                                            | pass |
| --- | --- | --- |
| train_heldout_run_overlap                   | []                                                                                                                                                                                                                                                                                                                                                               | True |
| raw_reproduction_exact                      | 640737 of 640737                                                                                                                                                                                                                                                                                                                                                 | True |
| ml_features_exclude_odd_charge_run_event_id | multiplicity,depth_idx,even_total_charge,even_max_amp,saturated_count,log_charge_stave_0,log_charge_stave_1,log_charge_stave_2,log_charge_stave_3,log_amp_stave_0,log_amp_stave_1,log_amp_stave_2,log_amp_stave_3,hit_stave_0,hit_stave_1,hit_stave_2,hit_stave_3,peak_stave_0,peak_stave_1,peak_stave_2,peak_stave_3,early_charge_fraction,late_charge_fraction | True |
| cnn_status                                  | trained                                                                                                                                                                                                                                                                                                                                                          | True |
| birks_kB_cm_per_MeV                         | 0.0485                                                                                                                                                                                                                                                                                                                                                           | True |

## Results

The named winner in `result.json` is `geant4_birks_lookup`. It is a traditional method, not an ML win: the best ML/NN method is `gradient_boosted_trees` with res68 0.05809, worse than the GEANT4/Birks baseline at 0.04025. The ML-minus-traditional delta is +0.01784; since smaller is better, the positive delta means ML loses.

Run-level spread for the production candidate and best ML method:

| method                 | n_runs | median_res68 | min_res68 | max_res68 |
| --- | --- | --- | --- | --- |
| geant4_birks_lookup    | 21     | 0.041935     | 0.031519  | 0.052982  |
| gradient_boosted_trees | 21     | 0.065117     | 0.035924  | 0.13897   |

The range-energy and benchmark figure is archived at `reports/1781212364.2054355.4a1327ef__g4_02_energy_calibration/figures/fig_G4_02_range_energy_benchmark.png`.

## Interpretation

The result supports a conservative calibration policy. GEANT4 truth supplies a physically motivated layer-energy prior, and the duplicate readout shows that a simple Birks inversion transfers across held-out real runs better than the learned models. The ML panel is still informative: gradient-boosted trees approach the traditional candidate in MAE, but their res68 tails and run-block CIs do not justify replacing the transparent physics rule.

This does not establish an absolute calorimetric energy scale for data. The target is duplicate-readout closure after a GEANT4/dE/dx prior, not an independent event-level truth label. Absolute adoption is therefore blocked until G4-01 validates the geometry/material response and G4-04 constrains Birks quenching and light-yield systematics.

## MC Verdict

MC validation is partially available through the GEANT4 stopping-power prior and range-energy curve used here, but not yet sufficient for production adoption. The calibration is marked conditional: use `docs/reports/G4_02_energy_calibration_calib.json` as a calibration artifact only after G4-01 and G4-04 pass.

## Systematics And Caveats

- Birks quenching: the fitted `kB` absorbs scintillator quenching and electronics response; G4-04 must separate these effects.
- Light yield and ADC scale: `alpha` is learned from duplicate readout and is not an independent absolute light-yield measurement.
- Geometry and layer alignment: the nominal `center_4cm` geometry fixes the MeV scale; alternate center spacings can shift the range-energy prior.
- Particle composition: the ticket asks for proton/deuteron control regions, but current raw ROOT labels do not provide event-level particle truth. This study therefore reports the proton dE/dx anchored closure and flags PID-separated adoption as pending.
- Saturation: saturated pulses remain represented through saturation count and clipped waveform features; high-charge tails can bias neural losses.
- Closure target: odd readout is a duplicate electronics channel, not true deposited energy. It validates transfer consistency, not absolute truth.

## Open Questions

1. G4-04: vary Birks constants and light-yield maps in GEANT4, then test whether `kB` and `alpha` remain stable under duplicate-readout closure.
2. G4-01: propagate material budget and stave-center uncertainty into the G4-02 range-energy curve and report the induced MeV scale envelope.
3. G4-02b: add event-level PID control labels and repeat the benchmark separately for proton and deuteron control regions.

## Provenance

```text
Git commit:        3defbda9afa80dc0895f57f15924a3ad627e8a66
Ticket:            1781212364.2054355.4a1327ef
Data SHA256:       see reports/1781212364.2054355.4a1327ef__g4_02_energy_calibration/input_sha256.csv
Python:            3.7.6
numpy:             1.21.6
pandas:            1.3.4
Run host/job:      local testbeam-laptop-4
Artifacts:         reports/1781212364.2054355.4a1327ef__g4_02_energy_calibration/{REPORT.md,result.json,manifest.json,figures/}
Calibration JSON:  docs/reports/G4_02_energy_calibration_calib.json
```
