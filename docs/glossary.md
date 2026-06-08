# Glossary

- **CCB** — Centrum Cyklotronowe Bronowice (Cyclotron Centre Bronowice), Kraków; the facility.
- **CD₂** — deuterated polyethylene target.
- **HRD Stack A / B** — the two scintillator range stacks. "bstack"/"astack" = Stack B / A.
- **Stave (B2/B4/B6/B8, A1/A3)** — individual scintillator slab; deeper index = deeper in stack.
- **Sample I / II** — B-stack run groups: I (runs 31–57, D-enriched, terminal-B2-like);
  II (runs 58–65, p-enriched, penetrating, clean timing reference).
- **Sample III / IV** — A-stack analogues of Sample I / II.
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
