# WIKI Chapter 4 (Timing Analysis) — Data-Science Audit

Auditor pass 2026-07-05. Scope: WIKI.md §4.1–4.8 (lines ~222–364). Every quantitative
claim traced to a repo artifact and its exact value confirmed. VERIFY-not-trust.
`[BACKED]` exact source+value match · `[BACKED-note]` matches an external-analysis-note
doc (docs/*.md), not a reports/ study artifact · `[MISMATCH]` source exists but value/label
differs · `[UNBACKED]` no artifact found · `[STALE]` withdrawn/superseded (self-flagged OK).

Key artifacts:
- `reports/s25_covariance_timing_1783241582/s25_summary.json` (S25 combined 0.490)
- `reports/mv4_timing_1783077795/mv4_summary.json` (MV4)
- `reports/s22_timing_vs_amplitude_1783108999/s22_summary.json` (S22)
- `reports/1780997954.15157.07ef03cf__s02_timing_pickoff/head_to_head_benchmark.csv` (S02)
- `reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction/head_to_head_benchmark.csv` (S03a)
- `reports/1781048240.758.327a70d2__s03k_analytic_comparator_reuse_gate/REPORT.md` (HGB 1.107)
- `reports/1780997954.15397.168324f2__s18_astack_independent_reproduction/head_to_head_benchmark.csv` (S18)
- `docs/05_timing_resolution.md` (external-note Table 19 per-stave), `docs/ANALYSIS_REPORT.md` (LORO)

---

## Per-claim ledger  `[status] line — claim — source-or-gap — fix`

### Key Findings block (224–231)
- `[BACKED-note]` 225 — B6 σ(core) ≈ 0.68–0.75 ns (Gaussian-core, not σ68, under review) — `docs/05_timing_resolution.md` Table 19 downstream B6 = 0.675 (SI) / 0.754 (SII); correctly labeled Gaussian-core & "under review". — keep.
- `[BACKED]` 226 — combined σ68 = 0.490 [0.470, 0.508] (S25) — s25_summary `combined_sigma_ns`=0.49002, `combined_sigma_ci`=[0.46964, 0.50819]. — keep.
- `[BACKED]`/`[UNBACKED]` 227 — analytic 1.49–1.55; ML 1.39–1.47 — analytic: S03a held-out 1.4946 + LORO 1.551 (ANALYSIS_REPORT §4.3) → 1.49–1.55 exact. ML: lower 1.39 = S03a 1.3915; **upper 1.47 has no source** (S03a ML held-out 1.392, LORO ridge 1.537). — change ML range to **1.39–1.54** (S03a→LORO), or cite the 1.47 source.
- `[STALE-ok]` 228 — B2 large covariance — qualitative only; quantitative 1042/16 withdrawn (see §4.5). — keep.
- `[BACKED]` 229 — A1–A3 width 1.39 ns matches note 1.43 — S18 head_to_head sample_iii robust_width 1.38906; reproduction table note 1.43. — keep.
- `[BACKED]` 230 — MC pair-equiv σ68 2.087 ± 0.009, between raw 2.993 & corrected 1.50 — mv4_summary `mc_pair_equivalent_ns.raw`=2.0868 ± 0.00935. — keep.
- `[BACKED]`/`[MISMATCH]` 231 — S22 1/A>1/√A; per-stave 0.85–1.1 ns; B2 saturation-excluded — per_stave_sqrt2_highest_bin range 0.87–1.12 (min 0.875 SII B6-B8, max 1.122 SII B4-B8); "0.85–1.1" undershoots the 1.12 max. B2 "30–40%" is imprecise (see §4.8). — widen to **0.87–1.12 ns**.

### §4.1 (233–239)
- `[OK-method]` 237 — σ_single = σ(Δt)/√2, approximate for σ68 — no number; caveat honest. — keep.

### §4.2 Timing-chain table (247–258)
- `[MISMATCH-flagged]` 249 — "CFD20 at 20% of peak → σ68 1.85" — value 1.85 = **ml_ridge** (S02 head_to_head `ml_ridge`=1.8461), NOT raw CFD20 (which is 2.993, row `cfd20_reference`). The wiki's own ⚠ note (258) flags exactly this. — relabel row "CFD20 + ML-ridge correction" to remove the residual contradiction.
- `[BACKED]` 250 — Template phase fit 2.89 — S02 `traditional_best_template_phase`=2.8892. — keep.
- `[BACKED]` 251 — Amplitude-only analytic 1.49–1.55 — S03a 1.4946 + LORO 1.551. — keep.
- `[UNBACKED-upper]` 252 — Ridge residual corrector 1.39–1.47 — lower 1.39=S03a 1.3915; **upper 1.47 unbacked** (LORO ridge=1.537). — change to 1.39–1.54.
- `[BACKED]` 253 — HGB on waveform+shape (S03k, gated) 1.11 (in-fold only) — S03k REPORT `hgb_waveform_amp_shape_stave`=1.1074 [1.075,1.159]. — keep.
- `[BACKED]` 254 — Combined S25 0.490 [0.470, 0.508] — as 226. — keep.
- `[BACKED]` 256 — HGB σ68 = 1.107 ns gated — S03k 1.1074. — keep.
- `[BACKED]` 258 — raw CFD20 pair σ68 = 2.993 (head_to_head_benchmark.csv row cfd20_reference) — exact 2.99339. — keep.

### §4.3 (260–272)
- `[OK-method]` 270 — f(A)=A0+B/amplitude, B2-blind — coefficients in S03a `analytic_coefficients.csv` (inv_amp_1000 = −4.999, etc.). — keep.

### §4.4 Per-stave table (280–286)
- `[UNBACKED]` 282 — B2 ~2.8 ns — **no artifact gives a B2 single-stave ~2.8.** Note Table 19 gives B2 = 1.107 (SII all-pair) / 1.479 (SI all-pair); B2 *pair* widths are 37–41 ns (docs/05). 2.8 matches nothing. — replace with the note's B2 value (1.1–1.5, all-pair) or a measured B2 pair σ68, and state which.
- `[BACKED-note]`/`[STALE]` 283 — B4 ~1.45 (labeled σ68) — docs/05 Table 19 downstream B4 = 1.470 (SI); but it is **Gaussian-core σ, not σ68**, and is now superseded by measured S25 σ68 B4 = **1.521**. — mark Gaussian-core; note S25 supersedes (1.52).
- `[BACKED-note]` 284 — B6 ~0.72 (Gaussian-core, flagged) — Table 19 downstream 0.675/0.754; S25 σ68 = 0.679. Wiki flags it. — keep; can now cite S25 0.68.
- `[BACKED-note]`/`[STALE]` 285 — B8 ~0.93 (labeled σ68) — Table 19 downstream 0.933/0.942 (Gaussian-core); S25 σ68 = **0.799** (better). — mark Gaussian-core; S25 supersedes (0.80).
- `[BACKED]` 286 — B4+B6+B8 = 0.490 [0.470, 0.508] — S25. — keep.
- **Column-header defect:** header says "σ68 (ns)" but B2/B4/B6/B8 rows are the note's narrow-core Gaussian σ (per docs/05 method §3), NOT σ68. The combined row IS σ68 (S25). Mixed metric in one column.

### §4.5 B2 covariance (288–304)
- `[STALE-ok]` 293–294 — B2-X ≈ 1042 ns²; downstream ≈ 16 ns² — **withdrawn** (line 296, closure script numerically invalid); no artifact holds these. Self-flagged correctly. — keep as struck.
- `[BACKED]` 300 — n = 3,820 events, 7 runs, 400 replicas — s25_summary n_triples=3820, exploration_runs=7, n_bootstrap=400. — keep.
- `[BACKED]` 300 — per-stave B4 1.52 / B6 0.68 / B8 0.80 — s25 per_stave_sigma_ns 1.5210 / 0.6793 / 0.7993. — keep.
- `[BACKED]` 300 — independence p = 0.62 — s25 `offdiag_equality_bootstrap_p`=0.615. — keep.
- `[BACKED]` 300 — held-out BLOCKED (reserved runs unstaged) — s25 held_out.status=BLOCKED_DATA_UNAVAILABLE; reserved_runs_present=[]. — keep.
- `[BACKED]` 302–304 — Fig 35: A>1000, n=3820 — s25 primary. — keep.

### §4.6 A-stack (306–320)
- `[BACKED]` 318 — Sample III robust width 1.39 ns reproduces note 1.43 — S18 sample_iii 1.38906; note 1.43. — keep.
- `[BACKED]` 319 — Sample IV 1.79 ns = low-stats broadening — S18 sample_iv 1.79363, n_pairs=127 (vs 2514 for III); CI [1.379, 2.220] overlaps 1.39 → statistically a low-stats effect. — keep.
- `[MISMATCH]` 320 — "ML makes timing worse (1.94 ns) — ML not adopted" — **S18 primary benchmark shows ML ties/improves, not worsens:** ml_ridge robust width = 1.383 (III, vs trad 1.389) and **1.559 (IV, better than trad 1.794)**. No ML robust width equals 1.94; 1.94 matches a **full-RMS/CI** figure (e.g. sample_iv trad full_rms_ci_high 1.948, or S18h full_rms). ML-not-adopted is correct (paired CI [−0.054, 0.026], p=0.524 → tie, not a loss). — replace "makes worse (1.94)" with "ties (III 1.383 vs 1.389; IV 1.559 vs 1.794; paired p=0.524) → not adopted."

### §4.7 MV4 (322–340)
- `[BACKED]` 329 — timewalk B = +39.6 ns·ADC (1/A form) — mv4 `timewalk_fit.B_ns_ADC`=39.6025. — keep.
- `[BACKED]` 333 — raw: 1.476±0.007 | 2.087±0.009 | 2.993 | 0.697±0.003 — mv4 sigma68.raw 1.4756±0.0066; mc_pair_equiv.raw 2.0868±0.0093; data 2.993; ratio.raw 0.6972±0.0031. — keep.
- `[BACKED]` 334 — corrected: 1.481±0.009 | 2.094±0.012 | 1.50 | 1.396±0.008 — mv4 corrected_test_half 1.4805±0.0086; mc_pair_equiv.corr 2.0938±0.0121; data 1.50; ratio.corr 1.3958±0.0081. — keep.
- `[BACKED]` 340 — MC timewalk no improvement (1.00×) — mv4 improvement_factor 0.9967. — keep.
- `[OK]` 322/340 — gain 92 ADC/MeV retracted, scale-only — mv4 gain_retraction_note present. — keep.

### §4.8 S22 (342–364)
- `[BACKED]` 351 — 1/A form σ(A)=√(c²+k²(1000/A)²) — s22 scaling_fits model `inv_A`. — keep.
- `[BACKED]` 351 — B4-B6 χ²/ndf 0.32–0.87 (1/A) vs 1.25–3.71 (1/√A) — s22 raw B4-B6: SI inv_A 0.322 / inv_sqrtA 1.249; SII inv_A 0.869 / inv_sqrtA 3.714. Exact. — keep.
- `[BACKED]` 352 — tie where floor dominates (B6-B8) — s22 raw B6-B8 SI inv_A 0.0643 = inv_sqrtA 0.0644. — keep.
- `[MISMATCH-approx]` 353 — per-stave ≈ 0.85–1.1 ns high amp — actual per_stave_sqrt2_highest_bin 0.875–1.122. — state 0.87–1.12.
- `[MISMATCH]` 355 — "30–40% of B2 above ~7000 ADC" — s22 b2_saturation frac_b2_ge7000 = **0.417 (Sample I)**, **0.061 (Sample II)**. SI is 41.7% (above the stated 40%); SII is 6%, far below. — state "≈42% (Sample I) / 6% (Sample II)".
- `[OK-method]` 358–360 — two-stage timewalk (downstream first, B2 frozen), LORO, √2 caveat — s22 timewalk.fit / evaluation / per_stave_assumption fields. — keep.

---

## (a) Unbacked / mismatched / stale numbers — prioritized

1. **§4.4 B2 ~2.8 ns — UNBACKED.** No study or note artifact yields a B2 single-stave ~2.8 ns. Note Table 19 gives B2 = 1.1–1.5 (all-pair); B2 pair widths are 37–41 ns. The 2.8 is invented/mis-transcribed. **Highest priority.**
2. **§4.6 "ML makes A-stack timing worse (1.94 ns)" — MISMATCH.** S18 primary shows ML ties/improves (IV 1.559 < trad 1.794; III 1.383 ≈ 1.389; paired p=0.524). 1.94 is a full-RMS/CI number, not a robust width, and contradicts the adopted "tie" conclusion.
3. **§4.4 column labels the note's Gaussian-core σ as "σ68".** B4 1.45 / B6 0.72 / B8 0.93 are narrow-core Gaussian σ (docs/05 §3), not σ68; and now conflict with S25 measured σ68 (B4 1.52, B6 0.68, B8 0.80). Mixed metric + superseded (STALE for B4/B8).
4. **§4.2 & KF: Ridge "1.39–1.47" upper bound UNBACKED.** Artifacts give 1.39 (S03a held-out) and 1.54 (LORO). 1.47 has no source — likely should be 1.54.
5. **§4.8 & KF: B2 saturation "30–40%" MISMATCH.** True values 41.7% (SI) / 6.1% (SII).
6. **§4.2 CFD20 row 1.85 = ML-ridge, not raw CFD20 (2.993).** Self-flagged by the ⚠ note but the table row still reads "CFD20 at 20% of peak," an internal contradiction.
7. **§4.4/KF per-stave 0.85–1.1 → should be 0.87–1.12** (minor).
8. `[STALE-ok]` §4.5 1042/16 ns² — already struck; no action beyond keeping strike.

## (b) Outliers + root cause

1. **B4 σ68 = 1.52 ns ≫ B6 0.68 / B8 0.80 (S25).** *Root cause found via LUNARC check (my rerun on runs 58–63,65, A>1000 triples, n=3858 ≈ S25's 3820):* median amplitude B4=2314, B6=2408, B8=3260 ADC. **B4 and B6 have essentially equal amplitude, yet B4 is 2.2× worse — so B4's poor timing is NOT an amplitude/timewalk effect** (B8, the highest-amplitude stave, is also worse than B6). B4's excess variance (2.31 ns² vs 0.46 / 0.64) is therefore *intrinsic*: B4 is the most upstream downstream stave (nearest B2/beam) → most exposed to topology contamination / secondary hits / wider pulse-shape variation. Lead to confirm: per-stave residual-tail fraction and pulse-shape (rise-time) spread for B4 vs B6 at matched amplitude.
2. **A-stack Sample IV 1.79 vs III 1.39.** Root cause = low statistics: n=127 pairs (IV) vs 2514 (III); S18 CI [1.379, 2.220] overlaps 1.39. Not physics. BACKED.
3. **MC/data ratio 0.697 (raw) → 1.396 (corrected).** Root cause: the *data* anchor collapses 2.993→1.50 (≈2× from the timewalk correction) while *MC* is flat 2.087→2.094 (improvement 1.00×). MV4's rising-edge CFD already removed the low-amplitude noise-crossing bias that the data correction fixes, so the MC has nothing left to gain → the ratio nearly doubles. BACKED (improvement_factor 0.997).
4. **Extreme inter-stave correlation ρ≈0.99 in S25 raw cov matrix.** Expected: the raw stave-time covariance is dominated by the shared event T0 (~16 ns common mode); only the pair *differences* (variances 1.10–2.95 ns²) carry resolution. Not an anomaly; it is why the combined number is a *relative* resolution / floor.

## (c) Top visualization additions (with exact data source)

1. **Per-stave σ68-vs-amplitude curves with 95% CI and the 1/A overlay, all downstream pairs.** Fig 31 exists but shows pair σ68; add the √2-converted *per-stave* curves. Source: `reports/s22_timing_vs_amplitude_1783108999/s22_curves.csv` + `s22_triangle_decomposition.csv`, fits in `s22_summary.json:scaling_fits`.
2. **B4-outlier diagnostic panel: B4 vs B6 residual distribution at matched amplitude (2000–2600 ADC), plus rise-time/tail-fraction overlay.** Directly visualizes "same amplitude, 2× worse." Source: raw ROOT `data/root/root/hrdb_run_005[89],006[0-3],0065.root` (channels B4=2,B6=4,B8=6; recompute as in this audit's LUNARC check) + `s25_summary.json` per_stave_sigma.
3. **The three residual histograms behind each S25 per-stave σ68**, with the 68% band drawn — makes the σ68 definition and the B4 tail visible. Source: reconstruct from raw ROOT triples (same selection as `s25_summary.json`); estimators in `src/ccb_mc_validation/statistics/estimators.py`.
4. **MC/data ratio waterfall (raw vs corrected) showing why 0.697→1.396.** Two bars each for MC and data at raw & corrected, annotated with the flat MC improvement. Source: `mv4_summary.json` (sigma68, mc_pair_equivalent_ns, data_reference).
5. **B2 saturation histogram (ADC, 0–8000) per sample with the 7000 ceiling line and the true 41.7% / 6.1% fractions.** Replaces the prose "30–40%". Source: `s22_summary.json:b2_saturation` + `s22_b2_saturation.csv`.

---

## Summary counts (of ~40 checked quantitative claims)
- BACKED / BACKED-note (exact or note-exact): 27
- MISMATCH (source exists, value/label off): 5  (CFD20-1.85 label, A-stack ML-1.94, B2-saturation 30–40%, per-stave 0.85–1.1, §4.4 σ68-vs-core label)
- UNBACKED (no source): 2  (B2 ~2.8; Ridge upper 1.47)
- STALE (withdrawn/superseded, self-flagged): 3  (1042/16 ns²; §4.4 B4 1.45 & B8 0.93 vs S25)
