# CCB Test-Beam — Synthesis of findings (what we understand about the pulse)

**A distilled, physics-organized synthesis of the autonomous study program.** As of 2026-06-10 the
fleet has completed **~230 studies**; this document pulls their conclusions into one narrative so you
don't have to read 230 reports. Per-study detail is in `reports/<id>/REPORT.md`; the full row-by-row
scoreboard is `reports/SUMMARY.md`. Everything is data-driven (no Monte-Carlo truth); every claim is
reproduce-first, traditional-vs-ML head-to-head, split by run, with bootstrap CIs and leakage controls.

> **Reading the verdicts:** "ML wins" means it beat a *strong* conventional baseline on held-out runs
> with non-overlapping CIs AND survived leakage sentinels. Many tentative ML wins were **rejected**
> after run-family / event-block shuffle controls — those rejections are findings, not failures.

---

## The one-paragraph answer
The CCB B-stack pulse is **low-dimensional in shape** and **well-described by analytic models** for
timing and pile-up rate, so **ML helps most where the signal lives in waveform *shape* and the truth
is independent of the inputs** — saturation recovery, duplicate-readout amplitude/charge closure, and
two-pulse time resolution. It **ties or loses** where an analytic physics model is already optimal
(timewalk correction, Poisson pile-up rate) or where an apparent win rests on a label that is a
disguised function of the input (D_t / curvature classifiers). The single most consequential *physics*
result is that the report's pile-up headline rests on an **assumed** 90 ns dead-time; the measured
waveform live-time implies a substantially **lower R_max (~3 MHz, not ~4.2 MHz)**.

---

## 1. Timing  (S02, S03, S04, S05, S18, P01, P03)
- **Pickoff:** ridge-corrected CFD20 gives single-stave σ68 ≈ **1.85 ns**, beating a template-phase
  fit (2.89 ns) — ML wins here (S02). But once a proper **analytic amplitude timewalk** is applied,
  the conventional method reaches ≈ **1.50 ns** and is very hard to beat.
- **Timewalk:** the analytic amp-only timewalk (≈1.495 ns) is the champion. ML residual correctors
  (ridge/HGB) shave it only to ≈1.39–1.45 ns, and that gain is **control-sensitive** and often
  vanishes under leave-one-run-out + shuffle controls (S03a–d). **Waveform MLP/CNN timing loses to
  the analytic baseline** (P03a–c) — deep nets add nothing for timing here.
- **Per-sample anatomy:** samples ~3–6 carry the timing information; apparent sample-5 sign-flips are
  **CFD artifacts**, not physics (P01c, P01d, P01e).
- **Error structure:** the inter-stave timing covariance is **B2- / topology-dominated**; the naive
  σ²=σ_i²+σ_j² independence is imperfect (S05c, S18g).
- **A-stack cross-check (S18):** A1–A3 robust width **1.39 ns** reproduces the note (1.43 ns).
  Sample-IV broadening is **calibration-pool / low-statistics sensitivity**, not a physics effect.

## 2. Pile-up  (S10, S11, S13)  ← the headline physics revision
- **R_max is lower than the note claims.** The note's R_max ≈ 4.2 MHz assumes τ_eff = 90 ns. Direct
  measurement of the waveform live-time window finds **all thresholds imply > 90 ns**, i.e. the true
  dead-time is longer and **R_max ≈ 3.05 MHz** (S10b, S10c, "S10c threshold"). This is the most
  important data-driven correction to the original analysis.
- **Two-pulse recovery:** ML (compact MLP/CNN) resolves **shorter separations (~20 ns vs 60 ns)** and
  lower time-RMS (≈9–10 ns vs 13–18 ns) than a constrained two-pulse template fit — *but at a markedly
  **higher failure rate*** (≈0.25–0.32 vs ≈0.17). The failure-rate regression gates adoption; the
  conventional fit is **safer at the accepted-recovery operating point** (S10d, S11a–e, P05a–b).
- **Current-dependent excess** is real (CIs exclude zero) but **heterogeneous**: after matching on
  amplitude/baseline/topology it concentrates in **high-amplitude / large-baseline-lowering /
  broad-late** pulses (S10c–f, S11b–d). Topology stays the physics-facing rate handle; ML/CWoLa is
  **monitoring/diagnostic only** (S13b–c).

## 3. Pulse shape & learned representation  (P01, P02, P09)
- **Compression:** an autoencoder beats PCA by **40–51 % at low latent dim (≤4)**; PCA wins by dim 8
  (P02). So a *compact* nonlinear embedding is the best small representation.
- **Honest null on downstream value:** for actual downstream tasks, the learned latent does **not**
  robustly beat hand-crafted / PCA shape features once **run-family and event-block shuffle sentinels**
  are applied — repeated leakage controls **reject** the representation-superiority claim (P01a–f).
  This is the program's clearest example of disciplined falsification.
- **Unsupervised types:** a ~4 % **early-peak / near-zero-area anomalous class** was discovered with
  no labels (P02); learned clustering only beats cuts for specific morphologies (P02b–e).
- **Anomaly detection:** ML is better for *novel* taxa and delayed-peak isolation; conventional cuts
  give slightly better curated precision (P09a, P09c).

## 4. Amplitude, charge & energy  (P04, S14, P07, P10)
- **Amplitude/charge (duplicate-readout closure):** ML (HGB / ExtraTrees) is a **decisive win** —
  res68 ≈ **0.003–0.009** vs **0.12–0.20** for peak/integral (P04, P04c–e). The traditional direct
  template-scale has a pathology that needs diagnosis.
- **But absolute energy is not reachable** to the 10 % target from data alone: propagated per-event
  energy res68 ≈ 0.19–0.25 fails the threshold (S14b–c). Honest limitation — there is no MC truth.
- **Saturation recovery (P07):** ML recovers true amplitude to **~3–4 %** vs template **10–29 %** on
  artificial clips (3–7× win). Natural-saturation transfer carries a **run-dependent timing-tail
  envelope** and needs boundary/systematic audits before production (P07b–e).
- **Conditional templates (P10):** an explicit analytic timewalk **beats** a learned conditional
  template on the primary q-template metric; ML only helps a secondary timing metric (P10a–b).

## 5. Pedestal / baseline  (S16)
- The adaptive pedestal is **badly biased** (MAE 341 ADC); a learned pedestal cuts MAE to **≈49 ADC**
  — ML win (S16). **Caveat:** there is **no true forced/random pedestal sample** in the data
  (S16b–f), so this is proxy-validated only, and high-baseline-lowering events are
  **contamination/pathology**, not pedestal truth.

## 6. Cross-cutting methodology (why to trust the above)
- **Leakage is hunted, not assumed away.** D_t / curvature classifiers hit AUC≈1.0 because the label
  is a disguised function of the input — the fleet flags these as **self-referential**, not wins
  (S07b, S07e, S07g, P02d). On injected-corruption truth (label independent of input), shape-only ML
  legitimately wins (S07f, S07h) — but that is *not* a measured beam pile-up rate.
- **The pattern:** ML wins when truth is independent and the signal is in shape (saturation,
  duplicate-amplitude, two-pulse RMS); ML ties/loses when an analytic model is already optimal
  (timewalk, Poisson rate) or when the apparent win is leakage.

---

## Open questions / what's missing (no data-driven answer yet)
- **Absolute energy & particle ID (p vs d):** needs GEANT4 (S17) — no per-event truth exists in data.
- **A true forced/random pedestal sample:** absent; all pedestal validation is proxy-based.
- **Real (not injected) pile-up truth:** the two-pulse and current-excess studies use injected or
  matched-control truth; a real-pile-up label remains unavailable.
- **Failure-rate transfer:** ML two-pulse recovery must be shown to keep its accuracy *and* control
  its failure rate on real high-current data before any production use.

_This synthesis is regenerated as the program advances; see `reports/SUMMARY.md` for the live,
per-study scoreboard and `PROJECT_REPORT.md` for project/infra status._
