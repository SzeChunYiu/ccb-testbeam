# 06 — Pile-up

## Working definition
A **late or overlapping-pulse topology**: the waveform contains early activity plus a later
rising/maximum component, breaking the single-pulse / same-particle assumption. Detected
data-drivenly via (a) broad B2-containing pair residuals, (b) large event timing span Δt_B,
(c) waveforms with early activity + later maximum, (d) large adaptive-pedestal lowering.

## Traditional evidence
- **Sample I B2 pair residuals 37–41 ns wide** vs downstream 1.2–1.8 ns — the smoking gun.
- **Waveform morphology:** B2 candidates show early activity → dip → later maximum (Fig. 45).
- **Rate dependence (runs 46+47 at 2 nA vs 20 nA):** multi-stave fraction 1.56% (2 nA) vs
  2.68% (20 nA); ≥3-stave 0.41% vs 0.85%; any downstream hit 2.31% vs 3.34%. Higher current ⇒
  more multi-stave/downstream hits ⇒ more pile-up-like component.

## Pile-up rate model (App. G)
- Pile-up fraction per pulse scales ~linearly with current: f(I) = f₀ + kI.
- Poisson occupancy μ: P₀=e^{−μ}, P₁=μe^{−μ}, P≥₂=1−P₀−P₁.
- Total efficiency ε(μ) = P₀ + P₁·ε₁ (≥2 extra pulses conservatively treated as failures).
- **Max tolerable rate** R_max = μ_max / τ_eff, with τ_eff = 90 ns nominal:

| Requirement (>90% eff) | μ_max | R_max |
|---|---|---|
| timing < 1 ns | 0.425 | 4.72 MHz |
| timing < 2 ns | 0.490 | 5.44 MHz |
| peak amp < 10% | 0.385 | 4.28 MHz |
| charge/area < 20% | 0.445 | 4.94 MHz |
| **combined \|Δt\|<1 ns AND area<20%** | **0.380** | **≈ 4.22 MHz** |

⚠ Scales as 1/τ_eff; **not** a universal hardware limit. τ_eff = 90 ns is an assumption to
test (S10).

## Injection-based tolerance (traditional, controlled)
Inject a second clean real pulse onto a clean primary at random delay/amplitude; measure
recovery of the primary time/amplitude/area:
- All: σ_t 2.68 → 0.98 ns. Separation ≥3 bins: 2.33 → 0.55 ns (ε_{|Δt|<1ns}=0.961).
  Separation <3 bins: 3.44 → 1.66 ns. **Close, comparable-amplitude pile-up is the hard case.**

## Current-dependent excess (App. G)
The ML pile-up score ratio high/low current is **~1.29, not ~10** → the raw score is **not**
pure beam pile-up; it has a large current-independent baseline (scintillator tails, topology,
waveform pathologies). Only the **high−low excess ≈ 9.2% downstream at 20 nA** is genuine beam
pile-up. **This is the key honest result: most of the "pile-up score" is not beam pile-up.**

## ML handles on pile-up (benchmarked against the above)
See [07_ml_methods.md](07_ml_methods.md). Three complementary ML approaches:
1. **Injection-trained classifiers** (App. B): dropout & pile-up tagging + timing recovery.
2. **Weakly-supervised current classifier** (App. H, CWoLa): learns the current-dependent
   component from 20 nA vs 2 nA without truth.
3. **Timing-control-region classifier** (App. I): label clean (D_t<3 ns) vs gross (D_t>50 ns),
   train on waveform shape only, use as a pile-up/pathology rejection variable.

## Open issues
- τ_eff = 90 ns assumption (S10); occupancy model needs a measured live-time.
- Constrained **two-pulse template fit** (App. B.5 recommendation) is **not yet implemented**
  — a traditional method that should be built and benchmarked vs ML recovery (S11).
- App. I positive class is only **72 events** — uncertainties must be bootstrapped (S12).
