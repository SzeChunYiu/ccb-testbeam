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
| 04 | ccb-wt-lane04 | fix/lane04-waveA | Source/weights | #1050-#1058 #1174 #1179 | MERGED (#1240) | #1240 |
| 05 | ccb-wt-lane05 | fix/lane05-waveA | Timing CFD/template | #954 #964-#968 #1003-#1004 #1032-#1033 #1059-#1064 | MERGED (#1239) | #1239 |
| 06 | ccb-wt-lane06 | fix/lane06-waveA | PID ΔE-E | #956 #1022-#1031 #1042 #1048 | IN_PROGRESS | |
| 07 | ccb-wt-lane07 | fix/lane07-waveA | Stats/bootstrap | #958-#960 #1049 #1052 #1097 #1164 #1166 | IN_PROGRESS | |
| 08 | ccb-wt-lane08 | fix/lane08-waveA | DAQ/S00 provenance | #953 #961-#962 #973 #997-#998 #1014 #1073 #1149 | IN_PROGRESS | |
| 09 | ccb-wt-lane09 | fix/lane09-waveA | ARU study scripts | #1112-#1129 #1137 | IN_PROGRESS | |
| 10 | ccb-wt-lane10 | fix/lane10-waveA | Docs/gov/orchestrator | #969-#970 #990 #1002 #1078 #1218 + run_pipeline | MERGED (#1241) | #1241 |

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
| #1067 | FIXED (core) | Measured-impulse fail-closed in pinned core |
| #1068 | BLOCKED | ADR-SIPM-PHYSICS-BLOCKED (normalization/units) |
| #1069 | FIXED | candidate_limit_reached aborts; counters in sidecar |
| #1070 | BLOCKED | ADR-SIPM-PHYSICS-BLOCKED (illumination footprint) |
| #1071 | BLOCKED | ADR-SIPM-PHYSICS-BLOCKED (correlated-noise source-binding) |
| #1072 | FIXED (H1) | OV/T overrides != profile abort; ADR-SIPM-OPERATING-POINT-H1 |
| #1084 | FIXED (label) | Metadata + analyzer: legacy PE = INDEPENDENT_DIAGNOSTIC_DRAW; ADR-SIPM-DUALPATH-H2 |
| #1096 | FIXED (core) | Pre-window history in pinned core (history_start_ns) |

Submodule gitlink aligned with #1243: geant4/single_stave/sipm -> cf12c6b8955c48590bda858477f8dc4ebd67251b.

## Lane 10 wave-A atom status (authoritative for merged #1241)

| Issue | Atom | Decision | Notes |
|-------|------|----------|-------|
| #969 | AF-021/022 public claim authority | FIXED | docs/contracts/PUBLIC_CLAIM_AUTHORITY.json + validator; README front-door synced |
| #970 | AF-TIM-POP-001 selection-flow DAG | FIXED (infra) / BLOCKED (full note regen) | DAG contract + QA tests landed; timing-note regen remains BLOCKED pending immutable input (#952/#962) |
| #990 | AF-042 nature badges | FIXED | Review taxonomy badges + validator; badges no longer unqualified ACCEPTED |
| #1002 | AF-051 compare_data_mc narrative | FIXED | Narrative derived from machine-readable fields; causal claim gated |
| #1078 | ARU-MV0-MODEL-IDENTITY-001 | FIXED (freeze) | Executable MV0 identity frozen; Chapter 10 prose marked DIVERGENT until regenerated |
| #1218 | ARU-GOV-MERGE-CLOSE-KEYWORD-001 | FIXED | Merge-close keyword checker + scientific completion gate policy |
| PR #1236 | SiPM recovery coupling archive | AUDITED (already merged) | Coordination/provenance only; no detector-claim promotion; do not treat as physics close of #1066/#1071 |

### PR #1236 audit (Lane 10; no force-merge)

- State observed at campaign start: already MERGED to main@147a5124.
- Scope: chatgpt_todo/ACTIVE_TASK.md, HANDOFF.md, archive ARU-SIPM-RECOVERY-CORRELATED-NOISE-COUPLING-001.
- Scientific content: records PARTIAL result that parent-generation correlated-noise probabilities remain hard-wired to raw r(dt) under FULL_RECOVERY; does not close #1066/#1071.
- Policy compliance with #1218: acceptable because it did not claim scientific-universe completion for those parents.

## Lane 01 Wave B kickoff

Branch: `fix/lane01-waveB` (rebased onto origin/main after Wave A #1248 merge).

| Issue | Disposition | Note |
|-------|-------------|------|
| #1009 | IN_PROGRESS (fail-closed) | Metadata marks PEAK_ONLY_DISCARDED + daq schema UNSET; no invented HRD Nsamples |
| #1010 | BLOCKED | Needs external CCB electronics impulse evidence |
| #1066 #1068 #1070 #1071 | BLOCKED | Carried from Wave A ADRs |
