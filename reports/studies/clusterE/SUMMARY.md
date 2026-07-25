# Cluster E — CCB test-beam synthesis layer (VIS-SYS / VIS-REP / VIS-CLAIM)

**Goal.** Merge clusters A-D + Opticks (all on `origin/main`) into one end-to-end
"the project works" view: a systematic budget, an uncertainty-coverage check, a
sensitivity/robustness panel, a reproducibility DAG, a claim dashboard, and the
top-level `reports/PROJECT_DASHBOARD.md`. This cluster **aggregates** — it does
not re-run any physics computation. Every number on every figure is sourced to a
cluster `metrics.json` / `counts.json` / `fig_*_summary.json` or to
`docs/claim_ledger.csv`; nothing is fabricated.

**Driver.** `scripts/clusterE/clusterE_synthesis.py` (pure numpy/matplotlib,
self-contained — no `src/` import). Reproduce:
```bash
source /projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/activate
export MPLCONFIGDIR=/projects/hep/fs10/shared/nnbar/billy/.mplcache
cd <worktree on origin/main>
python scripts/clusterE/clusterE_synthesis.py     # -> reports/studies/clusterE/
```
(Do **not** prefix with `PYTHONPATH=src`; on this LUNARC venv that interaction
drops the venv `site-packages` from `sys.path` and breaks `matplotlib`/`packaging`.
The script inlines the house rcParams so it needs no `src/` import.)

**Honoured governance.** Canonical cross-domain claim status follows
`docs/claim_ledger.csv` (2026-07-25, 26 rows). Where the legacy
`PROJECT_REPORT.md` / `FINDINGS_SYNTHESIS.md` (2026-06-28) still call a number
"PASS", the ledger has since **downgraded** it; this synthesis uses the ledger
state, not the stale prose. Concretely: CL-010 Rmax **BLOCKED**, CL-012
Rmax=3.044 MHz **SUPERSEDED**, CL-013 MV0 gain **GATED**, CL-017/018 PID truth
ceiling **GATED**, CL-002..006 detector timing **BLOCKED**, CL-022 anomaly
**TRUTH_LEVEL_MC_ONLY**, CL-026 systematic budget **BLOCKED**.

---

## The headline, honestly

**The analysis chain works end-to-end on Monte Carlo.** That is what this
programme proves. The detector-performance claims that would transfer that to
data are **BLOCKED_DATA**, because the raw beam ROOT (`hrdb_run_*.root`) is not
staged on LUNARC (only the Krakow 1M MC and the derived `s00_selected_b_pulses`
table are). Device/electronics calibration is an operator-bench item, not
something LUNARC can settle.

| Verdict | What is proven (with the number) |
|---|---|
| ✅ **PASS (MC closure)** | combined timing σ68 = **0.089 ns** (4-sensor, clusterB) · CFD σ68 = 0.151 ns · timewalk corrected to slope ≈ 0 · pull \|z\|<1 = 0.683 (exact) |
| ✅ **PASS (MC closure)** | PID p-vs-d AUC = **0.898** (realistic ΔE-E chain, clusterA), 5-fold 0.898 ± 0.01 |
| ✅ **PASS (MC closure)** | ADC = **119.17 ADC/MeV** (digitizer gain, clusterC) · Birks kB = **0.0156 cm/MeV** (per-track) · digitizer-domain Rmax = **0.605 MHz** @0% gate |
| ✅ **VALIDATED (data)** | S00 selected B-stack pulses = **640,737** (CL-001, the single data-pipeline PASS) |
| 🟡 **PARTIAL** | Opticks GPU/CPU parity — CPU `ctest 9/9 PASS`; GPU gather returns null (EventMode/component-save config point) |
| ⛔ **BLOCKED / GATED** | detector timing resolution · canonical Rmax · data-side PID · MV0 gain (GATED) · anomaly/C12 ID · systematic budget |

---

## Figures (each captioned + sourced; machine-readable sidecars alongside)

| ID | File | What it shows |
|----|------|---------------|
| VIS-SYS-001 | `VIS-SYS-001_systematic_budget.png` | Dominant systematics: SiPM/optical-chain nuisance elasticities (clusterD `sipm-p2-001`, 11 knobs; reflectivity 3.48, coupling 0.94, pde_scale 0.89 dominate) + the cross-cutting envelopes not captured by a knob sweep (digitizer gain ±30% CL-013 *envelope, not a CI*; Birks kB span 0.008→0.0156 cm/MeV; geometry/material ~8-10 g/cm² missing upstream from MV3). Right: the one covariance actually computed — the timing 4-sensor residual variance vector with bootstrap 68% CIs (clusterB VIS-TIM-004; off-diagonal was not stored, shown honestly as the diagonal). |
| VIS-SYS-002 | `VIS-SYS-002_uncertainty_coverage.png` | (a) Timing pull coverage vs nominal: observed [0.683, 0.909, 0.979] vs Gaussian [0.683, 0.954, 0.997] — 1σ closes exactly, 2σ/3σ mild under-coverage from the 10.5% non-Gaussian tail. (b) PID grouped-bootstrap (clusterA, block=500 ev): full AUC 0.898 with the 5 pseudo-run folds inside the ±0.01 CI. Caveat: CL-026 — coverage is statistical-only, not total (systematic propagation BLOCKED). |
| VIS-SYS-003 | `VIS-SYS-003_sensitivity_robustness.png` | Headline observables vs each varied cut/model/nuisance, ★ = frozen nominal: (a) timing σ68 vs pickoff (CFD/template/lead → combined 0.089); (b) timing σ68 vs sensor (single ≈0.15, leave-one-out ≈0.10, combined 0.089); (c) PID AUC vs slice (global 0.898 → worst saturated-ΔE 0.029, reported not averaged away); (d) Birks PE/event vs kB (clusterD grid 0.100–0.160 mm/MeV + clusterC fits converted cm/MeV→mm/MeV); (e) ADC/MeV (clusterC 119.17 both species vs MV0 proxy 110 GATED ±30%); (f) pile-up overlap (obs 15.9% vs Poisson 16.5% @1 MHz) + Rmax variants (clusterC 0.605/0.289 MHz ★ vs legacy 3.04 MHz ✗ SUPERSEDED). |
| VIS-REP-001 | `VIS-REP-001_reproducibility_dag.png` | Input → code → config/seed → output → claim DAG, one row per cluster + opticks, colour-coded by PASS_MC / GOVERNED / PARTIAL. Annotated with the origin/main squash-merge commits and PR #s (A #921/`9096345d`, B #918/`96c72ad0`, C #917/`276eb5b1`, D #919/`5367ec7b`, opticks #920/`2c0afcd6`), seeds, and the BLOCKED_DATA strip (raw `hrdb_run_*.root` not on LUNARC). |
| VIS-CLAIM-001 | `VIS-CLAIM-001_claim_dashboard.png` | The 16 headline claims with headline number, evidence class (SIMULATION_RESULT / MC_METHOD_CLOSURE / DATA_MEASUREMENT / BLOCKED_DATA / TRUTH_LEVEL_MC_ONLY / SUPERSEDED …), status colour-coded PASS/GATED/BLOCKED/PARTIAL/SUPERSEDED, and source (cluster PR / ledger ID). Machine-readable twin: `claims_table.csv`. |
| (overview) | `PROJECT_DASHBOARD_OVERVIEW.png` | The single-image executive summary rendered from the same numbers; also embedded in `reports/PROJECT_DASHBOARD.md`. |

### Machine-readable outputs
- `metrics.json` — every headline number with its source-file path (PASS / BLOCKED / SUPERSEDED buckets).
- `provenance.json` — sha256(12) digests of every cluster input file this synthesis read + base commit + claim-ledger row count.
- `claims_table.csv`, `systematic_budget.csv`, `sensitivity_robustness.csv` — the figure data in row form.

---

## Claim status table (canonical — agrees with `docs/claim_ledger.csv`)

| Claim | Headline | Evidence class | Status | Source |
|---|---|---|---|---|
| Selected B-stack pulses (S00 gate) | 640,737 | DATA_MEASUREMENT | ✅ VALIDATED | CL-001 |
| Combined timing σ68 | 0.089 ns | MC_METHOD_CLOSURE | ✅ PASS | clusterB #918 |
| Detector timing resolution (data) | withheld | BLOCKED_DATA | ⛔ BLOCKED | CL-002..006 |
| Pile-up Rmax (canonical) | withheld | BLOCKED | ⛔ BLOCKED | CL-010 (S-STAT-003) |
| Legacy Rmax = 3.044 MHz | SUPERSEDED | SUPERSEDED | 🚫 SUPERSEDED | CL-012 (do not use) |
| Rmax (digitizer domain, 0% gate) | 0.605 MHz | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| PID p-vs-d AUC (realistic chain) | 0.898 | SIMULATION_RESULT | ✅ PASS | clusterA #921 |
| PID p-vs-d AUC (truth ceiling HGB) | 0.986 | TRUTH_LEVEL_MC_ONLY | 🟡 GATED | CL-017 (BLK-MV1-001) |
| PID on beam data | deferred | BLOCKED_DATA | ⛔ BLOCKED_DATA | raw ROOT not staged |
| ADC calibration (digitizer gain) | 119.17 ADC/MeV | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| ADC gain (data/MC proxy, MV0) | 110 ± 30% | DATA_MC_PROXY | 🟡 GATED | CL-013 (BLK-MV0-001) |
| Birks kB (per-track dE/dx) | 0.0156 cm/MeV | SIMULATION_RESULT | ✅ PASS | clusterC #917 |
| Anomaly / C12 identity | 25/38 toy early-peak C12 | TRUTH_LEVEL_MC_ONLY | ⛔ BLOCKED | CL-022 (AUD-ANOM-001) |
| Stopping-depth data/MC closure | χ²/ndf ≈ 8.6e4 FAIL | MC_DIAGNOSTIC | 🟠 TENSION | CL-021 (BLK-MV3-LEGACY-001) |
| Opticks GPU/CPU parity | 0 GPU hits / 4592 CPU | SIMULATION_RESULT | 🟡 PARTIAL | opticks #920 |
| Systematic uncertainty budget | incomplete | BLOCKED | ⛔ BLOCKED | CL-026 (BLK-SYST-001) |

---

## Residue / blockers (carried forward, not hidden)

- **BLOCKED_DATA — raw beam ROOT not on LUNARC.** `hrdb_run_*.root` (data-side ΔE-E, ADC, composite-key join, PID-on-data, data-side timing waveforms) is not staged. The Krakow 1M MC and the derived `s00_selected_b_pulses.csv.gz` are. Until the raw ROOT is staged, every detector-performance claim stays at MC-closure level.
- **Operator-bench — device calibration / measured electronics.** SiPM PDE / reflectivity / coupling, digitizer gain against a pulser, and measured time anchors are bench measurements; LUNARC cannot produce them. The ±30% CL-013 envelope is a heuristic, not a confidence interval.
- **Opticks — GPU gather PARTIAL.** Production GDML ingestion, 4-SiPM annotation, and 148k photons/event upload are proven on the A40; the residual is the device→host GATHER returning null in standalone EventMode (a pipeline configuration point), not a sensor/geometry defect. CPU reference ctest 9/9 PASS.
- **Canonical Rmax definition open** (S-STAT-003). clusterC's 0.605 MHz is a digitizer-domain quality-gate number; it is not a detector capacity until the occupancy-quality threshold is fixed and validated against data.
- **Systematic budget incomplete** (CL-026). Per-claim nuisance model, covariance treatment, hash-bound inputs, and coverage study do not yet exist; component estimates are not blanket authorisation.
- **MV3 stopping-depth TENSION** (χ²/ndf ≈ 8.6e4): missing upstream material budget in the MC geometry; all quantitative MC stopping claims are unreliable until the geometry is fixed and re-run.

*Source: `scripts/clusterE/clusterE_synthesis.py`; inputs `reports/studies/cluster{A,B,C,D}/**`,
`figures/opticks/SUMMARY.md`, `docs/claim_ledger.csv`. Sidecars: `metrics.json`, `provenance.json`.*
