# Physics / Statistics Derivation Baseline

Status: audit support for #1602/#1607/#1609. These equations are only valid under their stated assumptions. Detector-specific parameters still require measured or validated provenance.

## Poisson pulse-overlap probability

Assume arrivals form a stationary Poisson process with rate `r` and consider a fixed vulnerable time interval `tau` after an accepted pulse. Then the number of additional arrivals `N` in that interval is Poisson with mean `lambda = r tau`:

`P(N = k) = exp(-r tau) (r tau)^k / k!`.

Therefore the probability of at least one additional arrival is

`P_overlap = 1 - exp(-r tau)`.

This is **not** a universal detector rate limit. It is conditional on stationary independent arrivals and on a defined vulnerable interval. If the beam is bunched, rate varies in time, pulse windows depend on amplitude, or deadtime is paralyzable/non-paralyzable rather than a simple fixed overlap window, the model must be changed and validated. Any `Rmax` must additionally specify the allowed overlap/quality criterion.

## Covariance-aware linear combination

For measurements collected into vector `x` with covariance matrix `C`, estimate a common scalar quantity by `t_hat = w^T x` subject to unbiasedness `1^T w = 1`. Minimizing `Var(t_hat) = w^T C w` with a Lagrange multiplier gives

`w = C^{-1} 1 / (1^T C^{-1} 1)`

and

`Var(t_hat) = 1 / (1^T C^{-1} 1)`.

The familiar inverse-variance weighting is the special case of diagonal `C`. If stave or clock errors are correlated, diagonal weighting is not justified.

Reference basis: Particle Data Group statistics review; covariance terms must be retained when measurements are dependent.

## Variance of a difference

For two estimators `x` and `y`,

`Var(x - y) = Var(x) + Var(y) - 2 Cov(x,y)`.

Thus extracting a single-channel timing resolution from pairwise residual widths requires an explicit covariance model. Assuming independence is a physical/statistical assumption, not an identity.

## Robust central-68% width

If `q16` and `q84` are the 16th and 84th percentiles of a residual distribution, define

`sigma68 = (q84 - q16)/2`.

For an exactly Gaussian distribution this equals one standard deviation, but for asymmetric or heavy-tailed distributions it is only a robust width statistic. It must not be described as a Gaussian sigma without a distributional check; tail fraction/RMS or a goodness-of-fit diagnostic should accompany it where relevant.

## Birks-type quenching

A common Birks-law convention is

`dL/dx = S (dE/dx) / (1 + kB dE/dx)`.

The exact convention and units must match the implementation used by Geant4 and the material configuration. `kB dE/dx` must be dimensionless. Geant4 documents Birks quenching through `G4EmSaturation` and warns that the effective coefficient depends on the treatment/production threshold of delta electrons. Consequently, a value of `kB` fitted within a simulation chain is a model parameter under that configuration unless independently calibrated against the detector.

Authoritative software reference: Geant4 Book for Application Developers, Birks Quenching / `G4EmSaturation` documentation.

## Stopping-power comparison

NIST PSTAR tabulates stopping power and range for **protons**. A comparison to PSTAR is only meaningful when the simulation observable represents the same physical stopping-power quantity, material and projectile/energy regime. Sensitive-volume deposited energy divided by path length is not automatically identical to projectile total stopping power when secondaries can carry energy away or when the projectile changes energy substantially over the scoring interval.

A deuteron mapping to a proton table using an equal-velocity `E_d/2` proxy may be a diagnostic approximation but is not direct NIST deuteron evidence.

## Audit rule for phenomenological corrections

Any correction of the form `f(A)`, `A + B/sqrt(A)`, polynomial timewalk, empirical saturation map, or ML residual correction must document:

1. dimensional consistency;
2. expected sign/monotonicity from detector response;
3. fitted parameter provenance;
4. training/calibration domain;
5. held-out residual trend after correction;
6. sensitivity to alternate defensible functional forms;
7. transfer across run/stave/operating conditions.

A good fit on the same data used to select the form is not physical justification.
