# Analysis Report Refresh for `1781083988.768.29c955ca`

- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-07-08
- **Claimed ticket:** `1781083988.768.29c955ca`
- **Primary deliverable:** `docs/ANALYSIS_REPORT.md`

## Question

The claimed queue item asks for a periodic refresh of `docs/ANALYSIS_REPORT.md`
after new reports land. The concrete task is to re-read the rolling scoreboard,
the main synthesis, overview documentation, and a bounded representative set of
new or changed reports, then update method-winner tables, confidence intervals,
caveats, and GEANT4/open-question status.

## Method

The refresh used the existing project synthesis as the baseline and sampled the
newest report set visible in the repository. The bounded report set was chosen
to cover the newest high-impact themes rather than every report:

| Theme | Source |
|---|---|
| Rolling method scoreboard | `reports/SUMMARY.md` |
| Physics synthesis and MC status | `FINDINGS_SYNTHESIS.md` |
| Current report chapter | `docs/ANALYSIS_REPORT.md` |
| GEANT4 PID truth bridge | `reports/1781083265.459.750722a1__s17a_geant4_energy_pid_truth_bridge/REPORT.md` |
| Pretrigger tau sign falsifier | `reports/1781081181.768.455d705f__s16p_pretrigger_tau_sign_inversion_falsifier/REPORT.md` |
| Overlay-to-real pile-up backprojection | `reports/1781081189.836.1e03033f__s10r_overlay_to_real_pileup_backprojection/REPORT.md` |
| Dynamic-only timing quarantine | `reports/1781081167.631.051f65df__s02l_dynamic_only_timing_quarantine_boundary/REPORT.md` |
| Dynamic charge externalization null | `reports/1781081173.700.0ebd3bf2__p04x_dynamic_externalization_null/REPORT.md` |

No new ROOT extraction or model training was run for this ticket because the
claimed work item is a documentation synthesis refresh. The report update only
quotes already-landed study artifacts and preserves their run-bootstrap or
pseudo-run-bootstrap intervals.

The synthesis used a conservative evidence-transfer rule. For each source
study \(s\), the refresh extracted the reported traditional comparator
\(T_s\), the strongest ML/NN comparator \(M_s\), its reported interval
\([L_s, U_s]\), and the source study's own applicability statement
\(A_s\). A method was promoted in the chapter-level table only when the source
study both won its local metric and retained the same support as the intended
physics use:

\[
\Delta_s = M_s - T_s,\qquad
\mathrm{promote}(s) = [\Delta_s > 0] \land [0 \notin CI(\Delta_s)] \land A_s.
\]

For error metrics where lower is better, the sign convention was reversed
before evaluating \(\Delta_s\). When a source result was strong only on a
synthetic, duplicate-readout, dynamic-selector, or simulation-truth target, the
chapter records the numerical win but marks the status as diagnostic or gated
instead of physics-adopted. Reported confidence intervals are not recomputed in
this ticket; they are carried forward from the underlying run-block bootstrap
or pseudo-run bootstrap described in each source report.

## Updated Results

The documentation now has a new subsection,
`12.1 Latest Refresh From July 2026 Reports`, summarizing five recent reports:

| Study | Traditional comparator | ML/NN result | Synthesis verdict |
|---|---|---|---|
| S17a GEANT4 truth bridge | DeltaE/range AP 0.7666 [0.7570, 0.7771] | HGB AP 0.9918 [0.9910, 0.9925]; 1D-CNN 0.9904; MLP 0.9902; ridge 0.9381 | HGB wins simulation-side PID ranking, not yet data calibration |
| S02l dynamic-only timing quarantine | Median-first timing sigma68 1.655 [1.530, 1.847] ns | Dynamic/proxy refits near 5 ns | Traditional timing remains preferred |
| S10r overlay-to-real pile-up | Template overlay AUC 0.770 [0.738, 0.804] | GBT overlay AUC 0.862 [0.836, 0.888] | Synthetic ML win, real backprojection gated |
| S16p pretrigger tau sign | Stratified score downstream delta 0.5938 [0.5388, 0.6806] | Ridge delta 0.6307 [0.5699, 0.7406] | Ridge diagnostic win only |
| P04x dynamic charge externalization | Strong Huber duplicate res68 0.696 [0.642, 0.879] | Dynamic-selector GBT duplicate res68 0.0877 [0.0693, 0.0951] | ML wins local closure, externalization mostly null |

The method-winner table was extended with rows for dynamic-only timing support,
overlay pile-up backprojection, dynamic-selector duplicate charge, pretrigger
tau sign, and the GEANT4 truth PID bridge. The caveats now explicitly state
that held-out local closure is insufficient for promotion when the target is
the same electronics channel or a synthetic construction; a support-preserving
externalization test is required.

## Prompt-to-Artifact Checklist

| Requirement from claimed ticket | Evidence in this refresh |
|---|---|
| Re-read `reports/SUMMARY.md` and `FINDINGS_SYNTHESIS.md` | Both files are listed in `result.json` and in the source table appended to `docs/ANALYSIS_REPORT.md`. |
| Re-read docs overview material | The updated source table records `docs/00_overview.md` through `docs/09_open_questions.md` as the setup and methods sources for the chapter. |
| Use a bounded representative set of new or changed reports | Five latest high-impact reports were incorporated: S17a, S16p, S10r, S02l, and P04x. |
| Update method-winner tables | Five new rows were added to section 12: dynamic-only timing, overlay pile-up, dynamic-selector duplicate charge, pretrigger tau sign, and GEANT4 truth PID bridge. |
| Preserve confidence intervals | The refresh carries forward the source-report intervals for AP, AUC, downstream-sign deltas, and robust residual widths. |
| Update caveats | Section 13.5 now states the externalization requirement for local-closure ML wins. |
| Update GEANT4/open-question status | Section 14 now includes the S17a GEANT4 truth-bridge and S10r overlay-to-real transfer status. |
| Append at most one novel ticket | No novel ticket was appended; `result.json` contains an empty `next_tickets` list. |

## Systematics and Caveats

This ticket is a synthesis update. It inherits the limitations of the source
reports:

- GEANT4 PID truth is simulation-side and still depends on unresolved response
  issues from the MC validation path.
- Overlay pile-up labels are synthetic and do not yet validate real
  high-current unresolved candidates.
- Dynamic-selector duplicate-readout closure is not an external energy or
  charge calibration.
- Pretrigger tau sign scores are diagnostic current-family handles, not a
  calibrated pile-up rate.

## Outcome

`docs/ANALYSIS_REPORT.md` was refreshed with the latest representative
evidence, new method-winner rows, revised ML label-source caveats, updated
GEANT4/PID and overlay-pile-up open-question text, and appended source-report
provenance. No novel ticket was appended.
