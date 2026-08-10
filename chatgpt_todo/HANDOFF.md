# Latest Handoff

## Selected atom: configured scattering-source readiness (#1182)

Protected `main` is now `f5f96951c3f56986769a16cd53ab8e23dee3e287`. PR #1181's bounded deterministic sampler repair has been squash-merged after both exact-head MC Validation runs `31415757686` and `31415753649` completed successfully. The first merge attempt was correctly rejected while one required `test` check was still running; no bypass was attempted. The merged model is `linear_node_pdf_exact_inverse_v1` on `measured_table_support_truncate_v1` with `unit_direct_sampling_v1`.

The numerical inverse is therefore on main, but #1178 remains scientifically open: repository CI does not compile or execute `geant4/src_patch`, configured-source fault/readiness semantics and runtime manifest binding remain unresolved, and #1179 separately owns source statistical/systematic covariance.

### New atomic contract

The selected transition is

`messenger-selected files -> validate/parse -> per-generator-instance readiness -> BeamEnergy + SampleThetaCM -> primary event`.

Required states are

`UNINITIALIZED -> UNCONFIGURED_UNIFORM | CONFIGURED_READY | FATAL`.

For generator instance/worker `j`, event generation must satisfy

`Generate_j(e) => Ready_j`.

If a CS source is configured, `Ready_j` must mean `CONFIGURED_READY`. An invalid configured source must never become the same observable state as an explicitly unconfigured uniform proposal.

### Executed source-level falsifier

The merged source is Git blob `4a9f3de78ec12147159e2ec9b6fb52bf76f1cbe7`. Direct inspection after #1181 confirms that the runtime mechanisms separated into #1182 persist:

- `GeneratePrimaryVertex()` calls `LoadFiles()` only when `event->GetEventID()==0`, then immediately uses `BeamEnergy()`.
- `BeamEnergy()->EvalELoss()` assumes a populated stopping table; an empty table can reach `dEdx[0]` and `Ene[0]`.
- `SampleThetaCM()` uses a uniform fallback for empty/inconsistent CDF state, so an invalid configured source is not distinguished by state from intentional no-source generation.
- required input open failure uses `exit(0)`, allowing shell-success semantics for failed scientific input.
- cross-section row parsing does not verify `sscanf` conversion count.
- no explicit idempotent per-instance readiness state is present; repeated loaders append mutable vectors.

PR #1183 on `audit/mc-source-readiness-contract` adds the executable deterministic static audit, focused tests, `results/research/scattering_source_readiness_v1.json`, and immutable ARU archive. The branch was reconciled onto `main@f5f96951...` with a normal merge commit, preserving both audit history and the validated inverse rather than force-pushing. The machine-readable verdict is `BLOCK_RUNTIME_AUTHORIZATION`; it is static source-contract evidence only, not a Geant4 execution result.

### Geant4 lifecycle evidence and unresolved condition

Official Geant4 Application Developers documentation states that worker user actions are constructed per worker in MT mode and that event numbers processed by a worker are not sequential. Thus a global event-ID-zero predicate is not a valid general per-worker initialization primitive.

However, the repository still does not carry immutable evidence for the exact hibeam_g4 production run-manager choice, Geant4 MT build flag and worker count. The historical S21 review warned about this same event-zero/mutable-vector risk but did not establish that production was actually multi-worker. Therefore the MT failure mechanism remains a **surviving conditional hypothesis**, not a claimed historical failure. Sequential-only execution would remove that particular worker-missing-event-zero mechanism but would not remove the fail-open configured-source, `exit(0)`, parser, or table-readiness defects.

### Mechanisms disposition

- **H1 event-zero initialization:** survives only for a proven strictly sequential executable; rejected as a general worker-local contract.
- **H2 idempotent per-instance lazy readiness after messenger configuration:** preferred implementation class.
- **H3 constructor/run-hook initialization:** possible only if the messenger configuration lifecycle is proven correct.
- **H4 configured-source failure -> uniform:** rejected because it silently changes the proposal measure.
- **H5 missing source -> `exit(0)`:** rejected because failed scientific input cannot report successful process completion.

### Four sequential reviews

- **Source/runtime lead — REVISE / BLOCK runtime authorisation.** Evidence: merged event-zero gate, mandatory stopping lookup, official Geant4 lifecycle and prior S21 warning. Strongest counter-hypothesis: a guaranteed sequential hibeam_g4 executable. Attempted falsifier: repository search for exact run-manager/build/thread provenance was insufficient. Residual: actual production thread mode and messenger/config lifecycle.
- **Adversarial mechanism reviewer — REJECT fail-open semantics.** Evidence: empty-CDF uniform fallback, `exit(0)`, unchecked parsing and empty stopping-table dereference. Strongest counter-hypothesis: invalid inputs always fail obviously. The source itself falsifies that guarantee. Residual: compiled failure behavior after repair.
- **Independent validation reviewer — ACCEPT deterministic source falsifier / BLOCK physics inference.** Strongest counter-hypothesis: seeded CDF agreement alone validates the source. Falsifier: readiness/source-fault semantics are orthogonal to CDF accuracy once ready. Residual: compiled source-fault and sequential/worker closure plus manifest.
- **Claims/provenance reviewer — BLOCK CL-021 runtime promotion.** Strongest counter-hypothesis: green Python CI authorizes the generator. Falsifier: the workflow does not compile `geant4/src_patch`. Residual: exact executable/build/runtime provenance and downstream regeneration.

### Required implementation and experiments

1. Implement an explicit per-instance readiness state reached before any call to `BeamEnergy()` or configured `SampleThetaCM()`.
2. Parse stopping/source tables transactionally with checked row conversion, finite/domain/order/cardinality validation and idempotence.
3. Make required stopping-data and configured-CS failures fatal with unmistakable non-success run semantics; preserve uniform sampling only for explicit `CSFile=null` mode.
4. Bind the exact hibeam_g4 `main`, run-manager construction, Geant4 build flags and worker count for representative production runs.
5. Execute missing/empty/one-row/malformed/nonfinite/negative/duplicate/decreasing/all-zero source fixtures plus analogous stopping-table faults.
6. Run seeded compiled generator-only sequential closure and multi-worker closure if supported by the exact executable; record generator commit, Geant4 version/build mode, worker count, seed(s), event count, table hashes and mode IDs.
7. Serialize readiness/source mode and the input/model identities in the production manifest before downstream MC products are authorising.

### Claim and data boundary

No beam ROOT data were opened. No production Geant4 sample was generated. No angular campaign, source uncertainty, ESS, p-value, PID, penetration, timing, energy, pile-up, rate or detector-performance result was regenerated or promoted. #880/#1053 remain historical `PrimaryWeight` carrier/measure dependencies.

### Next

Land PR #1183 only after its exact-head checks pass. Then implement #1182's per-instance fail-closed readiness on top of the merged exact inverse, run the compiled hostile-input/lifecycle matrix, and bind exact runtime threading provenance. Once readiness and sampler execution are stable, move to #1179 source statistical/systematic nuisance propagation and then downstream truth/detector-response sensitivity.
