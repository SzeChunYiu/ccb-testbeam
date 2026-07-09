# Chapter 7: Energy Calibration — Digitizer Gain, Birks Quenching, and Range-Energy

## Abstract

The conversion of ADC pulse amplitudes to physical energy deposition units requires calibration of the digitizer gain (ADC/MeV) and correction for the Birks quenching effect that suppresses scintillation light yield at high ionisation density. This chapter presents the MV0 digitizer gain calibration via Monte Carlo truth matching, the Birks quenching model, the PSTAR-based range-energy calibration using stopping-depth information, the structural limitation that prevents absolute per-event energy reconstruction from waveform data alone, and the systematic uncertainties that dominate energy-scale-dependent physics quantities. The digitizer gain of 245.6 plus or minus 73.7 ADC/MeV (30% systematic) is the largest single systematic in the analysis programme.

---

## 1. The Energy Reconstruction Problem

### 1.1 From ADC to MeV

The fundamental quantity measured by each HRD stave is the 18-sample ADC waveform. The pulse amplitude A (the maximum baseline-subtracted ADC value) is proportional to the scintillation light yield L, which is in turn related to the energy deposited by the charged particle in the scintillator, E_dep, through a chain of efficiency factors:

A = G * L = G * epsilon_WLS * epsilon_SiPM * L_scint(E_dep)

where:
- G is the overall digitizer gain (ADC per photoelectron or ADC per MeV-equivalent),
- epsilon_WLS is the wavelength-shifting fibre collection and transport efficiency (typically 3-10% for one-ended readout, depending on fibre geometry and optical coupling),
- epsilon_SiPM is the SiPM photon detection efficiency (typically 25-50% for modern SiPMs at the WLS emission wavelength),
- L_scint(E_dep) is the scintillation light yield, which depends nonlinearly on E_dep through Birks quenching.

The product G * epsilon_WLS * epsilon_SiPM is the quantity calibrated by the MV0 digitizer gain measurement. The individual factors are not separately determined; only their product, as a single MeV-to-ADC conversion factor, is constrained by the data-MC matching procedure.

### 1.2 The MV0 digitizer gain calibration

The gain calibration uses the GEANT4 Monte Carlo truth energy deposition as the reference. For each charged particle hit in the B-stack, the Monte Carlo records the true energy deposited E_dep (in MeV) via the Sci_bar_EDep branch. The data records the ADC amplitude A for the corresponding stave and event. By matching the Monte Carlo energy deposition distribution to the data amplitude distribution for a well-characterised reference sample, the MeV-to-ADC conversion factor is determined.

The reference sample is the Sample II (proton-dominated, single-B trigger) first B-layer (B2). This sample is chosen because:

1. Sample II is proton-dominated (48.4% deuterons at B2 entry, compared to 73.5% for Sample I), and protons in the 100-200 MeV range are near minimum-ionising in plastic scintillator (dE/dx approximately 2 MeV cm^2/g * 1.032 g/cm^3 = 2.06 MeV/cm). At minimum ionisation, the Birks quenching correction is small (kB * dE/dx approximately 0.1-0.2 mm/MeV * 2 MeV/cm = 0.002-0.004 cm = 0.02-0.04 mm, which is much less than 1), making the light yield nearly linear with energy deposition.

2. Sample II has a broader energy deposition distribution than Sample I (mean EDep 23.1 MeV vs 32.2 MeV at B2), providing a wider dynamic range for the calibration.

3. Sample II has lower B2 saturation (6.1% of pulses above 7000 ADC) than Sample I (41.7%), reducing the saturation-induced bias.

The calibration is performed by matching the median of the Monte Carlo B2 energy deposition distribution to the median of the data B2 amplitude distribution:

gain = median(A_data, B2, Sample II) / median(E_dep_MC, B2, Sample II)

The measured value is:

gain = 3662.9 ADC / 14.91 MeV = 245.6 ADC/MeV

The systematic uncertainty of plus or minus 30% (plus or minus 73.7 ADC/MeV) arises from three sources added in quadrature:

1. **Single-point calibration (plus or minus 15%):** Using only the median of one distribution (Sample II B2) rather than a multi-stave, multi-energy calibration scan. The gain may vary between staves (B2 vs B4 vs B6 vs B8) due to differences in WLS fibre coupling, SiPM gain, and electronics chain.

2. **Digitizer model approximations (plus or minus 10%):** The Monte Carlo digitizer does not include Birks quenching (kB = 0 by default), which would reduce the scintillation light yield for the higher-dE/dx deuteron population and shift the median EDep relative to the proton-dominated population. The digitizer also does not model the SiPM saturation roll-off (only a hard clip at 7000 ADC), which affects the amplitude distribution at the high end.

3. **Missing forced-trigger pedestal data (plus or minus 10%):** The baseline subtraction uses the median of ADC samples 0-3. Without forced-trigger data (events recorded with no beam, providing a true zero-energy reference), the absolute baseline level has an irreducible uncertainty of approximately 10% of the baseline RMS. A forced-trigger run in a future beam test would reduce this to approximately 5%.

The gain uncertainty propagates linearly into any physics quantity expressed in energy units. For the deuteron fraction estimation, a 30% uncertainty in the MeV-to-ADC conversion translates to a 30% uncertainty in the energy threshold used to define "deuteron-like" stopping in B2, though the deuteron fraction itself (computed from counting statistics) is less sensitive because the B2 amplitude distributions for protons and deuterons are well-separated in Sample I.

---

## 2. Birks Quenching

### 2.1 Physical mechanism

Birks quenching describes the saturation of scintillation light yield per unit energy deposition at high ionisation density. When a charged particle deposits energy in a plastic scintillator, the primary process is the excitation and ionisation of the polymer molecules (polyvinyltoluene for BC-408). The excited molecules can either decay radiatively (producing scintillation light) or interact non-radiatively with neighbouring damaged molecules (quenching centres) produced by the same particle track. The density of quenching centres is proportional to the ionisation density dE/dx, leading to the Birks saturation formula:

dL/dx = A * (dE/dx) / (1 + k_B * dE/dx)

where dL/dx is the scintillation light yield per unit path length, dE/dx is the specific energy loss (MeV/cm), A is the absolute scintillation efficiency at zero ionisation density, and k_B is the Birks constant (mm/MeV for plastic scintillator). In the limit dE/dx -> 0 (minimum-ionising particles), dL/dx -> A * dE/dx (linear response). In the limit dE/dx -> infinity (heavily ionising particles, Bragg peak), dL/dx -> A / k_B (saturated response, independent of dE/dx).

For the HRD B-stack, the relevant dE/dx ranges are:

- Minimum-ionising proton (190 MeV, through-going): dE/dx approximately 2.06 MeV/cm, Birks correction factor = 1 / (1 + 0.15 * 2.06) = 0.764 (24% light reduction).
- Stopping deuteron at Bragg peak (approximately 5 MeV residual energy): dE/dx approximately 15-20 MeV/cm, Birks correction factor = 1 / (1 + 0.15 * 15) = 0.308 (69% light reduction).
- C12 recoil (1-4 MeV): dE/dx approximately 10^4 MeV/cm, Birks correction factor = 1 / (1 + 0.15 * 10000) = 0.00067 (99.93% light reduction), consistent with the observed near-zero integrated area of C12 anomaly waveforms.

The Birks constant k_B for BC-408 plastic scintillator is approximately 0.10-0.15 mm/MeV (0.010-0.015 cm/MeV, or 0.10-0.15 g/cm^2/MeV when scaled by density). The exact value has not been independently measured for this specific detector and must be calibrated from data.

### 2.2 Calibration strategy

The Birks constant can be calibrated by exploiting the range telescope principle. For a particle that stops in the B-stack (depositing all its kinetic energy in the scintillator staves), the sum of the energy depositions in all staves equals the incident kinetic energy (minus the energy lost in passive material between staves):

sum_i E_dep_i = T_incident * f_geom

where f_geom accounts for energy lost in the WLS fibres, air gaps, and stave support structures. If T_incident is known from the beam energy (190 MeV for protons) or from two-body scattering kinematics (see Chapter 2, Section 1.3 for the deuteron energy-angle relation), the Birks constant can be determined by requiring that the Birks-corrected energy sum equals the known incident energy for stopping particles.

In practice, this calibration is coupled to the digitizer gain calibration because both affect the ADC-to-energy conversion. The current analysis treats the Birks constant as a free parameter to be determined in a combined fit with the gain, using stopping protons (B6 or B8 stops) and stopping deuterons (B2 or B4 stops) as calibration sources with known incident energies. The fit is not yet performed (GAP-03: digitizer gain uncertainty), and the default digitizer configuration runs with Birks quenching disabled (k_B = 0), acknowledging that the resulting energy scale is systematically biased for high-dE/dx particles.

---

## 3. PSTAR Range-Energy Calibration

### 3.1 The range-energy relation

For a charged particle of known species, the range R (the total path length travelled before stopping) is a monotonic function of the incident kinetic energy T. The NIST PSTAR database provides CSDA (continuous slowing-down approximation) range tables for protons and deuterons in plastic scintillator (BC-408 composition: H 8.5%, C 91.5% by weight, density 1.032 g/cm^3). These tables can be parametrised by a power-law:

R(T) = alpha * T^beta

where alpha and beta are fitted to the PSTAR data over the energy range of interest (5-200 MeV for deuterons, 10-200 MeV for protons). The fit parameters for BC-408 are:

| Species | alpha (cm/MeV^beta) | beta | Energy range (MeV) |
|---|---|---|---|
| Proton | 0.0231 | 1.74 | 10-200 |
| Deuteron | 0.0104 | 1.72 | 5-200 |

Given a measured stopping layer (the deepest stave in which the particle deposits energy above threshold), the residual range can be estimated as:

R_residual = (N_stop_layer + 0.5) * d_stave

where N_stop_layer is the index of the stopping stave (0 for B2, 1 for B4, etc.), d_stave = 4 cm is the stave-to-stave centre spacing, and the +0.5 term accounts for the fact that the particle stops, on average, halfway through the stopping stave. The incident kinetic energy is then estimated by inverting the range-energy relation:

T_reconstructed = (R_residual / alpha)^(1/beta)

### 3.2 Systematic limitations

The PSTAR range-energy method provides an energy estimate that is independent of the ADC amplitude, making it complementary to the amplitude-based energy estimate and valuable as a cross-check. However, several systematics limit its accuracy:

1. **Missing upstream material:** The GEANT4 geometry incompleteness (GAP-01, estimated 8-10 g/cm^2 missing material) means that the true energy at the B-stack entrance is lower than the nominal 190 MeV for protons (or the two-body kinematic energy for deuterons) by the energy lost in the target, trigger paddles, TPC, and air. The PSTAR range must be corrected for this upstream energy loss, but the correction is uncertain because the upstream material budget is uncertain.

2. **Passive inter-stave material:** The odd-numbered staves (B1, B3, B5, B7) are not instrumented but represent passive material (structural support, WLS fibre routing) that particles must traverse. The PSTAR range-energy relation assumes a homogeneous scintillator medium; the passive inter-stave material reduces the effective range per layer and introduces a systematic offset.

3. **Stochastic range straggling:** The CSDA range is an average quantity. Individual particles experience range straggling — statistical fluctuations in the number and energy of individual collisions — with a standard deviation of approximately 2-3% of the mean range for protons in plastic scintillator. This limits the fundamental energy resolution of the range method to sigma_T/T approximately (1/beta) * sigma_R/R approximately 0.57 * 0.025 = 1.4%.

4. **Species ambiguity:** The range-energy relation is species-dependent (proton vs deuteron). Without independent particle identification, the wrong species assumption introduces a large energy bias: using the proton range-energy relation for a deuteron overestimates the energy by a factor of approximately (alpha_p/alpha_d)^(1/beta) = (0.0231/0.0104)^(1/1.73) approximately 1.6.

### 3.3 Absolute energy limitation

Study MV2 demonstrated that absolute per-event energy reconstruction from waveform data alone is not achievable at the 10% level. The combined uncertainty from digitizer gain (30%), Birks quenching (uncalibrated), upstream material budget (uncertain), and range straggling (1.4% fundamental limit) exceeds 30% for individual particle energies. The PSTAR range-energy method, combined with stopping-depth information and species identification from the deltaE-E plane, can achieve approximately 10-15% energy resolution for identified stopping particles — sufficient for the physics goals of this analysis (sample-level particle composition, not per-event calorimetry), but not for precision energy measurement.

---

## 4. Energy Proxies and Cross-Checks

### 4.1 Integrated pulse area

The integrated pulse area (sum of baseline-subtracted ADC values over all 18 samples) provides an energy proxy that is less sensitive to saturation than the peak amplitude. For a saturating pulse (ADC clipped at approximately 7000), the peak amplitude is truncated but the pulse area continues to increase because the saturated samples contribute their ceiling value and the unsaturated samples (rising edge before saturation, falling edge after recovery) continue to grow with increasing energy. The pulse area is therefore a more linear energy estimator than the peak amplitude for heavily ionising particles, at the cost of larger noise (integration over 18 samples accumulates 18 independent noise contributions, increasing the noise RMS by sqrt(18) = 4.2 relative to the single-sample peak amplitude).

### 4.2 Template amplitude scaling

The amplitude-adaptive template method fits a scaled template pulse shape to the observed waveform. The scaling factor (template amplitude) provides an amplitude estimate that is robust to pulse shape variations because the fit uses the full waveform shape, not just the peak sample. This method is particularly useful for two-pulse decomposition (Chapter 5) and for pulses with anomalous shapes (Chapter 9).

### 4.3 Charge-based energy from SiPM current integration

If the SiPM output current were integrated by a charge-sensitive amplifier rather than sampled by a flash ADC, the integrated charge would be proportional to the total number of photoelectrons, which is proportional to the scintillation light yield (after Birks correction). The current flash ADC system with 100 MSPS sampling can approximate charge integration by summing the ADC samples (the pulse area method), but a true charge-integrating readout would achieve better signal-to-noise ratio. This is a potential upgrade path for future beam tests.

---

## 5. Systematic Uncertainty Budget

The energy-scale systematic uncertainties, ranked by magnitude:

| Source | Magnitude | Mitigation |
|---|---|---|
| Digitizer gain (MV0) | 30% | Forced-trigger pedestal, multi-stave calibration |
| Birks constant (uncalibrated) | 5-15% (dE/dx dependent) | Stopping-particle calibration |
| Missing upstream material (GAP-01) | 5-10% | GEANT4 geometry update |
| Baseline uncertainty | 5% | Forced-trigger data |
| Inter-stave gain variation | 10% | Per-stave calibration |
| Range straggling | 1.4% (fundamental) | Cannot be reduced |
| **Total (quadrature)** | **35%** | — |

The energy-scale uncertainty is the dominant systematic for deuteron fraction estimation, Birks calibration, and any analysis that converts ADC to MeV. Reducing this uncertainty is the highest-priority improvement for future beam tests (GAP-03).

---

## 6. Calibration Algorithm Implementation

### 6.1 MV0 digitizer gain calibration algorithm

The gain calibration is implemented in `scripts/mv0_calibrate_from_data.py` with the following algorithm:

```
Input: MC truth ROOT file, data pulse table CSV
Output: gain (ADC/MeV), gain_uncertainty

1. Load MC truth: for each B-stack hit, record (LayerID, PDG, EDep)
2. Filter: LayerID == 0 (B2 first layer), PDG == charged
3. Classify events into Sample I (coincidence) and Sample II (single-B)
   using the trigger mimicry algorithm (Chapter 2, Section 4.3)
4. For Sample II B2 charged hits: compute median_EDep_MC = median(EDep)
5. Load data: for each B-stack pulse, record (stave, amplitude_adc, group)
6. Filter: stave == B2, group in sample_ii_analysis
7. Compute median_ADC_data = median(amplitude_adc)
8. gain = median_ADC_data / median_EDep_MC
9. Bootstrap uncertainty:
   - Resample data and MC with replacement (N_bootstrap = 1000)
   - Recompute gain for each bootstrap sample
   - gain_uncertainty = std(gain_bootstrap)
   - Report 68% CI: [gain_lo, gain_hi]
10. Systematic components added in quadrature (see Section 1.2)
```

The bootstrap yields a statistical uncertainty of approximately 2% on the median ratio. The dominant 30% systematic is estimated from the three sources described in Section 1.2 and dominates the total uncertainty.

### 6.2 Birks correction algorithm

The Birks correction, when enabled in the digitizer, is applied per-hit before waveform synthesis:

```
Function birks_quench(edep_mev, kB=0.15):
    # edep_mev: energy deposited in MeV
    # kB: Birks constant in mm/MeV
    # dx: effective scintillator thickness per hit in mm (from GEANT4 step)
    dE_dx = edep_mev / dx  # MeV/mm
    light_yield = edep_mev / (1.0 + kB * dE_dx)
    return light_yield  # MeV-equivalent light yield
```

The effective scintillator thickness dx is not directly recorded in the current GEANT4 output format; it would require the Sci_bar_StepLength branch (not currently in the truth tree). The default digitizer configuration therefore runs with Birks quenching disabled (kB = 0), and the Birks correction is treated as a systematic uncertainty to be constrained by future calibration.

### 6.3 PSTAR parametrisation fit

The PSTAR range-energy data for protons and deuterons in BC-408 plastic scintillator are fit to a power-law using the following procedure:

```
Function fit_pstar_range(particle_species):
    Load NIST PSTAR table for {particle_species} in BC-408
    Extract (T_i, R_i) pairs for T_i in [T_min, T_max]
    Fit: log(R_i) = log(alpha) + beta * log(T_i) via linear least squares
    Return: alpha, beta, covariance_matrix
```

The fit is performed in log-log space because the power-law relation R = alpha * T^beta becomes linear: log(R) = log(alpha) + beta * log(T). The linear least-squares fit provides both the best-fit parameters and their covariance matrix, which propagates into the reconstructed energy uncertainty.

For a stopping particle observed in stave layer N_stop_layer, the reconstructed kinetic energy is:

```
Function reconstruct_energy(N_stop_layer, species, d_stave=4.0):
    R_residual = (N_stop_layer + 0.5) * d_stave  # cm
    alpha, beta = pstar_params[species]
    T_reco = (R_residual / alpha)^(1/beta)  # MeV
    # Propagate fit uncertainties
    sigma_T = T_reco * sqrt((sigma_alpha/alpha)^2 + (sigma_beta * log(R_residual/alpha))^2)
    return T_reco, sigma_T
```

The +0.5 in the residual range accounts for the particle stopping, on average, halfway through the stopping stave. A more precise estimate would use the energy deposition pattern across staves: a particle that deposits most of its energy in stave N and very little in stave N+1 likely stopped near the beginning of stave N, while a particle with a more gradual energy decrease across staves likely stopped near the end. This refinement is not implemented in the current analysis.

[1] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

[2] NIST PSTAR database, https://physics.nist.gov/PhysRefData/Star/Text/PSTAR.html.

[3] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," datasheet (2021).

[4] Knoll, G. F., Radiation Detection and Measurement, 4th ed. (Wiley, 2010), Ch. 8.

[5] Leo, W. R., Techniques for Nuclear and Particle Physics Experiments, 2nd ed. (Springer, 1994), Ch. 7.
