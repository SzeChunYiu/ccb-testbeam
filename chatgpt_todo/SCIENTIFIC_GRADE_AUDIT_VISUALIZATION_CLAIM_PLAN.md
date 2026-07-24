# Scientific-Grade Repository Audit, Visualization Blueprint, Claim-Evidence Plan, and AI Handoff

**Repository:** `SzeChunYiu/ccb-testbeam`  
**Planning base:** `main` at `bf295c1e7d295698673ffa7bb4c668c19015df49`  
**Prepared:** 2026-07-23  
**Document status:** implementation plan and audit handoff; not a declaration that the repository is scientifically complete  
**Coordination rule:** this document does not replace or take ownership of the currently claimed `AUD-G4-012` task in `chatgpt_todo/ACTIVE_TASK.md`.

## 1. Executive decision

The repository must remain **preliminary and fail-closed for publication claims** until the P0 defects, claim-ledger contradictions, blocked quantitative figures, and missing end-to-end reruns are resolved. The project has unusually strong documentation intent, but the executable evidence chain is fragmented across many scripts, result directories, registries, and partially blocked artifacts. A reader can currently encounter a `VALIDATED` label even when the authoritative ledger says the confidence interval is blocking, the result source is external or absent, or the canonical packaged implementation is still a skeleton.

This plan has four inseparable goals:

1. remove numerical, software, data-contract, ML-leakage, and simulation loopholes;
2. make every transformation and decision visible with diagnostic plots and machine-readable plot provenance;
3. require every public claim to be generated from immutable data or simulation evidence with uncertainty and acceptance criteria;
4. leave a recursive task system that another AI or human reviewer can execute without guessing the analysis history.

## 2. What was reviewed

- Current repository governance: `chatgpt_todo/README.md`, `MASTER_INDEX.md`, `BACKLOG.md`, `ACTIVE_TASK.md`, `HANDOFF.md`, `CLAIM_EVIDENCE_MATRIX.md`, and `VISUALIZATION_MATRIX.md`.
- Public synthesis and claims: `README.md`, `WIKI.md`, `docs/claim_ledger.csv`, `docs/REPORT_STANDARD.md`, `docs/FIGURE_INDEX.md`, and `paper/figures.yaml`.
- High-impact current-main code: digitizer sampling, truth track construction and PDG utilities, MV1/MV3 study logic, geometry mapping, optical-table loading, and pipeline smoke/validation gates.
- The previous 62-item static audit at commit `0005ed0cb2c06617abd36b3bb1e615497e15832a`, reclassified below so fixed findings are not falsely reported as current defects.
- Primary scientific references from Geant4, NIST PSTAR, Particle Data Group, CERN Analysis Preservation, scikit-learn grouped cross-validation documentation, FAIR principles, bootstrap/ROC literature, and simulation-study reporting guidance.

### Scope boundary

This is a repository and method audit, not a substitute for running the exact ROOT data, Geant4 builds, LUNARC jobs, or detector calibrations. A static audit can prove some code defects and governance loopholes, but cannot validate final numerical physics results. Every item depending on external ROOT files or cluster-only execution remains `BLOCKED_COMPUTE` until exact bytes, commands, environments, seeds, outputs, and hashes are preserved.

## 3. Current-main contradictions and immediate publication blockers

### 3.1 Claim status is not fail-closed

- `WIKI.md` says every number has uncertainty, but the claim ledger marks numerous headline rows `CI_MISSING_BLOCKING`.
- `CL-002` and `CL-003` are labelled `VALIDATED` while their CI state is blocking. `CL-010`, `CL-011`, and `CL-013` also carry unresolved or blocking uncertainty/provenance fields.
- The Wiki confidence legend does not define `PASS`, yet the canonical table uses `PASS` for MV4 raw timing. Status vocabularies differ among the Wiki, study package, figure registry, claim ledger, and orchestration layer.
- `source_commit` and `link_validated` are blank for the listed headline claims, so the public number is not pinned to an immutable code revision and verified source chain.
- A `VALIDATED` claim must therefore be treated as provisional until an automated promotion gate re-evaluates all required fields.

### 3.2 Quantitative figures are mostly not reproducible from the checkout

`paper/figures.yaml` correctly attempts to bind figures to result JSON and tables, but almost every quantitative entry is `EXTERNAL_BLOCKER`. The registry comments state that required analysis results are outside the checkout. Consequently, the paper and Wiki cannot be rebuilt from the repository alone, and the figure registry cannot currently verify the headline numbers it is intended to govern.

### 3.3 Visualization coverage is far below the requested step-by-step standard

The repository-level `VISUALIZATION_MATRIX.md` currently concentrates on a small group of Geant4/PSTAR, issue #885, anomaly, and amplitude tasks. It does not yet enumerate the complete raw-data pipeline, timing chain, pile-up chain, PID chain, ML training/validation, systematic propagation, or final claim-to-figure coverage. `docs/FIGURE_INDEX.md` is a useful filename index, but it lacks input hashes, plot code, exact command, acceptance criterion, uncertainty definition, and claim linkage for each figure.

### 3.4 Current-main code defects confirmed during this review

- Digitizer hit timing still cancels in `integrate_samples`, and a peak-normalized shape is still differenced as if it were a cumulative integral.
- The canonical truth builder still passes unscaled `Sci_bar_Momentum_*` values into a MeV/c kinetic-energy function, discards weights and event/source keys, and equates deepest observed layer with stopping layer.
- PDG helpers still give unknown elementary particles a pion mass and return positive charge for anti-nuclei.
- MV1 still defaults to row-index parity, evaluates a simple threshold on the data used to derive it, and converts model exceptions into `_ml_error` while retaining production status.
- MV3 still substitutes event parity when sample labels are absent, assumes all layers up to the deepest observed layer were occupied, and returns production status.
- Geometry defaults remain incompatible between the four-layer registry and the eight-layer pair mapping.
- Optical CSV loading still fails open on missing directories/files, silently ignores malformed rows, and does not enforce units.
- The smoke gate is still hard-coded `PASS`; production validation still accepts only MV1-MV3 with minimal checks and explicitly treats a synthesis containing `MV4 | BLOCKED` as acceptable.
- The latest audited head had no attached combined status checks, so no repository-hosted CI proof exists for that exact revision.

### 3.5 Previously confirmed Geant4 defects that are now fixed

- Inner and outer fibre claddings now use distinct material instances; preserve a regression that verifies distinct material names and refractive indices.
- Raw and Birks-visible deposited energy are now scored separately through `G4EmSaturation`; preserve a regression showing visible energy is never greater than raw energy and differs for strongly ionising steps.

## 4. Complete carry-forward defect register

The following 62 findings form the recursive audit backlog. `CONFIRMED_PRESENT_ON_CURRENT_MAIN` means the reviewed current file still exhibits the defect. `FIXED_ON_CURRENT_MAIN_RETAIN_REGRESSION` means the original defect was repaired but must remain under test. `REVALIDATE_CURRENT_MAIN` means the issue was confirmed at the older audited revision and must be re-read or dynamically rerun before closure.

| Severity | ID | Subsystem | Finding | Current-main state | Location | Required fix |
|---|---|---|---|---|---|---|
| P0 | DIG-001 | Digitizer | Hit time cancels out in sampling | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/digitizer/sampling.py:28-30 | Use global sample edges independent of hit t0, integrate a causal normalized intensity/CDF over each bin, and test time translation and multi-hit separation. |
| P0 | DIG-002 | Digitizer | Peak-normalized pulse is differenced as a cumulative integral | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/digitizer/scintillation.py:15-31; sampling.py:28-30 | Define an area-normalized intensity or analytical CDF, integrate over bins, require nonnegative contributions and documented captured fraction. |
| P1 | DIG-003 | Digitizer | RNG seed is only the numeric event ID | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/digitizer/pipeline.py:137-161 | Derive independent deterministic streams from a master seed plus source/run/event/channel and use order-independent substreams. |
| P1 | DIG-004 | Digitizer | Missing hit fields silently become zero | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/digitizer/pipeline.py:55-96 | Validate required hit schema and finite physical values; reject malformed hits with contextual errors. |
| P1 | DIG-005 | Digitizer | Clipping flag does not match actual clipping threshold | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/digitizer/electronics.py:39-45 | Define clip_limit=min(adc_ceiling, full_scale), flag at the actual limit with documented equality semantics, and validate config. |
| P1 | DIG-006 | Digitizer | ADC output is always int16 | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/digitizer/electronics.py:32-45 | Restrict supported bit depth or choose dtype by range; reject non-finite input and unsafe ceilings. |
| P1 | DIG-007 | Digitizer | Birks approximation is dimensionally invalid | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/digitizer/birks.py:8-15 | Require step/path length and correct units, or remove the approximation and source visible response from validated Geant4 truth. |
| P0 | TRU-001 | Truth extraction | Momentum units are wrong in canonical track builder | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/truth/track_builder.py:78-82; truth/pdg.py:98-102 | Put momentum units in the branch schema, convert GeV/c to MeV/c exactly once, and add known-kinematics tests. |
| P0 | TRU-002 | Truth extraction | Same GeV/MeV bug in legacy MC analysis | REVALIDATE_CURRENT_MAIN | scripts/mc01_trigger_split_truth.py:223-227 | Use the canonical unit-aware helper and quarantine/regenerate affected outputs. |
| P0 | TRU-003 | Truth extraction | Deepest observed layer is called a stopping layer | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/truth/track_builder.py:84-100; scripts/mc01_trigger_split_truth.py:229-249 | Rename last_observed_layer, derive stopped/censored/escaped/reaction flags from truth, and use censoring-aware range analysis. |
| P0 | TRU-004 | Truth extraction | MC event weights are discarded | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/truth/track_builder.py:27-100; scripts/mc01_trigger_split_truth.py:106-110 | Require a declared weight policy; propagate event/primary weights and report weighted counts, sums of weights, sumw2 and ESS. |
| P1 | TRU-005 | Truth extraction | Track records discard scientific keys | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/truth/track_builder.py:89-101 | Preserve source hash/id, entry index, stable event id, track id, sample flags and weight in every record. |
| P0 | TRU-006 | PDG utilities | Unknown particle masses silently default to pion mass | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/truth/pdg.py:84-95 | Use an authoritative mass table/library and fail explicitly for unsupported particles. |
| P0 | TRU-007 | PDG utilities | Anti-nucleus charge sign is wrong | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/truth/pdg.py:59-70 | Apply PDG sign to nuclear charge and add anti-deuteron/anti-alpha tests. |
| P1 | TRU-008 | Event identity | Stable event ID depends on path spelling | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/truth/event_builder.py:15-18 | Use file content hash plus tree/entry index and retain a longer/full digest. |
| P1 | TRU-009 | Event accounting | Empty truth entries are dropped | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/truth/event_builder.py:50-66 | Retain one row for every tree entry with zero-hit flags so denominators are explicit. |
| P1 | TRU-010 | Trigger classification | Jagged lengths and coincidence values are unvalidated | REVALIDATE_CURRENT_MAIN | src/ccb_mc_validation/truth/trigger.py:39-107 | Validate equal per-event lengths, finite times, legal layer ids and positive finite coincidence windows. |
| P0 | ML-001 | MV1 PID | Simple-cut threshold is trained and evaluated on all data | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/studies/mv1_pid.py:148-154 | Fit threshold on training groups and evaluate only on held-out groups; report paired uncertainty. |
| P0 | ML-002 | MV1/MV2 | Default split is row-index parity | CONFIRMED_PRESENT_ON_CURRENT_MAIN | configs/mc_validation/splits.yaml:3-12; studies/splits.py:44-58 | Require group-aware split keyed by source/event/run; remove production parity modes and test zero group overlap. |
| P0 | ML-003 | MV1/MV2 | Model failures are swallowed as production | CONFIRMED_PRESENT_ON_CURRENT_MAIN | studies/mv1_pid.py:106,132-146; mv2_energy_range.py:88-123 | Fail closed or return FAILED/BLOCKED; validators must reject _ml_error and missing mandatory metrics. |
| P1 | ML-004 | MV1/MV2 | Models are not fully deterministic | REVALIDATE_CURRENT_MAIN | studies/mv1_pid.py:137-144; mv2_energy_range.py:109-117 | Set and record random_state where applicable, pin versions and test reproducible metrics/artifacts. |
| P0 | ML-005 | MV2 features | Public helper includes target `ekin` in feature vector | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/truth/features.py:11-12,28-38 | Separate X and y APIs; prohibit target fields in feature schemas with leakage tests. |
| P0 | MV3-001 | MV3 stopping | Missing labels are replaced by event parity and published as production | CONFIRMED_PRESENT_ON_CURRENT_MAIN | studies/mv3_stopping_depth.py:68-78,109-121 | Block production without real sample labels; parity proxy may exist only in explicitly labelled fixtures. |
| P0 | MV3-002 | MV3 stopping | Occupancy assumes every layer up to the deepest hit was crossed | CONFIRMED_PRESENT_ON_CURRENT_MAIN | studies/mv3_stopping_depth.py:26-33 | Build occupancy from actual per-layer deposits/hits and quantify gaps/efficiencies. |
| P0 | GEO-001 | Geometry mapping | Core modules have incompatible layer-to-stave defaults | CONFIRMED_PRESENT_ON_CURRENT_MAIN | truth/geometry.py:28-43,63-70; studies/mv3_stopping_depth.py:13-23; docs/contracts/GEOMETRY_READOUT_MAPPING_CONTRACT.md:3-35 | Remove defaults from production, require populated geometry contract hash and one canonical mapping. |
| P0 | DATA-001 | Data joins | B-stave joins use only `eventno` | REVALIDATE_CURRENT_MAIN | scripts/data01_sample_split_staves.py:111-124,194-200 | Join on validated composite source/run/event keys, aggregate to one row per key/stave and assert cardinality. |
| P0 | DATA-002 | Stopping data | Baseline is subtracted twice | REVALIDATE_CURRENT_MAIN | scripts/mv3_stopping_v2.py:30-37; mv3_stopping_v3.py:24-28 | Enforce PulseTable contract and use unambiguous net amplitude; quarantine and rerun affected results. |
| P0 | DATA-003 | Stopping data | Sample I selector also matches Sample II in v2 | REVALIDATE_CURRENT_MAIN | scripts/mv3_stopping_v2.py:43-44 | Use exact enum/category matching and add category disjointness tests. |
| P1 | DATA-004 | Legacy scripts | Plot error handler masks the original exception | REVALIDATE_CURRENT_MAIN | scripts/data01_sample_split_staves.py:28,240-243 | Import sys and do not broadly suppress required figure failures; exit nonzero and record traceback. |
| P1 | DATA-005 | Legacy scripts | Unseeded plot subsampling | REVALIDATE_CURRENT_MAIN | scripts/data01_sample_split_staves.py:201-204; mc01_trigger_split_truth.py plotting | Use a configured generator/seed and record selected row/event IDs or use deterministic density plots. |
| P1 | DATA-006 | MC script | Energy-deposit cap is order-biased | REVALIDATE_CURRENT_MAIN | scripts/mc01_trigger_split_truth.py:138,206-207 | Use deterministic reservoir/stratified sampling or streamed weighted histograms with full count accounting. |
| P1 | DATA-007 | MC script | Narrative contains hard-coded physics conclusions | REVALIDATE_CURRENT_MAIN | scripts/mc01_trigger_split_truth.py result note section | Generate interpretations from computed metrics and validated thresholds, or keep them exclusively in reviewed reports. |
| P0 | G4-001 | Geant4 optical | Inner and outer cladding share and overwrite one material singleton | FIXED_ON_CURRENT_MAIN_RETAIN_REGRESSION | geant4/single_stave/src/DetectorConstruction.cc:130-150 | Create distinct material instances with distinct MPTs and test refractive-index ordering. |
| P0 | G4-002 | Geant4 scoring | Raw and 'quenched' energy are identical | FIXED_ON_CURRENT_MAIN_RETAIN_REGRESSION | geant4/single_stave/src/SteppingAction.cc:48-59; RunAction.cc:31-38 | Record raw deposit and a correctly computed visible/quenching observable; verify with Birks scans. |
| P0 | G4-003 | Geant4 optical inputs | Missing or malformed optical tables fail open | CONFIRMED_PRESENT_ON_CURRENT_MAIN | geant4/single_stave/src/OpticalTables.cc:113-176; DetectorConstruction.cc:77-188 | Require named tables, schema, units, monotonic domains and physical ranges; abort production on missing/invalid data. |
| P1 | G4-004 | Geant4 provenance | Geometry hash is implementation-defined and incomplete | REVALIDATE_CURRENT_MAIN | DetectorConstruction.cc:35-47 | Serialize complete canonical geometry/material/surface/readout configuration and hash with SHA-256. |
| P1 | G4-005 | Geant4 config | Numeric parsing is fail-open and range validation is incomplete | REVALIDATE_CURRENT_MAIN | geant4/single_stave/src/AppConfig.cc:61-119 | Use checked parsing with full-consumption/range tests; validate finite angles, positions, scales, Birks, seed and geometry bounds. |
| P1 | G4-006 | Geant4 provenance | Metadata is incomplete and manually JSON-escaped | REVALIDATE_CURRENT_MAIN | geant4/single_stave/src/RunAction.cc:137-167; AppConfig.hh:3-6,21-56 | Use a JSON writer; record every effective option, versions, build flags, physics list, thread count, macro/source/config hashes. |
| P1 | G4-007 | Geant4 physics | Reflectivity fallback can exceed 1 | REVALIDATE_CURRENT_MAIN | geant4/single_stave/src/DetectorConstruction.cc:175-188 | Clamp/validate fallback values and reject nonphysical scales. |
| P0 | VAL-001 | Validation gates | Smoke gate is hard-coded PASS | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/execution/pipeline.py:135-170 | Derive status from every requested study; require critical paths to execute, and never PASS with blocked/error/skipped mandatory tasks. |
| P0 | VAL-002 | Validation gates | Release validation accepts blocked/incomplete science | CONFIRMED_PRESENT_ON_CURRENT_MAIN | execution/pipeline.py:548-650 (validation section) | Validate MV0-MV9 schemas, metrics, uncertainty, weights, hashes and dependency states; reject blockers and errors. |
| P0 | VAL-003 | Validation gates | Plot status depends on file existence, not validation result | CONFIRMED_PRESENT_ON_CURRENT_MAIN | execution/pipeline.py:670-681 | Require validation status PASS and verified result/figure manifests before plotting or promotion. |
| P1 | VAL-004 | Testing | Test API ignores requested scope/strictness | REVALIDATE_CURRENT_MAIN | execution/pipeline.py:423-433 | Implement scope-specific test commands and make strictness affect exit/status. |
| P1 | VAL-005 | Testing | Current HEAD has no CI status/run evidence | CONFIRMED_NO_STATUS_CHECKS_ON_AUDITED_HEAD | GitHub commit 0005ed0c... | Expand workflows and require branch protection/status checks for current HEAD. |
| P1 | CI-001 | CI | Workflow path filters exclude most scientific code | REVALIDATE_CURRENT_MAIN | github workflow mc_validation_ci.yml:3-20 | Trigger on scripts, Geant4, tools, figures, contracts/configs and claim/figure registries; add targeted jobs. |
| P1 | CI-002 | CI | Only Python 3.11 is tested while package declares >=3.9 | REVALIDATE_CURRENT_MAIN | pyproject.toml:7-27; workflow:28 | Test declared versions or narrow requires-python to versions actually supported. |
| P1 | REP-001 | Reproducibility | Dependencies are only lower-bounded | REVALIDATE_CURRENT_MAIN | pyproject.toml:12-27 | Add lock/constraints and container/Apptainer definition; capture complete environment. |
| P0 | PROV-001 | Provenance | Core manifest does not hash outputs or verify them | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/manifest.py:42-99; schemas.py:63-87 | Store output path/hash/size/media/schema and verify existence/content; reject unknown/modified artifacts. |
| P1 | PROV-002 | Configuration | Resolved-config digest omits most resolved scientific settings | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/config.py:182-240,281,302-314 | Hash canonical fully resolved config including defaults, environment expansions and all scientific settings. |
| P1 | PROV-003 | Provenance | Alternative manifest stack degrades validation when jsonschema is absent | REVALIDATE_CURRENT_MAIN | tools/ccbprov/validate.py:20-155 | Make jsonschema mandatory for publication/release validation or implement a complete thread-safe fallback. |
| P1 | STAT-001 | Statistics | Bootstrap routines lack input validation | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_mc_validation/statistics/bootstrap.py:12-45; metrics.py:31-79 | Validate lengths, finite data, 0<alpha<1, n_boot>0, groups and metric outputs; fail with scientific errors. |
| P1 | STAT-002 | Statistics | Row bootstrap ignores run/event clustering | CONFIRMED_PRESENT_ON_CURRENT_MAIN | scripts/01_build_pulse_table_from_root.py:310-316; statistics/bootstrap.py | Resample at the independent unit (run/event/source) and document cluster hierarchy; provide sensitivity comparisons. |
| P0 | S00-001 | S00 ML check | The target is defined by the amplitude feature | CONFIRMED_PRESENT_ON_CURRENT_MAIN | scripts/01_build_pulse_table_from_root.py:61-67,115-168,291-308; tail:41-50 | Remove/relabel as a deterministic implementation check; do not present as independent ML performance. |
| P1 | S00-002 | S00 ML check | Case-control subsampling distorts calibration/prevalence | CONFIRMED_PRESENT_ON_CURRENT_MAIN | scripts/01_build_pulse_table_from_root.py:149-169 | Use representative sampling or inverse-probability weights; report sampling design and population metrics. |
| P1 | PUB-001 | Publication | Legacy figure generator has wrong import path | CONFIRMED_PRESENT_ON_CURRENT_MAIN | scripts/generate_all.py:21-24 | Resolve repo root correctly or remove the legacy path; CI-test clean execution. |
| P0 | PUB-002 | Publication | Legacy figure modules hard-code headline scientific values | CONFIRMED_PRESENT_ON_CURRENT_MAIN | src/ccb_figures/figures/fig20_key_results.py:3-10,28-80 | Delete/quarantine quantitative literal generators; render only from verified result registry. |
| P0 | PUB-003 | Claims | README advertises validated results while canonical implementations are blocked/unimplemented | CONFIRMED_PRESENT_ON_CURRENT_MAIN | README.md:31-38; studies/mv4_timing.py:18-45; mv5_pileup.py:12-29; mv6_representation.py:12-19; mv7_pedestal.py:12-19; mv8_saturation.py:12-19 | Generate claims from one authoritative registry and downgrade/block until exact producing artifacts and acceptance gates pass. |
| P1 | AUD-001 | Audit governance | Inventory audit always exits 0 and is not in CI | CONFIRMED_PRESENT_ON_CURRENT_MAIN | tools/audit/run_repo_audit.py:3-10,56-69 | Add a gating mode/baseline and CI integration; track triage/waivers with expiry and owner. |
| P1 | AUD-002 | Audit coverage | Static auditor is regex-limited and ignores major languages/configs | CONFIRMED_PRESENT_ON_CURRENT_MAIN | tools/audit/audit_repository.py:49-165 | Add AST/dataflow checks, C++/CMake/YAML/notebook/shell auditing and dynamic schema/property tests. |
| P1 | SEC-001 | Execution safety | Scientific script uses shell=True and code-generates unescaped paths | REVALIDATE_CURRENT_MAIN | scripts/s21b_1783656688_10969_21015d93_weighted_source_geometry_audit.py:55-65,92-140,151-186 | Use argv lists, controlled environment and safely escaped/generated macro inputs; validate paths. |
| P1 | DATA-008 | Data governance | Canonical LUNARC data location is still unpopulated/TODO | CONFIRMED_PRESENT_ON_CURRENT_MAIN | DATA.md:8-16 | Populate and verify content-addressed canonical inputs or update manifest to the true canonical immutable store. |
| P1 | REP-002 | Repository hygiene | Generated reports/logs and multiple executable generations coexist | CONFIRMED_PRESENT_ON_CURRENT_MAIN | repository metadata/root inventory; reports/, scripts/ | Define source/result/archive policy, move large immutable artifacts to releases/object store and maintain one canonical entry point per study. |

## 5. Mandatory scientific architecture

### 5.1 One canonical data flow

Every public result must have exactly one canonical path:

```text
immutable input bytes
  -> validated schema and units
  -> explicit selection/cutflow
  -> canonical event/track table with composite keys and weights
  -> traditional and/or ML estimator
  -> grouped uncertainty and systematic propagation
  -> result bundle with acceptance state
  -> plot bundle generated only from the result bundle
  -> claim ledger row generated/validated from the result bundle
  -> Wiki/paper text generated from accepted claim rows
```

Parallel legacy scripts may remain for historical reproduction, but they must be marked `LEGACY_DIAGNOSTIC`, excluded from release, and prevented from writing into canonical result or figure directories.

### 5.2 Canonical result bundle v2

Each study must emit one immutable directory containing:

- `result.json`: estimand, central values, units, statistical and systematic uncertainty, CI method/level, acceptance criterion, verdict, limitations, and upstream blockers;
- `cutflow.csv`: ordered stages with input/output counts and composite-key uniqueness checks;
- `metrics.csv`: fold/run/stave/species/slice-level metrics, not only aggregates;
- `uncertainty.json`: resampling unit, nuisance parameters, covariance matrix, random seeds, convergence diagnostics, and coverage tests;
- `manifest.json`: code commit, dirty state, command argv, fully resolved config digest, environment/container, input and output SHA-256, sizes, schemas, event counts, weights, and timestamps;
- `plot_manifest.json`: one entry per figure with claim IDs, source hashes, plot code, command, axes, units, selections, normalization, binning, uncertainty definition, caption, and acceptance state;
- `claims.json`: claims supported by the bundle, evidence class, allowed public wording, status, limitations, and superseded claims;
- `figures/`: SVG plus PNG for review; PDF for paper-quality plots where appropriate;
- `REPORT.md`: generated skeleton plus human interpretation, following `docs/REPORT_STANDARD.md`.

The manifest verifier must rehash every output and fail if any output is missing, altered, unlisted, or generated from a dirty/unrecorded revision.

### 5.3 Evidence classes

Every claim and plot must use one explicit class: `REPOSITORY_FACT`, `MEASURED_DATA`, `SIMULATION_RESULT`, `INDEPENDENT_CALCULATION`, `LITERATURE_BACKED_FACT`, `ASSUMPTION`, `HYPOTHESIS`, `APPROXIMATION`, or `UNRESOLVED_QUESTION`. Simulation truth must never be promoted to a real-data species identification without a validated transfer study.

## 6. Step-by-step visualization blueprint

The goal is not to maximize plot count. The goal is to make every consequential transformation, model choice, failure mode, and uncertainty visible. Every plot must be generated from a machine-readable source table and registered with an acceptance criterion.

### 6.1 Universal plot contract

Every figure must record: plot ID, study ID, claim IDs, input and source-table hashes, code commit, command, resolved config hash, title, axes and units, sample definition, cutflow counts, bin edges, normalization, weights, uncertainty method, seeds, legend semantics, status, limitations, caption, and output hashes. Color cannot be the only distinction. Any data/MC overlay must state whether MC is weighted and must show ratio or residual panels with uncertainty.

### 6.2 Minimum required plot suite

| Plot ID | Stage/purpose | Required visualization | Acceptance gate |
|---|---|---|---|
| VIS-DATA-001 | Input integrity | File count/size/hash map; missing/duplicate files; run coverage; schema versions | Exact expected file set and hashes; unexplained differences block downstream work |
| VIS-DATA-002 | Raw waveform inspection | Random and stratified waveform gallery by run/stave/sample, including malformed/saturated examples | Selection seed fixed; examples linked to event keys; no cherry-picking |
| VIS-DATA-003 | Baseline extraction | Per-sample baseline distribution, run/stave trend, RMS, autocorrelation, nonstationarity and outlier map | Baseline definition and valid domain displayed; drift thresholds preregistered |
| VIS-DATA-004 | Pulse polarity and amplitude contract | Raw waveform with pedestal, signed peak, net amplitude, area and selected samples annotated | Polarity and formula hash-bound to producer/schema evidence |
| VIS-DATA-005 | Selection cutflow | Waterfall/Sankey plus table of rows/events after each cut, with expected/actual/delta | Composite-key counts close exactly and all rejection reasons sum |
| VIS-DATA-006 | Event-key integrity | Duplicate-key heatmap, join cardinality before/after, cross-run event-number collision plot | All canonical joins one-to-one or explicitly many-to-one; fan-out blocks result |
| VIS-DATA-007 | Run/sample/stave coverage | Counts, livetime proxies, occupancy, amplitudes and saturation by run/sample/stave | No hidden run omission; calibration and analysis runs separated |
| VIS-TIM-001 | Timing pickoff construction | Waveform examples showing CFD/template/fit timing and failure reasons | Algorithms use identical waveform/time units and explicit valid domains |
| VIS-TIM-002 | Timewalk | Raw residual versus amplitude and corrected residual versus amplitude, per stave/run, with fit band | Correction fitted only on training groups; held-out residual slope compatible with zero |
| VIS-TIM-003 | Timing distributions | Full residual histogram, Gaussian core, tails, QQ plot, sigma68, RMS and tail fraction | Report robust and core metrics together; fit goodness-of-fit shown |
| VIS-TIM-004 | Run and topology stability | LORO/run/stave/topology forest plot and covariance matrices with bootstrap intervals | No headline driven by one run; covariance estimator positive semidefinite |
| VIS-TIM-005 | Combined estimator | Weights, correlation matrix, eigenvalues, leave-one-stave-out performance, pull coverage | Combined claim blocked until covariance-aware uncertainty closes |
| VIS-PU-001 | Pulse-tail/live-time definition | Average pulse and uncertainty band; threshold crossings for alternative tau definitions | At least two independent tau estimators and truncation/censoring study |
| VIS-PU-002 | Pile-up occupancy/rate model | Observed/expected overlap versus rate/current, ratio panel, Poisson/dead-time alternatives | Definition of Rmax and quality threshold explicit; no conflation with 5% probability |
| VIS-PU-003 | Two-pulse recovery | Efficiency, bias, RMS and catastrophic-failure rate versus delay, amplitude ratio and rate | Operating point chosen on validation sample; baseline and ML shown on same truth |
| VIS-PU-004 | Window censoring | Recovered tail fraction and Rmax shift versus acquisition window | Censoring systematic propagated to final uncertainty |
| VIS-ENE-001 | ADC response and calibration | ADC/MeV response by stave/species/energy with residual and pull panels | No global calibration accepted when fit goodness-of-fit fails |
| VIS-ENE-002 | Birks/quenching | Visible/raw ratio versus dE/dx or track class; kB scan and data/MC comparison | kB and path-length semantics explicit; nuisance uncertainty retained |
| VIS-ENE-003 | Saturation | Observed ceiling, saturation probability, recovery bias and coverage versus true amplitude | Saturation flag matches actual clipping threshold |
| VIS-STOP-001 | Geometry/material budget | Detector cross-sections plus ray-traced areal-density distributions by trajectory and component | Geometry hash, material table and coordinate mapping fixed before acceptance |
| VIS-STOP-002 | Stopping/censoring | Last observed layer, proven stop, escape, reaction and censored categories by species/energy | Never label deepest hit as stop without truth condition |
| VIS-DE-001 | Delta-E/E data | Hexbin/density and conditional quantiles by sample/stave with event counts | Composite keys and signed amplitude conversion validated; ADC/MeV not mixed |
| VIS-DE-002 | Delta-E/E MC truth | Weighted truth bands by species with efficiency/purity and data overlay | MC weights and geometry contract applied; domain gap shown |
| VIS-PID-001 | PID discrimination | ROC and precision-recall with grouped bootstrap/DeLong intervals; operating-point confusion matrix | Event/run/source-disjoint split; truth-level scope explicit |
| VIS-PID-002 | PID calibration | Reliability diagram, score distributions, purity/efficiency versus threshold and abstention | Calibration evaluated on independent groups; class prevalence stated |
| VIS-PID-003 | PID robustness | Performance by run, stave, energy, topology, saturation, sample and domain | Worst-slice and drift performance reported, not only global AUC |
| VIS-ANOM-001 | Anomaly discovery | Embedding/projection plus reconstruction/error distributions with frozen selection boundary | Discovery and evaluation samples separated; cluster stability quantified |
| VIS-ANOM-002 | Anomaly closure | Injection efficiency, sideband false-positive rate, morphology/rate data-MC comparison | No real-data species claim without independent tag or validated proxy |
| VIS-ML-001 | Dataset split audit | Group overlap matrix, class balance and feature/target provenance graph | Zero event/run/source overlap; target-derived features blocked |
| VIS-ML-002 | Learning curves | Train/validation metric versus independent groups and sample size | Gap and saturation visible; tuning sample separate from final test |
| VIS-ML-003 | Hyperparameter selection | Nested-CV validation surface and selected point, with outer-fold results | No test-set tuning; all scanned configurations recorded |
| VIS-ML-004 | Traditional versus ML | Paired per-fold delta forest/violin with CI and practical margin | ML wins only if grouped CI clears zero and preregistered margin |
| VIS-ML-005 | Leakage controls | Target-shuffle, group-shuffle, event-block nulls with observed statistic | All required nulls compatible with chance and observed result outside null |
| VIS-ML-006 | Calibration and uncertainty | Reliability, residuals, interval coverage and selective-risk curve | Point metrics alone are insufficient |
| VIS-MC-001 | Generator/source validation | Primary spectra, angles, positions and weights versus intended distributions | Weights, Jacobians and generator support documented |
| VIS-MC-002 | Transport validation | Energy loss/range/secondary escape versus NIST/Geant4 calculators with ratio panels | Observable definitions match reference; physics-list/cut dependence shown |
| VIS-MC-003 | Optical validation | Photon generation, WLS, arrival time/wavelength, PDE and PE distributions by sensor | Required optical tables validated and hashed; no fallback production |
| VIS-MC-004 | Thread/seed reproducibility | Same-seed equality, different-seed independence, scaling and ensemble stability | Exact deterministic contract and ensemble thresholds preregistered |
| VIS-MC-005 | Data/MC closure | All calibrated observables with residuals/pulls and nuisance bands | No calibration/tuning on the same distribution used for final closure |
| VIS-SYS-001 | Systematic budget | Nuisance impact bars and covariance/correlation heatmap | Sources derived from reruns/priors; correlations explicit |
| VIS-SYS-002 | Uncertainty coverage | Toy/MC coverage versus nominal level and pull distribution | Coverage acceptable before intervals are trusted |
| VIS-SYS-003 | Sensitivity/robustness | Headline result versus each cut/model/nuisance with frozen nominal point | Reasonable variations do not silently change claim status |
| VIS-REP-001 | Reproducibility DAG | Input-code-config-output-claim graph with hashes and statuses | Every public claim has one complete path; blocked nodes visibly propagate |
| VIS-CLAIM-001 | Claim dashboard | Claim status, evidence class, CI/provenance completeness, source and figure links | Public Wiki generated only from rows passing all gates |

### 6.3 Plot-level tests

- Source-table hash in the plot manifest must match the table on disk.
- Renderer reruns must be deterministic or record the random seed and acceptable image/content differences.
- Axis units must be machine-checked against metric units.
- Log axes require strictly positive data and explicit zero/negative handling.
- Ratio/pull plots must use the same binning and selection on both operands.
- Captions must be generated from the same result keys used to draw the figure.
- A figure cannot be `VALIDATED` if its claim is `BLOCKED`, `FLAWED`, `SUPERSEDED`, or missing uncertainty.
- Illustrative/synthetic figures must be visually and textually labelled and stored separately from quantitative evidence.

## 7. Claim-evidence promotion gate

A claim may enter `README.md`, `WIKI.md`, academic chapters, or the paper only when all conditions pass:

1. exact input bytes and schemas are available or preserved in an approved external store;
2. the producing code commit, resolved configuration, environment and command are immutable;
3. event/track keys, weights, units and selection are validated;
4. the estimand and evidence class are explicit;
5. central value, statistical uncertainty, systematic uncertainty and confidence level are complete or a documented reason makes uncertainty inapplicable;
6. grouped resampling or an appropriate analytic interval reflects the actual dependence structure;
7. model selection and final evaluation use independent groups;
8. all upstream P0 dependencies and geometry/data-contract blockers are closed;
9. source report, script, config, data, manifest, figure and table paths exist and hashes verify;
10. output files are hashed and reverified;
11. a reviewer-facing plot bundle shows the result, controls, residuals, stability and failure modes;
12. allowed public wording and limitations are stored in `claims.json`;
13. an automated test regenerates or validates the Wiki row from the result bundle;
14. no `_ml_error`, `FIXTURE`, `SMOKE`, `NOT_RUN`, `BLOCKED`, `SUPERSEDED`, or unresolved `TENSION` state is promoted as validated.

### Immediate ledger corrections

- Downgrade any `VALIDATED` row with `CI_MISSING_BLOCKING`, a missing source, blank source commit, unresolved blocker, or external-only result to `BLOCKED_EVIDENCE` or the appropriate narrower truth status.
- Replace free-form status values with one versioned enum used by code, ledger, figure registry and Wiki.
- Split `scientific_status` from `artifact_status`: a scientifically supported result can still be unavailable locally, and a present artifact can still be scientifically invalid.
- Add `evidence_bundle_sha256`, `result_schema_version`, `review_commit`, `reviewer`, `last_verified_utc`, and `allowed_public_wording` fields.
- Generate the Wiki result table from the ledger; do not maintain numbers by hand in multiple documents.

## 8. Implementation work packages

| Package | Priority | Scope | Main deliverables | Acceptance criteria |
|---|---:|---|---|---|
| PLAN-P0-001 | P0 | Freeze claim promotion | Release gate that rejects blocking CI/provenance/status and external-only quantitative claims | Current public tables cannot pass while ledger contains blocking fields |
| PLAN-P0-002 | P0 | Repair digitizer mathematics | Causal bin-integrated pulse model, global sample clock, charge normalization, validation suite | Time shift changes waveform correctly; multi-hit separation preserved; nonnegative/conserved response within stated model |
| PLAN-P0-003 | P0 | Truth schema and units | Versioned ROOT branch units, GeV-to-MeV conversion, event/source/track keys, weights, censoring labels | Known kinematic fixtures match analytic energies; no record loses traceability or weight |
| PLAN-P0-004 | P0 | PDG correctness | Authoritative mass/charge lookup or explicit unsupported-particle failure | Neutron/photon/muon/kaon/anti-nucleus tests pass; no silent pion fallback |
| PLAN-P0-005 | P0 | Grouped ML evaluation | Event/run/source-disjoint registry, nested tuning, weighted metrics, fail-closed exceptions | Zero group overlap; threshold and ML evaluated only on held-out groups; errors produce FAILED/BLOCKED |
| PLAN-P0-006 | P0 | MV3 and geometry contract | Populate deployed geometry/readout contract; remove parity proxies; distinguish stop/escape/censor/reaction | No production MV3 without real sample labels and validated mapping/material budget |
| PLAN-P0-007 | P0 | Data join and amplitude contracts | Composite keys, cardinality validators, signed polarity conversion, exact sample categories | All joins validate cardinality; stopping bins close to physical-event count; no double subtraction |
| PLAN-P0-008 | P0 | Geant4 production input validation | Required optical tables/units/ranges, config parsing, stable complete metadata and geometry hash | Missing/malformed table or invalid numeric option aborts before run; metadata round-trips |
| PLAN-P0-009 | P0 | Orchestration and release gates | Status aggregation across MV0-MV9, output hash verification, blocker propagation | Any blocked/failed/error/missing uncertainty prevents PASS, plotting promotion and release |
| PLAN-P0-010 | P0 | Canonical result/plot bundle | Implement bundle v2 and migration adapters | Every accepted study has complete machine-readable evidence and deterministic figure build |
| PLAN-P1-001 | P1 | Full visualization matrix | Register every required plot above and map to claims/studies | No material transformation or headline claim lacks diagnostics and acceptance plot |
| PLAN-P1-002 | P1 | Recursive inventory | Enumerate every report, script, config, notebook, figure, table, claim and dataset with stable IDs | `MASTER_INDEX.md` reaches item-level coverage; directory counts alone never marked complete |
| PLAN-P1-003 | P1 | CI expansion | Python matrix, ruff/type/schema/property tests, script compilation, CMake/CTest, figure/claim gates | Any relevant source/config/docs change triggers appropriate checks; audited head has status evidence |
| PLAN-P1-004 | P1 | Reproducible environments | Lock dependencies; container/Apptainer definition; environment capture | Clean rebuild reproduces tests and deterministic fixtures from documented commands |
| PLAN-P1-005 | P1 | Wiki/paper generation | Generate tables/captions/links from accepted registry and evidence bundles | No hand-entered quantitative literals in public figures or headline tables |
| PLAN-P1-006 | P1 | Repository hygiene | Separate source, immutable evidence, caches/builds and external large data | No tracked build products; one canonical script per study; archival outputs clearly immutable |

## 9. Required tests by subsystem

### Digitizer
- time-translation and sub-sample phase tests; multi-hit separation; causality; non-negativity; integrated light/energy normalization; pedestal/noise applied once; saturation-mask threshold equality; dtype/range validation; event-channel-run RNG independence; invalid hit fields rejected.

### Data and truth
- ROOT branch presence, jagged-length equality, unit metadata, finite values, composite-key uniqueness, event denominator preservation, weight propagation, known relativistic-energy fixtures, stop/escape/censor/reaction truth, and deterministic source IDs based on content hash rather than path spelling.

### Statistics and ML
- grouped split disjointness, target-column prohibition, nested model selection, deterministic estimators, weighted and unweighted metric comparison, class prevalence, DeLong/grouped-bootstrap AUC interval, Wilson interval for efficiencies/purities, calibration/coverage, missing-class folds, small-sample behavior, invalid alpha/bootstrap counts, and exception-to-status propagation.

### Geant4
- clean build and CTest; unique materials and optical indices; required CSV schema/units/domain; stable geometry fingerprint from serialized constants and source/config hashes; same-seed thread invariance; different-seed independence; visible <= raw energy; energy conservation including secondaries; physics-list/cut variation; metadata JSON escaping and completeness.

### Provenance and release
- resolved-config digest changes for every scientific setting; output mutation/missing-file detection; dirty-tree handling; schema validation with mandatory `jsonschema`; blocked/error fixtures; claim-to-source link validation; figure source/caption consistency; Wiki generation diff; no literal headline constants.

## 10. New scientific studies and improvements

### Detector and simulation
1. Populate the deployed geometry contract from ROOT/VGM/Geant4 coordinates, copy numbers, surveyed dimensions and DAQ labels; ray-trace areal-density distributions for actual trajectories.
2. Quantify upstream and inter-stave material systematics with controlled Geant4 variations and compare penetration profiles by species and energy.
3. Validate the beam/target source: beam-energy spectrum, target thickness/density, reaction kinematics, angular weights, trigger acceptance and generator Jacobians.
4. Validate optical response against manufacturer tables and measured observables: scintillation yield, WLS absorption/emission, attenuation, coupling, PDE, cell saturation, arrival-time distributions and position dependence.
5. Compare relevant Geant4 physics lists, production cuts and EM options; treat model spread as a systematic only after convergence and data closure.

### Timing
6. Build a covariance-aware B4+B6+B8 estimator with bootstrap covariance, leave-one-stave-out diagnostics and coverage toys.
7. Decompose timing resolution into reference jitter, sampling/quantization, photon statistics, propagation, timewalk, electronics noise and run drift.
8. Compare CFD fractions, analytic timewalk, matched filtering and template likelihood on identical grouped folds; preregister the production metric and practical margin.

### Pile-up
9. Build truth-labelled waveform overlays using real single-pulse templates and independently simulated arrival times; include amplitude ratios, baseline memory, saturation and acquisition-window truncation.
10. Separate probability of an additional hit from reconstruction-quality tolerance; validate dead-time/occupancy models against current or rate proxies.
11. Produce efficiency-bias-failure operating surfaces and select thresholds on validation data only.

### Energy, stopping and PID
12. Measure or constrain per-stave response, Birks quenching, attenuation and saturation rather than using a single global gain.
13. Separate last observed layer, proven stop and censored range; use survival/censoring-aware models where appropriate.
14. Validate PID transfer from MC truth to data using control samples or calibrated weak labels; report purity, efficiency, calibration and abstention, not AUC alone.
15. Perform domain-shift diagnostics and reweighting sensitivity for beam spectrum, geometry, response and trigger selection; never tune on the final closure sample.

### Anomaly analysis
16. Freeze preprocessing and anomaly selection, then measure synthetic-injection efficiency, sideband false-positive rate, cluster stability and matched data/MC morphology/rate closure.
17. Require an independent species tag or validated proxy before identifying a data anomaly as C12.

### Global uncertainty and robustness
18. Build a nuisance-parameter graph and propagate correlated uncertainties to all headline results with toys or profile methods; publish covariance matrices.
19. Run coverage studies for intervals and pull tests for fitted parameters; validate bootstrap resampling units against event/run dependence.
20. Preregister key model families, cuts and acceptance thresholds; preserve a blinded or newly generated final validation sample.

### Software and review quality
21. Add property-based and mutation tests for parsers, joins, units, status promotion and numerical invariants.
22. Use a dependency lock plus container/Apptainer image for laptop and LUNARC reproducibility.
23. Generate an analysis dependency graph and reviewer dashboard from manifests and claim links.
24. Archive accepted evidence bundles in a content-addressed store and expose lightweight hashes/metadata in Git.
25. Require independent reviewer sign-off for claim promotion and preserve reviewer comments/decisions.

## 11. Phased execution order

### Phase A — Stop false promotion
- Implement the claim/figure/release fail-closed gate; synchronize status enums; quarantine hand-entered public values and blocked figures.

### Phase B — Repair foundations
- Fix digitizer mathematics, truth units/weights/keys, PDG logic, data joins/amplitude contracts, grouped splits, MV3 proxies, optical input validation and output hashing.

### Phase C — Establish geometry and calibrated simulation
- Populate geometry/material/readout contracts; rerun clean Geant4 validation; freeze input tables and response model; quantify physics-list/material/optical systematics.

### Phase D — Rebuild canonical data and MC products
- Reproduce S00 from exact raw ROOT; regenerate event/track tables and MV0-MV9 bundles; no downstream reuse of quarantined artifacts.

### Phase E — Build complete diagnostic plot bundles
- Generate all plots in section 6 from source tables; run plot-level tests; have a domain expert review every failure mode and caption.

### Phase F — Re-audit claims and regenerate documentation
- Validate ledger rows, generate Wiki/paper tables and captions from accepted claims, record superseded history, and publish a clear open-blocker dashboard.

### Phase G — Independent replication
- A second environment/session reruns the exact commands from immutable inputs, compares output hashes or tolerance-qualified arrays, and signs the final evidence bundle.

## 12. AI-session handoff protocol

A future AI session must:

1. read all required `chatgpt_todo/` coordination files and recent session logs;
2. never overwrite another active task; choose one dependency-resolved package and record exact ownership;
3. pin the starting `main` SHA and inspect concurrent work before changing files;
4. state whether each assertion is repository fact, data result, simulation result, calculation, literature fact, assumption or hypothesis;
5. reproduce the defect with a minimal test before fixing it;
6. add fail-closed regression tests and, when relevant, diagnostic plots showing old versus corrected behavior;
7. do not alter final numerical results without rerunning exact data/MC and updating all dependent claims, plots and reports;
8. record commands, environment, seeds, inputs/outputs and hashes;
9. update `BACKLOG`, `MASTER_INDEX`, `CODE_RESULT_MAP`, `STUDY_REVIEW_LEDGER`, `CLAIM_EVIDENCE_MATRIX`, `VISUALIZATION_MATRIX`, `BLOCKERS`, `SESSION_LOG`, `HANDOFF`, and an immutable archive record only after evidence exists;
10. leave unresolved items explicitly `PARTIAL` or `BLOCKED`; never convert absence of evidence into `PASS`.

## 13. Definition of scientific completion

The repository-wide task is complete only when every identifiable study, script, config, dataset, simulation, figure, table, claim and Wiki section has a stable ID and evidence-backed state; every accepted result can be reproduced from immutable inputs with a clean environment; every material transformation is visible in registered diagnostics; all uncertainties and correlations are propagated; all public text is generated from accepted claim records; and an independent rerun confirms the evidence chain. Directory counts, passing unit tests, attractive figures, high AUC, or a plausible physics narrative are not sufficient.

## 14. Scientific and reproducibility references

| Reference | Link | Project implication |
|---|---|---|
| Geant4 Physics Reference Manual and Application Developers Guide | https://geant4.web.cern.ch/docs/ | Use for electromagnetic/hadronic transport, G4EmCalculator, Birks/G4EmSaturation and simulation model definitions. |
| Geant4 Birks Quenching documentation | https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/birks.html | Quenching is a nonlinear conversion from deposited energy to observed signal and must not be confused with raw stopping power. |
| NIST ESTAR/PSTAR/ASTAR documentation | https://physics.nist.gov/PhysRefData/Star/Text/readme.html | PSTAR provides proton electronic, nuclear and total stopping powers and ranges using ICRU methods. |
| NIST PSTAR quantity definitions | https://physics.nist.gov/PhysRefData/Star/Text/programs.html | Total stopping power is electronic plus nuclear stopping power; units and material identity must match. |
| Particle Data Group Review of Particle Physics, current edition | https://pdg.lbl.gov/ | Use current particle masses, charges, numbering, passage-through-matter and statistical guidance. |
| PDG Monte Carlo Particle Numbering Scheme | https://pdg.lbl.gov/current/mc-particle-id | Use the maintained PDG/StdHep particle code scheme; do not invent silent mass defaults. |
| scikit-learn grouped cross-validation documentation | https://scikit-learn.org/stable/modules/cross_validation.html | Dependent samples from the same group must not appear in both training and validation sets. |
| CERN Analysis Preservation | https://analysispreservation.cern.ch/docs/general/what.html | Preserve data, software, environment, workflow steps and provenance so HEP analyses remain understandable and reusable. |
| FAIR Guiding Principles, Wilkinson et al., Scientific Data 3, 160018 (2016) | https://doi.org/10.1038/sdata.2016.18 | Make digital research objects findable, accessible, interoperable and reusable with rich metadata/provenance. |
| Efron, Bootstrap Methods: Another Look at the Jackknife, Annals of Statistics 7 (1979) | https://doi.org/10.1214/aos/1176344552 | Bootstrap resampling must reflect the sampling unit and dependence structure. |
| DeLong et al., Comparing correlated ROC areas, Biometrics 44 (1988) | https://doi.org/10.2307/2531595 | Provides a nonparametric framework for uncertainty/comparison of correlated ROC AUCs. |
| Morris, White and Crowther, Using simulation studies to evaluate statistical methods, Statistics in Medicine 38 (2019) | https://doi.org/10.1002/sim.8086 | Use ADEMP: aims, data-generating mechanisms, estimands, methods and performance measures; report Monte Carlo uncertainty and diagnostics. |

## 15. Final handoff statement

The highest-leverage next action is not another headline study. It is to install the fail-closed claim/result/plot architecture and fix the digitizer/truth/grouping foundations. Once those are correct, the data and simulation must be regenerated and every dependent claim re-evaluated. Until then, the Wiki should present the project as an actively audited preliminary analysis with explicit blocked evidence, not as a set of final validated detector-performance measurements.
