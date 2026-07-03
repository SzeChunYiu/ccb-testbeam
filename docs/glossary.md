# Glossary

- **CCB** — Centrum Cyklotronowe Bronowice (Cyclotron Centre Bronowice), Kraków; the facility.
- **CD₂** — deuterated polyethylene target.
- **HRD Stack A / B** — two **independent** scintillator range stacks at **conjugate angles**,
  each ~100 cm from the target and each behind its own trigger scintillators (TPC in front of A);
  the arms measure **different particles** of kinematically-correlated pairs (pd-elastic: proton
  in one arm, deuteron in the other). "bstack"/"astack" = Stack B / A. (Experiment-owner setup
  facts, 2026-07-03.)
- **Stave (B2/B4/B6/B8, A1/A3)** — individual scintillator slab; deeper index = deeper in stack.
- **Sample I / II** — B-stack run groups defined by trigger configuration (2026-07-03):
  I (runs 31–57, **A·B trigger coincidence**; terminal-B2-like; D-enrichment = hypothesis, S21);
  II (runs 58–65, **B trigger only**, A ignored; p-enriched, penetrating, clean timing reference).
  In data these are **disjoint run sets**; in the MC mimic Sample I (first-A/first-B entry within
  15 ns) is a **subset** of Sample II.
- **Sample III / IV** — A-stack data from the Sample I / II run periods (the A arm records
  different particles than B).
- **Calibration run / analysis run** — runs used to build templates & timewalk vs runs used for
  results.
- **A** — baseline-subtracted peak amplitude (ADC); selection cut **A > 1000 ADC**.
- **Adaptive pedestal** — positivity-constrained baseline (tolerance ε(A)=max(25, 0.015A))
  replacing the fixed first-four-sample median.
- **Jagged sample** — pathological sample dipping to ~0/negative between high neighbours;
  masked, not rejected.
- **Amplitude-adaptive template** s_i(j;A) — per-stave, per-amplitude-bin reference pulse shape,
  interpolated in log₁₀A.
- **CFD20** — software constant-fraction time at 20% of peak (timing seed).
- **Optimal filter (OF)** — linearised template + derivative least-squares fit giving sub-sample
  time.
- **t_v3_raw_of_ns / t_v3_ns** — raw OF time / fully corrected precision time (table columns).
- **Timewalk** — amplitude/shape-dependent timing bias of the *same* physical pulse; f_i(A,x).
- **B2-blind** — excluding B2 from the timewalk correction (δ_B2 = 0); reference {B4,B6,B8}.
- **Δt_B** — event timing span max−min of corrected B times ("similar/intermediate/different").
- **D_t** — downstream-only timing span (App. I pile-up labels: <3 ns clean, >50 ns gross).
- **R_t** — internal consistency pull of the combined event time (≈1 compatible, large = bad).
- **C_t** — three-stave timing curvature t_B8 − 2t_B6 + t_B4.
- **σ_comb** — inverse-variance-weighted combined event-time resolution.
- **Robust width (sigma68)** — outlier-resistant 68% half-width of a residual distribution.
- **Narrow-core σ** — Gaussian-fit sigma over −5<Δt<5 ns only (excludes tails).
- **q_template / q_desc / q_ideal** — template-agreement / v4-description / ideal-pulse quality
  variables. (q_ideal is a shape diagnostic, **not** a timing-quality cut.)
- **v3 / v4** — precision-timing definition (leading-edge, B8 full-pulse branch off) /
  full-waveform 13-parameter description model.
- **WLS** — wavelength-shifting fibre readout (one-ended, v_WLS = 17 cm/ns).
- **Penetration depth** — deepest stave hit above threshold ("stops in B2", "deepest B4/B6/B8").
- **Terminal / late-overlap / pile-up topology** — event with a later overlapping component;
  the Sample I B2 class with tens-of-ns residuals.
- **τ_eff** — effective pile-up integration/live time (nominal 90 ns) in the occupancy model.
- **CWoLa** — Classification Without Labels; weak supervision from mixed samples (20 nA vs 2 nA).
- **usable_for_precision_timing** — boolean flag selecting clean multi-stave timing candidates.
