# Open atomic issue pickup queue — 2026-08-08

This is the implementation order for issues created by the recursive audit at `main@957c2fd6...`. It is a **dependency queue**, not a claim that all listed hypotheses are already experimentally resolved. Read each issue body before implementation. The machine-readable version is `ISSUE_PICKUP_QUEUE_20260808.csv`.

## Phase 0 — stop-gate data identity and waveform contract

Do these before authorising any timing/PID/light-collection result.

| Order | Issue | Atomic objective | Status on audit branch |
|---:|---:|---|---|
| 1 | #952 | Per-event HRD width/schema gate (16 vs 18) | validator + adversarial tests added; real schema unresolved |
| 2 | #961 | Canonical DAQ event identity (`EVENTNO`/`EVT`/`NO`) | research required on real pipeline |
| 3 | #953 | Exact raw→sorted event/channel/sample closure | exact key-set validator added; ADC-word comparator still needed |
| 4 | #954 | Measured per-channel polarity | blocked on immutable raw/calibration evidence |
| 5 | #993 | Prove 8×16 ↔ 8×18 product lineage | blocked on byte-level pipeline provenance |
| 6 | #971 | Make S00 output conform to pulse-table schema | ready after polarity/amplitude semantics are fixed |
| 7 | #972 | Remove fabricated skip-sorted crosscheck; authorising exit must require integrity gates | ready |
| 8 | #973 | Make checksum/provenance logic consistent with missing sorted inputs | ready |
| 9 | #983 | Reject overlapping exclusive run roles | validator + tests added; wire into config loaders |
| 10 | #962 | Canonical run ledger; resolve run 61 vs 64 calibration | needs acquisition metadata |
| 11 | #1004 | Timing loaders must fail authorising runs on unexpected missing/empty requested inputs | ready |

### Gate to leave Phase 0

A machine-readable release record must show `PASS` for schema, canonical key/domain, raw→sorted closure, channel/stave map, polarity, last-channel survival, run ledger, requested-run completeness and immutable hashes. Missing checks are `NOT_RUN/BLOCKED`, never copied reference values.

## Phase 1 — quarantine/recompute claims that depend on Phase 0

| Issue | Objective |
|---:|---|
| #955 | Reclassify CL-001 so exact count reproduction is not confused with waveform/channel validation |
| #956 | Recompute the real-data ΔE–E proxy exactly as #618 defines before causal data/MC claims |
| #970 | Rebuild the timing note from one immutable selection-flow DAG; reconcile Table 3/4 populations |
| #969 | Generate public data/claim status from one machine-readable authority |
| #994 | Give every ADC/MeV quantity a truth-type/estimator-specific identity |
| #990 | Separate reviewer/editorial acceptance from source/reproduction/claim authorization |
| #1002 | Generate numerical/causal data/MC narrative from validated outputs rather than hard-coded prose |

## Phase 2 — detector hardware, material and geometry truth

These issues should be worked as one evidence campaign but remain individually testable.

| Issue | Objective |
|---:|---|
| #869 | Complete physical layer ↔ DAQ/readout mapping (existing supervisor issue) |
| #987 | One-fibre vs two-fibre CCB hardware truth |
| #991 | ~1 m beam-test stave vs 50 cm Geant4 stave |
| #992 | 2 cm vs 4 cm analysed-stave spacing |
| #1000 | Resolve actual scintillator material; stop treating BC-408 as polystyrene-equivalent without evidence |
| #986 | Canonical separate geometry/optical/physics/digitizer digests |
| #844 | Geometry/material budget closure and nuisance scans (existing supervisor issue) |
| #879 | Quantify readout parity/missing-stave censoring (existing supervisor issue) |
| #999 | Geometry-aware primary ray-intersection/entry preflight for MC scans |

**Required artifact:** one source-bound hardware/material ledger (CAD/build/measurement/photo/run-log/manufacturer evidence with uncertainty) from which geometry, materials, layer distances, MC masks and documentation are generated.

## Phase 3 — optical/SiPM/electronics simulation correctness

### Direct fixes already prepared

- #975: invalid core config/runtime digitizer errors now fail closed in `EventAction.cc` on the audit branch.
- #976: env overrides are strictly parsed; zero DCR/crosstalk/afterpulse controls are effective; integration regression added.
- #978: calibration SLURM driver now explicitly uses `--strict-optical`.
- #996: shared action/PDE optical-table load now obeys strict mode and requires `sipm_pde` before event generation.
- #998: required Geant4 UI/macro command failures now produce nonzero status.

### Remaining simulation blockers

| Issue | Objective |
|---:|---|
| #974 | Make cell-count/systematic reach the production microcell/ADC model |
| #977 | Persist full effective ccb-sipm-core/electronics config and digest |
| #997 | Persist hit position, angle, WLS profile and every response-defining requested/effective config field |
| #980 | Make optical-table validation semantic (units/ranges/malformed rows), not merely structural |
| #981 | One PDE source + one extrapolation policy for legacy/control and ADC paths |
| #979 | Move hard-coded scintillator/WLS optical constants into a sourced property ledger |
| #982 | Analyzer must verify requested vs effective run metadata, not trust filename labels |
| #984 | Paired multi-seed nuisance sweeps / common-random-number design |
| #985 | Replace universal global linear slope with local/asymmetric nonlinear response treatment |
| #998 | Add BeamOn/event-count/macro-hash completion postcondition beyond command-status check |
| #885 | Full single-stave p/d response surface + digitized waveform outputs (existing supervisor) |
| #880 | MC weight provenance, ESS and weighted statistics everywhere (existing supervisor) |
| #1001 | Make public data/MC comparison fail closed on MC weights and use a weight-aware distribution test |

## Phase 4 — timing inference after waveform/geometry gates

| Issue | Objective |
|---:|---|
| #963 | Replace positivity-forced pedestal validation with identifiable baseline model |
| #964 | Rank/condition/predictive audit of the high-dimensional v4 waveform description |
| #965 | Treat `qtemplate` as heuristic until held-out threshold/transport calibration |
| #967 | Species/energy/path-aware TOF uncertainty instead of a fixed 100 MeV proton only |
| #966 | Mixture/covariance-aware timing resolution; separate core width from tails/common jitter |
| #1003 | Quantify timing-selection bias from peak-sample preselection; publish unconditional and conditional residuals |
| #968 | Mechanism-neutral B2 broad-residual study before 'pile-up-like' microscopic wording |
| #988 | Remove/rederive the blocked 3.05 MHz pile-up-rate claim |

## Phase 5 — p/d interpretation, calibration and PID

| Issue | Objective |
|---:|---|
| #989 | Reconcile ~105 MeV elastic-deuteron kinematics with ~15.8 MeV fitted 'deuteron-like' scale; correct PSTAR misuse |
| #956 | Correct event-level data ΔE/residual-E definition and weighted MC comparison |
| #879 | Treat unobserved alternating layers as a censoring/systematic matrix |
| #887 | Threshold selection as a held-out selection-function study |
| #994 | Keep incident/deposited/visible/reconstructed energy and ADC conversions truth-type explicit |
| #1000 | Recompute transport/range response using the actual scintillator material |

A relativistic p+d elastic kinematics tool and tests are already present on the audit branch. Only after these physics/data gates close should an event-level proton/deuteron performance number be promoted.

## Phase 6 — statistical/ML estimand repair

| Issue | Objective |
|---:|---|
| #958 | Include the second class-cap inclusion probability or simplify sampling design |
| #959 | FIXED (#1245): group-aware weighted ML selection/calibration; fail-closed when weights unset |
| #960 | Bootstrap the same weighted estimand; failures cannot become zero-width CIs |
| #961 | Use the canonical DAQ event identity for folds/bootstrap/join grouping |
| #1001 | Reuse one MC-weight contract for weighted data/MC tests and uncertainty |

## Nature-style role assignment for every issue

Each AI session performs four explicit passes before proposing closure:

1. **Domain/physics lead** — define the measurand and contract.
2. **Adversarial reviewer** — construct the strongest alternative mechanism/counterexample.
3. **Independent validation/statistics reviewer** — specify held-out data, weights, uncertainty and negative controls.
4. **Claims/provenance reviewer** — identify every report/wiki/claim/figure that must change.

These are role-separated AI review lenses, not independent human reviewers. The public `nature-reviewer` skill requires genuine context isolation before reports can be called mutually blind; this runtime does not provide that isolation, so the project must not make that claim. Academic search should follow the public `nature-academic-search` T1→T2→T3 routing and verify DOI/source metadata before using a literature value as evidence.

## Pickup rule

- Prefer a leaf whose dependencies are already `PASS`.
- If blocked on an external artifact, record the exact missing byte/hardware/run record and take the next unrelated ready leaf.
- Work out the method and executable falsifier **before** adding prose.
- Preserve negative results; do not repeatedly rediscover a failed hypothesis.
- Close an issue only with commit SHA, test commands/results, immutable input/output hashes where applicable, residual limitations, and the next unlocked child issue.
- After closing a leaf, recurse into every assumption introduced by its fix and open only independently actionable child issues.

See `ATOMIC_RESEARCH_PROTOCOL.md`, `AI_SESSION_PICKUP_GUIDE_20260808.md`, `CURRENT_ATOMIC_FINDINGS_20260808.md`, `CURRENT_ATOMIC_FINDINGS_ADDENDUM_20260808.md`, `LITERATURE_AND_METHOD_MAP_20260808.md`, and `ISSUE_PICKUP_QUEUE_20260808.csv`.