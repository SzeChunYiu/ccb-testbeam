# S46a — 190-MeV p-d source-model uncertainty: sampled envelope closure + lab-frame bands (#1179)

- **Ticket:** `1786866977.1138000.3f71d0b1` · **Worker:** testbeam-laptop · **Issue:** #1179
- **Script:** `scripts/s46a_1786866977_1179_3f71d0b1_cs_source_uncertainty_sampled_closure.py`
  · **Config:** `configs/1786866977.1138000.3f71d0b1_cs_source_uncertainty.json`
- **Extends:** `results/research/sigma_cm_source_uncertainty_v1.json` (af0c3989, PR #1186)
- **Verdict:** **PASS** — all 12 gates green. **Fully deterministic** (fixed
  seeds, no wall-clock or platform inputs): rerun reproduces every number and hash.

## Inputs (pinned, fail-closed)

- Table `geant4/src_patch/sigma_pd_cm_190.txt` — sha256 `0ca33e76a745dde0…`,
  28 rows, support 26.49–169.78 deg
  (verified against `.source.json` before anything else runs; DOI 10.1103/PhysRevC.71.064004).
- v1 result sha256 `5afbb11fd3f4c085…` — every v1 number below re-derived, not trusted.

## Sampler known-answer (law of #1178)

Piecewise-linear pdf through nodes σᵢ·sin θᵢ, trapezoid interval masses, analytic
quadratic interval inverse (`linear_node_pdf_exact_inverse_v1` + measured-support
truncation):

| check | result |
|---|---|
| interval inverse vs repo `inverse_linear_pdf_fraction` (27×10 points) | max \|Δt\| = 1.1e-16 |
| u → θ → CDF round-trip (200,001 points) | max \|Δ\| = 8.9e-16 |
| analytic box envelope re-derived vs v1 | max \|Δ\| = 2.2e-16 |

## Sampled validation (N = 5,000,000, seed 1179, common random numbers)

All nuisance configurations consume the **same** uniform draws, so paired
quantile-shift curves are deterministic; CDF sup-differences carry only
O(√(p(1−p)/N)) ≈ 1e-4 binomial noise, gated with an explicit tolerance
(MC_TOL = 2.7e-4, 5σ at p = 0.015).

| configuration | max \|Δθ\| vs nominal [deg] | max up / down ECDF excursion | within envelope |
|---|---|---|---|
| common ×1.045 | 2.8e-13 | — (shape invariant) | — |
| corner +3%/−3% @ 46.95° | 1.893 | +0.01435 / +0.00000 | yes |
| corner −3%/+3% @ 46.95° | 1.842 | +0.00000 / -0.01447 | yes |
| alternating +−3% | 0.093 | +0.00148 / -0.00087 | yes |
| alternating −+3% | 0.093 | +0.00086 / -0.00149 | yes |

Analytic envelope: max up 0.01431, max down
−0.01438 (both at ≈46.95°). Exact nominal mean
θ_cm = 56.7839620005 deg (v1: 56.7839620005,
Δ = 1e-14); population sd θ_cm = 33.153 deg.

## Negative controls (issue-required, all executed and gated)

| control | expectation | measured | gate |
|---|---|---|---|
| (a) common multiplicative scale | normalized shape invariant | max \|Δθ\| = 2.8e-13 deg (float noise) | PASS |
| (b) alternating ±3% | does NOT cancel (shape moves) | sampled \|exc\| = 1.4822e-03 vs v1 analytic 1.4570e-03 (Δ 2.5e-05 < MC_TOL) | PASS |
| (c) zero uncertainty | bit-identical nominal sample | `array_equal` = True | PASS |
| (d) box configs ⊆ envelope | envelope bounds, never adds | all four corner/alternating configs inside, excess ≤ 8.5e-6 | PASS |

No duplicate parameterization is counted: the common scale and the per-node box
are separate nuisance modes, and the alternating controls are diagnostics, never
added to the envelope.

## Row-statistical nuisance (diagonal, iid)

200 seeded replicas, σᵢ → σᵢ(1+εᵢ), εᵢ ~ N(0, sᵢ/σᵢ), propagated through
**exact analytic per-replica means** (zero Monte-Carlo noise):

- mean θ_cm sd = 0.02429 deg vs v1 delta-method
  0.02253 deg → ratio
  1.078 (excess = second-order terms the
  linear delta method ignores; consistent within replica error).
- mean θ_lab sd = 0.02014 deg.

**Rejected design (recorded):** a first replica pass sampled M = 200k events per
replica and measured sd = 0.0785 deg — 3.5× the delta prediction. Diagnosis: with
population sd θ = 33.2 deg, each replica mean
carries MC noise 0.0741 deg, which dominates
in quadrature (prediction 0.07748 deg vs measured
0.07846). The v1 delta method is CONSISTENT with sampling once this is accounted;
the sampled design was replaced by exact analytic means, not tuned.

## Lab-frame propagation (θ_cm → θ_lab)

Exact two-body relativistic kinematics for p(190 MeV) + d → p + d, round-trip
validated against the repo's own `weight_adapter._reconstruct_cm_theta`
(S21b exact) over 1001 points: max \|Δθ_cm\| =
4.0e-13 deg, \|Δθ_lab\| = 2.8e-14 deg
(`offset=0` pinned — the production default 0.115 deg is an alignment convention,
not kinematics).

- Nominal mean θ_lab = 39.345 deg.
- ±3% box envelope on the mean (exact means under the corner laws):
  **[38.806, 39.886] deg** — brackets the
  nominal (mean-of-map ≠ map-of-mean for this skewed distribution; the point-mapped
  corner means would NOT bracket and were rejected as a defect).
- Full quantile curves (199 quantiles) for nominal + both corners recorded in
  `result.json` and plotted in fig 2.

## Absolute-yield rule

A fully common multiplicative normalization cancels from the normalized angular shape only. Any absolute-yield/rate estimand must restore the common normalization mode (bounded by the published total systematic <4.5% at 190 MeV); no such claim is made or authorized here.

## Scientific boundary

Source-level deterministic/conditional uncertainty research only. The 3% node box is a sensitivity envelope, not a confidence region or an inferred covariance. No detector response, production Geant4 sample, or detector-performance claim is validated. Production-Geant4 propagation with perturbed tables
(end-to-end detector-level systematics) remains the separate blocked scope of
CL-026 / `docs/SYSTEMATIC_UNCERTAINTIES.md`; nothing here authorizes a detector
claim.

## Issue acceptance coverage (#1179)

| acceptance criterion | status |
|---|---|
| meanings/units explicit | every quantity above carries units; JSON schemas versioned (`ccb_sigma_cm_source_uncertainty_v2`) |
| envelope source-mapped + versioned | table sha256 + `.source.json` DOI pinned; v1 result sha pinned and re-derived |
| shape-vs-rate nuisance separated | control (a) + absolute-yield rule: common normalization cancels from shape only |
| source-level propagated before detector conclusions | θ_lab bands delivered source-level; detector claims explicitly out of scope |
| table SHA, sampler mode, nuisance mode, seeds, counts, output hashes recorded | `manifest.json`: git head 3f71d0b1d, table/v1/result/v2 sha256, seeds, N, box/scale/split |
| CL-021 central-value-only until gate passes | gates green ⇒ CL-021 updated in this PR to envelope-propagated (source level), still no detector claim |
| negative controls | (a)–(d) executed and gated above |
| no inference of unreported covariance | none inferred: box = sensitivity envelope; row-stat = diagonal only, stated |

## Outputs

- `result.json` (full), `manifest.json` (hashes/seeds/provenance)
- `fig1_envelope_cdf.png`, `fig2_lab_band.png`
- `results/research/sigma_cm_source_uncertainty_v2.json` (paper-facing summary)
