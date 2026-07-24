# Blockers

## BLK-CI-001 — PR #868 lint gate

- **State:** RESOLVED
- **Resolution commit:** `7992aa31`
- **Verified run:** GitHub Actions `29861328983` (conclusion=success)
- **Observed failing run:** GitHub Actions `29855061309`, job `88717198244`.
- **Artifact:** `validation-logs-29855061309-1`, artifact ID `8504991924`, digest `sha256:c6339f3fff30b504b2424ac6d63efd682aef6593b859df20dfc3daeb071f4a13`.
- **Verified pytest result:** `147 passed, 1 skipped in 41.64s`.
- **Verified ruff findings in the earlier failed run:** exactly three `E501` violations, later corrected:
  1. `scripts/compare_single_stave_mt_reproducibility.py:389` (103 > 100),
  2. `scripts/compare_single_stave_photon_trees.py:364` (103 > 100),
  3. `tests/test_compare_single_stave_mt_reproducibility.py:79` (109 > 100).
- **Resolution evidence:** workflow run `29861328983` completed successfully after the targeted line-wrap fixes.

## BLK-CI-002 — current-main amplitude audit unit-test regression

- **State:** RESOLVED
- **Observed defects:** one regression still asserted obsolete warning `ABSOLUTE_WITHOUT_BASELINE_LEVEL`; aggregate `n_invalid_baseline_data_tables` inspected evidence-gated `physics_acceptance`, omitting heuristic non-NET tables whose unconditional convention state was `BASELINE_DATA_INVALID`.
- **Validated transport:** PR #884, head `9750d0fddc626a76f0c954fa09065db05ac83f32`, changed exactly `tools/audit/amplitude_convention_audit.py` and `tests/test_amplitude_convention_audit.py` by four additions and two deletions.
- **Validation:** MC Validation CI run `29993563323`, job `89161772967`, completed successfully.
- **Resolution on main:** squash merge commit `4f857f508160bbbe059d936866b426a45788c9bd`; post-merge file reads confirm the synchronized warning assertion and convention-level non-NET invalid-baseline counter.
- **Scientific boundary:** the repair restores Python audit-gate consistency. It does not validate a real pulse table, amplitude convention, pedestal subtraction, polarity, stopping distribution, simulation, or detector-performance claim.

## BLK-COORD-001 — concurrent deletion of scientific-review coordination records

- **State:** PARTIAL
- **Observed change:** PR #886 merged during this run as `98f74d1c9a79abbedfcc9d4e934deb9e40ee3e97` and intentionally deleted the entire pre-existing `chatgpt_todo/` tree together with separate factory, fleet, supervisor, and ticket infrastructure.
- **Conflict:** the active scheduled scientific-review requirement explicitly mandates the repository-local `chatgpt_todo/` handoff system. This requirement is separate from the removed factory/fleet/ticket system.
- **Resolution completed:** recreated the minimum mandatory scientific-review protocol and ledgers (`README.md`, `CLAIM_EVIDENCE_MATRIX.md`, `STUDY_REVIEW_LEDGER.md`, `VISUALIZATION_MATRIX.md`) and retained/recreated the current task, backlog, index, code-result map, blockers, session log, handoff, and current immutable archive record.
- **Remaining limitation:** older archive files removed by PR #886 were not blindly restored. Their bytes remain recoverable from Git history before `98f74d1c9a79abbedfcc9d4e934deb9e40ee3e97`, but current-tree restoration requires a deliberate provenance review to avoid overturning unrelated operator intent.
- **Do not claim:** that the historical archive directory has been fully reconstructed on current `main`.

## BLK-G4-001 — real simulation validation unavailable

- **State:** RESOLVED
- **Resolution evidence:** the 2026-07-21T22:28:29Z LUNARC session recorded a Geant4 11.2.2 build, 3/3 CTests passing, five 500-event optical runs, exact one-thread versus 48-thread event/photon equality, multiseed diagnostics, and mean optical yield 178.3 PE/event.
- **Important limitation:** the present connector-only session did not independently access the LUNARC files or rerun the simulation. The resolution is therefore repository-recorded evidence from that session, not a new independent reproduction here.
- **Required provenance retention:** preserve commands, versions, ROOT/JSON/PDF artifact paths, hashes, seeds, event counts, and uncertainty calculations in the Geant4 handoff and claim-evidence records.

## BLK-G4-BUILD-001 — tracked generated build tree from PR #888

- **State:** RESOLVED
- **Observed change:** PR #888 added 66 files under `geant4/single_stave/build/`, including CMake cache/generator files, compiler probes, object/dependency files, a linked executable, copied macros and optical tables, and a generated metadata sidecar.
- **Why it was unsafe:** the cache embeds absolute LUNARC worktree/toolchain paths; binaries and object files are platform-specific; copied runtime assets duplicate canonical source; a committed build tree can be mistaken for reproducible validation evidence even though PR #888 CI ran Python unit tests only.
- **Resolution:** commit `c7cdd653c5fef08b1e70cb33db9c574f7e7e0de9` removed the complete tracked build tree, added `geant4/**/build/` to `.gitignore`, and added `tests/test_no_tracked_geant4_build_artifacts.py`.
- **Validation:** the regression failed against a synthetic tracked `CMakeCache.txt` and passed after removal plus ignore configuration; the candidate Git commit was inspected before fast-forwarding `main`, and source files from PR #888 plus concurrent PR #889 remained present.
- **Remaining scientific limitation:** removal of generated artifacts does not validate or invalidate the scientific source fixes in PR #888/#889. Clean Geant4 builds, CTests, runtime outputs, and immutable result provenance still require independent review.

## BLK-G4-SP-001 — accepted stopping-power closure unavailable

- **State:** OPEN
- **Resolved engineering defects:** reference path/self-test provenance (`AUD-G4-004`), reference-domain rejection (`AUD-G4-006`), strict reference parsing (`AUD-G4-007`), quenched-proxy rejection (`AUD-G4-008`), reusable strict event-table parsing (`AUD-G4-009`), canonical simulation-parser integration (`AUD-G4-010`), canonical PSTAR component identity (`AUD-G4-012`), exact configured-energy grouping (`AUD-G4-013`), fail-closed deuteron proxy authorization (`AUD-G4-014`), point-estimate uncertainty authorization (`AUD-G4-015`), round-trip report serialization (`AUD-G4-016`), self-contained central-value/configuration reporting (`AUD-G4-017`), row-order invariant compensated grouped sums (`AUD-G4-018`), one-snapshot simulation row/provenance binding with controlled UTF-8 failure (`AUD-G4-019`), removal of the unsupported cross-energy mean (`AUD-G4-020`), and input-preserving atomic report publication (`AUD-G4-021`) are validated. Both inputs use shared fail-closed parsers and exact provenance; distinct energies are neither pooled, collapsed, averaged, made order-sensitive, nor paired with a later replacement of the simulation input path in machine-readable output; proton PSTAR at `E_d/2` cannot masquerade as a direct deuteron reference; no numerical point estimate can print PASS or exit successfully while uncertainty is `NOT_EVALUATED`; report output cannot alias validated inputs and is atomically published with byte/hash provenance.
- **Remaining data-provenance blocker:** no exact real exported Geant4 event table was available in this run. Before interpreting any ratio, run the integrated CLI on immutable exports and retain path, byte size, SHA-256, row count, particle/energy coverage, basis, code commit, command, environment, output hash, and any rejection.
- **Remaining uncertainty blocker:** no accepted statistical/systematic uncertainty budget exists. Preregister event/replicate Type A treatment, between-seed/run/configuration effects, deposited-energy/path covariance, material-density and reference uncertainty, production-cut/physics-list/material/geometry sensitivity, secondary escape, energy evolution, coverage, and acceptance criteria before inspecting final closure results.
- **Why scientific acceptance remains blocked:** NIST stopping power is projectile energy loss per path length. Geant4 local energy deposit can exclude energy carried away by generated secondaries, and particle energy evolves along the track. NIST PSTAR supplies proton tables; the deuteron `E_d/2` mapping is an equal-velocity proxy, not a direct deuteron PSTAR datum.
- **Validated boundary:** current output remains `DIAGNOSTIC_ONLY`; deuteron input is status-2 by default and explicit proxy output is non-accepting. Direct proton numerical proximity is labelled `POINT_ONLY`, carries `uncertainty_method=NOT_EVALUATED`, and is non-accepting. Cross-energy output is limited to descriptive bounds labelled `no combined estimate` under `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`.
- **Resolution:** validate exact real exports; then run a clean proton closure using `G4EmCalculator::ComputeTotalDEDX` or primary entry/exit kinetic energy plus path-length/reference integration; quantify escaping secondary energy and production-cut dependence; implement and validate the preregistered uncertainty budget; preserve exact material, density, physics list, cuts, versions, commands, seeds, event counts, hashes, uncertainty, and plots. For deuterons, use an authoritative deuteron reference or independently validate a bounded approximation for the exact material and energy domain.
- **Do not claim until resolved:** that local deposited-energy agreement validates Geant4 total stopping power, that proton PSTAR at half the deuteron energy validates deuteron stopping power, or that point estimates or descriptive cross-energy bounds establish agreement without uncertainty.

## BLK-G4-SP-002 — canonical PSTAR component-sum gate unavailable

- **State:** RESOLVED
- **Original defect:** the standalone exact-decimal validator checked `total = electronic + nuclear`, but `compare_stopping_power.py` parsed references independently and could accept a modified finite, positive, ordered total.
- **Resolution:** `validate_pstar_component_sum.py` v1.1.0 exposes `read_validated_pstar_table()`, and the canonical comparison imports it directly. No second PSTAR reference parser remains in the comparison path.
- **Validation:** a direct CLI reference containing `1,9,1,8` returns status 2, writes no result CSV, and prints no numerical PASS; valid output records reference SHA-256, bytes, validated rows, validator version, identity, and consistency. Combined focused regression returned `42 passed in 4.22s`; integration Markdown/JSON/SVG evidence is on `main`.
- **Remaining independent question:** external NIST transcription/material provenance has not been independently re-queried in this session. That limitation does not reopen the canonical software integration gate.

## BLK-I885-001 — accepted issue #885 calibration unavailable

- **State:** OPEN
- **Resolved engineering defects:** coverage is now manifest-audited; the summary distinguishes 14/72 total from 14/40 main-grid files and gives species-specific energies. `refit_i885_campaign.py` forms one seed-averaged point per energy, separates `n_files` and `n_energy_points`, requires at least three energies, combines propagated within-file and between-seed SEM, and records residual dof, covariance, fit range, chi-square and p-value. Focused regression returned `6 passed`; JSON/CSV/SVG/Markdown evidence is committed.
- **Measured scientific result:** no linear calibration is accepted. Deuteron fits are skipped because two energy points leave zero residual degrees of freedom. Proton SiPM and Birks-visible global lines are rejected with reduced chi-square 357.99 and 33391.66 for three residual degrees of freedom; the SiPM p-value is `1.62e-232` and the Birks p-value underflows double precision. `i885_fits.json` has an empty accepted `fits` object.
- **Why acceptance remains blocked:** only 14/72 files and seven of 20 main-grid species-energy points are committed; only two seeds exist per observed energy; no systematic/model error is included; attenuation/timing coverage is absent; no nonlinear or restricted-range response was preregistered; no independent validation energies or real-data closure exist.
- **Resolution:** complete the campaign or freeze an independent validation subset, preregister physically plausible response models and/or restricted ranges, compare bias/residuals/uncertainty coverage using held-out or newly simulated energies, quantify seed/run/systematic effects, and perform data/MC closure before accepting calibration constants.
- **Do not claim until resolved:** validated proton/deuteron slopes or intercepts, adequacy of a global line, completed 2–20 MeV shared coverage, attenuation/timing performance, a detector calibration, or completion of the 72-file campaign.

## BLK-MERGE-001 — PR #868 integration into current main

- **State:** OPEN
- **Reason:** runtime and CI acceptance were recorded as passing on the PR branch, but `main` advanced substantially afterward and PR #868 is now closed without merge. The implementation must be mapped to exact commits already present on `main` or recovered through a new, current-main-based transport branch; no closed branch may be assumed integrated.
- **Resolution:** compare the closed PR head with current `main`, identify every validated code and artifact commit already integrated, transport only missing validated work onto current `main`, rerun required checks, and record the resulting main-branch SHAs. Do not reopen or merge stale conflicting coordination files blindly.

## BLK-DOC-001 — public C12 wording synchronization

- **State:** OPEN
- **Affected files:** `WIKI.md`, `docs/academic_chapters/09_anomaly_id.md`.
- **Verified stale content:** three WIKI entries still classify the MC-only C12-like result as `VALIDATED`, the WIKI still gives an unsupported numerical veto-impact estimate, and Chapter 9 still presents simulation-only interpretation and downstream quantities as established.
- **Available validated tool:** `scripts/sync_c12_public_claims.py`; synthetic regression suite previously passed (`6 passed`).
- **Current execution blocker:** this environment cannot resolve `github.com` for a local checkout or raw-file download. The GitHub contents connector requires complete replacement content for updates; using truncated file responses would risk data loss and is prohibited.
- **Resolution:** run the synchronizer in a complete checkout based on current `origin/main`, execute `--check`, run its tests and `scripts/broken_link_checker.py`, inspect the exact WIKI/Chapter 9 diff, and commit the reviewed changes directly to `main`.

## BLK-AMP-001 — real A-002 amplitude authorization and regeneration

- **State:** OPEN
- **Tasks:** `AUD-AMP-009`, `AUD-AMP-010`, `AUD-DELTAE-001`, `AUD-DELTAE-002`.
- **Reason:** no exact A-002 pulse-table bytes or independently reviewable schema, producer-code, pedestal-evidence, or pulse-polarity artifact bytes were accessible in this session. Absolute/net convention alone does not identify whether pulse codes rise or fall relative to the pedestal.
- **Validated tooling:** `validate_amplitude_evidence_map.py` v1.3.0 resolves each relative evidence reference beneath a controlled root, compares its measured SHA-256 with the map, and verifies any optional fragment as a canonical existing line or line range. `amplitude_convention_audit.py` v3.1.0 authorizes physics use only from such a verified map; raw programmatic dictionaries remain non-authorizing. The A-002 bridge now requires explicit positive/negative polarity for absolute input and rejects polarity violations instead of applying `abs`.
- **Resolution:** obtain and hash the exact A-002 table and supporting artifact, create a map with both digests, accepted evidence basis, exact evidence scope, and pulse polarity; run the validator and full-table auditor without `--max-rows`; run the bridge with the authorized polarity; resolve all warnings/errors; then regenerate the quarantined A-002 JSON, event CSV, stopping fractions, and ΔE–E plot with cardinality and provenance checks.
- **Do not claim until resolved:** whether A-002 `amplitude_adc` is absolute or net, whether pulses are positive- or negative-going, whether pedestal subtraction is correct, or any corrected stopping distribution or detector-performance conclusion.

## BLK-G4-SP-003 — unsupported cross-energy stopping-power mean

- **State:** RESOLVED
- **Task:** `AUD-G4-020`.
- **Original defect:** source blob `4e45e55b48c1d51320b9e6d0959b0b8423d0b2fc` grouped ratios from distinct configured energies by species and printed `statistics.mean(ratios)` as `mean point-estimate ratio` although uncertainty and covariance were not evaluated.
- **Resolution:** the canonical reporter removes the arithmetic mean and `statistics` import, retains individual exact-energy points, emits only descriptive min/max bounds explicitly labelled `no combined estimate`, prints `NO_CROSS_ENERGY_COMBINATION_WITHOUT_UNCERTAINTY_MODEL`, and records that policy in every result and CSV row.
- **Validation:** focused `py_compile`; source audit returned `VALIDATED`; combined audit/reporter suite returned `6 passed in 0.04s`; committed source/test Git blobs matched locally validated files; Markdown/JSON/SVG evidence is on `main`.
- **Scientific boundary:** descriptive bounds are not an average, combined estimator, or accepted closure. Any future combination still requires a preregistered measurand, uncertainties, covariance, combination method, grid-sensitivity study, and coverage validation.

## BLK-G4-SP-004 — stopping-power report can overwrite inputs or publish a partial artifact

- **State:** RESOLVED
- **Task:** `AUD-G4-021`.
- **Original defect:** source blob `360f3e46db664f4eead48021536f210e2f7a85c9` opened the requested final path directly with `out_path.open("w")`, with no output/input alias rejection or atomic replacement path.
- **Resolution:** source blob `043dbd8cae7362dede199b42b28aeb383bccde8d` resolves paths, rejects equality and existing-file identity with either validated input, serializes the complete CSV to a unique same-directory temporary file, flushes and fsyncs it, measures bytes/SHA-256, publishes with `os.replace`, and removes temporary files on failure while preserving any prior final report.
- **Validation:** direct CLI simulation/reference alias regressions preserve exact input bytes; a resolved symlink alias is rejected; injected serialization and replacement failures preserve an existing output and leave no temporary files; successful output returns exact bytes/SHA-256 and records the policy. Focused compatible suite returned `12 passed in 0.07s`; AST audit returned `VALIDATED`; source/test Git blobs match locally validated files; Markdown/JSON/SVG evidence is on `main`.
- **Scientific boundary:** this resolves artifact publication integrity only. It does not validate a real Geant4 event export, accepted projectile total-energy-loss observable, uncertainty budget, calibration, or detector performance.

## BLK-LEDGER-001 — canonical claim-ledger row-width and field alignment

- **State:** OPEN
- **Task:** `AUD-LEDGER-001`.
- **Observed defect:** `docs/claim_ledger.csv` has a 43-column header, but the original 26 data rows had only 35--40 columns. Late values therefore shifted into the wrong named fields under standard CSV parsing.
- **Bounded remediation:** `CL-001`, `CL-007`, `CL-010`, `CL-011`, and `CL-012` are reconstructed to exactly 43 columns from source evidence. `CL-010`/`CL-012` explicitly quarantine an internally conflicted Rmax instead of preserving a false canonical value.
- **Remaining scope:** 21 rows still have 35--39 columns. Their late status, truth type, source, figure/table, CI, blocker, supersession, commit, or notes fields cannot be assumed to match the header.
- **Resolution:** reconstruct every row from source reports/scripts/data and intended schema; require exactly 43 fields; review semantic mappings and non-empty value preservation; rerun WIKI, claim, link, and figure/source checks.
- **Do not claim until resolved:** that all canonical claim-ledger late fields are correctly aligned or that downstream tools using those fields are reading the intended values.

## BLK-PU-RMAX-001 — canonical pile-up Rmax definition is internally conflicted

- **State:** OPEN
- **Task:** `AUD-LEDGER-001`; prerequisite `S-STAT-003`.
- **Measured conflict:** the MV5 JSON value `3.0448717948717947 MHz` is `(1/124.8 ns) × 0.38`, where `0.38` is the recorded beam duty factor. The academic chapter instead uses `mu_max=0.1`, derives `3.20 MHz` for four staves, and then substitutes `3.05 MHz` as a purported rounding. The recovery summary records no failure-ceiling crossing (`null`) because the maximum simulated failure fraction `0.03475` is below the ceiling `0.17`.
- **Validated containment:** `CL-010` is exact-width and `BLOCKED`; `CL-012` is exact-width and `SUPERSEDED`; both accepted values are blank; focused validator tests returned `6 passed`; source-conflict Markdown/JSON/SVG evidence and repaired FIG-PU-003 provenance are on `main`.
- **Resolution:** preregister the rate measurand, per-stave versus total normalization, occupancy-quality criterion, beam-duty treatment, recovery-curve acceptance rule, uncertainty budget, falsifiers, and independent validation. Recompute from exact inputs, then synchronize WIKI and Chapter 5 only if the gate passes.
- **Do not claim until resolved:** that `3.044`, `3.05`, or `3.20 MHz` is an accepted pile-up tolerance, that the recovery method crossed its ceiling, or that the two definitions agree independently.
