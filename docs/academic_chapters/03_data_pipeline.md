# §3 — Data Pipeline: From Raw Waveforms to Truth-Bridged Analysis

The analysis of the CCB test-beam data proceeds through a three-stage pipeline that reduces 110 raw ROOT files to a unified selected-pulse table, distributes the reduced data into parallel analysis branches, and cross-validates every result against a GEANT4 Monte Carlo simulation equipped with a custom digitizer that converts truth-level energy depositions into synthetic ADC waveforms. This pipeline architecture ensures that every physics result — timing resolution, pile-up tolerance, particle identification — is assessed against a truth-labelled reference obtained by running the identical analysis code on digitised Monte Carlo events.

## Stage 1: Raw ROOT to selected-pulse table

The raw data comprise 110 ROOT files totalling approximately 810 MB for the compressed B-stack, organised by run number with the naming convention `hrdb_run_NNNN.root`. Each file contains a TTree (`h101`) with three branches per event: `EVENTNO` (event number), `EVT` (event type flag), and `HRDv` (a two-dimensional array of 18-sample ADC waveforms indexed by stave and channel). The reconstruction script `01_build_pulse_table_from_root.py` processes these files in a single pass, performing the following operations for each waveform:

1. **Baseline estimation:** The median of ADC samples 0–3 (the pre-trigger region, corresponding to the first 40 ns of the 180 ns acquisition window) is computed per waveform. This median estimator is robust against single-sample fluctuations and pre-trigger pile-up tails. An alternative dynamic baseline estimator, which adapts the baseline window based on the pulse peak position, yields 706,373 selected pulses; the difference arises because the dynamic estimator recovers pulses near the window edges where the fixed pre-trigger samples are contaminated by the rising edge of a preceding pulse. The median estimator is chosen as the canonical selector for its simplicity and reproducibility.

2. **Pulse amplitude extraction:** The baseline is subtracted from all 18 samples, and the maximum baseline-subtracted ADC value is recorded as the pulse amplitude. The sample index of this maximum is recorded as the peak sample.

3. **Pulse area integration:** The sum of baseline-subtracted ADC values across all 18 samples provides an integrated charge proxy, which is less sensitive to saturation than the peak amplitude and serves as a cross-check for heavily ionising particles.

4. **Selection:** Only pulses with amplitude A > 1000 ADC are retained. This threshold rejects electronic noise (typical RMS ~50–80 ADC in the pre-trigger region) and low-energy background while preserving >99% of pulses from charged particles that deposit measurable energy in the scintillator.

The output is a compressed CSV table (`s00_selected_b_pulses.csv.gz`) containing 640,737 selected B-stack pulse records. The exact reproduction of this count against the original analysis note is verified by Study S00, which records SHA256 checksums for all input ROOT files and the output pulse table, establishing a cryptographically verifiable provenance chain.

Data quality monitoring is performed per run: the baseline mean and RMS are recorded for each run, and runs with anomalous baseline distributions (mean shift >3σ from the global average, or RMS >2× the global median) are flagged for exclusion. In the current dataset, run 43 was removed from Sample I on this basis.

## Stage 2: Analysis branches

The selected-pulse table is the single point of entry for all downstream analyses, which are organised into three branches:

**Timing branch (Studies S02–S06).** This branch extracts particle arrival times using two complementary algorithms: a constant-fraction discriminator (CFD) at 20% of peak amplitude, and an optimal filter (OF) matched to the average pulse template. Inter-stave time residuals provide the primary observable for timing resolution. Corrections for amplitude-dependent timewalk are applied using an analytic parametrisation derived from the pulse shape. The combined multi-stave timing resolution reaches σ₆₈ ≈ 0.54–0.56 ns (see §4).

**Pile-up branch (Studies S10–S11).** This branch characterises the rate of overlapping pulses within the 180 ns acquisition window. The live-time method counts the fraction of events in which the pre-trigger baseline region is free of preceding pulses, yielding an effective beam rate and a maximum tolerable rate R_max ≈ 3.05 MHz, validated by Monte Carlo to 0.2% (see §5).

**Particle identification branch (Studies S08, MV1–MV2).** This branch constructs the ΔE-E plane from the energy deposition in B2 and B4, applying both traditional threshold-based cuts and machine-learning classifiers to separate protons from deuterons. The MC truth ceiling for proton-deuteron separation is AUC = 0.986 (see §8).

## Stage 3: Monte Carlo digitizer and truth bridge

The critical methodological contribution of this analysis is the MV0 digitizer, which converts GEANT4 truth-level energy depositions into synthetic 18-sample ADC waveforms, enabling the identical analysis pipeline to run on both data and Monte Carlo with truth labels attached. The digitizer models the following physical processes in sequence:

1. **Birks quenching** (optional, disabled by default): The scintillation light yield per unit energy deposition saturates at high ionisation density according to Birks' law, dL/dx = A (dE/dx) / (1 + kB dE/dx).

2. **Scintillation time profile:** The light pulse is modelled as a double-exponential with rise time τ_rise = 2.0 ns and decay time τ_decay = 35.0 ns, consistent with the BC-408 plastic scintillator used in the HRD staves. The time integral of the light pulse is proportional to the quenched energy deposition.

3. **WLS fibre transport:** The light collection and transport through the wavelength-shifting fibre introduces a Gaussian time dispersion with σ_transport = 0.5 ns, modelling the convolution of the WLS decay time and the fibre's intermodal dispersion.

4. **Sampling:** The continuous light curve is integrated over 10 ns bins to produce 18 discrete ADC samples, matching the 100 MHz flash ADC sampling.

5. **Electronics:** Gaussian electronic noise with σ_noise = 50 ADC channels is added to each sample, and the waveform is quantised to integer ADC values. An optional saturation ceiling clips the waveform at 7000 ADC to model the SiPM and ADC saturation observed in the data.

The digitizer is configured through a YAML specification (`configs/mc_validation/base.yaml`) that exposes every physical parameter. The digitizer output for 1 million GEANT4 events has been validated against data in Study MV0, with the primary systematic being the ±30% uncertainty on the overall MeV-to-ADC gain factor.

## Parameters and defaults

| Parameter | Value | Source |
|---|---|---|
| ADC samples per waveform | 18 | Hardware specification |
| Sample spacing | 10 ns | 100 MHz flash ADC |
| Baseline estimator | Median of samples 0–3 | S00 validation |
| Amplitude threshold | A > 1000 ADC | Noise rejection (S16 pedestal study) |
| Scintillator | BC-408 | HRD design document |
| τ_rise (scintillator) | 2.0 ns | BC-408 datasheet |
| τ_decay (scintillator) | 35.0 ns | BC-408 datasheet (approximate) |
| σ_transport (WLS) | 0.5 ns | Estimated from fibre length and WLS decay |
| σ_noise (electronics) | 50 ADC | Measured from forced-trigger data |
| Birks constant kB | Not applied (default) | Requires independent calibration |
| ADC saturation ceiling | 7000 ADC | Observed in data B2 spectra |
| MeV→ADC gain | 245.6 ± 73.7 | MV0 (Sample II first-layer median) |

## Pipeline provenance and reproducibility

The entire pipeline is version-controlled in the repository `SzeChunYiu/ccb-testbeam`. The S00 reproduction study records SHA256 checksums for all 110 input ROOT files and the output pulse table. The MC validation pipeline is executed via SLURM job scripts on the LUNARC cluster (LU48 partition) and produces self-contained report directories under `reports/sampleI_II_trigger_split_<timestamp>/` that include JSON summaries, NPZ data arrays, and publication-ready PNG figures. The digitizer pipeline is invoked through a unified CLI (`ccb-mc-validation`) that resolves study dependencies, manages random seeds for reproducibility, and writes a machine-readable manifest of all outputs.
