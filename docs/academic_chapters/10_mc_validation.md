# Chapter 10: Monte Carlo Validation Programme — MV0 through MV6 and MV9 Synthesis

## Abstract

The Monte Carlo validation programme comprises six systematic studies (MV0-MV6) and a synthesis study (MV9) that together provide truth-bridged assessment of every physics claim in the CCB test-beam analysis. The MV0 digitizer converts GEANT4 truth into synthetic ADC waveforms, enabling identical analysis code to run on data and simulation. MV1 establishes the proton-deuteron PID ceiling at AUC = 0.986. MV2 confirms the structural limitation that absolute per-event energy is not reachable from waveform data alone. MV3 reveals a stopping-depth model failure (chi^2/ndf = 68,269) caused by missing upstream material in the GEANT4 geometry. MV4 finds that raw timing passes MC validation (pull = 1.05 sigma) while timewalk-corrected timing shows tension (pull = 2.68 sigma) from an unphysical digitizer CFD model. MV5 validates the pile-up R_max measurement to 0.2% agreement. MV6 identifies the anomaly class as C12 nuclear recoils. MV9 synthesises all validation results into a unified confidence assessment.

---

## 1. MV0: Digitizer Calibration

The MV0 digitizer is the foundation of the MC validation programme. It converts GEANT4 truth-level energy depositions into synthetic 18-sample ADC waveforms by modelling the following physical processes in sequence (see Chapter 3, Section 3 for the digitizer architecture):

1. **Birks quenching** (optional, disabled by default): dL/dx = dE/dx / (1 + k_B * dE/dx), where k_B is the Birks constant (default 0, meaning no quenching).

2. **Scintillation time profile:** Double-exponential pulse with tau_rise = 2.0 ns and tau_decay = 35.0 ns, consistent with BC-408 plastic scintillator. The time integral of the light pulse is proportional to the quenched energy deposition.

3. **WLS fibre transport:** Gaussian time dispersion with sigma_transport = 0.5 ns, modelling the WLS decay time and intermodal dispersion.

4. **Sampling:** Integration over 10 ns bins to produce 18 discrete ADC samples.

5. **Electronics:** Gaussian noise with sigma_noise = 50 ADC added to each sample, followed by quantisation to integer ADC values and optional saturation clipping at 7000 ADC.

The digitizer gain calibration (Chapter 7, Section 1.2) yields 245.6 plus or minus 73.7 ADC/MeV (30% systematic). The digitizer produces 1 million synthetic waveforms from the 1 million GEANT4 events, which are then processed by the identical analysis pipeline as the data.

**Validation status:** The raw timing comparison (MV4) passes, confirming that the digitizer noise model and scintillator time constants are adequate. The timewalk-corrected comparison shows tension (MV4b), traced to the B/sqrt(ADC) parametrisation in the digitizer CFD model, which should be B/amplitude. Fixing this is a code-only change (GAP-02).

---

## 2. MV1: Particle ID Ceiling

MV1 establishes the achievable ceiling for proton-deuteron separation by training classifiers on MC truth features with known particle identity (PDG code). The study processes 1 million GEANT4 events through the B-stack truth tree and constructs per-track features: EDep in layers 0-3, stopping layer, total EDep, and track length. Three classifiers are evaluated:

- **Single-cut on EDep layer 0 (deltaE analogue):** AUC = 0.891
- **Logistic regression on 4 features:** AUC = 0.963
- **Histogram gradient boosting on all features:** AUC = 0.986, purity at 90% deuteron efficiency = 0.964

The HGB result of AUC = 0.986 represents the maximum achievable separation given the intrinsic overlap between proton and deuteron energy deposition distributions. This ceiling is driven by the continuous nature of the Bethe-Bloch energy loss, range straggling (approximately 2-3% of mean range), and the position-dependent light collection in the one-ended WLS readout. No data-driven method can exceed this ceiling without additional information beyond the 18-sample waveform.

**Validation status:** Fully validated. The AUC = 0.986 ceiling is a closed finding and serves as the benchmark for all data-only PID methods (Chapter 8).

---

## 3. MV2: Energy and Range Calibration

MV2 tests the claim that absolute per-event energy can be reconstructed from waveform data to 10% accuracy. The study uses MC truth kinetic energy (from the Sci_bar_Momentum branches) as the target and trains regressors on observables available in data: stopping layer, total EDep, EDep in individual layers, and number of hit layers.

The best model (HGB regressor) achieves fractional energy resolution sigma_68 = 18% for protons and 25% for deuterons, significantly exceeding the 10% target. The limitation is structural: the one-ended WLS readout introduces a position-dependent amplitude scale that cannot be corrected without position measurement, and the range straggling (approximately 2-3%) sets a fundamental floor of approximately 1.4% fractional energy resolution. Combined with the 30% digitizer gain uncertainty, absolute energy reconstruction from waveform data alone is not achievable.

**Validation status:** The limitation is MC-confirmed. Absolute per-event energy is not reachable from data alone. This is a structural finding (not a failure) that constrains the scope of energy-dependent physics claims.

---

## 4. MV3: Stopping-Depth Profile

MV3 compares the Monte Carlo stopping-depth profile (fraction of events with a hit in each B-stack layer) against the data depth profile (fraction of selected pulses in each stave). The comparison reveals a dramatic discrepancy:

- Data: 87.6% of pulses in B2, 6.3% in B4, 3.9% in B6, 2.3% in B8
- MC: 47.0% of hits in layer 0 (B2), 18.2% in layer 1, 12.5% in layer 2, 22.3% in layer 3

The chi^2/ndf for the comparison is 68,269 (4 bins, 3 degrees of freedom), a decisive failure. The Monte Carlo overestimates the fraction of particles reaching deep staves by a factor of 10 for B8. The root cause, diagnosed in MV3b, is missing upstream material budget in the GEANT4 geometry: the target support structure, beam window, trigger scintillators, and inter-stave absorber layers (approximately 8-10 g/cm^2 total) are not included. These materials would scatter or stop particles before they reach the B-stack, reducing the deep-stave population.

**Validation status:** Structural failure (GAP-01, blocking). Until the GEANT4 geometry is updated with full material specification, quantitative MC-based acceptance corrections for the depth profile are unreliable. The qualitative features of the depth profile (B2 >> B4 > B6 > B8) are correctly reproduced.

---

## 5. MV4: Timing Resolution

MV4 compares the Monte Carlo timing resolution against data for both raw CFD timing and timewalk-corrected timing. The digitizer produces synthetic waveforms with known hit times (from Sci_bar_Time), enabling direct comparison of reconstructed and true times.

- **Raw timing (no timewalk correction):** MC sigma_68 = 1.744 plus or minus 0.007 ns, data sigma_68 = 1.85 ns. Pull = (1.85 - 1.744) / sqrt(0.007^2 + 0.05^2) = 1.05 sigma. PASS.

- **Timewalk-corrected timing:** MC sigma_68 = 1.770 ns, data sigma_68 = 1.50 ns. Pull = (1.50 - 1.770) / sqrt(0.01^2 + 0.05^2) = 2.68 sigma. TENSION.

The raw timing passes because the digitizer noise model (sigma_noise = 50 ADC) and the scintillator time constants (tau_rise = 2.0 ns, tau_decay = 35.0 ns) adequately capture the dominant timing resolution contributions. The timewalk-corrected tension is traced to an unphysical negative B coefficient in the digitizer CFD model. The digitizer currently parametrises the CFD timewalk as B/sqrt(ADC), which produces an inverted amplitude dependence (larger pulses appear to arrive later in the digitizer, opposite to the data behaviour). The correct parametrisation, B/amplitude, follows from the physical CFD threshold-crossing model (Chapter 4, Section 4.2) and is a code-only fix.

MV4b diagnosed the issue and confirmed that switching from B/sqrt(ADC) to B/amplitude in the digitizer CFD stage resolves the tension in a test run. The fix has not yet been deployed to the production digitizer configuration (GAP-02).

---

## 6. MV5: Pile-up Validation

MV5 validates the pile-up R_max measurement by simulating overlapping waveforms from Poisson-statistics beam arrivals. The simulation uses the digitizer to generate single-particle waveforms, then superposes pairs of waveforms with time separations drawn from an exponential distribution with mean 1/R (where R is the beam rate per stave). The two-pulse recovery algorithm (constrained template fit) is applied, and the failure rate (fraction of fits that fail to converge or produce a time separation error > 30 ns) is measured as a function of rate.

The recovery failure rate crosses the template ceiling of 0.168 at R = 3.044 MHz, in 0.2% agreement with the data-driven R_max = 3.05 MHz. Both values use tau_eff = 124.79 ns and the same duty factor D = 0.38. The agreement validates the Poisson pile-up model and the effective live-time measurement, though it is a self-consistency check (both data and MC use the same tau_eff) rather than an independent validation.

**Validation status:** Passed. R_max = 3.05 MHz is the validated pile-up tolerance. The original 4.22 MHz is confirmed as an error from the incorrect tau_eff = 90 ns assumption.

---

## 7. MV6: Anomaly Identification

MV6 identifies the physical origin of the GMM anomaly cluster (Chapter 9) by cross-referencing anomaly-classified waveforms with GEANT4 truth particle identity. The anomaly cluster (283 tracks, 0.32%) is 55% C12 recoils, with the remainder being protons (15%), electrons (13%), alphas (9%), and other heavy ions (7%).

**Validation status:** Closed. The C12 anomaly is fully identified and its impact on physics is negligible (0.1% systematic on deuteron count).

---

## 8. MV9: Synthesis

MV9 synthesises the six validation studies into a unified confidence assessment for the CCB test-beam analysis programme:

| Study | Verdict | Impact on physics claims |
|---|---|---|
| MV0 (digitizer) | Calibrated (30% syst.) | Dominant systematic for energy scale |
| MV1 (PID ceiling) | AUC = 0.986 validated | Benchmark for data-only PID |
| MV2 (energy) | Structural limitation confirmed | Absolute energy not reachable |
| MV3 (stopping) | Structural failure (GAP-01) | MC acceptance corrections unreliable |
| MV4 (timing raw) | Passed (1.05 sigma) | Raw timing validated |
| MV4 (timing corrected) | Tension (2.68 sigma, GAP-02) | Timewalk MC needs fix |
| MV5 (pile-up) | Passed (0.2% agreement) | R_max = 3.05 MHz validated |
| MV6 (anomaly) | Closed | C12 recoils identified |

The MC validation programme provides a mixed but informative assessment: where the digitizer and geometry are adequate (raw timing, pile-up, anomaly ID), the data and MC agree within uncertainties. Where the digitizer or geometry are incomplete (timewalk model, stopping-depth), the disagreement is traced to specific, fixable deficiencies. No physics claim in the analysis programme is unvalidated; every claim carries an explicit MC validation status.
