# CCB Test-Beam — Project Report & Status

**One document with everything a human needs to know about this project: the science, what has been
done, the results, the current state, what is blocking us, and what comes next.**

- **Last updated:** 2026-06-28; corrected 2026-07-03 following External Review 2026-07-02 (MV0/MV2/MV5/MV6 retracted; MV4 under review — see `EXTERNAL_REVIEW_2026-07-02.md`)
- **Repository:** `SzeChunYiu/ccb-testbeam` (branch `main`); canonical tree on LUNARC at
  `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/`
- **Status:** research in progress — all numbers **preliminary, not peer-reviewed**
- **This file is the status entry point.** The science is distilled in `FINDINGS_SYNTHESIS.md`; the
  reporting rules are in `docs/REPORT_STANDARD.md`; a newcomer should start at
  `docs/ANALYSIS_GUIDE.md`. Per-study detail is in `reports/<id>/REPORT.md`; the live scoreboard is
  `reports/SUMMARY.md`.

---

## 1. TL;DR (read this first)

| | |
|---|---|
| **What** | Data-driven analysis of CCB test-beam data (190 MeV protons on a CD2 target, HRD scintillator range stacks), now cross-validated against a GEANT4 Monte-Carlo truth bridge. |
| **Physics goals** | (1) same-particle **timing resolution** of the staves; (2) **pile-up** characterisation; (3+) energy/PID, now reachable via MC. |
| **Data** | 640,737 selected B-stack pulses (median selector) / 706,373 (dynamic selector), 18-sample waveforms @ 10 ns. ~6.4 GB, stored **outside git**, immutable. |
| **Method discipline** | Reproduce-first, traditional **and** ML head-to-head, atomic decomposition, three leakage controls, explicit MC verdict per study. See `docs/REPORT_STANDARD.md`. |
| **Done so far** | ~230 data-driven studies complete; **all 6 MC validations done (MV0–MV6)**; Sample I/II trigger split mimicked in MC (2026-07-03: the enrichment claim is downgraded to a hypothesis for S21 — the earlier run used retracted machinery). MV9 synthesis complete. |
| **Headline science** | Analytic timewalk wins timing (sigma68 ~1.49-1.55 ns); pile-up R_max revised down 4.2 -> ≤3.05 MHz (one-sided bound); ML wins shape-closure tasks; **p/d PID MC-closed at AUC 0.986.** |
| **Biggest open item** | **2026-07-03 correction:** MV0/MV2/MV5/MV6 retracted, MV4 under review (External Review 2026-07-02). MV3 stopping-depth FAIL (structural; root cause not established — MV3b toy estimate retracted). Anomaly species identity reopened (MV6 C12 attribution retracted). |

---

## 2. The measurement (science in brief)

At the Cyclotron Centre Bronowice (CCB, Krakow) a **190 MeV proton beam** strikes a **deuterated
polyethylene (CD2)** target. Charged particles leaving the target are recorded by **two independent
HRD scintillator range stacks** (A and B) at **conjugate angles**, each ~1 m from the target and
each behind its **own trigger scintillators**, with a **TPC in front of stack A** (experiment-owner
setup facts, 2026-07-03). Each stack acts as a data-driven **ΔE-E / range telescope**; the two arms
measure **different particles** — pd-elastic sends the proton into one arm and the kinematically-
correlated deuteron into the other.

For each stave we record an **18-sample waveform at 10 ns spacing**, read out at one end via a
wavelength-shifting (WLS) fibre, and reconstruct an amplitude (ADC), a time (ns), and shape
variables. The main analysis uses **B-stack staves B2, B4, B6, B8**; the **A-stack (A1, A3)** is an
independent arm measuring **different particles** — an independent methodology check, not a
same-particle cross-check (corrected 2026-07-03, experiment-owner setup facts).

**The two original goals, plus the MC-enabled third:**
1. **Timing resolution** — how precisely a stave (and a multi-stave event) timestamps a particle,
   from same-particle inter-stave time residuals.
2. **Pile-up** — how often overlapping pulses corrupt time/charge, and at what beam rate it becomes
   limiting.
3. **Energy / PID** — truth-limited in data; now addressed via the GEANT4 bridge (MV1/MV2 done).

**The samples**

| Sample | Stack | Enrichment | Role |
|---|---|---|---|
| Sample I (runs 31-57) | B | terminal-B2-like; D-enrichment = hypothesis (S21) | topology-heavy |
| Sample II (runs 58-65) | B | p-enriched, penetrating | clean timing reference |
| Sample III / IV | A | = Sample I / II runs | A-arm data (different particles) |

**Trigger definitions (experiment-owner setup facts, 2026-07-03):** Sample I = **A AND B trigger
coincidence** (MC mimic: a charged particle entering the first A and the first B layer within
15 ns); Sample II = **B trigger only** (A ignored). In MC, Sample I is a **subset** of Sample II
(inclusive flags in `src/ccb_mc_validation/io/root_truth.py`); in data, Samples I and II are
**disjoint run sets** taken with different trigger configurations — MC-vs-data sample comparisons
must state this asymmetry. Matthias's deuteron enrichment of Sample I in the first B layer
(Sci_bar LayerID 1 = stack B, 2 = stack A) is a **hypothesis, to be tested by S21**
(trigger-mimicked truth study) — the earlier MC "confirmation" ran on retracted machinery.
Proposed mechanism: the coincidence tags kinematically-correlated pd-elastic pairs.

---

## 3. Status dashboard (study families)

Each row is a study family; per-row detail in `reports/SUMMARY.md`. "ML verdict" uses the
`docs/REPORT_STANDARD.md` taxonomy (wins / ties / loses / CORRECTED / gated).

| Family | Studies | Status | Headline | ML verdict |
|---|---|---|---|---|
| **S00** data gate | S00, S00a-d | ✅ done | 640,737 exact (median); 706,373 (dynamic) | n/a (deterministic) |
| **S01** templates | S01 | ✅ done | AE/PCA basis MSE 0.00208 vs template 0.0444 | ML wins (Delta=-0.0423, CI excl. 0) |
| **S02** pickoff | S02, S02b-d | ✅ done | analytic timewalk 1.49-1.55 ns; CFD20 1.846 ns | trad wins (analytic) |
| **S03** timewalk | S03a-e, S03k | ✅ done | analytic 1.494-1.551 ns champion; S03k 1.107 ns gated | CORRECTED (LORO) / S03k gated |
| **S05** covariance | S05c-e | ✅ done | B2/topology-dominated; ExtraTrees 1.352 ns | small ML gain, support-bounded |
| **S07** ML rigour | S07, S07b-k | ✅ done | D_t/curvature AUC~1.0 self-referential | CORRECTED (leakage) |
| **S10** pile-up | S10, S10b-m | ✅ done | R_max 4.22 -> 3.05 MHz; live10 124.79 ns | trad physics-facing; ML diagnostic |
| **S11** two-pulse | S11a-b | ✅ done | ML RMS 10.67 vs 13.30 ns; fail 0.295 vs 0.168 | ML wins RMS, gated on failure rate |
| **S13** CWoLa | S13b-c | ✅ done | topology ratio 1.445 vs CWoLa 1.220 | ML monitoring only |
| **S16** pedestal | S16, S16b-g | ✅ done | learned MAE 48.9 vs 341 ADC; no true pedestal | ML win, proxy-only |
| **S18** A-stack | S18, S18b | ✅ done | A1-A3 1.389 ns reproduces note | trad (CIs overlap) |
| **P02** representation | P02, P02b-e | ✅ done | AE +40-51% @ dim<=4; PCA wins dim 8 | ML wins (compact only) |
| **P01** downstream rep | P01a-f | ✅ done | latent does not beat hand-crafted | CORRECTED (leakage) |
| **P03** deep timing | P03a-c | ✅ done | MLP/CNN lose to analytic | trad wins |
| **P04** amplitude | P04, P04c-e | ✅ done | res68 0.003-0.009 vs 0.12-0.20 | ML wins (decisive) |
| **P07** saturation | P07, P07b-e | ✅ done | ML res68 0.032-0.046 vs 0.104-0.286 | ML wins (3-7x) |
| **P09** anomaly | P09a, P09c | ✅ done | ~4% early-peak class; species identity open (MV6 retracted 2026-07-03) | ML for novelty; cuts for precision |
| **P10** cond. template | P10a-b | ✅ done | analytic timewalk beats learned template | trad wins |

---

## 4. MC validation status (MV0-MV9)

All six MV studies ran to completion; following External Review 2026-07-02, MV0/MV2/MV5/MV6 are
retracted and MV4 is under review (see rows below). Numbers are from SLURM job JSON outputs
(`reports/<id>/*.json`).

| MV | What it validates | Status | Result |
|---|---|---|---|
| **MV0** | Digitizer gain calibration | ⛔ **RETRACTED** (2026-07-03) | v2 gain 92 ± 28 ADC/MeV retracted: anchor was \|net−pedestal\| of an already baseline-subtracted amplitude (true B2 net median 5752 ADC, not 1781), unreproducible from any committed script; v1 (~246) also invalid. Gain UNKNOWN pending geometry-fixed MC. |
| **MV1** | p/d PID (truth ceiling) | ✅ 100% PASS | HGB AUC **0.9860**, logreg 0.9629, cut purity 0.8910; purity@90%eff 0.9644 (400,369 truth tracks) |
| **MV2** | Energy / range / stopping | ⛔ **RETRACTED pending rerun** (2026-07-03) | momentum unit error → ekin columns eV-scale; edep medians misquoted (artifact: proton 101.1 / deuteron 73.4 MeV). Qualitative depth ordering (deuterons stop layers 0-1, protons penetrate 4-7) still supported |
| **MV3** | Stopping-depth profile (Layer↔stave) | ✅ 100% **FAIL** | χ²/ndf = **68,269**; MC B2=47.0%/B8=22.3% vs data B2=87.6%/B8=2.3%. **Structural**: missing upstream material budget in MC geometry — near-stopping protons exceed threshold in B8 unrealistically. Not fixable at analysis level. |
| **MV4** | Timing σ₆₈ reproduction in MC | ⚠️ **UNDER REVIEW, rerun required** (2026-07-03) | pulls −1.05/+2.68 unreliable: data anchor 1.85 ns is ML-corrected (raw 2.99 ns), single-trace MC vs pair-difference data, σ_data=0.10 assumed. Matched rerun required |
| **MV5** | Pile-up R_max from live-time model | ⛔ **RETRACTED as validation** (2026-07-03) | "MC τ_eff = 124.8 ns" was a hardcoded copy of the data value — no independent MC measurement. The 4.22 → 3.05 MHz correction stands as a data-driven one-sided upper bound (censoring-aware estimators suggest ≈2.1 MHz or lower) |
| **MV6** | Anomaly species ID (early-peak class) | ⛔ **RETRACTED** (2026-07-03) | ran with invalidated gain 246, no Birks quenching, no amplitude threshold, per-track whole-arm waveforms; C12 attribution unsupported; 12× data/MC rate mismatch unresolved |
| **MV3b** | Upstream material budget estimation (MV3 FAIL diagnosis) | ⚠️ toy estimate retracted (own errata) | The 11.12 g/cm² needed / 10.03 g/cm² unmodelled figures were a toy estimate, retracted in MV3b's errata (realistic inter-stave estimate 0.1–0.5 g/cm²/pair); the real missing amount is unknown — beamline audit required. See `reports/mv3b_material_budget/` |
| **MV4b** | Physical timewalk model diagnosis (MV4 TENSION diagnosis) | ✅ done | Toy 1/√ADC with B=−23 ns·√ADC is **unphysical** (B<0). Correct form: 1/A = τ_rise·V_th/A. After fix, pull=+2.68 expected to collapse to ~0. See `reports/mv4b_timewalk_model/` |
| **MV9** | MC synthesis | ✅ 100% | 6/6 PRODUCTION; see `reports/mc_validation_synthesis/SYNTHESIS.md` |
| **MV7/MV8** | Systematics / two-ended readout | reserved | — |


## 5. Key findings, ranked by physics impact

| # | Finding | Number (with uncertainty) | Confidence | Source |
|---|---|---|---|---|
| 1 | Pile-up R_max revised down ~30% | 4.222 -> ≤3.05 MHz one-sided bound (live10 124.79 ns, CI [123.33,126.36]) | ⚠️ data-only (MV5 retracted as validation) | S10b/c |
| 2 | p/d PID is MC-closed | AUC 0.9860 (HGB), data ~0.985 | ✅ validated (data+MC) | MV1 |
| 3 | Analytic timewalk wins timing | sigma68 1.494-1.551 ns (LORO); best trad 1.343 ns | ⚠️ data-only (MV4 under review, rerun required) | S03/S02d+S16e |
| 4 | Duplicate-readout amplitude closure | res68 0.003-0.009 vs 0.12-0.20 | ⚠️ data-only | P04 |
| 5 | Saturation recovery by ML | res68 0.032-0.046 vs template 0.104-0.286 | ⚠️ data-only | P07 |
| 6 | Absolute energy unreachable from data | res68 0.19-0.25 (fails 10%) | ⚠️ data-side limitation stands (MV2 support retracted pending rerun) | S14/MV2 |
| 7 | Range telescope + p/d depth separation | d-frac 0.36-0.39 (lyr 0-1), p-frac 0.89-0.90 (lyr 4-7) | ⚠️ qualitative only (MV2 retracted pending rerun) | MV2 |
| 8 | Two-pulse ML recovery vs failure rate | RMS 10.67 vs 13.30 ns; fail 0.295 vs 0.168 | ⚠️ gated on failure rate | S11a |
| 9 | Representation-superiority claim is leakage | latent does not beat hand-crafted under controls | ❌ CORRECTED | P01a-f |
| 10 | Early-peak anomaly class | ~4% early-peak class in data; species identity open (MV6 C12 attribution retracted) | ⛔ MV6 retracted (2026-07-03) | P02/P09/MV6 |

---

## 6. Data and where everything lives

| What | Path | Notes |
|---|---|---|
| **Canonical tree (LUNARC)** | `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/` | this report, docs, reports, geant4 |
| **Canonical data store** | `/home/billy/ccb-data` (outside repo, immutable) | survived the 2026-06-08 data-loss incident |
| → raw | `…/ccb-data/raw/` | `sorted-a/b.zip`, `root.zip` — sha256-verified vs S00 |
| → extracted | `…/ccb-data/extracted/` | 110 ROOT files (57 hrda + 53 hrdb + sorted), 6.1 GB |
| GEANT4 truth | `geant4/data/output_krakow_1M.root` | 1M-event `hibeam` tree (PDG, Ekin, per-stave EDep/time) |
| Processed S00 table | `data/processed/s00_selected_b_pulses.csv.gz` | git-ignored; regenerate from raw (S01b) |
| Study plan | `studies/STUDIES.md` | S00-S18 + P01-P11, prioritised |
| Per-study results | `reports/<study>/REPORT.md` | one dir per study + `manifest.json` + figures |
| Scoreboard | `reports/SUMMARY.md` | rolling one-row-per-study table |
| Reporting standard | `docs/REPORT_STANDARD.md` | the rules every report obeys |

**Data-safety rules (from the 2026-06-08 incident):** data is read-only, external, immutable, backed
up; never store the only data copy in an agent's working tree. Full post-mortem in `fleet/LESSONS.md`.

---

## 7. Infrastructure status

- **Compute:** LUNARC (fs10 mounted on compute nodes; interactive via `ssh cosmos2`). GEANT4 jobs run
  under SLURM (`geant4/jobs/*.sbatch`). MV1/MV2 ran on cn039.
- **Analysis env:** Python 3.11, `uv`-managed, scikit-learn 1.4.x, numpy/scipy, matplotlib (dpi=130
  figures). GEANT4/ROOT via conda env `nnbar_env` (GEANT4 11.2.2, ROOT 6.32, VGM 5.4.0).
- **Fleet (legacy local):** sandboxed codex workers + keeper; codex pinned at 0.129.0-alpha.15
  (never upgrade). The 0.129 sandbox `.git`/queue write bug is worked around with an external
  bubblewrap jail (`~/.tb-bwrap-codex.sh`). On LUNARC the work is now driven via SLURM rather than the
  local fleet.
- **Code review graph:** `.code-review-graph/` present; use graph tools before grep/read.

---

## 8. Open actions for humans (operator-only)

These cannot be done by an agent and block specific next steps:

1. ✓ MV4/MV5/MV6 SLURM jobs **done** — all 6 MC validations complete.
2. **MV3 geometry (structural FAIL):** stopping-depth MC–data discrepancy (χ²/ndf=68,269) caused by missing upstream material budget in MC geometry. Fixing requires a new MC production run with corrected geometry. Decision needed: physics priority or accepted systematic?
3. **Provide or confirm there is no forced-trigger/random pedestal sample** in the original DAQ; if
   one exists off-tree, it closes the S16 pedestal validation directly.
4. **Sign off on the GEANT4 production macro / event-to-HRD alignment** before MV results are quoted
   as a production calibration (currently a layer-level prior + smoke-tested truth tree).
5. **Decide adoption policy** for the gated S03k 1.107 ns timing model (real in-fold, transfer audit
   pending) and the S11 two-pulse ML (lower RMS, higher failure rate).

---

## 9. Next steps (queued analyses)

| Priority | Item | Closes | Blocker |
|---|---|---|---|
| P0 | MV6 — anomaly species ID (REOPENED 2026-07-03; retracted) | species identity open | honest MV6 redo (Birks quenching, threshold, data-matched selection) |
| P0 | MV3 — stopping-depth FAIL (structural) | χ²/ndf=68,269; B8 MC 22% vs data 2% | root cause not established — beamline material audit + geometry update + nuisance scan |
| P1 | MV0 — gain RETRACTED (2026-07-03); gain unknown | energy scale, S16 pedestal proxy-only | re-derive on geometry-fixed MC with correct anchor variable |
| P1 | MV4 — under review, rerun required | pulls unreliable (comparison mismatches) | matched rerun (per-stave traces, pair-difference, measured σ_data) + physical timewalk model |
| P1 | MV5 — retracted as validation | R_max is a data-only one-sided bound ≤3.05 MHz | independent MC live-time measurement |
| P2 | Validate P07 saturation on real B2>7000 pulses | production saturation use | strengthen S01 template baseline |
| P2 | Two-ended-readout √2 projection with correlated terms | timing projection bias | MV7 (reserved) |

---

## 10. Map of the documentation

| You want… | Read |
|---|---|
| New to the project? Start here | **`docs/ANALYSIS_GUIDE.md`** |
| Status + results overview | **`PROJECT_REPORT.md`** (here) |
| The distilled science | **`FINDINGS_SYNTHESIS.md`** |
| The rules every report obeys | **`docs/REPORT_STANDARD.md`** |
| Master index of all docs | `docs/INDEX.md` |
| Physics background, detail | `docs/00_overview.md` … `docs/09_open_questions.md`, `docs/glossary.md` |
| The full prioritised study plan | `studies/STUDIES.md` |
| A single study's full write-up | `reports/<study>/REPORT.md` + its `manifest.json`/figures |
| The rolling scoreboard | `reports/SUMMARY.md` |
| MC validation architecture | `docs/mc_validation/` (ADR-0001, TASK_LEDGER.md) |
| Data location & manifest | `DATA.md`, section 6 above |
| Standing mistakes to avoid (leakage, etc.) | `fleet/LESSONS.md` |
