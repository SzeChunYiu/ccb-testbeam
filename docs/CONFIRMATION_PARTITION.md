# Confirmation partition policy

- **Status:** in force (2026-07-03, statistics-hardening pass)
- **Motivation:** External Review 2026-07-02 §4 — all timing studies of the 2026-06 program reuse
  the same 7 Sample-II analysis runs; run 65 is exhausted as a holdout (used in 331 artifacts, 215
  of them as a held-out/evaluation run); with ~238 adaptive studies and thousands of CIs on the
  same events, small "wins" on this set are unfalsifiable without data the fleet has not already
  fitted, tuned, or selected on.

## 1. Run inventory (from `DATA.md` and the artifact census)

Run numbers span 0012–0065. The report run-splits are: **Sample I** = runs 31–57
(calibration 31–42, analysis 44–57; run 43 removed, run 38 absent for the A-stack);
**Sample II** = runs 58–65 (calibration 64). The heavily-reused evaluation set is the
**Sample-II analysis runs {58, 59, 60, 61, 62, 63, 65}** — every one of them appears in
~280–330 result.json artifacts.

## 2. The reserved partition

The following runs are **reserved for confirmation only** (they are the runs *not* in the
heavily-reused Sample-II analysis set):

| Reserved runs | Role in the 2026-06 program | Contamination status |
|---|---|---|
| **Run 64** (Sample-II calibration) | never part of the standard {58–63, 65} evaluation set | least-touched Sample-II run, but **not pristine**: it appears in 147 artifacts (57 as a held-out run, e.g. the P09c-style {42, 57, 64, 65} splits) |
| **Runs 12–30** (pre-Sample-I) | outside both report splits; ≤9 artifact mentions each, none as a timing holdout | effectively untouched, but beam/detector conditions differ from Samples I–II and must be validated (currents, HV, geometry) before use as evidence |

Sample-I calibration runs 31–42 are **not** reserved — they were fitted as training data in
~100 studies each and run 42 served as a holdout 54 times.

> **UPDATE 2026-07-05 (Track A, `reports/trackA_heldout_confirmation/`): the reserved
> partition is DAQ-incompatible, not merely un-staged.** The reserved raw runs were located
> (in `ccb_data/hrd/root/`, never staged into the working dir) and inspected. They cannot
> serve as a held-out confirmation of the Sample-II 18-sample downstream-stave timing
> resolution because they were recorded in a *different acquisition configuration*:
> **16-sample** window (vs 18); the active detector channels are the **odd** channels
> (1/3/5/7) rather than the analysis **even**-channel B-stave map (B2=0,B4=2,B6=4,B8=6), so
> the frozen selection reads near-empty channels (downstream-stave median amplitude 13–17
> ADC); and the active channels are **truncated**, peaking at the last sample (ch7:
> ~99–100% of pulses in the final two samples). This applies to **run 64 as well** — it is
> *not* a clean in-Sample-II holdout. Consequence: the S25 σ₆₈ = 0.490 ns is a **definitive
> single-partition (uncorroborated)** result; a genuine held-out confirmation requires a
> *new* Sample-II-configuration beam run. Run 65 remains the only (exhausted) Sample-II
> holdout. See the Track A report for the per-run channel/amplitude/truncation table.

Honest caveat: nothing in this dataset is a virgin partition. Run 64 is the best available
approximation inside Sample II; treat its **first preregistered confirmation use per claim as the
only use** — after that it is burned for that claim family, like run 65 before it. A genuinely
clean confirmation requires the next beam run.

## 3. The rule

1. **Any sub-0.3 ns timing claim requires confirmation on the reserved partition before
   publication.** This covers (a) any absolute timing resolution quoted with sub-0.3 ns precision
   or claimed below 0.3 ns, and (b) any claimed timing *improvement* (ML-vs-traditional or
   method-vs-method delta) smaller than 0.3 ns — which is every S03-family delta of the 2026-06
   program, including the gated-then-falsified S03k 1.107 ns result (Δ = −0.44 ns vs the analytic
   comparator; see S03p/S03r rows in `reports/SUMMARY.md`).
2. Confirmation means: the exact frozen model/correction and the preregistered metric
   (`sigma68`, `res68_abs`, or `res68_centered` from
   `src/ccb_mc_validation/statistics/estimators.py` — named explicitly), evaluated **once** on the
   reserved runs, with a cluster bootstrap CI at the correct dependence unit
   (`paired_delta_bootstrap`). No hyperparameter, threshold, feature, or selector may change after
   looking at the reserved runs.
3. The confirmation result is reported whatever it says (a failed confirmation is a first-class
   result), and the claim's scoreboard row must cite the confirmation artifact.
4. Claims that pass the program-level BH FDR census (`scripts/stats01_program_fdr.py`) but have
   no reserved-partition confirmation remain labelled **"uncorroborated (single-partition)"** in
   any synthesis document.

## 4. Enforcement

Studies touching runs 64 or 12–30 for anything other than a rule-3 confirmation must state why in
their REPORT.md; reviewers should treat unexplained use of reserved runs as a protocol violation.
Like the Critic gate, this policy is only real if enforced by CI/review, not prose — add a check
that flags configs listing reserved runs outside a `confirmation:` block.
