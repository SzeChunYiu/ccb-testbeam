# Latest Handoff

## Selected atom: configured scattering-source readiness (#1182)

Protected `main` at the branch point is `fa62e8bb6ce7de10f840ebfa016eaa40cd9f74ec`, where PR #1180 already bound the 190 MeV p-d source table to its primary-literature identity and gated CL-021. This session reviewed the current deterministic sampler repair in PR #1181 and then selected a distinct runtime-state child, `ARU-MC-CS-WORKER-INIT-001`.

### Parent sampler status

PR #1181 exact head is `edf71180b2f622b7cf16a8c1243d2140c2369eb9`. Its bounded numerical repair declares `linear_node_pdf_exact_inverse_v1` on `measured_table_support_truncate_v1`, with unit direct-sampling event weight. One exact-head MC Validation run, `31415757686`, completed successfully. A second required `test` check on the same head, run `31415753649`, was still in progress when polled. A squash-merge attempt was rejected by branch protection with `Required status check "test" is in progress`; no bypass was attempted. Keep #1178 open even after a future merge because Python CI does not compile the Geant4 source.

### New atomic contract

The selected transition is

`messenger-selected files -> validate/parse -> per-generator-instance readiness -> BeamEnergy + SampleThetaCM -> primary event`.

Required states are

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`.

For generator instance/worker `j`, event generation must satisfy

`Generate_j(e) => Ready_j`.

If a CS source is configured, `Ready_j` must mean `CONFIGURED_READY`. An invalid configured source must never become the same observable state as an explicitly unconfigured uniform proposal.

### Executed source-level falsifier

At current main and still at the reviewed #1181 head for the relevant paths:

- `GeneratePrimaryVertex()` calls `LoadFiles()` only when `event->GetEventID()==0`, then immediately uses `BeamEnergy()`.
- `BeamEnergy()->EvalELoss()` assumes a populated stopping table; an empty table can reach `dEdx[0]` and `Ene[0]`.
- `SampleThetaCM()` uses a uniform fallback for empty CDF state, so an invalid configured source is not distinguished by state from intentional no-source generation.
- required input open failure uses `exit(0)`, allowing shell-success semantics for a failed scientific input.
- cross-section row parsing does not verify `sscanf` conversion count.
- no explicit idempotent per-instance readiness flag/state is present; repeated loaders append mutable vectors.

The branch `audit/mc-source-readiness-contract` adds an executable deterministic static audit, focused tests, `results/research/scattering_source_readiness_v1.json`, and the immutable ARU archive. Its current verdict is `BLOCK_RUNTIME_AUTHORIZATION`. This is static source-contract evidence only, not a Geant4 execution result.

### Geant4 lifecycle evidence and unresolved condition

Official Geant4 Application Developers documentation states that worker user actions are constructed per worker in MT mode and that event numbers processed by a worker are not sequential. Thus a global event-ID-zero predicate is not a valid general per-worker initialization primitive.

However, this repository does not currently carry immutable evidence for the exact hibeam_g4 production run-manager choice, Geant4 MT build flag and worker count. The historical S21 review warned about this same event-zero/mutable-vector risk but did not establish that production was actually multi-worker. Therefore the MT failure mechanism remains a **surviving conditional hypothesis**, not a claimed historical failure.

### Mechanisms disposition

- **H1 event-zero initialization:** survives only for a proven strictly sequential executable; rejected as a general worker-local contract.
- **H2 idempotent per-instance lazy readiness after messenger configuration:** preferred implementation class.
- **H3 constructor/run-hook initialization:** possible only if the messenger configuration lifecycle is proven correct.
- **H4 configured-source failure -> uniform:** rejected because it silently changes the proposal measure.
- **H5 missing source -> `exit(0)`:** rejected because failed scientific input cannot report successful process completion.

### Four sequential reviews

- **Source/runtime lead — REVISE / BLOCK runtime authorisation.** Strongest counter-hypothesis is a guaranteed sequential hibeam_g4 executable. Exact run-manager/build/runtime provenance is required to eliminate or retain the worker-init mechanism.
- **Adversarial mechanism reviewer — REJECT fail-open semantics.** Empty CDF uniform fallback, `exit(0)`, unchecked parsing and empty stopping-table dereference are independent of the sampler's inverse-CDF accuracy.
- **Independent validation reviewer — ACCEPT deterministic source falsifier / BLOCK physics inference.** No stochastic test is needed for this state-contract defect, but compiled fault injection and seeded runtime closure remain mandatory.
- **Claims/provenance reviewer — BLOCK CL-021 runtime promotion.** Green Python CI for #1181 does not compile or execute the generator, and this child must remain visible rather than being averaged into the successful inverse-CDF review.

### Required implementation and experiments

1. Implement an explicit per-instance readiness state reached before any call to `BeamEnergy()` or configured `SampleThetaCM()`.
2. Parse stopping/source tables transactionally with checked row conversion, finite/domain/order/cardinality validation and idempotence.
3. Make required stopping-data and configured-CS failures fatal with unmistakable non-success run semantics; preserve uniform sampling only for explicit `CSFile=null` mode.
4. Bind the exact hibeam_g4 `main`, run-manager construction, Geant4 build flags and worker count for representative production runs.
5. Execute missing/empty/one-row/malformed/nonfinite/negative/duplicate/decreasing/all-zero source fixtures plus analogous stopping-table faults.
6. Run seeded compiled generator-only sequential closure and multi-worker closure if supported by the exact executable; record generator commit, Geant4 version/build mode, worker count, seed(s), event count, table hashes and mode IDs.
7. Serialize readiness/source mode and the input/model identities in the production manifest before downstream MC products are authorising.

### Claim and data boundary

No beam ROOT data were opened. No production Geant4 sample was generated. No angular distribution, source uncertainty, ESS, p-value, PID, penetration, timing, energy, pile-up, rate or detector-performance result was regenerated or promoted. #1179 remains the separate source covariance/systematics atom; #880/#1053 remain the historical `PrimaryWeight` carrier/measure dependencies.

### Next

Allow #1181 to merge only after every required exact-head check is complete. Then implement #1182 on top of the exact-inverse source, run the compiled hostile-input/lifecycle matrix, and bind exact runtime threading provenance. Once readiness and sampler execution are stable, move to #1179 source statistical/systematic nuisance propagation and then downstream truth/detector-response sensitivity.
