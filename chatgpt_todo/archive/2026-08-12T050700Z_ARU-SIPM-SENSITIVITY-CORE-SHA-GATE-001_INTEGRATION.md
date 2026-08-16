# ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001 — integration addendum

Status: `VALIDATED` at bounded downstream software/provenance scope. Parent #977 and cross-dependency #1067 remain `OPEN/PARTIAL`.

This addendum preserves the pre-merge derivation in `2026-08-12T050300Z_ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001.md` unchanged while recording final execution and repository state.

## Exact integration provenance

- protected base before the bounded change: `d32d21832e6dd8eaec7b321693b8b33bdf483b78`;
- branch: `audit/sipm-sensitivity-core-sha-gate-v1`;
- exact final branch head: `7b09b68a36145a501531d2a061c6b297714d6d7d`;
- PR: #1282, `fix(provenance): gate SiPM sensitivity on exact core revision`;
- changed files: exactly five — `scripts/single_stave/sipm_sensitivity.py`, `tests/test_sipm_sensitivity_provenance.py`, `chatgpt_todo/ACTIVE_TASK.md`, `chatgpt_todo/HANDOFF.md`, and the derivation archive;
- protected exact-head push MC Validation: run `31564970064`, job `94014820058`, `completed/success`;
- protected exact-head pull-request MC Validation: run `31564993781`, job `94014888409`, `completed/success`;
- both exact-head jobs passed checkout, package installation, exact SiPM-submodule source/C++ validation, curated ruff, scientific close-intent/merge-close gates, full unit-test step, diagnostics upload, and final enforcement;
- PR marked ready only after both exact-head contexts were green;
- squash merge used expected-head guard `7b09b68a36145a501531d2a061c6b297714d6d7d`;
- resulting protected main: `9d74a2a2c94227a4ea206c2921a9a8f137b176a9`;
- merge message uses `Refs #977 #1067 #1072 #982 #1280`, not a parent-closing keyword;
- exact SiPM gitlink remains `3627dc87137a9f33f511a755671414b11853c0a0`.

Post-merge main MC Validation run `31565320321` was queued on exact `9d74a2a...` when this addendum branch was created. It is not counted as a PASS unless independently verified after completion.

## Validated bounded contract

For admitted sensitivity points `i`, the integrated consumer requires a canonical lowercase nonzero 40-hex recorded core revision `H_i`. It rejects a campaign aggregation when two admitted points carry different exact recorded revisions. If a caller supplies `H_expected` using `--expected-core-sha`, each point must satisfy `H_i = H_expected` exactly. Existing `validation_status == OK`, nonempty `digitizer_config_sha256`, and requested-versus-effective knob checks remain independent gates.

This validates *consumer admission semantics*, not historical authenticity. A 40-hex token is syntactically revision-shaped; it is not, by itself, proof that a legacy producer actually executed those bytes. Before #1280 the producer field could be caller/environment supplied. Therefore the historical-output audit remains material.

## Final role-separated votes

### Detector-response / provenance lead
Evidence inspected: exact final branch, both protected jobs, final merge SHA, producer/core dependency state. Strongest counter-hypothesis: config digest plus `OK` status already binds implementation. Falsifier: source revision remains independent of serialized numerical configuration. Residual: full binary/toolchain identity and historical authenticity remain unresolved. Vote: `ACCEPT bounded child VALIDATED / BLOCK #977 COMPLETE`.

### Adversarial mechanism reviewer
Evidence inspected: hostile missing/short/mismatch/mixed-SHA controls plus legacy producer semantics. Strongest counter-hypothesis: canonical 40-hex + campaign equality proves provenance truth. Falsifier: a legacy caller could provide an arbitrary full SHA. Residual: immutable external expectation source is absent. Vote: `ACCEPT syntactic/homogeneity gate / REVISE historical-authenticity inference`.

### Independent statistics / validation reviewer
Evidence inspected: deterministic pre-CI fixture and two independent exact-head protected workflow contexts. Strongest counter-hypothesis: green software CI validates detector sensitivity. Falsifier: no ROOT event population or detector data entered this atom. Residual: statistical estimators, weights, uncertainty, and detector-domain validity are unchanged/unvalidated here. Vote: `ACCEPT software/provenance execution closure / BLOCK detector inference`.

### Claims / provenance reviewer
Evidence inspected: #977/#1067 acceptance contracts, PR body/merge message, issue comments, final main state. Strongest counter-hypothesis: producer and consumer SHA hardening suffices to close #977. Falsifier: historical outputs, content-bound campaign intent, complete build manifest, requested/effective operating point, and calibration authority remain open. Vote: `KEEP #977/#1067 OPEN/PARTIAL`.

## Cross-scale boundary

Micro/software: missing/noncanonical core labels cannot be silently admitted by the analyzer.

Campaign: mixed exact recorded revisions cannot be combined as one response surface.

Study: `PROVENANCE.json` and global summary expose the recorded campaign core revision.

Claim: no detector-response/performance claim is promoted. Historical sensitivity outputs are not retroactively validated.

## Children / next atom

Highest-value next atom: `ARU-SIPM-CAMPAIGN-MANIFEST-CORE-SHA-SOURCE-001` — define a content-bound, immutable source for `H_expected`; bind source bytes/schema/hash and superproject/core relation; reject operator-memory and stale/substituted expectation states.

Retained children: `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`, `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001`, #1072, and #1067 calibration/source-authorization leaves.

No beam bytes, production Geant4 detector population, measured electronics calibration, DATA↔MC result, timing/PID metric, pile-up efficiency, rate, ESS, p-value, or detector-performance quantity was produced or promoted.
