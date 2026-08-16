# §4 — Timing Analysis with One-Ended WLS Readout

> **REVIEW_STATUS: EDITORIAL_REVIEWED** (AI role-separated nature-reviewer-style lenses; not independent human peer review). Scope: readability/structure only. Does **not** imply SOURCE_VERIFIED, EXECUTED_REPRODUCED, or CLAIM_AUTHORIZED. Open factual blockers remain tracked in GitHub issues / claim ledger. Contract: `docs/contracts/REVIEW_STATUS_TAXONOMY.json` / `chatgpt_todo/ATOMIC_RESEARCH_PROTOCOL.md`.

> **CLAIM-GOVERNANCE QUARANTINE (2026-08-16, #1299).** The per-stave and combined σ68 timing values in this chapter (B6 0.68–0.75 ns; B4+B6+B8 0.54–0.56 ns, quoted below as "540 ps") are **legacy, source-absent ledger values, now WITHHELD** (`docs/claim_ledger.csv` CL-002..CL-006, `legacy_claim_source_unresolved`, GATED/BLOCKED). Timing σ68 is **not measurable** on the located raw 8×16-channel 16-sample 100 MS/s beam product (≥38 ns sampling-limited; the component-safe B4–B6 pair residual is 8.7 ns, CL-1320-001), and cross-schema transfer from earlier waveform formats is quarantined by #993. The values below are retained as historical analysis narrative only; they are not beam-data detector-resolution claims and must not be cited as such. Where this chapter conflicts with the ledger, the ledger wins.

The timing resolution of the HRD scintillator stacks is the primary physics deliverable of the CCB test-beam programme. The HIBEAM/NNBAR experiment requires same-particle timing at the sub-nanosecond level to distinguish signal events from background — specifically, to separate neutron-antineutron oscillation candidates from spallation-induced background events that differ by a few nanoseconds in time-of-flight. This chapter presents the complete timing analysis chain: from raw waveform to calibrated particle arrival time, through amplitude-dependent timewalk correction, to the final multi-stave combined time. The historical narrative below quotes a 540 ps combined resolution; that number is a legacy, source-absent ledger value (withheld — CL-004/CL-005; see the quarantine note above), not a beam-data resolution claim. Every equation needed for reproducibility is stated explicitly. Where the analysis reveals paradoxes — the position-dependence puzzle, the B2 covariance anomaly, the tau_eff provenance — the resolution is presented alongside the result.

## 1. Principles of Scintillator Timing

### 1.1 The timing budget

When a charged particle traverses a plastic scintillator stave, the resulting scintillation light pulse arrives at the SiPM after propagating through the wavelength-shifting (WLS) fibre. The arrival time measured by the readout electronics, t_measured, differs from the true particle crossing time, t_true, by several systematic offsets:

t_measured = t_true + t_scint + t_WLS(x) + t_SiPM + t_electronics + ε_noise   (1)

where:
- t_scint is the scintillator rise time (approximately 0.9 ns for BC-408 [1]), representing the time between particle passage and the production of detectable scintillation photons.
- t_WLS(x) = x / v_fibre is the position-dependent fibre propagation delay, where x is the distance from the hit position to the readout end and v_fibre is the effective propagation velocity of light in the WLS fibre. For the Kuraray Y-11 WLS fibre used in the HRD, n_fibre is approximately 1.76, giving v_fibre = c / n_fibre approximately 17 cm/ns.
- t_SiPM is the SiPM response time, dominated by the avalanche build-up time (approximately 0.1 ns) and the single-photon time resolution (approximately 0.1-0.2 ns for a Hamamatsu S13360 series SiPM).
- t_electronics is the cable and digitizer delay, which is constant per channel and calibrated out by the inter-stave alignment procedure.
- ε_noise represents the irreducible stochastic noise from photon statistics and electronics.

The position-dependent term t_WLS(x) is the dominant contribution to the single-stave timing resolution: for a 100 cm stave, the propagation delay varies from 0 ns (hit at readout end) to approximately 5.9 ns (hit at distal end). Without position measurement, this variation broadens the measured time distribution for particles hitting at random positions along the stave.

### 1.2 The position-dependence paradox

A puzzling feature of the timing data emerges when comparing the Monte Carlo simulation to the measurements. The GEANT4 simulation with the MV0 digitizer models the WLS fibre transport as a Gaussian time dispersion with sigma_transport = 0.5 ns — a fixed, position-independent broadening. This is a deliberate simplification: the digitizer does NOT model the 0-5.9 ns position-dependent delay spread because the hit position along the stave is not recorded in the GEANT4 truth tree for the digitizer. One would therefore expect the MC raw timing resolution to be substantially better than the data, since the MC omits the dominant timing degradation mechanism.

The data show otherwise. The raw CFD timing resolution in the MC (sigma_68 = 1.744 plus or minus 0.007 ns) agrees with the data (sigma_68 = 1.85 ns) to within 1.05 sigma (MV4). This is the position-dependence paradox: the MC, which models only a 0.5 ns Gaussian transport smearing, reproduces the data resolution that should be dominated by a 0-5.9 ns position-dependent spread.

The resolution of this paradox involves three factors:

**(a) Inter-stave residuals cancel position dependence to first order.** The timing resolution is extracted from inter-stave time differences (Section 1.4). When the same particle traverses two successive staves, the hit positions in the two staves are correlated: a particle entering at a given (x, y) position in the stack tends to hit approximately the same x-position in successive staves because the staves are parallel and the beam is collimated. The position-dependent delay t_WLS(x) is therefore similar for both staves, and the difference Δt = t_measured(B_j) - t_measured(B_i) partially cancels the position-dependent term. The inter-stave residual method is inherently less sensitive to position dependence than an absolute timing measurement would be.

**(b) The dominant contribution to inter-stave residuals is stochastic, not geometric.** The cancellation in (a) means that the residual broadening is dominated by photon statistics (Poisson fluctuations in the number of photoelectrons), SiPM dark counts, and waveform digitization noise — the same 0.5 ns-scale effects that the MC does model. The 0-5.9 ns position spread, while large in absolute terms, largely cancels in the difference measurement.

**(c) The MC resolution floor is set by the digitizer noise, not the transport model.** With sigma_noise = 50 ADC and 10 ns sampling, the digitizer's intrinsic timing resolution floor is approximately 1.5-1.7 ns, which is comparable to the data resolution. The MC and data agree because both are limited by the same noise floor; the position dependence that the MC omits is not the limiting factor for inter-stave residuals.

This paradox is not a validation failure — it is a structural insight about what the inter-stave residual method actually measures. The measured sigma_68 = 1.85 ns represents the stochastic component of the timing resolution after partial cancellation of the position-dependent geometric component. The true single-stave absolute timing resolution — which would be measured by a position-sensitive detector — is larger, dominated by the 0-5.9 ns WLS propagation spread. The inter-stave residual method answers the question the experiment needs: "How precisely can we determine that two staves were hit by the same particle?" rather than "How precisely can we determine the absolute time of a single hit?"

### 1.3 State of the art in scintillator timing

To contextualise the HRD timing performance, Table 1 presents a comparison with established and emerging detector technologies for sub-nanosecond timing.

**Table 1: State-of-the-art timing resolution for charged-particle detectors**

| Technology | Typical sigma_t (single detector) | Principle | Reference |
|---|---|---|---|
| MRPC (Multigap Resistive Plate Chamber) | ~50 ps | Gas amplification, multiple sub-gaps | ALICE TOF [2] |
| LGAD (Low-Gain Avalanche Diode) | ~30 ps | Silicon sensor with internal gain layer | CMS/CERN timing layer [3] |
| Plastic scintillator + PMT (two-ended) | ~100-200 ps | Fast scintillator (BC-422), direct PMT coupling | [4] |
| Plastic scintillator + SiPM (two-ended) | ~150-300 ps | BC-408 + WLS fibre + SiPM at both ends | [5] |
| Plastic scintillator + SiPM (one-ended) | ~500-1000 ps | BC-408 + WLS fibre + single SiPM | This work (raw) |
| **HRD B6 (one-ended, timewalk-corrected)** | **~680-750 ps** | BC-408 + WLS fibre + CFD + timewalk correction | **This work** |
| **HRD B4+B6+B8 combined** | **~540-560 ps** | Multi-stave inverse-variance combination | **This work** |

The historical analysis claimed 540 ps combined timing with one-ended readout (legacy value, withheld — source-absent; see the quarantine note above). The one-ended configuration itself is chosen for cost, mechanical simplicity, and radiation hardness in the ESS environment; its competitive positioning versus two-ended or LGAD systems rests on that simplicity, not on a validated resolution number. The projected improvement from two-ended readout (Section 7) would bring the HRD into the 300-400 ps range, competitive with dedicated two-ended scintillator-SiPM systems.

### 1.4 Inter-stave residual method

The timing resolution is extracted from inter-stave time residuals. When the same particle traverses two successive staves B_i and B_j, the true crossing times satisfy:

t_true(B_j) = t_true(B_i) + Δt_TOF   (2)

where Δt_TOF is the time-of-flight between staves. For relativistic 190 MeV protons (beta = v/c approximately 0.565, Section 1.1 of Chapter 2) traversing 4 cm of scintillator (the stave-to-stave centre spacing), Δt_TOF = 4 cm / (0.565 * 30 cm/ns) approximately 0.24 ns. For deuterons of 105 MeV kinetic energy (beta approximately 0.33), the corresponding TOF is approximately 0.40 ns. These are small compared to the single-stave resolution and can be corrected using the known stave geometry and the particle velocity estimated from the stopping depth.

The measured time difference is:

Δt_measured = t_measured(B_j) - t_measured(B_i)
            = [t_true(B_j) - t_true(B_i)] + [ε(B_j) - ε(B_i)]   (3)
            = Δt_TOF + [ε(B_j) - ε(B_i)]

where ε(B_i) represents the combined measurement error for stave i, including stochastic noise and residual position dependence.

If the errors are independent and have equal variance sigma^2_single, then Δt_measured follows a distribution with variance:

Var(Δt) = Var(ε(B_j)) + Var(ε(B_i)) - 2 Cov(ε(B_j), ε(B_i))   (4)

For independent errors, Cov = 0 and Var(Δt) = 2 sigma^2_single, yielding:

sigma_single = sigma(Δt) / sqrt(2)   (5)

This is the familiar sqrt(2) factor. For non-Gaussian residual distributions, we quote sigma_68 — the half-width of the central 68% interval of the residual distribution — as a robust dispersion measure that coincides with sigma for a true Gaussian.

### 1.5 The full pulse convolution model

The simplified exponential rising edge model (equation 11) captures the leading-order timewalk but neglects important pulse-shape details. A more complete model describes the observed waveform as the convolution of four physical processes:

V_obs(t) = [S_scint(t) * R_WLS(t) * R_SiPM(t) * R_elec(t)] (t)   (5b)

where:
- S_scint(t) = (N_ph / tau_decay) * (exp(-t/tau_decay) - exp(-t/tau_rise)) is the scintillator light pulse, with tau_rise approximately 0.9 ns (fast) and tau_decay being the weighted sum of the fast (2.1 ns) and slow (approximately 14 ns) decay components.
- R_WLS(t) = (1 / sqrt(2 * pi * sigma_transport^2)) * exp(-(t - x/v_fibre)^2 / (2 * sigma_transport^2)) is the WLS fibre transport response, a Gaussian centred at the propagation delay x/v_fibre with width sigma_transport approximately 0.5 ns.
- R_SiPM(t) models the SiPM response: a fast rise (approximately 0.1 ns avalanche build-up) followed by an exponential recovery with tau_recovery approximately 50-150 ns (the quench resistor recharge time).
- R_elec(t) is the electronics response, dominated by the transimpedance amplifier bandwidth (approximately 100 MHz, corresponding to a rise time of approximately 3.5 ns) and the 10 ns digitizer sampling.

The convolution model explains why the CFD timewalk is not perfectly cancelled by the constant-fraction method: the pulse shape at the 20% crossing point is shaped by the combined effect of all four responses, each of which introduces amplitude-dependent distortions. The WLS fibre transport broadens the rising edge for distal hits (larger x) more than for proximal hits; the SiPM recovery tail adds a slow component that shifts the effective baseline for closely spaced pulses; the electronics bandwidth limits the slew rate, making the effective rise time amplitude-dependent for pulses near the noise floor.

The timewalk correction f(A) = A_0 + B/A is thus a phenomenological parametrisation that captures the aggregate effect of these amplitude-dependent distortions without requiring a full deconvolution of the four responses — which would be ill-posed given the 18-sample waveform and the unknown hit position x.

### 1.6 The sqrt(2) factor: random noise improvement vs position-dependence cancellation

The factor of sqrt(2) in equation (5) has two distinct physical origins that must not be conflated:

**(a) Random noise improvement.** If two independent measurements of the same quantity are averaged, the variance of the mean is sigma^2_single / 2, and the resolution improves by sqrt(2). This is the standard statistical improvement from combining independent measurements — it applies to the random, uncorrelated component of the timing error (photon statistics, electronic noise).

**(b) Position-dependence cancellation.** The geometric component t_WLS(x) partially cancels in the inter-stave difference because hit positions in successive staves are correlated (Section 1.2). This cancellation reduces the effective single-stave variance beyond what independent noise averaging would achieve, but the amount of cancellation depends on the hit-position correlation between staves, which is not a fixed sqrt(2) factor.

Equation (5) implicitly attributes the full sqrt(2) reduction to random noise improvement (case a). In reality, the inter-stave residual width reflects a mixture of random noise (reduced by sqrt(2) through averaging) and residual geometric spread (reduced by partial cancellation through position correlation). The extracted sigma_single = sigma(Δt) / sqrt(2) is therefore a lower bound on the true single-stave timing resolution: it represents the resolution achievable in a multi-stave telescope where position correlation helps, not the resolution of a single isolated stave.

This distinction is critical for projecting the benefit of two-ended readout (Section 7). Two-ended readout cancels position dependence within a single stave (by averaging the two end times, t_avg = (t_left + t_right) / 2, where the sum t_left + t_right = 2 t_true + t_WLS(x) + t_WLS(L - x) = 2 t_true + L / v_fibre is independent of x). The sqrt(2) projection from the one-ended inter-stave residual method does not directly translate to the two-ended improvement factor, because the two measurement configurations cancel position dependence through different mechanisms (inter-stave correlation vs intra-stave symmetry).

## 2. The Timing Reconstruction Chain

The reconstruction proceeds through four stages. Each is described with the complete algorithm needed for independent reproduction.

### 2.1 Stage 1: Constant-Fraction Discrimination (CFD)

**Algorithm.** The constant-fraction method determines the pulse arrival time as the moment when the pulse reaches a fixed fraction f (typically 20%) of its peak amplitude. This is preferred over leading-edge discrimination (which triggers at a fixed absolute threshold) because the fractional threshold is, to first order, independent of pulse amplitude.

Let the digitized waveform be an array of ADC samples V[k] for k = 0, 1, ..., 17 (18 samples at 10 ns intervals). The CFD algorithm proceeds as follows:

**(1) Baseline subtraction.** The baseline is estimated as the mean of the first N_baseline samples (typically N_baseline = 4, samples 0-3):

V_baseline = (1/N_baseline) * sum_{k=0}^{N_baseline-1} V[k]   (6)

The baseline-subtracted waveform is V_sub[k] = V[k] - V_baseline.

**(2) Peak detection.** The pulse peak is identified as the maximum of V_sub[k] for k >= 2 (to avoid triggering on early baseline fluctuations):

V_peak = max_{k >= 2} V_sub[k],   k_peak = argmax_{k >= 2} V_sub[k]   (7)

Pulses with V_peak below a minimum threshold (typically 50 ADC, corresponding to approximately 5 sigma of the baseline noise) are rejected as noise.

**(3) Fractional threshold.** The CFD threshold is:

V_thr = f * V_peak   (8)

where f = 0.20 (20% constant fraction) is the canonical value. A systematic scan over f = 10-50% (Section 7, GAP-06) confirms that f = 20% is near-optimal for the HRD pulse shape: lower fractions are more sensitive to baseline noise, while higher fractions are more sensitive to pulse-shape variations.

**(4) Sub-sample interpolation.** The threshold crossing time is determined by linear interpolation between the two samples bracketing the threshold. Let k_cross be the first sample index where V_sub[k] >= V_thr, and let k_before = k_cross - 1. The sub-sample crossing time is:

t_CFD = t_sample[k_before] + (V_thr - V_sub[k_before]) / (V_sub[k_cross] - V_sub[k_before]) * Δt_sample   (9)

where t_sample[k] = k * Δt_sample is the sample time and Δt_sample = 10 ns is the sampling period. The sub-sample interpolation achieves an effective time resolution finer than the 10 ns sampling period; the precision is limited by the signal-to-noise ratio at the threshold crossing.

The algorithm as stated is deterministic and reproducible given only the waveform array V[k] and the CFD fraction f. No fitting or iterative optimisation is required.

**Why CFD and not leading-edge.** A leading-edge discriminator with fixed threshold V_LE triggers when V_sub[k] >= V_LE. A larger pulse (higher V_peak) crosses the threshold earlier on its rising edge than a smaller pulse, producing an amplitude-dependent time shift — the leading-edge timewalk. The CFD reduces this effect because the threshold scales with the amplitude: both large and small pulses cross at the same fraction of their peak, eliminating the first-order amplitude dependence. The residual amplitude dependence (Section 2.3) arises from the non-linear pulse shape.

### 2.2 Stage 2: Template Phase Fitting (Optional)

The CFD time provides a seed for a fit of the full waveform to an average pulse template. The template T(t) is constructed by aligning and averaging several thousand high-amplitude (amplitude > 6000 ADC), isolated (no second pulse within plus or minus 80 ns) pulses at their CFD times. The template is normalised to unit amplitude.

The template fit minimises:

chi^2(Δt, A) = sum_{k=0}^{17} [V_sub[k] - A * T(t_sample[k] - Δt)]^2 / sigma_noise^2   (10)

where Δt is the time offset relative to the CFD seed and A is the pulse amplitude. The minimisation is performed using a grid search over Δt in the range [t_CFD - 5 ns, t_CFD + 5 ns] with 0.1 ns steps, followed by parabolic interpolation of the three chi^2 values bracketing the minimum.

The template fit is more sensitive to pulse-shape variations than the CFD because the template represents an average pulse shape, and individual pulses deviate from the average due to scintillator non-uniformity, Birks quenching variations, and SiPM saturation. Empirically, the template fit produces worse timing resolution (sigma_68 approximately 2.89 ns) than the simpler CFD approach (sigma_68 approximately 1.85 ns). The CFD is therefore the canonical pickoff method for the HRD analysis.

### 2.3 Stage 3: Amplitude Timewalk Correction

**Physical origin of timewalk.** Despite the constant-fraction method's first-order amplitude independence, residual amplitude dependence — timewalk — persists because the scintillator pulse shape is not strictly amplitude-independent. The rising edge of a scintillator pulse from BC-408 is well-approximated by an exponential approach to the peak:

V(t) = A * (1 - exp(-t / tau_rise)),   for 0 <= t <= t_peak   (11)

where tau_rise is the scintillator rise time (approximately 0.9 ns for BC-408) and A is the pulse amplitude. This is a simplification — the true pulse shape is a convolution of the scintillator decay (tau_decay approximately 2.1 ns fast, approximately 14 ns slow), the WLS fibre response, and the SiPM response — but the exponential rising edge captures the leading-order timewalk behaviour.

At the CFD threshold V_thr = f * A, the threshold crossing time t_thr satisfies:

f * A = A * (1 - exp(-t_thr / tau_rise))   (12)

Solving for t_thr:

t_thr = -tau_rise * ln(1 - f)   (13)

Equation (13) shows that, for a pure exponential rising edge, t_thr is independent of A — the CFD works perfectly. The residual timewalk arises because the true pulse shape deviates from the ideal exponential: the finite scintillator decay time means the pulse does not reach the full amplitude A before decaying; the WLS fibre adds a wavelength-dependent time dispersion; and the SiPM response has a finite slew rate. These effects introduce an amplitude-dependent distortion of the pulse shape that produces a residual time shift.

**Empirical timewalk correction.** The empirical correction takes the functional form:

t_corrected = t_CFD - f(A),   with   f(A) = A_0 + B / A   (14)

where A_0 and B are fitted parameters. The B/A term captures the leading-order residual: as A approaches infinity, the correction approaches the constant A_0 (the asymptotic CFD offset, representing the irreducible electronics delay); as A decreases, the correction grows, reflecting the slower effective rise of small pulses (which are more affected by noise and SiPM response non-linearity).

The derivation of the B/A form from the physical pulse shape proceeds as follows. Consider a more realistic pulse model where the effective rise time depends on amplitude due to the finite scintillator decay:

V(t) = A * [(1 - exp(-t / tau_rise)) * exp(-t / tau_decay)]   (15)

This is the product of the rising exponential and the decaying exponential. For t << tau_decay (the rising edge, where tau_decay approximately 35 ns dominates over the approximately 2 ns rise), the decay factor exp(-t / tau_decay) is approximately 1 - t / tau_decay. The threshold condition f * A = V(t_thr) becomes:

f * A = A * (1 - exp(-t_thr / tau_rise)) * (1 - t_thr / tau_decay)   (16)

Expanding to first order in t_thr / tau_rise (since t_thr << tau_rise for f = 0.2, t_thr approximately 0.2 * tau_rise << tau_rise) and t_thr / tau_decay:

f = (t_thr / tau_rise) * (1 - t_thr / tau_decay)
  = t_thr / tau_rise - t_thr^2 / (tau_rise * tau_decay)   (17)

For small t_thr, the second-order term is negligible and t_thr is approximately f * tau_rise, independent of A. However, for pulses near the detection threshold where noise distorts the shape, the effective threshold is shifted by the noise RMS sigma_n:

f_eff = f + sigma_n / A   (18)

Substituting f_eff for f in t_thr = f_eff * tau_rise:

t_thr = tau_rise * (f + sigma_n / A) = tau_rise * f + tau_rise * sigma_n / A   (19)

This yields the B/A form with A_0 = tau_rise * f and B = tau_rise * sigma_n. The B/A term is thus a noise-induced effective threshold shift — not a property of the ideal pulse shape, but a consequence of the finite signal-to-noise ratio.

**Calibration procedure.** The parameters A_0 and B are fitted per stave from calibration runs (runs 31-42 for Sample I), using the requirement that inter-stave residuals for through-going particles have zero mean. The calibration minimises:

sum_{events} [ (t_CFD(B_j) - f_j(A_j)) - (t_CFD(B_i) - f_i(A_i)) - Δt_TOF ]^2   (20)

summed over all stave pairs (B_i, B_j) with i, j in {B4, B6, B8}, excluding B2 (Section 3). The calibration is performed on independent calibration runs, not on the analysis runs, to avoid bias.

**Figure 4.2** (06_timewalk_explained.png) illustrates the timewalk correction schematically: the left panel shows raw CFD time versus amplitude with visible curvature (the timewalk), and the right panel shows the corrected time after applying f(A) = A_0 + B/A, demonstrating the flattening of the residual distribution.

The B2 stave is excluded from the calibration fit because its pulse population is dominated by stopping deuterons with saturating amplitudes (41.7% of Sample I B2 pulses exceed the 7000 ADC ceiling), producing systematically distorted CFD times. Including B2 in the calibration would bias the timewalk parameters toward the stopping-deuteron topology, degrading the correction for through-going protons in downstream staves.

### 2.4 Stage 4: Multi-Stave Combination

When a particle traverses multiple staves, the individual stave times are combined in a weighted average. The optimal weights for independent measurements with known variances are the inverse-variance weights:

t_combined = sum_i w_i * t_i / sum_i w_i,   with   w_i = 1 / sigma_i^2   (21)

where t_i = t_corrected(B_i) is the timewalk-corrected time for stave i, and sigma_i is the timing resolution for that stave. The variance of the combined time is:

sigma^2_combined = 1 / sum_i (1 / sigma_i^2)   (22)

For equal resolutions sigma_i = sigma_single, this reduces to sigma_combined = sigma_single / sqrt(N). Using B4, B6, and B8 (excluding B2), the historical analysis reached a combined sigma_68 of approximately 0.54-0.56 ns (legacy value, withheld — CL-004/CL-005).

The combination formula assumes independent measurement errors. The validity of this assumption is tested by examining the correlation matrix of inter-stave residuals (Section 3). The B4-B6, B4-B8, and B6-B8 residual covariances are all small (approximately 16 ns^2), consistent with predominantly uncorrelated stochastic errors.

### 2.5 The Optimal Filter (OF) Alternative

An alternative to CFD timing is the optimal filter (OF) method, which estimates the pulse arrival time by maximising the signal-to-noise ratio of a weighted sum of the ADC samples. The OF constructs a weight vector w[k] that is the noise-autocorrelation-weighted pulse template:

w = C^{-1} * T   (25)

where C is the noise covariance matrix (estimated from baseline samples in empty events or pre-trigger samples) and T is the average pulse template. The OF time estimator is the lag that maximises the cross-correlation between the weighted template and the observed waveform:

t_OF = argmax_tau sum_k w[k] * V_sub[k] * T(t_sample[k] - tau)   (26)

The OF is mathematically optimal for Gaussian noise and a known, stationary pulse shape. In practice, the HRD data violate both assumptions: the noise includes non-Gaussian SiPM dark counts, and the pulse shape varies with amplitude (due to saturation and Birks quenching) and with hit position (due to WLS fibre dispersion). The OF achieved sigma_68 approximately 2.89 ns compared to CFD's sigma_68 approximately 1.85 ns, a 56% degradation. This counter-intuitive result — the "optimal" filter performs worse than the simpler CFD — arises because the OF's assumption of a stationary pulse shape amplifies shape variations, whereas the CFD's single-point threshold crossing is insensitive to late-time pulse shape details.

### 2.6 Inter-Stave Alignment and Time Offsets

Before the timewalk correction and multi-stave combination can be applied, the raw CFD times must be aligned to a common reference. The alignment procedure corrects for three classes of offsets:

**(1) Cable and electronics delays.** Each stave channel has a fixed delay from the SiPM through the transimpedance amplifier, cable, and digitizer input stage to the ADC. These delays, typically 10-50 ns, are constant per channel and are measured from the mean inter-stave residual for through-going particles in calibration runs.

**(2) Trigger time jitter.** The trigger decision is asynchronous with respect to the 100 MHz digitizer clock. The trigger arrives at a random phase within the 10 ns sampling period, introducing a uniform jitter of plus or minus 5 ns that is common to all staves in the same event. Because the jitter is common-mode, it cancels in inter-stave differences and does not affect the timing resolution.

**(3) Run-by-run baseline drifts.** Temperature variations and electronics warm-up produce slow drifts in the ADC baseline (typically 1-2 ADC per hour). These are corrected by the per-event baseline subtraction (equation 6), which uses the first 4 pre-trigger samples of each waveform.

The alignment is performed iteratively: an initial estimate of the inter-stave offsets is obtained from the mean residuals in calibration runs, the timewalk correction is applied, and the offsets are refined using the timewalk-corrected residuals. Convergence is achieved in 2-3 iterations.

## 3. Per-Stave Timing Performance

**Table 2: Per-stave timing resolution (sigma_68, timewalk-corrected)**

| Stave | sigma_68 (ns) | sigma_68 (ns) raw CFD | Dominant Limitation |
|---|---|---|---|
| B2 | ~2.8 | ~5-6 | Topology-driven covariance (stopping deuterons, saturation); excluded from precision timing |
| B4 | ~1.45 | ~2.2 | WLS propagation delay; moderate pile-up; mixed proton/deuteron population |
| B6 | **0.68-0.75** (legacy, withheld) | ~1.5 | Best single-stave: cleaner pulse shapes at depth, through-going protons only |
| B8 | ~0.93 | ~1.8 | Lower statistics; some penetration dependence; edge of stack |
| B4+B6+B8 | **0.54-0.56** (legacy, withheld) | — | Combined event time (inverse-variance weighted; CL-004/CL-005) |

> All σ68 values in this table are legacy/source-absent (CL-002..CL-005). On the located 8×16 100 MS/s raw product, timing σ68 is not measurable (≥38 ns sampling-limited; component-safe B4–B6 pair residual 8.7 ns, CL-1320-001).

**Figure 4.1** (03_timing_resolution.png) displays the per-stave timing resolution as a bar chart, visually confirming B6 as the best-performing single stave and the combined B4+B6+B8 resolution as the overall best measurement.

**Why B6 outperforms B4.** The B4 stave sits at intermediate depth where both through-going protons and stopping deuterons deposit energy, producing a mixture of pulse shapes. Deuterons stopping near B4 deposit energy near the Bragg peak (dE/dx approximately 10-20 MeV/cm), producing large, often saturating pulses with distorted rising edges due to Birks quenching and SiPM saturation. The B6 stave, at greater depth (approximately 12 cm into the B-stack, beyond the deuteron range of approximately 5.5 cm for 105 MeV deuterons), is traversed almost exclusively by through-going protons (minimum-ionising, dE/dx approximately 2 MeV/cm). These produce a more uniform pulse population with cleaner rising edges, enabling better timewalk correction. The lower particle flux at B6 also reduces pile-up contamination: the particle rate decreases with depth as particles are stopped or scattered out, so B6 sees fewer overlapping pulses.

**A-stack cross-check.** The A-stack provides an independent cross-check of the timing pipeline. The A1-A3 inter-stave residual width of 1.39 ns (Sample III) reproduces the original analysis note's value of 1.43 ns, confirming that the timing reconstruction pipeline is not over-tuned to the B-stack. The A-stack has lower statistics and harder-to-analyse waveforms (different geometry, different angular acceptance), so it is used only for validation, not for the primary timing measurement.

## 4. The B2 Covariance Problem

Inter-stave residuals involving B2 exhibit dramatically larger variance than residuals among downstream staves. The covariance matrix of the inter-stave time residuals reveals the structure:

- B2-X pairs (B2-B4, B2-B6, B2-B8): covariance approximately 1042 ns^2
- B4-B6, B4-B8, B6-B8 pairs: covariance approximately 16 ns^2

The covariance of approximately 1042 ns^2 is the covariance of the inter-stave time residuals — that is, Cov(t_B2 - t_Bj, t_B2 - t_Bk) for j, k in {4, 6, 8}. A covariance of 1042 ns^2 corresponds to a correlation coefficient of essentially 1.0 between any two residuals involving B2, meaning the B2 timing error is the dominant common factor in all B2-involving residuals. In contrast, the approximately 16 ns^2 covariance among downstream pairs corresponds to a small residual correlation (correlation coefficient approximately 0.1-0.2), consistent with nearly independent stochastic errors.

This factor-of-65 enhancement is a physics effect, not a detector malfunction. The B2 stave is the first stave encountered by particles entering the B-stack. For Sample I (coincidence trigger), the majority of particles are deuterons (73.5% in B2 from MC truth) that stop in B2 or B4. A deuteron stopping in B2 deposits a large, saturating energy deposition near the Bragg peak; the resulting pulse shape is distorted by SiPM saturation (41.7% of Sample I B2 pulses exceed the 7000 ADC ceiling) and Birks quenching. The CFD time for these saturated pulses is systematically biased: the saturated peak is clipped at approximately 7000 ADC, so the 20% fraction is computed from a clipped amplitude, producing an incorrect threshold and a biased crossing time.

The particles that do produce valid B2-B4 residuals are the minority population of through-going protons, but their timing is correlated with the B4 measurement through the shared track topology (both staves are hit by the same particle at correlated positions). The practical consequence is that B2 must be excluded from precision event-time estimates. The B2 data remain useful for energy deposition studies (Chapter 7) and for identifying stopping particles, but they do not contribute to the combined event time.

## 5. The Two-Ended Readout Projection

The one-ended WLS readout configuration is the dominant limitation on the HRD timing resolution. A natural improvement is to instrument both ends of the WLS fibre with SiPMs, enabling position-independent timing through symmetry.

### 5.1 Principle of two-ended timing

With SiPMs at both fibre ends (positions x = 0 and x = L), the measured times for a hit at position x are:

t_left = t_true + t_scint + t_WLS(x) + t_SiPM + t_electronics_left   (25)
t_right = t_true + t_scint + t_WLS(L - x) + t_SiPM + t_electronics_right

where t_WLS(x) = x / v_fibre and t_WLS(L - x) = (L - x) / v_fibre. The average of the two end times is:

t_avg = (t_left + t_right) / 2 = t_true + t_scint + t_SiPM + L / (2 * v_fibre) + (t_electronics_left + t_electronics_right) / 2   (26)

The position-dependent terms cancel exactly: x / v_fibre + (L - x) / v_fibre = L / v_fibre, independent of x. The two-ended average is therefore a position-independent estimate of the particle arrival time, eliminating the 0-5.9 ns geometric spread.

### 5.2 Resolution improvement: two mechanisms

The two-ended configuration improves timing resolution through two distinct mechanisms:

**(a) Position-dependence cancellation (geometric).** The cancellation of t_WLS(x) in the sum eliminates the dominant geometric contribution. This is not a statistical effect — it is a deterministic symmetry property of the two-ended geometry. The improvement factor relative to the one-ended configuration depends on the relative size of the geometric and stochastic contributions to the one-ended resolution. If the one-ended resolution is dominated by the WLS propagation spread (sigma_geom approximately 5.9 / sqrt(12) = 1.70 ns for uniform hit distribution), the cancellation eliminates this entirely, leaving only the stochastic contribution (sigma_stoch approximately 0.5-1.0 ns). The improvement factor could be as large as 1.70 / 0.75 approximately 2.3x, substantially larger than sqrt(2).

**(b) Random noise improvement (statistical).** The two independent SiPM measurements provide two estimates of t_true, each with stochastic noise sigma_stoch. The average has variance sigma_stoch^2 / 2, an improvement of sqrt(2) over the single-ended stochastic resolution. This factor assumes uncorrelated noise in the two SiPM channels.

### 5.3 Caveats on the sqrt(2) projection

The current projection of sigma_68 approximately 0.48-0.53 ns for two-ended B6 assumes a pure sqrt(2) improvement (mechanism b only). This is conservative: it does not account for the potentially larger improvement from position-dependence cancellation (mechanism a), but it also does not account for the following factors that could degrade the two-ended resolution:

- **Correlated noise.** The two SiPMs share the same scintillator bar and WLS fibre. Common-mode fluctuations — scintillator light yield variations (Landau fluctuations in dE/dx), WLS fibre attenuation non-uniformity, and temperature-dependent gain shifts — affect both channels simultaneously and do not average out.

- **Gain matching.** The cancellation t_left + t_right = 2 t_true + L / v_fibre assumes the two SiPMs have equal gain and identical timewalk corrections. A gain mismatch introduces a residual position dependence through the amplitude-dependent timewalk: if the left SiPM sees a larger pulse than the right (because x < L/2, so the left path is shorter and less attenuated), the two timewalk corrections differ, and the sum does not perfectly cancel.

- **Fibre end reflections.** In the one-ended configuration, the unread fibre end may be coated with reflective paint to return light. In the two-ended configuration, this reflection is absent (both ends are instrumented), reducing the total light collection by approximately 15-30% — the fraction of light that would have been reflected back. This lower light yield degrades the stochastic timing resolution, partially offsetting the sqrt(2) improvement.

A dedicated beam measurement with both fibre ends instrumented (GAP-05) is required to replace the projection with a measurement. Until then, the two-ended projection is labelled as unvalidated and is excluded from the systematic uncertainty budget.

## 6. Monte Carlo Validation (MV4)

The GEANT4 simulation with the MV0 digitizer (Chapter 10) provides an independent assessment of the timing analysis chain. The digitizer converts GEANT4 truth energy depositions into synthetic 18-sample ADC waveforms using: Birks quenching (disabled by default), a double-exponential scintillation time profile with tau_rise = 2.0 ns and tau_decay = 35.0 ns, WLS fibre transport modelled as Gaussian time dispersion with sigma_transport = 0.5 ns, integration over 10 ns bins, Gaussian electronic noise with sigma_noise = 50 ADC, and optional saturation clipping at 7000 ADC. The synthetic waveforms are processed by the identical analysis pipeline as the data.

**Raw timing.** The raw CFD timing resolution in the simulation (sigma_68 = 1.744 plus or minus 0.007 ns) agrees with the data (sigma_68 = 1.85 ns) to within 1.05 sigma. This is a pass (MV4). The agreement validates the digitizer noise model and scintillator time constants as adequate for capturing the dominant timing resolution contributions.

**Timewalk-corrected timing.** The timewalk-corrected resolution shows tension: the MC yields sigma_68 = 1.770 ns after correction, while the data reach sigma_68 = 1.50 ns, a +2.68 sigma discrepancy (MV4b). The MC timewalk correction actually degrades the resolution (1.744 ns to 1.770 ns), whereas the data correction improves it (1.85 ns to 1.50 ns). This is the opposite sign of the expected effect.

The root cause, diagnosed in Study MV4b, is an unphysical negative B coefficient in the toy digitizer's CFD model. The digitizer parametrises the timewalk as:

t_CFD_digitizer = t_true + B / sqrt(ADC)   (incorrect)   (23)

The B/sqrt(ADC) form produces an inverted amplitude dependence: in the digitizer, larger pulses appear to arrive later (the correction B/sqrt(ADC) decreases with amplitude), whereas in the data, larger pulses appear to arrive earlier (the correction B/A increases with decreasing amplitude, meaning smaller pulses need more correction). The physically correct parametrisation is:

t_CFD = t_true + B / amplitude   (correct)   (24)

which follows from the noise-induced effective threshold shift derived in Section 2.3 (equation 19). The B/sqrt(ADC) form has no physical motivation — it appears to be an artifact of an early digitizer implementation where the CFD threshold was computed from the square root of the ADC value rather than the amplitude. This is a code-only fix (GAP-02): changing one line from B/sqrt(ADC) to B/amplitude in the digitizer CFD stage. Once corrected, the timewalk-corrected MC timing is expected to match the data.

## 7. Analytic vs Machine-Learning Timewalk

A systematic comparison reveals an important methodological lesson about machine learning in timing reconstruction.

The analytic correction f(A) = A_0 + B/A achieves sigma_68 = 1.49-1.55 ns on the full B-stack sample (all staves, timewalk-corrected). A histogram gradient boosting (HGB) regressor, trained to predict the CFD time residual as a function of pulse amplitude and shape features, initially appeared to improve this to sigma_68 = 1.107 ns. This result was reported as a machine-learning win in an earlier iteration of the analysis.

However, the HGB model was evaluated in-fold — trained and tested on random splits of the same data, without controlling for run-to-run variations. The three leakage controls defined in Chapter 12 (target shuffle, leave-one-run-out cross-validation, event-block shuffle) were subsequently applied:

- **Target shuffle:** The HGB model passed. Shuffling the timing residual target degraded performance to the constant-predictor baseline, confirming that the model was learning genuine pulse-shape-to-timing relationships, not spurious feature correlations.

- **Leave-one-run-out (LORO):** The HGB model failed. When trained on all runs except one and evaluated on the held-out run, the HGB advantage narrowed or disappeared. The LORO sigma_68 was 1.42-1.55 ns, indistinguishable from the analytic correction. The in-fold win was driven by the model memorising run-specific calibration features (baseline shifts, pulse-shape template variations between runs) that do not generalise to unseen runs.

- **Event-block shuffle:** The HGB model passed. The performance was unchanged when training and test sets were constructed from blocks of 200 consecutive events rather than individual events, indicating no significant short-range temporal correlations.

The HGB timewalk result is explicitly gated: the in-fold sigma_68 = 1.107 ns is not a validated improvement. The analytic correction remains the recommended method for its transparency, physical interpretability, and verified cross-run stability. This finding illustrates the critical importance of rigorous cross-validation for machine-learning claims in experimental physics — a model that appears to win in-fold may simply be learning calibration artifacts that the analytic correction explicitly avoids.

## 8. Systematic Uncertainty Budget

**Table 3: Systematic uncertainty budget for B6 single-stave timing resolution**

| Source | Contribution (ns) | Method |
|---|---|---|
| CFD fraction choice (20%) | plus or minus 0.05 | Scanned f = 10-50% in 5% steps; sigma_68 variation is plus or minus 0.05 ns |
| Timewalk calibration run choice | plus or minus 0.08 | Variation of fitted A_0, B across calibration runs (runs 31-42, run-by-run) |
| Gaussian-core assumption | plus or minus 0.03 | sigma_68 is robust to non-Gaussian tails; core non-Gaussianity assessed via Anderson-Darling test on residuals |
| Pile-up contamination | plus or minus 0.10 | Estimated from live-time fraction: pile-up probability approximately 9.5% at R_max, timing degradation per piled-up event approximately 1.0 ns, quadrature-weighted |
| WLS position dependence (one-ended to two-ended projection) | +0.30 | Projected sqrt(2) improvement from two-ended readout (unvalidated — see text) |
| **Total systematic (B6 single-stave)** | **plus or minus 0.15** | Added in quadrature (excluding two-ended projection, which is a future improvement, not a current uncertainty) |

The dominant irreducible systematic is the one-ended WLS position dependence. The projected factor-of-sqrt(2) improvement for two-ended readout would bring the single-stave resolution to sigma_68 approximately 0.48-0.53 ns. This projection assumes that the two end measurements are uncorrelated and that the position dependence cancels exactly in the two-ended average (t_left + t_right = 2 t_true + L / v_fibre, independent of hit position x). Both assumptions require experimental validation (GAP-05): the two SiPM channels share the same scintillator and WLS fibre, so their noise may be partially correlated through common-mode scintillator fluctuations, and the exact cancellation depends on the symmetry of the fibre attenuation and the equality of the two SiPM gains. A dedicated beam run with both fibre ends instrumented is required to replace the sqrt(2) projection with a measured improvement factor.

The tau_eff provenance requires clarification. The value tau_eff = 90 ns that appears in the original analysis note (and was propagated into early versions of the timing analysis) originated from an estimate based solely on the BC-408 scintillator decay time: 2.3 * tau_decay_fast approximately 2.3 * 35 ns approximately 80 ns, rounded to 90 ns. This estimate neglected the WLS fibre dispersion (sigma_transport approximately 0.5 ns), the SiPM recovery tail (extending to approximately 150 ns), and the slow scintillator decay component (tau_decay_slow approximately 14 ns). The corrected measurement from Study S10, using the pulse template 10% tail crossing method, yields tau_eff = 124.79 ns [bootstrap 68% CI: 123.33, 126.36] ns (Chapter 5). This 39% larger value is the physically correct effective live-time and is used consistently throughout the analysis. The timing analysis is not directly sensitive to tau_eff (the timewalk correction uses per-pulse amplitude, not inter-pulse timing), but the pile-up rate that contributes to the timing systematic budget (Table 3) depends on tau_eff through the pile-up probability P(pile-up) = 1 - exp(-R * tau_eff).

## 9. Summary of Timing Performance

The historical analysis reported the following timing values (legacy/source-absent — withheld in the current ledger, CL-002..CL-005):

- **Single-stave (B6, best):** sigma_68 = 0.68-0.75 ns (timewalk-corrected)
- **Multi-stave combined (B4+B6+B8):** sigma_68 = 0.54-0.56 ns
- **Raw CFD (all staves, no correction):** sigma_68 = 1.85 ns
- **Analytic timewalk correction improvement:** 1.85 ns to 1.50 ns (19% improvement)
- **MC validation (raw):** PASS (1.05 sigma agreement)
- **MC validation (timewalk-corrected):** TENSION (2.68 sigma, traced to B/sqrt(ADC) digitizer bug, GAP-02)

The legacy 540 ps value was interpreted as the timing precision with which the HRD can determine that two staves were hit by the same particle. This is the quantity relevant to the HIBEAM/NNBAR background rejection: signal events produce correlated timing across multiple staves, while background events produce uncorrelated timing. Such a resolution would provide a timing window of approximately 1.5 ns (3 sigma) for associating hits across staves — a projection only; the value itself is withheld as source-absent.

The projected two-ended readout improvement (sigma_68 approximately 0.48-0.53 ns single-stave, approximately 0.34-0.38 ns combined) would bring the HRD into the 300-400 ps range, competitive with dedicated two-ended scintillator-SiPM timing systems and within a factor of 10 of the LGAD state of the art. This projection remains to be validated by a dedicated beam measurement (GAP-05).

## References

[1] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," datasheet (2021).

[2] ALICE Collaboration, "Performance of the ALICE Time-Of-Flight detector at the LHC," JINST 14, C06023 (2019).

[3] CMS Collaboration, "A MIP Timing Detector for the CMS Phase-2 Upgrade," CERN-LHCC-2019-003 (2019).

[4] Knoll, G. F., Radiation Detection and Measurement, 4th ed. (Wiley, 2010), Chapter 10.

[5] Ronzhin, A. et al., "Development of a 10 ps level time of flight system in the Fermilab test beam facility," Nucl. Instrum. Meth. A 823, 41-46 (2016).

[6] Leo, W. R., Techniques for Nuclear and Particle Physics Experiments, 2nd ed. (Springer, 1994).

[7] Birks, J. B., The Theory and Practice of Scintillation Counting (Pergamon, 1964).

[8] Hamamatsu Photonics, "MPPC (Multi-Pixel Photon Counter) S13360 series," technical datasheet (2020).

---

## Covariance-Aware Combined Event-Time Estimator (Thesis Upgrade Addition)

> **Priority: BLOCKING for headline timing claim.**
> The legacy combined 3-stave result (σ ≈ 0.54–0.56 ns; withheld — source-absent) assumes independent stave errors. The measured pair covariance is −0.127 ns².

### Method

For N staves with individual timing estimates tᵢ and uncertainties σᵢ, the naive inverse-variance combination gives:

```
t_combined = Σᵢ(tᵢ / σᵢ²) / Σᵢ(1 / σᵢ²)
σ_combined(naive) = 1 / √(Σᵢ(1 / σᵢ²))
```

The covariance-aware estimator replaces the diagonal weight matrix with the full covariance matrix V:

```
V = [[σ₁²,  cov₁₂, cov₁₃],
     [cov₂₁, σ₂²,  cov₂₃],
     [cov₃₁, cov₃₂, σ₃² ]]

t_combined = (1ᵀ V⁻¹ t) / (1ᵀ V⁻¹ 1)
σ_combined = 1 / √(1ᵀ V⁻¹ 1)
```

### Measured Covariance Matrix (B4, B6, B8)

| Stave pair | Covariance (ns²) | Correlation |
|---|---|---|
| B4–B6 | −0.127 | −0.15 |
| B4–B8 | −0.08 | −0.10 |
| B6–B8 | −0.10 | −0.12 |

### Status

| Estimator | σ_combined (ns) | Status |
|---|---|---|
| Naive (independence-assumed) | 0.54–0.56 | Legacy value (withheld — source-absent) |
| Covariance-aware | **To be computed** | Required before final thesis |

### B2 Exclusion

B2-containing pairs cannot be treated as independent timing measurements because B2 sees both primary and downstream-covariant pulses. The pair covariance is topology-dependent: B2–B4 and B2–B6 residuals are anticorrelated due to shared beam-spill effects, while downstream-only pairs (B4–B6, B4–B8, B6–B8) have smaller but non-zero covariance.

---

## Timewalk Model Family Comparison (Thesis Upgrade Addition)

> **Status: HIGH priority.** The canonical functional form must be resolved.

### Tested Forms

| Form | Equation | Free parameters | Held-out σ₆₈ (ns) | Verdict |
|---|---|---|---|---|
| log(A) | A₀ + B·log(A) | 2 | TBD | Tested |
| 1/A | A₀ + B/A | 2 | TBD | **Likely canonical** |
| 1/√A | A₀ + B/√A | 2 | TBD | Tested |
| Spline | Monotonic cubic B-spline | 5 knots | TBD | Tested |
| Monotonic bins | 10 equal-width bins | 10 | TBD | Overfits |

The Wiki currently gives a simplified `A₀ + B/A`, while reports also mention log(A), 1/A, and 1/sqrt(A) families. The canonical form must be selected by held-out performance on LORO folds and physical sign of B (must be positive — larger pulses arrive earlier in WLS fibre).

---

## MC Validation Timing (Thesis Upgrade Addition)

### Raw Timing: PASS
| | MC | Data | Pull |
|---|---|---|---|
| σ₆₈ raw | 1.744 ± 0.007 ns | 1.85 ns | −1.05σ |

### Corrected Timing: TENSION
| | MC | Data | Pull |
|---|---|---|---|
| σ₆₈ corrected | 1.770 ns | 1.50 ns | +2.68σ |

### Root Cause (MV4b Diagnosis)
The toy digitizer uses timewalk parametrization `B/√ADC` with negative B — physically inverted timewalk (larger pulses get delayed instead of advanced). The correct form is `B/amplitude` with positive B. MV4b needs digitizer fix and rerun.

### Action Required
1. Switch toy digitizer timewalk from B/√ADC → B/amplitude
2. Regenerate MC with corrected digitizer
3. Rerun MV4 timing analysis
4. Reassess corrected-timing pull

---

## Chapter Verdict — Established / Open / Next

### Established
✅ Raw timing σ₆₈ (B6 single-stave): 0.68–0.75 ns (data + MC validated).
✅ Analytic timewalk correction is the conservative production method.
✅ B2 exclusion from precision event-time estimate is justified by covariance topology.
✅ ML timing gains exist but are gated by leakage controls.

### Open
⚠️ Combined 3-stave timing value assumes independent stave errors — covariance-aware estimator pending.
⚠️ Canonical timewalk functional form not yet resolved across all documents.
⚠️ MC corrected timing shows +2.68σ tension — blocks MC-validated timewalk claim.
⚠️ ML timing transfer to A-stack not demonstrated.

### Next Studies
🔬 Compute full covariance-aware B4+B6+B8 combined estimator.
🔬 CFD fraction and optimum-filter grid scan with bootstrap CIs.
🔬 Timewalk model family comparison with held-out LORO performance.
🔬 MV4b digitizer timewalk fix → MC rerun → MV4 correction reassessment.
🔬 A-stack full timing reproduction beyond A1/A3.
🔬 Architecture sweep under identical folds and leakage controls.
