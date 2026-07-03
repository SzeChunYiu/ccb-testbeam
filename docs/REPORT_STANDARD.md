# REPORT_STANDARD.md — Scientific reporting standard for the CCB test-beam program

**Purpose.** This document defines how every study report in this project must be written so that
the body of work is *reproducible, falsifiable, and publication-grade*. It is written for future
AI (and human) sessions. If you are about to write or update a `reports/<id>/REPORT.md`, read this
file first and follow it exactly. A report that does not meet this standard is not "done" — it is a
draft.

- **Status:** authoritative standard (v1.0, 2026-06-28)
- **Authors:** CCB analysis fleet
- **Scope:** all `reports/<id>/REPORT.md`, the rolling `reports/SUMMARY.md`, `FINDINGS_SYNTHESIS.md`,
  and any MC-validation write-up under `docs/mc_validation/`.
- **Companion docs:** `docs/ANALYSIS_GUIDE.md` (how to navigate and reproduce), `FINDINGS_SYNTHESIS.md`
  (the distilled science), `PROJECT_REPORT.md` (status/infra).

---

## 0. The five non-negotiable rules

These predate this document and override convenience. Every report must visibly honor all five.

1. **Reproduce first.** Before extending anything, reproduce the upstream number from raw ROOT.
   `S00` (the 640,737-pulse gate) is the entry condition for every downstream claim. If your study
   does not start from a reproduced anchor, it is not admissible.
2. **Traditional AND ML, fair head-to-head.** Every study runs a *strong* conventional method and
   an ML method on the *same* held-out data with the *same* metric. No strawman baselines. The
   conventional method is the incumbent; ML must *beat it with a margin whose CI excludes zero* to
   win.
3. **Atomic decomposition.** No black boxes. Every step from raw waveform to final number must be
   traceable. If you cannot explain a number, you cannot report it.
4. **Hunt leakage, do not assume it away.** Most premature ML "wins" in this project were leakage
   (the label was a disguised function of the input). Every ML claim must survive the three leakage
   controls in section 4. A claim that fails any control is **CORRECTED**, which is a *first-class
   positive result*, not a failure.
5. **Never report a number without its uncertainty and its baseline comparison.** A bare number is
   not a result. `1.39 ns` is meaningless; `1.394 ns, CI [1.242, 1.682] (pooled LORO, vs s03a
   amp-only 1.551 ns, CI [1.369, 1.925])` is a result (real values from the S03d record,
   `reports/1781010985.923.35c141ac/result.json`).

---

## 1. Required structure of every REPORT.md (in this order)

Every `reports/<id>/REPORT.md` MUST contain the following sections, in this exact order. Sections
may not be omitted; if a section does not apply, state explicitly *why* (e.g. "No MC validation
exists for this observable yet — see section 9").

### 1. Header block
```
# <STUDY_ID> — <Title>
- Study ID:      <id>           (e.g. S03d, P07, MV1)
- Title:         <one line>
- Date:          YYYY-MM-DD
- Status:        DRAFT | DONE | CORRECTED | BLOCKED
- Authors:       CCB analysis fleet
- Dependencies:  <upstream study IDs whose anchors this study reuses>
- Data anchor:   <count reproduced, e.g. 640,737 selected B-pulses>
```

### 2. One-sentence verdict (bold, immediately after the header)
A single bold sentence using exactly one of these verdict templates:
- **"ML wins: <metric> <ml_value> vs <trad_value> (Delta=<delta>, CI <ci>), survives all leakage controls."**
- **"ML ties: CIs overlap (<ml_value> vs <trad_value>); the transparent traditional method is the production candidate."**
- **"ML loses: traditional <trad_value> beats ML <ml_value>; <one-line reason>."**
- **"CORRECTED: the apparent ML win is leakage (<which control failed>); not a physics result."**
- **"Not yet validated against MC: <observable> requires <MV_ID> to close."**

### 3. Reproduction gate
The exact command, the exact expected count, and the exact seed. Example:
```
Command:  python scripts/01_build_pulse_table_from_root.py --config configs/s00_reproduction.yaml
Expected: 640,737 selected B-stave pulses (A > 1000 ADC, even physical staves {0,2,4,6},
          baseline = median of samples 0-3)
Seed:     numpy/sklearn random_state = 20260601 (fixed across all folds)
Check:    Sample I analysis B2 = 241,422; Sample II B4/B6/B8 = 21,229 / 11,148 / 4,506
```
If the reproduced count differs from expected, the study is **BLOCKED** until reconciled — do not
proceed on a drifted anchor (this is how `S00b`/`S00c` distinguished the median selector,
640,737, from the dynamic selector, 706,373).

### 4. Key metrics table
All numerical results in a table (never only in prose), with units, 68% CI, and comparison to the
traditional baseline and to any prior study reporting the same observable. See section 2 for precision.

### 5. Physics motivation (2-3 sentences)
WHY this question matters for the experiment. Tie it to the two physics goals (timing resolution,
pile-up) or to a truth-limited gap (energy, PID).

### 6. Methodology (full and rigorous)
- **Data selection:** exact filter, N rows after filter, `(N_expected, N_actual, delta)`.
- **Feature set:** every feature, its definition, its units. (e.g. `amp = max(baseline-subtracted
  ADC)`; `cfd20 = 20%-fraction constant-fraction crossing time in ns`.)
- **ML method:** algorithm, hyperparameters, and cross-validation scheme. The default CV here is
  **LORO (leave-one-run-out)**; state which runs were folds. If you scan a hyperparameter (e.g.
  ridge alpha), report the grid and the selection criterion.
- **Traditional baseline:** the full analytic definition, not a sketch. This is the incumbent and
  must be the *strongest* available form (e.g. analytic amplitude timewalk, not raw CFD).
- **Leakage controls:** which of the three (section 4) were applied and what each returned.

### 7. Results
- Every metric in a table with its CI (bootstrap, 300–1000 resamples as configured per study, or LORO SEM — state which).
- A **comparison panel**: ML vs traditional vs prior studies, same metric, same units.
- The sign and magnitude of `Delta = ML - traditional` with its CI.

### 8. Interpretation (physics first)
- What does this mean for the experiment?
- What does it explicitly NOT answer?
- Does it agree with MC truth (if MC is available)? Quote the MC number.

### 9. MC verdict (explicit, every study)
One of:
- `MC validation available: <MV_ID>. MC result <x> vs data result <y>; agreement within <z>%.`
- `MC validation not yet run — required to close this open question. Proposed: <MV_ID> (<one line>).`
- `MC not applicable: this observable (<name>) has no MC truth analogue because <reason>.`

### 10. Open questions
A numbered list. Each item is a *concrete study proposal*: an ID, a one-line hypothesis, and the
falsifying test that would settle it.

### 11. Provenance
```
Git commit:        <40-char hash>
Data SHA256:       <sha of the input table / ROOT files>
Python:            <e.g. 3.11.x>
scikit-learn:      <e.g. 1.4.x>
numpy / scipy:     <versions>
Run host / job:    <e.g. LUNARC cn039, SLURM job 3310358>
Artifacts:         reports/<id>/{REPORT.md, manifest.json, figures/*.png}
```

---

## 2. Numerical precision requirements

Report numbers to the precision that the measurement supports, and *never* drop the uncertainty.

| Observable | Precision | Uncertainty | Notes |
|---|---|---|---|
| Timing sigma68 | 0.001 ns | CI to 0.010 ns | always pair with the analytic baseline on the same fold |
| AUC | 4 decimals | bootstrap CI | e.g. `0.9860` not `0.99` |
| Efficiency / purity | 4 decimals | + `[N_true, N_total]` | e.g. `0.9644 [144,889 / 150,130]` |
| Energy resolution res68 | 4 decimals | bootstrap CI | `res68 = [P90 - P10] / 2 / median` of the residual |
| MAE / RMS (ADC or ns) | 2 decimals | CI | state units explicitly |
| Counts | exact integer | `(N_expected, N_actual, delta)` | delta must be 0 at the gate |
| Pile-up rate | 3 sig figs (MHz) | Poisson / bootstrap CI | state the tau_eff assumption explicitly |
| Pile-up fraction | 4 decimals/event | bootstrap CI | report as fraction, not only a raw count |
| MSE (shape) | 5 decimals | — | reconstruction MSE on normalized waveforms |

**Rules:**
- Quote sigma as **sigma68 (robust)** by default; if you quote a Gaussian-core sigma, also quote
  full RMS and the tail fraction, and report chi2/ndf (a blank chi2/ndf is an open caveat — see
  `S04`).
- For every count comparison, write `(expected, actual, delta)`. The gate delta must be 0.
- For every ML-vs-traditional metric, write `Delta = ML - traditional` and its CI. State whether the
  CI excludes zero.

---

## 3. Plot requirements

Every report must include the following figures (PNG, in `reports/<id>/figures/`):

1. **Reproduction-gate sanity plot** — e.g. amplitude distribution with N annotated on the panel,
   so a reader sees the anchor count visually.
2. **Main result figure** — traditional vs ML, with error bars (CIs).
3. **Leakage-control figure** — the null distributions from target shuffle / run-family holdout /
   event-block shuffle, with the observed statistic marked.
4. **Pull plot** — `(result - null_mean) / null_std` for each metric; a win must sit far from 0.
5. **Cross-validation / LORO spread** — box or violin plot of per-fold values, so a reader sees
   whether the win is uniform or driven by one run.
6. **MC comparison panel** — data vs MC for the observable, OR a labeled placeholder
   "MC pending: <MV_ID>".

**Figure conventions:** `fig.set_size_inches(8, 5)` (single) or `(12, 8)` (multi-panel), `dpi=130`,
`tight_layout()`, explicit axis labels *with units*, a title carrying the study ID, and a legend
that names the traditional and ML methods. Save with the study ID in the filename
(`fig_<id>_<what>.png`). Register every figure in `docs/FIGURE_INDEX.md`.

---

## 4. Leakage controls (the most important section)

Most invalidated claims in this project died here. Before you claim *any* ML win, run all three:

1. **Target shuffle (permutation null).** Refit the *same* model with the labels randomly permuted.
   Expectation: AUC ~ 0.5000, or regression skill ~ 0. If the shuffled model still "wins", the
   pipeline is leaking and the claim is rejected.
2. **Run-family holdout (LORO).** Exclude *all* events from a held-out run (or run family) from
   training and evaluate only on it. A win that exists in-fold but vanishes under LORO is
   **control-sensitive** and is not adoptable (see `S03a-d`: the HGB residual gain at 1.394 ns
   shrank or vanished under LORO + shuffle).
3. **Event-block shuffle.** Shuffle events within time blocks to break temporal/acquisition
   correlations the model could exploit as a proxy for the label.

**Decision rule:** the ML claim is **REJECTED (-> CORRECTED)** unless it beats the traditional
baseline on ALL THREE controls with a CI excluding zero. Document each control's result in section 6
and plot the nulls (section 3, figure 3).

**Canonical leakage traps in this project (do not repeat):**
- `D_t` / curvature classifiers hit AUC ~ 1.000 because the label *is* a function of the input —
  self-referential, not a win (`S07b`, `S07e`, `S07g`, `P02d`).
- Saturation recovery clipped at `C = frac*A` let the model read amplitude off `max = frac*A`,
  giving an absurd res68 ~ 0.002. The fix was a *constant* ceiling; recorded in `fleet/LESSONS.md`
  as the canonical cautionary tale (`P07`). **A benchmark that looks perfect is usually leaking.**

---

## 5. The scientific mindset for this project

- **Scan first, hypothesize second.** Find what is real in the data before constructing a story.
- **Design the falsifying test, not the confirming one.** Ask "what would prove this wrong?" and run
  *that*.
- **CORRECTED is a positive result.** Discovering an ML claim was leakage *advances* the program.
  Mark it, record it, move on — do not bury it.
- **Compare to the STRONG traditional baseline.** Beating a strawman proves nothing. The incumbent
  is the best analytic method available (e.g. analytic amplitude timewalk, the GEANT4 Birks lookup).
- **The constraint is the next idea.** When a method fails, name the constraint precisely — it points
  at the adjacent study.
- **Vary one dimension at a time.** A failure unconditionally can succeed conditioned on the right
  slice (topology, run, saturation, current).
- **Truth-limited honesty.** Where there is no data truth (absolute energy, per-event PID, real
  pile-up, forced pedestal), say so plainly and route the question to MC — do not manufacture truth.

---

## 6. Confidence labels (use everywhere, including the synthesis)

Every claim carries exactly one label:

- VALIDATED (data + MC): reproduced anchor, beats strong baseline with CI excluding zero,
  survives all leakage controls, AND agrees with MC truth within stated tolerance. Marked with the
  check mark in synthesis docs.
- DATA-ONLY (MC pending): strong data result, but the closing MC validation has not been run.
  Marked with the warning sign in synthesis docs.
- INVALIDATED / CORRECTED: an apparent win that failed a leakage control or an MC cross-check.
  Marked with the cross mark in synthesis docs.

---

## 7. Template: a complete REPORT.md (fillable)

```markdown
# S0X — <Title>
- Study ID: S0X
- Date: 2026-06-DD
- Status: DONE
- Authors: CCB analysis fleet
- Dependencies: S00 (gate), S02 (timing pickoff)
- Data anchor: 640,737 selected B-pulses

**ML <wins|ties|loses|CORRECTED>: <metric> <ml> vs <trad> (Delta=<d>, CI <ci>); <leakage verdict>.**

## Reproduction gate
Command: <cmd>
Expected: <count>;  Actual: <count>;  Delta: 0
Seed: random_state=20260601

## Key metrics
| Metric | Traditional | ML | Delta (ML-trad) | CI | Leakage-safe? |
|---|---|---|---|---|---|
| sigma68 (ns) | 1.494 | 1.394 | -0.100 | [-0.140,-0.061] | LORO: shrinks; shuffle: fails -> CORRECTED |

## Physics motivation
<2-3 sentences>

## Methodology
- Selection: <filter>; (expected, actual, delta) = (..., ..., 0)
- Features: <list with units>
- ML: <algo, hyperparams, LORO folds = runs {...}>
- Traditional: <full analytic definition>
- Leakage controls: target-shuffle <result>; LORO <result>; event-block <result>

## Results
<table + comparison panel + Delta with CI>

## Interpretation
<physics-first; what it does and does not answer>

## MC verdict
MC validation available: MV<k>. MC <x> vs data <y>; agreement within <z>%.
(or: MC not yet run — required to close; proposed MV<k>.)

## Open questions
1. <id> — <hypothesis> — falsifying test: <test>

## Provenance
git <hash>; data sha256 <...>; py <...>; sklearn <...>; host <...>
```

---

## 8. Template: JSON summary schema (`manifest.json` per report)

Every report directory carries a machine-readable `manifest.json`:

```json
{
  "study_id": "S03d",
  "title": "LORO timewalk residual correction",
  "date": "2026-06-23",
  "status": "CORRECTED",
  "verdict": "loses",
  "depends_on": ["S00", "S02", "S03a"],
  "data_anchor": {"expected": 640737, "actual": 640737, "delta": 0},
  "seed": 20260601,
  "metrics": [
    {
      "name": "sigma68_ns",
      "traditional": 1.494,
      "ml": 1.394,
      "delta": -0.100,
      "ci": [-0.140, -0.061],
      "ci_method": "bootstrap_1000",
      "units": "ns",
      "leakage_safe": false
    }
  ],
  "leakage_controls": {
    "target_shuffle": "pass(0.50)",
    "loro": "win_shrinks",
    "event_block_shuffle": "fail"
  },
  "mc": {"available": false, "mv_id": "MV4", "note": "timing MC validation pending"},
  "confidence": "invalidated",
  "provenance": {
    "git": "<hash>", "data_sha256": "<sha>", "python": "3.11",
    "sklearn": "1.4", "host": "LUNARC cn039", "slurm_job": null
  },
  "figures": ["fig_s03d_head_to_head.png", "fig_s03d_loro_spread.png",
              "fig_s03d_shuffle_null.png"]
}
```

---

## 9. Naming conventions

- **Report directory:** `reports/<epoch>.<pid>.<hash>__<slug>/` for fleet-generated studies, or
  `reports/<STUDY_ID>_<descriptive_slug>/` for orchestrator-run studies. Keep the study ID
  recoverable from the directory name.
- **MC validation:** `reports/mv<k>_<slug>_<epoch>/` with a `mv<k>_summary.json`. MV IDs are MV0
  (digitizer calibration), MV1 (PID), MV2 (energy/range), MV3 (stopping depth vs occupancy), MV4
  (timing), MV5 (pile-up overlays), MV6 (anomaly species), MV7-MV9 reserved.
- **Figures:** `fig_<id>_<what>.png`, registered in `docs/FIGURE_INDEX.md`.
- **Files in a report dir:** `REPORT.md`, `manifest.json`, `figures/`, and any `*.npz`/`*.json`
  intermediate artifacts.

---

## 10. How to update FINDINGS_SYNTHESIS.md when a study closes an open question

When a study lands that changes the state of knowledge:

1. **Locate the relevant section** (timing / pile-up / amplitude / pedestal / PID / representation)
   in `FINDINGS_SYNTHESIS.md`.
2. **Update the confidence label** for the affected claim. If MC just closed a data-only claim,
   flip the warning sign to the check mark and add the MC number to the "MC verdict" subsection.
3. **Add the number with its CI** and a citation to the report directory.
4. **Move the closed item** out of "Remaining open questions" and into the body; if a new constraint
   surfaced, add it to the open-questions list with a concrete MV/study proposal.
5. **Update "What we know for certain"** only if the new result is leakage-safe AND (for physics
   claims) MC-consistent.
6. **Update `reports/SUMMARY.md`** (one row) and `PROJECT_REPORT.md` status tables in the same pass.
7. **Regenerate** any synthesis figures referenced and re-point `docs/FIGURE_INDEX.md`.

A study is not "closed" until all of the above are done in one pass. Partial updates create drift.

---

## 11. Checklist (paste into every PR description)

```
[ ] Reproduction gate passes exactly (delta = 0)
[ ] One-sentence verdict present and uses an approved template
[ ] Every number has units + CI + baseline comparison
[ ] Traditional baseline is the STRONGEST available form (no strawman)
[ ] All three leakage controls run and plotted; decision rule applied
[ ] Confidence label assigned (validated / data-only / invalidated)
[ ] MC verdict section present (number, or explicit MV proposal)
[ ] 6 required figures present, dpi=130, labeled with units, in FIGURE_INDEX
[ ] manifest.json valid against the schema
[ ] Provenance block complete (git, data sha256, env, host)
[ ] FINDINGS_SYNTHESIS.md + SUMMARY.md + PROJECT_REPORT.md updated in the same pass
```

*End of standard. A report that ticks every box above is publication-grade and leaves no reviewer
question unanswered. Anything less is a draft.*

---

## Appendix A — Worked examples (corrected 2026-07-03)

> **Correction (2026-07-03).** An earlier version of this appendix presented S03d as a worked
> CORRECTED example with Δ = −0.100 ns, CI [−0.140, −0.061]. Those numbers exist in no artifact,
> and S03d's actual verdict was `stable_no_leakage_flag`, not CORRECTED; it never ran an
> event-block shuffle. The stitched example is replaced below with the real records.
> (External Review 2026-07-02)

### A.1 — The real S03d record (verdict: `stable_no_leakage_flag`)

**Setup.** S03d tested leave-one-run-out stability for the S03a amp-only and S03b monotone-binned /
HGB timewalk corrections. Anchor reproduced exactly (640,737 selected pulses; held-out runs
{58, 59, 60, 61, 62, 63, 65}, bootstrap unit = held-out run).

**Result** (from `reports/1781010985.923.35c141ac/result.json`, pooled LORO):
- HGB residual corrector: sigma68 = **1.394 ns**, CI **[1.242, 1.682]**
- s03a amp-only (traditional): sigma68 = **1.551 ns**, CI **[1.369, 1.925]**
- Verdict: **`stable_no_leakage_flag`** — the HGB gain *survives* LORO here; the CIs overlap, so
  this is not an adoptable CI-excluding-zero win either. It is a stability record, not a CORRECTED
  example.

### A.2 — A worked example of a CORRECTED verdict (P01 representation superiority)

The genuinely CORRECTED family is **P01**: the claim that a learned waveform representation beats
hand-crafted/PCA features on downstream tasks. The event-shuffle diagnosis (P01f,
`reports/1781018587.1208.05763e48/`) grounds it with real numbers (pooled, held-out runs
{42, 57, 64, 65}, 1224 pair residuals):

| Method | sigma68 (ns) | CI |
|---|---|---|
| Strict CFD20 (weak baseline) | 3.188 | [3.052, 3.303] |
| Strict traditional hand-shape ridge | 1.962 | [1.865, 2.063] |
| Strict ML AE latent ridge | 1.965 | [1.891, 2.054] |
| Strict ML **event-shuffled target** | 2.056 | [1.949, 2.173] |

Two independent falsifications:
1. **No win over the strong baseline:** the AE latent (1.965 ns) does not beat the traditional
   hand-shape ridge (1.962 ns) — the apparent superiority existed only against the weak CFD20
   baseline.
2. **The shuffled-target control retains most of the gain:** a model trained on an event-shuffled
   target still reaches 2.056 ns vs CFD20's 3.188 ns — most of the apparent "representation gain"
   is run/stave/amplitude composition structure, not per-event timing signal.

**Verdict: CORRECTED.** The representation-superiority claim is withdrawn; the transparent
traditional method remains the production candidate.

**Lesson for future sessions.** A gain over a weak baseline is *necessary but not sufficient*.
Adoption requires beating the strongest traditional baseline AND surviving all three controls —
including a shuffled-target control whose residual "skill" exposes composition leakage. Report the
correction proudly.

Note the contrast with `S03k`, where HGB on waveform+amp+shape+stave features reached 1.107 ns and
CI-beat the analytic comparator: that result is real *in-fold* but the report correctly leaves direct
downstream substitution **gated** pending the same transfer/leakage audit. "Gated" is a legitimate
status — it means "real but not yet adoptable", distinct from both "wins" and "CORRECTED".

---

## Appendix B — Project reference values (cite these as anchors, never re-derive silently)

These are the frozen reference numbers. If your study produces a different value for one of these,
you have either found something or broken something — investigate before reporting.

| Anchor | Value | Source |
|---|---|---|
| Selected B-pulse count (median selector) | 640,737 (exact) | S00 |
| Selected B-pulse count (dynamic selector) | 706,373 (exact) | S00b/S00c |
| Sample I analysis B2 | 241,422 | S00 |
| Sample II analysis B4 / B6 / B8 | 21,229 / 11,148 / 4,506 | S00 |
| Analytic amplitude-timewalk sigma68 (champion) | 1.494-1.551 ns (LORO) | S03/S03c/S03d |
| Pretrigger-proxy LORO sigma68 (best traditional) | 1.343 ns | S02d+S16e |
| CFD20 baseline pickoff sigma68 | 1.846 ns | S02 |
| Template-phase pickoff sigma68 | 2.889 ns | S02 |
| A1-A3 robust width (A-stack cross-check) | 1.389 ns (note: 1.43 ns) | S18 |
| Pile-up R_max (note assumption, tau_eff=90 ns) | 4.222 MHz | S10b |
| Pile-up R_max (measured live-time, corrected) | ~3.05 MHz | S10b/S10c |
| 10% tail-crossing live-time | 124.79 ns, CI [123.33, 126.36] | S10b/S10c |
| Two-pulse recovery time-RMS (ML vs trad) | 10.67 vs 13.30 ns (survivorship-conditioned; see P05f) | S11a |
| Two-pulse recovery failure rate (ML vs trad) | 0.295 vs 0.168 (survivorship-conditioned; see P05f) | S11a |
| Duplicate-readout amplitude res68 (ML vs trad) | 0.003-0.009 vs 0.12-0.20 (strong baseline: Huber closure 0.0203, P04d — cite this, not the 0.12-0.20 strawman) | P04 |
| Saturation recovery res68 (ML vs template) | 0.032-0.046 vs 0.104-0.286 | P07 |
| Pedestal MAE (learned vs pretrigger-median) | 48.9 vs 341 ADC | S16 |
| MV1 PID AUC (HGB / logreg / cut purity) | 0.9860 / 0.9629 / 0.8910 | MV1 |
| MV1 HGB purity at 90% eff | 0.9644 | MV1 |
| MV2 deuteron stop layer / proton stop layer | ~0-1 / ~4-7 | MV2 |
| MV2 truth protons / deuterons (1M events) | 836,534 / 314,646 | MV2 |

*End of appendices.*
