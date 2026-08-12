# ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001

Status: `ACTIVE/PARTIAL` pending exact-final-head protected CI and protected-main integration.

Parent: #977. Cross-dependencies: #1067, #1072, prior producer child `ARU-SIPM-RUN-METADATA-COMPILED-CORE-SHA-001` / PR #1280.

## 1. Atomic input/output contract

Input unit: one SiPM sensitivity campaign point consisting of one `*.root` file plus its exact sibling `*.meta.json` sidecar. The scientific statistical unit downstream remains the event; this atom governs whether the *point* is admitted to any event aggregation at all.

Required provenance state per point:

- `digitizer.validation_status == "OK"`;
- nonempty `digitizer.digitizer_config_sha256` for numerical effective configuration identity;
- canonical exact `digitizer.ccb_sipm_core_commit = H_i`, where `H_i` is a lowercase, nonzero, 40-hex Git revision identity;
- requested sweep knob equals effective metadata value under the existing #982 mapping.

Campaign aggregation invariant:

`forall i,j in admitted campaign: H_i = H_j`.

When an immutable external campaign specification supplies `H_expected`, the stronger invariant is

`forall i: H_i = H_expected`.

Output: only points satisfying these gates may contribute to `<knob>/PROVENANCE.json`, summaries, plots, and cross-knob sensitivity statistics. The output provenance row records the exact core SHA and `core_identity_status=EXACT_40HEX_CAMPAIGN_CONSISTENT`.

Units: Git revisions and configuration digests are dimensionless identifiers. This atom does not alter ADC, PE, MeV, probability, time, or any detector observable.

Scientific meaning: numerical configuration identity and implementation identity are independent state variables. `digitizer_config_sha256` answers "which serialized numerical model state?"; `ccb_sipm_core_commit` answers "which reviewed implementation revision produced that state/waveform?". Neither substitutes for the other.

## 2. Competing mechanisms / descriptions

H1 — `validation_status=OK` + nonempty config digest is sufficient provenance. Rejected: source revision is not an input to that digest, so two implementation revisions may share one numerical configuration.

H2 — any nonempty `ccb_sipm_core_commit` label is sufficient. Rejected: values such as `deadbeef`, `unspecified`, or arbitrary strings do not identify an exact revision.

H3 — the first observed full SHA can define campaign truth. Collapsed into a limited *homogeneity* check only. It detects mixed code revisions but is not an external authorization source and cannot retroactively prove historical caller-provided SHAs were truthful.

H4 — canonical per-point exact SHA + within/cross-knob equality + optional externally pinned expected SHA. Survives as the bounded consumer contract.

H5 — resolve current repository gitlink at analysis time and require equality. Not adopted as the default because historical campaigns may intentionally correspond to an older reviewed producer; current checkout identity is not automatically the intended campaign identity. A content-bound campaign-manifest source remains a child.

## 3. Equations, invariants, limiting cases, identifiability

Let `C_i` be the digitizer configuration digest and `H_i` the core revision for point `i`.

`C_i = C_j` does not imply `H_i = H_j`.

Conversely, `H_i = H_j` does not imply `C_i = C_j`; a legitimate sensitivity scan changes response parameters and therefore may change its effective configuration digest while keeping the implementation revision fixed.

Therefore the two identifiers are complementary rather than duplicate parameterizations.

Campaign-code homogeneity is identifiable from sidecars only if every `H_i` is exact and serialized. Historical truth of an old full SHA is not identifiable from the sidecar alone because legacy producer code accepted caller/environment state; that limitation is explicitly delegated to the historical-output audit child.

Limiting cases:

- one-point campaign: code homogeneity is vacuous, but canonical exact identity remains required;
- multiple points, one SHA: passes internal consistency;
- multiple points, two valid SHAs: rejected before aggregation;
- exact point SHA with externally supplied different `H_expected`: rejected;
- missing/short/uppercase/noncanonical/zero SHA: rejected;
- exact SHA but no config digest or non-OK validation status: remains rejected by prior gates.

## 4. Evidence inspected

Live protected base at atom selection: `ccb-testbeam/main@d32d21832e6dd8eaec7b321693b8b33bdf483b78`; gitlink `geant4/single_stave/sipm -> ccb-sipm-core@3627dc87137a9f33f511a755671414b11853c0a0`.

Current analyzer `scripts/single_stave/sipm_sensitivity.py` accepted sidecars after checking only `digitizer.validation_status == OK` and nonempty `digitizer_config_sha256`; it copied `ccb_sipm_core_commit` to output but did not validate it or compare points.

Current focused test fixture used `ccb_sipm_core_commit="deadbeef"` while expecting the normal happy path to pass, demonstrating that the prior test suite itself encoded the provenance gap.

Producer `RunAction::WriteMetadataSidecar()` emits `git_commit` and the digitizer block. PR #1280 separately bound the core SHA into the executable. The systematic launcher exports `CCB_GIT_COMMIT`; the historical core-SHA environment bridge is no longer the authorizing source after #1280.

Parent #977 remains OPEN/PARTIAL. Historical sidecar truth, compiler/linker/build-input identity, requested→effective operating point, and measured-electronics authorization are still unresolved.

Open PR #1279 concerns DAQ saturation authorization and was inspected as concurrent unrelated work; this branch does not modify its files.

Post-#1280 main-push MC Validation run `31561985291` was independently verified `completed/success` on exact `21de9a79cd32a2ecbc4005381c96322367ef3800` during this atom.

## 5. Implementation

Branch: `audit/sipm-sensitivity-core-sha-gate-v1`, based on exact `main@d32d21832e6dd8eaec7b321693b8b33bdf483b78`.

Code changes:

- add `canonical_core_sha()` with canonical lowercase nonzero 40-hex validation;
- require exact core SHA in `load_sidecar()` in addition to existing status/config-digest gates;
- optionally bind each point to `--expected-core-sha`;
- reject mixed exact core revisions within one knob directory;
- reject mixed exact core revisions across one campaign summary;
- serialize exact core identity status in each provenance row;
- expose observed campaign core SHA in the generated global summary;
- retain requested/effective knob matching and existing statistical calculations unchanged.

Tests added/strengthened in `tests/test_sipm_sensitivity_provenance.py`:

1. valid canonical exact core SHA passes;
2. missing core SHA fails closed;
3. short `deadbeef` fails despite `validation_status=OK` and a config digest;
4. valid but unexpected 40-hex SHA fails when `expected_core_sha` is supplied;
5. exact expected match passes;
6. two otherwise valid points from different core revisions cannot be aggregated;
7. accepted rows expose exact identity status.

## 6. Executed discriminating experiment

Local environment could not clone GitHub (`Could not resolve host: github.com`), so no claim is made for a local repository checkout or repository pytest run.

The proposed exact algorithm was nevertheless executed as a deterministic isolated Python fixture after `python -m py_compile` succeeded. An unrelated `ccb_mc_validation.response_surface` import was stubbed solely so the module could import; no sensitivity statistic used the stub.

Executed outcomes:

- canonical `3627dc87137a9f33f511a755671414b11853c0a0` with matching expectation: PASS;
- `deadbeef`: `ProvenanceError` as required;
- valid `ffffffffffffffffffffffffffffffffffffffff` with expected `3627dc...`: `ProvenanceError` as required;
- two-point campaign with exact but different valid SHAs: `ProvenanceError` as required.

Printed terminal result: `deterministic core-SHA gate fixture: PASS`.

No RNG, ROOT event payload, Geant4 transport, beam data, detector MC, event weights, or physics observable participated. Protected exact-final-head repository CI remains mandatory before merge.

## 7. Cross-scale propagation

Micro/software: exact implementation identity becomes a required metadata state rather than an ignored label.

Meso/campaign point: one row cannot enter analysis if implementation identity is absent or malformed.

Campaign: exact code-revision mixtures cannot be summarized as one response surface.

Study/result: future `PROVENANCE.json` and campaign summary explicitly carry the observed core revision. This prevents a configuration-only provenance record from masquerading as source-bound execution provenance.

Claim: no detector-response or performance claim is validated by this change. It only strengthens whether a simulation point is eligible for later analysis.

## 8. Four sequential AI review passes

### A. Detector-response / provenance lead

Background: detector simulation integration, reproducible builds, waveform-response configuration.

Evidence inspected: #977, #1280 producer repair, exact live analyzer and tests, sidecar producer, systematic launcher, current gitlink.

Strongest counter-hypothesis: the digitizer config digest already identifies the response implementation sufficiently.

Attempted falsifier: compare the variables entering the digest with the source revision; code identity is independent and can change without changing serialized numerical settings.

Residual uncertainty: historical full SHAs may have been caller-forged before #1280; full executable/toolchain identity is not represented.

Vote: `ACCEPT bounded downstream gate / BLOCK #977 COMPLETE`.

### B. Adversarial mechanism reviewer

Background: provenance substitution, mixed-population aggregation, fail-open state machines.

Evidence inspected: former `deadbeef` happy-path test, missing/short/mismatch/mixed-SHA hostile controls.

Strongest counter-hypothesis: any 40-hex value plus within-campaign equality is enough to prove truth.

Attempted falsifier: legacy producer history shows a caller/environment field could contain an arbitrary full SHA; equality detects consistency but not authenticity.

Residual uncertainty: expected SHA is only externally authoritative when its source is itself content-bound.

Vote: `ACCEPT canonical + mixed-revision rejection / REVISE any historical-authenticity claim`.

### C. Independent statistics / validation reviewer

Background: reproducibility, statistical-unit governance, negative controls.

Evidence inspected: deterministic algorithm fixture, focused test design, unchanged event-statistic code paths.

Strongest counter-hypothesis: a software gate can validate the sensitivity response surface itself.

Attempted falsifier: no ROOT events or detector population were read; the gate only controls admission, not estimator bias, uncertainty, weighting, or detector truth.

Residual uncertainty: exact-final-head protected CI has not yet run at archive creation.

Vote: `ACCEPT deterministic falsifier / BLOCK detector inference and merge pending CI`.

### D. Claims / provenance reviewer

Background: code→artifact→claim traceability and calibration authority.

Evidence inspected: parent #977 acceptance criteria, #1067 dependency, current claim/coordination state.

Strongest counter-hypothesis: once consumer and producer SHA fields agree, #977 can close.

Attempted falsifier: #977 still requires effective configuration completeness, campaign requested→effective closure, historical output audit, and data/MC figures tied to exact response config; #1067 still blocks measured-electronics authority.

Residual uncertainty: no immutable historical sidecar population was available for audit in this run.

Vote: `ACCEPT bounded child / KEEP #977 and #1067 OPEN/PARTIAL`.

## 9. Child atoms spawned / retained

- `ARU-SIPM-CAMPAIGN-MANIFEST-CORE-SHA-SOURCE-001`: bind `--expected-core-sha` to immutable campaign intent rather than operator memory.
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`: audit pre-#1280 sidecars, including valid-looking caller-provided full SHAs.
- `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001`: compiler/linker/build-input/executable-byte identity.
- #1072: requested vs effective operating-point response semantics.
- #1067: measured impulse source/effective-kernel calibration authorization.

## 10. Claim/wiki consequences

No public detector-performance statement is promoted. Any sensitivity result whose sidecars lack exact core identity is now intended to be rejected rather than plotted. Historical sensitivity outputs are not retroactively validated; they require the dedicated audit child. No WIKI performance text is changed by this atom.

## 11. Blockers / next gate

Mandatory next gate: protected exact-final-head MC Validation for the complete branch, including the focused provenance tests and repository-wide non-integration suite. Do not merge if any required context fails or if current main changes create a material conflict.

If CI passes and the branch remains bounded/mergeable, merge with expected-head protection, verify the resulting remote-main SHA and independent main-push CI when available, then mark this child `VALIDATED` at software/provenance scope only.
