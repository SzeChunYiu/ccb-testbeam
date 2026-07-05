# B-M3 — Certify the P04/P07 ML timing/regression wins through FDR

- Generated: 2026-07-05 by `scripts/stats02_p04p07_delta_ci.py` + `scripts/stats01_program_fdr.py`
- Reviewer origin: M3 ("the two flagship ML wins P04/P07 are not covered by the FDR census").
- Companion artifacts: `STATS02_REPORT.md` (per-win delta-CI table), `stats02_delta_ci_summary.json`,
  the five emitted `reports/bm3_<study>_deltaci_20260705_203249/result.json`, and the refreshed census
  `reports/stats01_program_fdr_20260705_203905/` (REPORT.md + claims.csv).

## Problem

The prior census (`stats01_program_fdr_20260703_220116`) reported **6 scoreboard bold wins with no
machine-readable delta-CI** ("prose-only"), and those 6 included the flagship duplicate-readout /
saturation ML wins **P04, P04c, P04d, P04e, P07**. They were cited as wins but could not be
FDR-assessed, so they were **not certified**.

## What was done

1. **Reproduced P04 (canonical) and P07 (saturation) held-out per-pulse residuals from raw ROOT**
   using the original pipelines (imported `scripts/p04_amplitude_charge_regression.py` functions;
   re-implemented the self-contained P07 clip logic), and computed the paired
   `delta = res68(best_traditional) - res68(ML)` with a **paired bootstrap at the correct dependence
   unit -- the physical event `(run,eventno)`**, not the pulse. The iid (per-pulse) bootstrap was run
   alongside to measure the **event-cluster design effect** (clustered_SE / iid_SE).
2. **P04c/P04d/P04e** (bespoke traditional baselines -- adaptive-template ridge, strong Huber -- not
   re-fit here): emitted **conservative** delta-CIs from each study's own per-method bootstrap CIs
   (unpaired `se = hypot(se_trad, se_ml)`, wider than paired), inflated by the measured design effect
   for the two studies whose CIs were iid; P04e already carries **run-block** CIs so it was not
   double-inflated.
3. **Emitted one stats01-compatible `result.json` per study** and **re-ran the program-level
   Benjamini-Hochberg census** so the wins are FDR-assessed inside the amplitude-charge family.

## Result -- delta-CIs (all positive => ML better; z = clustered)

| study | comparison | res68 trad | res68 ML | delta | 95% CI (event-clustered / conservative) | z | BH |
|---|---|---|---|---|---|---|---|
| P04 | amp: peak_calibrated - ml_hgb | 0.1238 | 0.0096 | 0.1142 | [0.1127, 0.1156] | 150 | survives |
| P04 | charge: integral_calibrated - ml_hgb | 0.1954 | 0.0153 | 0.1801 | [0.1783, 0.1825] | 166 | survives |
| P04c | amp: adaptive_template_ridge - ml_hgb | 0.0858 | 0.0091 | 0.0766 | [0.0752, 0.0781] | 105 | survives |
| P04d | amp: strong_traditional_huber - ml_extra_trees | 0.0203 | 0.0027 | 0.0176 | [0.0171, 0.0180] | 84 | survives |
| P04e | amp B2-holdout: traditional_huber - ml_extra_trees (run-block) | 0.1370 | 0.0168 | 0.1202 | [0.1100, 0.1304] | 23 | survives |
| P07 | ceiling 4000: template_scale - ml_gbr | 0.1044 | 0.0324 | 0.0719 | [0.0702, 0.0739] | 77 | survives |
| P07 | ceiling 3000 | 0.2389 | 0.0390 | 0.1999 | [0.1959, 0.2041] | 93 | survives |
| P07 | ceiling 2500 | 0.2332 | 0.0419 | 0.1913 | [0.1873, 0.1962] | 81 | survives |
| P07 | ceiling 2000 | 0.2864 | 0.0459 | 0.2404 | [0.2358, 0.2450] | 106 | survives |

- **Event-cluster design effect = 1.02-1.10 (mean 1.05).** For these observables the duplicate-readout
  and saturation residuals are effectively independent within an event, so the naive per-pulse
  bootstrap is only ~5% too narrow here -- the dependence inflation that dominates the *timing*
  pair-residuals (~sqrt(1.5)) does NOT dominate these amplitude/charge closures. The delta-CIs are
  therefore robust to the dependence unit.

## Census outcome (refreshed)

`reports/stats01_program_fdr_20260705_203905/`: **1,957 delta-CI claims** parsed (was 1,948). Of the
**15** scoreboard bold wins, **14 survive BH, 0 fail, 1 has no machine-readable delta-CI**. All five
P04/P07 wins now appear in the census win table as **"survives BH"** (P04: 2/2 claims, P04c 1/1,
P04d 1/1, P04e 1/1, P07 4/4). The single remaining prose-only win is **P05b** (a *pile-up* two-pulse
study -- outside the P04/P07 scope of B-M3).

**Certification statement:** each P04/P07 win now **passes the program-level BH-FDR census at
q = 0.05 within the amplitude-charge family** with a machine-readable, dependence-aware delta-CI.
They are FDR-certified **as statistically distinguishable from zero** -- the specific gate B-M3
required.

## Reconciliation with the retired S11a (0.295 / 0.168)

S11a (two-pulse recovery, failure rates 0.295 vs 0.168) was retired **not for failing BH but for
being rigged** (External Review P8: the injection grid equalled the fit-hypothesis grid; injected
waveforms were drawn from the fit's own templates; per-method failure definitions at unmatched
coverage). It was replaced by the honest truth-labelled MC03/S24 benchmark. In the census S11a is
**not among the BH survivors** because it carries no clean machine-readable delta-CI, and its rigged
numbers are retired everywhere.

S11a is the cautionary anchor for reading this certification correctly, alongside S03k (BH-surviving
yet leakage-falsified):

- **BH survival is necessary, not sufficient.** It certifies ML != traditional statistically; it
  cannot detect leakage, circularity, or an unfair baseline. S11a would have "won" on its rigged
  effect size; it was correctly killed by mechanism, not by multiplicity control.
- **Do P04/P07 share S11a's circularity?** Partially and less severely:
  - **P04/P04c/P04d/P04e** predict an **independent odd-channel duplicate readout**, not a quantity
    derived from the same samples that define the prediction -- so they do **not** have S11a's
    "fit-grid == injection-grid" circularity. Their standing caveat is milder and already documented:
    a **duplicate-readout electronics closure, not an absolute-energy calibration**; P04d/P04e
    additionally flag B2-externalization / support-frontier limits.
  - **P07** uses a **real truth** (the true unclipped amplitude), not a fit-derived label -- so it is
    materially less rigged than S11a; but the traditional template is built from the same clean-pulse
    family the test pulses are drawn from (kernel-family adjacency), and the natural-saturation
    transfer is unaudited. The win is certified as a statistical result on the artificial-clip task,
    not as a validated operating recommendation.

**Bottom line:** the P04/P07 wins are now FDR-certified (they pass BH with dependence-aware delta-CIs
and are not the rigged-circular kind S11a was), while retaining their pre-existing physics caveats
(duplicate-readout != energy truth; P07 template-family adjacency / natural-transfer unaudited).
"FDR census cannot assess them / prose-only" is retired.

## Reproduce

```bash
/home/billy/anaconda3/envs/nnbar_env/bin/python scripts/stats02_p04p07_delta_ci.py   # emits delta-CI result.json (~6 min, reads raw ROOT)
/home/billy/anaconda3/envs/nnbar_env/bin/python scripts/stats01_program_fdr.py        # folds them into the BH census
```
