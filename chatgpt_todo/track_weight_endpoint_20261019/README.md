# #1628 recursive verification — truth-track event weights and endpoint identity

**2026-10-19. Scientific release: NOT_AUTHORIZED.** Snapshot: main `a61427813344e29047ca9eb9b764182eb29e4c83`; draft PR #1629 parent `3c6b32d583935e94f6ceeb6d3833827bb414c84d`. No production source or canonical ledger is modified. Owner contexts: #880/#1053 (weight carrier), #1608 (MC physics), #1609 (inference), #1594/#1595 (audit).

### TW-01: canonical track-builder still bypasses the source-specific weight adapter

Main `src/ccb_mc_validation/truth/track_builder.py`, Git blob `7a664c25c38efb0610e577814baa50ecb9835d59`, uses `pw_i=np.asarray(weight_chunks[i]).reshape(-1)`; it chooses `float(pw_i[0])` if first entry is finite and otherwise substitutes `1.0`, while emitting `weighted=True` whenever the branch exists. Thus an empty/nonfinite raw vector is laundered into a unit-weight *weighted* record, a negative finite first value passes, and conflicting sibling values such as `[2,5]` silently reduce to 2. This code path contradicts the already-existing mode-bound `weight_adapter.py` (blob `861545b58f2bc9878f97b0b009f5243ed1f84c3b`) and `docs/contracts/MC_WEIGHT_POLICY.md` (blob `4e4d9db45631eed8ecbc8c897de13ec97873eb4b`). **The general first-weight failure was previously identified under #880 and other producers; this is the still-present canonical track-builder path, not a newly invented general issue.**

Downstream `scripts/studies/clusterA_dE_PID_stopping.py` directly consumes these `event_weight` values in weighted MC medians/species summaries/hexbin. Corrected `clusterA_data_side.py` separately validates/aligned event weights for its plot: do NOT attribute the builder's numeric fallback to that distinct downstream panel without tracing the actual use. Production weight-carrier shape and any bias in retained Cluster-A numbers have not been measured in this round.

### TW-02: max-layer sorting is not chronological endpoint evidence

The same builder uses `np.argsort(layers)` and the first/last resulting index for entry and terminal momenta, then maps last observed KE <=1 MeV to `stop`; otherwise outermost layer to `escape`. Synthetic identical hit **multisets** with layers `[0,7,7]` and momentum magnitudes `[.5,.5,.001]` versus `[.5,.001,.5]` GeV/c produce opposite `stop`/`escape` labels under the copied source expressions, although their deposited-energy multiset and deepest layer agree. Reordering two layer-0 hits also changes inferred entry KE. Source lacks a time/step-number/post-step/track-end input. Geant4 distinguishes the pre-step and post-step momenta and the actual track status; layer identity alone cannot establish a physical terminal state.

Do NOT just sort by `Sci_bar_Time` and infer stop: native writer momentum may be pre-step; track termination may occur outside the instrumented detector. Preserve deepest observed layer as an observation; report `STOP_NOT_IDENTIFIABLE` pending a source-bound track-end/post-step contract.

### Executed boundary

17 local Python unittest methods passed normally and under optimization (repeat mode, not 34 independent checks). Nine synthetic weight fixtures were compared with a strict mode-bound reference (seven deliberately invalid/ambiguous vectors rejected there), and 24 permutations confirmed a representation-invariant observed-track summary. A frozen expression transcription and synthetic references were executed; **the full canonical module/ROOT were not locally imported**. The appended `checkout_probe.py` pins the original Git blob and runs the exact module only on a complete checkout; its missing-checkout control exited 2/blocked. The complete tested local packet includes reference code, 17 tests, 9-case JSON, logs and hashes and is available from the audit session.

### Handoff and vetoes

1. Execute `checkout_probe.py --repo <pinned-full-checkout>` and compare its source hash, then add hostile tests to the *canonical* #880 adapter/track-builder test suite. No weight may be invented on malformed branch presence. Bind generator mode and per-event carrier representation; direct-CDF vs legacy-CM source measures remain separate.
2. Inspect native `SD_Det::ProcessHits`, `G4Step::PreStepPoint/PostStepPoint`, track end/status and `Sci_bar_*` ROOT field writer before selecting entry/terminal energy. Reject contradictory TrackID/PDG and ambiguous repeated-layer chronology.
3. Rerun the weighted Cluster-A and stopping/PID figures only from immutable MC with event/track identity, ESS and declared statistical unit. Quarantine stale captions and propagate real changes through #1595 claim/figure/dependency ledgers.
4. Hardware/DAQ, transport, statistics and provenance perspectives here are **one assistant**, not four independent human reviewers. No actual ROOT/Geant4 run, true production impact, physical detector calibration or human sign-off was established.

Primary source: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/tracking.html (step/pre/post/track distinctions). Other context: https://www.geant4.org/collaboration/working_groups/geometryTransport/docs/biasing/Sampling.html and https://arxiv.org/abs/1602.03572 (importance weights/ESS); neither is evidence for this beam dataset.
