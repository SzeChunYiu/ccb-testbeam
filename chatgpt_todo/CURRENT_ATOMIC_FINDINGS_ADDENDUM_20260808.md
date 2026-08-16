# Current atomic findings — recursive addendum (2026-08-08)

Base originally audited: `main@957c2fd6fa5b80233a283e88420631e93ee8cec7`.

This addendum continues `CURRENT_ATOMIC_FINDINGS_20260808.md`. The original AF-006 wording is **narrowed here**: `tools/audit/validate_event_keys.py` is documented as a *join-cardinality* validator, so unique-but-partial key sets do not violate that narrow contract. The gap is misuse of cardinality as pipeline closure; exact key-domain closure is now implemented separately on this branch by `tools/audit/validate_key_set_closure.py` and tracked in #953/#957.

## Data/schema/release control

### AF-023 — S00 producer violates the explicit pulse-table contract (#971)
`docs/contracts/PULSE_TABLE_CONTRACT.md` requires unambiguous `peak_height_adc` semantics and schema binding, while S00 still emits ambiguous `amplitude_adc`. This preserves the root condition behind historical double-baseline subtraction.

### AF-024 — `--skip-sorted` fabricates a raw-count crosscheck and can still exit authorising success (#972)
The skipped branch copies raw selected counts into the sorted-crosscheck object. Missing closure must be `NOT_RUN`, never a synthetic numerical comparison.

### AF-025 — `--skip-sorted` and checksum behavior are inconsistent (#973)
Unless SHA-256 is separately disabled, the checksum stage still tries to hash configured sorted files. Provenance should hash consumed/present inputs and explicitly record missing expected inputs.

### AF-035 — overlapping run groups are silently hidden/last-write-wins (#983)
`configured_runs()` deduplicates with a set; `run_group_lookup()` overwrites duplicate assignments. Calibration/analysis leakage can therefore be created by configuration without an error. A fail-closed validator is implemented on this branch.

### AF-048 — run sidecar omits beam position, angle and other response-defining AppConfig fields (#997)
The position-scan MC cannot be reproduced from the current sidecar alone because `hit_x_cm`, `hit_y_cm`, `theta_deg`, `phi_deg`, WLS profile, strictness and multiple response settings are not persisted. Requested/effective full configuration must be hash-bound.

### AF-053 — real-data CFD timing silently skips missing or empty requested runs (#1004)
`load_waveforms()` logs and continues for missing/empty ROOT inputs. A nominal multi-run result can therefore silently become a different run population. Authorising execution must require exact run-domain completeness or an explicit canonical exclusion policy.

## SiPM/digitizer/optical MC

### AF-026 — `--sipm-n-cells` does not reach the production ccb-sipm-core microcell grid (#974)
The CLI changes the legacy analytical saturation branch but `BuildSipmConfig()` retains the representative core's 60×60 grid. The existing cell-count systematic does not scan the ADC simulator as labelled.

### AF-027 — invalid digitizer configuration previously failed open to zero ADC (#975)
The audited `EventAction` caught configuration and event-simulation exceptions, warned, and continued. This branch removes those fail-open catches: invalid core configuration now aborts before event 0 and runtime simulator errors propagate.

### AF-028 — SiPM env override parser ignored zero controls and accepted trailing garbage (#976)
The audited parser required `v>0` and used `strtod(..., nullptr)`. Thus zero DCR/crosstalk/afterpulse controls in the checked-in grid were ineffective and malformed strings could partially parse. This branch strictly parses all core/current-campaign env overrides and allows physically valid zero controls.

### AF-029 — run sidecar does not persist the effective core/electronics configuration (#977)
Two runs can share current Geant4 metadata while differing in ccb-sipm-core/electronics response through env/profile/submodule changes. Add a canonical digitizer config digest and full effective metadata.

### AF-030 — canonical calibration SLURM path was permissive on optical-table fallback (#978)
The systematic driver already sets strict mode; the calibration driver and direct examples did not. This branch adds `--strict-optical` to `submit_calibration.sh`. Semantic strictness remains incomplete (AF-032).

### AF-031 — response-critical scalar optical constants remain hard-coded (#979)
RINDEX, scintillation yield/time, WLS time constant and cladding indices are outside the versioned optical-table/property ledger. Literature values are priors, not beam-test calibration.

### AF-032 — strict optical validation is not semantically strict (#980)
The parser checks only broad numeric/schema shape: it does not enforce the expected unit strings or property-specific ranges and can silently drop malformed rows. A wrong percent/fraction or length unit can remain authorising.

### AF-033 — duplicated PDE source/extrapolation semantics (#981)
Legacy Geant4 PE branches and core ADC use separate PDE copies. The former endpoint-clamps outside the table; the core returns zero. One source/digest/policy is required.

### AF-034 — sensitivity analysis trusts requested filename labels, not effective simulator metadata (#982)
This is directly unsafe because AF-028 proves requested zero controls could differ from effective defaults. The analyzer also hard-codes ADC clipping from nominal defaults.

### AF-036 — nuisance sweep seed changes with knob value (#984)
One seed per value confounds finite-MC fluctuation with parameter response. Use multiple seed replicates and common-random-number pairing across values where useful, reporting how much stochastic branch divergence preserves the pairing.

### AF-037 — global unweighted linear slope is not a general detector-response systematic (#985)
The analyzer applies one `polyfit` even through saturation/nonlinear regimes. Use nominal-local/asymmetric response surfaces with seed-level uncertainty and clipping diagnostics.

### AF-038 — geometry hash is non-canonical and mixes/omits fields (#986)
It omits geometry-changing fields such as far-end mode/coating/sensor thickness while including Birks, which is physics response, and concatenates values without names/units/schema. Split canonical geometry/optical/physics/digitizer digests.

### AF-045 — `--strict-optical` was bypassed for the shared action-level OpticalTables/PDE (#996)
`main.cc` originally loaded the table instance passed to actions without `cfg.strict_optical`, while `SteppingAction::PdeAt()` has a flat-40% fallback. This branch now loads that instance strictly and requires `sipm_pde` before run-manager construction. AF-032/AF-033 still remain.

### AF-046 — configured primary position/direction is not geometry-intersection validated (#999)
Finite `hit_x`, `hit_y`, `theta`, `phi` values can still launch a particle that misses or travels away from the intended front face. Automated position/angle campaigns need a ray-geometry preflight and executed-entry fraction gate.

### AF-047 — Geant4 UI/macro command failures were ignored (#998)
The audited main ignored `ApplyCommand` status and could return 0 after a missing/broken macro. This branch now makes required UI command errors nonzero. A macro still needs a postcondition proving expected BeamOn/event count.

### AF-049 — BC-408 is modeled as polystyrene rather than source-verified PVT material (#1000)
The repository calls the bars BC-408 but clones `G4_POLYSTYRENE` at 1.06 g/cm³. BC-408 is PVT-based; transport composition/density must be source-bound to the actual CCB bars and the proton/deuteron range study regenerated under the correct material.

### AF-050 — `compare_data_mc.py` can silently discard MC weighting and applies unweighted KS to weighted MC (#1001)
Missing/misaligned/nonpositive weights can fall back to unweighted medians, and the KS branch explicitly uses equal-weight MC values. A weight-aware target/test/uncertainty model is required, with #880 as the central weight audit.

### AF-051 — `compare_data_mc.py` embeds hard-coded numerical/causal narrative (#1002)
Fractions, correlations and “physics effect, not analysis artifact” prose are written as static strings rather than generated from validated results/claim state. Narrative must be rendered from machine-readable outputs and weakened automatically when upstream gates are blocked.

## Hardware/geometry provenance

### AF-039 — one-fibre vs two-fibre beam-test hardware contradiction (#987)
An academic setup chapter describes one Y-11 fibre per bar, while the single-stave MC implements two fibre channels and four endpoint sensors. Resolve from actual CCB hardware evidence before light-collection MC.

### AF-043 — ~1 m beam-test stave vs 50 cm single-stave Geant4 model (#991)
`docs/01_setup_and_detector.md` and the timing note use ~1 m longitudinal propagation; `docs/stave-geometry.md`/Geant4 implement 50 cm. This factor-of-two discrepancy directly changes attenuation and timing.

### AF-044 — 2 cm vs 4 cm analysed-stave spacing (#992)
The timing note uses 2 cm per B2→B4→B6→B8 step; a newer repository setup document says 4 cm and explicitly notes the discrepancy. Build one physical layer ledger and derive TOF/range distances from it.

## Timing and waveform inference

### AF-052 — real-data CFD timing conditions on peak-time agreement before measuring timing (#1003)
The CFD study derives per-stave peak-sample offsets from the same data and retains complete events only when their aligned peak spread is ≤1.5 samples before evaluating the timing residual. Because peak sample and CFD/template phase are correlated timing observables, this is a conditional clean-class result and can suppress topology/timing tails. Publish unconditioned and conditioned distributions, freeze preselection on calibration data, and quantify acceptance-vs-width bias with injection/MC closure.

## Pile-up/rate and nuclear-physics interpretation

### AF-040 — 3.05 MHz `Rmax` headline reuses 0.38 duty factor as `mu_max` (#988)
The claim ledger already blocks/supersedes this interpretation. Recursive source inspection found S10's producer hard-codes `mu_max=0.380` and checks arithmetic, rather than deriving it from event-arrival exposure. The LaTeX chapter must not promote it as measured pile-up tolerance.

### AF-041 — ~105 MeV elastic-deuteron kinematics vs ~15.8 MeV 'deuteron-like' fitted scale (#989)
The project uses incompatible-looking energy quantities without a truth-type reconciliation. A chapter also attributes deuteron range to NIST PSTAR, whose official scope is protons. A branch tool now solves relativistic p+d elastic recoil kinematics and gives ~104.18 MeV for a 190 MeV proton with the outgoing deuteron at 38°; therefore the ~105 MeV elastic scale is plausible and the ~15.8 MeV quantity genuinely needs a different estimator/reaction/material-loss explanation.

## Review governance

### AF-042 — nature-reviewer acceptance badges are not claim authorization (#990)
A chapter marked 'ACCEPTED 3/3' still contains unresolved detector/physics premises. Separate editorial/method review, source verification, executable reproduction and claim authorization; never describe AI role passes as independent human/blind reviewers.

The audit protocol has now been aligned explicitly with the public `Yuan1z0825/nature-skills` methodology. Because this runtime has no isolated review subagents, the project uses role-separated adversarial passes but does not claim the mutually blind reviewer condition required by the upstream `nature-reviewer` skill.

## Direct implementation completed on this audit branch

- fail-closed per-event HRD waveform structural validator + adversarial tests;
- exact composite-key set/domain closure validator + tests;
- exclusive run-group validator + tests;
- strict/fail-closed SiPM env/digitizer initialization in `EventAction.cc`;
- strict parsing of zero/nonfinite/trailing-garbage SiPM systematic controls;
- effective SiPM config logging for integration verification;
- SiPM zero-control + malformed-env integration regression script;
- strict optical mode in the canonical calibration SLURM driver;
- action-level strict optical/PDE startup gate in `main.cc`;
- fail-closed Geant4 required UI/macro command status handling;
- relativistic p+d elastic recoil kinematics tool + tests;
- expert-review protocol, literature/method map and AI pickup guide.

## Work that remains intentionally unresolved

The branch does **not** guess the correct 16/18-sample product, channel polarity, physical stave/fibre geometry, run-61/run-64 calibration role, or the correct incident deuteron distribution. Those require immutable raw data and/or authoritative hardware/run records. The correct scientific implementation is to make those missing contracts fail closed, not choose whichever value makes historical plots reproduce.

The branch also does not claim that passing Python CI validates the Geant4 integration changes. The SiPM/Geant4 regression still needs execution in a recursive Geant4-capable checkout and the real-data gates still need immutable beam-data bytes.