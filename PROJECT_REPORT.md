# CCB Test-Beam — Project Report & Status

**One document with everything a human needs to know about this project: the science, what has been
done, the results, the current state, what is blocking us, and what comes next.**

> **⚠️ STALE (2026-06-28) — superseded by the project dashboard (2026-07-25).**
> This file predates the cluster A–D + Opticks synthesis and still labels several
> since-downgraded claims "PASS" / "VALIDATED". The canonical entry point is now
> [`reports/PROJECT_DASHBOARD.md`](reports/PROJECT_DASHBOARD.md); the publication
> narrative is [`docs/PUBLICATION_NARRATIVE.md`](docs/PUBLICATION_NARRATIVE.md);
> the row-by-row authority is [`docs/claim_ledger.csv`](docs/claim_ledger.csv).
>
> **Specific downgrades vs this file's body:** the legacy pile-up R_max = 3.044 MHz
> is **SUPERSEDED** (CL-012 — do not use) and the canonical Rmax is **BLOCKED**
> (CL-010 / S-STAT-003); the realistic-chain p/d PID is **AUC = 0.898** (clusterA
> #921, PASS) — the 0.986 HGB value is a TRUTH_LEVEL_MC_ONLY ceiling (**GATED**,
> CL-017), not a data result; detector timing (the 0.68 / 0.54 ns values and the
> MV4 "PASS") is **BLOCKED** (CL-002..006, toy-digitizer); "MV5 PASS" → **BLOCKED**;
> "MV6 C12 identified" → **TRUTH_LEVEL_MC_ONLY** (data anomaly **not** identified as
> C12, CL-022); "MV3 FAIL" → **TENSION** (χ²/ndf ≈ 6.8e4, CL-021). Where the body
> below conflicts with the dashboard, **the dashboard wins.**

- **Last updated:** 2026-06-28 (MV0–MV6 + MV3b/MV4b diagnostic studies complete)
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
| **Done so far** | ~230 data-driven studies complete; **all 6 MC validations done (MV0–MV6)**; Sample I/II trigger split reproduced. MV9 synthesis complete. |
| **MC closure (clusters A–D, 2026-07-25)** | On the Krakow 1M-event Geant4 MC the full chain closes: combined timing **σ₆₈ = 0.089 ns** (clusterB #918), PID **AUC = 0.898** (clusterA #921), ADC **119.17 ADC/MeV**, Birks **kB = 0.0156 cm/MeV**, digitizer-domain **Rmax = 0.605 MHz** (clusterC #917); Opticks CPU ctest 9/9, GPU gather PARTIAL. |
| **Headline science (corrected)** | Detector-performance on beam data is **pending raw-data staging + bench calibration** (raw `hrdb_run_*.root` not on LUNARC). Legacy R_max 3.044 MHz is **SUPERSEDED** (CL-012); canonical Rmax **BLOCKED** (CL-010). The 0.986 PID is a GATED truth ceiling (CL-017); the realistic-chain MC AUC is 0.898. |
| **Biggest open item** | Stage raw beam ROOT → unblocks data-side timing / PID / ΔE-E. MV3 stopping-depth **TENSION** (χ²/ndf ≈ 6.8e4, missing upstream material budget, CL-021). Resolve S-STAT-003 (Rmax criterion). Operator bench: SiPM PDE / coupling / digitizer gain vs pulser / measured time anchors. |

---

## 2. The measurement (science in brief)

At the Cyclotron Centre Bronowice (CCB, Krakow) a **190 MeV proton beam** strikes a **deuterated
polyethylene (CD2)** target. Charged particles leaving the target are recorded by trigger
scintillators, a TPC, and **two HRD scintillator range stacks** (A and B), each ~1 m from the
target, acting as a data-driven **ΔE-E / range telescope**.

For each stave we record an **18-sample waveform at 10 ns spacing**, read out at one end via a
wavelength-shifting (WLS) fibre, and reconstruct an amplitude (ADC), a time (ns), and shape
variables. The main analysis uses **B-stack staves B2, B4, B6, B8**; the **A-stack (A1, A3)** is a
decoupled cross-check.

**The two original goals, plus the MC-enabled third:**
1. **Timing resolution** — how precisely a stave (and a multi-stave event) timestamps a particle,
   from same-particle inter-stave time residuals.
2. **Pile-up** — how often overlapping pulses corrupt time/charge, and at what beam rate it becomes
   limiting.
3. **Energy / PID** — truth-limited in data; now addressed via the GEANT4 bridge (MV1/MV2 done).

**The samples**

| Sample | Stack | Enrichment | Role |
|---|---|---|---|
| Sample I (runs 31-57) | B | D-enriched, terminal-B2-like | topology-heavy |
| Sample II (runs 58-65) | B | p-enriched, penetrating | clean timing reference |
| Sample III / IV | A | = Sample I / II runs | A-stack cross-check |

The Sample I/II split is **MC-confirmed**: the trigger-split GEANT4 run reproduces Matthias's
deuteron enrichment in the first B layer (Sci_bar LayerID 1 = stack B, 2 = stack A).

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
| **P09** anomaly | P09a, P09c | ✅ done | ~4% early-peak class; MC-closed: C12 recoils 0.32% (MV6) | ML for novelty; cuts for precision |
| **P10** cond. template | P10a-b | ✅ done | analytic timewalk beats learned template | trad wins |

---

## 4. MC validation status (MV0-MV9)

All six MV studies are now complete. Numbers are from SLURM job JSON outputs (`reports/<id>/*.json`).

| MV | What it validates | Status | Result |
|---|---|---|---|
| **MV0** | Digitizer gain calibration | ✅ 100% v2 corrected | gain = **92 ± 28 ADC/MeV** (net_adc median matching; v1 used raw amplitude vs MC digitizer pedestal — apples-to-oranges); peak_frac=0.733 |
| **MV1** | p/d PID (truth ceiling) | ✅ 100% PASS | HGB AUC **0.9860**, logreg 0.9629, cut purity 0.8910; purity@90%eff 0.9644 (400,369 truth tracks) |
| **MV2** | Energy / range / stopping | ✅ 100% PASS | deuterons stop layers 0-1 (d-frac 0.36-0.39), protons penetrate layers 4-7 (p-frac 0.89-0.90); absolute energy unreachable from data confirmed |
| **MV3** | Stopping-depth profile (Layer↔stave) | ✅ 100% **FAIL** | χ²/ndf = **68,269**; MC B2=47.0%/B8=22.3% vs data B2=87.6%/B8=2.3%. **Structural**: missing upstream material budget in MC geometry — near-stopping protons exceed threshold in B8 unrealistically. Not fixable at analysis level. |
| **MV4** | Timing σ₆₈ reproduction in MC | ✅ 100% PASS/TENSION | σ₆₈_raw = **1.744 ± 0.007 ns** vs data 1.85 ns → pull −1.05 (**PASS**); σ₆₈_corrected = 1.770 ± 0.011 ns vs data 1.50 ns → pull +2.68 (**TENSION**: toy timewalk B coefficient negative/unphysical) |
| **MV5** | Pile-up R_max from live-time model | ✅ 100% **PASS** | τ_eff=124.8 ns → R_max = **3.044 MHz** vs data corrected 3.05 MHz (0.2% agreement); confirms note's 4.22 MHz was wrong (τ_eff=90 ns assumption) |
| **MV6** | Anomaly species ID (early-peak class) | ✅ 100% **PASS** | anomaly fraction = **0.32%** (not ~4%); early-peak class dominated by **C12 heavy-ion recoils** from CD₂ (55% of early-peak tracks), GMM Cluster 2 purity=44.5%; 4 PCA components capture 74.5% variance |
| **MV3b** | Upstream material budget estimation (MV3 FAIL diagnosis) | ✅ done | 11.12 g/cm² extra material needed; 1.08 g/cm² known missing; **10.03 g/cm²** unmodelled inter-stave dead material. See `reports/mv3b_material_budget/` |
| **MV4b** | Physical timewalk model diagnosis (MV4 TENSION diagnosis) | ✅ done | Toy 1/√ADC with B=−23 ns·√ADC is **unphysical** (B<0). Correct form: 1/A = τ_rise·V_th/A. After fix, pull=+2.68 expected to collapse to ~0. See `reports/mv4b_timewalk_model/` |
| **MV9** | MC synthesis | ✅ 100% | 6/6 PRODUCTION; see `reports/mc_validation_synthesis/SYNTHESIS.md` |
| **MV7/MV8** | Systematics / two-ended readout | reserved | — |


## 5. Key findings, ranked by physics impact

| # | Finding | Number (with uncertainty) | Confidence | Source |
|---|---|---|---|---|
| 1 | MC method closure (clusters A–D) | timing σ₆₈ 0.089 ns · PID AUC 0.898 · ADC 119.17 · Birks 0.0156 · Rmax 0.605 MHz (all MC) | ✅ PASS (MC) | A–D / #917–921 |
| 2 | Pile-up R_max | legacy 3.044 MHz **SUPERSEDED** (CL-012); canonical **BLOCKED** (CL-010 / S-STAT-003) | 🚫 / ⛔ | S10b/c + clusterC |
| 3 | p/d PID | realistic-chain MC AUC 0.898 (PASS); 0.986 HGB = GATED truth ceiling (CL-017); data BLOCKED | ✅ / 🟡 / ⛔ | clusterA / MV1 |
| 4 | Duplicate-readout amplitude closure | res68 0.003-0.009 vs 0.12-0.20 | ⚠️ data-only | P04 |
| 5 | Saturation recovery by ML | res68 0.032-0.046 vs template 0.104-0.286 | ⚠️ data-only | P07 |
| 6 | Absolute energy unreachable from data | res68 0.19-0.25 (fails 10%) | ✅ limitation MC-confirmed | S14/MV2 |
| 7 | Range telescope + p/d depth separation | d-frac 0.36-0.39 (lyr 0-1), p-frac 0.89-0.90 (lyr 4-7) | ✅ validated | MV2 |
| 8 | Two-pulse ML recovery vs failure rate | RMS 10.67 vs 13.30 ns; fail 0.295 vs 0.168 | ⚠️ gated on failure rate | S11a |
| 9 | Representation-superiority claim is leakage | latent does not beat hand-crafted under controls | ❌ CORRECTED | P01a-f |
| 10 | Early-peak anomaly class | **0.32%** of tracks; **C12 recoils** (CD₂ target, 55% of early-peak), GMM Cluster 2 purity=44.5% | ✅ MC-identified (MV6) | P02/P09/MV6 |

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
| ~~P0~~ | ~~MV6 — anomaly species ID~~ | **CLOSED**: C12 recoils (0.32% frac, 55% of early-peak) | — |
| P0 | MV3 — stopping-depth FAIL (structural) | χ²/ndf=68,269; B8 MC 22% vs data 2% | MC geometry update required (upstream material budget) |
| P1 | MV0 — gain v2 adopted (92 ADC/MeV) | S16 pedestal proxy-only; no forced-trigger sample in data | accepted systematic |
| P1 | MV4 — timing PASS (raw)/TENSION (corrected) | σ₆₈_raw=1.744 PASS; corrected pull=+2.7σ (toy timewalk unphysical) | investigate physical timewalk model |
| P1 | MV5 — R_max PASS | 3.044 MHz MC vs 3.05 MHz data | closed |
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
