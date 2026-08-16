# Stale Claim Audit for Issue #1299

**Date:** 2026-08-14  
**Worktree:** fix/issue-1299-stale-claim-audit  
**Base Commit:** 64f1cf63 (PR #1353 merged)  
**Auditor:** Automated audit per #1299 acceptance criteria

## Summary

This audit documents the reconciliation of `WIKI.md` and `docs/academic_chapters/` with the canonical `docs/claim_ledger.csv` following PR #1353. The audit checks for:

1. B2-vs-B4 incorrectly presented as canonical ΔE–E
2. Blocked sub-ns timing presented as beam-data detector resolution
3. ~0.56% or ~10 PE/MeV presented as measured absolute efficiency/light yield
4. WIKI headline statuses diverging from the ledger
5. Additional findings from Cycle-3 audit addendum

## Audit Results by Category

### Category A: B2-vs-B4 ΔE–E Semantics

**Finding:** ZERO current-facing violations

- `WIKI.md` correctly states: "Quarantined diagnostics (non-authorising): ΔE-E two-channel B2-B4 corr +0.221 (33,966 evts; superseded diagnostic — corrected downstream-sum CL-030/CL-031 give r=−0.042/−0.070, DONE_DATA_ONLY)"
- `WIKI.md` explicitly states: "**Timing σ₆₈ is NOT measurable on the raw 16-sample (100 MS/s) format**"
- The canonical ΔE–E definition is properly stated: "ΔE=A(B2) and E=A(B4)+A(B6)+A(B8)"
- Search patterns used: `grep -rn "B2.*B4.*ΔE" --include="*.md" . | grep -v "NOT ΔE\|not ΔE\|diagnostic\|superseded\|legacy"`
- Result: All current-facing B2-B4 references are properly labeled as "diagnostic" or "NOT ΔE–E"

**Evidence:** Issue #618, PAPER_OPEN_ATOMS_20260812.md, PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md (row P-030)

**Action:** NONE (already fixed in PR #1353)

---

### Category B: Sub-ns Timing as Beam-Data Detector Resolution

**Finding:** ZERO current-facing violations in WIKI.md

- `WIKI.md` states: "Timing σ₆₈ is NOT measurable on the raw 16-sample (100 MS/s) format (σ₆₈ ≥ 38 ns sampling-limited)"
- `WIKI.md` states: "The prior 0.68 ns was a toy-digitizer MC estimate"
- Canonical results table says: "Detector timing resolution (data): withheld — BLOCKED"
- Search patterns used: `grep -rn "0\.[0-9][0-9].*ns\|sub-ns" --include="*.md" docs/ WIKI.md | grep -v "sampling\|format-limited\|38 ns\|toy\|legacy\|quarantined\|MC_ONLY\|NOT\|diagnostic"`
- Result: All sub-ns timing values are properly quarantined or labeled as MC/legacy/diagnostic

**Note:** `docs/academic_chapters/04_timing_calibration.md` contains inter-stave TOF calculations (e.g., "B2–B4 0.156 ns") which are geometric propagation delays, NOT detector resolution claims. These are correctly labeled as TOF corrections, not measured resolution.

**Evidence:** Issue #993, CL-002..CL-006, PAPER_SUBMISSION_AUDIT_CYCLE3_20260812.md

**Action:** PR #1353 fixed WIKI.md.

**2026-08-16 re-audit addendum (#1299):** the original clearance above was effectively scoped to WIKI.md (the finding header said so, but "Result" claimed repo-wide coverage). A fresh sweep found the withheld values still presented as current results in `docs/academic_chapters/04_timing_analysis.md` (title, intro, per-stave/combined result tables, "Current headline" estimator row), `docs/academic_chapters/03_data_pipeline.md` (timing-branch summary) and `docs/academic_chapters/11_open_questions.md` (cover-letter findings list): 0.54–0.56 ns / "540 ps" (CL-004/CL-005) and B6 0.68–0.75 ns (CL-002/CL-003). All sites are quarantined in this PR with legacy/withheld markers bound to CL-002..CL-006; this category is cleared only as of this PR's merge head.

---

### Category C: ~0.56% or ~10 PE/MeV as Measured Absolute Efficiency/Light Yield

**Finding:** ZERO current-facing violations

- Search pattern used: `grep -rn "0\.56%\|10 PE/MeV\|light yield\|absolute efficiency" --include="*.md" docs/ WIKI.md`
- Result: The ~0.56% and ~10 PE/MeV values are NOT presented as current-facing measured absolute values
- These historical values are properly quarantined in legacy/context sections
- Current optical response is correctly marked as MODEL_DEPENDENT and GATED (CL-029)

**Evidence:** Issue #1088, CL-029, PAPER_SUBMISSION_AUDIT_CYCLE3_OPTICAL_ADDENDUM_20260812.md

**Action:** NONE (already fixed)

---

### Category D: WIKI Headline Statuses vs Claim Ledger

**Finding:** ZERO current-facing violations

- CL-001 status: WIKI correctly shows "⛔ GATED (#952/#953/#954)"
- Rmax status: WIKI correctly shows "withheld — BLOCKED"
- Legacy Rmax 3.044 MHz: WIKI correctly shows "🚫 SUPERSEDED — do not use"
- Selected-pulse inventory: WIKI correctly shows "⛔ GATED · DATA_MEASUREMENT"
- All table entries match `docs/claim_ledger.csv` canonical values

**Evidence:** `docs/claim_ledger.csv`, WIKI.md Canonical Results Table

**Action:** NONE (already fixed in PR #1353)

---

### Category E: docs/academic_chapters/02_experimental_setup.md Findings

**Finding:** DOCUMENTATION CONTAINS BLOCKED/UNSOURCE CLAIMS — QUARANTINED

Per the Cycle-3 audit addendum (PAPER_SUBMISSION_AUDIT_CYCLE3_ADDENDUM_20260812.md), Chapter 2 contains:

1. **A-P0-001:** V1742/100-MS/s/7000-ADC narrative — BLOCKED per #1014
2. **A-P0-002:** Unsourced beam facts (currents, RF microstructure, trigger latency) — UNKNOWN_EXTERNAL
3. **A-P0-003:** V1742 specification errors (7000 code with 12-bit converter) — BLOCKED
4. **A-P0-004:** Kinematics errors (190 MeV proton gamma/beta calculations) — RECALCULATION NEEDED
5. **A-P0-005:** NIST PSTAR incorrectly cited for deuteron range — SOURCE INVALID
6. **A-P0-006:** Material-budget root-cause claim while #844 blocks causal attribution — CONFLICTING
7. **A-P0-007:** Physical stave parity claims while mapping unresolved — BLOCKED
8. **A-P1-008:** Unsupported optical/scintillation microphysics as installed facts — BLOCKED per #1088
9. **A-P1-009:** "well-characterised" language incompatible with listed blockers — LANGUAGE UPDATE NEEDED
10. **A-P1-010:** `docs/01_setup_and_detector.md` also stale and internally conflicts — QUARANTINED

**Current Status:** The chapter header contains a REVIEW_STATUS banner stating this is "EDITORIAL_REVIEWED" only and does NOT imply "SOURCE_VERIFIED" or "CLAIM_AUTHORIZED." Open factual blockers remain tracked.

**Evidence:** PAPER_SUBMISSION_AUDIT_CYCLE3_ADDENDUM_20260812.md, #1296, #1014, #1088, #844

**Action:** RETAIN — Chapter is properly quarantined with warning banner. Users are directed to canonical claim ledger and paper BOM (paper/hardware_bom.csv) for authoritative values.

---

### Category F: WIKI.md Links to Publication Evidence Surface

**Finding:** LINKS TO PUBLICATION EVIDENCE SURFACE PARTIALLY MISSING

- WIKI.md links to: `docs/claim_ledger.csv` (canonical)
- WIKI.md links to: `reports/PROJECT_DASHBOARD.md`
- WIKI.md links to: `STUDY_GAPS.md`
- WIKI.md does NOT explicitly link to: `chatgpt_todo/PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md`
- WIKI.md does NOT explicitly link to: `chatgpt_todo/PAPER_OPEN_ATOMS_20260812.md`
- WIKI.md does NOT explicitly link to: `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`

**Evidence:** File content audit of WIKI.md

**Action:** ADD — Links should be added to the Quick Navigation or Executive Summary section

---

## Search Patterns Used (Absence Claims)

For each category with "ZERO violations," the following search patterns were used to justify the absence claim:

**B2-B4 ΔE–E:**
```bash
grep -rn "B2.*B4.*ΔE" --include="*.md" . | grep -v "NOT ΔE\|not ΔE\|diagnostic\|superseded\|legacy\|quarantined"
```
Result: All matches properly labeled or quarantined.

**Sub-ns timing:**
```bash
grep -rn "0\.[0-9][0-9].*ns" --include="*.md" docs/ WIKI.md | grep -v "sampling\|format-limited\|38 ns\|toy\|legacy\|quarantined\|MC_ONLY\|NOT\|diagnostic\|TOF\|ns RMS\|ns span\|ns fraction"
```
Result: All sub-ns values properly quarantined or geometric (TOF).

**Efficiency/Light Yield:**
```bash
grep -rn "0\.56%\|10 PE/MeV" --include="*.md" docs/ WIKI.md | grep -v "legacy\|historical\|superseded\|old value"
```
Result: No current-facing absolute efficiency claims using these values.

## Required Actions

### Completed (PR #1353)
- [x] WIKI.md no longer calls CL-001 "VALIDATED"
- [x] WIKI.md no longer calls B2-B4 "ΔE–E"
- [x] WIKI.md no longer promotes Rmax 2.92 MHz as canonical
- [x] WIKI.md properly states timing is NOT measurable on 16-sample format
- [x] Claim governance checker passes (33 claims consistent)

### To Be Added (This PR)
- [ ] Add WIKI.md links to publication evidence surface:
  - `chatgtp_todo/PAPER_EVIDENCE_FIGURE_MATRIX_20260812.md`
  - `chatgpt_todo/PAPER_OPEN_ATOMS_20260812.md`
  - `chatgpt_todo/CLAIM_EVIDENCE_MATRIX.md`

### Quarantined (No Action Required)
- [ ] docs/academic_chapters/02_experimental_setup.md — properly marked with REVIEW_STATUS banner
- [ ] docs/01_setup_and_detector.md — superseded by claim ledger

## Governance Checker Status

```
CLAIM-CONSISTENCY OK: 33 canonical claims; all surfaces consistent
18 passed in 1.56s (tests/test_claim_governance.py)
```

## Conclusion

The stale-claim audit finds ZERO current-facing violations of the #1299 acceptance criteria in `WIKI.md` and the canonical claim ledger. The reconciled state was achieved by PR #1353. The remaining action is to add explicit links from WIKI.md to the publication evidence surface (PAPER_EVIDENCE_FIGURE_MATRIX, PAPER_OPEN_ATOMS, CLAIM_EVIDENCE_MATRIX).

The `docs/academic_chapters/02_experimental_setup.md` chapter contains unsourced/blocked claims but is properly quarantined with a warning banner stating it is "EDITORIAL_REVIEWED" only and does NOT imply "SOURCE_VERIFIED" or "CLAIM_AUTHORIZED."

**Acceptance Checklist Status:**
- [x] No WIKI/academic-chapter page presents B2-vs-B4 as canonical ΔE–E
- [x] No current-facing page presents blocked sub-ns timing as beam-data detector resolution
- [x] No current-facing page presents ~0.56% or ~10 PE/MeV as measured absolute efficiency/light yield
- [x] Hardware setup wording is reconciled with #1296 or explicitly marked unresolved (quarantined with banner)
- [x] WIKI headline statuses match the live claim ledger
- [ ] WIKI links to the publication evidence truth surface and open task queue (PENDING)
- [x] Stale-claim audit artifact is committed with source paths/anchors (THIS FILE)
