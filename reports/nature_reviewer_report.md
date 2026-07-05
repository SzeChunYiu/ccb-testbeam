# Referee report — CCB test-beam analysis (HIBEAM-NNBAR range-telescope timing/pile-up study)

*Prepared in the referee stance defined by `.claude/skills/nature-reviewer/SKILL.md`. The skill's
default deliverable is three reviewer reports plus a synthesis; the user explicitly requested a
single report structured as summary-of-claims / significance / prioritized major+minor points, which
the skill permits ("unless the user explicitly asks for another structure"). I have kept the skill's
red lines: no invented data, controls, or citations; supported / weak / not-assessable are
distinguished; no editorial decision is issued; and fit-to-Nature is treated as the editor's call,
not mine. The three source-grounded emphases (technical soundness; originality/significance;
interdisciplinary readership/readability) are folded into the point list rather than split across
personas.*

---

## Review setup

- **Input scope.** `WIKI.md` (primary), `FINDINGS_SYNTHESIS.md`, `PROJECT_REPORT.md`, and seven
  post-review program reports (Phase 2 geometry/MV3; MC03 overlay + τ_eff; Phase 4 Birks/MV6b/A-arm;
  S21 trigger-truth; S23 data–MC; S22 timing-vs-amplitude; STATS01 FDR census). I read the report
  prose and the tabulated numbers, not the raw ROOT/CSV artifacts or the analysis code.
- **Assessment boundary.** I did not rerun any analysis, inspect figures beyond their legends, or
  audit the digitizer/GEANT4 code. Claims about internal statistical behaviour are read off the
  reported tables. Where a number is only asserted in prose with no artifact, I mark it
  not-assessable.
- **What is under review.** A data-driven analysis of a two-arm scintillator range telescope
  (190 MeV p on CD₂), post external-review correction program. The manuscript is explicitly
  "preliminary, not peer-reviewed" and is a research synthesis, not yet a submitted paper.

## Shared manuscript claim summary

The manuscript makes, post-correction, the following headline claims:

1. **Timing.** Analytic amplitude timewalk is the timing champion (σ₆₈ ≈ 1.49–1.55 ns LORO; best
   traditional variant 1.343 ns), ML ties or loses; per-stave downstream resolution ≈ 0.85–1.1 ns at
   high amplitude (S22); best single-stave (B6) ≈ 0.68–0.75 ns and combined 3-stave ≈ 0.54–0.56 ns —
   both flagged "under review."
2. **Pile-up.** R_max revised from ~4.22 MHz to **≤ 3.05 MHz** (one-sided data-driven bound;
   censoring-aware estimators suggest ≈2.1 MHz). First independent MC live-time (MC03) = 134.99 ns
   vs data 124.79 ns (+8%, honest disagreement).
3. **Two-pulse recovery.** Honest truth-labelled benchmark (MC03/S24) replaces the retracted rigged
   S11a: traditional wins at matched 80% coverage, ML wins at full coverage (0.011 vs 0.048).
4. **PID.** p/d separation MC-closed at AUC = 0.986; data within 0.5% of the MC ceiling.
5. **Stopping depth (MV3).** Re-graded FAIL → TENSION: the χ²/ndf = 68,269 discrepancy is traced to
   the **unsimulated two-arm coincidence trigger**, not missing material (material narrative
   falsified: ≲0.8 g/cm² available vs ≥10.5 needed); a truth-level trigger proxy + event basis +
   species-inclusive + gain 60 collapses it to 625 (109×).
6. **Sample-I deuteron enrichment** confirmed at truth level (S21: B2 ratio 1.519) and in data
   (S23: B2 f(A>5000) ratio 3.45); MC under-predicts the contrast (DR 0.738, z = −99).
7. **Anomaly.** The 4.4% early-peak class is **not C12 recoils** (MV6b: 0/1,656 quenched C12 records
   pass A>1000 at any gain); reopened as an instrumental/trigger-phase data-side question.
8. **Gain.** No precision value: ≈60–80 ADC/MeV, "dominated by trigger/quenching modelling."
9. **Methodology.** Most apparent ML "wins" fail leakage controls; a program-level BH-FDR census
   over 1,948 delta-CI claims exists.

## Visible evidence base

Reproduce-first data gate (640,737 pulses, exact); leakage controls (target-shuffle, LORO,
event-block shuffle); bootstrap CIs; SLURM job IDs, md5/sha256 provenance, git commit, and
reproduce commands in most program reports; 1M-event GEANT4 truth tree; a config-driven per-stave
digitizer (mc02) with physically-motivated Birks quenching and a unit-test suite (157 tests).

## Missing materials affecting confidence

Machine-readable delta-CIs for the two flagship ML wins (P04 duplicate-readout, P07 saturation) are
absent from the FDR census; no real trigger simulation (Trig_bar unscored); no matched per-stave
MV4; no measured inter-stave timing covariance; no confirmed same-run Sample-I/II control in data;
the GEANT4 production macro / LayerID→stave mapping is unsigned-off and "under review."

---

## Significance assessment

- **Originality.** The analysis is careful and, in places, genuinely disciplined — the leakage-hunt
  culture and the willingness to retract (MV0, MV5, MV6, S11a) and re-grade under adversarial review
  are above the field norm. But the individual physics results are incremental detector-R&D
  measurements (timing resolution of a range stack; a pile-up tolerance bound; p/d range
  separation). The single most transferable contribution is methodological: a worked demonstration
  that most ML "wins" in a physics-instrumentation pipeline evaporate under run-family / event-block
  leakage controls and multiplicity control. That is interesting, but it is a lesson, not a
  discovery, and it is not framed or evidenced as a general result.

- **Scientific importance.** Field-local. The results matter to HIBEAM-NNBAR detector design and to
  the scintillator-timing/pile-up instrumentation community. I do not see a claim of outstanding,
  far-reaching importance that the current evidence establishes. Several would-be headlines are, by
  the authors' own labels, "under review," "REVIEW," "TENSION," a "bound," or "no precision value" —
  i.e., the physics headlines are qualified, and the two cleanest results (PID AUC ceiling; C12
  exclusion) are confirmatory/negative rather than novel-and-broad.

- **Interdisciplinary readership.** Narrow as physics; the ML-evaluation-discipline angle is the only
  part with plausible cross-domain reach (ML-for-science practitioners), and it is currently buried
  in a detector-analysis wiki rather than developed as a standalone methodological result.

- **Readability for nonspecialists.** The WIKI is pedagogically strong (diagrams, plain-language
  setup). But the correction program has left the headline tables so heavily caveated (nearly every
  row carries ⚠️/🔶/⛔) that a nonspecialist cannot extract a single defensible take-home number.
  Honesty is a strength; the absence of a clear, validated primary result is a weakness.

Net: this reads as strong, honest **detector-R&D and analysis-methodology** work. Establishing a
Nature-style broad-importance case from the present material is not supported, and I would not
represent it as settled.

---

## Major points (prioritized — address before the case is established)

**M1 — The central re-grade (MV3 FAIL → TENSION) rests on a truth-level trigger *proxy*, not a
simulated trigger, and the residual fit is still catastrophic.**
The manuscript's flagship correction — "root cause = the unsimulated two-arm coincidence trigger" —
is demonstrated only by requiring a truth-level A-arm coincidence post hoc. The `Trig_bar` volumes
are in the geometry but are *not scored*; no real per-event trigger flag exists. Even at the best
grid point the residual is χ²/ndf ≈ 555–1,061 (Phase 2 report), i.e. ~25σ-per-bin from agreement.
Calling this "root cause established" overstates a result that is directionally compelling but
quantitatively unclosed. Required: score `Trig_bar` as a sensitive detector, emit a genuine
Sample-I/II trigger flag, and re-fit — and soften the prose from "established" to "strongly
indicated, pending trigger simulation" until then. This is the single most load-bearing correction
in the manuscript and it is currently a proxy.

**M2 — Quoted confidence intervals are statistics-only and are contradicted by the systematics on
the same line; several headline CIs are physically meaningless.**
Examples the manuscript prints as headline numbers: MC τ_eff = 134.99 ns **[134.96, 135.01]** (a
±0.025 ns CI) while disagreeing with data by +10.2 ns; double ratios with z = −99 vs 1; S23
occupancy χ² in the hundreds of thousands. These enormous z-values and hair-thin CIs are a symptom,
not a strength: they show that systematic/model error dwarfs the reported statistical error
everywhere that matters, so the CIs do not bound the physical quantity. The review's own note that
pair-residual bootstraps under-cover by ~√1.5 compounds this. Required: attach a systematic
component (or an explicit "statistics-only, systematics dominate — do not interpret as an
uncertainty on the physical value" flag) to every headline CI, and stop quoting sub-0.1-ns CIs on
quantities with %-level model disagreement.

**M3 — The two flagship ML wins (P04 duplicate-readout, P07 saturation) are not covered by the FDR
census, so the manuscript's strongest ML claims are the least statistically certified.**
STATS01 states plainly: of 17 bold wins, 11 survive BH, 0 fail, and **6 have no machine-readable
delta-CI at all** — and those 6 include P04, P04c–e, and P07, precisely the "decisive"/"3–7×" ML
wins the narrative leans on. The census also (a) uses a normal approximation known to understate
skewed-bootstrap tails, (b) inherits the √1.5-too-narrow bootstraps, and (c) still lists the
retired, rigged S11a as a "BH survivor." BH survival is, by the authors' own worked S03k example,
necessary-not-sufficient. Required: emit machine-readable delta-CIs for P04/P07, run them through
the census, reconcile the S11a retirement with the census table, and stop citing P04/P07 as
certified wins until they are actually assessed.

**M4 — The headline timing resolution is internally inconsistent and unvalidated.**
Three different "best" timing numbers coexist: single-stave B6 ≈ 0.68–0.75 ns (Gaussian-core, *not*
σ₆₈, not MC-validated, under review), combined 3-stave ≈ 0.54–0.56 ns (relies on an independent-
error assumption whose covariance validation was *withdrawn* as numerically invalid), and S22's
directly-measured downstream per-stave ≈ 0.85–1.1 ns at high amplitude. These disagree by ~30–60%
and rest on the unproven √2 independence the manuscript elsewhere flags as unmeasured. Worse, S22's
own table shows the amp-only timewalk correction makes low-amplitude bins *substantially worse*
(e.g. B2–B4 1000–1250 ADC: raw 1.847 ns → corrected 3.021 ns) and barely helps at high amplitude —
which invites the question of whether the correction should be applied at all in those regimes.
Required: a single, covariance-correct timing resolution with *measured* (not assumed) inter-stave
correlation, a stated metric (σ₆₈ throughout, not mixed Gaussian-core), MC validation via the
matched per-stave MV4, and confirmation on the reserved partition for any sub-0.3 ns claim.

**M5 — The energy/gain scale is unanchored, and the trigger-preferred gain is mutually inconsistent
with the quenching model the same program adopts.**
Both prior gains (v1 246, v2 92±28) are retracted; the current statement is "no precision value,
≈60–80 ADC/MeV." Critically, the Phase-2 trigger-consistent optimum (~60) was fit on an *unquenched*
threshold model, yet with Birks quenching on, the quenched table has **zero A>1000 rows at gain 60**
(Phase 4 report, §2 caveat). So the gain preferred by the trigger scan produces *no selectable
events* under the quenching law the program now uses — an unresolved internal contradiction, not
merely a "re-scan pending." Because occupancy thresholds, R_max-via-occupancy, S23 amplitude
comparisons, and the two-pulse benchmark's "A>1000-equivalent" boundary all ride on this scale, the
contradiction propagates. Required: the quenched trigger-consistent gain re-scan the manuscript
promises, *before* any occupancy- or amplitude-threshold-dependent number is quoted, and an explicit
statement of which results are gain-invariant (double ratios, median-scaled KS) vs gain-dependent.

**M6 — The data-side "confirmation" of Sample-I enrichment cannot separate the trigger from
run-set/beam differences.**
In data, Samples I and II are *disjoint run sets* with different hardware triggers *and* unmodelled
beam/rate/drift differences (S23 caveats), while in MC Sample I ⊂ II. The S23 "confirmation in data"
(B2 f(A>5000) ratio 3.45) and the "MC moves toward data" direction are therefore consistent with the
trigger hypothesis but not uniquely attributable to it — a same-run or interspersed control is
absent. Moreover the double ratio still deviates strongly from unity (DR 0.738, z = −99), i.e. even
after the mimic, MC and data disagree on the between-sample contrast. Required: state explicitly that
the data-side result is directional/consistent, not a clean confirmation; quantify the plausible
beam-condition contribution between run sets; and avoid the unqualified "confirmed in data" framing
in the executive summary.

**M7 — The MC03 two-pulse benchmark, though much improved, retains a fixed trigger phase and
single-stave topology — and one of those very axes (trigger phase) is the manuscript's leading
hypothesis for the unexplained anomaly.**
The benchmark pins pulse 1 at 50 ns; both methods exploit this, so absolute failure rates are
"optimistic on this axis" (report §7), overlays are single-stave only, and residual kernel-family
circularity remains (fit template shares the card kernel with the generator). Given that the
manuscript simultaneously proposes "trigger-phase-related" as the explanation for the 4.4% early-peak
class (M8), a two-pulse benchmark with *no* phase jitter cannot be treated as representative.
Required: repeat with realistic phase jitter and, ideally, cross-stave overlays; report how the
split verdict (trad@matched vs ML@full) moves under jitter before recommending an operating point.

**M8 — An instrumental class affecting 4.4% of selected data pulses is unexplained and its impact on
the timing/pile-up headlines is unbudgeted.**
Ruling out C12 (MV6b) is clean and convincing (light suppressed 60–100×; 0/1,656 at any gain). But
the manuscript then *defers* the actual cause ("data-side question, P02/P09 leads") without
quantifying whether this 4.4% early-peak population contaminates the timing residuals, the live-time
τ_eff, or the pile-up excess. A 4.4% instrumental class is not a footnote in a paper whose headline
products are a sub-ns timing resolution and a pile-up rate. Required: characterize the class enough
to bound its leakage into each headline observable, or show it is removed by the selection used for
those headlines.

**M9 — Foundational ambiguities sit underneath the stave-level comparisons.**
The LayerID→stave mapping (paired vs odd) is "under review" yet underlies S21/S23/MV3 per-stave
assignments; the GEANT4 production macro / event-to-HRD alignment is unsigned-off ("layer-level
prior + smoke-tested truth tree," PROJECT_REPORT §8.4); the world volume is vacuum (air genuinely
missing, 0.13 g/cm²). Phase 2 argues the mapping is disfavoured for the "odd" variant and that air is
negligible, which is reassuring, but the manuscript should not quote per-stave fractions as
decision-grade while the mapping and production alignment are formally unresolved. Required: close
the mapping question and obtain production sign-off, or carry per-stave numbers explicitly as
mapping-conditional.

---

## Minor points

- **m1 — R_max is quoted three ways.** "≤3.05 MHz," "≈2.1 MHz or lower" (KM/IPCW), and the +8% MC
  τ_eff (which would push the bound lower still) coexist. Give one primary bound with an
  estimator-spread band, and note that the MC excess, if real, tightens rather than validates it.
- **m2 — "MC-closed" PID (AUC 0.986) is a truth-ceiling, not a data validation.** Data reaches it
  only via weak-label proxies, not species truth (the manuscript says so in §8 but the executive
  table's "✅ validated (data+MC)" framing is stronger than the caveat). Align the label with the
  caveat.
- **m3 — MV2 energy numbers are internally caveated as running on the *untriggered* population**, so
  absolute penetration/containment inherit exactly the selection bias Phase 2 identifies. Fine to
  report, but the containment fractions (p 0.70 / d 0.84) should not be read as trigger-representative.
- **m4 — MV7 pedestal closure is MC-on-MC** (zero-signal MC, no correlated noise/drift/contamination)
  and is explicitly a lower bound; the data side still has no true-pedestal sample. Keep it out of any
  "validated on data" column.
- **m5 — The confirmation partition (runs 64, 12–30) is "reserved" but, as far as the reports show,
  not yet used.** Sub-0.3 ns timing claims are therefore not yet confirmed on held-out data; say so.
- **m6 — S22 uses the same runs as S02/S03 ("no fresh confirmation partition")**, so the
  timing-vs-amplitude law is measured and cross-checked but not independently confirmed.
- **m7 — Numbers-with-uncertainty discipline is uneven.** Several PCA/AE MSE, R_max, and per-domain
  ML-verdict numbers are published with no per-point uncertainty (the manuscript flags this for the
  PCA/AE table and the timing-resolution bar chart). A referee expects uncertainties on every
  compared number.
- **m8 — Presentation.** The reliance on emoji status glyphs (✅/⚠️/🔶/⛔) as load-bearing verdict
  encoding will not survive into a manuscript; the same information needs prose/quantitative grading.
  Consider one consolidated "status of each headline" table with a single defensible primary result
  called out.
- **m9 — Terminology drift.** "Confirmed," "closed," "ruled out," "established" are used with varying
  strength across WIKI / FINDINGS / PROJECT_REPORT for the same result (e.g. MV3 "root cause
  established" vs "re-graded TENSION, residual large"). Normalize the strength language across the
  three top-level documents.

---

## Risk / unsupported or not-assessable claims

- **"MV3 root cause = the trigger" (established):** *weak-as-stated / directionally supported.* Rests
  on a truth proxy with residual χ²/ndf ~600–1,100; not established until `Trig_bar` is simulated
  (M1).
- **"Sample-I enrichment confirmed in data":** *supported directionally, over-stated as confirmation.*
  Disjoint run sets + unmodelled beam differences are not separated from the trigger (M6).
- **Headline timing resolutions (0.54–0.56 / 0.68–0.75 ns):** *not established.* Mixed metrics,
  withdrawn covariance validation, unvalidated √2 independence, internal inconsistency with S22 (M4).
- **P04/P07 "decisive" ML wins:** *not assessable from the FDR census* — no machine-readable delta-CI
  submitted (M3).
- **Gain ≈ 60–80 ADC/MeV:** *unresolved.* The trigger-preferred value is inconsistent with the
  adopted quenching model (M5); "no precision value" is the honest current state.
- **C12 ruled out (MV6b):** *supported.* Order-of-magnitude light suppression, robust across gain;
  the cleanest result in the manuscript. The *positive* identity of the 4.4% class remains open and
  unbudgeted (M8).
- **p/d PID AUC 0.986:** *supported as an MC truth ceiling;* the data-side "within 0.5%" uses weak
  labels, not species truth (m2).
- **R_max ≤ 3.05 MHz:** *supported as a soft one-sided bound only,* with factor-~1.5 estimator spread
  and an unreconciled +8% MC live-time (m1).
- **FDR census (11/17 survive BH):** *supported as a bounding exercise,* explicitly necessary-not-
  sufficient; does not certify the headline ML wins (M3).
- **Broad "outstanding importance" / Nature-fit:** *not assessable / not established from the supplied
  material;* this is an editor's judgement and the physics headlines are currently qualified.

*Groundedness note: every point above traces to a number or an explicit caveat in the supplied
documents; I have introduced no new experiment, control, citation, or prior-work comparison.*
