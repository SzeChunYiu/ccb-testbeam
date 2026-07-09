# §4 — Timing Analysis: Sub-Nanosecond Resolution with One-Ended WLS Readout

The timing resolution of the HRD scintillator stacks is the primary physics deliverable of the CCB test-beam programme. The HIBEAM/NNBAR experiment requires same-particle timing at the sub-nanosecond level to distinguish signal events from background. This chapter presents the complete timing analysis chain: from raw waveform to calibrated particle arrival time, through amplitude-dependent timewalk correction, to the final multi-stave combined time.

## Principles of scintillator timing

When a charged particle traverses a plastic scintillator stave, the resulting scintillation light pulse arrives at the SiPM after propagating through the wavelength-shifting (WLS) fibre. The arrival time measured by the readout electronics, t_measured, differs from the true particle crossing time, t_true, by several systematic offsets:

t_measured = t_true + t_scint + t_WLS(x) + t_SiPM + t_electronics

where t_scint is the scintillator rise time (typically 0.9 ns for BC-408), t_WLS(x) = x / v_fibre is the position-dependent fibre propagation delay (v_fibre ≈ 17 cm ns⁻¹, x is distance from hit position to readout end), t_SiPM is the SiPM response time (~0.1–0.5 ns), and t_electronics is the cable and digitizer delay (constant per channel). The position-dependent term t_WLS(x) is the dominant contribution to the single-stave timing resolution: for a 100 cm stave, the propagation delay varies from 0 ns (hit at readout end) to approximately 5.9 ns (hit at distal end). Without position measurement, this variation broadens the measured time distribution for particles hitting at random positions along the stave.

The timing resolution is extracted from inter-stave time residuals. When the same particle traverses two successive staves, the true crossing times satisfy t_true(B_j) = t_true(B_i) + Δt_TOF, where Δt_TOF ≈ 0.1–0.2 ns for relativistic 190 MeV protons traversing a few centimetres of scintillator — negligible compared to the single-stave resolution. The measured time difference is:

Δt_measured = t_measured(B_j) − t_measured(B_i) = [t_true(B_j) − t_true(B_i)] + [ε(B_j) − ε(B_i)]

where ε(B_i) represents the combined measurement error for stave i. If the errors are independent and have equal variance σ²_single, then Δt_measured follows a distribution with variance 2σ²_single, and the single-stave resolution is σ_single = σ(Δt) / √2. For non-Gaussian residual distributions, we quote σ₆₈ — the half-width of the central 68% interval of the residual distribution — as a robust dispersion measure that coincides with σ for a true Gaussian.

## The timing reconstruction chain

The reconstruction proceeds through four stages:

**Stage 1: Constant-fraction discrimination (CFD).** The waveform is interpolated to sub-sample precision, and the time at which the pulse reaches 20% of its peak amplitude is determined by linear interpolation between the two samples bracketing the threshold crossing. The constant-fraction method is preferred over leading-edge discrimination because it is, to first order, independent of pulse amplitude. In practice, residual amplitude dependence — timewalk — remains because the pulse shape is not strictly amplitude-independent.

**Stage 2: Template phase fitting (optional).** The CFD time provides a seed for a fit of the full waveform to an average pulse template constructed by aligning and averaging several thousand high-amplitude, isolated pulses. The template fit is sensitive to pulse-shape variations and produces worse resolution (σ₆₈ ≈ 2.89 ns) than the simpler CFD approach (σ₆₈ ≈ 1.85 ns). The CFD is the canonical pickoff method.

**Stage 3: Amplitude timewalk correction.** The raw CFD time exhibits a systematic dependence on pulse amplitude: larger pulses appear to arrive earlier because their steeper rising edge crosses the 20% threshold sooner in absolute time. The empirical correction is:

t_corrected = t_CFD − f(A), with f(A) = A₀ + B/A

The B/A term captures the leading-order residual: as A → ∞, the correction approaches the constant A₀ (the asymptotic CFD offset); as A decreases, the correction grows, reflecting the slower rise of small pulses. The parameters A₀ and B are fitted per stave from calibration runs, using the requirement that inter-stave residuals for through-going particles have zero mean. The B2 stave is excluded from the calibration fit to avoid bias from the stopping-deuteron topology.

**Stage 4: Multi-stave combination.** When a particle traverses multiple staves, the individual stave times are combined in a weighted average with weights w_i = 1/σ²_i (inverse variance). For equal resolutions, this yields the familiar σ_combined = σ_single / √N. Using B4, B6, and B8 (excluding B2), the combined event time achieves σ₆₈ ≈ 0.54–0.56 ns.

## Per-stave timing performance

| Stave | σ₆₈ (ns) | Dominant Limitation |
|---|---|---|
| B2 | ~2.8 | Topology-driven covariance (stopping deuterons); excluded from precision timing |
| B4 | ~1.45 | WLS propagation delay; moderate pile-up |
| B6 | **0.68–0.75** | Best single-stave: cleaner pulse shapes at depth |
| B8 | ~0.93 | Lower statistics; some penetration dependence |
| B4+B6+B8 | **0.54–0.56** | Combined event time |

**Why B6 outperforms B4:** The B4 stave sits at intermediate depth where both through-going protons and stopping deuterons deposit energy, producing a mixture of pulse shapes. The B6 stave, at greater depth, is traversed almost exclusively by through-going protons (deuterons stop at B2–B4), yielding a more uniform pulse population with cleaner rising edges. The lower particle flux at B6 also reduces pile-up contamination.

The A-stack provides an independent cross-check: the A1–A3 inter-stave residual width of 1.39 ns (Sample III) reproduces the original analysis note's value of 1.43 ns, confirming that the timing reconstruction pipeline is not over-tuned to the B-stack.

## The B2 covariance problem

Inter-stave residuals involving B2 exhibit dramatically larger variance than residuals among downstream staves. The covariance matrix reveals:

- B2–X pairs: covariance ≈ 1042 ns²
- B4–B6, B4–B8, B6–B8 pairs: covariance ≈ 16 ns²

This factor-of-65 enhancement is a physics effect, not a detector malfunction. The B2 stave is the first stave encountered by particles entering the B-stack. For Sample I, the majority of particles are deuterons that stop in B2 or B4. A deuteron stopping in B2 deposits a large, saturating energy deposition near the Bragg peak; the resulting pulse shape is distorted by saturation, and the CFD time is systematically biased. The particles that do produce B2–B4 residuals are the minority population of through-going protons, whose timing is correlated with the B4 measurement through the shared track topology. The practical consequence is that **B2 must be excluded from precision event-time estimates.**

## Monte Carlo validation

The GEANT4 simulation with the MV0 digitizer provides an independent assessment. The raw CFD timing resolution in the simulation (σ₆₈ = 1.744 ± 0.007 ns) agrees with the data (σ₆₈ = 1.85 ns) to within 1.05σ — a pass. However, the timewalk-corrected resolution shows tension: the MC yields σ₆₈ = 1.770 ns after correction, while the data reach σ₆₈ = 1.50 ns, a +2.68σ discrepancy.

The root cause, diagnosed in Study MV4b, is an unphysical negative B coefficient in the toy digitizer's CFD model. The digitizer parametrises the timewalk as B/√ADC, which produces an inverted amplitude dependence. The correct parametrisation, B/amplitude, follows from the physical model and is a code-only fix. Once corrected, the timewalk-corrected MC timing is expected to match the data.

## Analytic vs machine-learning timewalk

A systematic comparison reveals a methodological lesson. The analytic correction f(A) = A₀ + B/A achieves σ₆₈ = 1.49–1.55 ns. A histogram gradient boosting (HGB) regressor initially appeared to improve this to σ₆₈ = 1.107 ns, but this result is explicitly **gated**: the HGB model was evaluated in-fold rather than under rigorous leave-one-run-out (LORO) cross-validation. A subsequent LORO evaluation showed the HGB advantage narrowing or disappearing when the model is required to generalise to unseen runs. The analytic correction remains the recommended method for its transparency, physical interpretability, and verified cross-run stability.

## Systematic uncertainty budget

| Source | Contribution (ns) | Method |
|---|---|---|
| CFD fraction choice (20%) | ±0.05 | Scanned 10–50% in S02 |
| Timewalk calibration run choice | ±0.08 | Variation across calibration runs |
| Gaussian-core assumption | ±0.03 | σ₆₈ is robust; core non-Gaussianity assessed via GAP-07 |
| Pile-up contamination | ±0.10 | Estimated from live-time fraction |
| WLS position dependence | +0.30 (one-ended → two-ended) | Projected √2 improvement (unvalidated) |
| **Total (B6 single-stave)** | **±0.15** | Added in quadrature |

The dominant irreducible systematic is the one-ended WLS position dependence. The projected factor-of-√2 improvement for two-ended readout would bring the single-stave resolution to σ₆₈ ≈ 0.48–0.53 ns, but this projection assumes uncorrelated end measurements, an assumption that remains to be validated.
