# Latest Handoff

## Selected atom: MC event/stave deposited-energy statistical unit

PR #1169 on `feat/mc01-event-stave-truth-contract` implements the bounded H3 child of #1052/#1164. Branch point is protected `main@d088b5a886e0c8891d7926af7015193db7a503b8`.

The legacy comparison product is built from charged `Sci_bar_EDep` transport/hit records with a repeated event weight. The replacement contract uses one generator-event row and defines, for B stave `k`,

`E_dep(e,k) = sum_h EDep_h I(event_h=e, arm_h=B, layer_h=k)`.

A charged-only sum is retained separately so trigger-charge semantics cannot silently redefine total deposited energy. The exact transport-step-splitting invariant is: replacing one record `E` by records `E_j` with `sum(E_j)=E` must leave event/stave EDep unchanged even though hit-row multiplicity changes.

## Implemented repository work

- `src/ccb_mc_validation/truth/event_stave.py` aggregates all-particle and charged-only B-stave EDep, validates event identity/topology/matrices, and enforces one nonnegative finite first-primary `PrimaryWeight` per selected generator event.
- It reuses the existing content-bound `stable_event_id`/`build_event_rows` contract and stores Sample-I membership inside the Sample-II row universe, preserving `Sample I subset Sample II` without physical row duplication.
- Source SHA-256 and byte count are measured from one opened regular-file descriptor; Uproot receives a duplicate seekable stream from that same open file and descriptor metadata must remain stable through consumer exit.
- `scripts/mc01_event_stave_truth.py` creates `mc_event_stave_edep_v1.npz` plus a manifest inside a private staging directory. Product SHA-256 is bound into the manifest; both files are fsynced; one directory rename publishes an immutable `generations/<generation_id>/` under `flock`. Existing generations are never overwritten and there is no mutable latest alias.
- Generation identity binds source SHA, tree/coincidence/weighting/population settings, exact executing source hashes for the producer/constants/event-builder/event-stave/PDG/trigger modules, and Python/NumPy/Uproot versions.
- The new product has no `EDEP_CAP`; the legacy silent `600000` hit-prefix retention cannot truncate its event/stave arrays. `--max-events` is explicit and marked `PREFIX_DIAGNOSTIC`.

## Executed falsifiers

Tests cover exact step-splitting energy invariance, multi-record event aggregation, neutral-vs-charged deposition, A-arm exclusion, malformed energy/layer input, invalid event weights, duplicate event IDs, broken Sample-I/Sample-II nesting, charged>total corruption, exact opened-source hashing, in-place source mutation, mocked Uproot file-like integration, duplicate immutable-generation rejection, and injected product-write failure leaving no visible generation. A private isolated aggregation harness using minimal import stubs returned 16 passed with the builder-integration test excluded; only repository CI may authorize merge.

The neutral-deposit fixture is intentionally discriminating: a selected B0 event with proton 2 MeV plus neutron 3 MeV has all-particle `E_dep=5 MeV` and charged-only diagnostic `2 MeV`. Trigger-charge and detector deposited-energy scope are not the same contract.

The first publication implementation is preserved as a rejected child mechanism: independently replacing the NPZ and manifest allowed a crash window with mixed generations. Reordering those two commits is equivalent and was rejected. The current immutable-generation directory transaction removes that mixed-pair window for this diagnostic producer.

## Four role-separated review disposition

- **Detector / Geant4 response lead — ACCEPT H3 / BLOCK detector closure.** Event/stave EDep is the correct invariant truth intermediate, but quenching through digitization remains absent.
- **Adversarial mechanism reviewer — ACCEPT bounded aggregation and immutable-generation publication / REVISE production-scale execution.** Hit-row inference is representation-dependent; source and artifact identity now fail closed. Real ROOT scale/memory and the pre-existing truncated event-ID design remain checks.
- **Statistics / validation reviewer — ACCEPT event statistical unit / BLOCK authorising p-value.** One weight per event and retained nested-trigger membership repair necessary topology, not null calibration.
- **Claims / provenance reviewer — ACCEPT nonauthorising provenance / BLOCK promotion.** A scalar MeV-to-ADC gain cannot substitute for quenching, optical/WLS, SiPM, electronics, sampling and identical reconstruction.

## Scientific and claim boundary

`mc_event_stave_edep_v1` is explicitly `NONAUTHORISING_TRUTH_DIAGNOSTIC`. No production ROOT file was available in this runtime, no Geant4 campaign was rerun, and no DATA/MC discrepancy, p-value, ADC/MeV scale, PID, timing, penetration, energy, pile-up or detector-performance quantity changed. #1049, #1052, #1164 and #1166 remain scientifically open.

## Next highest-value work

First require exact-head/current-base MC Validation CI on the final #1169 head. If it passes, merge without bypassing protection and execute the producer on the immutable production MC source, recording source/output SHA-256, event counts, Sample-I/Sample-II membership counts, sum of weights, sum of squared weights, ESS, runtime and peak memory. Compare legacy H1 charged-hit and H3 event/stave spectra only as a mechanism diagnostic.

Then implement H4: stepwise quenching/visible energy at the Geant4-step level before event aggregation. The next discriminating controls are step subdivision invariance under the chosen Birks formulation, stopping-power/local-dE/dx definition, material-specific quenching parameters and secondary deposition semantics. H5 still requires optical/WLS transport, direct fibre light, SiPM PDE/microcells/noise/recovery, electronics impulse/saturation, digitizer phase/aperture and identical DATA-like reconstruction before any detector-level comparison or #1049 p-value can become authorising.
