# 05 — Timing resolution

## Method (traditional)
1. Form **same-particle inter-stave residuals** Δt_ij = t_i^corr − t_j^corr (− expected TOF).
2. Histogram. The **wide-range** histograms are shown but **not fitted** (heavy non-Gaussian
   tails, especially Sample I B2 pairs).
3. Fit only the **narrow core −5 < Δt < 5 ns** with **Gaussian + constant**
   N(Δt)=A·exp[−(Δt−μ)²/2σ²]+c (40 bins, Poisson errors). Quoted σ is a **narrow-core σ, not
   the full RMS** — critical caveat.
4. **Variance decomposition** assuming independent stave errors: σ_ij² ≃ σ_i² + σ_j² (Eq. 75).
   Two solvers: all-pair NNLS, and downstream-only exact (B4–B6, B4–B8, B6–B8).

## Per-stave resolution (newer report, Table 19)

| Stave | Sample I (all-pair) | Sample I (downstream) | Sample II (all-pair) | Sample II (downstream) |
|---|---|---|---|---|
| B2 | 1.479 | — | 1.107 | — |
| B4 | 1.066 | 1.470 | 1.113 | 1.559 |
| B6 | 1.077 | **0.675** | 1.087 | **0.754** |
| B8 | 1.091 | 0.933 | 1.212 | 0.942 |

**B6 is consistently the best stave (~0.68–0.75 ns).** Numbers differ from the older v41 note
(which gave e.g. Sample II all-pair B2 1.112, B4 0.909, B6 0.810, B8 0.982) — reconciling the
two is part of Study S04.

## Combined multi-stave event time (App. E)
Inverse-variance weighted combination of downstream staves (B2 ignored), with an internal
consistency pull R_t = √[ (1/(N_S−1)) Σ ((t_i−δ_i)−t̂_S)²/σ_i² ]:

| Combination | Sample I σ_comb | Sample II σ_comb |
|---|---|---|
| B4+B6 | 0.707 | 0.718 |
| B6+B8 | 0.584 | 0.603 |
| B4+B6+B8 | **0.539** | **0.558** |

- Preferred precision category: **3-stave B4+B6+B8 with R_t < 2** (≈95% of events).
- ⚠ B4+B8-only is rare and tail-heavy (p68(R_t) up to 4.99) — must **not** define a precision
  sample.

## Two-ended-readout projection (§13.6)
Averaging both fibre ends cancels first-order longitudinal WLS delay; for uncorrelated end
resolutions σ(t^2end) ≃ σ_end/√2 → **factor √2 improvement**, indicatively **σ ≈ 0.6–1.0 ns**.
- ⚠ Does **not** improve correlated terms (clock jitter, common pickup, correlated timewalk).
  Quantifying the correlated vs uncorrelated split is Study S05.

## The Sample I B2 anomaly
B2-containing pairs in Sample I have robust widths of **37–41 ns** — *tens of ns*, far beyond
anything explainable by TOF (≤0.5 ns), angle (≤0.004 ns), WLS (≤0.06 ns), or downstream
resolution. Interpreted as a **late/overlapping-pulse (pile-up-like) topology**, not a method
failure → handled in [06_pileup.md](06_pileup.md), and B2 is excluded from the timing estimate.

## Open issues for the timing-resolution programme
- χ²/ndf of the Gaussian-core fits is **not reported** (Table 18 blank) — goodness unknown.
- Narrow-core σ vs robust width vs **full RMS** must be reported together (S04).
- Independence assumption σ_ij²=σ_i²+σ_j² is unverified (correlated electronics?) (S05).
- σ vs amplitude/energy dependence only partially mapped (S06).
