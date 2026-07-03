# CCB Test-Beam — Master Documentation Index

The single entry point to all project documentation. Read top to bottom if you are new; jump to a
section if you know what you want. Confidence labels: ✅ validated (data+MC) / ⚠️ data-only / ❌ corrected.

---

## Start here (read in order)

| # | Document | What it gives you |
|---|---|---|
| 1 | [docs/ANALYSIS_GUIDE.md](ANALYSIS_GUIDE.md) | Orientation: what the experiment is, how to navigate, how to reproduce, how to run a study |
| 2 | [FINDINGS_SYNTHESIS.md](../FINDINGS_SYNTHESIS.md) | The distilled science — every conclusion with confidence label + MC verdict |
| 3 | [PROJECT_REPORT.md](../PROJECT_REPORT.md) | Status dashboard, MC validation table, key-findings ranking, infra, human actions, next steps |
| 4 | [docs/REPORT_STANDARD.md](REPORT_STANDARD.md) | The reporting standard every study must obey (read before writing) |

## The science in depth

| Topic | Document |
|---|---|
| Physics overview | [docs/00_overview.md](00_overview.md) |
| Setup & detector | [docs/01_setup_and_detector.md](01_setup_and_detector.md) |
| Data & runs | [docs/02_data_and_runs.md](02_data_and_runs.md) |
| Pulse reconstruction | [docs/03_pulse_reconstruction.md](03_pulse_reconstruction.md) |
| Timing calibration | [docs/04_timing_calibration.md](04_timing_calibration.md) |
| Timing resolution | [docs/05_timing_resolution.md](05_timing_resolution.md) |
| Pile-up | [docs/06_pileup.md](06_pileup.md) |
| ML methods | [docs/07_ml_methods.md](07_ml_methods.md) |
| A-stack independent-arm check | [docs/08_astack.md](08_astack.md) |
| Open questions & caveats | [docs/09_open_questions.md](09_open_questions.md) |
| Glossary | [docs/glossary.md](glossary.md) |
| References | [docs/references.md](references.md) |
| Full analysis report (long) | [docs/ANALYSIS_REPORT.md](ANALYSIS_REPORT.md) |
| Reviewer-level method trace | [docs/METHOD_LOGIC_TRACE.md](METHOD_LOGIC_TRACE.md) |
| Findings summary (short) | [docs/FINDINGS_SUMMARY.md](FINDINGS_SUMMARY.md) |
| Figure index | [docs/FIGURE_INDEX.md](FIGURE_INDEX.md) |

## Monte-Carlo validation (the truth bridge)

| Item | Document / path | Status |
|---|---|---|
| MC validation architecture | [docs/mc_validation/ADR-0001-mc-validation-architecture.md](mc_validation/ADR-0001-mc-validation-architecture.md) | — |
| MC task ledger | [docs/mc_validation/implementation_status/TASK_LEDGER.md](mc_validation/implementation_status/TASK_LEDGER.md) | — |
| GEANT4 reproduction status | [geant4/REPRODUCTION_STATUS.md](../geant4/REPRODUCTION_STATUS.md) | ✅ built & run |
| MV1 (PID) + MV2 (energy/range) | `reports/mv1_mv2_truth_pid_energy_1782220258/` | ✅ done (AUC 0.986) |
| MC summary (per-layer p/d) | `geant4/results/sim_summary.json` | ✅ |
| Autonomous GEANT4 study plan | [docs/AUTONOMOUS_STUDY_PLAN_GEANT4.md](AUTONOMOUS_STUDY_PLAN_GEANT4.md) | — |
| MV0/MV3/MV4/MV5/MV6 | `geant4/jobs/mv*.sbatch` | ⚠️ staged / queued |

## Evidence & process

| Item | Path |
|---|---|
| Rolling scoreboard (~230 studies) | `reports/SUMMARY.md` |
| Per-study reports | `reports/<id>/REPORT.md` + `manifest.json` + `figures/` |
| Study plan (prioritised) | `studies/STUDIES.md` |
| Standing mistakes / leakage lessons | `fleet/LESSONS.md` |
| Critic / Integrator protocols | `fleet/CRITIC_PROTOCOL.md`, `fleet/INTEGRATOR_PROTOCOL.md` |
| Data location & manifest | `DATA.md` |

---

## State of knowledge at a glance (2026-06-28)

| Domain | Verdict | Confidence |
|---|---|---|
| Data gate (640,737 / 706,373) | exact, reproduced | ✅ |
| Timing | analytic timewalk wins, sigma68 ~1.49-1.55 ns | ⚠️ data-only (MV4 pending) |
| Pile-up | R_max 4.2 -> ~3.05 MHz | ⚠️ data-only (MV5 pending) |
| Amplitude/charge closure | ML wins (res68 0.003-0.009) | ⚠️ data-only |
| Saturation recovery | ML wins (3-7x) | ⚠️ data-only |
| Absolute energy | unreachable from data | ✅ limitation MC-confirmed |
| p/d PID | AUC 0.986 | ✅ validated (data+MC) |
| Representation superiority | leakage | ❌ corrected |
| 4% early-peak anomaly | species unknown | ⚠️ open (MV6) |

When any of these change, update this index, `FINDINGS_SYNTHESIS.md`, and `PROJECT_REPORT.md`
together (see `docs/REPORT_STANDARD.md` section 10).
