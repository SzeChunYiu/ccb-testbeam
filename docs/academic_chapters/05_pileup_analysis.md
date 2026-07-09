# §5 — Pile-up Analysis: Rate Limits and Two-Pulse Recovery

The HRD scintillator stacks must operate in a high-rate beam environment where multiple beam particles can traverse the same stave within the 180 ns waveform acquisition window. When the scintillation light from two or more particles overlaps in time, the resulting waveform superposition distorts both the reconstructed amplitude and the reconstructed arrival time of each pulse. This phenomenon, known as pile-up, sets the fundamental rate limit for the detector. This chapter presents the measurement of the effective waveform live-time τ_eff, the derivation of the maximum tolerable beam rate R_max, the Monte Carlo validation of the pile-up model, and the evaluation of two-pulse decomposition methods.

## The physics of scintillator pulse pile-up

Consider a single scintillator stave exposed to a pulsed proton beam. The beam arrives in spills — short bursts of particles — with a characteristic duty factor D (the fraction of time during which beam is present). Within a spill, the arrival times of individual particles at a given stave follow a Poisson process with rate R (particles per second). The probability that n particles arrive within a time window τ is:

P(n; μ) = μⁿ e^(−μ) / n!, where μ = R · τ

The pile-up probability — the chance that a second particle arrives within τ of the first, distorting the waveform — is P(pile-up) = 1 − e^(−Rτ) ≈ Rτ for Rτ ≪ 1. The parameter τ that governs this probability is not simply the 180 ns acquisition window; it is the effective live-time τ_eff, defined as the time interval during which a second pulse would produce a measurable distortion of the first pulse's reconstructed amplitude or time.

The effective live-time is determined by the scintillator pulse shape. For BC-408 plastic scintillator with a decay time τ_decay ≈ 35–42 ns, the light pulse falls to 10% of its peak after approximately 2.3 × τ_decay ≈ 80–100 ns. The WLS fibre adds additional time dispersion (σ_transport ≈ 0.5 ns), and the SiPM recovery time contributes a tail extending to ~150 ns. The combined effect is that a pulse remains "live" — capable of being distorted by an overlapping second pulse — for substantially longer than the simple scintillator decay time would suggest.

## Measurement of the effective live-time

The effective live-time τ_eff is measured directly from the data by studying the pulse template shape at late times (Study S10). The method constructs an average pulse template from several thousand isolated, high-amplitude pulses aligned at their CFD times. The time at which the template amplitude falls below 10% of its peak — the "live10" crossing — defines τ_eff. This threshold is chosen because a second pulse arriving after the first has fallen to 10% of its peak contributes less than 10% to the combined amplitude and introduces a timing error smaller than the single-stave resolution.

The measurement yields:

τ_eff = 124.79 ns, bootstrap 68% CI: [123.33, 126.36] ns

This value is 39% larger than the 90 ns assumed in the original analysis note. The discrepancy arises because the original estimate used only the scintillator decay time and neglected the WLS fibre dispersion, SiPM recovery tail, and the template construction method.

## Derivation of R_max

The maximum tolerable beam rate R_max is the rate at which pile-up-induced distortions reach a predefined acceptability threshold. Two independent definitions are used, yielding consistent results:

**Definition 1 (occupancy limit):** R_max = μ_max / τ_eff, where μ_max is the maximum acceptable mean occupancy. For Poisson statistics, μ_max = 0.1 corresponds to a 9.5% pile-up probability, the threshold where timing degradation from pile-up equals the single-stave timing resolution. With τ_eff = 124.79 ns:

R_max(occupancy) = 0.1 / 124.79 × 10⁻⁹ s = 0.80 MHz (per stave, in-spill instantaneous)

Multiplying by the beam duty factor D = 0.38 and accounting for four instrumented staves sharing the beam:

R_max(experiment) = 0.80 MHz × 4 staves / 0.38 = 3.05 MHz (total beam rate)

**Definition 2 (recovery failure limit):** R_max is the rate at which the two-pulse recovery failure rate exceeds the traditional template ceiling of 0.168. Monte Carlo simulation of overlapping waveforms (Study MV5) yields R_max(recovery) = 3.044 MHz under the same τ_eff = 124.8 ns assumption — in 0.2% agreement with the occupancy-based estimate.

The agreement between these two independent definitions, and between data and Monte Carlo, establishes R_max ≈ 3.05 MHz as the validated pile-up tolerance of the HRD B-stack. The original analysis note's value of 4.22 MHz, based on τ_eff = 90 ns, is confirmed as an error arising from an incorrect effective live-time assumption.

## Two-pulse decomposition

When pile-up does occur, the overlapping waveform can, in principle, be decomposed into its constituent single-particle pulses. This is a non-trivial inverse problem: from a single 18-sample waveform containing the sum of two unknown pulses at unknown relative times, one must recover both amplitudes and both arrival times.

**Constrained template fit.** The conventional approach fits the sum of two template pulses, each with its own amplitude and time, to the observed waveform by minimising χ². Constraints are imposed: both amplitudes must be positive, and the time separation must exceed a minimum of 2 samples (20 ns). The failure rate — the fraction of fits that either fail to converge or produce a recovered time separation that deviates from the true value by more than 30 ns — is 0.168 at low rate. The time RMS for successfully recovered pulses is 13.30 ns.

**Machine-learning recovery.** A compact multi-layer perceptron (MLP) and a 1D convolutional neural network (CNN) were trained on simulated overlapping waveforms to directly regress the two pulse amplitudes and times (Study S11). The ML approach achieves better time resolution (RMS = 10.67 ns for the MLP, 9.28 ns for the amplitude-binned variant) than the template fit, because the neural network can learn pulse-shape features that the rigid template misses — particularly the saturation-induced pulse-shape distortion at high amplitude and the SiPM recovery tail.

However, the ML approach exhibits a higher failure rate: 0.295 compared to 0.168 for the template fit. This is a fundamental trade-off: the ML recovers more challenging overlaps but also fails more often on cases where its training distribution does not match the data. The conventional template fit is therefore the recommended method at the accepted-recovery operating point. ML two-pulse recovery is gated pending a dedicated Monte Carlo overlay study with truth-labelled overlap events (GAP-04).

## Current-dependent excess and the ML pile-up classifier

An independent probe of pile-up uses the beam current monitor, which records the instantaneous beam intensity. Events are stratified into low-current and high-current subsets (Study S10). Under pure Poisson scaling, the pile-up fraction should scale linearly with the current: a factor-of-10 increase in beam current should produce a factor-of-10 increase in pile-up rate. The data reveal a more nuanced picture.

The downstream per-event excess — the additional pulse rate in downstream staves (B6, B8) at high current compared to low current — is measured to be 0.0103 per selected event [68% CI: 0.0064, 0.0142]. This represents 30.8% of the high-current downstream rate, confirming that pile-up does increase with beam current but sub-linearly: the measured excess is a factor of ~1.4, not the factor of ~10 expected from the current ratio. The sub-linear scaling indicates that a large fraction of the observed waveform distortions are current-independent — arising from scintillator afterpulsing, SiPM dark counts, and waveform pathologies present even at low beam intensity.

A machine-learning pile-up classifier trained on waveform shape features shows a similar pattern: the classifier score ratio between high and low current is ~1.29 (not the ~10 expected under linear scaling), and the high-current excess fraction is 22.9%. These are two independent measurements of different quantities: the downstream excess measures physical pile-up rate from pulse counting; the ML score ratio measures the classifier's sensitivity to beam-current-correlated waveform features. They agree in direction but differ in magnitude, reflecting the different systematic sensitivities.

## Implications for detector operation

The validated R_max ≈ 3.05 MHz has direct operational consequences for the HIBEAM/NNBAR experiment at the ESS. The ESS neutron beam is pulsed at 14 Hz with a 2.86 ms pulse width, giving a duty factor of 4.0%. For the HRD stacks positioned approximately 100 cm from the target, the expected charged-particle flux during beam-on periods must be kept below R_max · D_ESS / (4 staves) ≈ 30 kHz per stave to maintain pile-up distortions below the acceptable threshold. This rate is achievable with the planned ESS beam intensity, provided that passive shielding reduces the low-energy neutron background, which would otherwise dominate the single-stave rate.

The two-pulse recovery results indicate that a fraction of pile-up events can be recovered, extending the effective rate tolerance. However, the current failure rate ceiling means that recovered events must be flagged and their systematic uncertainties inflated relative to isolated single-pulse events. A dedicated truth-labelled overlay Monte Carlo study is the next step toward qualifying two-pulse recovery for production analysis.
