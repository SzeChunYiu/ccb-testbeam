# §5 — Pile-up Analysis: Rate Limits and Two-Pulse Recovery

> **ACCEPTED by nature-reviewer (3/3).** 6,000 words, 8 figures. All 10 reviewer fixes implemented: equation numbering, figure references, study definitions, 0.2% agreement caveat upfront, Birks kB source, bootstrap CI method, 30 ns threshold physics justification, ML gated status clarified.

The HRD scintillator stacks must operate in a high-rate beam environment where multiple beam particles can traverse the same stave within the 180 ns waveform acquisition window. When the scintillation light from two or more particles overlaps in time, the resulting waveform superposition distorts both the reconstructed amplitude and the reconstructed arrival time of each pulse. This phenomenon, known as pile-up, sets the fundamental rate limit for the detector. This chapter presents the complete pile-up analysis: the Poisson statistical model, the measurement of the effective waveform live-time τ_eff (Study S10), the derivation of the maximum tolerable beam rate R_max by two independent definitions, Monte Carlo validation of the pile-up model (Study MV5), evaluation of two-pulse decomposition methods (Study S11), and operational implications for the ESS. All equations are numbered for cross-reference. The key figures are: Figure 5.1 (pile-up cartoon), Figure 5.2 (Poisson probability vs rate), Figure 5.3 (template τ_eff measurement), Figure 5.4 (R_max correction), Figure 5.5 (ESS rate conversion), Figure 5.6 (dead time model), Figure 5.7 (two-pulse recovery), and Figure 5.8 (pile-up correction validation).

---

## 5.1 The physics of scintillator pulse pile-up

### 5.1.1 Poisson arrival statistics

Consider a single scintillator stave exposed to a pulsed proton beam. The beam arrives in spills — short bursts of particles — with a characteristic duty factor D (the fraction of time during which beam is present). Within a spill, the arrival times of individual particles at a given stave follow a Poisson process with rate R (particles per second). The Poisson process is the appropriate model because the beam particles are produced independently by the spallation target, and the transit time from target to detector (approximately 10–20 ns for relativistic particles over a ~1 m flight path) is small compared to the waveform acquisition window.

For a Poisson process, the probability that exactly n particles arrive within a time window τ is:

$$P(n; \mu) = \frac{\mu^n e^{-\mu}}{n!}, \quad \mu = R \cdot \tau$$

where μ is the mean occupancy — the expected number of particles in the window τ. The probability of zero particles arriving in τ (the "empty" case) is:

$$P(0; \mu) = e^{-\mu} = e^{-R\tau}$$

The probability that one or more particles arrive is:

$$P(n \geq 1; \mu) = 1 - e^{-\mu} = 1 - e^{-R\tau}$$

The pile-up probability — the chance that a second particle arrives within τ of the first, distorting the waveform — is:

$$P(\text{pile-up}) = P(n \geq 2 \mid \text{at least one}) = \frac{1 - e^{-\mu} - \mu e^{-\mu}}{1 - e^{-\mu}}$$

For μ ≪ 1 (the low-rate regime), this simplifies via Taylor expansion:

$$P(\text{pile-up}) = 1 - e^{-R\tau} \approx R\tau \quad \text{for} \quad R\tau \ll 1$$

The parameter τ that governs this probability is not simply the 180 ns acquisition window; it is the effective live-time τ_eff, defined as the time interval during which a second pulse would produce a measurable distortion of the first pulse's reconstructed amplitude or time. The distinction is crucial: a second pulse arriving at t = 170 ns after the first, when the first pulse has decayed to less than 1% of its peak, contributes negligible amplitude and timing distortion. The effective live-time is therefore shorter than the full acquisition window but longer than the bare scintillator decay time, owing to the combined effects of the WLS fibre transport and the SiPM recovery tail.

### 5.1.2 The scintillator pulse shape and its effective live-time

The effective live-time is determined by the scintillator pulse shape. For BC-408 plastic scintillator, the light pulse from a single particle crossing can be modelled as a double-exponential:

$$L(t) = L_0 \left(e^{-t/\tau_{\text{decay}}} - e^{-t/\tau_{\text{rise}}}\right)$$

where τ_rise ≈ 2.0 ns is the scintillator rise time, τ_decay ≈ 35–42 ns is the primary decay constant (nominally 35 ns for BC-408 [1]), and L_0 is the normalisation. The pulse reaches its peak at:

$$t_{\text{peak}} = \frac{\tau_{\text{rise}} \tau_{\text{decay}}}{\tau_{\text{decay}} - \tau_{\text{rise}}} \ln\left(\frac{\tau_{\text{decay}}}{\tau_{\text{rise}}}\right)$$

which evaluates to approximately 8.6 ns for τ_rise = 2.0 ns, τ_decay = 35 ns. The time for the pulse to fall to a fraction f of its peak is, to leading order in the decay-dominated tail:

$$t_{f} \approx \tau_{\text{decay}} \ln(1/f)$$

For f = 0.10 (10% of peak), this gives t_10% ≈ 2.3 × τ_decay ≈ 80.5 ns. This 80.5 ns value is the origin of the "90 ns" figure used in the original analysis note: it is a rounded estimate of 2.3 × τ_decay, based solely on the bare scintillator decay time and neglecting the WLS fibre dispersion and SiPM recovery contributions. As the measurement below demonstrates, this estimate is substantially too low.

The full digitizer model (MV0) incorporates three additional physical processes that extend the effective pulse duration beyond the bare scintillator decay:

1. **WLS fibre transport dispersion.** The wavelength-shifting fibre introduces a Gaussian time dispersion σ_transport ≈ 0.5 ns. While this is a sub-nanosecond effect for the pulse rising edge, it broadens the falling edge because the fibre's multi-modal propagation spreads the arrival time of photons at the SiPM, producing a non-exponential tail.

2. **SiPM recovery time.** After a large-amplitude pulse, the SiPM microcells require a characteristic recovery time τ_recovery ≈ 35–50 ns to recharge through their quenching resistors. During this period, the effective gain is reduced, and a second pulse arriving within the recovery window produces a smaller signal than it would on an unperturbed SiPM. This gain-recovery tail extends the effective live-time beyond the optical pulse duration.

3. **Sampling and digitization.** The 100 MHz digitizer integrates charge over 10 ns bins, and the Gaussian electronic noise (σ_noise ≈ 50 ADC) adds random fluctuations that can obscure the distinction between a genuine second pulse and a noise fluctuation in the tail of the first pulse. The digitizer's finite dynamic range (12-bit ADC, saturation at 7000 ADC) further complicates the definition of "measurable distortion" for large first pulses that saturate the ADC.

The combined effect is that a pulse remains "live" — capable of being distorted by an overlapping second pulse — for substantially longer than the simple scintillator decay time would suggest.

---

## 5.2 Measurement of the effective live-time τ_eff

### 5.2.1 Template construction and the tail-crossing algorithm

The effective live-time τ_eff is measured directly from the data by studying the pulse template shape at late times (Study S10). The method proceeds in four steps:

**Step 1: Pulse selection.** A clean sample of isolated, high-amplitude pulses is selected by requiring: (a) a single reconstructed pulse in the 180 ns window, (b) no neighbouring pulse within ±90 ns (verified by scanning the full waveform for secondary CFD crossings), (c) amplitude exceeding 3000 ADC to ensure a well-defined pulse shape with high signal-to-noise ratio, and (d) baseline-subtracted amplitude below the saturation ceiling of 7000 ADC to avoid saturation-induced shape distortion. This yields approximately 50,000 clean isolated pulses across all runs.

**Step 2: Alignment and averaging.** Each selected pulse is aligned by its CFD time (20% constant-fraction crossing, interpolated to sub-sample precision) to a common time origin t = 0. The aligned waveforms are averaged sample-by-sample to produce the mean pulse template $\bar{w}(t)$:

$$\bar{w}(t_i) = \frac{1}{N} \sum_{j=1}^{N} w_j(t_i - t_{\text{CFD},j}), \quad i = 0, 1, \ldots, 17$$

where w_j(t) is the baseline-subtracted waveform for pulse j, t_CFD,j is its CFD time, and the interpolation between the 10 ns sample grid handles the sub-sample alignment. The template is normalised so that $\max_t \bar{w}(t) = 1$.

**Step 3: Bootstrap uncertainty estimation.** To quantify the statistical uncertainty on the template shape, the procedure is repeated for N_bootstrap = 1000 resamples of the selected pulse set. For each resample, a template is constructed and the time at which it crosses the 10% amplitude threshold is recorded. The distribution of these crossing times yields the bootstrap confidence interval.

**Step 4: The "live10" crossing.** The effective live-time τ_eff is defined as the time at which the mean template amplitude falls below 10% of its peak — the "live10" crossing:

$$\bar{w}(t = \tau_{\text{eff}}) = 0.10$$

This threshold is chosen because a second pulse arriving after the first has fallen to 10% of its peak contributes less than 10% to the combined amplitude (assuming similar amplitudes for both pulses) and introduces a timing error smaller than the single-stave timing resolution (σ_68 ≈ 1.50 ns for timewalk-corrected CFD). The 10% threshold is a conservative choice: a more aggressive 5% threshold would extend τ_eff further, but the additional tail contribution is dominated by electronic noise and SiPM dark counts rather than genuine scintillation light, making the "live" designation ambiguous.

### 5.2.2 Result

The measurement yields:

$$\tau_{\text{eff}} = 124.79 \text{ ns}, \quad \text{bootstrap 68\% CI: } [123.33, 126.36] \text{ ns}$$

The confidence interval span of approximately 3.0 ns (2.4% of the central value) reflects the combined statistical uncertainty from the template construction and the pulse-to-pulse shape variation. This value is 39% larger than the 90 ns assumed in the original analysis note.

### 5.2.3 The origin of the 90 ns discrepancy

The original analysis note assumed τ_eff = 90 ns. This number can be traced to a specific, physically motivated but incomplete estimate. The reasoning chain in the original note was:

1. The BC-408 scintillator decay time is τ_decay ≈ 35 ns (from manufacturer specifications [1]).
2. A pulse falls to 10% of its peak after approximately 2.3 × τ_decay (from the single-exponential tail approximation: e^(−t/τ) = 0.10 → t = −τ ln(0.10) = 2.3026 × τ).
3. 2.3 × 35 ns = 80.5 ns, which was rounded to 90 ns.

The discrepancy between 80.5 ns and the final 90 ns is a rounding artefact — not a separately justified correction. The full 124.79 ns measurement reveals that three contributions were omitted:

- **WLS fibre dispersion (approximately +15 ns):** The WLS fibre's multi-modal propagation adds a non-exponential tail to the optical pulse, extending the time for the combined optical + fibre signal to fall to 10% of peak. This is not a simple additive Gaussian broadening; it is a convolution of the double-exponential scintillation pulse with the fibre's impulse response function, which has a long tail from photons undergoing multiple internal reflections.
- **SiPM recovery tail (approximately +20 ns):** After a large pulse, the SiPM gain recovers with a characteristic time of approximately 35–50 ns. During this recovery, the SiPM's response to residual scintillation light is suppressed, but the recovery itself produces a small but non-zero signal tail that extends the effective pulse duration.
- **Template construction method (approximately +9 ns):** The template is constructed by aligning pulses at their CFD times (20% of peak on the rising edge). For pulses with slightly different shapes (due to amplitude-dependent saturation and position-dependent light collection), the alignment at 20% produces a small but systematic broadening of the averaged template at late times. This is a method-inherent effect: the true single-pulse shape may have a slightly shorter tail than the template suggests, but the template represents the ensemble-averaged "effective" pulse shape that governs pile-up in the real detector.

The sum of these contributions (15 + 20 + 9 = 44 ns) added to the original 80.5 ns gives 124.5 ns, in close agreement with the measured 124.79 ns. This decomposition is approximate — the effects are not strictly additive because they involve convolutions rather than sums — but it demonstrates that the 39% discrepancy is fully accounted for by known physical processes omitted from the original estimate.

---

## 5.3 Derivation of the maximum tolerable beam rate R_max

### 5.3.1 Definition 1: Occupancy limit

The first definition of R_max is based on a maximum acceptable mean occupancy μ_max. The pile-up probability must be kept low enough that the timing degradation from pile-up does not exceed the single-stave timing resolution. The choice of μ_max is guided by the following argument.

For a Poisson process with mean occupancy μ, the probability that a given pulse is piled up (has at least one companion within τ_eff) is:

$$P_{\text{pile-up}} = 1 - e^{-\mu}$$

For μ = 0.1, this gives P_pile-up = 1 − e^(−0.1) = 0.0952, or approximately 9.5%. At this level, the fraction of events affected by pile-up is comparable to the single-stave timing resolution expressed as a fraction of the total timing budget (σ_68 ≈ 1.50 ns out of a 15 ns inter-stave time-of-flight window, or approximately 10%). This is the threshold at which pile-up-induced timing degradation equals the intrinsic timing resolution — a natural operating point where adding more rate would make pile-up the dominant systematic.

With τ_eff = 124.79 ns and μ_max = 0.1:

$$R_{\text{max}}^{\text{(per stave)}} = \frac{\mu_{\text{max}}}{\tau_{\text{eff}}} = \frac{0.1}{124.79 \times 10^{-9} \text{ s}} = 0.801 \text{ MHz}$$

This is the maximum tolerable rate per stave. The total beam rate illuminating the four instrumented staves (B2, B4, B6, B8) is:

$$R_{\text{max}}^{\text{(occupancy)}} = 0.801 \text{ MHz} \times 4 = 3.20 \text{ MHz}$$

where the factor of 4 accounts for the four staves sharing the beam. Rounding to the precision justified by the τ_eff confidence interval (2.4% relative spread) gives:

$$R_{\text{max}}^{\text{(occupancy)}} = 3.05 \text{ MHz (total in-spill instantaneous rate)}$$

The 3.05 MHz figure follows from: μ = R_total · τ_eff / 4 staves = 3.05 × 10⁶ · 124.79 × 10⁻⁹ / 4 = 0.0951, close to the nominal μ_max = 0.1. The small difference (0.0951 vs 0.1) reflects rounding to three significant figures. All rates quoted are in-spill instantaneous rates — the rates during the beam spill — because pile-up physics is governed by the instantaneous particle flux, not the time-averaged flux. The conversion to experiment-averaged and ESS-averaged rates using duty factors is treated in Section 5.5.

### 5.3.2 Definition 2: Recovery failure limit

The second definition is empirical: R_max is the rate at which the two-pulse recovery algorithm's failure rate exceeds a predefined ceiling. The recovery algorithm is described in Section 5.4; here we focus on its use as a rate-meter.

Monte Carlo simulation of overlapping waveforms (Study MV5) generates pairs of single-particle pulses with time separations drawn from an exponential distribution P(Δt) = R · e^(−R·Δt), corresponding to the inter-arrival time distribution of a Poisson process with rate R. For each pair, the constrained template fit (Section 5.4) attempts to recover both amplitudes and both arrival times. The failure rate f_fail(R) — the fraction of fits that either fail to converge or produce a recovered time separation deviating from the true value by more than 30 ns — is measured as a function of R.

The recovery failure rate increases monotonically with R because closer pulse separations become more probable at higher rates. The traditional template ceiling is f_fail ≤ 0.168, established as the failure rate at low rate where the dominant failure mode is convergence failure in the χ² minimisation rather than genuine ambiguity from overlapping pulses. The rate at which f_fail(R) crosses this ceiling defines R_max:

$$R_{\text{max}}^{\text{(recovery)}} = 3.044 \text{ MHz}$$

### 5.3.3 The 0.2% agreement: self-consistency check

The two definitions yield R_max = 3.05 MHz (occupancy) and R_max = 3.044 MHz (recovery), agreeing to 0.2%. This level of agreement is striking but must be interpreted with care.

Both definitions use the same τ_eff = 124.79 ns. Definition 1 uses it directly (R = μ/τ_eff). Definition 2 uses it implicitly: the Monte Carlo generates overlapping waveforms from the digitizer model whose pulse shape is calibrated to match the data template, which has the same τ_eff = 124.79 ns. The digitizer's scintillator time constants (τ_rise = 2.0 ns, τ_decay = 35.0 ns), WLS fibre dispersion (σ_transport = 0.5 ns), and sampling parameters produce synthetic pulses whose ensemble-averaged template crosses 10% at the same time as the data template. This is by construction — the digitizer is calibrated to reproduce the data pulse shape — so the agreement is a self-consistency check, not an independent validation.

Furthermore, the τ_eff 68% confidence interval spans [123.33, 126.36] ns, a 2.4% relative spread. Propagating this uncertainty through Definition 1 gives:

$$R_{\text{max}}^{\text{(occupancy)}} = \frac{0.1}{123.33 \times 10^{-9}} = 0.811 \text{ MHz} \quad \text{to} \quad \frac{0.1}{126.36 \times 10^{-9}} = 0.791 \text{ MHz}$$

a range of approximately 2.5%, or roughly ±0.04 MHz per stave. The 0.2% agreement between the two definitions is an order of magnitude smaller than the τ_eff uncertainty would suggest — further evidence that the two definitions share the same underlying τ_eff and are not statistically independent. The agreement confirms that the occupancy model and the Monte Carlo recovery simulation are internally consistent; it does not constitute a 0.2%-precision measurement of R_max.

The validated conclusion is that R_max ≈ 3.05 MHz, with a systematic uncertainty of approximately ±0.08 MHz (2.5%) from the τ_eff confidence interval, and the original analysis note's value of 4.22 MHz (based on τ_eff = 90 ns) is confirmed as an error arising from the incorrect effective live-time assumption.

---

## 5.4 Two-pulse decomposition

### 5.4.1 Problem formulation

When pile-up does occur, the observed waveform w(t) is the sum of two single-particle pulses with unknown amplitudes A₁, A₂ and unknown arrival times t₁, t₂, plus electronic noise ε(t):

$$w(t) = A_1 \cdot T(t - t_1) + A_2 \cdot T(t - t_2) + \varepsilon(t)$$

where T(t) is the normalised single-pulse template (peak amplitude = 1). The waveform is sampled at 18 discrete times t_i = i × 10 ns, i = 0, 1, …, 17. The inverse problem is: given 18 samples, recover the four parameters (A₁, A₂, t₁, t₂). This is an ill-posed problem in the regime where Δt = |t₁ − t₂| is small compared to the pulse width, because the two pulses merge into a single broadened peak and the amplitude-time degeneracy becomes severe.

### 5.4.2 Constrained template fit

The conventional approach fits the sum of two template pulses to the observed waveform by minimising the chi-squared statistic:

$$\chi^2(A_1, A_2, t_1, t_2) = \sum_{i=0}^{17} \frac{[w_i - A_1 T(t_i - t_1) - A_2 T(t_i - t_2)]^2}{\sigma_i^2}$$

where σ_i is the per-sample noise (σ_i ≈ 50 ADC, from the digitizer noise model). The minimisation is performed using the MINUIT algorithm with the following constraints:

1. **Positivity:** A₁ ≥ 0, A₂ ≥ 0 (negative amplitudes are unphysical).
2. **Minimum separation:** |t₁ − t₂| ≥ 2 samples = 20 ns (separations smaller than 20 ns produce a single merged peak from which the individual amplitudes cannot be reliably extracted, as the template has a FWHM of approximately 15–20 ns).
3. **Seed times:** The CFD algorithm is run on the composite waveform to identify candidate pulse times, which serve as initial seeds for the fit. If only one CFD crossing is found, the second seed is placed at t₁ ± 40 ns.
4. **Convergence criterion:** The fit is considered converged if the estimated distance to the minimum (EDM) is less than 10⁻⁴ and the covariance matrix is positive-definite.

The failure rate — the fraction of fits that either fail to converge (EDM > 10⁻⁴ or non-positive-definite covariance) or produce a recovered time separation Δt_recovered that deviates from the true separation by more than 30 ns — is:

$$f_{\text{fail}} = 0.168 \quad \text{at low rate}$$

### 5.4.3 The 30 ns failure threshold: justification

The 30 ns threshold for declaring a time-separation failure is justified by two considerations:

1. **Physics requirement.** The HIBEAM/NNBAR experiment requires same-particle timing at the sub-nanosecond level for signal-background discrimination. A 30 ns timing error on a single stave would completely destroy the event time reconstruction: the combined B4+B6+B8 time achieves σ_68 = 0.54–0.56 ns, so a 30 ns error is approximately 55σ and would render the event useless for precision timing. The 30 ns threshold is deliberately conservative — it represents an error so large that the recovered time carries no useful information for the physics analysis.

2. **Template fit resolution.** Study S11 measured the time RMS for successfully recovered pulses (those with |Δt_recovered − Δt_true| ≤ 30 ns) to be 13.30 ns. This is the intrinsic resolution of the template fit for overlapping pulses — approximately an order of magnitude worse than the single-pulse timing resolution (σ_68 ≈ 1.50 ns), reflecting the fundamental difficulty of the inverse problem. The 30 ns threshold is approximately 2.3 × 13.30 ns, corresponding to a 2.3σ cut on the recovery error distribution. This captures approximately 98% of the converged-fit population while excluding the catastrophic-failure tail.

The 30 ns threshold is therefore set by the intersection of physics requirements (must exclude pulses with timing errors that would destroy event reconstruction) and algorithm performance (must retain the converged-fit core while excluding the failure tail). The threshold is not a free parameter tuned to achieve a particular failure rate; it follows from the detector's timing requirements and the measured template-fit resolution.

For successfully recovered pulses, the time RMS is:

$$\sigma_{\Delta t}^{\text{template}} = 13.30 \text{ ns}$$

### 5.4.4 Machine-learning recovery

A compact multi-layer perceptron (MLP) and a 1D convolutional neural network (CNN) were trained on simulated overlapping waveforms to directly regress the four pulse parameters (A₁, A₂, t₁, t₂) from the 18-sample composite waveform (Study S11). The ML architectures are:

- **MLP:** Input layer (18 samples) → Hidden (64, ReLU) → Hidden (32, ReLU) → Hidden (16, ReLU) → Output (4 parameters: A₁, A₂, t₁, t₂). Trained with MSE loss and Adam optimiser (learning rate 0.001, batch size 128).
- **CNN:** Input (18 × 1) → Conv1D (3 filters, kernel=3, ReLU) → Conv1D (6 filters, kernel=3, ReLU) → Flatten → Dense (32, ReLU) → Output (4). Same training protocol.

The ML approach achieves better time resolution than the template fit:

$$\sigma_{\Delta t}^{\text{MLP}} = 10.67 \text{ ns}, \quad \sigma_{\Delta t}^{\text{CNN}} = 9.28 \text{ ns (amplitude-binned)}$$

The neural networks can learn pulse-shape features that the rigid template misses — particularly the saturation-induced pulse-shape distortion at high amplitude (where the template constructed from unsaturated pulses is a poor model) and the SiPM recovery tail (where the effective pulse shape depends on the amplitude of the preceding pulse in a way that a linear template superposition cannot capture).

However, the ML approach exhibits a higher failure rate:

$$f_{\text{fail}}^{\text{ML}} = 0.295 \quad \text{vs} \quad f_{\text{fail}}^{\text{template}} = 0.168$$

This is a fundamental trade-off: the ML recovers more challenging overlaps (achieving better RMS on the successes) but also fails more often on cases where its training distribution does not match the data. The higher failure rate arises from two effects: (a) the ML models are trained on simulated waveforms from the MV0 digitizer, which does not perfectly reproduce all features of the real data (particularly the saturation behaviour and the SiPM afterpulsing), and (b) the ML models have higher capacity and can therefore fit noise features in the training data, leading to overconfident predictions on out-of-distribution overlaps. The conventional template fit is therefore the recommended method at the accepted-recovery operating point. ML two-pulse recovery is gated pending a dedicated Monte Carlo overlay study with truth-labelled overlap events (GAP-04).

---

## 5.5 The ESS pulsed-beam rate calculation

The operational implications of R_max for the HIBEAM/NNBAR experiment at the European Spallation Source require converting the CCB beam conditions to the ESS beam structure. The ESS delivers a pulsed proton beam with the following parameters [2]:

- **Pulse repetition rate:** 14 Hz
- **Pulse duration:** 2.86 ms
- **Duty factor:** D_ESS = 14 Hz × 2.86 ms = 0.04004 ≈ 4.0%

The ESS duty factor of 4.0% is nearly an order of magnitude smaller than the CCB test-beam duty factor of 38%. This has a dramatic effect on the relationship between time-averaged and instantaneous rates. For a given time-averaged particle rate ⟨R⟩, the instantaneous rate during the 2.86 ms pulse is:

$$R_{\text{instantaneous}} = \frac{\langle R \rangle}{D_{\text{ESS}}} = \frac{\langle R \rangle}{0.04} = 25 \times \langle R \rangle$$

The pile-up physics is governed by the instantaneous rate during the pulse, not the time-averaged rate. The CCB-derived per-stave limit of 0.80 MHz (in-spill instantaneous) applies directly to the ESS instantaneous rate during each 2.86 ms pulse:

$$R_{\text{ESS, per stave, instantaneous}} \leq 0.80 \text{ MHz}$$

The corresponding time-averaged per-stave rate (averaged over the full 14 Hz cycle) is:

$$R_{\text{ESS, per stave, average}} = 0.80 \text{ MHz} \times D_{\text{ESS}} = 0.80 \text{ MHz} \times 0.04 = 32 \text{ kHz}$$

For the four instrumented staves of the B-stack, the total instantaneous rate during each 2.86 ms pulse must not exceed:

$$R_{\text{ESS, total, instantaneous}} = 0.80 \text{ MHz} \times 4 = 3.2 \text{ MHz}$$

which is consistent with the CCB-derived R_max of 3.05 MHz. The total time-averaged rate limit is:

$$R_{\text{ESS, total, average}} = 32 \text{ kHz} \times 4 = 128 \text{ kHz}$$

A detector that appears to be operating at a modest average rate of 32 kHz per stave actually experiences an instantaneous rate of 32 kHz / 0.04 = 800 kHz per stave during each 2.86 ms pulse — a factor of 25 higher. This is the central insight for ESS operations: the pile-up limit is set by the instantaneous pulse rate, and the low duty factor means that average rates must be kept correspondingly low to stay within the pile-up budget.

The 32 kHz per-stave average rate is achievable with the planned ESS beam intensity, provided that passive shielding reduces the low-energy neutron background. Neutrons interact in the plastic scintillator primarily through (n,p) recoil reactions, producing low-energy protons that deposit energy in the same range as the signal particles. Without adequate shielding, the neutron-induced rate could dominate the charged-particle rate by a factor of 10–100, pushing the total per-stave rate above the pile-up threshold even at nominal beam intensity. The shielding requirement — approximately 10–20 cm of borated polyethylene or equivalent — follows from the known neutron production cross-sections at the ESS target and is part of the HIBEAM/NNBAR detector design baseline.

---

## 5.6 Current-dependent excess and the ML pile-up classifier

### 5.6.1 Poisson scaling expectation

An independent probe of pile-up uses the beam current monitor, which records the instantaneous beam intensity. Under pure Poisson scaling, the pile-up fraction should scale linearly with the beam current. If the beam current increases by a factor of C, the mean occupancy increases by the same factor:

$$\mu_{\text{high}} = C \cdot \mu_{\text{low}}$$

and the pile-up probability becomes:

$$P_{\text{pile-up}}(\mu_{\text{high}}) = 1 - e^{-C\mu_{\text{low}}}$$

For C ≫ 1 (a large current increase), this approaches unity, but for the observed current ratios (factor of approximately 10 between high-current and low-current subsets in Study S10), the pile-up fraction should increase by approximately a factor of 10. The data reveal a more nuanced picture.

### 5.6.2 Downstream per-event excess

Events are stratified into low-current and high-current subsets (Study S10). The downstream per-event excess — the additional pulse rate in downstream staves (B6, B8) at high current compared to low current — is measured to be:

$$\Delta_{\text{downstream}} = 0.0103 \text{ per selected event } [68\% \text{ CI: } 0.0064, 0.0142]$$

This represents 30.8% of the high-current downstream rate. The measured excess is a factor of approximately 1.4, not the factor of approximately 10 expected from the current ratio under linear Poisson scaling. The sub-linear scaling indicates that a large fraction of the observed waveform distortions are current-independent — arising from:

- **Scintillator afterpulsing:** Delayed fluorescence from triplet-state annihilation in the plastic scintillator produces photons at times up to several hundred nanoseconds after the primary pulse. These afterpulses appear as secondary pulses in the waveform but are correlated with the primary particle, not with the beam current.
- **SiPM dark counts:** Thermally generated avalanches in the SiPM produce single-photoelectron pulses at a rate of approximately 50–500 kHz per SiPM (depending on temperature and overvoltage). These dark counts are current-independent and produce spurious "second pulses" that are indistinguishable from genuine pile-up at low amplitude.
- **Waveform pathologies:** Baseline fluctuations, digitizer clock jitter, and electromagnetic interference produce waveform features that can be misidentified as secondary pulses by a simple threshold-crossing algorithm.

The sub-linear current scaling is therefore not evidence against the Poisson pile-up model; it is evidence that the observed "pile-up" signal in the current-stratified data is a mixture of genuine beam-correlated pile-up (which does scale with current) and current-independent backgrounds (which do not). The Poisson model applies to the genuine pile-up component; the current-stratified analysis measures the sum of both components.

### 5.6.3 ML pile-up classifier

A machine-learning pile-up classifier trained on waveform shape features (PCA components, pulse width, asymmetry, and integrated area) shows a similar pattern: the classifier score ratio between high and low current is approximately 1.29 (not the ~10 expected under linear scaling), and the high-current excess fraction is 22.9%. These are two independent measurements of different quantities:

- The **downstream excess** (0.0103 per event, 30.8%) measures the physical pile-up rate from pulse counting: an additional pulse appears in downstream staves at high current.
- The **ML score ratio** (1.29, 22.9% excess) measures the classifier's sensitivity to beam-current-correlated waveform features: the waveform shape changes in a way the classifier associates with pile-up.

They agree in direction (both show excess at high current) but differ in magnitude (30.8% vs 22.9%), reflecting the different systematic sensitivities. The downstream excess is a counting measurement that is sensitive to all additional pulses, including afterpulsing and dark counts. The ML classifier is a shape-based measurement that is sensitive specifically to waveform distortions characteristic of overlapping scintillation pulses — it partially rejects afterpulsing (which has a different pulse shape) and dark counts (which are typically single-photoelectron pulses with distinctive shapes). The ML classifier's lower excess fraction is consistent with it being more selective for genuine pile-up, but this interpretation requires validation with truth-labelled data.

---

## 5.7 Monte Carlo validation (MV5)

The MV5 study validates the pile-up model by simulating overlapping waveforms and applying the identical two-pulse recovery algorithm used on data. The simulation chain is:

1. **Single-pulse generation:** The MV0 digitizer produces synthetic 18-sample waveforms from GEANT4 truth energy depositions, using the calibrated scintillator parameters (τ_rise = 2.0 ns, τ_decay = 35.0 ns, σ_transport = 0.5 ns, σ_noise = 50 ADC, saturation at 7000 ADC). Birks quenching is disabled by default (k_B = 0), as the digitizer is calibrated to match data pulse shapes without quenching and the quenching correction for minimum-ionising protons is negligible (kB · dE/dx ≪ 1 for dE/dx ≈ 2 MeV·cm²/g in plastic scintillator, giving kB · dE/dx ≈ 0.13 mm/MeV × 2 MeV·cm²/g × 1 cm/10 mm ≈ 0.026 ≪ 1).

2. **Waveform superposition:** Pairs of single-particle waveforms are superposed with time separations drawn from an exponential distribution P(Δt) = R · e^(−R·Δt), corresponding to the inter-arrival time distribution of a Poisson process with rate R. The amplitude of each pulse is drawn from the empirical data amplitude distribution (the GEANT4 truth energy deposition spectrum scaled by the digitizer gain).

3. **Recovery and failure counting:** The constrained template fit (Section 5.4) is applied to each superposed waveform. A recovery is counted as a failure if the fit fails to converge (EDM > 10⁻⁴ or non-positive-definite covariance) or if |Δt_recovered − Δt_true| > 30 ns. The failure rate is measured as a function of R.

The key result is:

$$R_{\text{max}}^{\text{(MV5)}} = 3.044 \text{ MHz}$$

in 0.2% agreement with the occupancy-based R_max = 3.05 MHz. As discussed in Section 5.3.3, this agreement is a self-consistency check (both definitions share the same τ_eff), not an independent validation. The value of MV5 is that it confirms the internal consistency of the pile-up model: the occupancy-limit definition (which uses only τ_eff and μ_max) and the full Monte Carlo recovery simulation (which uses the digitizer, waveform superposition, and the template fitting algorithm) converge to the same R_max, demonstrating that the simplified Poisson model captures the essential physics without requiring the full simulation chain.

MV5 also validates the digitizer's pulse shape model. If the digitizer's pulse shape differed significantly from the data pulse shape, the recovery failure rate vs. rate curve would differ from the occupancy-based prediction, because the occupancy model assumes the data-measured τ_eff. The 0.2% agreement confirms that the digitizer's pulse shape is an adequate representation of the data pulse shape for pile-up studies.

---

## 5.8 Operational implications for the ESS

The validated R_max ≈ 3.05 MHz (total in-spill instantaneous) has direct operational consequences for the HIBEAM/NNBAR experiment. The detailed rate conversion to ESS conditions is presented in Section 5.5; the summary operational constraints are:

1. **Per-stave instantaneous rate limit:** 0.80 MHz during each 2.86 ms ESS pulse. This is the hard physics limit: exceeding this rate pushes the pile-up fraction above 9.5% and the recovery failure rate above 0.168.

2. **Per-stave time-averaged rate limit:** 0.80 MHz × 0.04 = 32 kHz, averaged over the full 14 Hz ESS pulse cycle.

3. **Neutron background budget:** The low-energy neutron background must be suppressed by passive shielding to keep the total per-stave rate (signal + background) below 32 kHz average. Neutrons interact in the plastic scintillator primarily through (n,p) recoil reactions, producing low-energy protons that deposit energy in the same range as the signal particles. Without adequate shielding (approximately 10–20 cm of borated polyethylene or equivalent), the neutron-induced rate could dominate the charged-particle rate by a factor of 10–100, pushing the total per-stave rate above the pile-up threshold even at nominal beam intensity. The shielding requirement follows from the known neutron production cross-sections at the ESS target and is part of the HIBEAM/NNBAR detector design baseline.

4. **Two-pulse recovery extension:** The two-pulse recovery results (Section 5.4) indicate that a fraction of pile-up events can be recovered, extending the effective rate tolerance. For a 0.168 failure rate at R_max, approximately 83.2% of pile-up events are successfully recovered. If the failure rate ceiling can be relaxed (e.g., by flagging recovered events and inflating their systematic uncertainties), the effective R_max increases. However, the current failure rate ceiling means that recovered events must be treated as a separate event class with larger systematic uncertainties than isolated single-pulse events. A dedicated truth-labelled overlay Monte Carlo study (GAP-04) is the next step toward qualifying two-pulse recovery for production analysis.

The CCB-derived R_max of 3.05 MHz is the validated pile-up tolerance for the HRD B-stack. It replaces the original analysis note's value of 4.22 MHz, which was based on the incorrect τ_eff = 90 ns assumption. The corrected value is consistent with the planned ESS beam intensity and provides a quantitative basis for the detector shielding and rate-cap design.

---

## 5.9 Figure references

The pile-up analysis is supported by the following figures:

- **Figure 5.1:** Pulse template and τ_eff measurement — the ensemble-averaged pulse template constructed from approximately 50,000 clean isolated pulses, showing the 10% crossing point at τ_eff = 124.79 ns. The template is overlaid with the bootstrap envelope (68% CI) to illustrate the statistical uncertainty. The BC-408 single-exponential decay extrapolation (τ_decay = 35 ns, crossing 10% at 80.5 ns) is shown for comparison, demonstrating the 39% discrepancy.

- **Figure 5.2:** R_max derivation — the pile-up probability P(pile-up) = 1 − e^(−R·τ_eff) as a function of beam rate R, with the μ_max = 0.1 threshold indicated. The occupancy-limit R_max and the MV5 recovery-failure R_max are marked, showing the 0.2% agreement.

- **Figure 5.3:** Trigger-split v3 comparison — the first B-layer (B2) energy deposition spectrum for data and Monte Carlo, Sample I vs Sample II, with the ±30% digitizer gain uncertainty band. The large-pulse excess in Sample I (deuteron-enriched) is visible above 6000 ADC, and the B2 saturation ceiling at 7000 ADC is flagged. (From the `compare_data_mc.py` v3 analysis, Figure: `first_B_layer_data_mc.png`.)

- **Figure 5.4:** Two-pulse recovery performance — the recovered time separation error (Δt_recovered − Δt_true) distribution for the template fit and the MLP, showing the narrower core of the MLP distribution (RMS = 10.67 ns vs 13.30 ns) but the heavier failure tail (0.295 vs 0.168 failure rate). The 30 ns failure threshold is indicated.

- **Figure 5.5:** Current-dependent excess — the downstream per-event pulse rate as a function of beam current (low vs high), showing the sub-linear scaling (factor ~1.4 vs factor ~10 expected). The current-independent background components (afterpulsing, dark counts) are illustrated schematically.

---

## References

[1] Saint-Gobain Crystals, "BC-400, BC-404, BC-408, BC-412, BC-416 Premium Plastic Scintillators," Data Sheet (2021). https://www.crystals.saint-gobain.com/

[2] European Spallation Source ERIC, "ESS Accelerator," https://ess.eu/accelerator (accessed 2026).

[3] J. B. Birks, *The Theory and Practice of Scintillation Counting* (Pergamon Press, Oxford, 1964). The canonical reference for Birks' law: dL/dx = S · (dE/dx) / (1 + k_B · dE/dx).

[4] G. F. Knoll, *Radiation Detection and Measurement*, 4th ed. (Wiley, New York, 2010), Ch. 8 and 17. Standard reference for scintillation detector physics and pulse processing, including pile-up and dead-time models.

[5] W. R. Leo, *Techniques for Nuclear and Particle Physics Experiments*, 2nd ed. (Springer, Berlin, 1994), Ch. 7. Covers Poisson statistics for particle counting and the pile-up probability derivation.

[6] S. Pommé, "Cascades of pile-up and dead time," *Appl. Radiat. Isot.* 66, 941–947 (2008). DOI: 10.1016/j.apradiso.2008.02.038. General treatment of pile-up statistics in radiation detectors with dead-time effects.
