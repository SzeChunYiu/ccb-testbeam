# Latest Handoff

## SiPM sensitivity consumer now requires exact core source identity before aggregation

Selected atom: `ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001`, child of reopened #977 and downstream of the producer-side compiled core binding from #1280.

The live protected repository was inspected at `main@d32d21832e6dd8eaec7b321693b8b33bdf483b78`; its exact SiPM gitlink is still `ccb-sipm-core@3627dc87137a9f33f511a755671414b11853c0a0`. The prior main-push MC Validation run for #1280, `31561985291` on exact `21de9a79cd32a2ecbc4005381c96322367ef3800`, is now independently verified `completed/success`.

The downstream defect is separate from that producer repair. Current-main `scripts/single_stave/sipm_sensitivity.py::load_sidecar()` previously authorized a row after checking only `digitizer.validation_status == "OK"` and nonempty `digitizer_config_sha256`. It copied `digitizer.ccb_sipm_core_commit` into emitted provenance without validating it. The existing happy-path test even used `deadbeef`, showing that a short/unbound core label was part of the accepted test contract.

The bounded consumer invariant is now explicit on branch `audit/sipm-sensitivity-core-sha-gate-v1`: every admitted point must carry one canonical lowercase nonzero 40-hex core SHA; points aggregated within a knob and across one campaign must all use the same exact revision; and when an externally pinned `--expected-core-sha` is supplied, every point must match it exactly. `digitizer_config_sha256` remains independently required because numerical configuration identity and implementation identity are complementary rather than interchangeable.

The branch adds canonical SHA validation, optional expected-SHA matching, within-knob and cross-knob mixed-revision rejection, explicit core identity state in `PROVENANCE.json`, observed core revision in the generated global summary, and hostile missing/short/mismatch/mixed-SHA tests. The exact proposed algorithm was also executed locally in an isolated deterministic fixture after `py_compile`; canonical match passed, `deadbeef` failed, a valid but wrong full SHA failed against an expectation, and a two-point mixed-core campaign failed. The unrelated response-surface import was stubbed only to import the module; no ROOT event payload or response statistic was evaluated. Local network access could not resolve `github.com`, so there is no local repository pytest/Geant4 claim.

Stable concern `CCB-977-SENSITIVITY-CORE-SHA-GATE-001` is recorded on #977. The four sequential AI reviews are: **detector-response/provenance lead** `ACCEPT bounded gate / BLOCK #977 COMPLETE`; **adversarial reviewer** `ACCEPT canonical+homogeneity gate / REVISE any historical-authenticity claim`, because legacy caller-provided full SHAs can still look syntactically valid; **independent validation reviewer** `ACCEPT deterministic falsifier / BLOCK merge and detector inference pending exact-final-head protected CI`; **claims/provenance reviewer** `KEEP #977 and #1067 OPEN/PARTIAL`.

Archive: `chatgpt_todo/archive/2026-08-12T050300Z_ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001.md`.

Remaining material children are `ARU-SIPM-CAMPAIGN-MANIFEST-CORE-SHA-SOURCE-001` to bind an external expected SHA to immutable campaign intent rather than operator memory; `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`; `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001`; #1072 requested/effective operating-point semantics; and #1067 measured-impulse source/calibration authorization. Open PR #1279 is concurrent unrelated DAQ saturation work and must not be absorbed into this branch.

Next action: open a bounded draft PR for this branch, require every exact-final-head protected MC Validation context to pass, inspect any failure as evidence, and merge only with an expected-head guard if the final branch remains bounded and compatible with current protected main. No beam bytes, production Geant4 population, measured electronics calibration, DATA↔MC result, timing/PID metric, pile-up efficiency, rate, ESS, p-value, or detector-performance quantity was produced or promoted.
