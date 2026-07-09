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

## Pipeline execution environment

### 5.1 LUNARC cluster configuration

The analysis pipeline is executed on the LUNARC high-performance computing cluster at Lund University. The SLURM job scripts (under `geant4/jobs/`) request resources from the LU48 partition:

```
#SBATCH -A lu2026-2-51
#SBATCH -p lu48
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH -t 00:25:00
```

Each job runs on a single node with 4 CPU cores and a 25-minute wall time. The full trigger-split pipeline (MC truth analysis of 1 million events, data analysis of 640,737 pulses, and data/MC comparison with 10 plots) completes within the 25-minute allocation. The Python environment is the `hibeam_env` conda environment located at `/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/`, which provides NumPy, SciPy, pandas, scikit-learn, uproot, Matplotlib, and PyTorch.

### 5.2 Data flow architecture

The pipeline's data flow follows a directed acyclic graph (DAG) structure:

```
raw ROOT (110 files, 810 MB)
    |
    v
01_build_pulse_table_from_root.py
    |
    v
s00_selected_b_pulses.csv.gz (640,737 rows, ~50 MB compressed)
    |
    +---> Timing branch: CFD20 -> timewalk -> residuals -> sigma_68
    |
    +---> Pile-up branch: live10 -> tau_eff -> R_max -> two-pulse recovery
    |
    +---> PID branch: B2/B4 amplitudes -> deltaE-E plane -> AUC
    |
    +---> ML branch: PCA/AE embeddings -> classifiers -> leakage controls

MC truth (output_krakow_1M.root, 677 MB)
    |
    v
MV0 digitizer (configs/mc_validation/base.yaml)
    |
    v
Synthetic waveforms (1M events, 18-sample ADC)
    |
    v
Identical analysis pipeline (same scripts, same configs)
    |
    v
Truth-labelled results -> data/MC comparison (MV1-MV6)
```

Each intermediate data product is stored in a versioned format (CSV with gzip compression for the pulse table, NPZ for NumPy arrays, JSON for structured results, PNG for figures). No intermediate product exceeds 100 MB, ensuring that the full pipeline can be rerun from scratch on a single LUNARC node.

### 5.3 Random seed management

Reproducibility of stochastic algorithms (bootstrap resampling, train/test splitting, GMM initialisation, neural network weight initialisation) is ensured by fixed random seeds configured in the base YAML:

```
seeds:
  global: 424242
  split: 1701
  bootstrap: 9001
```

The global seed initialises the NumPy random state at the start of each script. The split seed is used for train/test splits, ensuring that the same events are assigned to training and test sets across pipeline runs. The bootstrap seed initialises the resampling for confidence interval computation. All three seeds are recorded in the output manifest, enabling exact reproduction of any stochastic result.

### 5.4 Error handling and data quality

The pipeline includes automated data quality checks at each stage:

- **Input validation:** The `audit_truth_tree()` function in `src/ccb_mc_validation/io/root_truth.py` verifies that the expected branches (Sci_bar_LayerID, Sci_bar_PDG, Sci_bar_EDep, Sci_bar_Time) are present in the ROOT file and that the data types match the schema. Missing or malformed branches raise an `InputNotFoundError` or `SchemaMismatchError` with a descriptive message.

- **Run-level QC:** Baseline mean and RMS are computed per run. Runs with baseline shift >3 sigma from the global mean or RMS >2 times the global median are flagged and excluded from analysis (run 43 is the only exclusion in the current dataset).

- **Study dependency resolution:** The MC validation CLI resolves study dependencies automatically. If MV4 (timing) is requested but MV0 (digitizer) has not been run, the pipeline raises a `StudyBlockedError` indicating the missing prerequisite. This prevents downstream studies from running on unvalidated digitizer output.

- **Output integrity:** Each study writes a JSON manifest recording the git commit hash, the resolved configuration, the random seeds, the input file paths with SHA256 checksums, and the output file list. The manifest is the authoritative record of the study's execution environment and can be used to detect bit-level changes in upstream data or code.

## Pulse reconstruction algorithm

### 6.1 Baseline subtraction

The baseline subtraction algorithm computes the median of the first 4 ADC samples for each waveform:

```
Function compute_baseline(waveform):
    pretrigger = waveform[0:4]  # ADC samples 0-3
    baseline = median(pretrigger)
    return baseline, waveform - baseline
```

The median is preferred over the mean because it is robust to single-sample outliers: a pre-trigger pile-up tail or an electronic noise spike that affects one sample does not bias the median, whereas it would shift the mean. The pre-trigger window of 4 samples (40 ns) is chosen as a compromise between statistical precision (more samples reduce the baseline RMS) and contamination risk (later samples may be affected by the rising edge of the pulse or by a preceding pulse tail).

The baseline RMS is approximately 50-80 ADC, measured from the pre-trigger samples of isolated pulses in low-rate runs. This is the fundamental noise floor for amplitude and timing measurements.

### 6.2 CFD time extraction

The constant-fraction discriminator (CFD) algorithm determines the pulse arrival time by finding the sample at which the waveform crosses a fixed fraction (20%) of its peak amplitude:

```
Function cfd_time(waveform, fraction=0.2):
    amplitude = max(waveform)
    threshold = fraction * amplitude
    peak_sample = argmax(waveform)
    # Search backward from peak for threshold crossing
    for i in range(peak_sample, 0, -1):
        if waveform[i] <= threshold and waveform[i-1] > threshold:
            # Linear interpolation between samples i-1 and i
            t_cfd = i - 1 + (waveform[i-1] - threshold) / (waveform[i-1] - waveform[i])
            return t_cfd  # in sample units (10 ns per sample)
    return 0.0  # No crossing found (should not happen for selected pulses)
```

The linear interpolation between the two samples bracketing the threshold crossing provides sub-sample timing precision. The effective time resolution of the CFD algorithm, limited by the 50-80 ADC noise RMS and the approximately 500 ADC/sample rising-edge slope, is approximately 50/500 * 10 ns = 1 ns, consistent with the measured sigma_68 of 1.85 ns for single-stave CFD timing.

### 6.3 Optimal filter

The optimal filter (OF) is an alternative time pickoff that correlates the full waveform with a template pulse shape:

```
Function optimal_filter_time(waveform, template):
    # template: average pulse shape (18 samples), normalised to unit amplitude
    # Compute cross-correlation at sub-sample shifts
    best_t = 0.0
    best_chi2 = inf
    for t_shift in linspace(-2.0, 2.0, 41):  # +/-2 samples, 0.1 sample steps
        shifted_template = interpolate(template, t_shift)
        scale = sum(waveform * shifted_template) / sum(shifted_template^2)
        chi2 = sum((waveform - scale * shifted_template)^2)
        if chi2 < best_chi2:
            best_chi2 = chi2
            best_t = t_shift
    return best_t
```

The OF provides better noise rejection than the CFD (it uses all 18 samples rather than just the 2 samples bracketing the threshold), but it is sensitive to pulse shape variations: a saturated or pile-up-distorted pulse has a different shape from the template, and the OF fit can converge to a biased time. For this reason, the CFD is the canonical pickoff method (sigma_68 = 1.85 ns), while the OF is used as a cross-check (sigma_68 = 2.89 ns, worse due to shape sensitivity).

### 6.4 Template construction

The average pulse template is constructed from a high-purity sample of isolated, high-amplitude pulses:

```
Function build_template(pulse_table, n_pulses=5000):
    # Select isolated pulses: no other selected pulse within +/- 50 ns
    # in the same event and stave
    isolated = filter(pulse_table, isolation_cut)
    # Select high-amplitude pulses: amplitude > 4000 ADC (unsaturated, good SNR)
    high_amp = filter(isolated, amplitude > 4000)
    # Randomly sample n_pulses
    sample = random_sample(high_amp, n_pulses)
    # Align at CFD time and average
    aligned_waveforms = []
    for pulse in sample:
        waveform = load_waveform(pulse.run, pulse.eventno, pulse.stave)
        t_cfd = cfd_time(waveform)
        aligned = shift_waveform(waveform, -t_cfd)  # align CFD time to t=0
        aligned_waveforms.append(aligned)
    template = mean(aligned_waveforms, axis=0)
    return template / max(template)  # normalise to unit amplitude
```

The template is constructed per stave and per run group (Sample I calibration, Sample II calibration) to account for subtle differences in pulse shape arising from SiPM gain variations and WLS fibre coupling differences. The template construction is performed once and the templates are stored as NPZ files for use by downstream timing and shape analyses.
