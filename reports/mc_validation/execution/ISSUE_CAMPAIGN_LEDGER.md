# ISSUE CAMPAIGN LEDGER — Current (2026-08-12)

Main HEAD: `d32d2183` ("docs(audit): record compiled SiPM core provenance integration (#1281)")
Submodule gitlink: `3627dc87137a9f33f511a755671414b11853c0a0`
Access: `ssh billy-old` -> `ssh lunarc`
Python: `/projects/hep/fs10/shared/nnbar/billy/packages/hibeam_env/bin/python3`
MC ROOT: `geant4/data/output_krakow_1M.root` (present)

## Wave completion summary

All 4 waves (A, B, C, D) complete across all 10 lanes. Not every lane required every wave — some issues were resolved in earlier waves.

| Lane | Theme | Wave A | Wave B | Wave C | Wave D |
|------|-------|--------|--------|--------|--------|
| 01 | SiPM/digitizer fail-closed | #1248 | #1254 | #1261 | #1268 |
| 02 | Optical/WLS/material | #1246 | #1257 | — | #1269 |
| 03 | Geometry/kinematics | #1237 | #1255 | — | #1270 |
| 04 | Source/weights | #1240 | #1258 | — | #1271 |
| 05 | Timing CFD/template | #1239 | #1249 | #1263 | #1272 |
| 06 | PID ΔE-E | #1238 | #1256 | — | — |
| 07 | Stats/bootstrap | #1245 | #1252 | #1265 | — |
| 08 | DAQ/S00 provenance | #1244 | #1253 | #1260 | — |
| 09 | ARU study scripts | #1242 | #1251 | #1264 | — |
| 10 | Docs/gov/orchestrator | #1241 | #1247 | #1262 | #1273 |

## Merged PR inventory (post-Wave-D, most recent first)

### Post-wave standalone PRs
| PR | Title | Commit | Issues |
|----|-------|--------|--------|
| #1278 | fix(timing): expose first-local selector identifiability limits | 5b7312e8 | — |
| #1277 | test(timing): quantify first-local selector nuisance sensitivity | de51f1a9 | — |
| #1276 | fix(sipm): repin conflict-free core and execute gitlink in required CI | 896c6c0b | #1067 (gitlink) |
| #1275 | feat: add machine-readable Nuisance contract to data↔MC comparison (#1166) | ca1c32ae | #1166 (nuisance topology) |
| #1273 | fix(aru): Wave D Lane 10 lock #1126 fail-closed torch identity | 0461d858 | #1126 |

### Wave D
| PR | Lane | Title | Commit |
|----|------|-------|--------|
| #1272 | 05 | fix(timing): Wave D Lane 05 chord TOF surrogate non-authorising | 50234506 |
| #1271 | 04 | fix(source): Wave D Lane 04 dedx provenance headers BLOCKED | 14820660 |
| #1270 | 03 | fix(geometry): Wave D Lane 03 spacing TOF gate BLOCKED | a9217e81 |
| #1269 | 02 | fix(mc): Wave D Lane 02 Geant4 UI fail-closed contract | e7de24a1 |
| #1268 | 01 | fix(s00): Wave D Lane 01 authorising snapshot contract | f425ede3 |

### Wave C
| PR | Lane | Title | Commit |
|----|------|-------|--------|
| #1265 | 07 | fix(stats/calib): Wave C lane07 track-scope, Birks, provenance, step gates | 6c52246b |
| #1264 | 09 | fix(lane09): Wave C Birks/template/primary-track contracts + BLOCKED ADRs | 8fbdad36 |
| #1263 | 05 | fix(response): Lane 05 Wave C Birks/step/primary/hash/grid contracts | bdaf0498 |
| #1262 | 10 | fix(lane10): Wave C completion-gate + provenance/pipeline contracts | bdbe0c15 |
| #1261 | 01 | fix(sipm): Wave C Lane 01 fail-closed polarity + light-collection gates | ba7e9f75 |
| #1260 | 08 | fix(lane08): Wave C Birks/geometry/timing fail-closed contracts | ec69cb0b |

### Wave B
| PR | Lane | Title | Commit |
|----|------|-------|--------|
| #1258 | 04 | fix(mc): Lane 04 Wave B — stopping/Birks/digest/stage/weight contracts | 04a17fda |
| #1257 | 02 | fix(optical/provenance): Wave B Lane 02 digests, quenching hypothesis, I885 probes | 59f25ba1 |
| #1256 | 06 | fix(mc): Lane 06 Wave B stop-depth H3 + transport BLOCKED gates | 7ca1618c |
| #1255 | 03 | fix(mc): Wave B Lane 03 fail-closed physics/config/estimator contracts | 0e08ff78 |
| #1254 | 01 | fix(sipm): Wave B fail-closed waveform/DAQ schema unset | f15aac41 |
| #1253 | 08 | fix(digitizer): Lane 08 Wave B fail-closed config and stage-graph | 0c408925 |
| #1252 | 07 | fix(stats/mc): Wave B lane07 stopping-depth and nuisance-sweep contracts | 03f5726c |
| #1251 | 09 | fix(lane09): Wave B electronics/baseline/RNG/I885 phase-space contracts | 75b80839 |
| #1249 | 05 | fix(response): Lane 05 Wave B Birks/material/window hypotheses + digitizer preflight | e43a3940 |
| #1247 | 10 | fix(lane10): Wave B fail-closed trigger/digitizer + paired multi-seed sweeps | e52d4dfb |

### Wave A
| PR | Lane | Title | Commit |
|----|------|-------|--------|
| #1248 | 01 | fix(sipm): Wave A Lane 01 fail-closed digitizer + provenance | e8f4c867 |
| #1246 | 02 | fix(optical): Wave A Lane 02 fail-closed tables + BLOCKED material ADR | f350ad9e |
| #1245 | 07 | fix(stats/data-mc): Wave A lane07 weighted estimands and unit contracts | ac2e0bdd |
| #1244 | 08 | fix(daq/s00): Lane 08 Wave A DAQ/S00 provenance gates | a8e91677 |
| #1243 | — | Update submodule gitlink to ccb-sipm-core cf12c6b (issue #1066) | 8df405a1 |
| #1242 | 09 | fix(aru): Lane 09 Wave A ARU study-script bugs | bb62addc |
| #1241 | 10 | fix(lane10): Wave A docs/gov contracts + LUNARC pipeline hardening | 5a020b61 |
| #1240 | 04 | fix(mc): Lane 04 Wave A — CS parse, weight measure closure, signed diagnostics | 25aed9a5 |
| #1239 | 05 | fix(timing): Lane05 Wave-A CFD/template/selection/polarity contracts | ed1cea48 |
| #1238 | 06 | fix(pid): lane06 Wave A ΔE–E/penetration contract fixes | c80a9ce7 |
| #1237 | 03 | fix(geometry): Wave A Lane 03 hypothesis registry + beam preflight | 82285e5e |

### Pre-wave audit / infrastructure PRs
| PR | Title | Commit |
|----|-------|--------|
| #1236 | docs(audit): record SiPM recovery correlated-noise coupling child | 147a5124 |
| #1235 | fix(sipm): integrate partial trigger/gain recovery separation (#1066) | d9992a48 |
| #1234 | fix(sipm): integrate runtime-kernel provenance binding | e25d59be |
| #1232 | fix(sipm): remove empty-sensor bypass to simulate DCR/noise for all sensors (#1087) | 594bea08 |
| #1231 | fix(sipm): integrate provenance-state quarantine | cf3106f9 |
| #1230 | docs(audit): finalize composed SiPM handoff | 9d8c32e8 |
| #1228 | fix(sipm): restore composed history and measured-impulse semantics | a00dd8a8 |
| #1226 | fix(sipm): degenerate measured impulse fails closed (fixes #1067) | 0800a0ce |
| #1225 | fix(sipm): integrate validated dark-history DCR support | a83d3b64 |
| #1224 | docs(audit): reopen SiPM pre-window history on dark-process support | 0a2e4635 |
| #1223 | Update ccb-sipm-core submodule to 2027b06 (fix #1096 pre-window tails) | fcb246a1 |
| #1222 | audit(mc): bind exec-boundary filesystem namespace state | 37eeb1d2 |
| #1220 | audit(mc): bind exec-boundary cwd across executable image replacement | 8a064b37 |
| #1219 | docs(todo): finalize validated issue-closure governance handoff | 5c1e2eca |
| #1217 | docs(audit): repair scientific issue completion provenance | 31f963ef |
| #1216 | mc(source): implement full-2π azimuth reference (partial #1057) | e76482cf |
| #1215 | audit(mc): bind live cwd without overclaiming initial cwd | 859903ad |
| #1213 | audit(mc): bind Linux procfs argument region | c485d965 |
| #1212 | ci: wire base-freshness gate into MC validation (#1188) | 69678659 |
| #1211 | audit(mc): bind Linux procfs initial environment region | 41a568a7 |
| #1210 | audit(mc): attest loader secure-execution state | d6dc5ab2 |
| #1209 | audit(repo): bind authoring bytes to committed GitHub blobs | 4122dc6d |
| #1208 | audit(mc): co-observe runtime ELF metadata on mapped object FDs | acd1be85 |
| #1207 | audit(mc): attest live executable code pages | a9b7184b |
| #1206 | audit(mc): attest ELF link metadata against runtime mappings | 081ee04b |
| #1205 | docs(todo): hand off validated runtime mapping atom | e99cef64 |
| #1204 | audit(mc): attest live runtime executable mappings | 1b6608b8 |
| #1203 | docs(todo): hand off validated tool-probe binding | 8a0f509f |
| #1202 | audit(mc): bind tool probes to opened executable bytes | 6c7a7429 |
| #1201 | audit(mc): attest CMake-selected Geant4 toolchain state | 1968f735 |
| #1200 | docs(mc): record validated Geant4 build binding | dbb57b46 |
| #1199 | audit(mc): bind Geant4 build inputs to executable identity | 948ea288 |
| #1198 | audit(mc): gate exact external Geant4 overlay provenance | 17349d0a |
| #1197 | docs(todo): hand off CI routing to compiled provenance | 774eda1b |
| #1196 | docs(mc): gate historical Geant4 validation claims | 5646568f |
| #1194 | ci: make required PR validation unfilterable by path | 0a77369c |
| #1193 | docs(todo): hand off source readiness to compiled provenance | e4c924b9 |
| #1191 | docs(todo): hand off source sensitivity to runtime readiness | f181f91e |
| #1190 | research(mc): compose source-node and interpolation sensitivity (#1179) | d4d174d2 |
| #1189 | audit(ci): fail closed on stale PR base ancestry (#1188) | 49797c9f |
| #1187 | research(mc): quantify 190 MeV source interpolation-order sensitivity | 57407692 |
| #1186 | research(mc): bound 190 MeV p-d source uncertainty without inventing covariance | af0c3989 |

## Rules

- Edit only on LUNARC worktrees. Push branches; open PRs to main.
- Do not invent physics numbers. Physics contradictions -> BLOCKED + ADR.
- Fail closed when contracts unset.
- Submodule sipm updates only lane 01.
- #1218: merges must not auto-close issues without ledger evidence. Do not use Fixes/Closes in PR body.
- P0s trump all other work; reject non-P0 progress while P0s are open.

## Closed issues since Wave A

| Issue | Disposition | Evidence |
|-------|-------------|----------|
| #1066 | CLOSED/COMPLETED | Trigger/gain recovery separation integrated via #1235 (ccb-sipm-core cf12c6b), env-override wiring via #1243, confirmed on main@896c6c0b. Submodule gitlink 3627dc87 includes the full recovery-model dispatch. |
| #1067 | CLOSED/COMPLETED | Degenerate measured impulse fails closed via #1226 (ccb-sipm-core), submodule gitlink updated via #1266, confirmed on main@896c6c0b. |
| #1009 | CLOSED/COMPLETED | Wave B Lane 01 (#1254): fail-closed waveform/DAQ schema unset, metadata marks PEAK_ONLY_DISCARDED + daq schema UNSET; no invented HRD Nsamples. |
| #1049 | CLOSED/COMPLETED | Weighted-KS null validated with a design-consistent cluster-bootstrap preserving event-cluster identity, closed via #1245 (staff/stats Wave A lane 07). The unit-weight value-permutation null remains NONAUTHORISING in code; the cluster-identity export contract is now owned by #1164. |

## Open issues (19 total: 8 P0, 10 P1, 1 unlabeled)

### P0 issues

| Issue | Title | Status | Notes |
|-------|-------|--------|-------|
| #880 | Weight | UNLABELED | Original MC weight tracking issue (13 comments). "The MC events have weights. Pls make sure they are properly used. Tack!" — likely parent of weight-related child issues. Needs priority label. |
| #1007 | [MC][STOPPING] `track_len_scint_mm` mixes all non-optical tracks | OPEN | Event Edep/path is not primary p/d stopping power. |
| #1014 | [DAQ][HARDWARE] Chapter names CAEN V1742 but assigns 100 MS/s / 10 ns sampling | OPEN | Identify the actual HRD digitizer. |
| #977 | [MC][PROVENANCE] Run metadata omits effective ccb-sipm-core/electronics config | OPEN | Geant4 sidecar `WriteMetadataSidecar()` does not serialize `ccb::sipm::ModelConfig`. Two runs with identical `.meta.json` can produce different ADC waveforms via env overrides or changed submodule — P0 for reproducible data/MC claims. |
| #1059 | [TIMING][CFD] Global-maximum constant-fraction timing can switch physical pulse components | OPEN | CFD fraction change can switch which pulse component fires. |
| #1073 | [DAQ][ADC] Three incompatible saturation/code-range worlds | OPEN | Resolve before any clipped-waveform MC or DATA claim. |
| #1095 | [MC][STEP-CONVERGENCE] Birks/range response has no explicit step-size convergence contract near Bragg stopping | OPEN | Step convergence contract needed. |
| #1164 | [STAT][DATA-MC] Preserve event-cluster identity for weighted-null calibration | OPEN | Event-cluster identity export needed for weighted-null calibration. Referenced in #1275 nuisance contract as blocker. |

### P1 issues

| Issue | Title | Status |
|-------|-------|--------|
| #958 | [STAT] Correct S00 case-control weights after the second class-specific cap sampling stage | OPEN |
| #959 | [ML] Use group-aware weighted model selection/calibration and forbid silent unweighted fallback | OPEN |
| #960 | [STAT] Make bootstrap uncertainty match the weighted estimand; never collapse failures to zero-width CI | OPEN |
| #968 | [TIMING] Discriminate B2 broad-residual mechanisms before calling the class pile-up-like | OPEN |
| #986 | [MC][PROVENANCE] Geometry hash is non-canonical and omits geometry-changing fields while including Birks physics | OPEN |
| #1047 | [MC][STAT] Fix weighted stopping-depth estimand for stop/escape/censored tracks | OPEN |
| #1077 | [MC][DIGITIZER-GRAPH] Make requested stage list equal the effective execution graph | OPEN |
| #1091 | [MC][NEUTRON-TIME] QGSP_BIC carries an implicit 10 µs neutron tracking-time cut | OPEN |
| #1097 | [STAT][P01] `run_block_bootstrap` discards sampled-run multiplicity | OPEN |
| #1218 | [GOV] Prevent merge auto-close from overriding scientific-universe completion gates | OPEN |

## Priority order for next work

1. **#1164** (P0) — Event-cluster identity for weighted-null calibration. Referenced as blocker in #1275 nuisance contract.
2. **#1059** (P0) — Timing CFD global-maximum component switching
3. **#1073** (P0) — ADC saturation code-range resolution
4. **#1095** (P0) — Step convergence contract near Bragg stopping
5. **#1007** (P0) — track_len_scint_mm track mixing
6. **#1014** (P0) — Hardware digitizer identification
7. **#880** (unlabeled) — Assign priority label, then resolve
8. Remaining P1 issues in title order