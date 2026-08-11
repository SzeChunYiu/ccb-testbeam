# Latest Handoff

## Validated milestone: scientific issue-state repair is on protected main

Protected `main` is `31f963efb6d6fba14e245c5aed30d956bb01c0dc`, squash merge of PR #1217. Exact PR head `fbae1dcd807efdf0ba928996a960d0fe64934b3b` passed MC Validation run `31499388937`: the curated ruff step, full non-integration pytest step, diagnostics upload, and enforcement all completed successfully. PR #1217 was marked ready and squash-merged using an expected-head guard.

The bounded repository result is now durable: #1057 is `open/reopened`, while the full-2π source implementation from #1216 remains merged. The issue body has been corrected so the historical distinguishable-particle marginal is `q(phi)=1/(4a)` on the two opposite support intervals and `p/q=2a/pi`; it marks only the explicit source-measure/versioning and removal of the 5 cm / 1 m detector surrogate as completed leaves. Compiled/seeded source closure, accepted-observable geometry/trigger closure, actual CCB polarization, source-provenance serialization, and downstream detector-response compatibility remain unchecked.

### Governance contract and child

The repaired invariant is

`MERGED(implementation) != COMPLETE(research_universe)`

and

`COMPLETE(I) => (AND material acceptance gates are ACCEPTED) AND cross-scale compatibility PASS`,

unless every unresolved condition is explicitly transferred to named successors without loss of blocker and claim state.

#1182 is the deliberate counterexample that prevents over-generalization: later coordination explicitly scopes it as a completed **source-readiness implementation** issue and transfers unresolved runtime/path provenance to named children. It therefore remains closed.

Issue #1218 (`ARU-GOV-MERGE-CLOSE-KEYWORD-001`) now owns prevention/detection of future merge-close contradictions. Its candidate contract distinguishes `ACCEPTANCE_COMPLETE`, explicit successor transfer, `SUPERSEDED`, and partial/non-closing states; requires deterministic repository-owned fixtures rather than silently depending on live network state; preserves #1057 as the accidental-close regression witness and #1182 as the legitimate-transfer control; and retains post-merge reconciliation if the merge mechanism cannot be made fully fail-closed beforehand.

### Four sequential AI reviews

- **Source/physics lead — ACCEPT #1057 state repair / BLOCK source-physics completion.** The merged source change is a bounded spin-averaged/full-azimuth reference; no compiled/seeded HIBEAM population or accepted-observable closure was produced.
- **Adversarial mechanism reviewer — REJECT accidental merge-equals-complete semantics / ACCEPT explicit completion-or-successor-transfer model.** A blanket ban on closure is also rejected because #1182 is a valid bounded-scope counterexample.
- **Independent validation reviewer — ACCEPT deterministic governance evidence / BLOCK Geant4 and detector inference.** The exact-head CI that validated #1217 is Python/static; it does not build the external HIBEAM application.
- **Claims/provenance reviewer — ACCEPT repository-state correction / BLOCK CL-021 promotion.** No claim status is upgraded by issue-state governance.

### Scientific boundary and next atom

Current `.github/workflows/mc_validation_ci.yml` routes `geant4/**` but still runs Python 3.11 ruff/pytest rather than a HIBEAM/Geant4 compile. The historical `geant4/setup_and_run.sh` relies on host-local `nnbar_env`, local Geant4/VGM paths, an external HIBEAM checkout and local staged inputs. The tracked installer verifies the reviewed source pair, but installation is not compilation or generator validation.

The next highest-value scientific atom therefore remains `ARU-MC-SOURCE-PHI-COMPILED-CLOSURE-001`: install the exact reviewed source pair in a provenance-bound external tree, compile it, bind executable/toolchain/runtime/input identities, set explicit seed/run-manager/thread/event count, and execute seeded full-azimuth/coplanarity closure. If that exact execution environment is unavailable, preserve the precise blocker and move to another ready scientific leaf instead of treating static CI as compiled evidence.

Other #1057 leaves remain `ARU-MC-SOURCE-PHI-ACCEPTANCE-CLOSURE-001`, `ARU-MC-SOURCE-PHI-POLARIZATION-001`, and `ARU-MC-SOURCE-PHI-PROVENANCE-SERIALIZATION-001`. Existing #1053/#1178/#1179, geometry/trigger, event-weight, runtime-provenance and detector-response atoms remain coupled gates. CL-021 remains gated.

No production Geant4 campaign, beam or production-MC ROOT bytes, detector-response sample, rate, B2/B8, PID, timing, calibration, pile-up, ESS, p-value, or DATA/MC result was produced or promoted in this governance run.
