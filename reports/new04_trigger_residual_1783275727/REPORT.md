# NEW-04 — Data-side residual of the MV3 ideal-trigger over-purification

- Generated: 2026-07-05 (UTC)
- Study ID: **NEW-04** (STUDY_GAPS §2.1 / backlog B-M1 follow-up)
- Depends on: **B-M1 / MV3 v5** (`reports/mv3_v5_realtrigger_1783242005/`), **S10** pile-up
  rate model (`reports/1780997954.15277.548b01a3__s10_pileup_rate_model/`),
  **S21/S23** trigger truth, `docs/06_pileup.md`, `docs/01_setup_and_detector.md`.
- Artifacts (this dir): `new04_summary.json` (machine-readable), `new04_residual_budget.py`
  (arithmetic, reproduces every number below).
- Compute: none required — a first-principles budget over numbers already established in the
  cited reports (no new GEANT4 production, no data staging touched).

---

## Question

MV3 v5 established, with a **real** GEANT4 `Trig_bar` sensitive-detector two-arm coincidence,
that the trigger — not missing material — drives the B-stack stopping-depth concentration
(untriggered B2 45.9% -> triggered **99.7%**). But the *ideal* simulated trigger
**over-purifies**: it produces a 99.7% B2 sample, overshooting the data's own coincidence
sample (Sample I = **93.3%** B2). In non-B2 (deep-stave) terms:

| | B2 | non-B2 (B4+B6+B8) |
|---|---:|---:|
| MC ideal two-arm coincidence | 99.7% | **0.3%** |
| Data Sample I (A.B coincidence) | 93.3% | **6.7%** |
| **Residual to explain** | 6.4 pts | **6.4 pts** |

The MC coincidence is perfect, noise-free, accidental-free, and single-event (same primary
vertex). The data trigger is a hardware A.B coincidence in a 15 ns window on a few-MHz beam.
**This report budgets the 6.4-point residual from data-side effects the ideal MC omits.**

---

## Inputs (all traceable)

| Quantity | Value | Source |
|---|---|---|
| Coincidence window | "within **15 ns**" | `docs/01_setup_and_detector.md:27`; WIKI section 8 |
| Beam / occupancy rate @ 20 nA | **R_max <= 3.05 MHz** (mu_max 0.380 / tau_eff 124.8 ns), **one-sided UPPER bound** | `docs/06_pileup.md`, `docs/SYSTEMATIC_UNCERTAINTIES.md`. **The old 4.22 MHz @ tau_eff = 90 ns is retracted.** |
| MC per-pd-event trigger fractions | A_fired 3.65%, B_fired 11.1%, **coincidence 3.62%** (A subset of B) | MV3 v5 REPORT |
| MC deep-proton A-firing (truth) | **0.06%** (conjugate 37 MeV deuteron ranges out before the A-paddle) | MV3 v5 REPORT |
| Data Sample II (B-only = B-singles) non-B2 | **30.5%** | MV3 v5 REPORT (0.695 B2) |
| MC untriggered non-B2 | 54.1% | MV3 v5 REPORT (0.459 B2) |
| S10 current-driven downstream excess @ 20 nA | **+1.03 pts** [0.64, 1.42]; total 20 nA downstream 3.34 pts | S10 REPORT / `result.json` |

Because every B particle entering the stack also crosses the first B trigger paddle,
**R_B ~ R_max ~ 3.05 MHz** is a defensible (lower-bound) estimate of the B-paddle singles rate
at 20 nA. The A-paddle singles rate follows from the MC A:B ratio,
**R_A ~ (0.0365/0.111).R_B ~ 1.0 MHz**.

---

## 1. Accidental (random) coincidences — first principles

A fraction of data A.B coincidences are two **uncorrelated** particles landing in the 15 ns
window by chance. These do not obey pd-elastic kinematics: the recorded B particle is drawn
from the ordinary B-singles population (dominated by deep-stopping protons whose conjugate
deuteron never reached the A-paddle), so **accidentals dilute Sample I toward the deep-stave
profile** — exactly the direction of the residual.

**Random-coincidence rate** (standard form): `R_acc = R_A . R_B . Dt`, with Dt = 2*tau the
full resolving width. The task formula `R_A.R_B.(2.tau_window)` with tau_window = 15 ns gives
**Dt = 30 ns** (central); treating "15 ns" as the full window gives **Dt = 15 ns** (low).

The **true** coincidence rate is `R_true = f_coinc . R_pd`. Since A subset of B (every A-fire
in an elastic pair also fires B) and f_A ~ f_coinc, R_true ~ R_A(from pd), and the ratio
**collapses to a clean, R_pd-independent form:**

```
R_acc / R_true  ~  R_B . Dt        (accidental-to-true ratio ~ B-rate x window)
f_acc           =  (R_B.Dt)/(1 + R_B.Dt)
```

| Dt | f_acc (accidental fraction of Sample I) |
|---|---|
| 30 ns (2*tau, central) | **8.4 %** |
| 15 ns (window-as-full, low) | **4.4 %** |

Both are **upper estimates**, because R_max = 3.05 MHz is itself a one-sided upper bound and
f_acc scales ~linearly with rate.

**Non-B2 carried by accidentals.** The B partner in an accidental is a random B-singles
particle, whose measured proxy is **Sample II** (B-trigger-only = B-singles population,
non-B2 = 30.5%). Contribution to the Sample-I non-B2 fraction = f_acc x phi_rand:

| Dt | phi_rand = Sample II (0.305) | phi_rand = MC untriggered (0.541) |
|---|---|---|
| 30 ns | **2.6 pts** | 4.6 pts |
| 15 ns | **1.3 pts** | 2.4 pts |

**Accidentals contribute ~ 1.3-2.6 points** (central ~ 2.0) of the 6.4, using the empirical
Sample-II partner profile; up to ~4.6 points only if the accidental B partner follows the
harder MC-untriggered profile. **Accidentals alone do NOT close the residual** with the
corrected R_max <= 3.05 MHz. (With the retracted 4.22 MHz the accidental term would be ~40%
larger — another reason the correction matters.)

**Independent DATA cross-check (S10).** The measured current-dependent downstream excess,
2.31% (2 nA) -> 3.34% (20 nA), is a **+1.03-point** [0.64, 1.42] rate-driven deep-stave
contamination — a direct data measurement of exactly the accidental/pile-up mechanism, at the
same ~1-3-point scale as the first-principles estimate. This brackets the accidental term
from data and confirms it is real and modest.

---

## 2. Sample-I selection impurity / paddle fidelity

The ideal MC trigger uses a truth energy deposit (>0.5 MeV) in the paddle *volume* within a
same-vertex event. The data offline Sample-I definition admits events the ideal trigger
rejects:

**(a) Paddle fidelity — deep-proton A-firing above the 0.06% truth.** In MC only 0.06% of
deep-proton events fire the A-paddle (the conjugate 37 MeV deuteron ranges out first). A real
paddle has a finite (ADC/noise) threshold below the 0.5 MeV truth cut, delta-rays,
range-straggling tails, and secondaries — all of which raise the real deep-proton A-firing
probability p_deep. Deep protons are ~44% of B events (84,388 fire the first B paddle vs
33,176 true coincidences), so a small p_deep leaks a **correlated** deep-stave population into
Sample I:

| real p_deep | Sample-I deep-proton fraction | non-B2 pts |
|---|---|---|
| 0.06% (truth) | 0.15% | 0.15 |
| 0.5% | 1.26% | **1.3** |
| 1.0% | 2.48% | **2.5** |
| 1.5% | 3.68% | 3.7 |

A plausible real p_deep of 0.5-1.5% contributes **~1.3-3.7 points** — potentially the
**largest single term**, but **poorly constrained without forced-trigger paddle data or a
digitized paddle model**. Central estimate ~1.5 points.

**(b) Finite paddle efficiency (<100%)** removes some *true* B2 coincidences; second-order,
and it slightly *raises* the non-B2 fraction rather than adding deep events — a sub-0.5-point
effect, same sign.

**(c) Sample-I run-set / beam differences (B-M6).** Data Samples I and II are **disjoint run
sets** with different trigger configs (`docs/00_overview.md`, WIKI section 8). Part of the
93.3% may reflect run-set/beam differences rather than the pure trigger; a systematic **on the
target itself**, unquantified here (owned by B-M6). Plausibly +/-1-2 points, sign unknown.

**(d) Non-conjugate but real A partner** (beam halo, scatter) is a correlated variant of the
accidental term; partly already counted in section 1 via the singles rate, so not added
separately to avoid double-counting.

---

## 3. Residual budget

Total residual = **6.4 points** (Sample-I non-B2 0.3% -> 6.7%).

| Source | Central | Range | Basis / confidence |
|---|---:|---:|---|
| **Accidental coincidences** | **2.0 pts** | 1.3 - 2.6 | First-principles `R_B.Dt`; UPPER-bounded (R_max <= 3.05 MHz); DATA-anchored by S10 (+1.0 pt current excess). **Solid.** |
| **Paddle fidelity** (deep-proton A-firing > truth 0.06%) | **1.5 pts** | 0.5 - 3.7 | Plausible real p_deep 0.5-1.5%; **poorly constrained** — needs paddle threshold/digitizer or forced-trigger data. |
| **Selection / run-set (B-M6)** | 0 | -2 ... +2 | Disjoint Sample-I/II run sets; sign unknown; owned by B-M6. |
| **Still unexplained** | **~2.9 pts** | 0 - 4 | Remainder after central accidental + paddle; collapses toward 0 only at the high end of both. |

**Reading:**
- **Accidentals are real, first-principles, and independently data-anchored, but MODEST** —
  ~2 points, and formally an upper bound because R_max is an upper bound. They account for
  roughly **one-third** of the 6.4-point residual and cannot close it alone.
- **The larger and softer term is data-side paddle/selection fidelity** — chiefly the real
  deep-proton A-firing probability sitting above the idealized 0.06% truth. This is where the
  budget is least constrained (0.5-3.7 points) and where the next measurement should aim.
- **No forced closure.** With central estimates, **~2-3 points remain genuinely unexplained**.
  Closure within error is possible only at the joint high end (accidentals on the untriggered
  profile + p_deep ~ 1.5%), which is not asserted.

**Honest one-line budget:** `6.4 pts ~ 2.0 (accidental, UB) + 1.5 (paddle fidelity, loose)
+ ~2.9 (unexplained) +/- large`, with the accidental term the only well-constrained,
data-anchored piece.

---

## What would tighten this

1. **Digitize the `Trig_bar` SD hits** (Birks + noise + ADC threshold) and re-derive the
   paddle-firing probabilities — turns section 2(a) from a 0.5-3.7-point guess into a number
   (compute only; the SD tree from B-M1 already has the deposits).
2. **B-M6**: separate Sample-I run-set/beam differences from the trigger, removing the +/-2-pt
   selection systematic.
3. **Forced-trigger / random-trigger data** in the next beam run measures the accidental
   fraction directly (validates the R_B.Dt estimate) and the real paddle threshold.
4. A direct **accidental-subtraction** on data (delayed-window A.B coincidences) would give a
   data-measured f_acc to replace the rate estimate — no new beam time if a delayed trigger
   tag exists.

---

## Provenance

Reproduce: `python3 new04_residual_budget.py` (writes `new04_summary.json`). All inputs cited
inline above; no data staging or GEANT4 production touched. Prepared for STUDY_GAPS NEW-04 /
IMPROVEMENT_BACKLOG B-M1 follow-up. Not git-committed (main session owns commits).
