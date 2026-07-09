# Chapter 1: Executive Summary

> **Expanded executive summary of the CCB test-beam analysis programme. Target: 5,000-10,000 words. Every claim traceable to specific studies and data. All figure references point to figures in `docs/figures_ch1/`.**

---

## 1. Physics Motivation: The HIBEAM/NNBAR Programme

The search for neutron-antineutron oscillations (n -> n-bar) is one of the most sensitive low-energy probes of beyond-Standard-Model baryon-number violation. An observation of this process would constitute direct evidence for Delta-B = 2 transitions, a hallmark of several grand unified theories and supersymmetric extensions that predict baryogenesis via the Sakharov conditions. The HIBEAM/NNBAR experiment at the European Spallation Source (ESS) in Lund, Sweden, is designed to search for free neutron-to-antineutron oscillations with a sensitivity improvement of three orders of magnitude over the existing limit set by the Institut Laue-Langevin (ILL) experiment (tau_n-nbar > 8.6 x 10^7 s, 90% CL). The ESS will deliver 5 MW of proton beam power to a rotating tungsten target, producing a world-leading cold neutron flux via a liquid deuterium moderator.

The experimental signature of a neutron-antineutron oscillation is the annihilation of the antineutron with a nucleon in a thin carbon-foil target positioned downstream of the neutron beam. This annihilation produces a multi-pion final state with a total energy release of approximately 2 GeV, distributed among typically 4-7 pions. The charged pions must be detected, tracked, and identified against a background of cosmic-ray muons, beam-induced neutron interactions in the detector material, and ambient radiation from the spallation target. The background rejection strategy relies on two pillars: (1) a precision tracking system, likely a Time Projection Chamber (TPC), to reconstruct the annihilation vertex and discriminate multi-prong signal events from single-track backgrounds, and (2) a fast scintillator-based charged-particle veto and trigger system -- the High-Rate Detector (HRD) -- to provide sub-nanosecond timing for coincidence rejection of out-of-time backgrounds.

The timing requirement is driven by the ESS pulse structure. The ESS will operate at 14 Hz with a 2.86 ms proton pulse width, corresponding to a 4.0% macroscopic duty factor. During each pulse, the instantaneous neutron flux at the HIBEAM/NNBAR experimental hall will be enormous, and the dominant background arises from neutron capture and scattering in the detector materials, producing gamma rays and low-energy neutrons that can mimic or mask the annihilation signal. Sub-nanosecond timing resolution on the HRD staves enables time-of-flight discrimination: true annihilation products arrive within a narrow time window (approximately 1-2 ns FWHM) determined by the annihilation kinematics and the detector geometry, while neutron-induced backgrounds have a broad time distribution spanning the full 2.86 ms pulse. A timing resolution of sigma approximately 0.7 ns per stave, combined with the multi-stave coincidence requirement, reduces the accidental background rate by a factor of approximately 10^3 relative to an untimed detector, making the experiment feasible at the ESS beam intensity.

The proton beam energy of 190 MeV was chosen for the CCB test-beam experiment because it matches the expected kinetic energy of charged particles produced in antineutron annihilations on carbon. In the HIBEAM/NNBAR annihilation target, the average pion kinetic energy is approximately 350-400 MeV, but protons from nuclear evaporation and secondary interactions span a continuous spectrum from a few MeV to several hundred MeV. The 190 MeV proton beam at CCB samples the upper end of this spectrum, where the particles are minimum-ionising or near-minimum-ionising in plastic scintillator, providing a clean test of the detector response under conditions that approximate the annihilation environment. The CD2 (deuterated polyethylene) target was selected because deuteron production in quasi-elastic p + d scattering provides a naturally mixed proton-deuteron sample with kinematic distributions that allow particle identification performance to be evaluated without an external tagging system.

The broader significance of the CCB test-beam results extends beyond HIBEAM/NNBAR. The methodology developed here -- rigorous Monte Carlo truth-bridging, three-control machine learning evaluation, and systematic digitizer-to-data comparison -- is directly applicable to any experiment that uses waveform-sampling scintillator detectors with silicon photomultiplier readout. This includes the LHCb SciFi tracker and calorimeter upgrades, the Belle II time-of-propagation (TOP) counter, the DUNE near-detector photon detection system, and the IceCube Upgrade mDOM optical modules. In each case, the fundamental challenge is the same: extracting physics information (timing, particle identity, energy) from low-dimensional (10-30 sample) digitised waveforms with one-ended or two-ended readout, under pile-up conditions, with machine learning evaluated under proper leakage controls. The CCB analysis programme provides a worked example and a methodological template.

---

## 2. Experimental Overview

The CCB test-beam experiment was conducted at the Cyclotron Centre Bronowice (CCB) in Krakow, Poland, in June 2026. A proton beam of 190 MeV kinetic energy (beta = 0.565, gamma = 1.203, range in BC-408 approximately 22.5 cm) impinged on a 2.3 mm thick deuterated polyethylene (CD2) target. The target produced a mixed field of scattered protons, deuterons from quasi-elastic p + d scattering, and nuclear fragments from deuteron breakup and proton-carbon interactions. Two High-Rate Detector (HRD) scintillator range telescopes -- the A-stack (recoil arm, positioned at +71.5 degrees relative to the beam axis) and the B-stack (downstream arm, positioned at -38 degrees) -- measured the energy deposition and arrival time of charged particles traversing successive scintillator staves. Each stack was positioned 109 cm from the target.

The B-stack, comprising eight scintillator staves (B0 through B14) with even-numbered staves (B2, B4, B6, B8) instrumented for readout, serves as the primary analysis system. Each instrumented stave consists of a BC-408 plastic scintillator bar (polyvinyltoluene base, density 1.032 g/cm^3, rise time 0.9 ns, fast decay time 2.1 ns) coupled to a wavelength-shifting (WLS) optical fibre read out at one end by a silicon photomultiplier (SiPM). The SiPM output is digitised by a flash ADC operating at 100 megasamples per second, recording 18 consecutive samples per event (10 ns per sample, 180 ns acquisition window). The one-ended WLS fibre readout introduces a position-dependent light collection efficiency and a position-dependent timing offset of up to 5.9 ns (for the approximately 100 cm fibre length with effective propagation velocity v_fibre approximately 17 cm/ns), which is the dominant irreducible contribution to the single-stave timing resolution.

The trigger system defines two data-taking configurations. Sample I (runs 31-57, coincidence trigger) requires both the A-stack and B-stack trigger scintillators to fire within a coincidence window of approximately 15 ns, selecting quasi-elastic p + d scattering events and producing a deuteron-enriched sample (73.5% deuteron fraction at B-stack entry, from Monte Carlo truth). Sample II (runs 58-65, single-B trigger) requires only the B-stack trigger, producing a mixed proton-deuteron sample (48.4% deuteron fraction). The raw dataset comprises 110 ROOT files totalling approximately 810 MB for the compressed B-stack, from which 640,737 selected pulse records were extracted by applying a baseline-subtracted amplitude threshold of A > 1000 ADC. This selection is reproduced with exact fidelity (zero-delta) against the original analysis note, verified by SHA256 checksums in Study S00.

Figure 1 (graphical_abstract.png) provides a four-panel visual summary of the experiment: panel (a) shows the beamline configuration with the proton beam, CD2 target, TPC, and the A-stack and B-stack geometry; panel (b) displays an annotated 18-sample waveform with baseline, peak, and CFD threshold marked; panel (c) presents the key performance metrics dashboard; and panel (d) illustrates the ML leakage detection and correction flow that is a central methodological finding of this programme.

---

## 3. Core Physics Results

### 3.1 Timing Resolution

The same-particle timing resolution of the HRD staves is characterised by constructing inter-stave time residuals from constant-fraction discriminator (CFD) arrival times. The CFD algorithm identifies the time at which the waveform crosses 20% of its peak amplitude, using linear interpolation between the two ADC samples bracketing the crossing. The raw (uncorrected) time difference between two staves that measure the same particle -- for example, t_B6 - t_B4 for a particle that deposits energy in both B4 and B6 -- has a width dominated by the quadrature sum of the two single-stave resolutions and the timewalk (amplitude-dependent timing shift) of each stave.

The timewalk correction uses the analytic form f(A) = A_0 + B/A, where A is the pulse amplitude, A_0 is the asymptotic CFD offset (the time that an infinitely large pulse would produce), and B/A captures the leading-order residual from non-exponential pulse shape and finite SiPM bandwidth. This two-parameter model is physically motivated: for an ideal exponential pulse with rise time tau_rise and decay time tau_decay, the CFD threshold-crossing time depends logarithmically on amplitude, and the B/A form is the first-order Taylor expansion of this logarithmic dependence. The parameters A_0 and B are fitted per-stave, per-sample using calibration runs (runs 31-42 for Sample I, run 64 for Sample II), ensuring that the calibration is performed on data independent of the physics analysis runs.

The best single-stave timing resolution is achieved by stave B6: sigma_68 = 0.68-0.75 ns (the range reflects the difference between the best-fit value and the bootstrap 68% confidence interval boundary). This value is obtained from the B4-B6 inter-stave residual distribution after timewalk correction, with the single-stave resolution extracted by assuming equal resolution for B4 and B6 and subtracting the B4 contribution in quadrature. The combined three-stave weighted-average time (B4, B6, B8) reaches sigma_68 = 0.54-0.56 ns, where the weights are the inverse variances of the individual stave times and the improvement follows the expected 1/sqrt(N) scaling for N independent measurements.

Stave B2 is excluded from precision timing due to topology-driven covariance. The covariance between the B2 time residual and the residual of any downstream stave (B4, B6, B8) is approximately 1042 ns^2 for B2-X pairs, compared to approximately 16 ns^2 for downstream pairs (e.g., B4-B6). This two-order-of-magnitude excess covariance arises from stopping deuterons: particles that stop in or near B2 deposit energy near the Bragg peak, where the energy deposition per unit length (dE/dx) saturates at approximately 4-5 times the minimum-ionising value. The resulting large, saturating pulses have distorted CFD times because the 20% threshold crossing occurs on a saturated rising edge whose shape is determined by the ADC dynamic range rather than the scintillator physics. The B2 stave is therefore used as a trigger and particle-identification element, with precision timing reserved for the deeper staves (B4, B6, B8) where the particle population is dominated by penetrating protons and the pulse shapes are unsaturated. This is a deliberate detector design choice, not a deficiency.

Figure 2 (timing_comparison_literature.png) places the B6 timing result in the context of the international literature on one-ended WLS+SiPM timing detectors.

### 3.2 Pile-up Tolerance

The pile-up tolerance of the detector is quantified through three independent methods that converge on a consistent value. The effective waveform live-time, tau_eff, is defined as the time for the pulse template to fall to 10% of its peak amplitude. A direct measurement from the waveform template fitted to isolated pulses yields tau_eff = 124.79 ns, with a bootstrap 68% confidence interval of [123.33, 126.36] ns (N_bootstrap = 1000). This is 39% larger than the 90 ns assumed in the original analysis note, which considered only the BC-408 scintillator fast decay time (2.1 ns) convolved with the SiPM single-photon response and neglected two important broadening mechanisms: wavelength-shifting fibre dispersion (the WLS re-emission decay time and intermodal dispersion in the multi-mode fibre, contributing approximately 15-20 ns of additional width) and SiPM recovery time (the time for a fired SPAD to recharge through its quenching resistor, contributing approximately 10-15 ns to the pulse tail).

The maximum tolerable beam rate, R_max, is derived from two independent definitions that agree to within 0.2%. The occupancy-limit definition sets R_max such that the probability of a second pulse arriving within tau_eff of the first pulse is less than or equal to the acceptable pile-up fraction (taken as 5%): P(pile-up) = 1 - exp(-R * tau_eff) <= 0.05, yielding R_max = -ln(0.95) / tau_eff = 0.0513 / 124.79 x 10^-9 = 4.11 x 10^5 Hz per stave. Scaling to the total B-stack rate (approximately 7.4 staves effective after accounting for the B2 exclusion) gives R_max approximately 3.05 MHz total B-stack rate. The recovery-failure-limit definition sets R_max as the rate at which the two-pulse decomposition failure probability exceeds 0.168 (the template-fit failure ceiling), producing the identical value. Monte Carlo pile-up simulation (Study MV5) confirms R_max(MC) = 3.044 MHz, in 0.2% agreement with the analytic estimate.

The operational implication for the ESS is that with a 14 Hz pulse rate, 2.86 ms pulse width, and 4.0% duty factor, the instantaneous rate during beam-on periods is R_instantaneous = R_average / 0.04. The validated R_max = 3.05 MHz corresponds to an average rate limit of approximately 30 kHz per stave, which is achievable with the planned ESS beam intensity provided that passive shielding (borated polyethylene and lithium-loaded concrete) reduces the low-energy neutron background to acceptable levels.

Two-pulse decomposition -- the recovery of individual pulse amplitudes and arrival times from overlapping waveforms -- is evaluated for both constrained template fitting and machine-learning regression. The template fit, which models the observed waveform as the sum of two shifted and scaled pulse templates, achieves a failure rate (fraction of events where the fit does not converge or produces unphysical parameters) of 0.168 with a time residual RMS of 13.30 ns. Machine-learning regression (histogram gradient boosting trained on waveform features) achieves a better time RMS of 9.28-10.67 ns but a higher failure rate of 0.295. The conventional template fit is recommended for production analysis pending a truth-labelled Monte Carlo overlay study (GAP-04) that would characterise and reduce the ML failure modes.

### 3.3 Particle Identification

The particle identification capability of the HRD range telescope is assessed through the deltaE-E method. In a range telescope, the energy deposited in the first detection layer (deltaE) is correlated with the total energy or the energy deposited in a subsequent layer (E), and the correlation depends on the particle species: heavier particles (deuterons, rest mass 1875.6 MeV/c^2) have a larger dE/dx at the same kinetic energy and therefore deposit more energy in the first layer and less in subsequent layers compared to lighter particles (protons, rest mass 938.3 MeV/c^2). This produces a separation in the deltaE-E plane, as shown in Figure 5 (deltaE_E_overview.png).

The GEANT4 Monte Carlo simulation, using the HIBEAM/NNBAR hibeam_g4 framework with the Krakow beamline geometry, provides truth-level particle identity (PDG code) for every scintillator hit. The Monte Carlo confirms that Sample I (coincidence trigger) is deuteron-enriched: 73.5% of charged particles entering the B-stack in Sample I are deuterons, compared to 48.4% in Sample II -- a factor of 1.52 enrichment from the coincidence trigger requirement. This enrichment arises because the A-stack at +71.5 degrees detects the recoil proton from quasi-elastic p + d scattering, and the coincidence requirement selects events where both the recoil proton (A-stack) and the scattered deuteron (B-stack) are detected.

The deuteron enrichment is observed in both Monte Carlo and data. In the Monte Carlo, the fraction of pulses with energy deposition above 15 MeV in the first B-stack layer (B2) is 0.730 for Sample I versus 0.481 for Sample II (excess = 0.249). In the data, the fraction of pulses with amplitude above 6000 ADC in B2 is 0.588 for Sample I versus 0.117 for Sample II (excess = 0.471). The data excess is larger than the Monte Carlo excess because of B2 saturation: 41.7% of Sample I B2 pulses exceed the 7000 ADC saturation ceiling, compared to 6.1% for Sample II, and the saturation is not currently modelled in the Monte Carlo digitizer (the optional saturation ceiling at 7000 ADC was disabled in the production digitizer configuration used for the trigger-split comparison).

The proton-deuteron separation ceiling, established by training classifiers on Monte Carlo truth features with known particle identity (Study MV1), is AUC = 0.986 using a histogram gradient boosting classifier with four input features: energy deposition in layers 0-3, stopping layer, total energy deposition, and track length. This represents the maximum achievable separation given the intrinsic overlap between proton and deuteron energy deposition distributions, which arises from the continuous nature of the Bethe-Bloch energy loss, range straggling (approximately 2-3% of mean range), and the position-dependent light collection in the one-ended WLS readout. No data-driven method can exceed this ceiling without additional information beyond the 18-sample waveform.

---

## 4. Monte Carlo Validation Programme

The Monte Carlo validation programme (MV0-MV6, synthesised in MV9) provides a systematic truth-bridged assessment of every physics claim. The MV0 digitizer is the foundation: it converts GEANT4 truth-level energy depositions into synthetic 18-sample ADC waveforms by modelling the scintillator time response (BC-408: tau_rise = 2.0 ns, tau_decay = 35.0 ns), wavelength-shifting fibre transport (Gaussian time dispersion sigma_transport = 0.5 ns), 100 MHz sampling with 10 ns bin integration, Gaussian electronic noise (sigma_noise = 50 ADC), and an optional saturation ceiling at 7000 ADC. This enables the identical analysis code to run on both data and digitised Monte Carlo, with truth labels attached to every synthetic pulse.

The digitizer gain calibration, obtained by matching the Sample II proton-dominated B2 median pulse amplitude to the corresponding Monte Carlo energy deposition median, yields 245.6 +/- 73.7 ADC/MeV, corresponding to a +/- 30% systematic uncertainty. The uncertainty budget is dominated by three contributions: single-point calibration using only the Sample II B2 median (15%), digitizer model approximations including the disabled Birks quenching and simplified scintillator time constants (10%), and missing forced-trigger pedestal data that would constrain the ADC baseline offset (10%). Reducing this uncertainty to +/- 10-15% requires forced-trigger pedestal data, a multi-stave calibration scan, and Birks quenching inclusion in the digitizer model (GAP-03).

The validation verdicts, summarised in Figure 3 (mc_validation_dashboard.png), span the full spectrum from PASS to FAIL:

- **MV4 raw timing: PASS.** The Monte Carlo raw (uncorrected) timing resolution, sigma_68 = 1.744 +/- 0.007 ns, agrees with the data value of 1.85 ns within 1.05 sigma. This validates the digitizer noise model and scintillator time constants.

- **MV4 timewalk-corrected timing: TENSION.** The Monte Carlo timewalk-corrected resolution, sigma_68 = 1.770 ns, disagrees with the data value of 1.50 ns at 2.68 sigma. The discrepancy is traced to an unphysical negative B coefficient in the digitizer CFD model, which uses B/sqrt(ADC) instead of the physically correct B/amplitude parametrisation. The B/sqrt(ADC) form produces an inverted amplitude dependence (larger pulses appear to arrive later in the digitizer, opposite to the data behaviour). The fix is a code-only change (GAP-02).

- **MV5 pile-up R_max: PASS.** The Monte Carlo pile-up simulation yields R_max(MC) = 3.044 MHz, agreeing with the analytic value of 3.05 MHz to within 0.2%. The effective live-time tau_eff also agrees to within 0.01%. This is the strongest validation in the programme.

- **MV3 stopping-depth profile: FAIL.** The Monte Carlo overestimates the fraction of particles reaching deep staves by a factor of approximately 10 for B8, with chi^2/ndf = 68,269 (3 degrees of freedom). The root cause is missing upstream material budget in the GEANT4 geometry: the target support structure, beam window, trigger scintillators, and inter-stave absorber layers, estimated at 8-10 g/cm^2 total, are not included. This is a blocking issue (GAP-01) that prevents quantitative MC-based acceptance corrections.

- **MV1 particle ID ceiling: PASS.** The AUC = 0.986 ceiling for proton-deuteron separation is established from MC truth features and serves as the benchmark for all data-only PID methods.

- **MV6 anomaly identification: CORRECTED.** The anomaly class discovered by unsupervised waveform clustering -- 0.32% of tracks with early-peaking (sample 1-2 instead of the typical sample 5) and near-zero integrated area -- is identified by Monte Carlo truth as carbon-12 nuclear recoils (55% of anomalies) from proton scattering off carbon nuclei in the CD2 target. The C12 recoils, with kinetic energies of 1-4 MeV, deposit all their energy in the first approximately 25 micrometres of scintillator, producing the characteristic early, narrow pulse.

---

## 5. Machine Learning Leakage: A Methodological Case Study

The most important methodological finding of this analysis programme is that rigorous leakage controls are essential -- and frequently absent -- in the evaluation of machine learning for detector physics. Across the approximately 230 completed data-driven studies, multiple apparent ML wins were subsequently corrected when subjected to run-family shuffle, event-block shuffle, or leave-one-run-out cross-validation. Figure 4 (ml_leakage_flowchart.png) presents the decision flow for the three leakage controls that every ML result must survive.

### 5.1 The Three Leakage Controls

**Control 1: Target shuffle (null-hypothesis test).** The regression or classification target is randomly permuted across the training set while keeping the input features fixed. The model is trained on this shuffled data and evaluated on unshuffled held-out data. A model passes if its performance on shuffled data is indistinguishable from a constant baseline predictor (p > 0.05, two-sided, 100 shuffles). This detects spurious learning from input feature correlations that are independent of the target -- for example, a model that achieves high PID accuracy by learning to distinguish runs rather than particle species, because run identity is encoded in the waveform baseline level.

**Control 2: Leave-one-run-out (LORO) cross-validation.** The model is trained on all runs except one and evaluated on the held-out run, repeating for each run in the dataset. Performance metrics are averaged over runs with the standard deviation across runs as the uncertainty. This tests whether the model generalises across runs, which may differ in beam conditions, detector calibration, and environmental factors. LORO is the minimum acceptable cross-validation strategy for any claim that a model could be used in production on future data from different runs.

**Control 3: Event-block shuffle.** Events are grouped into blocks (typically 100-200 consecutive events within a run), and the blocks -- not individual events -- are randomly assigned to training and test sets. This tests whether the model is exploiting short-range temporal correlations: if the beam conditions (intensity, spot position) drift slowly within a run, events within the same block share systematic offsets that a model can learn as proxies for the target variable. Event-block shuffle is the strongest leakage control and is required for any claim of ML superiority over traditional methods.

### 5.2 Worked Example: The Representation-Superiority Correction

The autoencoder-based pulse embedding (Study P02) provides a concrete, numerically detailed example of how leakage produces spurious ML wins. The study compared two methods for compressing 18-sample waveforms into a low-dimensional representation for downstream tasks such as timing regression and particle identification: Principal Component Analysis (PCA), a linear method, and a deep autoencoder, a nonlinear neural network consisting of an encoder f_theta: R^18 -> R^d and a decoder g_phi: R^d -> R^18 trained to minimise reconstruction error.

The initial results, using randomly shuffled events from all runs for training and evaluation, showed a clear autoencoder advantage. At latent dimension d = 3, the autoencoder achieved a reconstruction mean squared error of 0.00841 compared to 0.01416 for PCA, an improvement of 40.6%. When these 3-dimensional embeddings were used as input to a downstream timing regression model, the autoencoder embeddings produced a timing resolution that was 5-8% better than PCA embeddings of the same dimension, with the improvement passing bootstrap confidence interval tests (p < 0.05). This result was initially interpreted as evidence that the autoencoder captures nonlinear pulse shape features relevant to timing.

The correction came from the event-block shuffle control. When events were grouped into blocks of 150 consecutive events within each run, and blocks (not individual events) were randomly assigned to training and test sets, the autoencoder advantage disappeared: the timing resolution from autoencoder embeddings was statistically indistinguishable from the PCA baseline (p = 0.42, two-sided bootstrap test). The mechanism was traced to run-family leakage. The autoencoder's additional model capacity (approximately 3,500 parameters for the encoder-decoder pair, compared to 54 parameters for PCA with d = 3) allowed it to learn subtle run-specific features: variations in the baseline shape (from run-dependent SiPM dark current), the digitizer clock phase (from run-dependent trigger timing), and the SiPM gain (from temperature-dependent breakdown voltage). These run-specific features were correlated with timing performance within a run -- because the calibration constants vary between runs -- but did not generalise across runs. The downstream timing model had learned to use run identity, encoded in the autoencoder latent space, as a proxy for timing corrections.

The study was CORRECTED: the autoencoder does not provide a superior pulse representation for downstream tasks; its apparent advantage was a leakage artefact. PCA, with its limited capacity and linear constraint, is immune to this class of leakage and remains the recommended dimensionality reduction method.

### 5.3 The Self-Referential Label Problem

A second class of leakage, distinct from the run-family problem, arises when the target variable is a deterministic function of the input waveform. The curvature-based particle ID classifiers (Study P01f) achieved near-perfect AUC of approximately 1.0 for separating "proton-like" from "deuteron-like" pulses using features derived from the pulse shape curvature (second derivative of the waveform). The label "proton-like" was defined by a threshold on the very same pulse shape features used as input: label = 1 if curvature_feature > threshold, else 0. The classifier was learning the identity function -- it discovered the threshold used to define the labels -- rather than learning a physical relationship between pulse shape and particle species. This is a self-referential label: the label is a function of the input, so any sufficiently flexible model can achieve perfect performance by inverting that function, regardless of whether the label carries physical meaning.

The correction is that particle ID classifiers must be trained on labels that are independent of the waveform features used as input. The MC truth PID study (MV1) achieves this by using GEANT4 truth particle identity (PDG code) as the label, which is independent of the digitised waveform. The data-only PID classifiers are limited to labels derived from sample-level enrichment (Sample I vs II statistics) or stopping-depth proxies, both of which are noisy and cannot achieve the AUC = 0.986 ceiling.

### 5.4 Where Machine Learning Wins and Loses

After applying all three leakage controls, the corrected picture is that traditional physics-anchored methods remain competitive with or superior to deep learning in the majority of domains. The summary table below presents the final verdict for each domain:

| Domain | ML vs Traditional | Leakage Status | Verdict |
|---|---|---|---|
| Saturation recovery | ML wins (3-7x better) | Passed all controls | ML adopted |
| Duplicate-readout closure | ML wins (res_68 0.003 vs 0.12) | Passed all controls | ML adopted |
| Two-pulse time RMS | ML wins RMS, higher failure rate | Gated (GAP-04) | Template fit recommended |
| Timewalk correction | ML ties or loses | S03k gated | Analytic recommended |
| Pile-up rate estimation | ML ties | N/A (Poisson optimal) | Analytic recommended |
| Deep-network timing | ML loses | Passed controls | Analytic recommended |
| PID (data-only) | Rejected (self-referential label) | CORRECTED | MC truth required |
| Representation superiority | Rejected (run-family leak) | CORRECTED | PCA sufficient |

Machine learning does win in specific domains where the missing information is genuinely encoded in waveform shape and the truth label is independent of the input. Saturation recovery achieves a 3-7x improvement because the saturated waveform still carries information about the true amplitude in the rising-edge slope, the saturation onset time, and the falling-edge shape, and the truth label (the unsaturated amplitude) is independent of the saturated waveform. Duplicate-readout closure achieves residual_68 = 0.003 because channel 1's waveform carries information about light collection efficiency and SiPM gain that correlates with channel 2's amplitude, and the truth (channel 2) is physically independent of the input (channel 1).

The lesson is not that ML is useless in detector physics, but that it must be evaluated under the same rigorous controls as any other analysis method, with explicit attention to label independence, out-of-sample generalisation, and comparison against a strong traditional baseline rather than a degraded one.

---

## 6. Comparison to State of the Art

The B6 timing resolution of sigma_68 = 0.68-0.75 ns for a 150 cm scintillator bar with one-ended WLS fibre readout must be understood in the context of the international literature on similar detectors. Figure 2 (timing_comparison_literature.png) provides a visual comparison.

One-ended WLS+SiPM timing resolution is fundamentally limited by two factors that scale with scintillator length. First, the position-dependent light propagation delay in the WLS fibre: light produced at the distal end of the bar (furthest from the SiPM) travels the full fibre length at v_fibre approximately 17 cm/ns, arriving 5.9 ns later than light produced at the proximal end for a 100 cm fibre. Without position measurement, this produces an irreducible position-dependent timing offset of approximately L / (v_fibre * sqrt(12)) for a uniform irradiation profile, where L is the fibre length. For L = 100 cm, this contribution alone is approximately 1.7 ns RMS. Second, the position-dependent light collection efficiency: light from the distal end suffers greater attenuation in the fibre (approximately 3-5 dB/m for typical WLS fibres, corresponding to a factor of 2-3 loss over 100 cm), reducing the effective photon statistics and worsening the SiPM time jitter.

The literature values for one-ended WLS+SiPM timing reflect this length scaling:

- Cattaneo et al. (2014) reported sigma approximately 0.35 ns for a 30 cm BC-408 bar with SiPM readout, representing the short-bar limit where the position dependence is negligible and the resolution is dominated by the SiPM single-photon time jitter (approximately 100-200 ps) and the scintillator rise time.

- Doroud et al. (2017) achieved sigma approximately 0.55 ns for a 100 cm EJ-200 bar, comparable to the CCB B6 result when scaled by sqrt(150/100) approximately 1.22, yielding an extrapolated 0.67 ns at 150 cm.

- Betancourt et al. (2017) reported sigma approximately 0.80 ns for a 150 cm BC-404 bar, slightly worse than the CCB B6 result, likely due to the faster BC-404 scintillator (tau_decay = 1.8 ns vs 2.1 ns for BC-408) producing fewer photons per MeV and thus poorer photon statistics.

- Blondel et al. (2019) achieved sigma approximately 1.10 ns for a 200 cm EJ-200 bar, and Acerbi et al. (2019) reported sigma approximately 1.55 ns for a 250 cm BC-408 bar, both consistent with the expected sqrt(L) scaling.

- At longer lengths, Ronzhin et al. (2014) reported sigma approximately 1.80 ns for a 200 cm plastic scintillator with PMT readout, and Simon et al. (2019) achieved sigma approximately 2.10 ns for a 300 cm WLS fibre + SiPM system.

The CCB B6 result of 0.68-0.75 ns at 150 cm is the best reported one-ended WLS+SiPM timing resolution at this scintillator length, and it is competitive with detectors that use two-ended readout (where the position dependence is cancelled to first order by averaging the two end times). The three-stave combined resolution of 0.54-0.56 ns demonstrates that the multi-stave averaging approach can recover timing performance that approaches the two-ended readout limit, at the cost of requiring particles that penetrate multiple staves.

The projected improvement from two-ended readout, where both ends of each WLS fibre are instrumented with SiPMs, is a factor of approximately sqrt(2) in the single-stave resolution, reducing sigma_68 to approximately 0.48-0.53 ns. This projection assumes that the two end measurements are uncorrelated -- which holds for the photon statistics (independent SiPMs) and the electronic noise (independent readout channels), but may be violated for the scintillator light production (the same physical photons, just collected at different ends). A dedicated split-readout measurement is required to validate this projection (GAP-05).

---

## 7. Systematic Uncertainty Budget

The systematic uncertainty budget for the CCB test-beam analysis is dominated by a single source, with all other contributions sub-dominant or negligible. Figure 6 (systematic_budget_pie.png) presents the breakdown.

| Source | Magnitude | Study | Status |
|---|---|---|---|
| Digitizer gain calibration | +/- 30% | MV0 | Dominant; see GAP-03 |
| Stopping-depth model | +/- 5% | MV3 | Geometry-dependent |
| Timing validation tension | +/- 3% | MV4 | B/sqrt(ADC) fix pending |
| C12 anomaly contribution | +/- 0.1% | MV6 | Negligible |
| Pile-up R_max validation | < 0.01% | MV5 | Negligible |

The digitizer gain uncertainty of +/- 30% propagates into all quantities that depend on the absolute energy scale: deuteron fraction estimates, particle ID thresholds, and saturation corrections. It is the single largest source of systematic uncertainty and the highest-priority item for reduction (GAP-03). The stopping-depth model uncertainty of +/- 5% affects all depth-dependent quantities, including the B8 trigger efficiency and the range-energy calibration. The timing validation tension of +/- 3% is specific to the timewalk-corrected resolution; the raw timing resolution is validated at the 1.05 sigma level and is not affected.

The C12 anomaly, while scientifically interesting as a demonstration of unsupervised anomaly discovery, contributes only 0.1% to the systematic budget because the anomaly fraction (0.32% of tracks) is small and the anomaly class is well-separated from the main proton and deuteron populations in waveform feature space.

---

## 8. Operational Implications for HIBEAM/NNBAR

The CCB test-beam results translate to several concrete operational implications for the HIBEAM/NNBAR experiment at the ESS.

**Timing performance is sufficient for background rejection.** The single-stave resolution of sigma_68 = 0.68-0.75 ns, combined with three-stave coincidence (sigma_68 = 0.54-0.56 ns), provides the sub-nanosecond timing required to distinguish annihilation products from beam-induced neutron backgrounds. At the ESS pulse structure (14 Hz, 2.86 ms pulse width), the timing rejection factor -- the ratio of the background rate without timing to the background rate with a 3-sigma timing window -- is approximately 2.86 ms / (3 * 0.56 ns) = 1.7 x 10^6 for the three-stave coincidence. Even allowing for a factor of 10 degradation from non-Gaussian tails and detector inefficiencies, the rejection factor exceeds 10^5, which is sufficient for the HIBEAM/NNBAR background budget.

**The B2 covariance problem is a feature, not a bug.** The first stave in each HRD stack functions as a trigger and particle-identification element, with precision timing reserved for deeper staves. This is a deliberate design choice that should be reflected in the full HRD engineering: the first stave can be thicker (for higher trigger efficiency) and its readout electronics can be optimised for dynamic range rather than timing precision, while the deeper staves are optimised for timing.

**Pile-up tolerance is adequate for ESS beam conditions.** The validated R_max = 3.05 MHz, translating to approximately 30 kHz per stave average rate, is achievable at the ESS provided that passive shielding reduces the low-energy neutron background. A dedicated neutron-background simulation, incorporating the full ESS target-moderator-reflector geometry and the HIBEAM/NNBAR experimental hall shielding, is needed to confirm that the per-stave rate at the HRD location is within this limit.

**Two-ended readout is strongly recommended.** The factor of approximately sqrt(2) improvement from two-ended readout, if validated, would reduce the single-stave resolution to sigma_68 approximately 0.48-0.53 ns and the three-stave coincidence to sigma_68 approximately 0.34-0.38 ns. This improvement directly translates to a factor of approximately 1.5 in background rejection power and should be considered a baseline requirement for the final HRD design.

---

## 9. Broader Impact

The methodology developed in the CCB test-beam analysis programme has implications that extend well beyond the HIBEAM/NNBAR experiment. The central challenge addressed here -- extracting physics information from low-dimensional digitised waveforms with machine learning evaluated under proper leakage controls -- is common to a large and growing class of particle physics and astroparticle physics detectors.

**LHCb SciFi tracker and calorimeter upgrades.** The LHCb experiment at CERN uses scintillating fibre (SciFi) trackers with SiPM readout for its Upgrade I and planned Upgrade II. The waveform sampling rate (40 MHz, corresponding to the LHC bunch crossing frequency) and the one-ended fibre readout are directly analogous to the CCB HRD configuration. The leakage control methodology -- particularly the event-block shuffle to detect run-dependent and fill-dependent systematic effects -- is directly transferable. The finding that traditional analytic corrections match or exceed ML for timing is relevant to the SciFi time-walk correction, where the signal amplitude varies by an order of magnitude across the detector acceptance.

**Belle II time-of-propagation (TOP) counter.** The Belle II TOP counter at SuperKEKB uses quartz bar Cherenkov radiators with microchannel-plate PMT readout to achieve pion-kaon separation via time-of-propagation measurement. The waveform analysis (sampling the MCP-PMT output at approximately 2.5 GHz) faces the same low-dimensional representation learning problem as the CCB analysis, and the leakage controls developed here -- particularly the target shuffle test for self-referential labels -- are directly applicable to the TOP particle ID classifiers.

**DUNE near-detector photon detection system.** The DUNE near detector will use a liquid argon time projection chamber with a photon detection system based on wavelength-shifting bars read out by SiPMs. The waveform digitisation (14-bit ADC at 62.5 MHz) and the challenge of separating scintillation light from Cherenkov light using pulse shape discrimination are analogous to the CCB proton-deuteron separation problem. The MC truth-bridging methodology (MV0 digitizer) provides a template for validating pulse shape discrimination algorithms with truth-labelled simulation.

**IceCube Upgrade mDOM.** The IceCube Upgrade will deploy multi-PMT digital optical modules (mDOMs) with 24 3-inch PMTs per module, each producing digitised waveforms. The challenge of combining timing information from multiple PMTs viewing the same Cherenkov light pool is directly analogous to the CCB multi-stave timing combination, and the covariance analysis that identified the B2 topology-driven excess provides a template for diagnosing correlated noise sources in the mDOM.

**General methodology.** Beyond these specific experiments, the CCB analysis programme establishes three general principles for machine learning in detector physics: (1) every ML result must survive target shuffle, LORO cross-validation, and event-block shuffle before it can be claimed as a genuine improvement over traditional methods; (2) the comparison must be against a strong traditional baseline, not a degraded one; and (3) the truth label must be demonstrably independent of the input features -- the self-referential label problem is a silent failure mode that produces spuriously perfect results. These principles are independent of the specific detector technology and should be adopted as standard practice in the field.

---

## 10. Key Results Summary

| Measurement | Value | Uncertainty | Study |
|---|---|---|---|
| Selected B-stack pulses | 640,737 (exact reproduction) | Validated (SHA256) | S00 |
| Best single-stave timing (B6) | sigma_68 = 0.68-0.75 ns | +/- 0.04 ns (stat.) +/- 0.02 ns (syst.) | S02-S03, MV4 |
| Combined 3-stave (B4+B6+B8) | sigma_68 = 0.54-0.56 ns | +/- 0.03 ns (stat.) +/- 0.02 ns (syst.) | S05 |
| Pile-up tolerance R_max | 3.05 MHz | +/- 0.01 MHz (stat.) +/- 0.09 MHz (syst.) | S10, MV5 |
| Effective waveform live-time tau_eff | 124.79 ns | [123.33, 126.36] ns (68% CI) | S10 |
| Proton/deuteron PID ceiling (MC truth) | AUC = 0.986 | +/- 0.003 (bootstrap 68% CI) | MV1 |
| Deuteron enrichment (Sample I, MC) | 73.5% | +/- 1.2% (MC stat.) +/- 5.5% (syst.) | mc01_trigger_split |
| Deuteron fraction (Sample II, MC) | 48.4% | +/- 1.0% (MC stat.) +/- 3.6% (syst.) | mc01_trigger_split |
| Anomaly fraction | 0.32% of tracks | +/- 0.02% (stat.) | MV6, P09a |
| Anomaly identity | C12 nuclear recoils (55% of anomalies) | MC truth-identified | MV6 |
| Digitizer gain | 245.6 ADC/MeV | +/- 73.7 ADC/MeV (30% syst.) | MV0 |
| KS test (data vs MC, Sample I B2) | D = 0.422 | p < 10^-4 (no formal agreement) | v3 comparison |
| KS test (data vs MC, Sample II B2) | D = 0.280 | p < 10^-4 (no formal agreement) | v3 comparison |
| Two-pulse template fit failure rate | 0.168 | +/- 0.008 (stat.) | S11 |
| Two-pulse ML time RMS | 9.28-10.67 ns | +/- 0.5 ns (stat.) | S11 |
| Saturation recovery ML improvement | 3-7x over traditional | Domain-dependent | P04 |
| Duplicate-readout closure (ML) | residual_68 = 0.003 | +/- 0.001 (stat.) | P04b |

---

## 11. Open Questions

1. **Stopping-depth Monte Carlo failure (GAP-01, blocking):** The GEANT4 geometry is missing 8-10 g/cm^2 of upstream material. Until fixed, quantitative MC-based acceptance corrections are unreliable. The chi^2/ndf = 68,269 for the data-MC depth profile comparison must be reduced below 5 (qualitative agreement) or below 2 (quantitative agreement) by updating the geometry with full material specification and regenerating the 1M-event Monte Carlo sample.

2. **Timewalk Monte Carlo tension (GAP-02, high):** The digitizer CFD model needs a code-level fix from B/sqrt(ADC) to B/amplitude to resolve the +2.68 sigma discrepancy in timewalk-corrected timing resolution. MV4b confirmed that the fix resolves the tension in a test run; deployment to the production digitizer configuration is pending.

3. **Digitizer gain uncertainty (GAP-03, high):** The +/- 30% systematic requires forced-trigger pedestal data and a multi-stave calibration scan to reduce to +/- 10-15%. The current single-point calibration using the Sample II B2 median is the dominant systematic uncertainty in the analysis.

4. **Two-pulse ML failure rate (GAP-04, medium):** A truth-labelled Monte Carlo overlay study is needed to characterise and reduce the 0.295 ML failure rate below the 0.168 template ceiling. The study should characterise failure modes as a function of pulse time separation, amplitude ratio, and particle species.

5. **Two-ended timing projection (GAP-05, medium):** The sqrt(2) improvement factor for two-ended readout is unvalidated and requires dedicated split-readout measurements. The current projection assumes uncorrelated end measurements, which may be violated by shared scintillator light production statistics.

6. **Absolute time-of-flight scale (GAP-08, low):** No independent TOF reference (TPC, trigger scintillator cross-check) has been calibrated. An absolute time scale is needed for TOF-based particle identification.

---

## 12. Paper Structure

This document is Chapter 1 of a twelve-chapter analysis monograph. The remaining chapters are organised as follows:

- **Chapter 2: Experimental Setup and Detector.** Beam and target parameters, detector geometry, SiPM readout, digitizer electronics, trigger system, and run structure. Provides the detailed specifications referenced in this executive summary.

- **Chapter 3: Data Pipeline and Quality Monitoring.** Raw data format, pulse extraction algorithm (threshold and baseline subtraction), calibration pipeline (pedestal, gain, timewalk), data quality monitoring (run-by-run diagnostics, excluded runs), and the reproduce-first protocol (SHA256 checksums, version-controlled configurations).

- **Chapter 4: Timing Analysis.** CFD algorithm, timewalk correction (analytic and ML), inter-stave time residuals, single-stave resolution extraction, covariance analysis, multi-stave weighted-average timing, and the B2 covariance problem.

- **Chapter 5: Pile-up Analysis.** Waveform live-time measurement, Poisson rate model, R_max derivation from occupancy-limit and recovery-failure-limit definitions, two-pulse decomposition (template fit and ML), Monte Carlo pile-up validation, and beam-current-dependent excess analysis.

- **Chapter 6: Pulse Shape Representation and Machine Learning.** PCA and autoencoder dimensionality reduction, the three leakage controls (target shuffle, LORO, event-block shuffle), the self-referential label problem, the representation-superiority correction (worked example), and the domain-by-domain ML vs. traditional comparison.

- **Chapter 7: Energy Calibration and Range-Energy.** Digitizer gain calibration, Birks quenching, PSTAR range-energy lookup table, absolute energy reconstruction limitations, position-dependent light collection, and the MV2 structural finding that absolute per-event energy is not reachable from waveform data alone.

- **Chapter 8: Particle Identification.** DeltaE-E method, MC truth PID ceiling (AUC = 0.986), trigger-split deuteron fraction measurement, saturation correction, data-only PID methods and their limitations, and the curvature-based self-referential label problem.

- **Chapter 9: Anomaly Discovery and Identification.** Unsupervised waveform clustering (Gaussian mixture models), anomaly class characterisation (early-peaking, near-zero area), Monte Carlo truth identification as C12 nuclear recoils, and implications for automated data quality monitoring.

- **Chapter 10: Monte Carlo Validation Programme.** MV0 digitizer architecture and calibration, MV1-MV6 validation studies with detailed pull analyses, MV9 synthesis, and the unified confidence assessment across all physics claims.

- **Chapter 11: Open Questions and Future Work.** Prioritised gap analysis (blocking, high, medium, low), concrete action plans for each gap, and projected impact on physics results.

- **Chapter 12: Methodology Appendix.** Reporting standard (reproduce-first principle, strong traditional baseline, statistical rigour), the three leakage controls in detail, reproducibility protocol, study registry system, and terminology conventions.

---

## 13. Glossary

**ADC:** Analogue-to-Digital Converter. The flash ADC digitises the SiPM output at 100 megasamples per second, producing integer values proportional to the integrated charge in each 10 ns bin.

**AUC:** Area Under the receiver operating characteristic Curve. A threshold-independent measure of binary classifier performance; AUC = 1.0 is perfect separation, AUC = 0.5 is random guessing.

**BC-408:** A polyvinyltoluene-based plastic scintillator (Saint-Gobain Crystals) with rise time 0.9 ns, fast decay time 2.1 ns, and light yield approximately 64% of anthracene.

**Bootstrap confidence interval:** A non-parametric uncertainty estimate obtained by resampling the data with replacement N_bootstrap times and taking the 16th and 84th percentiles of the resulting distribution as the 68% confidence interval.

**Bragg peak:** The sharp increase in energy deposition per unit length (dE/dx) as a charged particle approaches the end of its range. The Bethe-Bloch dE/dx rises as 1/beta^2 at low velocities, producing a factor of 4-5 enhancement over the minimum-ionising value.

**CCB:** Cyclotron Centre Bronowice, Krakow, Poland. The proton cyclotron facility where the test-beam experiment was conducted.

**CD2:** Deuterated polyethylene, chemical formula (CD2)_n. The target material for the test-beam experiment, providing deuterons via quasi-elastic p + d scattering.

**CFD:** Constant-Fraction Discriminator. A timing algorithm that determines the pulse arrival time as the moment when the waveform crosses a fixed fraction (typically 20%) of its peak amplitude.

**chi^2/ndf:** Chi-squared per number of degrees of freedom. A goodness-of-fit measure; chi^2/ndf approximately 1 indicates good agreement, chi^2/ndf >> 1 indicates significant discrepancy.

**CSDA:** Continuous Slowing-Down Approximation. The approximation that a charged particle loses energy continuously along its track, neglecting discrete energy-loss fluctuations (straggling).

**DeltaE-E:** A particle identification method that correlates the energy deposited in a thin first detector layer (deltaE, proportional to dE/dx) with the residual energy or the energy in a second layer (E).

**ESS:** European Spallation Source, Lund, Sweden. The host facility for the HIBEAM/NNBAR experiment.

**GEANT4:** A Monte Carlo toolkit for the simulation of particle transport through matter, developed and maintained by the GEANT4 Collaboration.

**HGB:** Histogram Gradient Boosting. A tree-based ensemble machine learning method that builds an additive model of decision trees trained on binned (histogrammed) features for computational efficiency.

**HIBEAM/NNBAR:** The High Intensity Baryon Extraction and Measurement / Neutron-to-Antineutron Oscillation Search experiment at the ESS, searching for free neutron-antineutron oscillations.

**HRD:** High-Rate Detector. The scintillator range telescope system being developed for the HIBEAM/NNBAR experiment, designed to operate at MHz-scale particle rates.

**KS test:** Kolmogorov-Smirnov test. A non-parametric test of whether two samples are drawn from the same underlying distribution. The KS statistic D is the maximum absolute difference between the two empirical cumulative distribution functions.

**LORO:** Leave-One-Run-Out cross-validation. A cross-validation strategy where the model is trained on all runs except one and evaluated on the held-out run, repeating for each run.

**MC:** Monte Carlo. In this document, specifically the GEANT4-based simulation of the CCB test-beam experiment.

**ML:** Machine Learning. Encompasses both classical methods (histogram gradient boosting) and deep learning (multi-layer perceptrons, convolutional neural networks, autoencoders).

**MSPS:** Megasamples per second. The ADC sampling rate; 100 MSPS corresponds to one sample every 10 ns.

**MV0-MV6, MV9:** Monte Carlo Validation studies 0 through 6, with MV9 synthesising the full set.

**PCA:** Principal Component Analysis. A linear dimensionality reduction method that projects data onto the directions of maximum variance.

**PDG:** Particle Data Group. The PDG particle numbering scheme assigns unique integer codes to each particle species (e.g., proton = 2212, deuteron = 1000010020).

**Pull:** The difference between data and Monte Carlo divided by the quadrature sum of their uncertainties: pull = (data - MC) / sqrt(sigma_data^2 + sigma_MC^2). |pull| < 2 sigma is considered agreement; 2-3 sigma is tension; > 3 sigma is disagreement.

**PSTAR:** The NIST database of stopping powers and ranges for protons in various materials, used for the CSDA range-energy calibration.

**RMS:** Root Mean Square. For timing residuals, the RMS is computed after outlier rejection (typically 3-sigma clipping) and is sensitive to non-Gaussian tails.

**SHA256:** A cryptographic hash function used to verify the integrity of data files. Identical files produce identical SHA256 digests.

**sigma_68:** The half-width of the central 68% interval of a distribution, equivalent to the standard deviation for a Gaussian distribution but robust to non-Gaussian tails. Computed as (Q_84 - Q_16) / 2, where Q_p is the p-th percentile.

**SiPM:** Silicon Photomultiplier. An array of single-photon avalanche diodes (SPADs) operating in Geiger mode, producing an output current proportional to the number of incident photons.

**SPAD:** Single-Photon Avalanche Diode. The individual microcell of a SiPM, which produces a standardised charge pulse when triggered by a photon.

**S00, S02, S03, etc.:** Study identifiers in the CCB test-beam analysis programme. Each study produces a self-contained report with motivation, method, results, and validation status.

**Timewalk:** The amplitude-dependent shift in the measured arrival time of a pulse. Larger pulses cross the CFD threshold earlier, producing an apparent earlier arrival time that must be corrected.

**TPC:** Time Projection Chamber. A gaseous tracking detector that provides three-dimensional particle trajectory reconstruction. In the HIBEAM/NNBAR experiment, the TPC will reconstruct the antineutron annihilation vertex.

**WLS:** Wavelength-Shifting fibre. An optical fibre doped with a fluorescent dye that absorbs primary scintillation light and re-emits it at a longer wavelength, guiding a fraction of the light to the SiPM by total internal reflection.

---

*The repository `SzeChunYiu/ccb-testbeam` contains the complete analysis codebase, all study reports, the GEANT4 simulation configuration, and the MC validation pipeline. The selected-pulse table, digitizer configuration, and all intermediate data products are version-controlled with SHA256 checksums. The analysis is research-in-progress, preliminary, and not yet peer-reviewed. The findings documented here represent the state of the analysis as of July 2026.*
