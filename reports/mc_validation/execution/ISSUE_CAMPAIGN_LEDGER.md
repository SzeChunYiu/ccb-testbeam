# ISSUE CAMPAIGN LEDGER — Wave A (2026-08-11)

Base commit at lane start: `147a5124`
Rebased onto `origin/main` including #1243 (sipm@cf12c6b) and #1246 (lane02 optical).
Access: `ssh billy-old` -> `ssh lunarc`
Python: `/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3`
MC ROOT: `geant4/data/output_krakow_1M.root` (present)

| Lane | Worktree | Branch | Theme | Issues | Status | PR |
|------|----------|--------|-------|--------|--------|-----|
| 01 | ccb-wt-lane01 | fix/lane01-waveA | SiPM/digitizer fail-closed | #974-#977 #981-#982 #1065-#1072 #1084 #1096 | READY_FOR_PR | https://github.com/SzeChunYiu/ccb-testbeam/pull/1248 |
| 02 | ccb-wt-lane02 | fix/lane02-waveA | Optical/WLS/material | #978-#980 #996 #1000 #1005 #1035-#1036 #1085-#1088 | MERGED (#1246) | #1246 |
| 03 | ccb-wt-lane03 | fix/lane03-waveA | Geometry/kinematics | #987 #989 #991-#992 #999 | MERGED (#1237) | #1237 |
| 03b | ccb-wt-lane03 | fix/issue-986-geometry-hash | Geometry provenance (#986) | #986 | READY_FOR_PR | https://github.com/SzeChunYiu/ccb-testbeam/pull/1292 |
| 04 | ccb-wt-lane04 | fix/lane04-waveA | Source/weights | #1050-#1058 #1174 #1179 | MERGED (#1240) | #1240 |
| 05 | ccb-wt-lane05 | fix/lane05-waveA | Timing CFD/template | #954 #964-#968 #1003-#1004 #1032-#1033 #1059-#1064 | MERGED (#1239) | #1239 |
| 06 | ccb-wt-lane06 | fix/issue-1095-step-convergence | MC step + digitizer graph | #1095 #1077 | READY_FOR_PR | https://github.com/SzeChunYiu/ccb-testbeam/pull/1290 |
| 07 | ccb-wt-lane07 | fix/issue-1164-cluster-identity | Stats/bootstrap | #958-#960 #1049 #1052 #1097 #1164 #1166 | READY_FOR_PR | https://github.com/SzeChunYiu/ccb-testbeam/pull/1291 |
| 08 | ccb-wt-lane08 | fix/issue-1073-saturation-worlds | DAQ/S00 provenance | #953 #961-#962 #973 #997-#998 #1014 #1073 #1149 | READY_FOR_REVIEW | https://github.com/SzeChunYiu/ccb-testbeam/pull/1279 |
| 09 | ccb-wt-lane09 | fix/lane09-waveA | ARU study scripts | #1112-#1129 #1137 | IN_PROGRESS | |
| 10 | ccb-wt-lane10 | fix/lane10-waveA | Docs/gov/orchestrator | #969-#970 #990 #1002 #1078 #1218 + run_pipeline | MERGED (#1241) | #1241 |
| 10b | ccb-wt-lane10 | fix/issue-1218-completion-gate | Gov completion gate | #1218 | READY_FOR_PR | https://github.com/SzeChunYiu/ccb-testbeam/pull/1295 |

## Rules
- Edit only on LUNARC worktrees. Push branches; open PRs to main.
- Do not invent physics numbers. Physics contradictions -> BLOCKED + ADR.
- Fail closed when contracts unset.
- Submodule sipm updates only lane 01.
- #1218: merges must not auto-close issues without ledger evidence. Do not use Fixes/Closes in PR body.

## Lane 01 issue disposition

| Issue | Disposition | Evidence |
|-------|-------------|----------|
| #974 | FIXED | ApplySipmCellCount maps --sipm-n-cells to square cells_x x cells_y; non-squares abort |
| #975 | FIXED | Invalid digitizer config aborts in ctor via validate() / shared builder |
| #976 | FIXED | Strict full-string env parsers; zero probs/rates accepted; trailing garbage rejected |
| #977 | FIXED | .meta.json digitizer block + digitizer_config_sha256 + core metadata JSON string |
| #981 | FIXED | Core PDE from optical/sipm_pde.csv; SteppingAction zero-outside matches core |
| #982 | FIXED | sipm_sensitivity.py joins sidecar; requested!=effective -> non-zero exit |
| #1065 | FIXED (core) | Verified in ccb-sipm-core ancestry through cf12c6b (fractional-delay convolution) |
| #1066 | PARTIAL / BLOCKED | Model knobs + env overrides at cf12c6b (#1243); CCB-true law -> ADR-SIPM-PHYSICS-BLOCKED |
| #1067 | PARTIAL / BLOCKED | Fail-closed numerical child exists upstream, but root #1266 pinned conflicted core `0fc78af...`; repair branch repins validated descendant `3627dc...`. Source-byte/calibration/resampling/run-serialization/historical-output leaves remain unresolved. |
| #1068 | BLOCKED | ADR-SIPM-PHYSICS-BLOCKED (normalization/units) |
| #1069 | FIXED | candidate_limit_reached aborts; counters in sidecar |
| #1070 | BLOCKED | ADR-SIPM-PHYSICS-BLOCKED (illumination footprint) |
| #1071 | BLOCKED | ADR-SIPM-PHYSICS-BLOCKED (correlated-noise source-binding) |
| #1072 | FIXED (H1) | OV/T overrides != profile abort; ADR-SIPM-OPERATING-POINT-H1 |
| #1084 | FIXED (label) | Metadata + analyzer: legacy PE = INDEPENDENT_DIAGNOSTIC_DRAW; ADR-SIPM-DUALPATH-H2 |
| #1096 | FIXED (core) | Pre-window history in pinned core (history_start_ns) |

Historical Wave-A integration aligned the gitlink with #1243 at `cf12c6b8955c48590bda858477f8dc4ebd67251b`. This is **not current-root state**: #1266 later advanced protected main to conflicted `0fc78af...`. `ARU-SIPM-ROOT-GITLINK-EXECUTION-CLOSURE-001` repairs that regression by targeting validated/guarded descendant `3627dc...` and adding exact-gitlink C++ execution to required root CI. Do not mark #1067 COMPLETE from the historical Wave-A row.

## Lane 10 wave-A atom status (authoritative for merged #1241)

| Issue | Atom | Decision | Notes |
|-------|------|----------|-------|
| #969 | AF-021/022 public claim authority | FIXED | docs/contracts/PUBLIC_CLAIM_AUTHORITY.json + validator; README front-door synced |
| #970 | AF-TIM-POP-001 selection-flow DAG | FIXED (infra) / BLOCKED (full note regen) | DAG contract + QA tests landed; timing-note regen remains BLOCKED pending immutable input (#952/#962) |
| #990 | AF-042 nature badges | FIXED | Review taxonomy badges + validator; badges no longer unqualified ACCEPTED |
| #1002 | AF-051 compare_data_mc narrative | FIXED | Narrative derived from machine-readable fields; causal claim gated |
| #1078 | ARU-MV0-MODEL-IDENTITY-001 | FIXED (freeze) | Executable MV0 identity frozen; Chapter 10 prose marked DIVERGENT until regenerated |
| #1218 | ARU-GOV-MERGE-CLOSE-KEYWORD-001 | READY_FOR_PR | PR #1295: `run_close_intent_gates.py` + PR template + full fixture matrix in CI |
| PR #1236 | SiPM recovery coupling archive | AUDITED (already merged) | Coordination/provenance only; no detector-claim promotion; do not treat as physics close of #1066/#1071 |

### PR #1236 audit (Lane 10; no force-merge)

- State observed at campaign start: already MERGED to main@147a5124.
- Scope: chatgpt_todo/ACTIVE_TASK.md, HANDOFF.md, archive ARU-SIPM-RECOVERY-CORRELATED-NOISE-COUPLING-001.
- Scientific content: records PARTIAL result that parent-generation correlated-noise probabilities remain hard-wired to raw r(dt) under FULL_RECOVERY; does not close #1066/#1071.
- Policy compliance with #1218: acceptable because it did not claim scientific-universe completion for those parents.

## Lane 02 Wave B — neutron tracking-time cut (#1091)

Branch: fix/issue-1091-neutron-timecut (worktree ccb-wt-lane02).

| Issue | Disposition | Evidence |
|-------|-------------|----------|
| #1091 | IN_PROGRESS (provenance pin) | --neutron-timecut-policy-id required; /physics_engine/neutron/timeLimit applied post-Initialize; run sidecar records configured 10 us pin (pin_qgsp_bic_default_10us); delayed-neutron claims remain BLOCKED (ADR-0013) |

## Lane 05 timing CFD follow-up (#1059 #968)

Branch: `chatgpt/paper-draft-20260812` (paper PR #1298); software branch `fix/issue-1059-cfd-component` (PR #1289).

| Issue | Disposition | Evidence |
|-------|-------------|----------|
| #1059 | CLOSED | Software binding + measurand docs; beam-data timing format-limited only |
| #968 | PARTIAL (contract) / BLOCKED (physics) | `src/ccb_mc_validation/timing/b2_broad_residual_mechanisms.py` fail-closes microscopic `pile-up-like` wording until AF-020 discriminants are `SATISFIED` |
| #1060 | FIXED | Left-censored crossings report `NO_CROSSING_IN_WINDOW`, never `t=0` |
| #1061 | FIXED | Leave-one-run-out template phase in producer |
| #1062 | FIXED (policy) | Same-sample minimum sigma68 is `SAME_SAMPLE_MINIMUM_EXPLORATORY_ONLY`; not authorising |
| #1063 | FIXED | Canonical `digital_cfd` import path for production timing |
| #993 | CLOSED DISTINCT | 8×16 LUNARC raw authorising; 18-sample historical non-authorising; see `reports/studies/paper_a02_waveform_lineage/` |
| #954 #964 #965 #967 #1003 #1004 #1032 #1033 #1064 | OPEN / carried | Not closed by Lane 05 follow-up |

## Lane 06 MC step + digitizer graph (#1095 #1077)

Branch: `fix/issue-1095-step-convergence` (worktree `ccb-wt-lane06`).

| Issue | Disposition | Evidence |
|-------|-------------|----------|
| #1095 | BLOCKED (infra FIXED) | `configs/transport/step_policy_registry.json` + `require_step_policy` / `authorize_step_convergence_claim` fail closed; ADR-0005 + ADR-0008; `pin_qgsp_bic_inherited_em_stepfunction` claims_authorized=false until convergence digest |
| #1077 | FIXED | `DigitizerPipeline` executes `effective_stages`; run provenance uses frozen `stage_graph_meta`; hidden `integrate_samples` fallback removed; `tests/test_lane06_step_digitizer_graph.py` + lane04/lane08 regressions |

## Lane 07 stats/bootstrap cluster identity (#958 #960 #1097 #1164)

Branch: `fix/issue-1164-cluster-identity` (worktree `ccb-wt-lane07`).

| Issue | Disposition | Evidence |
|-------|-------------|----------|
| #1164 | FIXED (export) | `data01_sample_split_staves.py` exports `run:eventno` cluster IDs fail-closed; `mc01_event_stave_truth.py` publishes `first_B_layer_event_edep.npz` with `generator_event_index` cluster IDs via `build_compare_first_b_event_edep`; `compare_data_mc.py` blocks null calibration without aligned cluster IDs |
| #960 | FIXED | `weighted_cluster_bootstrap` targets IPW estimand; raises `NOT_ESTIMABLE` instead of zero-width CI |
| #1097 | FIXED | `run_block_bootstrap` preserves sampled-run multiplicity (`pulse_weighted` vs `equal_cluster`) |
| #958 | FIXED | `apply_second_stage_class_cap` updates HT weights after per-class cap |
| #1052 #1049 #1166 | FIXED (contract) | Event-unit preference, legacy p-value quarantine, nuisance topology record (base #1245) |

## Lane 01 Wave B kickoff

Branch: `fix/lane01-waveB` (rebased onto origin/main after Wave A #1248 merge).

| Issue | Disposition | Note |
|-------|-------------|------|
| #1009 | IN_PROGRESS (fail-closed) | Metadata marks PEAK_ONLY_DISCARDED + daq schema UNSET; no invented HRD Nsamples |
| #1010 | BLOCKED | Needs external CCB electronics impulse evidence |
| #1066 #1068 #1070 #1071 | BLOCKED | Carried from Wave A ADRs |

## Lane 01 Wave C kickoff — SiPM provenance (#977 / #1067 verify)

| Date | Branch | Tip | Issues | Disposition | PR |
|------|--------|-----|--------|-------------|-----|
| 2026-08-12 | fix/issue-977-sipm-metadata | (see PR) | #977 PARTIAL; #1067 FIXED (core, manual close requested) | Sidecar extended with requested/effective operating point, response_surface_id, electronics impulse hashes, remaining ModelConfig knobs; compile-bound core (#1280) + campaign intent (#1284) unchanged; binary build receipt remains #1285 child | https://github.com/SzeChunYiu/ccb-testbeam/pull/1287 @0371fe3e |